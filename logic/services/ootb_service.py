# ootb_service.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, List, Sequence

from datamodel.models import (
    FilterSpec,
    OptionSpec,
    BadgeSpec,
    SummarySpec,
    BadgeBuilder,
    NodeKind,
    NodeRef,
    Summary,
    Badge,
    DetailsData,
    ChildrenResult,
    FileNode,
    FileSet,
    BadgeColor,
    merge_badge_specs,
    status_color,
)
from logic.core.minerva.odata import MinervaODataClient
from logic.core.minerva.cli import MinervaCLIClient

import logging
from ..utils.decorators import log
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


@dataclass(frozen=True)
class TenantMapping:
    # Schema hints (never exposed to UI)
    project_item_type: str = "Ans_Project"
    wr_item_type: str = "Ans_SimulationRequest"
    task_item_type: str = "Ans_SimulationTask"
    data_item_type: str = "Ans_Data"

    # Relationship names
    rel_project_to_wr: str = "Ans_Project_Ans_SimRequest"
    rel_wr_to_task: str = "Ans_SimReq_Task"
    rel_wr_to_input: str = "Ans_SimReq_Input"
    rel_wr_to_output: str = "Ans_SimReq_Deliverable"
    rel_task_to_input: str = "ans_SimTask_Input"
    rel_task_to_output: str = "ans_SimTask_Output"
    rel_data_to_child_data: str = "Ans_DataChild"

class OOTBDisplayPolicy:
    def __init__(self, mapping: TenantMapping):
        self.mapping = mapping
        self._spec_by_item_type = {
            mapping.project_item_type: self._spec_project,
            mapping.wr_item_type: self._spec_wr,
            mapping.task_item_type: self._spec_task,
        }

    def _fmt_date_short(self, v: Any, row: dict) -> Any:
        if v is None:
            return None
        sv = v.strip() if isinstance(v, str) else str(v)
        if not sv:
            return None
        if len(sv) >= 10 and sv[4] == "-" and sv[7] == "-":
            return sv[:10]
        return sv

    def _spec_project(self) -> SummarySpec:
        return SummarySpec(
            title_keys=("name",),
            subtitle_keys=("item_number",),
            fallback_title="Project",
            badges=(
                BadgeSpec("Owner", "modified_by_id", order=30, show_label=False, color="light", views=("header",)),
                BadgeSpec("Created", "created_on", order=50, fmt=self._fmt_date_short, show_label=True, color="light", views=("sidebar",))
            ),
        )

    def _spec_wr(self) -> SummarySpec:
        return SummarySpec(
            title_keys=("name",),
            subtitle_keys=("item_number",),
            fallback_title="Work Request",
            badges=(
                BadgeSpec("State", "state", order=10, show_label=False, color="warning", color_fn=status_color, views=("card",)),
                BadgeSpec("Created", "created_on", order=40, fmt=self._fmt_date_short, show_label=True, color="light", views=("card",)),
                BadgeSpec("Modified", "modified_on", order=50, fmt=self._fmt_date_short, show_label=True, color="light", views=("card",)),
            ),
        )

    def _spec_task(self) -> SummarySpec:
        return SummarySpec(
            title_keys=("name",),
            subtitle_keys=("item_number",),
            fallback_title="Task",
            badges=(
                BadgeSpec("State", "state", order=10, show_label=False, color="warning", color_fn=status_color, views=("header",)),
                BadgeSpec("Created", "created_on", order=40, fmt=self._fmt_date_short, show_label=True, color="light", views=("header",)),
                BadgeSpec("Started", "date_start_actual", order=50, fmt=self._fmt_date_short, show_label=True, color="light", views=("header",)),
                BadgeSpec("Assignees", "assignees", order=60, show_label=False, color="secondary", views=("header",)),
            ),
        )

    def _spec_default(self) -> SummarySpec:
        return SummarySpec(
            title_keys=("keyed_name", "name"),
            subtitle_keys=("item_number", "description"),
            fallback_title="Item",
            badges=(),
        )

    def select_spec(self, item_type: str) -> SummarySpec:
        spec = self._spec_by_item_type.get(item_type, self._spec_default)
        return spec()



class OOTBService:
    """
    Provides UI contract for OOTB Minerva schema.
    The service owns auth, OData, and CLI clients directly.
    """

    def __init__(
        self,
        *,
        base_url: str,
        database: str,
        username: str,
        password: str,
        cli_exe_path: Optional[str] = None,
        mapping: Optional[TenantMapping] = None,
    ):
        self.mapping = mapping or TenantMapping()

        # Create infrastructure clients internally
        self.odata = MinervaODataClient(
            base_url=base_url,
            database=database,
            username=username,
            password=password,
        )
        self.cli = MinervaCLIClient(
            base_url=base_url,
            database=database,
            username=username,
            password=password,
            cli_exe_path=cli_exe_path,
        )

        # Display policy (summary/badges)
        self.display_policy = OOTBDisplayPolicy(self.mapping)
        self.badge_builder = BadgeBuilder()

    DEFAULT_SECTION_TITLES = {
        0: "Projects",
        1: "Work Requests",
        2: "Tasks",
    }
    ITEM_LABELS = {
        0: "Project",
        1: "Work Request",
        2: "Task",
    }

    def default_section_title(self, level: int, fallback: str) -> str:
        return self.DEFAULT_SECTION_TITLES.get(level, fallback)

    def item_label(self, level: int, fallback: str) -> str:
        return self.ITEM_LABELS.get(level, fallback)

    def get_filter_spec(self) -> FilterSpec:
        # Default: filters are not supported
        return {}

    # ---------------- UI Contract ----------------

    def list_level0(self, *, filters: Optional[dict[str, Any]] = None) -> List[NodeRef]:
        """Return Project nodes"""
        select_fields = ["id",
                         "item_number",
                         "keyed_name",
                         "name",
                         "created_on",
                         "modified_on",
                         ]
        rows = self.odata.list(self.mapping.project_item_type, select=select_fields)
        print(f"list_level0: fetched {len(rows)} {self.mapping.project_item_type}")
        out = [
            NodeRef(
                id=str(r["id"]),
                kind=NodeKind.LEVEL0,  # Project
                summary=self._to_summary(r, item_type=self.mapping.project_item_type),
                item_type=self.mapping.project_item_type,
                role="Project",
                can_expand=True,
            )
            for r in rows
        ]
        return out

    def _children_project_to_wr(self, node_id: str) -> List[NodeRef]:
        expand = "related_id" #($select=id,item_number,name,current_state,created_on,modified_on)
        rows = self.odata.list_related(self.mapping.project_item_type, node_id, self.mapping.rel_project_to_wr, expand=expand)

        out = [
            NodeRef(
                id=str(r["id"]),
                kind=NodeKind.LEVEL1,
                summary=self._to_summary(r, item_type=self.mapping.wr_item_type),
                item_type=self.mapping.wr_item_type,
                role="WR",
                can_expand=True,
            )
            for r in rows
        ]
        return out

    def _children_wr_to_task(self, node_id: str) -> List[NodeRef]:
        expand = "related_id" #($select=id,item_number,name,current_state,created_on,date_start_actual,assignees)
        rows = self.odata.list_related(self.mapping.wr_item_type, node_id, self.mapping.rel_wr_to_task, expand=expand)

        out = [
            NodeRef(
                id=str(r["id"]),
                kind=NodeKind.LEVEL2,
                summary=self._to_summary(r, item_type=self.mapping.task_item_type),
                item_type=self.mapping.task_item_type,
                role="Task",
                can_expand=None,
            )
            for r in rows
        ]
        return out

    def get_details(self, node: NodeRef) -> DetailsData:
        """Return summary and optional files"""
        if node.kind == NodeKind.LEVEL0:
            raw = self.odata.get(self.mapping.project_item_type, node.id)
            summary = self._to_summary(raw, item_type=self.mapping.project_item_type)
            return DetailsData(summary, None)

        if node.kind == NodeKind.LEVEL1:
            raw = self.odata.get(self.mapping.wr_item_type, node.id)
            summary = self._to_summary(raw, item_type=self.mapping.wr_item_type)
            return DetailsData(summary, files)

        if node.kind == NodeKind.LEVEL2:
            raw = self.odata.get(self.mapping.task_item_type, node.id)
            summary = self._to_summary(raw, item_type=self.mapping.task_item_type)
            files = self._task_files(node.id)
            return DetailsData(summary, files)

        return DetailsData({"id": node.id}, None)

    def get_children(self, node: NodeRef) -> ChildrenResult:
        """Resolve hierarchy: Project -> WR -> Task"""
        if node.kind == NodeKind.LEVEL0:
            return ChildrenResult(node, self._children_project_to_wr(node.id))
        if node.kind == NodeKind.LEVEL1:
            return ChildrenResult(node, self._children_wr_to_task(node.id))
        return ChildrenResult(node, [])

    # ---------------- Internals ----------------
    def _to_summary(self, row: dict, *, item_type: str) -> Summary:
        """Build a UI Summary using the display policy (spec-based).

        This keeps the service tenant-agnostic while allowing per-item-type
        customization via SummarySpec / BadgeSpec.
        """
        spec = self.display_policy.select_spec(item_type)

        def _pick_first(row: dict, keys: Sequence[str]) -> Optional[str]:
            for k in keys:
                v = row.get(k)
                if v is None:
                    continue
                if isinstance(v, str):
                    v = v.strip()
                    if not v:
                        continue
                    return v
                return str(v)
            return None

        title = _pick_first(row, spec.title_keys) or spec.fallback_title
        subtitle = _pick_first(row, spec.subtitle_keys)
        badges = self.badge_builder.build(row, spec.badges)

        # print("item_type =", item_type)
        # print("row.name =", row.get("name"))
        # print("row.item_number =", row.get("item_number"))
        # print("title =", title)
        # print("subtitle =", subtitle)
        # print("badges =", badges)

        return Summary(title=title, subtitle=subtitle, badges=badges)

    def _list_file_tree(
        self,
        *,
        root_item_type: str,
        root_id: str,
        root_relationship_name: str,
        expand: str,
    ) -> List[FileNode]:
        """
        Recursively collect files/folders starting from a root item.
        Depth 0:
            root_item_type + root_relationship_name
            e.g. WR -> Ans_SimReq_Input
        Depth > 0:
            Ans_Data -> Ans_DataChild
        """
        def _recurse(parent_id: str, depth: int) -> List[FileNode]:
            flattened: List[FileNode] = []

            item_type = root_item_type if depth == 0 else self.mapping.data_item_type
            rel_name = root_relationship_name if depth == 0 else self.mapping.rel_data_to_child_data

            items = self.odata.list_related(
                item_type,
                parent_id,
                rel_name,
                expand=expand,
            )

            for item in items:
                is_folder = item.get("is_folder") == "1"

                flattened.append(
                    FileNode(
                        id=str(item["id"]),
                        name=str(item.get("keyed_name") or ""),
                        is_folder=is_folder,
                        size=int(item.get("file_size") or 0),
                        modified_on=item.get("modified_on"),
                        depth=depth,
                        vault_id=item.get("local_file@aras.id") if not is_folder else "None",
                        classification=item.get("classification"),
                    )
                )

                if is_folder:
                    flattened.extend(_recurse(str(item["id"]), depth + 1))

            return flattened

        return _recurse(root_id, 0)

    def _wr_files(self, wr_id: str):
        """Fetch all files and folders recursively for a given Work Request."""
        results = {"inputs": [], "outputs": []}
        expand = "related_id($select=id,keyed_name,file_size,,modified_on,classification,is_folder,local_file)"

        rel_map = {
            self.mapping.rel_wr_to_input: "inputs",
            self.mapping.rel_wr_to_output: "outputs",
        }

        for rel, category in rel_map.items():
            results[category] = self._list_file_tree(
                root_item_type=self.mapping.wr_item_type,
                root_id=wr_id,
                root_relationship_name=rel,
                expand=expand,
            )

        return FileSet(results["inputs"], results["outputs"])

    def _task_files(self, task_id: str):
        """Fetch all files and folders recursively for a given Task."""
        results = {"inputs": [], "outputs": []}
        expand = "related_id($select=id,keyed_name,file_size,,modified_on,classification,is_folder,local_file)"

        rel_map = {
            self.mapping.rel_task_to_input: "inputs",
            self.mapping.rel_task_to_output: "outputs",
        }

        for rel, category in rel_map.items():
            results[category] = self._list_file_tree(
                root_item_type=self.mapping.task_item_type,
                root_id=task_id,
                root_relationship_name=rel,
                expand=expand,
            )

        return FileSet(results["inputs"], results["outputs"])

    # ---------------- Download to Server ----------------
    def download_to_server_via_cli(self, ans_data_id: str, dest: str) -> str:
        ret = self.cli.download(remote=f"ans_Data/{ans_data_id}", local=dest)
        print(f"CLI download result: {ret}")
        return dest

    def download_to_server_via_odata(self, vault_id: str, dest: str) -> str:
        print(f"Initiating OData download for vault_id={vault_id} to dest={dest}")
        ret = self.odata.download(vault_id, dest)
        print(f"OData download result: {ret}")
        return dest


# ---------------- Utility Functions ----------------
def normalize_options(raw: Any) -> List[OptionSpec]:
        """
        Normalize into Dash dropdown options: [{"label": ..., "value": ...}, ...]
        """
        if not raw:
            return []
        if isinstance(raw, list):
            if all(isinstance(x, dict) and "label" in x and "value" in x for x in raw):
                return raw
            # allow list of primitives
            out: List[OptionSpec] = []
            for x in raw:
                out.append({"label": str(x), "value": x})
            return out
        return []


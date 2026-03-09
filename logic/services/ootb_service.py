# ootb_service.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Iterable, List, Protocol, Sequence, Dict, TypeAlias, TypedDict

from datamodel.models import FileSet, NodeKind, NodeRef, Summary, Badge, DetailsData, ChildrenResult, FileNode
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


class OptionSpec(TypedDict):
    label: str
    value: Any

class FilterFieldSpec(TypedDict, total=False):
    label: str
    enabled: bool
    options: List[OptionSpec]
    default: Any
    placeholder: str  # optional UI hint
    multi: bool
    component: str   # "dropdown", "input", "radio" etc. (optional UI hint)

FilterSpec: TypeAlias = dict[str, FilterFieldSpec]

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

TextFormatter = Callable[[Any, dict], Any]

@dataclass(frozen=True)
class BadgeSpec:
    label: str
    key: str
    order: int = 100
    fmt: Optional[TextFormatter] = None
    when: Optional[Callable[[dict], bool]] = None


@dataclass(frozen=True)
class SummarySpec:
    title_keys: Sequence[str]
    subtitle_keys: Sequence[str]
    fallback_title: str = "Item"
    title_fmt: Optional[TextFormatter] = None
    subtitle_fmt: Optional[TextFormatter] = None
    badges: Sequence[BadgeSpec] = ()


# ----------------------------
# BadgeBuilder (implementation unit)
# ----------------------------

class BadgeBuilder:
    def _s(self, v: Any) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, str):
            vv = v.strip()
            return vv or None
        return str(v)

    def _badge(self, label: str, value: Any) -> Optional["Badge"]:
        sv = self._s(value)
        if sv is None:
            return None
        return Badge(label=label, value=sv)

    def build(self, row: dict, specs: Sequence[BadgeSpec]) -> List["Badge"]:
        out: List["Badge"] = []
        for s in sorted(specs, key=lambda x: x.order):
            if s.when and not s.when(row):
                continue
            raw = row.get(s.key)
            if s.fmt:
                raw = s.fmt(raw, row)
            b = self._badge(s.label, raw)
            if b:
                out.append(b)
        return out


def get_item_type(row: dict) -> str:
    return (row.get("item_type") or "").strip() or "UNKNOWN"


class OOTBDisplayPolicy:
    def __init__(self, mapping: TenantMapping):
        self.mapping = mapping
        self._spec_by_item_type = {
            mapping.project_item_type: self._spec_project,
            mapping.wr_item_type: self._spec_wr,
            # mapping.task_item_type: self._spec_task,
            # mapping.data_item_type: self._spec_data,
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
            title_keys=("keyed_name", "name"),
            subtitle_keys=("description", "item_number", "_model_name"),
            fallback_title="Project",
            badges=(
                BadgeSpec("State", "state", order=10),
                BadgeSpec("Owner", "owned_by_id", order=30),
                BadgeSpec("Modified", "modified_on", order=50, fmt=self._fmt_date_short),
                BadgeSpec("Type", "_model_name", order=90),
            ),
        )

    def _spec_wr(self) -> SummarySpec:
        return SummarySpec(
            title_keys=("item_number", "keyed_name", "name"),
            subtitle_keys=("description", "_model_name"),
            fallback_title="Work Request",
            badges=(
                BadgeSpec("State", "state", order=10),
                BadgeSpec("Status", "status", order=20),
                BadgeSpec("Owner", "owned_by_id", order=30),
                BadgeSpec("Created", "created_on", order=40, fmt=self._fmt_date_short),
                BadgeSpec("Modified", "modified_on", order=50, fmt=self._fmt_date_short),
                BadgeSpec("Classification", "classification", order=60),
                BadgeSpec("Type", "_model_name", order=90),
            ),
        )

    def _spec_default(self) -> SummarySpec:
        return SummarySpec(
            title_keys=("keyed_name", "name"),
            subtitle_keys=("item_number", "description", "_model_name"),
            fallback_title="Item",
            badges=(),
        )

    def select_spec(self, row: dict) -> SummarySpec:
        item_type = get_item_type(row)
        builder = self._spec_by_item_type.get(item_type, self._spec_default)
        return builder()




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

    def get_filter_spec(self) -> FilterSpec:
        # Default: filters are not supported
        return {}

    # ---------------- UI Contract ----------------

    def list_level0(self, *, filters: Optional[dict[str, Any]] = None) -> List[NodeRef]:
        """Return Project nodes"""
        rows = self.odata.list(self.mapping.project_item_type)
        return [
            NodeRef(
                id=str(r["id"]),
                kind=NodeKind.LEVEL0,  # Project
                summary=self._to_summary(r, fallback_title="Item"),
                item_type=self.mapping.project_item_type,
                role="Project",
                can_expand=True,
            )
            for r in rows
        ]

    def get_children(self, node: NodeRef) -> ChildrenResult:
        """Resolve hierarchy: Project -> WR -> Task"""
        if node.kind == NodeKind.LEVEL0:
            return ChildrenResult(node, self._children_project_to_wr(node.id))
        if node.kind == NodeKind.LEVEL1:
            return ChildrenResult(node, self._children_wr_to_task(node.id))
        return ChildrenResult(node, [])

    def get_details(self, node: NodeRef) -> DetailsData:
        """Return summary and optional files"""
        if node.kind == NodeKind.LEVEL0:
            raw = self.odata.get(self.mapping.project_item_type, node.id)
            summary = self._to_summary(raw, fallback_title=node.summary.title or "Item")
            return DetailsData(summary, None)

        if node.kind == NodeKind.LEVEL1:
            raw = self.odata.get(self.mapping.wr_item_type, node.id)
            summary = self._to_summary(raw, fallback_title=node.summary.title or "Item")
            return DetailsData(summary, files)

        if node.kind == NodeKind.LEVEL2:
            raw = self.odata.get(self.mapping.task_item_type, node.id)
            summary = self._to_summary(raw, fallback_title=node.summary.title or "Item")
            files = self._task_files(node.id)
            return DetailsData(summary, files)

        return DetailsData({"id": node.id}, None)

    # ---------------- Internals ----------------

    def _s(self, v: Any) -> Optional[str]:
        """Convert to a displayable string; return None for empty values."""
        if v is None:
            return None
        if isinstance(v, str):
            vv = v.strip()
            return vv or None
        return str(v)

    def _badge(self, label: str, value: Any) -> Optional[Badge]:
        sv = self._s(value)
        if sv is None:
            return None
        return Badge(label=label, value=sv)

    def _badges_by_specs(self, row: dict, specs: Sequence[BadgeSpec]) -> List[Badge]:
        out: List[Badge] = []

        for s in sorted(specs, key=lambda x: x.order):
            if s.when and not s.when(row):
                continue

            value = row.get(s.key)
            if s.fmt:
                value = s.fmt(value, row)

            b = self._badge(s.label, value)
            if b:
                out.append(b)

        return out

    def _to_summary(self, row: dict, *, fallback_title: str = "Item") -> Summary:
        """Build a UI Summary using the display policy (spec-based).

        This keeps the service tenant-agnostic while allowing per-item-type
        customization via SummarySpec / BadgeSpec.
        """
        spec = self.display_policy.select_spec(row)

        def _pick(keys, *, fmt: Optional[Callable[[Any, dict], Any]] = None) -> Optional[str]:
            for k in keys:
                v = row.get(k)
                if fmt:
                    v = fmt(v, row)
                sv = self._s(v)
                if sv is not None:
                    return sv
            return None

        title = _pick(spec.title_keys, fmt=spec.title_fmt) or (fallback_title or spec.fallback_title)
        subtitle = _pick(spec.subtitle_keys, fmt=spec.subtitle_fmt)
        badges = self._badges_by_specs(row, spec.badges)

        return Summary(title=title, subtitle=subtitle, badges=badges)

    def _children_project_to_wr(self, node_id: str) -> List[NodeRef]:
        rows = self.odata.list_related(self.mapping.project_item_type, node_id, self.mapping.rel_project_to_wr)
        return [
            NodeRef(
                id=str(r["id"]),
                kind=NodeKind.LEVEL1,
                summary=self._to_summary(r, fallback_title="Item"),
                item_type=self.mapping.wr_item_type,
                role="WR",
                can_expand=True,
            )
            for r in rows
        ]

    def _children_wr_to_task(self, node_id: str) -> List[NodeRef]:
        rows = self.odata.list_related(self.mapping.wr_item_type, node_id, self.mapping.rel_wr_to_task)
        return [
            NodeRef(
                id=str(r["id"]),
                kind=NodeKind.LEVEL2,
                summary=self._to_summary(r, fallback_title="Item"),
                item_type=self.mapping.task_item_type,
                role="Task",
                can_expand=None,
            )
            for r in rows
        ]


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
        expand = "related_id($select=id,keyed_name,file_size,classification,is_folder,local_file)"

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
        expand = "related_id($select=id,keyed_name,file_size,classification,is_folder,local_file)"

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

    def download_to_server_via_cli(self, ans_data_id: str, dest: str) -> str:
        ret = self.cli.download(remote=f"ans_Data/{ans_data_id}", local=dest)
        print(f"CLI download result: {ret}")
        return dest

    def download_to_server_via_odata(self, vault_id: str, dest: str) -> str:
        print(f"Initiating OData download for vault_id={vault_id} to dest={dest}")
        ret = self.odata.download(vault_id, dest)
        print(f"OData download result: {ret}")
        return dest
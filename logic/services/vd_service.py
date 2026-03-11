# vd_service.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, List

from logic.services.ootb_service import (
    OOTBDisplayPolicy,
    OOTBService,
    BadgeSpec,
    SummarySpec,
    TenantMapping,
    FilterSpec,
    get_item_type,
    normalize_options,
)
from datamodel.models import (
    OptionSpec,
    status_color,
    BadgeBuilder,
    NodeKind,
    NodeRef,
    Summary,
    DetailsData,
    ChildrenResult,
    merge_badge_specs,
)
import logging
from ..utils.decorators import log
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


@dataclass(frozen=True)
class VDMapping(TenantMapping):
    sr_item_type: str = "VD_SimulationRequest"
    rel_sr_to_wr: str = "VD_SimRequest_WorkRequest"
    id_of_list_development_year: str = "6158D0BE38234B1E82E1C88D0C79C121"
    id_of_list_product_category: str = "62841ADCFAA44C53BE010BFF1AC1C70D"


class VDDisplayPolicy:
    def __init__(self, base: OOTBDisplayPolicy, mapping: TenantMapping):
        self.base = base
        self.mapping = mapping

        # Only VD-only item types need patch
        self._patch_by_item_type = {
            mapping.project_item_type: self._patch_vd_project,
            mapping.sr_item_type: self._patch_vd_sr,
            mapping.wr_item_type: self._patch_vd_wr,
        }

    def select_spec(self, item_type: str) -> SummarySpec:
        base_spec = self.base.select_spec(item_type)
        patch = self._patch_by_item_type.get(item_type)
        return patch(base_spec) if patch else base_spec

    def _patch_vd_project(self, spec: SummarySpec) -> SummarySpec:
        return SummarySpec(
            title_keys=("name",),
            subtitle_keys=("item_number",),
            fallback_title="Project",
            badges=(
                BadgeSpec("State", "state", order=10, show_label=False, color="success", color_fn=status_color, views=("sidebar",)),
                BadgeSpec("Year", "_development_year", order=20, show_label=False, color="secondary",views=("sidebar",)),
                BadgeSpec("Product", "_product_category", order=30, show_label=False, color="info", views=("sidebar",)),
                BadgeSpec("Model", "_model_name", order=40, show_label=False, color="light", views=("header",)),
                BadgeSpec("Created", "created_on", order=50, fmt=self.base._fmt_date_short, show_label=True, color="light", views=("header",))
            ),
        )

    def stage_color(self, stage):
        s = str(stage).lower() if stage else ""
        if any(x in s for x in ["pre"]): return "info"
        if any(x in s for x in ["pv"]): return "warning"
        if any(x in s for x in ["pr"]): return "success"
        if any(x in s for x in ["sr"]): return "danger"
        return "secondary"

    def _patch_vd_sr(self, spec: SummarySpec) -> SummarySpec:
        # Example: change subtitle priority and add VD badges
        return SummarySpec(
            title_keys=("keyed_name",),
            subtitle_keys=("_simulation_type", ),
            fallback_title="Simulation Request",
            badges=(
                BadgeSpec("State", "state", order=20, show_label=False, color="warning", color_fn=status_color, views=("card",)),
                BadgeSpec("Stage", "_development_stage", order=30, show_label=False, color="light", color_fn=self.stage_color, views=("card",)),
                BadgeSpec("Type", "_request_type", order=40, show_label=False, color="light", views=("card",)),
                BadgeSpec("Created", "created_on", order=60, fmt=self.base._fmt_date_short, show_label=True, color="light", views=("card",)),
                BadgeSpec("Target", "_target_date", order=70, fmt=self.base._fmt_date_short, show_label=True, color="light", views=("card",)),
            ),
        )

    def _patch_vd_wr(self, spec: SummarySpec) -> SummarySpec:
        # Example: change subtitle priority and add VD badges
        return SummarySpec(
            title_keys=("name",),
            subtitle_keys=("item_number", ),
            fallback_title="Work Request",
            badges=(
                BadgeSpec("State", "current_state", order=10, show_label=False, color="warning", color_fn=status_color, views=("header",)),
                #BadgeSpec("Created", "created_on", order=60, fmt=self.base._fmt_date_short, show_label=True, color="light", views=("header",)),
                BadgeSpec("Modified", "modified_on", order=60, fmt=self.base._fmt_date_short, show_label=True, color="light", views=("header",)),
            ),
        )

class VDService(OOTBService):
    """VD schema extends OOTB hierarchy by inserting SR level"""

    def __init__(
        self,
        *,
        base_url: str,
        database: str,
        username: str,
        password: str,
        cli_exe_path: Optional[str] = None,
        mapping: Optional[VDMapping] = None,
    ):
        super().__init__(
            base_url=base_url,
            database=database,
            username=username,
            password=password,
            cli_exe_path=cli_exe_path,
            mapping=mapping or VDMapping(),
        )
        self.mapping: VDMapping = self.mapping

        # Patch display policy to include VD-only item types
        self.display_policy = VDDisplayPolicy(OOTBDisplayPolicy(self.mapping), self.mapping)
        self.badge_builder = BadgeBuilder()

    DEFAULT_SECTION_TITLES = {
        0: "Projects",
        1: "Simulation Requests",
        2: "Work Requests",
    }
    ITEM_LABELS = {
        0: "Project",
        1: "Simulation Request",
        2: "Work Request",
    }

    def get_filter_spec(self) -> FilterSpec:
        year_opts = normalize_options(self.get_filter_years())
        product_opts = normalize_options(self.get_filter_products())

        year_default = year_opts[-1]["value"] if year_opts else None
        product_default = None

        return {
            "year": {
                "enabled": True,
                "label": "Year",
                "options": year_opts,
                "default": year_default,
                "placeholder": "Select year",
                "multi": False,
            },
            "product": {
                "enabled": True,
                "label": "Product",
                "options": product_opts,
                "default": product_default,
                "placeholder": "Select product",
                "multi": False,
            },
        }

    def list_level0(self, *, filters: Optional[dict[str, Any]] = None) -> List[NodeRef]:
        """Return Project nodes"""
        filters = filters or {}
        year = filters.get("year")
        product = filters.get("product")
        filter_clauses = []

        if year is not None and str(year).strip() != "":
            filter_clauses.append(f"_development_year eq '{year}'")
        if product is not None and str(product).strip() != "":
            filter_clauses.append(f"_product_category eq '{product}'")
        filter = " and ".join(filter_clauses) if filter_clauses else None

        select_fields = ["id",
                         "item_number",
                         "name",
                         "_model_name",
                         "state",
                         "_development_year",
                         "_product_category"
                         ]

        rows = self.odata.list(self.mapping.project_item_type, select=select_fields, filter=filter)

        out = []
        for r in rows:
            row = dict(r)
            row["item_type"] = self.mapping.project_item_type

            out.append(
                NodeRef(
                    id=str(row["id"]),
                    kind=NodeKind.LEVEL0,
                    summary=self._to_summary(row, item_type=self.mapping.project_item_type),
                    item_type=self.mapping.project_item_type,
                    role="Project",
                    can_expand=None,
                )
            )
        return out

    def get_children(self, node: NodeRef) -> ChildrenResult:
        """Project -> SR -> WR"""
        if node.kind == NodeKind.LEVEL0:
            return ChildrenResult(node, self._children_project_to_sr(node.id))
        if node.kind == NodeKind.LEVEL1:
            return ChildrenResult(node, self._children_sr_to_wr(node.id))
        return ChildrenResult(node, [])

    def get_details(self, node: NodeRef) -> DetailsData:
        """WR holds files in VD"""
        if node.kind == NodeKind.LEVEL1:
            raw = self.odata.get(self.mapping.sr_item_type, node.id)
            summary = self._to_summary(raw, item_type=self.mapping.sr_item_type)
            return DetailsData(summary, None)

        if node.kind == NodeKind.LEVEL2:
            raw = self.odata.get(self.mapping.wr_item_type, node.id)
            summary = self._to_summary(raw, item_type=self.mapping.wr_item_type)
            files = self._wr_files(node.id)
            return DetailsData(summary, files)

        return super().get_details(node)

    def get_filter_years(self):
        years = self.odata.list_values(self.mapping.id_of_list_development_year)
        return years

    def get_filter_products(self):
        products = self.odata.list_values(self.mapping.id_of_list_product_category)
        return products

    def _children_project_to_sr(self, node_id: str) -> List[NodeRef]:
        filter = f"_project_id eq '{node_id}'"
        select_fields = ["id",
                         "_item_number",
                         "_name",
                         "state",
                         "_development_stage",
                         "_request_type",
                         "_simulation_type",
                         "created_on",
                         "_target_date",
                         "_background",
                         ]

        rows = self.odata.list("VD_SimulationRequest", filter=filter)
        return [
            NodeRef(
                id=str(r["id"]),
                kind=NodeKind.LEVEL1,
                summary=self._to_summary(r, item_type=self.mapping.sr_item_type),
                item_type=self.mapping.sr_item_type,
                role="SR",
                can_expand=None,
            )
            for r in rows
        ]

    def _children_sr_to_wr(self, node_id: str) -> List[NodeRef]:
        expand = "related_id($select=id,item_number,name,keyed_name,current_state,created_on,modified_on,_simulation_type)"
        rows = self.odata.list_related(self.mapping.sr_item_type, node_id, self.mapping.rel_sr_to_wr, expand=expand)
        return [
            NodeRef(
                id=str(r["id"]),
                kind=NodeKind.LEVEL2,
                summary=self._to_summary(r, item_type=self.mapping.wr_item_type),
                item_type=self.mapping.wr_item_type,
                role="WR",
                can_expand=None,
            )
            for r in rows
        ]



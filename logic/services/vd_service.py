# vd_service.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List

from logic.services.ootb_service import OOTBDisplayPolicy, OOTBService, BadgeSpec, SummarySpec, TenantMapping, FilterSpec, get_item_type, normalize_options
from datamodel.models import NodeKind, NodeRef, Summary, DetailsData, ChildrenResult

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
            mapping.sr_item_type: self._patch_vd_sr,
        }

    def _patch_vd_sr(self, spec: SummarySpec) -> SummarySpec:
        # Example: change subtitle priority and add VD badges
        return SummarySpec(
            title_keys=("keyed_name", "name"),
            subtitle_keys=("description", "item_number", "_model_name"),
            fallback_title="Simulation Request",
            badges=tuple(spec.badges) + (
                BadgeSpec("State", "state", order=10),
                BadgeSpec("Owner", "owned_by_id", order=30),
                BadgeSpec("Modified", "modified_on", order=50, fmt=self.base._fmt_date_short),
            ),
        )

    def select_spec(self, row: dict) -> SummarySpec:
        base_spec = self.base.select_spec(row)

        item_type = get_item_type(row)
        patch = self._patch_by_item_type.get(item_type)
        return patch(base_spec) if patch else base_spec


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
        self.mapping: VDMapping = self.mapping  # type: ignore

        # Patch display policy to include VD-only item types
        self.display_policy = VDDisplayPolicy(OOTBDisplayPolicy(self.mapping), self.mapping)

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

    def list_level0(self, *, year: Optional[int] = None, product: Optional[str] = None) -> List[NodeRef]:
        """Return Project nodes"""
        filters = []
        if year is not None and str(year).strip() != "":
            filters.append(f"_development_year eq '{year}'")
        if product is not None and str(product).strip() != "":
            filters.append(f"_product_category eq '{product}'")
        filter = " and ".join(filters) if filters else None

        select_fields = ["id", "item_number", "name", "_model_name", "state"]

        rows = self.odata.list(self.mapping.project_item_type, select=select_fields, filter=filter)
        return [
            NodeRef(
                id=str(r["id"]),
                kind=NodeKind.LEVEL0,
                summary=self._to_summary(r, fallback_title="Item"),
                item_type=self.mapping.project_item_type,
                role="Project",
                can_expand=None,
            )
            for r in rows
        ]

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
            summary = self._to_summary(raw, fallback_title=node.summary.title or "Item")
            return DetailsData(summary, None)

        if node.kind == NodeKind.LEVEL2:
            raw = self.odata.get(self.mapping.wr_item_type, node.id)
            summary = self._to_summary(raw, fallback_title=node.summary.title or "Item")
            files = self._wr_files(node.id)
            return DetailsData(summary, files)

        return super().get_details(node)

    # ---- VD specific relations ----
    def get_filter_years(self):
        years = self.odata.list_values(self.mapping.id_of_list_development_year)
        return years

    def get_filter_products(self):
        products = self.odata.list_values(self.mapping.id_of_list_product_category)
        return products

    def _children_project_to_sr(self, node_id: str) -> List[NodeRef]:
        filter = f"_project_id eq '{node_id}'"
        rows = self.odata.list("VD_SimulationRequest", filter=filter)
        return [
            NodeRef(
                id=str(r["id"]),
                kind=NodeKind.LEVEL1,
                summary=self._to_summary(r, fallback_title="Item"),
                item_type=self.mapping.sr_item_type,
                role="SR",
                can_expand=None,
            )
            for r in rows
        ]

    def _children_sr_to_wr(self, node_id: str) -> List[NodeRef]:
        rows = self.odata.list_related(self.mapping.sr_item_type, node_id, self.mapping.rel_sr_to_wr)
        return [
            NodeRef(
                id=str(r["id"]),
                kind=NodeKind.LEVEL2,
                summary=self._to_summary(r, fallback_title="Item"),
                item_type=self.mapping.wr_item_type,
                role="WR",
                can_expand=None,
            )
            for r in rows
        ]

    # def _children_sr_to_wr(self, node_id: str) -> List[NodeRef]:
    #     expand_str = "related_id($select=id,item_number,name,classification,created_on,current_state,owned_by_id,_simulation_type)"
    #     rows = self.odata.list_related(
    #         self.mapping.sr_item_type,
    #         node_id,
    #         self.mapping.rel_sr_to_wr,
    #         expand=expand_str,
    #     )

    #     out: List[NodeRef] = []
    #     for r in rows:
    #         rel = r.get("related_id") or {}
    #         wr_id = rel.get("id")
    #         if not wr_id:
    #             # related_id가 비어있으면 skip (데이터 품질 문제 / expand 실패 등)
    #             continue

    #         out.append(
    #             NodeRef(
    #                 id=str(wr_id),
    #                 kind=NodeKind.LEVEL2,
    #                 summary=self._to_summary(rel, fallback_title="Item"),
    #                 item_type=self.mapping.wr_item_type,
    #                 role="WR",
    #                 can_expand=None,
    #             )
    #         )
    #     return out
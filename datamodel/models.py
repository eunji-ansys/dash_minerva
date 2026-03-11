# datamodel/models.py
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Sequence, TypeAlias, TypedDict, List, Optional, Literal, Tuple


class OptionSpec(TypedDict):
    label: str
    value: Any


class FilterFieldSpec(TypedDict, total=False):
    label: str
    enabled: bool
    options: List[OptionSpec]
    default: Any
    placeholder: str
    multi: bool
    component: str


FilterSpec: TypeAlias = dict[str, FilterFieldSpec]
Filters: TypeAlias = dict[str, Any]

TextFormatter = Callable[[Any, dict], Any]

BadgeColor = Literal[
    "primary",
    "secondary",
    "success",
    "danger",
    "warning",
    "info",
    "light",
    "dark",
]

def status_color(status):
    s = str(status).lower() if status else ""
    if any(x in s for x in ["new",]): return "secondary"
    if any(x in s for x in ["active", "open", "success", "running"]): return "light"
    if any(x in s for x in ["close", "closed", "complete", "paused"]): return "dark"
    if any(x in s for x in ["new","accepted"]): return "warning"
    if any(x in s for x in ["progress", "queued", "in work"]): return "success"
    if any(x in s for x in ["in review"]): return "info"
    if any(x in s for x in ["failed", "error"]): return "danger"
    return "secondary"

@dataclass(frozen=True)
class BadgeSpec:
    label: str
    key: str
    order: int = 100
    fmt: Optional[TextFormatter] = None
    when: Optional[Callable[[dict], bool]] = None
    show_label: bool = True
    color: Optional[BadgeColor] = None
    color_fn: Optional[Callable[[Any], BadgeColor]] = None
    views: Tuple[str, ...] = ("sidebar", "header", "card")


@dataclass(frozen=True)
class SummarySpec:
    title_keys: Sequence[str]
    subtitle_keys: Sequence[str]
    fallback_title: str = "Item"
    title_fmt: Optional[TextFormatter] = None
    subtitle_fmt: Optional[TextFormatter] = None
    badges: Sequence[BadgeSpec] = ()


def merge_badge_specs(
    base: Sequence[BadgeSpec],
    override: Sequence[BadgeSpec],
) -> tuple[BadgeSpec, ...]:
    """
    Merge badge specs by key.

    Rules:
    - base badges are the default
    - override badges replace base badges with the same key
    - new override badges are appended
    - final result is sorted by order
    """
    merged: "OrderedDict[str, BadgeSpec]" = OrderedDict()

    for spec in base:
        merged[spec.key] = spec

    for spec in override:
        merged[spec.key] = spec

    return tuple(sorted(merged.values(), key=lambda x: x.order))


@dataclass(frozen=True)
class Badge:
    label: str
    value: str
    show_label: bool = True
    color: BadgeColor = "light"
    views: Tuple[str, ...] = ("sidebar", "header", "card")


class BadgeBuilder:
    def _s(self, v: Any) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, str):
            vv = v.strip()
            return vv or None
        return str(v)

    def _resolve_color(self, *, raw_value: Any, spec: BadgeSpec) -> BadgeColor:
        if spec.color_fn:
            try:
                return spec.color_fn(raw_value)
            except Exception:
                pass

        if spec.color:
            return spec.color

        return "light"

    def build(self, row: dict, specs: Sequence[BadgeSpec]) -> List["Badge"]:
        out: List["Badge"] = []

        for s in sorted(specs, key=lambda x: x.order):
            if s.when and not s.when(row):
                continue

            raw = row.get(s.key)
            if s.fmt:
                raw = s.fmt(raw, row)

            #print("### badge ", s.key, ": ", raw)

            value = self._s(raw)
            if value is None:
                continue

            out.append(
                Badge(
                    label=s.label,
                    value=value,
                    show_label=s.show_label,
                    color=self._resolve_color(raw_value=raw, spec=s),
                    views=s.views,
                )
            )

        return out


class NodeKind(str, Enum):
    LEVEL0 = "level0"
    LEVEL1 = "level1"
    LEVEL2 = "level2"

    def next(self) -> Optional["NodeKind"]:
        if self == NodeKind.LEVEL0:
            return NodeKind.LEVEL1
        if self == NodeKind.LEVEL1:
            return NodeKind.LEVEL2
        return None

    def is_leaf(self) -> bool:
        return self.next() is None


@dataclass(frozen=True)
class NodeRef:
    id: str
    kind: NodeKind
    summary: Summary
    item_type: str
    role: str
    can_expand: Optional[bool] = None


@dataclass(frozen=True)
class Summary:
    title: str
    subtitle: Optional[str]
    badges: List[Badge]


@dataclass(frozen=True)
class FileNode:
    id: str
    name: str
    is_folder: bool
    size: int = 0
    modified_on: Optional[str] = None
    depth: int = 0
    vault_id: Optional[str] = None
    classification: Optional[str] = None


@dataclass(frozen=True)
class FileSet:
    inputs: List[FileNode]
    outputs: List[FileNode]


@dataclass(frozen=True)
class DetailsData:
    summary: Summary
    files: Optional[FileSet] = None


@dataclass(frozen=True)
class ChildrenResult:
    parent: NodeRef
    children: List[NodeRef]

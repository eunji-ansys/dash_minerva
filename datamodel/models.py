# datamodel/models.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class NodeKind(str, Enum):
    """
    UI hierarchy levels (tenant/schema independent).
    """
    LEVEL0 = "level0"
    LEVEL1 = "level1"
    LEVEL2 = "level2"

    def next(self) -> Optional["NodeKind"]:
        """
        Return the next UI level.
        LEVEL0 -> LEVEL1 -> LEVEL2 -> None (leaf)
        """
        if self == NodeKind.LEVEL0:
            return NodeKind.LEVEL1
        if self == NodeKind.LEVEL1:
            return NodeKind.LEVEL2
        return None

    def is_leaf(self) -> bool:
        return self.next() is None


@dataclass(frozen=True)
class NodeRef:
    """
    Lightweight handle pointing to a node location.
    Does NOT contain actual server data.

    - item_type: schema type hint (e.g., ans_Project, VD_SimulationRequest, Ans_SimulationRequest)
                UI must NOT branch on this.
    - role: business/UI label (e.g., Project, SR, WR, Task)
    - can_expand: service hint for tree UI.
        * True  => show expand UI, allow get_children() call
        * False => leaf, do not call get_children()
        * None  => unknown (fallback to kind-based logic if needed)
    """
    id: str
    kind: NodeKind
    summary: Summary
    item_type: str
    role: str
    can_expand: Optional[bool] = None


@dataclass(frozen=True)
class Badge:
    label: str
    value: str


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
    depth: int = 0
    file_id: Optional[str] = None
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

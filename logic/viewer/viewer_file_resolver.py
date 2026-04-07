from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class SupportsODataDownload(Protocol):
    def download_to_server_via_odata(self, vault_id: str, dest: str) -> str:
        ...


@dataclass(frozen=True)
class ViewerFileRef:
    file_id: str
    file_name: str
    vault_id: str


@dataclass(frozen=True)
class ViewerFile:
    file_name: str
    local_path: Path
    entity_handle: Any | None = None

    @property
    def suffix(self) -> str:
        return self.local_path.suffix.lower()

    def require_local_path(self) -> Path:
        return self.local_path


FIXED_VIEWER_TYPES = {
    ".pdf": "document",
    ".txt": "text",
    ".log": "text",
    ".xml": "text",
    ".json": "text",
    ".csv": "table",
    ".xlsx": "table",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".gif": "image",
    ".bmp": "image",
    ".svg": "image",
    ".webp": "image",
    # future
    # ".step": "cad",
    # ".stp": "cad",
    # ".iges": "cad",
    # ".igs": "cad",
}

PATTERN_VIEWER_TYPES = [
    (r"\.s\d+p", "snp"),
]


def get_viewer_type(file_name: str | None) -> str | None:
    if not file_name:
        return None

    ext = Path(file_name).suffix.lower()

    if ext in FIXED_VIEWER_TYPES:
        return FIXED_VIEWER_TYPES[ext]

    for pattern, viewer_type in PATTERN_VIEWER_TYPES:
        if re.fullmatch(pattern, ext):
            return viewer_type

    return None


def resolve_viewer_file(
    *,
    service: SupportsODataDownload,
    viewer_file_ref: ViewerFileRef,
    temp_viewer_path: str,
    storage_scope=None,
) -> ViewerFile:
    request_id = uuid.uuid4().hex.upper()
    request_dir = Path(temp_viewer_path) / request_id
    request_dir.mkdir(parents=True, exist_ok=True)

    local_path = request_dir / Path(viewer_file_ref.file_name).name

    service.download_to_server_via_odata(
        vault_id=viewer_file_ref.vault_id,
        dest=str(local_path),
    )

    if not local_path.exists():
        raise FileNotFoundError(f"Downloaded file not found: {local_path}")

    entity_handle = None
    if storage_scope is not None:
        entity_handle = storage_scope.store(local_path)

    return ViewerFile(
        file_name=viewer_file_ref.file_name,
        local_path=local_path,
        entity_handle=entity_handle,
    )
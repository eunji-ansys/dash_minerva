from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path

from dash import html
from flask import abort, send_file

from logic.viewer.viewer_file_resolver import (
    ViewerFile,
    get_viewer_type,
)

from .document_viewer import render_document_viewer
from .image_viewer import render_image_viewer
from .snp_viewer import render_snp_viewer
from .table_viewer import render_table_viewer
from .text_viewer import render_text_viewer
from .cad_viewer import render_cad_viewer


VIEWER_ROUTE_PATH = "/dash/viewer/<token>"
VIEWER_URL_PREFIX = "/dash/viewer"

_VIEWER_FILE_REGISTRY: dict[str, Path] = {}
_RELATIVE_PATH_BUILDER = None
_VIEWER_ROUTE_REGISTERED = False


def configure_viewer(*, server=None, relative_path_builder=None) -> None:
    global _RELATIVE_PATH_BUILDER

    _RELATIVE_PATH_BUILDER = relative_path_builder

    if server is not None:
        register_viewer_route(server)


def register_viewer_route(server) -> None:
    global _VIEWER_ROUTE_REGISTERED

    if _VIEWER_ROUTE_REGISTERED:
        return

    @server.route(VIEWER_ROUTE_PATH)
    def serve_viewer_file(token: str):
        file_path = _VIEWER_FILE_REGISTRY.get(token)

        if not file_path or not file_path.exists():
            abort(404)

        mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type:
            mime_type = "application/octet-stream"

        return send_file(
            str(file_path),
            mimetype=mime_type,
            as_attachment=False,
            download_name=file_path.name,
        )

    _VIEWER_ROUTE_REGISTERED = True


def build_viewer_url(token: str) -> str:
    path = f"{VIEWER_URL_PREFIX}/{token}"

    if _RELATIVE_PATH_BUILDER:
        return _RELATIVE_PATH_BUILDER(path)

    return path


def register_viewer_file(file_path: str | Path) -> str:
    path = Path(file_path)
    token = uuid.uuid4().hex
    _VIEWER_FILE_REGISTRY[token] = path
    return token


def render_viewer_content(viewer_file: ViewerFile):
    viewer_type = get_viewer_type(viewer_file.file_name)
    local_path = viewer_file.require_local_path()

    if viewer_type == "document":
        token = register_viewer_file(local_path)
        return render_document_viewer(build_viewer_url(token))

    if viewer_type == "text":
        return render_text_viewer(local_path)

    if viewer_type == "table":
        return render_table_viewer(local_path)

    if viewer_type == "image":
        token = register_viewer_file(local_path)
        return render_image_viewer(build_viewer_url(token))

    if viewer_type == "snp":
        return render_snp_viewer(local_path, viewer_file.file_name)

    if viewer_type == "cad":
        return render_cad_viewer(local_path, viewer_file.file_name)

    mime_type, _ = mimetypes.guess_type(str(local_path))
    if mime_type and (
        mime_type.startswith("image/")
        or mime_type in ("application/pdf", "text/plain")
    ):
        token = register_viewer_file(local_path)
        return render_document_viewer(build_viewer_url(token))

    return html.Div(
        [
            html.Div(
                "This file type does not support inline preview.",
                className="fw-semibold",
            ),
            html.Div(viewer_file.file_name, className="text-muted small mt-1"),
        ],
        className="p-3",
    )
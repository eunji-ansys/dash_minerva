from pathlib import Path

from dash import html


def render_cad_viewer(file_path: str | Path, file_name: str):
    return html.Div(
        [
            html.Div("CAD preview is not implemented yet.", className="fw-semibold"),
            html.Div(file_name, className="text-muted small mt-1"),
        ],
        className="p-3",
    )
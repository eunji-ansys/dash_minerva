from pathlib import Path

from dash import html

from .text_viewer import render_text_viewer


def render_snp_viewer(file_path: str | Path, file_name: str):
    return html.Div(
        [
            html.Div("Touchstone preview is not implemented yet.", className="fw-semibold mb-2"),
            html.Div(file_name, className="text-muted small"),
            render_text_viewer(file_path, max_chars=50000),
        ]
    )
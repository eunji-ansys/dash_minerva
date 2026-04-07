from pathlib import Path

from dash import html


def render_text_viewer(file_path: str | Path, max_chars: int = 200000):
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(max_chars)

        return html.Pre(
            content,
            style={
                "maxHeight": "70vh",
                "overflow": "auto",
                "whiteSpace": "pre-wrap",
                "wordBreak": "break-word",
                "fontSize": "13px",
                "marginBottom": "0",
                "backgroundColor": "#f8f9fa",
                "padding": "12px",
                "border": "1px solid #dee2e6",
                "borderRadius": "8px",
            },
        )
    except Exception as e:
        return html.Div(f"Failed to load text preview: {e}", className="text-danger")
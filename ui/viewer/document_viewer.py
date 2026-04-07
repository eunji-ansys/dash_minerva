from dash import html


def render_document_viewer(url: str):
    return html.Iframe(
        src=url,
        style={
            "width": "100%",
            "height": "75vh",
            "border": "0",
            "borderRadius": "8px",
            "backgroundColor": "white",
        },
    )
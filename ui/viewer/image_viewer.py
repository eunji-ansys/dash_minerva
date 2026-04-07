from dash import html


def render_image_viewer(url: str):
    return html.Div(
        [
            html.Div(
                [
                    html.Img(
                        id="viewer-image",
                        src=url,
                        className="viewer-image",
                        draggable="false",
                    )
                ],
                id="viewer-image-stage",
                className="viewer-image-stage",
                **{"data-scale": "1"},
            )
        ],
        className="viewer-image-shell",
    )
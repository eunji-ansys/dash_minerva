import re
import os
import uuid
import shutil
import json
from pathlib import Path
import math
from typing import Any, List, TypedDict, TypeAlias
from dotenv import load_dotenv

import dash
from dash import dcc, html, Input, Output, State, callback, clientside_callback, ALL, MATCH, ctx
import dash_bootstrap_components as dbc
import glob
from urllib.parse import quote
from flask import logging, request, send_file, abort

from logic.services.service_factory import get_service
from datamodel.models import FilterFieldSpec, Filters, FilterSpec, NodeRef, NodeKind, DetailsData, FileNode, FileSet, Summary, Badge

print("### RUNNING DASH FILE:", __file__)

# --- [0. Load Environment Variables] ---
load_dotenv()
TEMP_DOWNLOAD_PATH = os.getenv("TEMP_DOWNLOAD_PATH", "./temp_downloads")

# --- [1. Build service (tenant-agnostic) ] ---
service = get_service()

print("### Service initialized:", service)

# --- [2. Helper Functions] ---
FIXED_VIEWER_CONFIG = {
    ".pdf": "PDF_VIEWER",
    ".txt": "TEXT_VIEWER",
    ".csv": "TABLE_VIEWER",
    ".xlsx": "TABLE_VIEWER",
}
PATTERN_VIEWER_CONFIG = [
    (r"\.s\d+p", "TOUCHSTONE_VIEWER"),
    (r"\.v\d+", "VERSION_VIEWER")
]

def get_viewer_type_by_ext(file_name: str | None):
    if not file_name:
        return None
    _, ext = os.path.splitext(file_name.lower())
    if ext in FIXED_VIEWER_CONFIG:
        return FIXED_VIEWER_CONFIG[ext]
    for pattern, viewer_type in PATTERN_VIEWER_CONFIG:
        if re.fullmatch(pattern, ext):
            return viewer_type
    return None

def render_placeholder(text, height="150px"):
    return html.Div(
        [html.Div(text, className="text-muted small fw-light px-4 text-center")],
        style={
            "height": height,
            "border": "1px dashed #ced4da",
            "borderRadius": "8px",
            "backgroundColor": "#fcfcfc",
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
        },
        className="w-100 mb-3",
    )


# ---- NodeRef (de)serialization for dcc.Store ----
def node_to_dict(n: NodeRef) -> dict:
    return {
        "id": n.id,
        "kind": n.kind.value if hasattr(n.kind, "value") else str(n.kind),
        "title": n.summary.title,
        "subtitle": n.summary.subtitle,
        "badges": [
            {
                "label": b.label,
                "value": b.value,
                "show_label": b.show_label,
                "color": b.color,
                "views": list(b.views),
            }
            for b in (n.summary.badges or [])
        ],
        "item_type": n.item_type,
        "role": n.role,
        "can_expand": n.can_expand,
    }

def node_from_dict(d: dict) -> NodeRef:
    return NodeRef(
        id=d["id"],
        kind=NodeKind(d["kind"]),
        summary=Summary(
            title=d.get("title", d["id"]),
            subtitle=d.get("subtitle"),
            badges=[
                Badge(
                    label=b["label"],
                    value=b["value"],
                    show_label=b.get("show_label", True),
                    color=b.get("color", "light"),
                    views=tuple(b.get("views", ("sidebar","header","card"))),
                )
                for b in d.get("badges", [])
            ],
        ),
        item_type=d.get("item_type", ""),
        role=d.get("role", ""),
        can_expand=d.get("can_expand", None),
    )

def merge_node_map(old_map: dict, nodes: list[NodeRef]) -> dict:
    new_map = dict(old_map or {})
    for n in nodes:
        new_map[n.id] = node_to_dict(n)
    return new_map


def build_node_map(nodes: list[NodeRef]) -> dict:
    return {n.id: node_to_dict(n) for n in nodes}


def build_filters(filter_values, filter_ids) -> Filters:
    return {
        fid["name"]: value
        for fid, value in zip(filter_ids or [], filter_values or [])
        if isinstance(fid, dict) and fid.get("name")
    }


def resolve_default_value(spec: FilterFieldSpec) -> Any:
    if "default" in spec:
        return spec["default"]

    options = spec.get("options", [])
    if options:
        return options[-1]["value"]

    return None


# ---- Summary rendering helpers ----
def render_badges(
    badges: list[Badge],
    *,
    className: str = "",
    gap_class: str = "gap-1",
):
    if not badges:
        return None

    components = []

    for b in badges:
        text = b.value if not b.show_label else f"{b.label}: {b.value}"
        text_color = "dark" if b.color == "light" else "white"

        components.append(
            dbc.Badge(
                text,
                color=b.color,
                text_color=text_color,
                className="border",
            )
        )

    return html.Div(
        components,
        className=f"d-flex flex-wrap align-items-center {gap_class} {className}".strip(),
        style={"rowGap": "6px"},
    )

def badges_for_view(badges: list[Badge], view: str) -> list[Badge]:
    return [b for b in badges or [] if view in (b.views or ())]

def render_summary_title_block(
    summary: Summary,
    *,
    title_class: str = "fw-bold",
    title_style: dict | None = None,
    subtitle_class: str = "text-muted",
    subtitle_style: dict | None = None,
    badges_class: str = "mt-2",
    container_class: str = "w-100",
    badge_view: str | None = None,
):
    title_style = title_style or {}
    subtitle_style = subtitle_style or {}

    visible_badges = (
        badges_for_view(summary.badges or [], badge_view)
        if badge_view
        else (summary.badges or [])
    )

    return html.Div(
        [
            html.Div(
                summary.title or "Item",
                className=title_class,
                style=title_style,
            ),
            html.Div(
                summary.subtitle,
                className=subtitle_class,
                style=subtitle_style,
            ) if summary.subtitle else None,
            render_badges(
                visible_badges,
                className=badges_class,
            ) if visible_badges else None,
        ],
        className=container_class,
    )

def render_header_from_details(details: DetailsData):
    return html.Div(
        [
            render_summary_title_block(
                details.summary,
                title_class="fw-bold mb-0",
                title_style={
                    "fontSize": "1.75rem",
                    "lineHeight": "1.2",
                },
                subtitle_class="text-muted",
                subtitle_style={
                    "fontSize": "1rem",
                    "marginTop": "4px",
                },
                badges_class="mt-3",
                container_class="w-100",
                 badge_view="header",
            )
        ],
        className="bg-white p-3 rounded shadow-sm border-start border-primary border-4 mb-2",
    )

# ---- File UI helpers ----
def format_size(size_bytes):
    if size_bytes is None or size_bytes == 0:
        return "0 B"
    try:
        if isinstance(size_bytes, str):
            size_bytes = float(size_bytes)
    except (ValueError, TypeError):
        return "Unknown"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"


def create_tree_table(file_list: list[FileNode], category: str, active_item: str):
    if not file_list:
        return html.Div("No files found.", className="p-4 text-muted small text-center")

    rows = []
    for f in file_list:
        file_id = f.id
        file_name = f.name
        is_folder = f.is_folder
        vault_id = f.vault_id
        depth = f.depth or 0
        file_size = f.size or 0

        rows.append(
            html.Tr(
                [
                    html.Td(
                        [
                            html.Span(
                                "└─ " if depth > 0 else "",
                                style={"color": "#adb5bd", "fontFamily": "monospace"},
                            ),
                            html.Span("📂 " if is_folder else "📄 ", className="me-1"),
                            html.Span(file_name),
                        ],
                        style={
                            "paddingLeft": f"{depth * 20 + 15}px",
                            "paddingTop": "4px",
                            "paddingBottom": "4px",
                            "fontWeight": "600" if is_folder else "400",
                            "fontSize": "14px",
                        },
                        className="align-middle",
                    ),
                    html.Td(
                        format_size(file_size) if not is_folder else "-",
                        className="text-end text-muted align-middle",
                        style={"fontSize": "14px", "paddingTop": "4px", "paddingBottom": "4px"},
                    ),
                    html.Td(
                        dbc.ButtonGroup(
                            [
                                dbc.Button(
                                    html.Img(src=dash.get_asset_url("icons/eye.svg"), style={"width": "14px"}),
                                    id={"type": "btn-view", "index": file_id, "file_name": file_name, "category": category},
                                    color="white",
                                    size="sm",
                                    className="border py-0 px-2",
                                    style={
                                        "visibility": "visible"
                                        if (not is_folder and get_viewer_type_by_ext(file_name))
                                        else "hidden"
                                    },
                                ),
                                dbc.Button(
                                    html.Img(
                                        src=dash.get_asset_url("icons/folder-download.svg" if is_folder else "icons/download.svg"),
                                        style={"width": "14px"},
                                    ),
                                    id={"type": "btn-download", "index": file_id, "file_name": file_name, "category": category, "is_folder": is_folder, "vault_id":vault_id},
                                    n_clicks=0,
                                    color="white",
                                    size="sm",
                                    className="ms-1 border py-0 px-2",
                                ),
                                dbc.Button(
                                    [
                                        html.Img(
                                            src=dash.get_asset_url("icons/arrow-up-right-square.svg"),
                                            style={"width": "12px", "marginRight": "4px"},
                                        ),
                                        "Minerva",
                                    ],
                                    id={"type": "btn-external", "index": file_id, "file_name": file_name, "category": category},
                                    color="primary",
                                    outline=True,
                                    size="sm",
                                    className="ms-1 py-0 px-2 d-flex align-items-center justify-content-center",
                                    style={"fontSize": "12px"},
                                ),
                            ],
                            size="sm",
                            className="w-100",
                        ),
                        className="text-center align-middle",
                        style={"paddingTop": "2px", "paddingBottom": "2px"},
                    ),
                ],
                className="file-row-item",
                id={"type": "file-row", "index": active_item, "file_id": file_id},
                **{"data-filename": (file_name or "").lower()},
                style={"height": "32px"},
            )
        )

    return dbc.Table(
        [
            html.Thead(
                html.Tr(
                    [
                        html.Th("Name", className="ps-4"),
                        html.Th("Size", className="text-end", style={"width": "100px"}),
                        html.Th("Actions", className="text-center", style={"width": "180px"}),
                    ],
                    style={"lineHeight": "1.2"},
                )
            ),
            html.Tbody(rows, id={"type": "file-table-body", "index": active_item, "category": category}),
        ],
        hover=True,
        borderless=True,
        className="mb-0 table-sm",
    )


# --- [3. App Initialization & Layout] ---
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.FLATLY, dbc.icons.BOOTSTRAP],
    suppress_callback_exceptions=True,
)



app.layout = dbc.Container(
    [
        dcc.Store(id="store-node-by-id", data={}),
        dcc.Store(id="store-selected", data={"level0": None, "level1": None, "level2": None}),
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.H4(service.default_section_title(0, "Projects"), className="fw-bold mb-3"),
                                        dbc.Row(id="filter-container", className="g-2 mb-3"),
                                        html.Hr(className="mt-2"),
                                    ],
                                    style={"flex": "0 0 auto", "padding": "0 5px"},
                                ),
                                dcc.Loading(html.Div(id="level0-list-container", style={"flex": "1 1 auto", "overflowY": "auto", "paddingRight": "5px"})),
                            ],
                            style={
                                "height": "calc(100vh - 40px)",
                                "display": "flex",
                                "flexDirection": "column",
                                "position": "sticky",
                                "top": "20px",
                                "overflowX": "hidden",
                            },
                        )
                    ],
                    width=3,
                    className="bg-light border-end p-3",
                ),
                dbc.Col(
                    [
                        html.Div(
                            [
                                html.Div(
                                    id="level0-header-area",
                                    children=[
                                        html.H4("Dashboard", className="fw-bold text-dark mb-1"),
                                        dcc.Loading(html.P(f"Select a {service.item_label(0, 'Level 0')} from the sidebar to load data.", className="text-muted small")),
                                    ],
                                    className="mb-4",
                                ),

                                # Dynamic titles
                                html.H6(id="level1-title", children=service.default_section_title(1, "Level 1"), className="fw-bold text-secondary mb-3"),
                                dcc.Loading(id="level1-cards-area", children=render_placeholder(f"Please select a {service.item_label(1, 'Level 1')} item.")),

                                dcc.Loading(
                                    id="loading-download",
                                    type="default",
                                    fullscreen=False,
                                    children=[html.Div(id="loading-output-target")],
                                    className="text-muted small",
                                ),

                                html.H6(id="level2-title", children=service.default_section_title(2, "Level 2"), className="fw-bold text-secondary mb-3 mt-4"),
                                html.Div(id="level2-accordion-area", children=render_placeholder(f"Select a {service.item_label(2, 'Level 2')} card.")),

                                html.Div(id="footer-status", className="mt-5 pt-3 border-top text-muted small"),
                            ],
                            className="p-4",
                            style={"minHeight": "100vh"},
                        )
                    ],
                    width=9,
                    className="bg-white",
                ),
            ]
        ),
        dbc.Toast(
            id="download-toast",
            header="File Transfer",
            is_open=False,
            dismissable=True,
            duration=4000,
            icon="info",
            style={"position": "fixed", "top": 66, "right": 10, "width": 350, "zIndex": 9999},
            children=html.P(id="download-toast-body", className="mb-0 small"),
        ),
        dcc.Download(id="download-component"),
    ],
    fluid=True,
)

# --- [4. Callback Logic] ---
def build_filter_components(filter_spec: FilterSpec) -> list:
    children = []

    for field_name, spec in filter_spec.items():
        if not spec.get("enabled", True):
            continue

        component_type = spec.get("component", "dropdown")

        if component_type != "dropdown":
            continue

        children.append(
            dbc.Col(
                [
                    dbc.Label(spec.get("label", field_name.title())),
                    dcc.Dropdown(
                        id={"type": "dynamic-filter", "name": field_name},
                        options=spec.get("options", []),
                        value=resolve_default_value(spec),
                        placeholder=spec.get("placeholder", f"Select {field_name}"),
                        multi=spec.get("multi", False),
                        clearable=True,
                        style={"width": "100%"},
                    ),
                ],
            )
        )

    return children

@callback(
    Output("filter-container", "children"),
    Input("filter-container", "id"),
    prevent_initial_call=False,
)
def render_filters(_):
    filter_spec = service.get_filter_spec() or {}
    return build_filter_components(filter_spec)

def render_level0_item(node: NodeRef, details: DetailsData | None = None, active: bool = False):
    summary = node.summary if node.summary else (details.summary if details else Summary(title=node.id))
    badges = badges_for_view(node.summary.badges, "sidebar") if node.summary else []

    return dbc.ListGroupItem(
        [
            html.Div(
                [
                    html.Div(
                        summary.title or "Item",
                        className="fw-semibold text-truncate",
                        style={
                            "fontSize": "14px",
                            "lineHeight": "1.25",
                        },
                    ),
                    html.Div(
                        summary.subtitle,
                        className="text-muted text-truncate mt-1",
                        style={
                            "fontSize": "12px",
                            "lineHeight": "1.2",
                        },
                    ) if summary.subtitle else None,
                    render_badges(
                        badges,
                        className="mt-2",
                    ) if badges else None,
                ],
                className="min-w-0",
            )
        ],
        id={"type": "level0-item", "index": node.id},
        action=True,
        active=active,
        className="border-0 border-bottom py-3",
    )


@callback(
    Output("level0-list-container", "children"),
    Output("store-node-by-id", "data"),
    Input({"type": "dynamic-filter", "name": ALL}, "value"),
    State({"type": "dynamic-filter", "name": ALL}, "id"),
    State("store-selected", "data"),
    prevent_initial_call=False,
)
def update_level0_list(filter_values, filter_ids, selected):
    filters = build_filters(filter_values, filter_ids)

    level0_nodes = service.list_level0(filters=filters)

    if not level0_nodes:
        return html.Div("No items found.", className="text-muted p-3 small text-center"), {}

    selected_level0 = (selected or {}).get("level0")

    node_map = build_node_map(level0_nodes)
    items = [
        render_level0_item(n, details=None, active=(n.id == selected_level0))
        for n in level0_nodes
    ]
    return dbc.ListGroup(items, flush=True, className="level0-list"), node_map

@callback(
    Output({"type": "level0-item", "index": ALL}, "active"),
    Input("store-selected", "data"),
    State({"type": "level0-item", "index": ALL}, "id"),
    prevent_initial_call=False,
)
def highlight_selected_level0(selected, item_ids):
    selected_level0 = (selected or {}).get("level0")
    return [
        item_id["index"] == selected_level0
        for item_id in (item_ids or [])
    ]


def render_level1_section(level1_nodes: list[NodeRef]):
    columns = [
        dbc.Col(render_level1_card(n), xs=12, sm=6, md=4, lg=4, className="d-flex align-items-stretch")
        for n in level1_nodes
    ]
    return html.Div([dbc.Row(columns, className="g-3")], style={"maxHeight": "70vh", "overflowY": "auto", "padding": "10px"})

def render_level1_card(node: NodeRef):
    return html.Div(
        dbc.Card(
            dbc.CardBody(
                [
                    render_summary_title_block(
                        node.summary,
                        title_class="fw-bold mb-1",
                        title_style={
                            "minHeight": "20px",
                            "lineHeight": "1.25",
                        },
                        subtitle_class="text-muted mb-2",
                        subtitle_style={"fontSize": "13px"},
                        badges_class="",
                        badge_view="card",
                    )
                ]
            ),
            className="h-100 shadow-sm border-0 sr-card-hover",
            style={"borderRadius": "14px"},
        ),
        id={"type": "level1-card", "index": node.id},
        n_clicks=0,
        style={"cursor": "pointer", "width": "100%"},
    )


@callback(
    [
        Output("level0-header-area", "children"),
        Output("level1-title", "children"),
        Output("level2-title", "children"),
        Output("level1-cards-area", "children"),
        Output("level2-accordion-area", "children", allow_duplicate=True),
        Output("store-selected", "data"),
        Output("store-node-by-id", "data", allow_duplicate=True),
    ],
    Input({"type": "level0-item", "index": ALL}, "n_clicks"),
    State("store-node-by-id", "data"),
    State("store-selected", "data"),
    prevent_initial_call=True,
)
def update_level0_view(n_clicks, node_map, selected):
    if not ctx.triggered_id or not any(n_clicks):
        return (dash.no_update,) * 7

    level0_id = ctx.triggered_id["index"]
    node_dict = (node_map or {}).get(level0_id)

    level0_title = service.default_section_title(0, "Level 0")
    level1_title = service.default_section_title(1, "Level 1")
    level2_title = service.default_section_title(2, "Level 2")

    if not node_dict:
        return dash.no_update, level1_title, level2_title, render_placeholder(f"{level0_title} not found."), dash.no_update, dash.no_update, dash.no_update

    level0_node = node_from_dict(node_dict)

    level0_details = service.get_details(level0_node)
    level1_nodes = service.get_children(level0_node).children
    node_map = merge_node_map(node_map, level1_nodes)

    header = render_header_from_details(level0_details)

    if not level1_nodes:
        level1_cards = render_placeholder(f"No {level1_title} found.")
    else:
        level1_cards = render_level1_section(level1_nodes)

    new_selected = dict(selected or {})
    new_selected.update({"level0": level0_id, "level1": None, "level2": None})

    return (
        header,
        level1_title,
        level2_title,
        level1_cards,
        render_placeholder(f"Select a {service.item_label(1, 'Level 1')} card to continue.", height="250px"),
        new_selected,
        node_map,
    )


@callback(
    [
        Output("level2-accordion-area", "children"),
        Output({"type": "level1-card", "index": ALL}, "className"),
        Output("level2-title", "children", allow_duplicate=True),
        Output("store-selected", "data", allow_duplicate=True),
        Output("store-node-by-id", "data", allow_duplicate=True),
    ],
    Input({"type": "level1-card", "index": ALL}, "n_clicks"),
    State({"type": "level1-card", "index": ALL}, "id"),
    State("store-node-by-id", "data"),
    State("store-selected", "data"),
    prevent_initial_call=True,
)
def update_level2_list(n_clicks, level1_ids, node_map, selected):
    if not any(n_clicks):
        return dash.no_update, [dash.no_update] * len(level1_ids), dash.no_update, dash.no_update, dash.no_update

    level1_id = ctx.triggered_id["index"]

    classnames = [
        "h-100 shadow border border-3 border-primary bg-primary bg-opacity-10" if sid["index"] == level1_id
        else "h-100 shadow-sm border-0"
        for sid in level1_ids
    ]

    level1_title = service.default_section_title(1, "Level 1")
    level2_title = service.default_section_title(2, "Level 2")

    node_dict = (node_map or {}).get(level1_id)
    if not node_dict:
        return render_placeholder(f"{level1_title} node not found."), classnames, f"{level2_title}", dash.no_update, dash.no_update
    level1_node = node_from_dict(node_dict)

    level2_nodes = service.get_children(level1_node).children
    node_map = merge_node_map(node_map, level2_nodes)

    if not level2_nodes:
        new_selected = dict(selected or {})
        new_selected.update({"level1": level1_id, "level2": None})
        return (
            html.Div(f"No {level2_title} found.", className="p-4 text-center text-muted"),
            classnames,
            level2_title,
            new_selected,
            node_map,
        )

    accordion_items = []
    for n in level2_nodes:
        accordion_items.append(
            dbc.AccordionItem(
                [dcc.Loading(html.Div(id={"type": "level2-detail-content", "index": n.id}, children="Loading details..."))],
                title=render_summary_title_block(
                    n.summary,
                    title_class="fw-bold",
                    title_style={
                        "fontSize": "16px",
                        "lineHeight": "1.2",
                    },
                    subtitle_class="text-muted small mt-1",
                    subtitle_style={},
                    badges_class="mt-2",
                    badge_view="header",
                ),
                item_id=n.id,
            )
        )

    accordion = dbc.Accordion(accordion_items, id="level2-accordion-root", flush=True, active_item=None, always_open=False)

    new_selected = dict(selected or {})
    new_selected.update({"level1": level1_id, "level2": None})

    return accordion, classnames, level2_title, new_selected, node_map


@callback(
    Output({"type": "level2-detail-content", "index": MATCH}, "children"),
    Input("level2-accordion-root", "active_item"),
    State({"type": "level2-detail-content", "index": MATCH}, "id"),
    State("store-node-by-id", "data"),
    prevent_initial_call=True,
)
def render_level2_details(active_item, component_id, node_map):
    current_id = component_id["index"]
    if active_item != current_id:
        return dash.no_update

    node_dict = (node_map or {}).get(current_id)
    if not node_dict:
        return render_placeholder("Node not found.", height="120px")

    node = node_from_dict(node_dict)
    details = service.get_details(node)

    files = details.files
    inputs = files.inputs or [] if files else []
    outputs = files.outputs or [] if files else []

    if not files:
        return html.Div(
            [
                html.Div("No files for this item.", className="px-2 text-muted small"),
            ],
            className="pb-2",
        )

    return html.Div(
        [
            html.Div(
                [
                    dbc.Input(
                        id={"type": "file-search", "index": current_id},
                        placeholder="Search files in this request...",
                        size="sm",
                        className="mb-2 shadow-sm",
                        debounce=True,
                    )
                ],
                className="px-2",
            ),
            dbc.Tabs(
                [
                    dbc.Tab(
                        create_tree_table(inputs, "inputs", current_id),
                        label=f"Input Files ({len(inputs)})",
                        tab_id="tab-inputs",
                        label_class_name="fw-bold text-primary",
                        className="p-2 border border-top-0 bg-white rounded-bottom",
                    ),
                    dbc.Tab(
                        create_tree_table(outputs, "outputs", current_id),
                        label=f"Output Files ({len(outputs)})",
                        tab_id="tab-outputs",
                        label_class_name="fw-bold text-success",
                        className="p-2 border border-top-0 bg-white rounded-bottom",
                    ),
                ],
                id={"type": "wr-tabs", "index": current_id},
                active_tab="tab-inputs",
            ),
        ],
        className="px-2 pb-2",
    )

clientside_callback(
    """
    function(search_term, content_id) {
        if (!content_id || typeof content_id.index === 'undefined') {
            return window.dash_clientside.no_update;
        }

        const term = search_term ? search_term.toLowerCase().trim() : "";
        const currentIndex = String(content_id.index);

        const rows = document.getElementsByClassName('file-row-item');

        for (let i = 0; i < rows.length; i++) {
            let row = rows[i];

            if (row.id && row.id.includes(currentIndex)) {
                const fileName = row.getAttribute('data-filename') || "";
                if (fileName.includes(term)) {
                    row.style.display = "";
                } else {
                    row.style.display = "none";
                }
            }
        }

        return window.dash_clientside.no_update;
    }
    """,
    Output({"type": "file-search", "index": MATCH}, "id"),
    Input({"type": "file-search", "index": MATCH}, "value"),
    State({"type": "level2-detail-content", "index": MATCH}, "id"),
    prevent_initial_call=True,
)



@callback(
    [
        Output("download-component", "data"),
        Output("download-toast", "is_open"),
        Output("download-toast-body", "children"),
        Output("loading-output-target", "children"),
    ],
    Input(
        {"type": "btn-download", "index": ALL, "file_name": ALL, "category": ALL, "is_folder": ALL, "vault_id": ALL},
        "n_clicks",
    ),
    State(
        {"type": "btn-download", "index": ALL, "file_name": ALL, "category": ALL, "is_folder": ALL, "vault_id": ALL},
        "id",
    ),
    prevent_initial_call=True,
)
def handle_file_download(n_clicks_list, id_list):
    if not n_clicks_list or not any(n_clicks_list):
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update
    info = None

    if isinstance(ctx.triggered_id, dict):
        info = ctx.triggered_id

    # n_clicks is the largest button
    if not info:
        i = max(range(len(n_clicks_list)), key=lambda k: (n_clicks_list[k] or 0))
        info = (id_list or [None] * len(n_clicks_list))[i] or {}

    print("DOWNLOAD FIRED", n_clicks_list, ctx.triggered_id)

    file_id = info.get("index")
    vault_id = info.get("vault_id")
    category = info.get("category", "files")
    file_name = info.get("file_name")
    is_folder = bool(info.get("is_folder", False))

    if not file_id:
        return dash.no_update, True, "Download failed: cannot resolve clicked file id.", ""

    try:
        os.makedirs(TEMP_DOWNLOAD_PATH, exist_ok=True)

        # Create an isolated work directory for this download request.
        request_id = str(uuid.uuid4().hex.upper())
        request_dir = os.path.join(TEMP_DOWNLOAD_PATH, request_id)
        os.makedirs(request_dir, exist_ok=True)

        # Target path inside the isolated request directory.
        target_path = os.path.join(request_dir, file_name) if file_name else None

        if is_folder:
            service.download_to_server_via_cli(ans_data_id=file_id, dest=request_dir)

            if not target_path or not os.path.exists(target_path):
                return (
                    dash.no_update,
                    True,
                    f"[{category.upper()}] Downloaded folder not found: {file_name}",
                    "",
                )

            if os.path.isdir(target_path):
                # Create zip outside the source folder but still inside the same request directory.
                zip_base = os.path.join(request_dir, Path(target_path).name)
                zip_path = shutil.make_archive(
                    base_name=zip_base,
                    format="zip",
                    root_dir=os.path.dirname(target_path),
                    base_dir=os.path.basename(target_path),
                )
                return (
                    dcc.send_file(zip_path),
                    True,
                    f"[{category.upper()}] Folder zipped; download started.",
                    "",
                )
        else:
            if not target_path:
                return (
                    dash.no_update,
                    True,
                    f"[{category.upper()}] File name is missing.",
                    "",
                )
            service.download_to_server_via_odata(vault_id=vault_id, dest=target_path)
            if not os.path.exists(target_path):
                return (
                    dash.no_update,
                    True,
                    f"[{category.upper()}] Download failed: file not found after OData download.",
                    "",
                )

            return (
                dcc.send_file(target_path),
                True,
                f"[{file_name}] Download started.",
                "",
            )

    except Exception as e:
        return dash.no_update, True, f"Transfer failed: {e}", ""


if __name__ == "__main__":
    app.run(debug=True)
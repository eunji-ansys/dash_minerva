import re
import os
import uuid
import shutil
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
from datamodel.models import NodeRef, NodeKind, DetailsData, FileNode, FileSet, Summary, Badge

print("### RUNNING DASH FILE:", __file__)

# --- [0. Load Environment Variables] ---
load_dotenv()
TEMP_DOWNLOAD_PATH = os.getenv("TEMP_DOWNLOAD_PATH", "./temp_downloads")

# --- [1. Build service (tenant-agnostic) ] ---
service = get_service()

print("### Service initialized:", service)

# --- [2. Helper Functions] ---


class OptionSpec(TypedDict):
    label: str
    value: Any


class FilterFieldSpec(TypedDict, total=False):
    label: str
    enabled: bool
    options: List[OptionSpec]
    default: Any
    placeholder: str  # optional UI hint
    multi: bool
    component: str   # "dropdown", "input", "radio" etc. (optional UI hint)


FilterSpec: TypeAlias = dict[str, FilterFieldSpec]
Filters: TypeAlias = dict[str, Any]


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


def get_status_color(status):
    s = str(status).lower() if status else ""
    if any(x in s for x in ["active", "open", "success", "running"]): return "light"
    if any(x in s for x in ["close", "closed", "complete"]): return "dark"
    if any(x in s for x in ["new"]): return "warning"
    if any(x in s for x in ["progress", "queued", "in work"]): return "success"
    if any(x in s for x in ["accepted", "in review"]): return "info"
    if any(x in s for x in ["paused", "failed", "error"]): return "danger"
    return "secondary"


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
        "item_type": n.item_type,
        "role": n.role,
        "can_expand": n.can_expand,
    }

def node_from_dict(d: dict) -> NodeRef:
    return NodeRef(
        id=d["id"],
        kind=NodeKind(d["kind"]),
        summary=Summary(title=d.get("title", d["id"]), subtitle=d.get("subtitle"), badges=d.get("badges", [])),
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
def _summary_badges_to_ui(badges: list[Badge]) -> list:
    out = []
    for b in badges or []:
        out.append(
            dbc.Badge(
                f"{b.label}: {b.value}",
                color="light",
                text_color="dark",
                className="me-2 border",
            )
        )
    return out

def render_header_from_details(details: DetailsData):
    s = details.summary
    title = s.title or "Item"
    subtitle = s.subtitle or ""
    badges = _summary_badges_to_ui(s.badges)

    return html.Div(
        [
            html.Div(
                [
                    html.H2(title, className="fw-bold d-inline-block me-3 mb-0"),
                    html.Span(subtitle, className="text-muted ms-1"),
                ],
                className="d-flex align-items-baseline flex-wrap gap-2",
            ),
            html.Div(badges, className="mt-2 d-flex flex-wrap"),
        ],
        className="bg-white p-3 rounded shadow-sm border-start border-primary border-4 mb-2",
    )


# ---- Dynamic section title helpers (NO tenant branching) ----
ROLE_TITLE_MAP = {
    "Project": "Projects",
    "SR": "Simulation Requests",
    "WR": "Work Requests",
    "Task": "Tasks",
}

def role_to_section_title(role: str | None, fallback: str) -> str:
    if not role:
        return fallback
    return ROLE_TITLE_MAP.get(role, role)


def infer_children_role_title(children: list[NodeRef], fallback: str) -> str:
    """
    Infer a section title from children roles.
    If multiple roles appear, choose the first non-empty; otherwise fallback.
    """
    for c in children or []:
        if c.role:
            return role_to_section_title(c.role, fallback)
    return fallback


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
                                        html.H4("Projects", className="fw-bold mb-3"),
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
                                        dcc.Loading(html.P("Select a Level 0 item from the sidebar to load data.", className="text-muted small")),
                                    ],
                                    className="mb-4",
                                ),

                                # Dynamic titles
                                html.H6(id="level1-title", children="Level 1", className="fw-bold text-secondary mb-3"),
                                dcc.Loading(id="level1-cards-area", children=render_placeholder("Please select a Level 0 item.")),

                                dcc.Loading(
                                    id="loading-download",
                                    type="default",
                                    fullscreen=False,
                                    children=[html.Div(id="loading-output-target")],
                                    className="text-muted small",
                                ),

                                html.H6(id="level2-title", children="Level 2 + Files", className="fw-bold text-secondary mb-3 mt-4"),
                                html.Div(id="level2-accordion-area", children=render_placeholder("Select a Level 1 card.")),

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

def render_level0_item(node: NodeRef, details: DetailsData | None = None):
    title = node.summary.title
    state_text = node.role or "LEVEL0"

    badge_components = []

    if details and details.summary and details.summary.badges:
        for b in details.summary.badges:
            value = b.value or ""
            label = str(b.label).lower()

            color = "light"
            if label == "state":
                color = get_status_color(value)

            badge_components.append(
                dbc.Badge(value, color=color, pill=True)
            )

    return dbc.ListGroupItem(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(title, className="fw-bold text-dark", style={"fontSize": "14px"}),
                            html.Div(node.summary.subtitle, className="text-muted", style={"fontSize": "11px", "marginTop": "2px"}),
                        ],
                        style={"flex": "1", "minWidth": "0"},
                    ),
                    *badge_components,  # Bage list
                ],
                className="d-flex justify-content-between align-items-center",
            )
        ],
        id={"type": "level0-item", "index": node.id},
        action=True,
        className="border-0 border-bottom py-3",
    )


@callback(
    Output("level0-list-container", "children"),
    Output("store-node-by-id", "data"),
    Input({"type": "dynamic-filter", "name": ALL}, "value"),
    State({"type": "dynamic-filter", "name": ALL}, "id"),
    prevent_initial_call=False,
)
def update_level0_list(filter_values, filter_ids):
    filters = build_filters(filter_values, filter_ids)

    try:
        level0_nodes = service.list_level0(filters=filters)
    except TypeError:
        try:
            level0_nodes = service.list_level0(
                year=filters.get("year"),
                product=filters.get("product"),
            )
        except TypeError:
            level0_nodes = service.list_level0()

    if not level0_nodes:
        return html.Div("No items found.", className="text-muted p-3 small text-center"), {}

    node_map = build_node_map(level0_nodes)
    items = [render_level0_item(n, details=None) for n in level0_nodes]
    return dbc.ListGroup(items, flush=True), node_map


def render_level1_section(level1_nodes: list[NodeRef]):
    columns = [
        dbc.Col(render_level1_card(n), xs=12, sm=6, md=4, lg=4, className="d-flex align-items-stretch")
        for n in level1_nodes
    ]
    return html.Div([dbc.Row(columns, className="g-3")], style={"maxHeight": "70vh", "overflowY": "auto", "padding": "10px"})


def render_level1_card(node: NodeRef):
    return html.Div(
        [
            dbc.Card(
                [
                    dbc.CardBody(
                        [
                            html.Div(
                                [
                                    html.Small(node.role, className="text-muted fw-bold", style={"fontSize": "11px"}),
                                    dbc.Badge(node.item_type, color="light", text_color="dark", pill=True, style={"fontSize": "10px"}, className="border"),
                                ],
                                className="d-flex justify-content-between align-items-center mb-2",
                            ),
                            html.H6(node.summary.title, className="fw-bold mb-3", style={"height": "18px", "overflow": "hidden"}),
                            html.Div([html.Div([html.I(className="bi bi-hash me-2"), node.id], className="small text-muted")], className="border-top pt-2"),
                        ]
                    )
                ],
                className="h-100 shadow-sm border-0 sr-card-hover",
            )
        ],
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
    if not node_dict:
        return dash.no_update, "Level 1", "Level 2 + Files", render_placeholder("LEVEL0 not found."), dash.no_update, dash.no_update, dash.no_update

    level0_node = node_from_dict(node_dict)

    level0_details = service.get_details(level0_node)
    level1_nodes = service.get_children(level0_node).children
    node_map = merge_node_map(node_map, level1_nodes)

    header = render_header_from_details(level0_details)

    # Dynamic titles inferred from children roles (NO tenant branching)
    level1_title = infer_children_role_title(level1_nodes, "Level 1")
    level2_title = "Level 2 + Files"  # unknown until a level1 node is selected

    if not level1_nodes:
        level1_cards = render_placeholder("No Level 1 items found for this Level 0.")
    else:
        level1_cards = render_level1_section(level1_nodes)

    new_selected = dict(selected or {})
    new_selected.update({"level0": level0_id, "level1": None, "level2": None})

    return (
        header,
        level1_title,
        level2_title,
        level1_cards,
        render_placeholder("Select a Level 1 card to see Level 2 + files.", height="250px"),
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

    node_dict = (node_map or {}).get(level1_id)
    if not node_dict:
        return render_placeholder("Level 1 node not found."), classnames, "Level 2 + Files", dash.no_update, dash.no_update

    level1_node = node_from_dict(node_dict)

    level2_nodes = service.get_children(level1_node).children
    node_map = merge_node_map(node_map, level2_nodes)

    # Dynamic title based on children role (NO tenant branching)
    level2_title = infer_children_role_title(level2_nodes, "Level 2 + Files")
    # If level2 are Tasks, "Files" may not apply; this stays acceptable. If you want, we can refine to "Level 2" only.

    if not level2_nodes:
        new_selected = dict(selected or {})
        new_selected.update({"level1": level1_id, "level2": None})
        return html.Div("No Level 2 items found.", className="p-4 text-center text-muted"), classnames, level2_title, new_selected, node_map

    accordion_items = []
    for n in level2_nodes:
        accordion_items.append(
            dbc.AccordionItem(
                [dcc.Loading(html.Div(id={"type": "level2-detail-content", "index": n.id}, children="Loading details..."))],
                title=html.Div([html.B(n.summary.title), html.Span(f"  ({n.role})", className="ms-2 text-muted small")], className="w-100"),
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
    if not files:
        return html.Div(
            [
                html.Div(_summary_badges_to_ui(details.summary.badges), className="mb-2 d-flex flex-wrap"),
                html.Div("No files for this item.", className="text-muted small"),
            ],
            className="px-2 pb-2",
        )

    inputs = files.inputs or []
    outputs = files.outputs or []

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

import json
import shutil

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
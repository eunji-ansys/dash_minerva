import os
import uuid
import shutil
import base64
from pathlib import Path
import math
from typing import Any
from dotenv import load_dotenv
import time
import threading

import dash
from dash import dcc, html, Input, Output, State, callback, clientside_callback, ALL, MATCH, ctx
import dash_bootstrap_components as dbc

from logic.services.service_factory import get_service
from datamodel.models import (
    FilterFieldSpec,
    Filters,
    FilterSpec,
    NodeRef,
    NodeKind,
    DetailsData,
    FileNode,
    Summary,
    Badge
)
from logic.viewer.viewer_file_resolver import (
    ViewerFileRef,
    ViewerFile,
    resolve_viewer_file,
    get_viewer_type,
)
from ui.viewer.viewer_manager import (
    render_viewer_content,
)


print("### RUNNING DASH FILE:", __file__)

# --- [0. Load Environment Variables] ---
load_dotenv()
TEMP_DOWNLOAD_PATH = os.getenv("TEMP_DOWNLOAD_PATH", "./temp_downloads")
TEMP_UPLOAD_PATH = os.getenv("TEMP_UPLOAD_PATH", "./temp_uploads")
TEMP_VIEWER_PATH = os.getenv("TEMP_VIEWER_PATH", "./temp_viewer")

# --- [1. Build service (tenant-agnostic) ] ---
service = get_service()

print("### Service initialized:", service)

# --- [2. Helper Functions] ---


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

def render_copy_button(
    item_id: str | None,
    *,
    title: str = "Copy Item ID",
):
    if not item_id:
        return None

    return html.Button(
        "⧉",
        id={"type": "copy-id-btn", "index": item_id},
        n_clicks=0,
        title=title,
        className="btn btn-sm ms-1 border py-0 px-2 copy-id-btn",
        **{
            "data-copy-text": item_id,
            "data-copy-title": title,
        },
        style={
            "fontSize": "14px",
            "lineHeight": "1",
            "fontWeight": "600",
            "color": "#495057",
            "minWidth": "28px",
            "height": "24px",
            "backgroundColor": "white",
        },
    )

def render_external_button(
    item_id: str | None,
    *,
    item_type: str | None = None,
    title: str = "Open in Minerva",
):
    if not item_id or not item_type:
        return None

    try:
        href = service.build_item_url(item_id=item_id, item_type=item_type)
    except Exception as e:
        print(f"render_external_button failed: {e}")
        return None

    return dbc.Button(
        html.Img(
            src=dash.get_asset_url("icons/arrow-up-right-square.svg"),
            style={"width": "14px"},
        ),
        href=href,
        target="_blank",
        external_link=True,
        color="white",
        size="sm",
        className="ms-1 border py-0 px-2",
        title=title,
    )

def render_id_row(
    item_id: str | None,
    *,
    label: str = "Item ID",
    className: str = "small mt-2",
    item_type: str | None = None,
    show_external_button: bool = False,
):
    if not item_id:
        return None

    return html.Div(
        [
            html.Code(
                item_id,
                style={
                    "fontSize": "10px",
                    "fontFamily": "Consolas, Monaco, monospace",
                    "color": "#6c757d",
                    "backgroundColor": "#f8f9fa",
                    "border": "1px solid #e9ecef",
                    "borderRadius": "5px",
                    "padding": "2px 6px",
                    "userSelect": "text",
                    "wordBreak": "break-all",
                    "lineHeight": "1.2",
                },
            ),
            render_copy_button(item_id, title=f"Copy {label}"),
            render_external_button(
                item_id,
                item_type=item_type,
                title=f"Open {label} in Minerva",
            ) if show_external_button else None,
        ],
        className=f"d-flex align-items-center flex-wrap {className}".strip(),
        style={
            "columnGap": "6px",
            "rowGap": "4px",
        },
    )

def render_summary_title_block(
    summary: Summary,
    *,
    title_class: str = "fw-bold",
    title_style: dict | None = None,
    subtitle_class: str = "text-muted",
    subtitle_style: dict | None = None,
    badges_class: str = "ms-3",
    container_class: str = "w-100",
    badge_view: str | None = None,
    copy_id: str | None = None,
    copy_label: str = "Item ID",
    show_copy_id_row: bool = False,
    copy_item_type: str | None = None,
    show_external_button: bool = False,
):
    title_style = {**(title_style or {}), "userSelect": "text"}
    subtitle_style = {**(subtitle_style or {}), "userSelect": "text"}

    visible_badges = (
        badges_for_view(summary.badges or [], badge_view)
        if badge_view
        else (summary.badges or [])
    )

    title_row = html.Div(
        [
            html.Div(
                summary.title or "Item",
                className=title_class,
                style=title_style,
            ),
            html.Div(
                render_badges(visible_badges),
                className=badges_class,
            ) if visible_badges else None,
        ],
        className="d-flex justify-content-between align-items-start flex-wrap",
    )

    return html.Div(
        [
            title_row,
            html.Div(
                summary.subtitle,
                className=subtitle_class,
                style=subtitle_style,
            ) if summary.subtitle else None,
            render_id_row(
                copy_id,
                label=copy_label,
                item_type=copy_item_type,
                show_external_button=show_external_button,
            ) if show_copy_id_row and copy_id else None,
        ],
        className=container_class,
    )

def render_header_from_details(details: DetailsData, item_id: str | None = None, item_type: str | None = None):
    return html.Div(
        [
            render_summary_title_block(
                details.summary,
                title_class="fw-bold mb-0",
                title_style={
                    "fontSize": "1.5rem",
                    "lineHeight": "1.15",
                },
                subtitle_class="text-muted mb-0",
                subtitle_style={
                    "fontSize": "0.95rem",
                    "marginTop": "2px",
                },
                badges_class="mt-2",
                container_class="w-100",
                badge_view="header",
                copy_id=item_id,
                copy_label="Item ID",
                show_copy_id_row=True,
                copy_item_type=item_type,
                show_external_button=True,
            )
        ],
        className="bg-white p-3 rounded shadow-sm border-start border-primary border-4 mb-2",
        style={"userSelect": "text"},
    )

# ---- File UI helpers ----
def sort_file_list(file_list: list[FileNode], sort_state: dict | None) -> list[FileNode]:
    if not file_list:
        return file_list

    sort_state = sort_state or {"column": "name", "direction": "asc"}
    column = sort_state.get("column", "name")
    direction = sort_state.get("direction", "asc")
    reverse = direction == "desc"

    def safe_str(value):
        return (value or "").lower()

    def safe_num(value):
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0

    def safe_modified(value):
        return value or ""

    def sort_key(node: FileNode):
        if column == "name":
            return safe_str(getattr(node, "name", None))
        if column == "size":
            return safe_num(getattr(node, "size", None))
        if column == "modified":
            return safe_modified(getattr(node, "modified_on", None))
        return safe_str(getattr(node, "name", None))

    class TreeItem:
        def __init__(self, node: FileNode):
            self.node = node
            self.children: list["TreeItem"] = []

    roots: list[TreeItem] = []
    stack: list[TreeItem] = []

    for node in file_list:
        depth = getattr(node, "depth", 0) or 0
        item = TreeItem(node)

        while len(stack) > depth:
            stack.pop()

        if depth == 0 or not stack:
            roots.append(item)
        else:
            stack[-1].children.append(item)

        stack.append(item)

    def sort_tree(items: list[TreeItem]):
        items.sort(key=lambda x: sort_key(x.node), reverse=reverse)
        for item in items:
            if item.children:
                sort_tree(item.children)

    sort_tree(roots)

    flattened: list[FileNode] = []

    def flatten(items: list[TreeItem], depth: int = 0):
        for item in items:
            node = item.node
            try:
                node.depth = depth
            except Exception:
                pass
            flattened.append(node)
            flatten(item.children, depth + 1)

    flatten(roots)
    return flattened


def render_sort_icon(sort_state: dict | None, column: str):
    if not sort_state or sort_state.get("column") != column:
        return html.I(className="bi bi-arrow-down-up ms-1 text-muted", style={"fontSize": "12px"})

    if sort_state.get("direction") == "asc":
        return html.I(className="bi bi-arrow-up ms-1", style={"fontSize": "12px"})

    return html.I(className="bi bi-arrow-down ms-1", style={"fontSize": "12px"})

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

def format_datetime(dt):
    if not dt:
        return "-"

    if isinstance(dt, str):
        return dt.replace("T", " ")[:16]

    return str(dt)


def create_tree_table(file_list: list[FileNode], category: str, active_item: str, sort_state: dict | None):
    if not file_list:
        return html.Div("No files found.", className="p-4 text-muted small text-center")

    sorted_files = sort_file_list(file_list, sort_state)

    rows = []
    for f in sorted_files:
        file_id = f.id
        file_name = f.name
        is_folder = f.is_folder
        vault_id = f.vault_id
        depth = f.depth or 0
        file_size = f.size or 0
        modified_on = getattr(f, "modified_on", None)

        external_href = None
        try:
            external_href = service.build_file_item_url(item_id=file_id)
        except Exception as e:
            print(f"file external url build failed: {e}")

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
                        format_datetime(modified_on),
                        className="text-muted align-middle",
                        style={"fontSize": "13px", "paddingTop": "4px", "paddingBottom": "4px", "whiteSpace": "nowrap"},
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
                                    id={
                                        "type": "btn-view",
                                        "index": file_id,
                                        "file_name": file_name,
                                        "category": category,
                                        "vault_id": vault_id,
                                        "is_folder": is_folder,
                                    },
                                    color="white",
                                    size="sm",
                                    className="border py-0 px-2",
                                    style={
                                        "visibility": "visible"
                                        if (not is_folder and get_viewer_type(file_name))
                                        else "hidden"
                                    },
                                ),
                                dbc.Button(
                                    html.Img(
                                        src=dash.get_asset_url("icons/folder-download.svg" if is_folder else "icons/download.svg"),
                                        style={"width": "14px"},
                                    ),
                                    id={"type": "btn-download", "index": file_id, "file_name": file_name, "category": category, "is_folder": is_folder, "vault_id": vault_id},
                                    n_clicks=0,
                                    color="white",
                                    size="sm",
                                    className="ms-1 border py-0 px-2",
                                ),
                                dbc.Button(
                                    html.Img(
                                        src=dash.get_asset_url("icons/arrow-up-right-square.svg"),
                                        style={"width": "14px"},
                                    ),
                                    href=external_href,
                                    target="_blank",
                                    external_link=True,
                                    color="white",
                                    size="sm",
                                    className="ms-1 border py-0 px-2",
                                    title="Open in Minerva",
                                    disabled=not external_href,
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
                        html.Th(
                            html.Button(
                                ["Name", render_sort_icon(sort_state, "name")],
                                id={"type": "file-sort", "column": "name", "index": active_item},
                                n_clicks=0,
                                className="btn btn-link p-0 text-decoration-none fw-bold text-dark",
                                style={"fontSize": "inherit"},
                            ),
                            className="ps-4",
                        ),
                        html.Th(
                            html.Button(
                                ["Modified", render_sort_icon(sort_state, "modified")],
                                id={"type": "file-sort", "column": "modified", "index": active_item},
                                n_clicks=0,
                                className="btn btn-link p-0 text-decoration-none fw-bold text-dark",
                                style={"fontSize": "inherit"},
                            ),
                            style={"width": "160px"},
                        ),
                        html.Th(
                            html.Button(
                                ["Size", render_sort_icon(sort_state, "size")],
                                id={"type": "file-sort", "column": "size", "index": active_item},
                                n_clicks=0,
                                className="btn btn-link p-0 text-decoration-none fw-bold text-dark",
                                style={"fontSize": "inherit"},
                            ),
                            className="text-end",
                            style={"width": "100px"},
                        ),
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

def save_uploaded_file(contents: str, filename: str, dest_dir: str) -> str:
    if not contents or not filename:
        raise ValueError("Invalid upload payload.")

    os.makedirs(dest_dir, exist_ok=True)

    content_type, content_string = contents.split(",", 1)
    decoded = base64.b64decode(content_string)

    safe_name = Path(filename).name
    target_path = os.path.join(dest_dir, safe_name)

    with open(target_path, "wb") as f:
        f.write(decoded)

    return target_path


def render_drop_overlay(category: str):
    label = "Inputs" if category == "inputs" else "Outputs"
    return html.Div(
        [
            html.Div(
                [
                    html.I(className="bi bi-cloud-arrow-up fs-3 d-block mb-2"),
                    html.Div(f"Drop files to upload to {label}", className="fw-semibold"),
                    html.Div("Release mouse to upload", className="small text-muted"),
                ],
                className="text-center",
            )
        ],
        className="file-drop-overlay",
    )


def render_files_tab(file_list, category, active_item, sort_state):
    return html.Div(
        [
            dcc.Upload(
                id={"type": "file-upload", "index": active_item, "category": category},
                children=html.Div(
                    [
                        html.Div(
                            create_tree_table(file_list, category, active_item, sort_state),
                            className="file-drop-content",
                        ),
                        render_drop_overlay(category),
                    ],
                    className="file-drop-zone position-relative",
                ),
                multiple=True,
                disable_click=True,
                className="d-block w-100",
                style={"display": "block"},
            ),
            html.Div(
                id={"type": "file-upload-status", "index": active_item, "category": category},
                className="small text-muted mt-2",
            ),
        ]
    )

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def touch_dir(path: str):
    try:
        os.makedirs(path, exist_ok=True)
        now = time.time()
        os.utime(path, (now, now))
    except Exception as e:
        print(f"[TEMP TOUCH ERROR] {path}: {e}")

def cleanup_temp_dirs(base_path: str, ttl_seconds: int):
    now = time.time()
    if not base_path or not os.path.exists(base_path):
        return

    for name in os.listdir(base_path):
        path = os.path.join(base_path, name)
        try:
            if not os.path.isdir(path):
                continue
            age = now - os.path.getmtime(path)
            if age > ttl_seconds:
                shutil.rmtree(path, ignore_errors=False)
                print(f"[TEMP CLEANUP] Removed expired temp dir: {path}")
        except FileNotFoundError:
            continue
        except PermissionError as e:
            print(f"[TEMP CLEANUP SKIP] In use or locked: {path} ({e})")
        except Exception as e:
            print(f"[TEMP CLEANUP ERROR] {path}: {e}")

def run_startup_cleanup():
    cleanup_temp_dirs(TEMP_VIEWER_PATH, ttl_seconds=2 * 60 * 60)
    cleanup_temp_dirs(TEMP_DOWNLOAD_PATH, ttl_seconds=2 * 60 * 60)
    cleanup_temp_dirs(TEMP_UPLOAD_PATH, ttl_seconds=24 * 60 * 60)

_CLEANUP_THREAD_STARTED = False

def start_temp_cleanup_scheduler():
    global _CLEANUP_THREAD_STARTED

    if _CLEANUP_THREAD_STARTED:
        print("### temp cleanup thread already started")
        return

    _CLEANUP_THREAD_STARTED = True

    def _loop():
        print("### temp cleanup thread started")
        while True:
            try:
                print("### temp cleanup tick")
                cleanup_temp_dirs(TEMP_VIEWER_PATH, ttl_seconds=2 * 60 * 60)
                cleanup_temp_dirs(TEMP_DOWNLOAD_PATH, ttl_seconds=2 * 60 * 60)
                cleanup_temp_dirs(TEMP_UPLOAD_PATH, ttl_seconds=24 * 60 * 60)
            except Exception as e:
                print(f"[TEMP CLEANUP LOOP ERROR] {e}")
            time.sleep(10 * 60)

    t = threading.Thread(target=_loop, daemon=True, name="temp-cleanup-thread")
    t.start()

# --- [3. App Initialization & Layout] ---

def layout():

    return dbc.Container(
    [
        dcc.Store(id="store-node-by-id", data={}),
        dcc.Store(id="store-selected", data={"level0": None, "level1": None, "level2": None}),
        dcc.Store(id="store-file-sort", data={"column": "name", "direction": "asc", "index": None}),
        dcc.Store(id="store-file-tab", data={"index": None, "active_tab": "tab-inputs"}),
        dcc.Store(id="store-file-drag-ui", data={}),
        dcc.Store(id="store-viewer-state", data={}),
        dcc.Store(id="store-viewer-request", data=None),
        dcc.Store(id="store-image-zoom", data={"scale": 1}),
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
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle(id="viewer-modal-title")),
                dcc.Loading(
                    dbc.ModalBody(
                        id="viewer-modal-body",
                        style={
                            "minHeight": "300px",
                            "display": "flex",
                            "justifyContent": "center",
                            "alignItems": "center",
                        },
                    ),
                    type="default",
                    color="#6f42c1",
                ),
                dbc.ModalFooter(
                    dbc.Button("Close", id="viewer-modal-close", color="secondary")
                ),
            ],
            id="viewer-modal",
            is_open=False,
            size="xl",
            scrollable=True,
            backdrop=True,
            centered=True,
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

    print("===== update_level0_list")

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


LEVEL1_CARD_MAX = 6

def render_level1_section(level1_nodes: list[NodeRef]):
    is_list = len(level1_nodes) > LEVEL1_CARD_MAX

    container_style = {
        "overflowY": "auto",
        "padding": "10px",
        "maxHeight": "45vh" if is_list else "70vh",
    }

    if not is_list:
        columns = [
            dbc.Col(
                render_level1_card(n),
                xs=12, sm=6, md=4, lg=4,
                className="d-flex align-items-stretch",
            )
            for n in level1_nodes
        ]
        return html.Div(
            [dbc.Row(columns, className="g-3")],
            style=container_style,
        )

    items = [render_level1_list_item(n) for n in level1_nodes]

    return html.Div(
        [
            html.Div(
                f"Showing {len(level1_nodes)} items in list view.",
                className="text-muted small px-2 pt-2 pb-1",
            ),
            dbc.ListGroup(items, flush=True),
        ],
        style=container_style,
    )

def render_level1_card(node: NodeRef):
    card_body = dbc.CardBody(
        [
            html.Div(
                node.summary.title or "Item",
                className="fw-bold mb-1",
                style={
                    "minHeight": "20px",
                    "lineHeight": "1.25",
                    "userSelect": "text",
                },
            ),
            html.Div(
                node.summary.subtitle,
                className="text-muted mb-2",
                style={"fontSize": "13px", "userSelect": "text"},
            ) if node.summary.subtitle else None,

            render_id_row(
                node.id,
                label="SR ID",
                className="small mb-2",
                item_type=node.item_type,
                show_external_button=True,
            ),

            render_badges(
                badges_for_view(node.summary.badges or [], "card"),
                className="",
            ) if badges_for_view(node.summary.badges or [], "card") else None,
        ]
    )

    return html.Div(
        dbc.Card(
            card_body,
            className="h-100 shadow-sm border-0 sr-card-hover",
            style={"borderRadius": "14px"},
        ),
        id={"type": "level1-card", "index": node.id},
        n_clicks=0,
        style={"cursor": "pointer", "width": "100%"},
    )

def render_level1_list_item(node: NodeRef):
    badges = badges_for_view(node.summary.badges or [], "card")

    return dbc.ListGroupItem(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                node.summary.title or "Item",
                                className="fw-semibold",
                                style={
                                    "fontSize": "15px",
                                    "lineHeight": "1.25",
                                    "userSelect": "text",
                                },
                            ),
                            html.Div(
                                node.summary.subtitle,
                                className="text-muted mt-1",
                                style={
                                    "fontSize": "13px",
                                    "lineHeight": "1.2",
                                    "userSelect": "text",
                                },
                            ) if node.summary.subtitle else None,
                        ],
                        className="min-w-0 flex-grow-1",
                    ),
                    html.Div(
                        render_id_row(
                            node.id,
                            label="SR ID",
                            className="small text-nowrap ms-md-3 mt-2 mt-md-0",
                            item_type=node.item_type,
                            show_external_button=True,
                        ),
                        className="flex-shrink-0",
                    ),
                ],
                className="d-flex flex-column flex-md-row align-items-md-start justify-content-between gap-2",
            ),
            render_badges(
                badges,
                className="mt-2",
            ) if badges else None,
        ],
        id={"type": "level1-card", "index": node.id},
        n_clicks=0,
        action=True,
        className="border-0 border-bottom py-3 shadow-sm",
        style={"cursor": "pointer"},
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

    print("===== update_level0_view")

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

    header = render_header_from_details(
        level0_details,
        item_id=level0_id,
        item_type=level0_node.item_type,
    )

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


def render_file_loading_placeholder():
    return html.Div(
        [
            html.Div(
                [
                    html.Div(className="spinner-border text-secondary mb-3", role="status"),
                    html.Div("Loading file list...", className="text-muted small"),
                ],
                className="d-flex flex-column align-items-center justify-content-center",
            )
        ],
        style={
            "height": "160px",
            "border": "1px dashed #ced4da",
            "borderRadius": "8px",
            "backgroundColor": "#fcfcfc",
        },
        className="w-100 mb-2",
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

    print("===== update_level2_list")

    level1_id = ctx.triggered_id["index"]

    classnames = [
        (
            "shadow border border-3 border-primary bg-primary bg-opacity-10"
            if sid["index"] == level1_id
            else "shadow-sm border-0"
        )
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
                [
                    dcc.Loading(
                        html.Div(
                            id={"type": "level2-detail-content", "index": n.id},
                            children=render_file_loading_placeholder(),
                        ),
                        type="default",
                        color="#6f42c1",
                        delay_show=150,
                        overlay_style={
                            "visibility": "visible",
                            "backgroundColor": "rgba(255,255,255,0.75)",
                        },
                    )
                ],
                title=html.Div(
                    [
                        html.Div(
                            n.summary.title or "Item",
                            className="fw-bold level2-title",
                            style={
                                "fontSize": "16px",
                                "lineHeight": "1.2",
                                "userSelect": "text",
                            },
                        ),
                        html.Div(
                            n.summary.subtitle,
                            className="text-muted small mt-1 level2-subtitle",
                            style={"userSelect": "text"},
                        ) if n.summary.subtitle else None,
                        render_badges(
                            badges_for_view(n.summary.badges or [], "header"),
                            className="mt-2",
                        ) if badges_for_view(n.summary.badges or [], "header") else None,
                    ],
                    className="w-100 level2-header",
                ),
                item_id=n.id,
                className="level2-accordion-item",
            )
        )

    accordion = dbc.Accordion(accordion_items, id="level2-accordion-root", flush=True, active_item=None, always_open=False)

    new_selected = dict(selected or {})
    new_selected.update({"level1": level1_id, "level2": None})

    return accordion, classnames, level2_title, new_selected, node_map


@callback(
    Output({"type": "level2-detail-content", "index": MATCH}, "children"),
    Input("level2-accordion-root", "active_item"),
    Input("store-file-sort", "data"),
    Input("store-file-tab", "data"),
    State({"type": "level2-detail-content", "index": MATCH}, "id"),
    State("store-node-by-id", "data"),
    prevent_initial_call=True,
)
def update_level2_details(active_item, sort_state, tab_state, component_id, node_map):
    current_id = component_id["index"]
    if active_item != current_id:
        return dash.no_update

    print("===== update_level2_details")

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

    current_sort = sort_state or {"column": "name", "direction": "asc", "index": None}
    if current_sort.get("index") != current_id:
        current_sort = {"column": "name", "direction": "asc", "index": current_id}

    current_tab = "tab-inputs"
    if tab_state and tab_state.get("index") == current_id:
        current_tab = tab_state.get("active_tab", "tab-inputs")

    return html.Div(
        [
            render_id_row(
                current_id,
                label="WR ID",
                className="small px-2 pt-2 mb-2",
                item_type=node.item_type,
                show_external_button=True,
            ),
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
                        render_files_tab(inputs, "inputs", current_id, current_sort),
                        label=f"Input Files ({len(inputs)})",
                        tab_id="tab-inputs",
                        label_class_name="fw-bold text-primary",
                        className="p-2 border border-top-0 bg-white rounded-bottom",
                    ),
                    dbc.Tab(
                        render_files_tab(outputs, "outputs", current_id, current_sort),
                        label=f"Output Files ({len(outputs)})",
                        tab_id="tab-outputs",
                        label_class_name="fw-bold text-success",
                        className="p-2 border border-top-0 bg-white rounded-bottom",
                    ),
                ],
                id={"type": "wr-tabs", "index": current_id},
                active_tab=current_tab,
            ),
        ],
        className="px-2 pb-2",
    )

clientside_callback(
    """
    function(search_term, input_id, current_class) {
        if (!input_id || typeof input_id.index === "undefined") {
            return current_class || "mb-2 shadow-sm";
        }

        const term = (search_term || "").toLowerCase().trim();
        const currentIndex = String(input_id.index);
        const rows = document.getElementsByClassName("file-row-item");

        for (let i = 0; i < rows.length; i++) {
            const row = rows[i];

            if (row.id && row.id.includes(currentIndex)) {
                const fileName = (row.getAttribute("data-filename") || "").toLowerCase();
                row.style.display = fileName.includes(term) ? "" : "none";
            }
        }

        return current_class || "mb-2 shadow-sm";
    }
    """,
    Output({"type": "file-search", "index": MATCH}, "className"),
    Input({"type": "file-search", "index": MATCH}, "value"),
    State({"type": "file-search", "index": MATCH}, "id"),
    State({"type": "file-search", "index": MATCH}, "className"),
    prevent_initial_call=True,
)


@callback(
    Output("store-file-sort", "data"),
    Input({"type": "file-sort", "column": ALL, "index": ALL}, "n_clicks"),
    State({"type": "file-sort", "column": ALL, "index": ALL}, "id"),
    State("store-file-sort", "data"),
    prevent_initial_call=True,
)
def update_file_sort(n_clicks, ids, current_sort):
    if not ctx.triggered_id:
        return dash.no_update

    triggered = ctx.triggered_id
    column = triggered.get("column")
    index = triggered.get("index")

    current_sort = current_sort or {}
    current_column = current_sort.get("column")
    current_direction = current_sort.get("direction", "desc")
    current_index = current_sort.get("index")

    if current_column == column and current_index == index:
        new_direction = "asc" if current_direction == "desc" else "desc"
    else:
        new_direction = "asc" if column == "name" else "desc"

    return {
        "column": column,
        "direction": new_direction,
        "index": index,
    }

@callback(
    Output("store-file-tab", "data"),
    Input({"type": "wr-tabs", "index": ALL}, "active_tab"),
    State({"type": "wr-tabs", "index": ALL}, "id"),
    State("store-file-tab", "data"),
    prevent_initial_call=True,
)
def update_file_tab(active_tabs, ids, current_tab_state):
    if not ctx.triggered_id:
        return dash.no_update

    triggered = ctx.triggered_id
    index = triggered.get("index")

    selected_tab = None
    for tab_value, tab_id in zip(active_tabs or [], ids or []):
        if tab_id.get("index") == index:
            selected_tab = tab_value
            break

    if not selected_tab:
        return dash.no_update

    return {
        "index": index,
        "active_tab": selected_tab,
    }


@callback(
    Output("viewer-modal", "is_open"),
    Output("viewer-modal-title", "children"),
    Output("viewer-modal-body", "children"),
    Output("store-viewer-request", "data"),
    Output("store-image-zoom", "data", allow_duplicate=True),
    Input(
        {"type": "btn-view", "index": ALL, "file_name": ALL, "category": ALL, "vault_id": ALL, "is_folder": ALL},
        "n_clicks",
    ),
    Input("viewer-modal-close", "n_clicks"),
    State(
        {"type": "btn-view", "index": ALL, "file_name": ALL, "category": ALL, "vault_id": ALL, "is_folder": ALL},
        "id",
    ),
    prevent_initial_call=True,
)
def open_viewer_modal(n_clicks_list, close_clicks, id_list):
    triggered = ctx.triggered_id

    if triggered == "viewer-modal-close":
        return False, dash.no_update, dash.no_update, None, {"scale": 1.0}

    if not triggered or not isinstance(triggered, dict) or triggered.get("type") != "btn-view":
        return (dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update,)

    if not n_clicks_list or not any((n or 0) > 0 for n in n_clicks_list):
        return (dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update,)

    triggered_clicks = 0
    for clicks, btn_id in zip(n_clicks_list or [], id_list or []):
        if btn_id == triggered:
            triggered_clicks = clicks or 0
            break

    if triggered_clicks <= 0:
        return (dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update,)

    file_id = triggered.get("index")
    file_name = triggered.get("file_name")
    vault_id = triggered.get("vault_id")
    is_folder = bool(triggered.get("is_folder", False))

    if not file_id or not file_name or not vault_id or is_folder:
        return (
            True,
            "Viewer",
            html.Div("Cannot preview this item.", className="text-danger"),
            None,
            {"scale": 1.0},
        )

    loading_body = html.Div(
        [
            dbc.Spinner(size="md", color="secondary"),
            html.Div("Loading preview...", className="text-muted mt-3"),
        ],
        className="d-flex flex-column justify-content-center align-items-center",
        style={"minHeight": "50vh"},
    )

    return (
        True,
        file_name,
        loading_body,
        {
            "file_id": file_id,
            "file_name": file_name,
            "vault_id": vault_id,
        },
        {"scale": 1.0},
    )

@callback(
    Output("viewer-modal-body", "children", allow_duplicate=True),
    Output("store-viewer-state", "data"),
    Input("store-viewer-request", "data"),
    prevent_initial_call=True,
)
def load_viewer_content(viewer_request):
    if not viewer_request or not viewer_request.get("file_id"):
        return dash.no_update, dash.no_update

    viewer_file_ref = ViewerFileRef(
        file_id=viewer_request["file_id"],
        file_name=viewer_request["file_name"],
        vault_id=viewer_request["vault_id"],
    )

    try:
        viewer_file = resolve_viewer_file(
            service=service,
            viewer_file_ref=viewer_file_ref,
            temp_viewer_path=TEMP_VIEWER_PATH,
        )
        body = render_viewer_content(viewer_file)

        return (
            body,
            {
                "file_id": viewer_file_ref.file_id,
                "file_name": viewer_file.file_name,
                "local_path": str(viewer_file.local_path),
            },
        )

    except Exception as e:
        return (
            html.Div(f"Viewer failed: {e}", className="text-danger"),
            {},
        )

@callback(
    Output("store-image-zoom", "data"),
    Input("img-zoom-in", "n_clicks"),
    Input("img-zoom-out", "n_clicks"),
    Input("img-zoom-reset", "n_clicks"),
    State("store-image-zoom", "data"),
    prevent_initial_call=True,
)
def update_image_zoom(n_in, n_out, n_reset, zoom_data):
    zoom_data = zoom_data or {"scale": 1.0}
    scale = float(zoom_data.get("scale", 1.0))

    triggered = ctx.triggered_id

    if triggered == "img-zoom-in":
        scale = min(scale + 0.25, 5.0)
    elif triggered == "img-zoom-out":
        scale = max(scale - 0.25, 0.25)
    elif triggered == "img-zoom-reset":
        scale = 1.0

    return {"scale": scale}

@callback(
    Output("viewer-image", "style"),
    Input("store-image-zoom", "data"),
    prevent_initial_call=True,
)
def apply_image_zoom(zoom_data):
    scale = float((zoom_data or {}).get("scale", 1.0))

    return {
        "maxWidth": "100%",
        "maxHeight": "75vh",
        "objectFit": "contain",
        "cursor": "zoom-in",
        "transition": "transform 0.2s ease",
        "display": "block",
        "margin": "0 auto",
        "borderRadius": "6px",
        "transform": f"scale({scale})",
        "transformOrigin": "center center",
    }

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
        request_id = str(uuid.uuid4().hex.upper())
        request_dir = os.path.join(TEMP_DOWNLOAD_PATH, request_id)
        os.makedirs(request_dir, exist_ok=True)
        touch_dir(request_dir)

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


@callback(
    Output({"type": "file-upload-status", "index": MATCH, "category": MATCH}, "children"),
    Input({"type": "file-upload", "index": MATCH, "category": MATCH}, "contents"),
    State({"type": "file-upload", "index": MATCH, "category": MATCH}, "filename"),
    State({"type": "file-upload", "index": MATCH, "category": MATCH}, "id"),
    prevent_initial_call=True,
)
def handle_file_upload(contents_list, filenames, component_id):
    if not contents_list or not filenames:
        return dash.no_update

    wr_id = component_id["index"]
    category = component_id["category"]

    try:
        request_dir = os.path.join(TEMP_UPLOAD_PATH, str(wr_id), category)
        touch_dir(request_dir)

        saved_files = []

        for contents, filename in zip(contents_list, filenames):
            saved_path = save_uploaded_file(contents, filename, request_dir)
            saved_files.append(Path(saved_path).name)

        touch_dir(request_dir)

        return html.Div(
            [
                html.Div(
                    f"Uploaded {len(saved_files)} file(s) to {category}.",
                    className="text-success fw-semibold",
                ),
                html.Ul(
                    [html.Li(name) for name in saved_files],
                    className="mb-0 mt-1",
                ),
            ]
        )

    except Exception as e:
        return html.Div(f"Upload failed: {e}", className="text-danger")


import re
import os
import uuid
import math
from datetime import datetime
import dash
from dash import dcc, html, Input, Output, State, callback, clientside_callback, ClientsideFunction, ALL, MATCH, ctx
import dash_bootstrap_components as dbc
from logic.services.minerva_client import MinervaClient
#from logic.services.dummy_client import DummyClient

#from dummy_data import MinervaClient

# --- [Configuration: Viewer Settings] ---

# --- [1. API Simulation Functions] ---
url = "http://seow22mindev01/AnsysMinerva"
db = "MinervaDB"
user = "admin"
password = "minerva"
minerva = MinervaClient(url, db, user, password)
#minerva = DummyClient()  # For testing without real server

# --- [2. Helper Functions] ---

# Fixed Extension Mapping (Extension: Viewer Type)
FIXED_VIEWER_CONFIG = {
    '.pdf': 'PDF_VIEWER',
    '.txt': 'TEXT_VIEWER',
    '.csv': 'TABLE_VIEWER',
    '.xlsx': 'TABLE_VIEWER'
}
# Pattern Mapping (Regex: Viewer Type)
# Stored in a list of tuples to ensure ordered sequential checking.
PATTERN_VIEWER_CONFIG = [
    (r"\.s\d+p", "TOUCHSTONE_VIEWER"),
    (r"\.v\d+", "VERSION_VIEWER"),
    (r"\.r\d{2,3}x", "SPEC_VIEWER")
]
def get_viewer_type(file_name):
    """Determines the appropriate viewer type based on file extension or regex pattern."""
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
    """Maps status strings to Bootstrap theme colors."""
    s = str(status).lower() if status else ""
    if any(x in s for x in ["active", "open", "success", "running"]): return "light"
    if any(x in s for x in ["close", "closed", "complete"]): return "dark"
    if any(x in s for x in ["new"]): return "warning"
    if any(x in s for x in ["progress", "queued", "in work"]): return "success"
    if any(x in s for x in ["accepted", "in review"]): return "info"
    if any(x in s for x in ["paused", "failed", "error"]): return "danger"
    return "secondary"

def render_dynamic_meta(data_dict, exclude_keys):
    """Converts dictionary items into metadata spans with styling."""
    return [
        html.Span([
            html.B(f"{k}: ", className="text-dark"), f"{v}"
        ], className="me-3 small text-muted border-end pe-2 mb-1")
        for k, v in data_dict.items() if k not in exclude_keys and v
    ]

def render_placeholder(text, height="150px"):
    """Renders a simple UI placeholder for empty states."""
    return html.Div([
        html.Div(text, className="text-muted small fw-light px-4 text-center")
    ], style={
        "height": height,
        "border": "1px dashed #ced4da",
        "borderRadius": "8px",
        "backgroundColor": "#fcfcfc",
        "display": "flex",
        "alignItems": "center",
        "justifyContent": "center"
    }, className="w-100 mb-3")

# --- [3. App Initialization & Layout] ---
app = dash.Dash(__name__,
                external_stylesheets=[dbc.themes.FLATLY, dbc.icons.BOOTSTRAP],
                suppress_callback_exceptions=True)

app.layout = dbc.Container([
    dbc.Row([
        # --- [LEFT COLUMN: Sidebar Filters & Project List] ---
        dbc.Col([
            html.Div([
                # Filter Section
                html.Div([
                    html.H4("Filters", className="fw-bold mb-3"),
                    dbc.Row([
                        dbc.Col([
                            dcc.Dropdown(id="filter-year", placeholder="Year", clearable=True, style={"fontSize": "13px"})
                        ], width=5),
                        dbc.Col([
                            dcc.Dropdown(id="filter-product", placeholder="Product", clearable=True, style={"fontSize": "13px"})
                        ], width=7),
                    ], className="g-2 mb-3 align-items-center"),
                    html.Hr(className="mt-2"),
                ], style={"flex": "0 0 auto", "padding": "0 5px"}),

                # Scrollable Project List
                dcc.Loading(html.Div(
                    id="project-list-container",
                    style={"flex": "1 1 auto", "overflowY": "auto", "paddingRight": "5px"}
                ))
            ], style={
                "height": "calc(100vh - 40px)",
                "display": "flex",
                "flexDirection": "column",
                "position": "sticky",
                "top": "20px",
                "overflowX": "hidden"
            })
        ], width=3, className="bg-light border-end p-3"),

        # --- [RIGHT COLUMN: Main Content Area] ---
        dbc.Col([
            html.Div([
                # 1. Header Area
                html.Div(id="prj-header-area", children=[
                    html.H4("Project Dashboard", className="fw-bold text-dark mb-1"),
                    dcc.Loading(html.P("Select a project from the sidebar to load simulation data.", className="text-muted small"))
                ], className="mb-4"),

                # 2. SR (Simulation Request) Section
                html.Div([
                    html.H6("Simulation Requests", className="fw-bold text-secondary mb-3"),
                    dcc.Loading(id="sr-cards-area", children=render_placeholder("Please select a project."))
                ]),

                dcc.Loading(
                        id="loading-download",
                        type="default",  # circle, dot, default 중 선택
                        fullscreen=False,
                        children=[html.Div(id="loading-output-target")], # 콜백의 Output이 될 빈 그릇
                        className="text-muted small"
                ),

                # 3. WR (Work Request) Section & File Table Integration
                html.Div([
                    html.H6("Work Requests", className="fw-bold text-secondary mb-3 mt-4"),
                    # 아코디언 내부에서 탭(Input/Output)과 트리 테이블이 로드됨
                    html.Div(id="wr-accordion-area", children=render_placeholder("Select an SR card."))
                ]),

                # 4. Optional: Quick Info Footer (선택 사항)
                html.Div(id="footer-status", className="mt-5 pt-3 border-top text-muted small")

            ], className="p-4", style={"minHeight": "100vh"})
        ], width=9, className="bg-white") # 메인 배경은 깨끗한 화이트로 설정
    ]),
    # --- [Layout Component for Notification] ---
    dbc.Toast(
        id="download-toast",
        header="File Transfer",
        is_open=False,
        dismissable=True,
        duration=4000,  # Auto-hide after 4 seconds
        icon="info",
        style={"position": "fixed", "top": 66, "right": 10, "width": 350, "zIndex": 9999},
        children=html.P(id="download-toast-body", className="mb-0 small")
    ),
    dcc.Download(id="download-component")
], fluid=True)

# --- [4. Callback Logic] ---
# Callback: Load filter options from server on app startup
@callback(
    [Output("filter-year", "options"),
     Output("filter-product", "options")],
    Input("filter-year", "id"), # Using the component ID to trigger on initial load
    prevent_initial_call=False # Must be False to react to 'None' (clear)
)
def initialize_filter_dropdowns(_):
    """
    Fetches filter metadata from the API and populates dropdown options
    immediately after the app layout is rendered.
    """

    # Map raw lists to Dash dropdown format: [{'label': 'name', 'value': 'val'}, ...]
    year_options = minerva.get_filter_years()
    product_options = minerva.get_filter_products()

    if not year_options:
        year_options = [{"label": "데이터 없음", "value": None}]
    if not product_options:
        product_options = [{"label": "데이터 없음", "value": None}]

    return year_options, product_options



# Callback: Filter project list based on Year/Product dropdowns
@callback(
    Output("project-list-container", "children"),
    [Input("filter-year", "value"),
     Input("filter-product", "value")],
     prevent_initial_call=True
)
def update_project_list(selected_year, selected_product):
    """Fetches and renders projects filtered by sidebar selections."""
    projects = minerva.list_projects(year=selected_year, product=selected_product)

    if not projects:
        return html.Div("No projects found.", className="text-muted p-3 small text-center")

    return dbc.ListGroup([
        render_project_item(p) for p in projects
    ], flush=True)

def render_project_item(p):
    """
    Renders an individual project item with clean logic.
    """
    name = p.get('name', 'Unknown')
    item_num = p.get('item_number', 'N/A')
    product_category = p.get('_product_category', 'N/A')
    state = p.get('state', 'Unknown')
    project_id = p.get('id', str(uuid.uuid4()))

    # Build list of info rows
    info_rows = [
        html.Div(name, className="fw-bold text-dark", style={"fontSize": "14px"}),
        html.Div(item_num, className="text-muted", style={"fontSize": "11px", "marginTop": "2px"}),
        html.Div(product_category, className="text-muted italic", style={"fontSize": "11px", "fontStyle": "italic"})
    ]

    return dbc.ListGroupItem([
        html.Div([
            html.Div(info_rows, style={"flex": "1", "minWidth": "0"}),
            dbc.Badge(state, color=get_status_color(state), pill=True)
        ], className="d-flex justify-content-between align-items-center")
    ], id={"type": "prj-item", "index": project_id}, action=True, className="border-0 border-bottom py-3")


# Callback: Handle project selection to update header and SR cards
@callback(
    [Output("prj-header-area", "children"),
     Output("sr-cards-area", "children"),
     Output("wr-accordion-area", "children", allow_duplicate=True)],
    Input({"type": "prj-item", "index": ALL}, "n_clicks"),
    prevent_initial_call=True
)
def update_project_view(n_clicks):
    if not ctx.triggered_id or not any(n_clicks):
        return dash.no_update, dash.no_update, dash.no_update

    prj_id = ctx.triggered_id['index']
    print(f"DEBUG: Project id -> {prj_id}")

    prj_info = minerva.get_project_by_id(prj_id)
    sr_list = minerva.list_sim_requests(prj_id)  # Placeholder for project info retrieval

    prj_name = prj_info.get('name')
    prj_state = prj_info.get('state', 'Unknown')

    header = html.Div([
        html.H2(prj_name, className="fw-bold d-inline-block me-3 mb-0"),
        dbc.Badge(prj_state, color=get_status_color(prj_state), pill=True)
    ], className="bg-white p-3 rounded shadow-sm border-start border-primary border-4 mb-2")

    # 4. Create SR Cards UI
    if not sr_list:
        sr_cards = render_placeholder("No Simulation Requests found for this project.")
    else:
        sr_cards = render_sr_section(sr_list)

    return header, sr_cards, render_placeholder(f"Select an SR to see Work Requests.", height="250px")

def render_sr_section(sr_list):
    """
    Renders SR cards in a responsive grid layout.
    """
    if not sr_list:
        return html.Div("No Simulation Requests found.", className="text-muted p-5 text-center")

    # Create a list of columns containing the cards
    # Using 'xs', 'md' for responsive design
    columns = [
        dbc.Col(
            render_sr_card(sr),
            xs=12, sm=6, md=4, lg=4, # 1 per row on mobile, 3 per row on desktop
            className="d-flex align-items-stretch" # Make all cards in a row same height
        ) for sr in sr_list
    ]

    return html.Div([
        #html.H5("Simulation Requests", className="fw-bold mb-3 text-secondary"),
        # dbc.Row will wrap the columns automatically
        dbc.Row(columns, className="g-3") # 'g-3' adds consistent gutter spacing
    ], style={
        "maxHeight": "70vh", # Limit height to 70% of viewport
        "overflowY": "auto",  # Enable vertical scroll if content overflows
        "padding": "10px"
    })

def render_sr_card(sr):
    """
    Renders the internal card content.
    """
    sr_id = sr.get('id')
    sr_num = sr.get('_item_number', 'No #')
    development_stage = sr.get('_development_stage', 'N/A')
    sr_type = sr.get('_simulation_type', 'Undefined')
    sr_state = sr.get('state', 'Unknown')
    sr_requested = sr.get('created_on', '').split('T')[0] if sr.get('created_on') else 'N/A'

    return html.Div([
        dbc.Card([
            dbc.CardBody([
                html.Div([
                    html.Small(sr_num, className="text-muted fw-bold", style={"fontSize": "11px"}),
                    dbc.Badge(sr_state, color=get_status_color(sr_state), pill=True, style={"fontSize": "10px"})
                ], className="d-flex justify-content-between align-items-center mb-2"),

                html.H6(development_stage, className="fw-bold mb-3", style={"height": "18px", "overflow": "hidden"}),

                html.Div([
                    html.Div([html.I(className="bi bi-tag me-2"), sr_type], className="small text-muted"),
                    html.Div([html.I(className="bi bi-calendar-event me-2"), f"Requested: {sr_requested}"], className="small text-muted")
                ], className="border-top pt-2")
            ])
        ], className="h-100 shadow-sm border-0 sr-card-hover")
    ], id={"type": "sr-card", "index": sr_id}, n_clicks=0, style={"cursor": "pointer", "width": "100%"})



# Callback: Handle SR card click to load WR accordion and highlight card
@callback(
    [Output("wr-accordion-area", "children"),
     Output({"type": "sr-card", "index": ALL}, "className")],
    Input({"type": "sr-card", "index": ALL}, "n_clicks"),
    [State({"type": "sr-card", "index": ALL}, "id")],
    prevent_initial_call=True
)
def update_wr_list(n_clicks, sr_ids):
    if not any(n_clicks):
        return dash.no_update, [dash.no_update] * len(sr_ids)

    sr_id = ctx.triggered_id['index']

    # Update class names for highlighting the selected card
    classnames = [
        "h-100 shadow border border-3 border-primary bg-primary bg-opacity-10" if sid['index'] == sr_id
        else "h-100 shadow-sm border-0" for sid in sr_ids
    ]

    wrs = minerva.list_work_requests_by_sr_id(sr_id)

    if not wrs:
        return html.Div("No Work Requests found.", className="p-4 text-center text-muted"), classnames

    accordion_items = []
    for wr in wrs:
        # Convert ISO date string to a user-friendly format
        created_on = wr.get('created_on', 'N/A')
        current_state = wr.get('current_state@aras.keyed_name', 'N/A')
        owned_by = wr.get('owned_by_id@aras.keyed_name', 'N/A')
        item_number = wr.get('item_number', 'N/A')
        wr_name = wr.get('name', '')
        wr_state = wr.get('state', 'N/A')
        wr_id = wr.get('id', str(uuid.uuid4()))

        if created_on:
            try:
                clean_date = created_on.replace('Z', '+00:00')
                dt_obj = datetime.fromisoformat(clean_date)
                formatted_date = dt_obj.strftime("%Y-%m-%d %H:%M")
            except Exception:
                formatted_date = created_on
        else:
            formatted_date = "N/A"

        # Create AccordionItem for each Work Request
        item = dbc.AccordionItem(
            [
                html.Div([
                    # dbc.Badge(f"{current_state}",
                    #           color=get_status_color(current_state), className="me-2"),
                    dbc.Badge(f"{owned_by}",
                              color="light", text_color="dark", className="me-2 border"),
                    # Apply the formatted date here
                    dbc.Badge(f"Created: {formatted_date}", color="light", text_color="secondary", className="me-2 border"),
                ], className="mb-3 p-2 bg-white rounded d-flex flex-wrap border"),

                dcc.Loading(
                    html.Div(
                        id={"type": "wr-detail-content", "index": wr_id},
                        children="Loading files..."
                    )
                )
            ],
            title=html.Div([
                html.B(item_number),
                html.Span(f" - {wr_name}", className="ms-2 text-muted small"),
                dbc.Badge(
                    current_state,
                    color=get_status_color(current_state),
                    className="float-end",
                    pill=True
                ),
            ], className="w-100"),
            item_id=wr_id
        )
        accordion_items.append(item)

    accordion = dbc.Accordion(accordion_items, id="wr-accordion-root", flush=True, active_item=None, always_open=False)

    return accordion, classnames

@callback(
    Output({"type": "wr-detail-content", "index": MATCH}, "children"),
    Input("wr-accordion-root", "active_item"),
    State({"type": "wr-detail-content", "index": MATCH}, "id"),
    prevent_initial_call=True
)
def render_wr_details(active_item, component_id):
    """
    Renders a searchable, tabbed interface for Work Request files.
    """
    current_index = component_id['index']

    # Check if the opened accordion matches this content index
    if active_item != current_index:
        return dash.no_update

    # Fetch data from Minerva service
    file_data = minerva.list_work_request_files(current_index)
    inputs = file_data.get('inputs', [])
    outputs = file_data.get('outputs', [])

    return html.Div([
        # 1. Search Bar UI (Placed above tabs)
        html.Div([
            dbc.Input(
                id={"type": "file-search", "index": current_index},
                placeholder="Search files in this request...",
                size="sm",
                className="mb-2 shadow-sm",
                debounce=True # Triggers after user stops typing
            )
        ], className="px-2"),
        # 2. Tabs for Inputs/Outputs
        dbc.Tabs([
            dbc.Tab(
                # Ensure create_tree_table receives 3 arguments
                create_tree_table(inputs, "inputs", current_index),
                label=f"Input Files ({len(inputs)})",
                tab_id="tab-inputs",
                label_class_name="fw-bold text-primary",
                className="p-2 border border-top-0 bg-white rounded-bottom"
            ),
            dbc.Tab(
                create_tree_table(outputs, "outputs", current_index),
                label=f"Output Files ({len(outputs)})",
                tab_id="tab-outputs",
                label_class_name="fw-bold text-success",
                className="p-2 border border-top-0 bg-white rounded-bottom"
            ),
        ], id={"type": "wr-tabs", "index": current_index}, active_tab="tab-inputs")
    ], className="px-2 pb-2")

# --- [Part 2: Clientside Callback for High-Performance Search] ---
clientside_callback(
    """
    function(search_term, content_id) {
        // [GUARD] If content_id is not yet ready, stop to prevent 'apply' error
        if (!content_id || typeof content_id.index === 'undefined') {
            return window.dash_clientside.no_update;
        }

        const term = search_term ? search_term.toLowerCase().trim() : "";
        const currentIndex = String(content_id.index);

        // Fetch all rows with the specific class
        const rows = document.getElementsByClassName('file-row-item');

        for (let i = 0; i < rows.length; i++) {
            let row = rows[i];

            // Filter: Only process rows that match the current accordion index
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
    State({"type": "wr-detail-content", "index": MATCH}, "id"),
    prevent_initial_call=True
)


def format_size(size_bytes):
    """
    Converts raw bytes into a human-readable format (KB, MB, GB).
    """
    if size_bytes is None or size_bytes == 0:
        return "0 B"

    # Convert string to float if necessary
    try:
        if isinstance(size_bytes, str):
            size_bytes = float(size_bytes)
    except (ValueError, TypeError):
        return "Unknown"

    # Unit names
    size_name = ("B", "KB", "MB", "GB", "TB")

    # Calculate log base 1024
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)

    return f"{s} {size_name[i]}"

def get_viewer_type(filename):
    """
    Determines if a file can be previewed based on its extension.
    Returns the viewer type or None.
    """
    if not filename:
        return None

    ext = filename.split('.')[-1].lower()

    # Define supported extensions for preview
    viewable_extensions = {
        'pdf': 'pdf',
        'txt': 'text',
        'log': 'text',
        'png': 'image',
        'jpg': 'image',
        'jpeg': 'image',
        'json': 'json'
    }

    return viewable_extensions.get(ext)

def create_tree_table(file_list, category, active_item):
    """
    Renders a tree-structured table with interactive buttons for each file/folder.
    """
    if not file_list:
        return html.Div("No files found.", className="p-4 text-muted small text-center")

    rows = []
    for f in file_list:
        file_id = f.get('id')
        file_name = f.get('name')
        is_folder = f.get('is_folder')
        depth = f.get('depth', 0)
        file_size = f.get('size')

        rows.append(html.Tr([
            # Column 1: Tree Name (Indentation + Icon + Name)
            html.Td([
                html.Span("└─ " if depth > 0 else "",
                          style={"color": "#adb5bd", "fontFamily": "monospace"}),
                html.Span("📂 " if is_folder else "📄 ", className="me-1"),
                html.Span(file_name)
            ],
            style={
                "paddingLeft": f"{depth * 20 + 15}px",
                "paddingTop": "4px", "paddingBottom": "4px",
                "fontWeight": "600" if is_folder else "400",
                "fontSize": "14px"
            },
            className="align-middle"),

            # Column 2: Formatted Size
            html.Td(
                format_size(file_size) if not is_folder else "-",
                className="text-end text-muted align-middle",
                style={"fontSize": "14px", "paddingTop": "4px", "paddingBottom": "4px"}
            ),

            # Column 3: Interactive Action Buttons
            html.Td(
                dbc.ButtonGroup([
                    # 1. View Button (Only for viewable files)
                    dbc.Button(
                        html.Img(src=dash.get_asset_url("icons/eye.svg"), style={"width": "14px"}),
                        id={"type": "btn-view", "index": file_id, "file_name": file_name, "category": category},
                        color="white", size="sm", className="border py-0 px-2",
                        style={"visibility": "visible" if not is_folder and get_viewer_type(file_name) else "hidden"}
                    ),
                    # 2. Download Button (Supports both file and folder download via CLI)
                    dbc.Button(
                        html.Img(src=dash.get_asset_url("icons/folder-download.svg" if is_folder else "icons/download.svg"),
                                 style={"width": "14px"}),
                        id={"type": "btn-download", "index": file_id, "file_name": file_name, "category": category},
                        n_clicks=0,
                        color="white", size="sm", className="ms-1 border py-0 px-2",
                    ),
                    # 3. Minerva External Link Button
                    dbc.Button([
                        html.Img(src=dash.get_asset_url("icons/arrow-up-right-square.svg"),
                                 style={"width": "12px", "marginRight": "4px"}),
                        "Minerva"
                    ],
                    id={"type": "btn-external", "index": file_id, "file_name": file_name, "category": category},
                    color="primary", outline=True, size="sm",
                    className="ms-1 py-0 px-2 d-flex align-items-center justify-content-center",
                    style={"fontSize": "12px"})
                ], size="sm", className="w-100"),
                className="text-center align-middle",
                style={"paddingTop": "2px", "paddingBottom": "2px"}
            )
        ],
        # Table Row ID for tracking
        className="file-row-item",
        id={"type": "file-row", "index": active_item, "file_id": file_id},
        **{"data-filename": file_name.lower()},
        style={"height": "32px"}))

    return dbc.Table([
        html.Thead(html.Tr([
            html.Th("Name", className="ps-4"),
            html.Th("Size", className="text-end", style={"width": "100px"}),
            html.Th("Actions", className="text-center", style={"width": "180px"})
        ], style={"lineHeight": "1.2"})),
        html.Tbody(rows, id={"type": "file-table-body", "index": active_item, "category": category})
    ], hover=True, borderless=True, className="mb-0 table-sm")



# --- [Callback for File Download] ---
@callback(
    [Output("download-component", "data"),
     Output("download-toast", "is_open"),
     Output("download-toast-body", "children"),
     Output("loading-output-target", "children")],
    # ID dictionary keys MUST match exactly: type, index, category
    Input({"type": "btn-download", "index": ALL, "file_name": ALL, "category": ALL}, "n_clicks"),
    prevent_initial_call=True
)
def handle_file_download(n_clicks_list):
    # 1. Check if the callback was triggered by an actual click
    # n_clicks_list will be a list of integers [0, 1, 0...]

    if not ctx.triggered or not any(click > 0 for click in n_clicks_list if click is not None):
        return dash.no_update
    print(f"Debug: Triggered ID: {ctx.triggered_id}")

    # 2. Identify which specific button was clicked
    # triggered_id will look like: {"type": "btn-download", "index": "FILE_XYZ", "category": "inputs"}
    triggered_info = ctx.triggered_id

    # 3. Extract information
    file_id = triggered_info['index']
    category = triggered_info['category']
    file_name = triggered_info['file_name']

    print(f"!!! DOWNLOAD START !!! File ID: {file_id} {file_name}, Category: {category}")

    try:
        success_msg = f"[{category.upper()}] {file_name} 다운로드를 시작합니다."

        DOWNLOAD_DIR = "C:/Minerva_Downloads"
        if not os.path.exists(DOWNLOAD_DIR):
            os.makedirs(DOWNLOAD_DIR)

        # Execute the download to server local directory via MinervaClient
        minerva.download_file_by_id(file_id, local_directory=DOWNLOAD_DIR)

        #file_url = minerva.get_file_url_by_id(file_id)
        #print(f"DEBUG: File URL -> {file_url}")

        # download to local via dcc.Download
        data = dcc.send_file(DOWNLOAD_DIR + "/" + file_name)

        return data, True, success_msg, ""

    except Exception as e:
        print(f"ERROR: {str(e)}")
        return True, f"다운로드 실패: {str(e)}"



if __name__ == "__main__":
    app.run(debug=True)

import dash
import dash_bootstrap_components as dbc

from ui.minerva_page import layout, run_startup_cleanup, start_temp_cleanup_scheduler

from ui.viewer.viewer_manager import (
    configure_viewer,
)

app = dash.Dash(
    __name__,
    #requests_pathname_prefix="/AnsysMinerva/custom/dash/",
    external_stylesheets=[dbc.themes.FLATLY, dbc.icons.BOOTSTRAP],
    suppress_callback_exceptions=True,
)

configure_viewer(
    relative_path_builder=app.get_relative_path,
    server=app.server,
)

run_startup_cleanup()
start_temp_cleanup_scheduler()

app.layout = layout()

if __name__ == "__main__":
    app.run(host="127.0.0.1", debug=True)
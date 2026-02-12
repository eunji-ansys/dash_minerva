import os
from ..core.minerva.auth import MinervaAuth
from ..core.minerva.odata import MinervaODataClient
from ..core.minerva.cli import CLIAuthContext, MinervaCLIClient
import logging
from ..utils.decorators import log
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

class VDClient:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, url: str, db: str, user: str, pw: str):
        if hasattr(self, '_init'): return

        # 1. Initialize Core Layers
        self.odata_auth = MinervaAuth(url, db, user, pw)
        self.odata = MinervaODataClient(self.odata_auth)
        self.cli = MinervaCLIClient(url, db)

        self.cli_auth = CLIAuthContext(
            mode="Explicit",
            user=os.getenv("MINERVA_USER"),
            password=os.getenv("MINERVA_PASS")
        )
        self.url = url
        self.db = db
        self._init = True

    @log("Fetching development years", mode="both")
    def get_filter_years(self):
        """Simulates API call to fetch dynamic filter categories from server."""
        years = self.odata.get_list_values("6158D0BE38234B1E82E1C88D0C79C121") # VD_DevelopmentYear
        return years

    @log("Fetching product filters", mode="both")
    def get_filter_products(self):
        """Simulates API call to fetch dynamic filter categories from server."""
        products = self.odata.get_list_values("62841ADCFAA44C53BE010BFF1AC1C70D") # VD_ProductCategory
        return products

    @log("Fetching projects for year: {year} and product: {product}", mode="both")
    def list_projects(self, year=None, product=None):
        """Simulates API call for fetching projects with filters."""

        filters = []
        if year is not None and str(year).strip() != "":
            filters.append(f"_development_year eq '{year}'")
        if product is not None and str(product).strip() != "":
            filters.append(f"_product_category eq '{product}'")
        filter_string = " and ".join(filters) if filters else None

        target_fields = ["id", "item_number", "name", "_model_name", "state"]

        items = self.odata.get_item_list("ans_Project",select_fields=target_fields, filter_string=filter_string)
        return items

    @log("Fetching project by ID: {project_id}", mode="both")
    def get_project_by_id(self, project_id):
        """Fetches project details by ID."""
        item = self.odata.get_item_by_id("ans_Project", item_id=project_id)
        return item

    @log("List simulation requests for Project ID: {project_id}", mode="both")
    def list_sim_requests(self, project_id):
        """Simulates fetching Simulation Requests (SR) for a project."""
        filter_string = f"_project_id eq '{project_id}'"
        items = self.odata.get_item_list("VD_SimulationRequest", filter_string=filter_string)
        return items

    @log("List work requests for Simulation Request ID: {sr_id}", mode="both")
    def list_work_requests_by_sr_id(self, sr_id):
        """Simulates fetching Work Requests (WR) for an SR."""
        items = []
        select_fields = "id"
        expand_str = "related_id($select=id,item_number,name,classification,created_on,current_state,owned_by_id,_simulation_type)"
        related_items = self.odata.get_linked_items(
                    item_name="VD_SimulationRequest",
                    item_id=sr_id,
                    relationship_name="VD_SimRequest_WorkRequest",
                    select_fields=select_fields,
                    expand_string=expand_str
                )
        for itm in related_items:
            items.append(itm.get('related_id'))
        return items

    @log("Recursive file scan for Work Request ID: {wr_id}", mode="both")
    def list_work_request_files(self, wr_id: str):
        """
        Fetches all files and folders recursively for a given Work Request.
        """
        results = {"inputs": [], "outputs": []}
        rel_map = {
            "Ans_SimReq_Input": "inputs",
            "Ans_SimReq_Deliverable": "outputs"
        }

        def _get_data_recursive(parent_id, relationship_name, depth=0):
            flattened = []
            expand = "related_id($select=id,keyed_name,file_size,classification,is_folder,local_file)"

            # depth 0 is WR-to-Data relation, depth > 0 is Folder-to-Data (Ans_DataChild)
            item_type = "Ans_SimulationRequest" if depth == 0 else "Ans_Data"
            rel_name = relationship_name if depth == 0 else "Ans_DataChild"

            try:
                items = self.odata.get_linked_items(
                    item_name=item_type,
                    item_id=parent_id,
                    relationship_name=rel_name,
                    expand_string=expand
                )

                for itm in items:
                    node = itm.get('related_id')
                    if not node: continue

                    is_folder = node.get('is_folder') == "1"
                    file_info = {
                        "id": node['id'],
                        "name": node.get('keyed_name'),
                        "size": node.get('file_size', 0),
                        "is_folder": is_folder,
                        "file_id": node.get('local_file'),
                        "type": node.get('classification'),
                        "depth": depth
                    }
                    flattened.append(file_info)

                    # Recursive call if folder exists
                    if is_folder:
                        children = _get_data_recursive(node['id'], None, depth + 1)
                        flattened.extend(children)

            except Exception as e:
                print(f"Error at depth {depth}: {e}")

            return flattened

        # Start recursion for both Input and Output categories
        for rel, category in rel_map.items():
            results[category] = _get_data_recursive(wr_id, rel, depth=0)

        return results

    def get_file_url_by_id(self, id: str) -> str:
        """Fetches the file URL/path on the Minerva server by file ID."""
        ans_data = self.odata.get_item_by_id("Ans_Data", item_id=id, select_fields=["local_file"])
        print(f"DEBUG: Ans_Data for ID {id} -> {ans_data}")
        local_file_id = ans_data.get("local_file@aras.id")
        print(f"DEBUG: Local file path for ID {id} is {local_file_id}")

        file_item = self.odata.get_item_by_id("File", item_id=local_file_id, select_fields=["local_file"])
        print(f"DEBUG: File item for local_file ID {local_file_id} -> {file_item}")

        return None


    #@log("[{timestamp}] Download by ID: {id} | Status: {status} | Took: {duration}", mode="both")
    def download_file_by_id(self, id: str, local_directory: str):
       path = "Ans_Data\\" + id
       return self.download_file(remote_path=path, local_directory=local_directory)

    @log("[{timestamp}] Download: {remote_path} | Status: {status} | Took: {duration}", mode="both")
    def download_file(self, remote_path: str, local_directory: str):
        """Executes CLI download with integrated auth context."""
        # The result of this call will be captured by the 'after' log as {return_value}
        return self.cli.download(remote=remote_path, auth=self.cli_auth, local=local_directory)
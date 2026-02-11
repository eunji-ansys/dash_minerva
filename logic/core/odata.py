import requests
import json
from .auth import MinervaAuth
from ..utils.decorators import log

class MinervaODataClient:
    """Handles all OData API operations using an Auth provider."""
    def __init__(self, auth_provider: MinervaAuth):
        self.auth = auth_provider
        self.api_base = f"{self.auth.base_url}/server/odata"

    def _handle_response(self, response):
        """Internal helper to parse response objects."""
        try:
            if response.status_code in [200, 201]:
                return response.json()
            elif response.status_code == 204:
                return {"status": "success", "code": 204}
            else:
                raise Exception(f"API Error {response.status_code}: {response.text}")
        except json.JSONDecodeError:
            return {"error": "Invalid JSON response", "content": response.text}

    def fetch_data(self, endpoint, select_fields=None, filter_string=None, expand_string=None, retry=True):
        """Generic GET with auto-reauth on 401."""
        url = f"{self.api_base}/{endpoint}"
        params = {}
        if filter_string: params["$filter"] = filter_string
        if expand_string: params["$expand"] = expand_string
        if select_fields:
            params["$select"] = ",".join(select_fields) if isinstance(select_fields, list) else select_fields

        response = requests.get(url, headers=self.auth.headers, params=params)

        if response.status_code == 401 and retry:
            if self.auth.authenticate():
                return self.fetch_data(endpoint, select_fields, filter_string, expand_string, retry=False)
        return response

    # --- CRUD & Specialized Helpers ---
    def get_item_list(self, item_name, **kwargs):
        resp = self.fetch_data(item_name, **kwargs)
        return self._handle_response(resp).get("value", [])

    def get_item_by_id(self, item_name, item_id, **kwargs):
        endpoint = f"{item_name}('{item_id}')"
        resp = self.fetch_data(endpoint, **kwargs)
        return self._handle_response(resp)

    def get_linked_items(self, item_name, item_id, relationship_name, **kwargs):
        endpoint = f"{item_name}('{item_id}')/{relationship_name}"
        resp = self.fetch_data(endpoint, **kwargs)
        data = self._handle_response(resp)
        return data.get("value", [])

    def create(self, item_name, payload):
        url = f"{self.api_base}/{item_name}"
        resp = requests.post(url, headers=self.auth.headers, json=payload)
        return self._handle_response(resp)

    def update(self, item_name, item_id, payload):
        url = f"{self.api_base}/{item_name}('{item_id}')"
        resp = requests.patch(url, headers=self.auth.headers, json=payload)
        return self._handle_response(resp)

    def delete(self, item_name, item_id, purge=False):
        url = f"{self.api_base}/{item_name}('{item_id}')"
        headers = self.auth.headers.copy()
        if purge: headers["@aras.action"] = "purge"
        resp = requests.delete(url, headers=headers)
        return resp.status_code

   # --- List Item ---
    def get_list_values(self, list_id):
        endpoint = f"List('{list_id}')/Value"
        resp = self.fetch_data(endpoint, select_fields=["value", "label"])
        data = self._handle_response(resp)
        items = data.get("value", [])
        return [{"label": i.get("label"), "value": i.get("value")} for i in items]
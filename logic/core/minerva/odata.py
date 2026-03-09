import json
import requests
import hashlib
from typing import Any, Dict, Iterable, List, Optional, Union

import logging
from ...utils.decorators import log
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

Json = Dict[str, Any]
Params = Dict[str, Any]
Headers = Dict[str, str]

class ODataAuth:
    """Handles OAuth2 authentication and credential management."""
    def __init__(self, base_url, database, username, password):
        self.base_url = base_url.rstrip('/')
        self.database = database
        self.username = username
        self.password = password  # Raw password for hashing
        self.token = None
        self.headers = {}
        self.credentials = {
            "username": username,
            "database": database,
            "md5_password": hashlib.md5(password.encode()).hexdigest()
        }

    def authenticate(self) -> bool:
        """Authenticates and updates headers. Returns success status."""
        url = f"{self.base_url}/OAuthServer/connect/token"
        payload = {
            'grant_type': 'password',
            'scope': 'Innovator',
            'client_id': 'IOMApp',
            'username': self.credentials["username"],
            'password': self.credentials["md5_password"],
            'database': self.credentials["database"]
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        try:
            response = requests.post(url, headers=headers, data=payload)
            if response.status_code == 200:
                self.token = response.json()["access_token"]
                self.headers = {
                    "Database": self.credentials["database"],
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/json"
                }
                return True
            return False
        except Exception as e:
            print(f"Auth Exception: {e}")
            return False

class MinervaODataClient:
    """
    REST-style API client over Minerva OData endpoint.

    Public method names:
      - list(), get(), list_related(), create(), patch(), delete()

    Internals:
      - request_raw(): executes HTTP + 401 re-auth retry, returns Response
      - request_json(): calls request_raw() + raises for status + parses JSON
    """

    def __init__(
        self,
        *,
        base_url: str,
        database: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        verify: Union[bool, str] = True,
        timeout: Union[int, float] = 30,
        auth: Optional[ODataAuth] = None,
        session: Optional[requests.Session] = None,
    ):
        """
        Initialize the client.

        If `auth` is provided, it will be used directly (advanced use).
        Otherwise, this client creates and owns a ODataAuth instance.
        """
        self.timeout = timeout
        self.verify = verify
        self.api_base = f"{base_url.rstrip('/')}/server/odata"

        if auth is None:
            if not database:
                raise ValueError("database is required when auth is not provided")
            if not username or not password:
                raise ValueError("username and password are required when auth is not provided")

        self.auth = auth or ODataAuth(
            base_url=base_url,
            database=database,
            username=username,
            password=password,
        )

        self.session = session or requests.Session()

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def _default_headers(self) -> Headers:
        """Return default auth headers."""
        return dict(self.auth.headers)

    def _merge_headers(
        self,
        *,
        extra_headers: Optional[Headers] = None,
        headers_override: Optional[Headers] = None,
    ) -> Headers:
        """
        Merge headers with precedence:
          1) default auth headers
          2) headers_override replaces the entire dict (if provided)
          3) extra_headers overwrites/adds keys (if provided)
        """
        headers = self._default_headers()
        if headers_override is not None:
            headers = dict(headers_override)
        if extra_headers:
            headers.update(extra_headers)
        return headers

    def _raise_for_status(self, response: requests.Response) -> None:
        """Raise exception if status code indicates failure."""
        if response.status_code in (200, 201, 204):
            return
        raise RuntimeError(f"API Error {response.status_code}: {response.text}")

    def _parse_json(self, response: requests.Response) -> Any:
        """Parse JSON response; handle 204 No Content."""
        if response.status_code == 204:
            return {"status": "success", "code": 204}
        try:
            return response.json()
        except json.JSONDecodeError:
            raise RuntimeError(f"Invalid JSON response: {response.text}")

    def _build_odata_params(
        self,
        *,
        select: Optional[Union[str, Iterable[str]]] = None,
        filter: Optional[str] = None,
        expand: Optional[str] = None,
        top: Optional[int] = None,
        skip: Optional[int] = None,
        orderby: Optional[str] = None,
        count: Optional[bool] = None,
    ) -> Params:
        """Build OData query parameters."""
        params: Params = {}
        if filter:
            params["$filter"] = filter
        if expand:
            params["$expand"] = expand
        if select:
            params["$select"] = select if isinstance(select, str) else ",".join(select)
        if top is not None:
            params["$top"] = top
        if skip is not None:
            params["$skip"] = skip
        if orderby:
            params["$orderby"] = orderby
        if count is not None:
            params["$count"] = "true" if count else "false"
        return params

    # ------------------------------------------------------------------
    # request_raw / request_json
    # ------------------------------------------------------------------

    def request_raw(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Params] = None,
        json_body: Optional[Json] = None,
        extra_headers: Optional[Headers] = None,
        headers_override: Optional[Headers] = None,
        retry_401: bool = True,
    ) -> requests.Response:
        """
        Execute an HTTP request and return the raw Response.

        Handles:
          - header composition
          - one-time 401 re-auth retry
        """
        url = f"{self.api_base}/{path.lstrip('/')}"
        headers = self._merge_headers(extra_headers=extra_headers, headers_override=headers_override)

        #logging.debug(f"Request: {method} {url} params={params} json={json_body}")
        response = self.session.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json_body,
            timeout=self.timeout,
            verify=self.verify,
        )
        logging.debug(f"Response: response.text={response.text}")

        if response.status_code == 401 and retry_401:
            if self.auth.authenticate():
                # Token may change after re-auth; rebuild headers and retry once.
                return self.request_raw(
                    method,
                    path,
                    params=params,
                    json_body=json_body,
                    extra_headers=extra_headers,
                    headers_override=headers_override,
                    retry_401=False,
                )

        return response

    def request_json(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Params] = None,
        json_body: Optional[Json] = None,
        extra_headers: Optional[Headers] = None,
        headers_override: Optional[Headers] = None,
        retry_401: bool = True,
    ) -> Any:
        response = self.request_raw(
            method,
            path,
            params=params,
            json_body=json_body,
            extra_headers=extra_headers,
            headers_override=headers_override,
            retry_401=retry_401,
        )
        self._raise_for_status(response)
        return self._parse_json(response)

    # ------------------------------------------------------------------
    # REST-style public API
    # ------------------------------------------------------------------

    def list(
        self,
        resource: str,
        *,
        select: Optional[Union[str, Iterable[str]]] = None,
        filter: Optional[str] = None,
        expand: Optional[str] = None,
        top: Optional[int] = None,
        skip: Optional[int] = None,
        orderby: Optional[str] = None,
        count: Optional[bool] = None,
    ) -> List[Json]:
        """List resources from a collection endpoint."""
        params = self._build_odata_params(
            select=select,
            filter=filter,
            expand=expand,
            top=top,
            skip=skip,
            orderby=orderby,
            count=count,
        )
        data = self.request_json("GET", resource, params=params)
        return data.get("value", []) if isinstance(data, dict) else []

    def get(
        self,
        resource: str,
        resource_id: str,
        *,
        select: Optional[Union[str, Iterable[str]]] = None,
        expand: Optional[str] = None,
    ) -> Json:
        """Get a single resource by id."""
        params = self._build_odata_params(select=select, expand=expand)
        path = f"{resource}('{resource_id}')"
        data = self.request_json("GET", path, params=params)
        return data if isinstance(data, dict) else {"value": data}

    def list_related(
        self,
        resource: str,
        resource_id: str,
        related: str,
        *,
        select: Optional[Union[str, Iterable[str]]] = None,
        filter: Optional[str] = None,
        expand: Optional[str] = "related_id($select=id, keyed_name)",
        top: Optional[int] = None,
        skip: Optional[int] = None,
        orderby: Optional[str] = None,
        count: Optional[bool] = None,
    ) -> List[Json]:
        """
        List related resources via a subresource/navigation path.

        Notes:
        - Relationship collections typically return relationship rows.
        - When `$expand=related_id(...)` is used, the actual target item is
          contained inside the expanded `related_id` field.
        """
        params = self._build_odata_params(
            select=select,
            filter=filter,
            expand=expand,
            top=top,
            skip=skip,
            orderby=orderby,
            count=count,
        )
        path = f"{resource}('{resource_id}')/{related}"
        data = self.request_json("GET", path, params=params)

        if not isinstance(data, dict):
            return []

        rel_rows = data.get("value", [])
        if not isinstance(rel_rows, list):
            return []

        # Extract expanded related_id items; flatten if related_id expands to a list.
        expanded: List[Json] = []
        for i, row in enumerate(rel_rows):
            if not isinstance(row, dict):
                continue
            rid = row.get("related_id")
            if not rid:
                expanded.append(row)  # No related_id means we return the relationship row itself.
            elif isinstance(rid, list):
                expanded.extend([x for x in rid if isinstance(x, dict)])
            elif isinstance(rid, dict):
                expanded.append(rid)

        return expanded

    def create(self, resource: str, payload: Json) -> Json:
        """Create a resource."""
        data = self.request_json("POST", resource, json_body=payload)
        return data if isinstance(data, dict) else {"value": data}

    def patch(self, resource: str, resource_id: str, payload: Json) -> Json:
        """Partially update a resource (PATCH semantics)."""
        path = f"{resource}('{resource_id}')"
        data = self.request_json("PATCH", path, json_body=payload)
        return data if isinstance(data, dict) else {"value": data}

    def delete(self, resource: str, resource_id: str, *, purge: bool = False) -> int:
        """
        Delete a resource. Returns HTTP status code.

        purge is Aras-specific; implemented via extra header.
        """
        path = f"{resource}('{resource_id}')"
        extra_headers = {"@aras.action": "purge"} if purge else None

        response = self.request_raw("DELETE", path, extra_headers=extra_headers)
        # If you want delete() to raise on non-2xx/204, uncomment:
        # self._raise_for_status(response)
        return response.status_code

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def update(self, resource: str, resource_id: str, payload: Json) -> Json:
        """Alias for patch()."""
        return self.patch(resource, resource_id, payload)

    def list_values(self, list_id: str) -> List[Dict[str, Any]]:
        """Aras list helper implemented via REST-style list_related()."""
        items = self.list_related("List", list_id, "Value", select=["value", "label"], expand=None)
        return [{"label": i.get("label"), "value": i.get("value")} for i in items]


    Json = Dict[str, Any]

    def iter_list(
        self,
        entity_set: str,
        *,
        page_size: int = 100,
        max_items: Optional[int] = None,
        select: Optional[Union[str, Iterable[str]]] = None,
        filter: Optional[str] = None,
        expand: Optional[str] = None,
        orderby: Optional[str] = None,
        count: Optional[bool] = None,
    ) -> Iterable[Json]:
        """
        Iterate items from an OData entity set using $top/$skip pagination.

        Assumptions:
        - self.list(...) returns List[Json] (already extracted list of items),
        not a raw OData payload like {"value": [...]}.
        - self.list(...) accepts keyword argument 'filter' (not 'filter_').
        """
        if page_size <= 0:
            raise ValueError("page_size must be > 0")

        # If max_items is 0 or negative, yield nothing.
        if max_items is not None and max_items <= 0:
            return

        yielded = 0
        skip = 0

        while True:
            # Fetch a page of items.
            items = self.list(
                entity_set,
                select=select,
                filter=filter,
                expand=expand,
                top=page_size,
                skip=skip,
                orderby=orderby,
                count=count,
            )

            # No items means we're done.
            if not items:
                break

            for item in items:
                yield item
                yielded += 1

                # Stop once we've yielded enough items.
                if max_items is not None and yielded >= max_items:
                    return

            # Advance the offset by the number of items we just received.
            skip += len(items)

            # If the server returned fewer than page_size items, assume last page.
            if len(items) < page_size:
                break

    def download(self, vault_id: str, dest: str):
        path = f"File('{vault_id}')/$value"
        response = self.request_raw("GET", path)
        print(f"status: {response.status_code} dest: {dest}")
        self._raise_for_status(response)

        with open(dest, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        print(f"Downloaded {vault_id} -> {dest}")
        return response.status_code



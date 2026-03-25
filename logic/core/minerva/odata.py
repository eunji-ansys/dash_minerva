import hashlib
import json
import requests
from typing import Any, Dict, Iterable, List, Optional, Union

import logging
from ...utils.decorators import log

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

Json = Dict[str, Any]
Params = Dict[str, Any]
Headers = Dict[str, str]


class BaseODataAuth:
    """Authentication strategy interface."""

    def authenticate(self) -> bool:
        raise NotImplementedError

    @property
    def headers(self) -> Headers:
        raise NotImplementedError


class ODataApiKeyAuth(BaseODataAuth):
    """Handles API key authentication and default header management."""

    def __init__(
        self,
        *,
        api_key: str,
        api_key_header: str = "x-api-key",
        api_key_prefix: Optional[str] = None,
        accept: str = "application/json",
        extra_headers: Optional[Headers] = None,
    ):
        if not api_key:
            raise ValueError("api_key is required")

        self.api_key = api_key
        self.api_key_header = api_key_header
        self.api_key_prefix = api_key_prefix
        self.accept = accept
        self.extra_headers = dict(extra_headers or {})
        self._headers: Headers = self._build_headers()

    def _build_headers(self) -> Headers:
        key_value = (
            f"{self.api_key_prefix} {self.api_key}" if self.api_key_prefix else self.api_key
        )

        headers: Headers = {
            self.api_key_header: key_value,
            "Accept": self.accept,
        }

        headers.update(self.extra_headers)
        return headers

    @property
    def headers(self) -> Headers:
        return dict(self._headers)

    def authenticate(self) -> bool:
        self._headers = self._build_headers()
        return True


class ODataLegacyOAuthAuth(BaseODataAuth):
    """
    Legacy Aras/Minerva OAuth password-flow auth.

    This preserves compatibility with the existing service_factory.py, which still
    passes username/password/database for tenants using the legacy OData server.
    """

    def __init__(
        self,
        *,
        base_url: str,
        database: str,
        username: str,
        password: str,
        accept: str = "application/json",
        extra_headers: Optional[Headers] = None,
    ):
        if not base_url:
            raise ValueError("base_url is required")
        if not database:
            raise ValueError("database is required")
        if not username:
            raise ValueError("username is required")
        if password is None:
            raise ValueError("password is required")

        self.base_url = base_url.rstrip("/")
        self.database = database
        self.username = username
        self.password = password
        self.accept = accept
        self.extra_headers = dict(extra_headers or {})
        self.token: Optional[str] = None
        self._headers: Headers = {}
        self.credentials = {
            "username": username,
            "database": database,
            "md5_password": hashlib.md5(password.encode()).hexdigest(),
        }
        self.authenticate()

    @property
    def headers(self) -> Headers:
        return dict(self._headers)

    def authenticate(self) -> bool:
        url = f"{self.base_url}/OAuthServer/connect/token"
        payload = {
            "grant_type": "password",
            "scope": "Innovator",
            "client_id": "IOMApp",
            "username": self.credentials["username"],
            "password": self.credentials["md5_password"],
            "database": self.credentials["database"],
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        try:
            response = requests.post(url, headers=headers, data=payload)
            if response.status_code == 200:
                self.token = response.json()["access_token"]
                self._headers = {
                    "Database": self.credentials["database"],
                    "Authorization": f"Bearer {self.token}",
                    "Accept": self.accept,
                }
                self._headers.update(self.extra_headers)
                return True
            else:
                logging.error("OAuth failed: %s %s", response.status_code, response.text)
                return False
        except Exception as e:
            logging.error("Auth Exception: %s", e)
            return False


class MinervaODataClient:
    """
    REST-style API client over an OData-compatible endpoint using API key auth.

    Public method names:
      - list(), get(), list_related(), create(), patch(), delete()

    Assumptions:
      - The new web service remains OData-compatible.
      - Entity set names remain unchanged.
      - The response still follows the OData JSON shape, typically {"value": [...]}.

    If your new service wraps responses differently, adjust _extract_list() and/or
    _extract_object() below.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: Optional[str] = None,
        api_base_path: str = "/server/odata",
        api_key_header: str = "x-api-key",
        api_key_prefix: Optional[str] = None,
        database: Optional[str] = None,
        verify: Union[bool, str] = True,
        timeout: Union[int, float] = 30,
        auth: Optional[BaseODataAuth] = None,
                username: Optional[str] = None,
        password: Optional[str] = None,
        session: Optional[requests.Session] = None,
        default_headers: Optional[Headers] = None,
    ):
        """
        Initialize the client.

        Parameters:
        - base_url:
            Base host URL of the new web service, e.g. https://api.company.com
        - api_base_path:
            OData route under the new service, e.g. /server/odata or /api/odata
        - api_key_header:
            Header name for API key auth. Common values:
              - x-api-key
              - Authorization
        - api_key_prefix:
            Optional prefix for auth header values, e.g. "Bearer" or "ApiKey".
            Examples:
              - header=x-api-key, prefix=None  -> x-api-key: abc123
              - header=Authorization, prefix=Bearer -> Authorization: Bearer abc123
        - database:
            Optional Database header if the new service still expects it.
        """
        self.timeout = timeout
        self.verify = verify
        self.api_base = f"{base_url.rstrip('/')}/{api_base_path.strip('/')}"

        if auth is None:
            if api_key:
                auth = ODataApiKeyAuth(
                    api_key=api_key,
                    api_key_header=api_key_header,
                    api_key_prefix=api_key_prefix,
                    extra_headers=default_headers,
                )
            else:
                if not database:
                    raise ValueError("database is required when api_key is not provided")
                if not username:
                    raise ValueError("username is required when api_key is not provided")
                if password is None:
                    raise ValueError("password is required when api_key is not provided")
                auth = ODataLegacyOAuthAuth(
                    base_url=base_url,
                    database=database,
                    username=username,
                    password=password,
                    extra_headers=default_headers,
                )

        self.auth = auth

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

    def _extract_list(self, data: Any) -> List[Json]:
        """
        Extract a list payload from common OData/REST response shapes.

        Supported examples:
        - {"value": [...]}          # standard OData
        - {"items": [...]}          # common wrapper style
        - [...]                      # already a list
        """
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if isinstance(data, dict):
            if isinstance(data.get("value"), list):
                return [x for x in data["value"] if isinstance(x, dict)]
            if isinstance(data.get("items"), list):
                return [x for x in data["items"] if isinstance(x, dict)]
        return []

    def _extract_object(self, data: Any) -> Json:
        """
        Extract a single object from common response shapes.
        """
        if isinstance(data, dict):
            return data
        return {"value": data}

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
        data_body: Optional[Any] = None,
        extra_headers: Optional[Headers] = None,
        headers_override: Optional[Headers] = None,
        retry_401: bool = True,
        stream: bool = False,
    ) -> requests.Response:
        """
        Execute an HTTP request and return the raw Response.

        Handles:
          - header composition
          - one-time 401 retry for interface compatibility
        """
        url = f"{self.api_base}/{path.lstrip('/')}"
        headers = self._merge_headers(extra_headers=extra_headers, headers_override=headers_override)

        #logging.debug(f"* Request: {method} {url} params={params} json={json_body}")
        response = self.session.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json_body,
            data=data_body,
            timeout=self.timeout,
            verify=self.verify,
            stream=stream,
        )
        #logging.debug(f"* Response: response.text={response.text}")

        if response.status_code == 401 and retry_401:
            if self.auth.authenticate():
                return self.request_raw(
                    method,
                    path,
                    params=params,
                    json_body=json_body,
                    data_body=data_body,
                    extra_headers=extra_headers,
                    headers_override=headers_override,
                    retry_401=False,
                    stream=stream,
                )

        return response

    def request_json(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Params] = None,
        json_body: Optional[Json] = None,
        data_body: Optional[Any] = None,
        extra_headers: Optional[Headers] = None,
        headers_override: Optional[Headers] = None,
        retry_401: bool = True,
    ) -> Any:
        response = self.request_raw(
            method,
            path,
            params=params,
            json_body=json_body,
            data_body=data_body,
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
        return self._extract_list(data)

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
        return self._extract_object(data)

    def list_related(
        self,
        resource: str,
        resource_id: str,
        related: str,
        *,
        select: Optional[Union[str, Iterable[str]]] = None,
        filter: Optional[str] = None,
        expand: Optional[str] = "related_id($select=id,keyed_name)",
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
        rel_rows = self._extract_list(data)

        expanded: List[Json] = []
        for row in rel_rows:
            rid = row.get("related_id")
            if not rid:
                expanded.append(row)
            elif isinstance(rid, list):
                expanded.extend([x for x in rid if isinstance(x, dict)])
            elif isinstance(rid, dict):
                expanded.append(rid)

        return expanded

    def create(self, resource: str, payload: Json) -> Json:
        """Create a resource."""
        data = self.request_json("POST", resource, json_body=payload)
        return self._extract_object(data)

    def patch(self, resource: str, resource_id: str, payload: Json) -> Json:
        """Partially update a resource (PATCH semantics)."""
        path = f"{resource}('{resource_id}')"
        data = self.request_json("PATCH", path, json_body=payload)
        return self._extract_object(data)

    def delete(self, resource: str, resource_id: str, *, purge: bool = False) -> int:
        """
        Delete a resource. Returns HTTP status code.

        purge is Aras-specific; implemented via extra header.
        """
        path = f"{resource}('{resource_id}')"
        extra_headers = {"@aras.action": "purge"} if purge else None

        response = self.request_raw("DELETE", path, extra_headers=extra_headers)
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
        """
        if page_size <= 0:
            raise ValueError("page_size must be > 0")

        if max_items is not None and max_items <= 0:
            return

        yielded = 0
        skip = 0

        while True:
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

            if not items:
                break

            for item in items:
                yield item
                yielded += 1

                if max_items is not None and yielded >= max_items:
                    return

            skip += len(items)

            if len(items) < page_size:
                break

    def download(self, vault_id: str, dest: str) -> int:
        path = f"File('{vault_id}')/$value"
        response = self.request_raw("GET", path, stream=True)
        self._raise_for_status(response)

        with open(dest, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        print(f"Downloaded {vault_id} -> {dest}")
        return response.status_code


# ----------------------------------------------------------------------
# Example construction patterns
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# Example construction patterns
# ----------------------------------------------------------------------
# 1) New web service with API key auth
# client = MinervaODataClient(
#     base_url="https://api.company.com",
#     api_base_path="/server/odata",
#     api_key="YOUR_API_KEY",
# )
#
# 2) New web service with Authorization: Bearer <key>
# client = MinervaODataClient(
#     base_url="https://api.company.com",
#     api_base_path="/server/odata",
#     api_key="YOUR_API_KEY",
#     api_key_header="Authorization",
#     api_key_prefix="Bearer",
# )
#
# 3) Existing legacy tenant using username/password/database
# client = MinervaODataClient(
#     base_url="https://legacy.company.com",
#     api_base_path="/server/odata",
#     database="InnovatorSolutions",
#     username="svc_user",
#     password="svc_password",
# )
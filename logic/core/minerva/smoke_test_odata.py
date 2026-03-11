import os
import sys
import json
from typing import Optional
from dotenv import load_dotenv

# TODO: adjust import path to your project
# from yourpkg.minerva.odata_client import MinervaODataClient
from .odata import MinervaODataClient


def env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if v not in (None, "") else default


def pretty(obj) -> str:
    try:
        return json.dumps(obj, indent=2, ensure_ascii=False)[:2000]
    except Exception:
        return str(obj)[:2000]


def main() -> int:
    load_dotenv()

    base_url = env("MINERVA_BASE_URL")
    database = env("MINERVA_DATABASE")
    username = env("MINERVA_USERNAME")
    password = env("MINERVA_PASSWORD")
    verify = env("MINERVA_VERIFY", "true").lower() in ("1", "true", "yes", "y")
    timeout = float(env("MINERVA_TIMEOUT", "30"))

    if not base_url or not username or not password:
        print("Missing env vars. Please set:")
        print("  MINERVA_BASE_URL, MINERVA_USERNAME, MINERVA_PASSWORD")
        print("Optional:")
        print("  MINERVA_VERIFY=true|false, MINERVA_TIMEOUT=30")
        return 2

    client = MinervaODataClient(
        base_url=base_url,
        database=database,
        username=username,
        password=password,
        verify=verify,
        timeout=timeout,
    )

    print("== Minerva OData Smoke Test ==")
    print(f"Base URL: {base_url}")
    print(f"Verify TLS: {verify}")
    print(f"Timeout: {timeout}s")
    print()

    # ------------------------------------------------------------
    # 1) Basic connectivity: $metadata (raw)
    # ------------------------------------------------------------
    # OData metadata endpoint is usually: /server/odata/$metadata
    # It may return XML (not JSON), so use request_raw().
    try:
        resp = client.request_raw("GET", "$metadata")
        print("[1] GET $metadata")
        print("  Status:", resp.status_code)
        print("  Content-Type:", resp.headers.get("Content-Type"))
        print("  Body (first 500 chars):")
        print(resp.text[:500])
        print()
    except Exception as e:
        print("[1] GET $metadata FAILED:", e)
        return 1

    # ------------------------------------------------------------
    # 2) List a safe-ish resource (JSON) - adjust resource as needed
    # ------------------------------------------------------------
    # 'Project' is common in Aras; if not available, change to a known entity set.
    try:
        print("[2] LIST 'Ans_SimulationRequest' (top=10, select=id,name)")
        items = client.list("Ans_SimulationRequest", top=10, select=["id", "name"])
        print("  Count:", len(items))
        print("  First item:", pretty(items[0] if items else None))
        print()
    except Exception as e:
        print("[2] LIST 'Ans_SimulationRequest' FAILED:", e)
        print("  Hint: change resource name to a valid EntitySet (e.g., Part, User, ItemType, ...)")
        return 1

    # ------------------------------------------------------------
    # 3) Pagination iterator test (small)
    # ------------------------------------------------------------
    try:
        print("[3] ITER_LIST 'Ans_SimulationRequest' (page_size=5)")
        got = []
        for x in client.iter_list("Ans_SimulationRequest", select=["id", "name"], page_size=2, max_items=10):
            got.append(x)
        print("  Got:", len(got))
        print("  Items:", pretty(got))
        print()
    except Exception as e:
        print("[3] ITER_LIST 'Ans_SimulationRequest' FAILED:", e)
        return 1

    # ------------------------------------------------------------
    # 4) Related collection test (optional)
    # ------------------------------------------------------------
    # This requires a known navigation property/relationship name.
    # Example: List('{id}')/Value is often valid.
    try:
        print("[2] LIST 'Ans_SimulationTask' (top=10, select=id,name,keyed_name)")
        items = client.list("Ans_SimulationTask", top=10, select=["id", "name"])
        print("  Items:", str(items))

        print("[4] LIST_RELATED Ans_SimulationTask('{id}')/Ans_SimTask_Input (top=5)")
        for i, item in enumerate(items):
            # reuse a list id from previous call
            list_id = item["id"]
            if not list_id:
                print("  Skipped: no List items returned.")
            else:
                related_items = client.list_related("Ans_SimulationTask", list_id, "ans_SimTask_Input", select=["id", "keyed_name"], expand=None)
                print(f"[4.{i}]  Related count:", len(related_items))
                print(f"[4.{i}]  First related:", pretty(related_items[0] if related_items else None))
            print()
    except Exception as e:
        print("[4] LIST_RELATED FAILED:", e)
        print("  Hint: related path must exist on your server. Try another related name.")
        # not fatal: keep going

    print("✅ Smoke test completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
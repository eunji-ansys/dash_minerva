# service_factory.py
import os
from typing import Literal

from logic.services.ootb_service import OOTBService
from logic.services.vd_service import VDService

Tenant = Literal["ootb", "ootb_api", "vd"]


def _get_common_base() -> dict:
    return dict(
        base_url=os.environ["MINERVA_BASE_URL"],
        api_base_path=os.environ.get("MINERVA_API_BASE_PATH", "/server/odata"),
        cli_exe_path=os.environ.get("MINERVA_CLI_EXE_PATH"),
    )


def _get_auth_config(tenant: Tenant) -> dict:
    """
    Resolve auth settings by tenant.

    Supported auth modes:
      - api_key
      - basic

    Recommended env examples:
      MINERVA_TENANT=vd
      MINERVA_AUTH_MODE=api_key
      MINERVA_API_KEY=xxxx

      MINERVA_TENANT=ootb
      MINERVA_AUTH_MODE=basic
      MINERVA_USERNAME=svc_user
      MINERVA_PASSWORD=svc_password
      MINERVA_DATABASE=InnovatorSolutions
    """
    auth_mode = os.environ.get("MINERVA_AUTH_MODE", "").strip().lower()

    # Optional defaulting by tenant if MINERVA_AUTH_MODE is not set
    if not auth_mode:
        auth_mode = "api_key" if tenant == "ootb_api" else "basic"

    if auth_mode == "api_key":
        api_key = os.environ.get("MINERVA_API_KEY")
        if not api_key:
            raise RuntimeError("MINERVA_API_KEY is required when MINERVA_AUTH_MODE=api_key")

        return dict(
            auth_mode="api_key",
            api_key=api_key,
            api_key_header=os.environ.get("MINERVA_API_KEY_HEADER", "x-api-key"),
            api_key_prefix=os.environ.get("MINERVA_API_KEY_PREFIX") or None,
        )

    if auth_mode == "basic":
        username = os.environ.get("MINERVA_USERNAME")
        password = os.environ.get("MINERVA_PASSWORD")
        database = os.environ.get("MINERVA_DATABASE")

        if not username:
            raise RuntimeError("MINERVA_USERNAME is required when MINERVA_AUTH_MODE=basic")
        if password is None:
            raise RuntimeError("MINERVA_PASSWORD is required when MINERVA_AUTH_MODE=basic")

        return dict(
            auth_mode="basic",
            username=username,
            password=password,
            database=database,
        )

    raise RuntimeError(f"Unsupported MINERVA_AUTH_MODE: {auth_mode}")


def get_service():
    tenant: Tenant = os.getenv("MINERVA_TENANT", "ootb").lower()

    common = _get_common_base()
    auth = _get_auth_config(tenant)

    kwargs = {**common, **auth}

    if tenant == "vd":
        return VDService(**kwargs)
    return OOTBService(**kwargs)
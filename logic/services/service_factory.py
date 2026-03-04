# service_factory.py
import os
from typing import Literal

from logic.services.ootb_service import OOTBService
from logic.services.vd_service import VDService

Tenant = Literal["ootb", "vd"]


def get_service():
    tenant: Tenant = os.getenv("MINERVA_TENANT", "ootb").lower()

    common = dict(
        base_url=os.environ["MINERVA_BASE_URL"],
        database=os.environ["MINERVA_DATABASE"],
        username=os.environ["MINERVA_USERNAME"],
        password=os.environ["MINERVA_PASSWORD"],
        cli_exe_path=os.getenv("MINERVA_CLI_EXE_PATH"),
    )

    if tenant == "vd":
        return VDService(**common)
    return OOTBService(**common)
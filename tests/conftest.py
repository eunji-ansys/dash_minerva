from pathlib import Path
import os

import pytest
from dotenv import load_dotenv

from logic.core.minerva.cli import MinervaCLIClient


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env.integration")


@pytest.fixture
def fake_cli_exe(tmp_path):
    exe = tmp_path / "AnsysMinerva_CLI.exe"
    exe.write_text("dummy exe")
    return str(exe)


@pytest.fixture
def unit_client(fake_cli_exe):
    return MinervaCLIClient(
        base_url="http://fake-server/AnsysMinerva",
        database="TEST_DB",
        username="tester",
        password="secret",
        auth_mode="Explicit",
        cli_exe_path=fake_cli_exe,
        interactive="None",
        output="stream://stdout",
        name="TEST_CLIENT",
    )


@pytest.fixture
def integration_client():
    base_url = os.getenv("MINERVA_BASE_URL")
    database = os.getenv("MINERVA_DATABASE")
    username = os.getenv("MINERVA_USERNAME")
    password = os.getenv("MINERVA_PASSWORD")
    cli_exe_path = os.getenv("ANS_MINERVA_CLI")

    missing = [
        key for key, value in {
            "MINERVA_BASE_URL": base_url,
            "MINERVA_DATABASE": database,
            "MINERVA_USERNAME": username,
            "MINERVA_PASSWORD": password,
            "ANS_MINERVA_CLI": cli_exe_path,
        }.items()
        if not value
    ]
    if missing:
        pytest.skip(f"Missing integration env vars: {', '.join(missing)}")

    if not Path(cli_exe_path).exists():
        pytest.skip(f"CLI executable not found: {cli_exe_path}")

    return MinervaCLIClient(
        base_url=base_url,
        database=database,
        username=username,
        password=password,
        auth_mode="Explicit",
        cli_exe_path=cli_exe_path,
        interactive="None",
        output="stream://stdout",
        name="INTEGRATION_CLIENT",
    )
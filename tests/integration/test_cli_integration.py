import os
import pytest

from logic.core.minerva.cli import MinervaCliError


pytestmark = pytest.mark.integration


TEST_REMOTE_DOWNLOAD = os.getenv("MINERVA_TEST_REMOTE_DOWNLOAD")
TEST_REMOTE_UPLOAD = os.getenv("MINERVA_TEST_REMOTE_UPLOAD")
TEST_REMOTE_SELECT = os.getenv("MINERVA_TEST_REMOTE_SELECT")


def _find_item(items, rel_path: str):
    for item in items:
        local_info = item.get("local") or {}
        if local_info.get("path") == rel_path:
            return item
    return None


def _write_workspace_files(ws):
    (ws / "a.txt").write_text("hello", encoding="utf-8")
    (ws / "b.log").write_text("log", encoding="utf-8")
    sub = ws / "sub"
    sub.mkdir()
    (sub / "nested.txt").write_text("nested", encoding="utf-8")


def test_cli_sign_in_and_sign_out(integration_client, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()

    sign_in_result = integration_client.sign_in(
        force=True,
        local=str(ws),
        parse_json=False,
    )
    assert sign_in_result is not None

    sign_out_result = integration_client.sign_out(
        local=str(ws),
        parse_json=False,
    )
    assert sign_out_result is not None


def test_cli_get_status_on_local_workspace(integration_client, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "a.txt").write_text("hello", encoding="utf-8")

    result = integration_client.get_status(
        local=str(ws),
        parse_json=True,
    )

    assert isinstance(result, dict)
    assert result["local"] == str(ws)
    assert "items" in result

    item = _find_item(result["items"], "a.txt")
    assert item is not None
    assert item["local"]["status"] == "Added"
    assert item["local"]["staged"] is False


def test_cli_stage_and_unstage_roundtrip(integration_client, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    _write_workspace_files(ws)

    stage_result = integration_client.stage(
        globs="*.txt",
        local=str(ws),
        parse_json=False,
    )
    assert stage_result is not None

    staged = integration_client.get_status(
        local=str(ws),
        parse_json=True,
    )
    a_txt = _find_item(staged["items"], "a.txt")
    assert a_txt is not None
    assert a_txt["local"]["staged"] is True

    unstage_result = integration_client.unstage(
        globs="*.txt",
        local=str(ws),
        parse_json=False,
    )
    assert unstage_result is not None

    unstaged = integration_client.get_status(
        local=str(ws),
        parse_json=True,
    )
    a_txt2 = _find_item(unstaged["items"], "a.txt")
    assert a_txt2 is not None
    assert a_txt2["local"]["staged"] is False


def test_cli_get_local_returns_workspace_info(integration_client, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    target = ws / "a.txt"
    target.write_text("hello", encoding="utf-8")

    result = integration_client.get_local(
        path=str(target),
        local=str(ws),
        parse_json=True,
    )

    assert result is not None
    assert isinstance(result, dict)


def test_cli_fetch_status_on_local_workspace(integration_client, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    _write_workspace_files(ws)

    result = integration_client.fetch_status(
        local=str(ws),
        glob="**/*.txt",
        parse_json=True,
    )

    assert isinstance(result, dict)
    assert "items" in result


@pytest.mark.skipif(
    not TEST_REMOTE_DOWNLOAD,
    reason="MINERVA_TEST_REMOTE_DOWNLOAD is not set",
)
def test_cli_download_test_item(integration_client, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()

    result = integration_client.download(
        remote=TEST_REMOTE_DOWNLOAD,
        local=str(ws),
        no_session=True,
        parse_json=True,
    )

    assert result is not None


@pytest.mark.skipif(
    not TEST_REMOTE_UPLOAD,
    reason="MINERVA_TEST_REMOTE_UPLOAD is not set",
)
def test_cli_upload_small_file(integration_client, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "sample.txt").write_text("integration upload", encoding="utf-8")

    result = integration_client.upload(
        remote=TEST_REMOTE_UPLOAD,
        local=str(ws),
        glob="sample.txt",
        no_session=True,
        parse_json=True,
    )

    assert result is not None


@pytest.mark.skipif(
    not TEST_REMOTE_SELECT,
    reason="MINERVA_TEST_REMOTE_SELECT is not set",
)
def test_cli_select_items_without_dialog(integration_client, tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()

    result = integration_client.select_items(
        mode="SelectFileFolder",
        remote=TEST_REMOTE_SELECT,
        local=str(ws),
        parse_json=True,
    )

    assert result is not None
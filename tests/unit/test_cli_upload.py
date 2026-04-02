import subprocess

from logic.core.minerva.cli import MinervaCLIClient


def _cp(stdout="ok", stderr="", returncode=0):
    return subprocess.CompletedProcess(
        args=[],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def _make_client(tmp_path):
    exe = tmp_path / "AnsysMinerva_CLI.exe"
    exe.write_text("dummy exe")

    return MinervaCLIClient(
        base_url="http://fake-server/AnsysMinerva",
        database="TEST_DB",
        username="tester",
        password="secret",
        auth_mode="Explicit",
        cli_exe_path=str(exe),
        interactive="None",
        output="stream://stdout",
        name="TEST_CLIENT",
    )


def _patch_run(monkeypatch, captured, stdout="ok"):
    def fake_run(cmd, capture_output, text, encoding, errors, env, timeout, cwd):
        captured["cmd"] = cmd
        captured["env"] = env
        captured["cwd"] = cwd
        return _cp(stdout=stdout)

    monkeypatch.setattr(subprocess, "run", fake_run)


def test_upload_with_single_file_glob(tmp_path, monkeypatch):
    client = _make_client(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "input.txt").write_text("hello")

    captured = {}
    _patch_run(monkeypatch, captured, stdout="upload ok")

    out = client.upload(
        remote="ans_Data/TARGET_ID",
        local=str(workspace),
        glob="input.txt",
    )

    assert out == "upload ok"
    assert captured["cmd"][0] == client.exe
    assert captured["cmd"][1] == "upload"
    assert "--remote" in captured["cmd"]
    assert "ans_Data/TARGET_ID" in captured["cmd"]
    assert "--local" in captured["cmd"]
    assert str(workspace) in captured["cmd"]
    assert "--glob" in captured["cmd"]
    assert "input.txt" in captured["cmd"]
    assert "--overwrite" in captured["cmd"]
    assert "Overwrite" in captured["cmd"]


def test_upload_with_recursive_folder_glob(tmp_path, monkeypatch):
    client = _make_client(tmp_path)
    workspace = tmp_path / "workspace"
    folder = workspace / "docs"
    folder.mkdir(parents=True)
    (folder / "a.txt").write_text("A")
    (folder / "b.txt").write_text("B")

    captured = {}
    _patch_run(monkeypatch, captured, stdout="folder upload ok")

    out = client.upload(
        remote="ans_Data/FOLDER_TARGET",
        local=str(workspace),
        glob="docs/**/*",
    )

    assert out == "folder upload ok"
    assert "--local" in captured["cmd"]
    assert str(workspace) in captured["cmd"]
    assert "--glob" in captured["cmd"]
    assert "docs/**/*" in captured["cmd"]
    assert "--remote" in captured["cmd"]
    assert "ans_Data/FOLDER_TARGET" in captured["cmd"]


def test_upload_with_multiple_globs(tmp_path, monkeypatch):
    client = _make_client(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    captured = {}
    _patch_run(monkeypatch, captured, stdout="multi glob ok")

    out = client.upload(
        remote="ans_Data/MIXED_TARGET",
        local=str(workspace),
        glob=["*.txt", "*.csv"],
    )

    assert out == "multi glob ok"
    assert captured["cmd"].count("--glob") == 2
    assert "*.txt" in captured["cmd"]
    assert "*.csv" in captured["cmd"]


def test_upload_without_glob_omits_glob_flag(tmp_path, monkeypatch):
    client = _make_client(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "a.txt").write_text("A")

    captured = {}
    _patch_run(monkeypatch, captured, stdout="upload all ok")

    out = client.upload(
        remote="ans_Data/TARGET_ID",
        local=str(workspace),
    )

    assert out == "upload all ok"
    assert "--local" in captured["cmd"]
    assert str(workspace) in captured["cmd"]
    assert "--glob" not in captured["cmd"]


def test_upload_without_local_omits_local_flag(tmp_path, monkeypatch):
    client = _make_client(tmp_path)

    captured = {}
    _patch_run(monkeypatch, captured, stdout="cwd upload ok")

    out = client.upload(
        remote="ans_Data/TARGET_ID",
        glob="**/*.txt",
    )

    assert out == "cwd upload ok"
    assert "--local" not in captured["cmd"]
    assert "--glob" in captured["cmd"]
    assert "**/*.txt" in captured["cmd"]
    assert captured["cwd"] is None


def test_upload_with_override_minervaignore_repeats_flag(tmp_path, monkeypatch):
    client = _make_client(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    captured = {}
    _patch_run(monkeypatch, captured, stdout="override ok")

    out = client.upload(
        remote="ans_Data/TARGET_ID",
        local=str(workspace),
        override_minervaignore=["*.msh", "*.dat"],
    )

    assert out == "override ok"
    assert captured["cmd"].count("--override-minervaignore") == 2
    assert "*.msh" in captured["cmd"]
    assert "*.dat" in captured["cmd"]


def test_upload_with_session_flags(tmp_path, monkeypatch):
    client = _make_client(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "input.txt").write_text("hello")

    captured = {}
    _patch_run(monkeypatch, captured, stdout="flags ok")

    out = client.upload(
        remote="ans_Data/TARGET_ID",
        local=str(workspace),
        glob="input.txt",
        no_session=True,
        close_session=True,
    )

    assert out == "flags ok"
    assert "--no-session" in captured["cmd"]
    assert "--close-session" in captured["cmd"]
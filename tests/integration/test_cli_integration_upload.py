import pytest

def _write_workspace_files(ws):
    (ws / "a.txt").write_text("hello", encoding="utf-8")
    (ws / "b.log").write_text("log", encoding="utf-8")
    sub = ws / "sub"
    sub.mkdir()
    (sub / "nested.txt").write_text("nested", encoding="utf-8")


# @pytest.mark.integration
def test_upload_small_file_to_Data(integration_client, tmp_path):
    workspace = tmp_path / "upload_case"
    workspace.mkdir()
    (workspace / "sample.txt").write_text("integration test 1")

    result = integration_client.upload(
        remote="/Data/test",
        local=str(workspace),
        glob="**/*",
        overwrite="Snapshot",
    )
    print ("Upload result:", result)
    assert result


@pytest.mark.integration
def test_upload_small_file_to_Data_UUID(integration_client, tmp_path):
    workspace = tmp_path / "upload_case"
    workspace.mkdir()
    (workspace / "sample.txt").write_text("integration test 0")

    result = integration_client.upload(
        remote="ans_Data/6DEF7E4F68B24132AE193770797E8FE0",
        local=str(workspace),
        glob="*",
        overwrite="Snapshot",
    )
    print ("Upload result:", result)
    assert result

# @pytest.mark.integration
def test_upload_small_file_to_Task(integration_client, tmp_path):
    workspace = tmp_path / "upload_case"
    workspace.mkdir()
    (workspace / "sample.txt").write_text("integration test 1")

    result = integration_client.upload(
        remote="/Tasks/#1000004/Output",
        local=str(workspace),
        glob="*",
        overwrite="Snapshot",
    )
    print ("Upload result:", result)
    assert result

# @pytest.mark.integration
def test_upload_small_file_to_Task_UUID(integration_client, tmp_path):
    workspace = tmp_path / "upload_case"
    workspace.mkdir()
    (workspace / "sample.txt").write_text("integration test 2")

    result = integration_client.upload(
        remote="Ans_SimulationTask/B36F0893B4964234A71CC10028F7F970/ans_SimTask_Output",
        local=str(workspace),
        glob="*",
        overwrite="Snapshot",
    )
    print ("Upload result:", result)
    assert result

# @pytest.mark.integration
def test_upload_small_file_to_WR(integration_client, tmp_path):
    workspace = tmp_path / "upload_case"
    workspace.mkdir()
    (workspace / "sample2.txt").write_text("integration test 4")

    result = integration_client.upload(
        remote="/Work Requests/WR-000001/Deliverables",
        local=str(workspace),
        glob="*",
        overwrite="Snapshot",
    )
    print ("Upload result:", result)
    assert result

# @pytest.mark.integration
def test_upload_small_file_to_WR_UUID(integration_client, tmp_path):
    workspace = tmp_path / "upload_case"
    workspace.mkdir()
    (workspace / "sample.txt").write_text("integration test 5")

    result = integration_client.upload(
        remote="Ans_SimulationRequest/028F856F9CB84CB0AAB9B304B505C467/Ans_SimReq_Deliverable",
        local=str(workspace),
        glob="*.txt",
        overwrite="Snapshot",
    )
    print ("Upload result:", result)
    assert result

@pytest.mark.integration
def test_upload_folder_to_WR_UUID(integration_client, tmp_path):
    workspace = tmp_path / "upload_case"
    workspace.mkdir()
    _write_workspace_files(workspace)

    result = integration_client.upload(
        remote="Ans_SimulationRequest/028F856F9CB84CB0AAB9B304B505C467/Ans_SimReq_Deliverable",
        local=str(workspace),
        glob="**/*",
        overwrite="Snapshot",
        parse_json=True,
    )
    print ("Upload result:", result)
    assert result["local"] == str(workspace)
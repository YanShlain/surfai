import pytest

from tests.conftest import assert_execute_response


@pytest.mark.asyncio
async def test_if_equals_true_branch(client, load_fixture):
    payload = load_fixture("branch_if_equals")
    expected = load_fixture("branch_if_equals", kind="responses")
    response = await client.post("/v1/workflows/execute", json=payload)
    assert response.status_code == 200
    assert_execute_response(response.json(), expected)


@pytest.mark.asyncio
async def test_if_equals_false_branch(client):
    payload = {
        "workflow": {
            "schema_version": 1,
            "entry": "check",
            "nodes": [
                {
                    "id": "check",
                    "action": "if_equals",
                    "left": {"type": "literal", "value": "no"},
                    "right": {"type": "literal", "value": "yes"},
                    "on_true": "yes-exit",
                    "on_false": "no-exit",
                },
                {"id": "yes-exit", "action": "exit", "status": "success"},
                {"id": "no-exit", "action": "exit", "status": "failure"},
            ],
        }
    }
    response = await client.post("/v1/workflows/execute", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "failure"


@pytest.mark.asyncio
async def test_if_file_exists_branch(client, tmp_path, settings):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "input.csv").write_text("a,b,c", encoding="utf-8")

    payload = {
        "workflow": {
            "schema_version": 1,
            "entry": "check",
            "nodes": [
                {
                    "id": "check",
                    "action": "if_file_exists",
                    "path": "data/input.csv",
                    "on_true": "yes",
                    "on_false": "no",
                },
                {"id": "yes", "action": "exit", "status": "success"},
                {"id": "no", "action": "exit", "status": "failure"},
            ],
        }
    }
    response = await client.post("/v1/workflows/execute", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

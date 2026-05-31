import pytest

from tests.conftest import assert_execute_response


@pytest.mark.asyncio
async def test_invalid_mixed_routing(client, load_fixture):
    payload = load_fixture("invalid_mixed_routing")
    expected = load_fixture("invalid_mixed_routing", kind="responses")
    response = await client.post("/v1/workflows/execute", json=payload)
    assert response.status_code == 200
    assert_execute_response(response.json(), expected)


@pytest.mark.asyncio
async def test_missing_entry_returns_failure(client):
    payload = {
        "workflow": {
            "schema_version": 1,
            "entry": "missing",
            "nodes": [{"id": "a", "action": "exit", "status": "success"}],
        }
    }
    response = await client.post("/v1/workflows/execute", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failure"
    assert body["error"]["code"] == "INVALID_ENTRY"


@pytest.mark.asyncio
async def test_cycle_returns_failure(client):
    payload = {
        "workflow": {
            "schema_version": 1,
            "entry": "check",
            "nodes": [
                {
                    "id": "check",
                    "action": "if_equals",
                    "left": {"type": "literal", "value": 1},
                    "right": {"type": "literal", "value": 2},
                    "on_true": "loop",
                    "on_false": "done",
                },
                {
                    "id": "loop",
                    "action": "set_variable",
                    "name": "x",
                    "value": 1,
                    "next": "check",
                },
                {"id": "done", "action": "exit", "status": "success"},
            ],
        }
    }
    response = await client.post("/v1/workflows/execute", json=payload)
    assert response.status_code == 200
    assert response.json()["error"]["code"] == "CYCLE_DETECTED"


@pytest.mark.asyncio
async def test_no_reachable_exit(client):
    payload = {
        "workflow": {
            "schema_version": 1,
            "entry": "a",
            "nodes": [
                {"id": "a", "action": "set_variable", "name": "x", "value": 1, "next": "b"},
                {"id": "b", "action": "set_variable", "name": "y", "value": 2, "next": "a"},
            ],
        }
    }
    response = await client.post("/v1/workflows/execute", json=payload)
    assert response.status_code == 200
    assert response.json()["error"]["code"] == "NO_REACHABLE_EXIT"


@pytest.mark.asyncio
async def test_malformed_body_returns_422(client):
    response = await client.post("/v1/workflows/execute", json={"bad": "shape"})
    assert response.status_code == 422

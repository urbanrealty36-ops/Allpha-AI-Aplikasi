import uuid

from fastapi.testclient import TestClient

from allpha_api.auth import current_user
from allpha_api.main import app
import allpha_api.workflow_api as workflow_api


OWNER = "11111111-1111-4111-8111-111111111111"
OTHER_OWNER = "99999999-9999-4999-8999-999999999999"
DEFINITION_ID = "22222222-2222-4222-8222-222222222222"
RUN_ID = "33333333-3333-4333-8333-333333333333"


class FakeWorkflowStore:
    definitions = {}
    runs = {}

    async def create_definition(self, body):
        row = {"id": DEFINITION_ID, **body, "created_at": "now"}
        self.definitions[(body["owner_user_id"], DEFINITION_ID)] = row
        return row

    async def get_definition(self, owner_id, definition_id):
        return self.definitions.get((owner_id, definition_id))

    async def list_definitions(self, owner_id, limit=50):
        return [row for (owner, _), row in self.definitions.items() if owner == owner_id][:limit]

    async def create_run(self, owner_id, definition, input_payload, trace_id):
        row = {"id": RUN_ID, "owner_user_id": owner_id, "definition_id": definition["id"],
               "input_payload": input_payload, "trace_id": trace_id, "status": "queued"}
        self.runs[(owner_id, RUN_ID)] = row
        return row

    async def get_run(self, owner_id, run_id):
        return self.runs.get((owner_id, run_id))

    async def list_runs(self, owner_id, limit=50):
        return [row for (owner, _), row in self.runs.items() if owner == owner_id][:limit]

    async def cancel_run(self, owner_id, run_id):
        row = self.runs.get((owner_id, run_id))
        if not row or row["status"] in {"succeeded", "failed", "cancelled", "timed_out"}:
            return None
        row["status"] = "cancelled"
        return row


def client(monkeypatch, owner_id=OWNER):
    FakeWorkflowStore.definitions = {}
    FakeWorkflowStore.runs = {}
    monkeypatch.setattr(workflow_api, "_store", lambda: FakeWorkflowStore())
    app.dependency_overrides[current_user] = lambda: {"id": owner_id}
    return TestClient(app)


def setup_function():
    app.dependency_overrides.clear()


def valid_definition():
    return {"definition": {
        "workflow_key": "hello-world",
        "version": 1,
        "nodes": [{"key": "source", "kind": "input", "config": {"field": "name"}}],
        "edges": [],
    }}


def test_definition_owner_is_taken_from_authenticated_context(monkeypatch):
    response = client(monkeypatch).post("/v1/workflows/definitions", json=valid_definition())
    assert response.status_code == 201
    assert response.json()["definition"]["owner_user_id"] == OWNER


def test_run_creation_does_not_disclose_other_owners_definition(monkeypatch):
    client(monkeypatch, owner_id=OTHER_OWNER)
    FakeWorkflowStore.definitions[(OWNER, DEFINITION_ID)] = {
        "id": DEFINITION_ID, "owner_user_id": OWNER, "workflow_key": "hello-world",
        "version": 1, "digest": "0" * 64, "definition": valid_definition()["definition"],
        "status": "active",
    }
    response = TestClient(app).post(
        f"/v1/workflows/definitions/{DEFINITION_ID}/runs", json={"input_payload": {}}
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "WORKFLOW_DEFINITION_NOT_FOUND"


def test_run_read_is_owner_scoped(monkeypatch):
    client(monkeypatch, owner_id=OTHER_OWNER)
    FakeWorkflowStore.runs[(OWNER, RUN_ID)] = {"id": RUN_ID, "owner_user_id": OWNER, "status": "queued"}
    response = TestClient(app).get(f"/v1/workflows/runs/{RUN_ID}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "WORKFLOW_RUN_NOT_FOUND"


def test_run_input_is_bounded_before_persistence(monkeypatch):
    client(monkeypatch)
    response = TestClient(app).post(
        f"/v1/workflows/definitions/{DEFINITION_ID}/runs",
        json={"input_payload": {"large": "x" * 17000}},
    )
    assert response.status_code == 422

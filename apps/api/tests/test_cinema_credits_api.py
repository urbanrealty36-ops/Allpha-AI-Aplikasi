import uuid

from fastapi.testclient import TestClient

from allpha_api import cinema_lifecycle_api
from allpha_api.auth import current_user
from allpha_api.main import app

OWNER = "11111111-1111-4111-8111-111111111111"
TITLE = "22222222-2222-4222-8222-222222222222"
AGENT = "33333333-3333-4333-8333-333333333333"


def _client():
    app.dependency_overrides[current_user] = lambda: {"id": OWNER}
    return TestClient(app)


def test_creator_credits_use_canonical_cinema_title_json_and_are_visible_to_catalog(monkeypatch):
    captured = {}
    async def title_access(*args, **kwargs):
        return {"id": TITLE, "owner_id": OWNER, "status": "draft", "version": 2, "title": "Test Film"}
    async def fake_db(method, table, *, params=None, payload=None, prefer=None):
        if method == "GET" and table == "cinema_titles":
            return [{"id": TITLE, "owner_id": OWNER, "status": "draft", "version": 2, "credits": []}]
        if method == "PATCH" and table == "cinema_titles":
            captured["payload"] = payload
            return [{"id": TITLE, "version": payload["version"], "credits": payload["credits"]}]
        raise AssertionError((method, table, params, payload))
    monkeypatch.setattr(cinema_lifecycle_api, "_cinema_title_access", title_access)
    monkeypatch.setattr(cinema_lifecycle_api, "_db", fake_db)
    client = _client()
    try:
        response = client.post(f"/v1/cinema/creator/titles/{TITLE}/credits", json={
            "contributor_type": "human", "role": "director", "attribution_label": "Director One",
        })
        assert response.status_code == 201
        credit = response.json()["credit"]
        assert credit["contributor_user_id"] == OWNER
        assert credit["contributor_type"] == "human"
        assert captured["payload"]["credits"][0]["id"] == credit["id"]
        assert captured["payload"]["version"] == 3
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_creator_credit_list_reads_canonical_title_metadata(monkeypatch):
    credit = {"id": str(uuid.uuid4()), "contributor_type": "human", "role": "actor", "attribution_label": "Lead"}
    async def title_access(*args, **kwargs):
        return {"id": TITLE, "owner_id": OWNER, "status": "draft", "version": 4, "title": "Test Film"}
    async def fake_db(method, table, *, params=None, payload=None, prefer=None):
        assert method == "GET" and table == "cinema_titles"
        return [{"id": TITLE, "owner_id": OWNER, "status": "draft", "version": 4, "credits": [credit]}]
    monkeypatch.setattr(cinema_lifecycle_api, "_cinema_title_access", title_access)
    monkeypatch.setattr(cinema_lifecycle_api, "_db", fake_db)
    client = _client()
    try:
        response = client.get(f"/v1/cinema/creator/titles/{TITLE}/credits")
        assert response.status_code == 200
        assert response.json()["items"] == [credit]
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_creator_agent_credit_requires_active_agent_owned_by_film_owner(monkeypatch):
    async def title_access(*args, **kwargs):
        return {"id": TITLE, "owner_id": OWNER, "status": "draft", "version": 2, "title": "Test Film"}
    async def fake_db(method, table, *, params=None, payload=None, prefer=None):
        if method == "GET" and table == "ai_agents":
            return [{"id": AGENT, "status": "active"}]
        if method == "GET" and table == "agent_ownerships":
            return [{"agent_id": AGENT}]
        if method == "GET" and table == "cinema_titles":
            return [{"id": TITLE, "owner_id": OWNER, "status": "draft", "version": 2, "credits": []}]
        if method == "PATCH" and table == "cinema_titles":
            return [{"id": TITLE, "version": 3, "credits": payload["credits"]}]
        raise AssertionError((method, table, params, payload))
    monkeypatch.setattr(cinema_lifecycle_api, "_cinema_title_access", title_access)
    monkeypatch.setattr(cinema_lifecycle_api, "_db", fake_db)
    client = _client()
    try:
        response = client.post(f"/v1/cinema/creator/titles/{TITLE}/credits", json={
            "contributor_type": "agent", "contributor_agent_id": AGENT,
            "role": "co_director", "attribution_label": "AI Co-Director",
        })
        assert response.status_code == 201
        assert response.json()["credit"]["contributor_agent_id"] == AGENT
        assert response.json()["credit"]["contributor_user_id"] is None
    finally:
        app.dependency_overrides.pop(current_user, None)

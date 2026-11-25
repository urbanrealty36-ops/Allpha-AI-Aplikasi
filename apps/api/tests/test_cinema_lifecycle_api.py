import uuid
from fastapi import HTTPException
from fastapi.testclient import TestClient
from allpha_api import cinema_lifecycle_api
from allpha_api.auth import current_user
from allpha_api.main import app

OWNER="11111111-1111-4111-8111-111111111111"
TITLE="22222222-2222-4222-8222-222222222222"
EPISODE="33333333-3333-4333-8333-333333333333"

def _client():
    app.dependency_overrides[current_user]=lambda:{"id":OWNER}
    return TestClient(app)

def test_playback_history_is_owner_scoped_and_returns_resume_progress(monkeypatch):
    async def fake_db(method,table,*,params=None,payload=None,prefer=None):
        if table=="cinema_playback_sessions":
            assert params["owner_user_id"]=="eq."+OWNER
            return [{"id":str(uuid.uuid4()),"title_id":TITLE,"episode_id":EPISODE,"status":"expired",
                     "last_position_seconds":125,"max_position_seconds":150,"duration_seconds":300,
                     "updated_at":"2026-11-25T00:00:00Z"}]
        if table=="cinema_titles": return [{"id":TITLE,"title":"Film"}]
        if table=="cinema_episodes": return [{"id":EPISODE,"title":"Episode 1","episode_number":1}]
        raise AssertionError((method,table,params))
    monkeypatch.setattr(cinema_lifecycle_api,"_db",fake_db)
    client=_client()
    try:
        response=client.get("/v1/cinema/playback-history?limit=20")
        assert response.status_code==200
        item=response.json()["items"][0]
        assert item["resume_position_seconds"]==125
        assert item["progress_percent"]==50
        assert item["title"]["title"]=="Film"
        assert item["episode"]["episode_number"]==1
    finally: app.dependency_overrides.pop(current_user,None)

def test_watchlist_add_requires_published_approved_rights_cleared_title(monkeypatch):
    calls=[]
    async def fake_db(method,table,*,params=None,payload=None,prefer=None):
        calls.append((method,table,params,payload,prefer))
        if method=="GET" and table=="cinema_titles":
            return [{"id":TITLE,"status":"published","moderation_status":"approved","rights_status":"cleared"}]
        if method=="POST" and table=="cinema_watchlist_items":
            return [{"id":str(uuid.uuid4()),"title_id":TITLE,"created_at":"2026-11-25T00:00:00Z"}]
        raise AssertionError((method,table,params,payload))
    monkeypatch.setattr(cinema_lifecycle_api,"_db",fake_db)
    client=_client()
    try:
        response=client.post("/v1/cinema/watchlist/"+TITLE)
        assert response.status_code==201 and response.json()["saved"] is True
        insert=next(call for call in calls if call[0]=="POST")
        assert insert[3]["owner_user_id"]==OWNER
        assert insert[4]=="resolution=ignore-duplicates,return=representation"
    finally: app.dependency_overrides.pop(current_user,None)

def test_watchlist_rejects_unavailable_title_without_writing(monkeypatch):
    async def fake_db(method,table,*,params=None,payload=None,prefer=None):
        if method=="GET" and table=="cinema_titles": return []
        raise AssertionError("unavailable titles must not be written")
    monkeypatch.setattr(cinema_lifecycle_api,"_db",fake_db)
    client=_client()
    try:
        response=client.post("/v1/cinema/watchlist/"+TITLE)
        assert response.status_code==404
        assert response.json()["error"]["code"]=="CINEMA_TITLE_NOT_AVAILABLE"
    finally: app.dependency_overrides.pop(current_user,None)

def test_watchlist_delete_is_scoped_to_authenticated_owner(monkeypatch):
    captured={}
    async def fake_db(method,table,*,params=None,payload=None,prefer=None):
        captured.update(method=method,table=table,params=params,prefer=prefer)
        return [{"id":str(uuid.uuid4())}]
    monkeypatch.setattr(cinema_lifecycle_api,"_db",fake_db)
    client=_client()
    try:
        response=client.delete("/v1/cinema/watchlist/"+TITLE)
        assert response.status_code==200 and response.json()["removed"] is True
        assert captured["params"]=={"owner_user_id":"eq."+OWNER,"title_id":"eq."+TITLE}
    finally: app.dependency_overrides.pop(current_user,None)


def test_watchlist_get_is_owner_scoped_and_hides_unavailable_titles(monkeypatch):
    owner_filter = {}
    async def fake_db(method, table, *, params=None, payload=None, prefer=None):
        if method == "GET" and table == "cinema_watchlist_items":
            owner_filter.update(params)
            return [
                {"id": "watch-1", "title_id": TITLE, "created_at": "2026-11-25T00:00:00Z"},
                {"id": "watch-2", "title_id": EPISODE, "created_at": "2026-11-24T00:00:00Z"},
            ]
        if method == "GET" and table == "cinema_titles":
            assert params["status"] == "eq.published"
            assert params["moderation_status"] == "eq.approved"
            assert params["rights_status"] == "eq.cleared"
            return [{"id": TITLE, "title": "Film"}]
        raise AssertionError((method, table, params))
    monkeypatch.setattr(cinema_lifecycle_api, "_db", fake_db)
    client = _client()
    try:
        response = client.get("/v1/cinema/watchlist")
        assert response.status_code == 200
        assert owner_filter["owner_user_id"] == "eq." + OWNER
        assert [item["title_id"] for item in response.json()["items"]] == [TITLE]
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_creator_analytics_aggregates_verified_views_and_policy_approved_earnings(monkeypatch):
    async def fake_db(method, table, *, params=None, payload=None, prefer=None):
        if table == "cinema_titles":
            assert params["owner_id"] == "eq." + OWNER
            return [{"id": TITLE, "title": "Owner Film", "status": "published"}]
        if table == "cinema_playback_sessions":
            assert params["fraud_status"] == "eq.cleared"
            return [
                {"id": "view-1", "title_id": TITLE, "watched_seconds": 120, "fraud_status": "cleared"},
                {"id": "view-2", "title_id": TITLE, "watched_seconds": 60, "fraud_status": "cleared"},
            ]
        if table == "cinema_qualified_watches":
            assert params["status"] == "eq.qualified"
            return [{"id": "qualified-1", "title_id": TITLE, "qualified_seconds": 90}]
        if table == "cinema_creator_earnings":
            assert params["owner_user_id"] == "eq." + OWNER
            return [
                {"id": "earning-1", "title_id": TITLE, "earning_credits": 25, "status": "approved"},
                {"id": "earning-2", "title_id": TITLE, "earning_credits": 15, "status": "pending_policy"},
                {"id": "earning-3", "title_id": TITLE, "earning_credits": 100, "status": "reversed"},
            ]
        raise AssertionError((method, table, params))
    monkeypatch.setattr(cinema_lifecycle_api, "_db", fake_db)
    client = _client()
    try:
        response = client.get("/v1/cinema/creator/analytics")
        assert response.status_code == 200
        result = response.json()
        assert result["totals"]["views"] == 2
        assert result["totals"]["watched_seconds"] == 180
        assert result["totals"]["qualified_views"] == 1
        assert result["totals"]["approved_earning_credits"] == 25
        assert result["totals"]["pending_earning_credits"] == 15
        assert result["subscriber_count"] is None
        assert result["cash_conversion_enabled"] is False
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_creator_analytics_returns_empty_totals_without_querying_unowned_activity(monkeypatch):
    async def fake_db(method, table, *, params=None, payload=None, prefer=None):
        assert method == "GET" and table == "cinema_titles"
        assert params["owner_id"] == "eq." + OWNER
        return []
    monkeypatch.setattr(cinema_lifecycle_api, "_db", fake_db)
    client = _client()
    try:
        response = client.get("/v1/cinema/creator/analytics")
        assert response.status_code == 200
        assert response.json()["items"] == []
        assert response.json()["totals"]["views"] == 0
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_creator_analytics_marks_missing_schema_unconfigured_instead_of_reporting_zero(monkeypatch):
    async def fake_db(method, table, *, params=None, payload=None, prefer=None):
        if table == "cinema_titles":
            return [{"id": TITLE, "title": "Owner Film", "status": "published"}]
        raise HTTPException(status_code=404, detail="relation not found")
    monkeypatch.setattr(cinema_lifecycle_api, "_db", fake_db)
    client = _client()
    try:
        response = client.get("/v1/cinema/creator/analytics")
        assert response.status_code == 200
        result = response.json()
        assert result["configured"] is False
        assert result["subscriber_metric_reason"] == "CINEMA_ANALYTICS_SCHEMA_NOT_CONFIGURED"
        assert result["totals"] == {}
    finally:
        app.dependency_overrides.pop(current_user, None)

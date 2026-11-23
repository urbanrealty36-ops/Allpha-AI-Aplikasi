from fastapi.testclient import TestClient

from allpha_api.main import app


def test_healthz_exposes_account_lifecycle_worker_runtime_state():
    class WorkerState:
        started_at = "2026-11-23T00:00:00+00:00"
        last_poll_at = "2026-11-23T00:00:10+00:00"
        last_claimed_count = 2
        last_cleanup_count = 1
        last_deletion_governance_count = 3
        poll_count = 3
        last_error_code = None

    app.state.account_lifecycle_worker = WorkerState()
    try:
        response = TestClient(app).get("/healthz")
    finally:
        app.state.account_lifecycle_worker = None

    assert response.status_code == 200
    assert response.json()["workers"]["account_lifecycle"] == {
        "status": "running",
        "started_at": "2026-11-23T00:00:00+00:00",
        "last_poll_at": "2026-11-23T00:00:10+00:00",
        "last_claimed_count": 2,
        "last_cleanup_count": 1,
        "last_deletion_governance_count": 3,
        "poll_count": 3,
        "last_error_code": None,
    }


def test_healthz_reports_worker_disabled_without_claiming_runtime():
    response = TestClient(app).get("/healthz")
    assert response.status_code == 200
    assert response.json()["workers"]["account_lifecycle"]["status"] == "disabled"


def test_account_lifecycle_health_reports_external_canonical_worker(monkeypatch):
    from allpha_api.main import app

    monkeypatch.setenv("ALLPHA_ACCOUNT_LIFECYCLE_WORKER_EXTERNAL_SERVICE", "allpha-social-graph-outbox-worker")
    previous = getattr(app.state, "account_lifecycle_worker", None)
    app.state.account_lifecycle_worker = None
    try:
        response = client.get("/healthz")
    finally:
        app.state.account_lifecycle_worker = previous
    assert response.status_code == 200
    assert response.json()["workers"]["account_lifecycle"]["status"] == "external"
    assert response.json()["workers"]["account_lifecycle"]["runtime_service"] == "allpha-social-graph-outbox-worker"
    assert response.json()["workers"]["account_lifecycle"]["monitoring_source"] == "railway_service_logs"

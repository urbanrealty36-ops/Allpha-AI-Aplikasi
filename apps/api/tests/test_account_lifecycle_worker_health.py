from fastapi.testclient import TestClient

from allpha_api.main import app


def test_healthz_exposes_account_lifecycle_worker_runtime_state():
    class WorkerState:
        started_at = "2026-11-23T00:00:00+00:00"
        last_poll_at = "2026-11-23T00:00:10+00:00"
        last_claimed_count = 2
        last_cleanup_count = 1
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
        "poll_count": 3,
        "last_error_code": None,
    }


def test_healthz_reports_worker_disabled_without_claiming_runtime():
    response = TestClient(app).get("/healthz")
    assert response.status_code == 200
    assert response.json()["workers"]["account_lifecycle"]["status"] == "disabled"

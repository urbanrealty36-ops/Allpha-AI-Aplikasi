from fastapi.testclient import TestClient

from allpha_api.main import app


def test_spatial_api_is_unavailable_to_anonymous_users():
    response = TestClient(app).get("/v1/spatial/navigation/nodes")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SPATIAL_UNDER_DEVELOPMENT"
    assert response.headers["cache-control"] == "no-store"


def test_spatial_api_is_unavailable_to_authenticated_users(monkeypatch):
    from allpha_api.auth import current_user

    def authenticated_user():
        return {"id": "spatial-lock-test-user"}

    app.dependency_overrides[current_user] = authenticated_user
    try:
        response = TestClient(app).get("/v1/spatial/navigation/nodes")
    finally:
        app.dependency_overrides.pop(current_user, None)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SPATIAL_UNDER_DEVELOPMENT"


def test_spatial_admin_api_is_unavailable_to_operator_paths():
    response = TestClient(app).get("/v1/admin/spatial/assets")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SPATIAL_UNDER_DEVELOPMENT"


def test_unrelated_social_api_routes_are_not_blocked():
    response = TestClient(app).get("/v1/spatially-unrelated")
    assert response.status_code != 404 or response.json().get("error", {}).get("code") != "SPATIAL_UNDER_DEVELOPMENT"

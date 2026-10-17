from allpha_api import spatial_test_auth


def test_spatial_test_auth_rejects_missing_credentials(monkeypatch):
    monkeypatch.delenv("ALLPHA_SPATIAL_TEST_ACCESS_KEY", raising=False)
    assert not spatial_test_auth.is_authorized_spatial_test_request(None, None)
    assert not spatial_test_auth.is_authorized_spatial_test_request(None, "Basic invalid")


def test_spatial_test_auth_accepts_dedicated_server_key(monkeypatch):
    monkeypatch.setenv("ALLPHA_SPATIAL_TEST_ACCESS_KEY", "s" * 40)
    assert spatial_test_auth.is_authorized_spatial_test_request("s" * 40, None)


def test_spatial_test_auth_accepts_only_verified_github_oidc(monkeypatch):
    monkeypatch.delenv("ALLPHA_SPATIAL_TEST_ACCESS_KEY", raising=False)
    monkeypatch.setattr(spatial_test_auth, "verify_spatial_renderer_oidc", lambda token: {"repository": spatial_test_auth.REPOSITORY})
    assert spatial_test_auth.is_authorized_spatial_test_request(None, "Bearer eyJ.test.token")
    monkeypatch.setattr(spatial_test_auth, "verify_spatial_renderer_oidc", lambda token: (_ for _ in ()).throw(ValueError("invalid")))
    assert not spatial_test_auth.is_authorized_spatial_test_request(None, "Bearer eyJ.bad.token")

def test_spatial_ingest_auth_does_not_accept_renderer_identity(monkeypatch):
    monkeypatch.delenv("ALLPHA_SPATIAL_TEST_ACCESS_KEY", raising=False)
    monkeypatch.setattr(spatial_test_auth, "verify_spatial_ingest_oidc", lambda token: {"workflow": "ENG-P22"})
    assert spatial_test_auth.is_authorized_spatial_ingest_request(None, "Bearer eyJ.ingest.token")
    monkeypatch.setattr(spatial_test_auth, "verify_spatial_ingest_oidc", lambda token: (_ for _ in ()).throw(ValueError("renderer not allowed")))
    assert not spatial_test_auth.is_authorized_spatial_ingest_request(None, "Bearer eyJ.renderer.token")

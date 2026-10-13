import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from allpha_api.main import ProfileUpdate, UserSettingsUpdate, app

client = TestClient(app)


def test_identity_settings_endpoints_require_authentication():
    for path in ("/v1/me/settings", "/v1/me/consents"):
        response = client.get(path)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AUTH_REQUIRED"
    response = client.patch("/v1/me/settings", json={"theme": "dark"})
    assert response.status_code == 401


def test_profile_update_cannot_change_authority_fields():
    with pytest.raises(ValidationError):
        ProfileUpdate.model_validate({"account_status": "active"})
    with pytest.raises(ValidationError):
        ProfileUpdate.model_validate({"role": "super_admin"})


def test_settings_payload_is_strict_and_typed():
    with pytest.raises(ValidationError):
        UserSettingsUpdate.model_validate({"theme": "neon"})
    with pytest.raises(ValidationError):
        UserSettingsUpdate.model_validate({"notification_preferences": {"security_alerts": "yes"}})
    with pytest.raises(ValidationError):
        UserSettingsUpdate.model_validate({"user_id": "another-user"})


def test_valid_settings_payload():
    value = UserSettingsUpdate.model_validate({
        "theme": "dark",
        "notification_preferences": {
            "product_updates": False,
            "security_alerts": True,
            "social_activity": False,
        },
        "privacy_settings": {"discoverable_by_username": False},
    })
    assert value.theme == "dark"
    assert value.notification_preferences.security_alerts is True
    assert value.privacy_settings.discoverable_by_username is False

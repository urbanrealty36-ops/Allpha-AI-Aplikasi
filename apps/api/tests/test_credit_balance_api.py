from fastapi.testclient import TestClient

from allpha_api.auth import current_user
from allpha_api.main import app


class FakeCreditStore:
    seen_owner = None

    @classmethod
    def from_environment(cls):
        return cls()

    async def get_balance(self, *, owner_user_id):
        type(self).seen_owner = owner_user_id
        return {
            "available_credits": 42,
            "reserved_credits": 5,
            "ledger_entry_count": 7,
            "as_of": "2026-10-15T00:00:00+00:00",
        }


def test_credit_balance_is_scoped_to_verified_auth_identity(monkeypatch):
    import allpha_api.main as main

    monkeypatch.setattr(main, "SupabaseCreditLedgerStore", FakeCreditStore)
    app.dependency_overrides[current_user] = lambda: {"id": "auth-user-123"}
    try:
        response = TestClient(app).get("/v1/credits/balance", headers={"Authorization": "Bearer test"})
    finally:
        app.dependency_overrides.pop(current_user, None)

    assert response.status_code == 200
    assert response.json()["account_id"] == "auth-user-123"
    assert response.json()["available_credits"] == 42
    assert FakeCreditStore.seen_owner == "auth-user-123"


def test_credit_balance_requires_authentication():
    response = TestClient(app).get("/v1/credits/balance")
    assert response.status_code == 401

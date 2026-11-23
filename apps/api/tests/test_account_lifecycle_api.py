import asyncio

from allpha_api.account_lifecycle_api import (
    AccountDeletionRequestCreate,
    request_account_deletion,
)


def test_deletion_request_reports_database_state_without_claiming_policy_is_unapproved(monkeypatch):
    async def verify(*args, **kwargs):
        return None

    async def create(*args, **kwargs):
        return [{
            "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "status": "awaiting_policy",
            "requested_at": "2026-11-24T00:00:00Z",
            "subject_ref": "a" * 64,
        }]

    monkeypatch.setattr(
        "allpha_api.account_lifecycle_api._verify_password_and_revoke_reauth_session",
        verify,
    )
    monkeypatch.setattr(
        "allpha_api.account_lifecycle_api.service_db_request",
        create,
    )
    payload = AccountDeletionRequestCreate(
        password="test-only-password",
        confirmation_phrase="HAPUS AKUN ALLPHA SAYA",
    )
    result = asyncio.run(request_account_deletion(
        payload,
        {"id": "11111111-1111-4111-8111-111111111111"},
    ))

    assert result["execution_state"] == "awaiting_policy"
    assert result["deletion_request"]["status"] == "awaiting_policy"
    assert "belum disetujui" not in result["message"]
    assert "belum ada data yang dihapus" in result["message"]

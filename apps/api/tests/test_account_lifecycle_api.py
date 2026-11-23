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


def test_account_deletion_ownership_transfer_uses_authenticated_database_rpc(monkeypatch):
    from uuid import UUID
    from starlette.requests import Request

    from allpha_api.account_lifecycle_api import (
        AccountDeletionOwnershipTransferCreate,
        create_account_deletion_ownership_transfer,
    )

    calls = []

    async def rpc(method, endpoint, access_token, **kwargs):
        calls.append((method, endpoint, access_token, kwargs))
        return {
            "request_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "resource_type": "agent",
            "resource_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
            "successor_user_id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
            "status": "requested",
        }

    monkeypatch.setattr("allpha_api.account_lifecycle_api.user_db_request", rpc)
    request = Request({
        "type": "http", "method": "POST", "path": "/", "headers": [],
        "query_string": b"", "server": ("test", 80), "client": ("test", 1),
        "scheme": "https", "http_version": "1.1",
    })
    request.state.supabase_access_token = "verified-session-token"
    payload = AccountDeletionOwnershipTransferCreate(
        resource_type="agent",
        resource_id=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
        successor_user_id=UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"),
    )

    result = asyncio.run(create_account_deletion_ownership_transfer(
        UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        payload,
        request,
        {"id": "11111111-1111-4111-8111-111111111111"},
    ))

    assert result["transfer"]["status"] == "requested"
    assert result["execution"] == "pending_deletion_request"
    assert calls == [(
        "POST",
        "rpc/set_my_account_deletion_ownership_transfer",
        "verified-session-token",
        {"body": {
            "p_request_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "p_resource_type": "agent",
            "p_resource_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
            "p_successor_user_id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        }},
    )]

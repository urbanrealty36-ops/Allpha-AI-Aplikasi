import asyncio
import json

import httpx
import pytest

from allpha_api.credit_ledger_contract import CreditLedgerError, CreditReservationCommand
from allpha_api.credit_ledger_service import ReservationState, SettlementCommand
from allpha_api.supabase_credit_ledger_store import (
    CreditLedgerPersistenceError,
    SupabaseCreditLedgerStore,
)


def store(handler):
    return SupabaseCreditLedgerStore(
        supabase_url="https://example.supabase.co",
        service_key="test-only-service-role",
        transport=httpx.MockTransport(handler),
    )


def reservation_command():
    return CreditReservationCommand(
        idempotency_key="reserve-1", account_id="00000000-0000-0000-0000-000000000001",
        task_id="task-1", capability_id="embedding", credits_to_reserve=20,
        credit_scheme_version="scheme-v1", tariff_version="tariff-v1",
        entitlement_version="entitlement-v1", policy_approval_reference="approval-1",
        policy_version="policy-v1", estimated_usage_units=10,
        usage_unit="embedding_input_unit",
    )


def receipt(state="reserved"):
    return {
        "reservation_id": "00000000-0000-0000-0000-000000000002",
        "idempotency_key": "reserve-1",
        "account_id": "00000000-0000-0000-0000-000000000001",
        "task_id": "task-1",
        "reserved_credits": 20,
        "state": state,
    }


def test_reserve_calls_only_canonical_atomic_rpc_and_maps_receipt():
    seen = {}

    async def handler(request):
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["body"] = json.loads((await request.aread()).decode())
        return httpx.Response(200, json=receipt())

    result = asyncio.run(store(handler).reserve(reservation_command()))
    assert result.state == ReservationState.RESERVED
    assert seen["url"].endswith("/rest/v1/rpc/credit_ledger_reserve")
    assert seen["headers"]["authorization"] == "Bearer test-only-service-role"
    assert seen["body"]["p_command"]["owner_user_id"] == reservation_command().account_id
    assert seen["body"]["p_command"]["estimated_usage_units"] == 10


def test_settlement_uses_durable_rpc_with_verified_actual_usage():
    async def handler(request):
        payload = json.loads((await request.aread()).decode())
        assert request.url.path.endswith("/rpc/credit_ledger_settle")
        assert payload["p_command"]["actual_credits"] == 12
        return httpx.Response(200, json=receipt("settled"))

    result = asyncio.run(store(handler).settle(SettlementCommand(
        reservation_id=receipt()["reservation_id"], idempotency_key="settle-1",
        source_event_id="usage-event-1", policy_version="policy-v1",
        actual_credits=12, actual_usage_units=6, usage_unit="embedding_input_unit", release_unused=True,
    )))
    assert result.state == ReservationState.SETTLED


def test_policy_and_idempotency_conflicts_are_sanitized():
    async def policy_handler(request):
        return httpx.Response(403, json={"code": "42501", "message": "CREDIT_POLICY_NOT_APPROVED"})
    with pytest.raises(CreditLedgerError, match="approved credit policy"):
        asyncio.run(store(policy_handler).reserve(reservation_command()))

    async def conflict_handler(request):
        return httpx.Response(409, json={"code": "23505", "message": "CREDIT_LEDGER_IDEMPOTENCY_CONFLICT"})
    with pytest.raises(CreditLedgerError, match="idempotency key conflicts"):
        asyncio.run(store(conflict_handler).reserve(reservation_command()))


def test_unknown_commit_status_fails_closed_without_claiming_success():
    async def handler(request):
        raise httpx.ReadTimeout("simulated timeout")
    with pytest.raises(CreditLedgerPersistenceError, match="commit status is unknown"):
        asyncio.run(store(handler).reserve(reservation_command()))


def test_environment_factory_requires_server_only_service_role_key(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    with pytest.raises(ValueError, match="SUPABASE_SERVICE_ROLE_KEY"):
        SupabaseCreditLedgerStore.from_environment()

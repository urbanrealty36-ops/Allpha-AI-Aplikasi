from __future__ import annotations

import asyncio
from pathlib import Path

from allpha_api.knowledge_worker import SupabaseKnowledgeJobStore
from allpha_api.lease_heartbeat import run_with_lease_heartbeat


def test_heartbeat_renews_until_operation_finishes():
    calls = 0

    async def heartbeat():
        nonlocal calls
        calls += 1
        return True

    async def operation():
        await asyncio.sleep(0.035)

    async def scenario():
        assert await run_with_lease_heartbeat(
            operation, heartbeat, lease_seconds=10, identity="job-ok",
            heartbeat_interval_seconds=0.01,
        ) is True

    asyncio.run(scenario())
    assert calls >= 2


def test_lost_lease_cancels_operation_and_returns_false():
    cancelled = False

    async def heartbeat():
        return False

    async def operation():
        nonlocal cancelled
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            cancelled = True
            raise

    async def scenario():
        assert await run_with_lease_heartbeat(
            operation, heartbeat, lease_seconds=10, identity="job-lost",
            heartbeat_interval_seconds=0.01,
        ) is False

    asyncio.run(scenario())
    assert cancelled is True


def test_heartbeat_error_fails_closed_and_cancels_operation():
    async def heartbeat():
        raise RuntimeError("database unavailable")

    async def operation():
        await asyncio.sleep(5)

    async def scenario():
        assert await run_with_lease_heartbeat(
            operation, heartbeat, lease_seconds=10, identity="job-error",
            heartbeat_interval_seconds=0.01,
        ) is False

    asyncio.run(scenario())


def test_supabase_knowledge_job_store_uses_lease_fenced_heartbeat_rpc():
    store = SupabaseKnowledgeJobStore(
        supabase_url="https://db.example.supabase.co",
        service_key="server-side-service-role",
    )
    observed = {}

    async def fake_request(method, path, *, params=None, body=None):
        observed.update(method=method, path=path, body=body)
        return True

    store._request = fake_request

    async def scenario():
        job = {"id": "job-uuid", "lease_token": "lease-uuid"}
        assert await store.heartbeat(job, lease_seconds=90) is True

    asyncio.run(scenario())
    assert observed == {
        "method": "POST",
        "path": "rpc/heartbeat_agent_knowledge_job",
        "body": {
            "p_job_id": "job-uuid",
            "p_lease_token": "lease-uuid",
            "p_lease_seconds": 90,
        },
    }



def test_knowledge_heartbeat_migration_is_service_only_and_lease_fenced():
    migration = (
        Path(__file__).resolve().parents[1]
        / "supabase" / "migrations"
        / "20261124075000_eng_p07_knowledge_job_lease_heartbeat.sql"
    )
    sql = " ".join(migration.read_text(encoding="utf-8").lower().split())
    assert "p_lease_seconds is null" in sql
    assert "job.lease_expires_at > clock_timestamp()" in sql
    assert "source.source_version = job.source_version" in sql
    assert "revoke all on function public.heartbeat_agent_knowledge_job" in sql
    assert "to service_role" in sql

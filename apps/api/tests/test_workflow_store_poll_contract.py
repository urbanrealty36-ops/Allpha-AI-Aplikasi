import asyncio

import httpx

from allpha_api.workflow_store import WorkflowStore


def test_runnable_run_scan_is_bounded_and_only_selects_poll_fields():
    observed = {}

    async def handler(request):
        observed["url"] = str(request.url)
        observed["params"] = dict(request.url.params)
        return httpx.Response(200, json=[
            {"id": "run-1", "owner_user_id": "owner-1", "status": "queued"},
        ])

    store = WorkflowStore(
        supabase_url="https://supabase.example",
        service_key="test-only",
        transport=httpx.MockTransport(handler),
    )
    rows = asyncio.run(store.list_runnable_runs(limit=250))

    assert rows[0]["id"] == "run-1"
    assert observed["url"].endswith("/rest/v1/workflow_runs")
    assert observed["params"]["select"] == "id,owner_user_id,status,created_at"
    assert observed["params"]["status"] == "in.(queued,running)"
    assert observed["params"]["order"] == "created_at.asc"
    assert observed["params"]["limit"] == "100"


def test_runnable_run_scan_returns_empty_when_no_candidates():
    async def handler(request):
        return httpx.Response(200, json=[])

    store = WorkflowStore(
        supabase_url="https://supabase.example",
        service_key="test-only",
        transport=httpx.MockTransport(handler),
    )
    assert asyncio.run(store.list_runnable_runs(limit=25)) == []

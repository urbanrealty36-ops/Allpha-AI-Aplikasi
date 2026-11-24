import asyncio
import json

import httpx
import pytest

from allpha_api.knowledge_worker import SupabaseKnowledgeJobStore


JOB = {
    "id": "11111111-1111-4111-8111-111111111111",
    "lease_token": "22222222-2222-4222-8222-222222222222",
    "source_version": 7,
}
RECEIPT = {
    "scanner_id": "scanner-prod-1",
    "engine_version": "1.4.6",
    "signature_version": "2026-11-24",
    "sha256": "a" * 64,
    "contract_version": "allpha.document-scan.v1",
}


def test_document_source_stage_update_uses_service_only_lease_fenced_rpc():
    seen = []

    async def handler(request):
        seen.append(request)
        assert request.url.path.endswith("/rpc/update_agent_knowledge_source_processing_state")
        assert request.headers["Authorization"] == "Bearer service-role-key"
        payload = json.loads(request.content)
        assert payload == {
            "p_job_id": JOB["id"],
            "p_lease_token": JOB["lease_token"],
            "p_source_version": 7,
            "p_stage": "document_parsing",
            "p_scanner_receipt": RECEIPT,
        }
        return httpx.Response(200, json=True)

    store = SupabaseKnowledgeJobStore(
        supabase_url="https://example.supabase.co",
        service_key="service-role-key",
        transport=httpx.MockTransport(handler),
    )

    async def scenario():
        result = await store.update_source_state(
            JOB, status="processing", stage="document_parsing",
            scanner_receipt=RECEIPT,
        )
        assert result is True
        assert len(seen) == 1

    asyncio.run(scenario())


def test_document_source_stage_update_does_not_fallback_to_unfenced_patch():
    async def handler(request):
        assert request.method == "POST"
        assert request.url.path.endswith("/rpc/update_agent_knowledge_source_processing_state")
        return httpx.Response(404, json={"code": "PGRST202"})

    store = SupabaseKnowledgeJobStore(
        supabase_url="https://example.supabase.co",
        service_key="service-role-key",
        transport=httpx.MockTransport(handler),
    )

    async def scenario():
        with pytest.raises(RuntimeError, match="Supabase worker operation failed"):
            await store.update_source_state(
                JOB, status="processing", stage="malware_scan",
            )

    asyncio.run(scenario())

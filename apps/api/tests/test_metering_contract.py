from datetime import datetime, timezone

import pytest

from allpha_api.embedding_contract import EmbeddingRequest, EmbeddingResponse
from allpha_api.metering_contract import MeteringContractError, build_metering_record


def request():
    return EmbeddingRequest(
        task_id="task-1", idempotency_key="stable-key", trace_id="trace-1",
        owner_id="owner-1", agent_id="agent-1", source_id="source-1",
        source_version=3, sensitivity="internal", attempt=1, timeout_ms=1000,
        chunks=[{"chunk_id": "chunk-1", "content_sha256": "a" * 64, "text": "x"}],
    )


def response(**changes):
    values = dict(
        task_id="task-1", provider_id="approved-provider", model_id="approved-model",
        model_version="immutable-v1", dimensions=2,
        vectors=[{"chunk_id": "chunk-1", "content_sha256": "a" * 64, "values": [0.1, 0.2]}],
        trace_id="trace-1", completed_at=datetime(2026, 10, 15, tzinfo=timezone.utc),
        usage_units=10, cost_microunits=125,
    )
    values.update(changes)
    return EmbeddingResponse(**values)


def test_metering_record_has_stable_idempotency_and_attribution():
    record = build_metering_record(request(), response())
    duplicate = build_metering_record(request(), response())
    assert record.idempotency_key == "stable-key"
    assert record.owner_id == "owner-1"
    assert record.agent_id == "agent-1"
    assert record.source_version == 3
    assert record.payload_fingerprint() == duplicate.payload_fingerprint()


def test_metering_record_fingerprint_detects_same_key_payload_conflict():
    first = build_metering_record(request(), response(cost_microunits=125))
    conflicting = build_metering_record(request(), response(cost_microunits=126))
    assert first.idempotency_key == conflicting.idempotency_key
    assert first.payload_fingerprint() != conflicting.payload_fingerprint()


@pytest.mark.parametrize(
    "changes",
    [
        {"usage_units": None},
        {"cost_microunits": None},
        {"task_id": "other-task"},
        {"trace_id": "other-trace"},
    ],
)
def test_metering_record_rejects_missing_actuals_or_identity_mismatch(changes):
    with pytest.raises(MeteringContractError):
        build_metering_record(request(), response(**changes))

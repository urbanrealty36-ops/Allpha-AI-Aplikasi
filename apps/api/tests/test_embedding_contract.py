import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from allpha_api.embedding_contract import (
    EmbeddingRequest, EmbeddingResponse, validate_response_matches_request,
)

def make_request():
    return EmbeddingRequest(
        task_id="job-1", idempotency_key="source-v1-batch-0", trace_id="trace-1",
        owner_id="owner-1", agent_id="agent-1", source_id="source-1",
        source_version=1, sensitivity="confidential", attempt=1, timeout_ms=5000,
        chunks=[
            {"chunk_id":"chunk-1","content_sha256":"a"*64,"text":"hello"},
            {"chunk_id":"chunk-2","content_sha256":"b"*64,"text":"world"},
        ],
    )

def make_response():
    return EmbeddingResponse(
        task_id="job-1", provider_id="router-selected", model_id="embedding-model",
        model_version="immutable-version-1", dimensions=3,
        vectors=[
            {"chunk_id":"chunk-1","content_sha256":"a"*64,"values":[0.1,0.2,0.3]},
            {"chunk_id":"chunk-2","content_sha256":"b"*64,"values":[0.4,0.5,0.6]},
        ],
        trace_id="trace-1", completed_at=datetime.now(timezone.utc),
    )

def test_embedding_contract_matches_chunk_provenance():
    validate_response_matches_request(make_request(), make_response())

def test_embedding_contract_rejects_partial_vectors():
    request, response = make_request(), make_response()
    response = response.model_copy(update={"vectors": response.vectors[:1]})
    with pytest.raises(ValueError, match="partial"):
        validate_response_matches_request(request, response)

def test_embedding_contract_rejects_dimension_mismatch():
    with pytest.raises(ValidationError, match="dimensions"):
        EmbeddingResponse(
            task_id="job-1", provider_id="router-selected", model_id="m",
            model_version="v1", dimensions=2,
            vectors=[{"chunk_id":"c","content_sha256":"c"*64,"values":[0.1,0.2,0.3]}],
            trace_id="t", completed_at=datetime.now(timezone.utc),
        )

def test_embedding_contract_rejects_duplicate_chunk_ids():
    request = make_request().model_dump()
    request["chunks"] = [request["chunks"][0], request["chunks"][0]]
    with pytest.raises(ValidationError, match="unique"):
        EmbeddingRequest.model_validate(request)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_embedding_contract_rejects_non_finite_values(bad):
    with pytest.raises(ValidationError, match="finite"):
        EmbeddingResponse(
            task_id="job-1", provider_id="p", model_id="m", model_version="v1", dimensions=2,
            vectors=[{"chunk_id": "c", "content_sha256": "c" * 64, "values": [0.1, bad]}],
            trace_id="t", completed_at=datetime.now(timezone.utc),
        )


@pytest.mark.parametrize("field,value", [
    ("provider_id", "  "), ("model_id", " m"), ("model_version", "latest"), ("model_version", "Default"),
])
def test_embedding_contract_requires_concrete_provider_and_immutable_model_identity(field, value):
    base = dict(
        task_id="job-1", provider_id="p", model_id="m", model_version="v1", dimensions=1,
        vectors=[{"chunk_id": "c", "content_sha256": "c" * 64, "values": [0.1]}],
        trace_id="t", completed_at=datetime.now(timezone.utc),
    )
    base[field] = value
    with pytest.raises(ValidationError):
        EmbeddingResponse(**base)


def test_embedding_contract_rejects_same_ids_with_different_content_hash():
    request, response = make_request(), make_response()
    tampered = response.vectors[0].model_copy(update={"content_sha256": "f" * 64})
    response = response.model_copy(update={"vectors": [tampered, response.vectors[1]]})
    with pytest.raises(ValueError, match="mismatch"):
        validate_response_matches_request(request, response)


def test_embedding_contract_rejects_task_or_trace_mismatch():
    request, response = make_request(), make_response()
    for update in ({"task_id": "other"}, {"trace_id": "other"}):
        with pytest.raises(ValueError, match="task/trace"):
            validate_response_matches_request(request, response.model_copy(update=update))

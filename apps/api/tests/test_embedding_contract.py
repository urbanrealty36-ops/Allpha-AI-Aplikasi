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
    request = make_request()
    with pytest.raises(ValidationError, match="unique"):
        request.model_copy(update={"chunks": [request.chunks[0], request.chunks[0]]})

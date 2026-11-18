import hashlib

import pytest

from allpha_api.generation_job_worker import _build_memory_context_evidence


def test_generation_memory_evidence_preserves_full_and_bounded_excerpt_digests():
    full = "M" * 7000
    excerpt = full[:3000]
    item = {
        "id": "memory-1",
        "content": excerpt,
        "content_sha256": hashlib.sha256(full.encode()).hexdigest(),
        "retrieved_content_sha256": hashlib.sha256(excerpt.encode()).hexdigest(),
        "memory_type": "long_term",
        "version": 4,
        "policy_version": 2,
        "classification": "internal",
        "retrieval_method": "keyword",
        "retrieval_score": 0.9,
    }

    context, evidence = _build_memory_context_evidence([item], "owner preferences")

    assert excerpt in context
    assert evidence["items"][0]["content_sha256"] == hashlib.sha256(full.encode()).hexdigest()
    assert evidence["items"][0]["retrieved_text_sha256"] == hashlib.sha256(excerpt.encode()).hexdigest()
    assert evidence["items"][0]["content_sha256"] != evidence["items"][0]["retrieved_text_sha256"]


def test_generation_memory_evidence_rejects_modified_excerpt():
    excerpt = "retrieved excerpt"
    item = {
        "id": "memory-1",
        "content": excerpt,
        "content_sha256": "a" * 64,
        "retrieved_content_sha256": "b" * 64,
        "memory_type": "long_term",
        "version": 4,
        "policy_version": 2,
        "classification": "internal",
    }

    with pytest.raises(ValueError, match="memory_context_item_integrity_invalid"):
        _build_memory_context_evidence([item], "query")

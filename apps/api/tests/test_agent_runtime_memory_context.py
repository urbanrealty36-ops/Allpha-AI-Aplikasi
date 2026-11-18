import hashlib

import pytest

from allpha_api.agent_runtime_api import _memory_context_snapshot
from allpha_api.memory_coordinator import MemoryUnavailable


def memory_item(content="Owner prefers concise, direct explanations."):
    return {
        "id": "memory-item-1",
        "content": content,
        "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "memory_type": "long_term",
        "classification": "internal",
        "version": 3,
        "policy_version": 5,
        "source_ref": {"private_message_id": "must-not-enter-planner-payload"},
        "provenance": {"private_origin": "must-not-enter-planner-payload"},
    }


def test_memory_snapshot_contains_only_consent_scoped_prompt_data_and_provenance():
    context, references, digest = _memory_context_snapshot([memory_item()])

    assert context == [{
        "memory_type": "long_term",
        "classification": "internal",
        "content": "Owner prefers concise, direct explanations.",
    }]
    assert references == [{
        "id": "memory-item-1",
        "content_sha256": memory_item()["content_sha256"],
        "version": 3,
        "policy_version": 5,
    }]
    assert len(digest) == 64
    assert "private_message_id" not in str(context)
    assert "private_origin" not in str(references)


def test_memory_snapshot_fails_closed_when_content_digest_or_version_is_invalid():
    invalid_digest = {**memory_item(), "content_sha256": "0" * 64}
    with pytest.raises(MemoryUnavailable):
        _memory_context_snapshot([invalid_digest])

    invalid_version = {**memory_item(), "version": True}
    with pytest.raises(MemoryUnavailable):
        _memory_context_snapshot([invalid_version])

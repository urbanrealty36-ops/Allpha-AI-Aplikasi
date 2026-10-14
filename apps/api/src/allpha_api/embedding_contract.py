"""Versioned, provider-neutral contract for ENG-P07 -> ENG-P09 embeddings.

This module deliberately defines the boundary only. Provider execution must be
implemented by the canonical AI Gateway/Model Router, not by a feature-specific
provider SDK or direct provider call.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CONTRACT_VERSION = "allpha.embedding.v1"


class EmbeddingChunkInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    chunk_id: str = Field(min_length=1, max_length=128)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    text: str = Field(min_length=1, max_length=1800)


class EmbeddingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    contract_version: Literal["allpha.embedding.v1"] = CONTRACT_VERSION
    task_id: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=1, max_length=256)
    trace_id: str = Field(min_length=1, max_length=128)
    owner_id: str = Field(min_length=1, max_length=128)
    agent_id: str = Field(min_length=1, max_length=128)
    source_id: str = Field(min_length=1, max_length=128)
    source_version: int = Field(ge=1)
    sensitivity: Literal["public", "internal", "confidential", "restricted"]
    attempt: int = Field(ge=1, le=8)
    timeout_ms: int = Field(ge=100, le=120_000)
    chunks: list[EmbeddingChunkInput] = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def unique_chunk_ids(self):
        ids = [item.chunk_id for item in self.chunks]
        if len(ids) != len(set(ids)):
            raise ValueError("chunk_id values must be unique within a request")
        return self


class EmbeddingVector(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    chunk_id: str = Field(min_length=1, max_length=128)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    values: list[float] = Field(min_length=1, max_length=8192)

    @field_validator("values")
    @classmethod
    def finite_values(cls, values: list[float]) -> list[float]:
        if not all(math.isfinite(value) for value in values):
            raise ValueError("embedding vector values must be finite")
        return values


class EmbeddingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    contract_version: Literal["allpha.embedding.v1"] = CONTRACT_VERSION
    task_id: str = Field(min_length=1, max_length=128)
    provider_id: str = Field(min_length=1, max_length=128)
    model_id: str = Field(min_length=1, max_length=128)
    model_version: str = Field(min_length=1, max_length=128)
    dimensions: int = Field(ge=1, le=8192)
    vectors: list[EmbeddingVector] = Field(min_length=1, max_length=128)
    usage_units: int | None = Field(default=None, ge=0)
    cost_microunits: int | None = Field(default=None, ge=0)
    trace_id: str = Field(min_length=1, max_length=128)
    completed_at: datetime

    @model_validator(mode="after")
    def validate_vectors(self):
        if any(len(vector.values) != self.dimensions for vector in self.vectors):
            raise ValueError("vector dimensions do not match response dimensions")
        ids = [vector.chunk_id for vector in self.vectors]
        if len(ids) != len(set(ids)):
            raise ValueError("response contains duplicate chunk IDs")
        return self


class EmbeddingFailure(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    contract_version: Literal["allpha.embedding.v1"] = CONTRACT_VERSION
    task_id: str = Field(min_length=1, max_length=128)
    code: str = Field(min_length=1, max_length=80)
    retryable: bool
    retry_after_ms: int | None = Field(default=None, ge=0, le=300_000)
    trace_id: str = Field(min_length=1, max_length=128)


def validate_response_matches_request(
    request: EmbeddingRequest, response: EmbeddingResponse
) -> None:
    """Reject partial, reordered/mismatched-content, or wrong-task responses."""
    if response.task_id != request.task_id or response.trace_id != request.trace_id:
        raise ValueError("embedding response task/trace does not match request")
    expected = {chunk.chunk_id: chunk.content_sha256 for chunk in request.chunks}
    actual = {vector.chunk_id: vector.content_sha256 for vector in response.vectors}
    if actual != expected:
        raise ValueError("embedding response is partial or chunk provenance mismatches")

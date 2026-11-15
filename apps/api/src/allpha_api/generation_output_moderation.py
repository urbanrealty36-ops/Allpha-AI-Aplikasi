"""Policy-bound generation output moderation adapter contract.

The built-in adapter supports manual-review-only operation. It never approves
content automatically; a Human reviewer must approve or reject each artifact
through the canonical review workflow.
"""
from __future__ import annotations

import importlib
import os
from typing import Any, Protocol


class GenerationOutputModerator(Protocol):
    async def moderate(self, *, text: str, policy: dict[str, Any], metadata: dict[str, str]) -> dict[str, Any]:
        ...


class ManualReviewOnlyModerator:
    """Fail-closed adapter: every output is held for an attributed Human review."""

    @staticmethod
    def supports_policy(policy: dict[str, Any]) -> bool:
        return policy.get("mode") == "manual_review_only" and policy.get("manual_review_only") is True

    async def moderate(self, *, text: str, policy: dict[str, Any], metadata: dict[str, str]) -> dict[str, Any]:
        if not self.supports_policy(policy):
            raise RuntimeError("manual review adapter requires an explicitly approved manual_review_only policy")
        if not isinstance(text, str) or not text.strip():
            return {"decision": "review_required", "reason_code": "empty_output"}
        return {
            "decision": "review_required",
            "reason_code": "manual_review_required",
            "review_mode": "human",
        }


def load_generation_output_moderator() -> GenerationOutputModerator | None:
    target = os.getenv("ALLPHA_GENERATION_OUTPUT_MODERATOR_FACTORY", "").strip()
    if not target:
        # This adapter cannot auto-approve. The worker still requires a currently
        # approved policy row, and the adapter additionally checks its explicit mode.
        return ManualReviewOnlyModerator()
    if ":" not in target:
        raise RuntimeError("generation moderation adapter factory must use module:factory syntax")
    module_name, factory_name = target.split(":", 1)
    if not module_name.startswith("allpha_api.") or not factory_name.isidentifier():
        raise RuntimeError("generation moderation adapter must be an allpha_api module factory")
    factory = getattr(importlib.import_module(module_name), factory_name, None)
    if not callable(factory):
        raise RuntimeError("generation moderation adapter factory is unavailable")
    adapter = factory()
    if not callable(getattr(adapter, "moderate", None)):
        raise RuntimeError("generation moderation adapter contract is invalid")
    return adapter

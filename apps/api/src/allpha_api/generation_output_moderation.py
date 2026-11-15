"""Policy-bound generation output moderation adapter contract.

No moderation provider is selected by default. The worker requires an explicitly
configured internal adapter and a currently approved database policy.
"""
from __future__ import annotations

import importlib
import os
from typing import Any, Protocol


class GenerationOutputModerator(Protocol):
    async def moderate(self, *, text: str, policy: dict[str, Any], metadata: dict[str, str]) -> dict[str, Any]:
        ...


def load_generation_output_moderator() -> GenerationOutputModerator | None:
    target = os.getenv("ALLPHA_GENERATION_OUTPUT_MODERATOR_FACTORY", "").strip()
    if not target or ":" not in target:
        return None
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

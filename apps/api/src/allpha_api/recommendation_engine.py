"""Shared, privacy-aware scoring primitives for every Allpha recommendation surface."""
from __future__ import annotations

from math import isfinite, log1p
from typing import Any, Awaitable, Callable

from fastapi import HTTPException

DEFAULT_WEIGHTS: dict[str, float] = {
    "followed_creator": 1000.0,
    "explicit_interest": 100.0,
    "passion": 25.0,
    "habit": 10.0,
    "engagement": 1.0,
    "mutual_connection": 2.0,
    "shared_interest": 3.0,
}
DEFAULT_POLICY_VERSION = "allpha-recommendation-v2"
FEED_RANKING_VERSION = DEFAULT_POLICY_VERSION


def normalize_weights(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return dict(DEFAULT_WEIGHTS)
    weights = dict(DEFAULT_WEIGHTS)
    for key in weights:
        raw = value.get(key)
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            number = float(raw)
            if isfinite(number) and 0 <= number <= 100:
                weights[key] = number
    return weights


def policy_from_rows(rows: Any) -> tuple[str, dict[str, float]]:
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict) and row.get("active") is True:
                version = row.get("version")
                return (
                    str(version) if isinstance(version, str) and version else DEFAULT_POLICY_VERSION,
                    normalize_weights(row.get("weights")),
                )
    return DEFAULT_POLICY_VERSION, dict(DEFAULT_WEIGHTS)


def score_creator_candidate(
    mutual_connections: int,
    shared_interests: int,
    weights: dict[str, float] | None = None,
) -> float:
    policy = normalize_weights(weights)
    return round(
        max(0, mutual_connections) * policy["mutual_connection"]
        + max(0, shared_interests) * policy["shared_interest"],
        6,
    )


def score_content_candidate(
    *,
    followed_creator: bool,
    explicit_interest_matches: int,
    passion_affinity: float,
    habit_affinity: float,
    engagement_total: int,
    weights: dict[str, float] | None = None,
) -> float:
    policy = normalize_weights(weights)
    return round(
        int(followed_creator) * policy["followed_creator"]
        + max(0, explicit_interest_matches) * policy["explicit_interest"]
        + max(0.0, min(10.0, passion_affinity)) * policy["passion"]
        + max(0.0, min(10.0, habit_affinity)) * policy["habit"]
        + log1p(max(0, engagement_total)) * policy["engagement"],
        6,
    )


def matched_signal_affinity(
    body_tokens: set[str],
    signals: list[dict[str, Any]],
    signal_type: str,
) -> float:
    affinity = 0.0
    for signal in signals:
        if signal.get("signal_type") != signal_type:
            continue
        key = str(signal.get("interest_key") or "").casefold()
        terms = {part for part in key.replace("-", "_").replace(".", "_").split("_") if part}
        if terms and terms.issubset(body_tokens):
            try:
                strength = float(signal.get("strength") or 0)
            except (TypeError, ValueError):
                continue
            if isfinite(strength) and 0 <= strength <= 1:
                affinity += strength
    return round(min(10.0, affinity), 6)


async def optional_scoring_rows(
    db_request: Callable[..., Awaitable[Any]],
    table: str,
    params: dict[str, str],
) -> list[dict[str, Any]]:
    """Use legacy ranking until the additive P04 schema is applied; never mask DB outages."""
    try:
        rows = await db_request("GET", table, params=params)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        if exc.status_code == 503 and detail.get("code") == "DATABASE_SCHEMA_NOT_READY":
            return []
        raise
    return rows if isinstance(rows, list) else []

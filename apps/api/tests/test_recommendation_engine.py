from allpha_api.recommendation_engine import normalize_weights, (
    DEFAULT_WEIGHTS,
    matched_signal_affinity,
    policy_from_rows,
    score_content_candidate,
    score_creator_candidate,
)


def test_scoring_policy_is_loaded_from_active_policy_and_validated():
    version, weights = policy_from_rows([{
        "active": True,
        "version": "policy-test-v3",
        "weights": {"followed_creator": 4, "passion": 2, "habit": -1, "engagement": float("nan")},
    }])
    assert version == "policy-test-v3"
    assert weights["followed_creator"] == 4
    assert weights["passion"] == 2
    assert weights["habit"] == DEFAULT_WEIGHTS["habit"]
    assert weights["engagement"] == DEFAULT_WEIGHTS["engagement"]


def test_creator_scoring_uses_shared_canonical_policy():
    assert score_creator_candidate(2, 1) == 7.0


def test_content_scoring_combines_explicit_passion_habit_and_quality_signals():
    score = score_content_candidate(
        followed_creator=True,
        explicit_interest_matches=2,
        passion_affinity=0.5,
        habit_affinity=1.0,
        engagement_total=3,
    )
    assert score > 9.0


def test_signal_affinity_only_matches_the_same_declared_interest():
    signals = [
        {"signal_type": "passion", "interest_key": "spatial_3d", "strength": 0.8},
        {"signal_type": "habit", "interest_key": "design_ui_ux", "strength": 0.6},
    ]
    assert matched_signal_affinity({"spatial", "3d", "render"}, signals, "passion") == 0.8
    assert matched_signal_affinity({"design", "ui", "ux"}, signals, "habit") == 0.6
    assert matched_signal_affinity({"business", "finance"}, signals, "passion") == 0.0



def test_optional_scoring_schema_fallback_only_handles_missing_migration(monkeypatch):
    import asyncio
    from fastapi import HTTPException
    from allpha_api.recommendation_engine import optional_scoring_rows

    async def missing_schema(*args, **kwargs):
        raise HTTPException(503, detail={"code": "DATABASE_SCHEMA_NOT_READY"})

    async def database_outage(*args, **kwargs):
        raise HTTPException(503, detail={"code": "CONTENT_DATABASE_UNAVAILABLE"})

    assert asyncio.run(optional_scoring_rows(missing_schema, "user_interest_graph_signals", {})) == []
    try:
        asyncio.run(optional_scoring_rows(database_outage, "user_interest_graph_signals", {}))
    except HTTPException as exc:
        assert exc.detail["code"] == "CONTENT_DATABASE_UNAVAILABLE"
    else:
        raise AssertionError("database outage must not be hidden")


def test_policy_weights_preserve_large_creator_priority_without_falling_back():
    weights = normalize_weights({
        "followed_creator": 2500,
        "explicit_interest": 250,
        "passion": 50,
        "habit": 20,
        "engagement": 2,
        "mutual_connection": 4,
        "shared_interest": 6,
    })
    assert weights["followed_creator"] == 2500
    assert weights["explicit_interest"] == 250
    assert score_content_candidate(
        followed_creator=True,
        explicit_interest_matches=1,
        passion_affinity=0,
        habit_affinity=0,
        engagement_total=0,
        weights=weights,
    ) == 2750

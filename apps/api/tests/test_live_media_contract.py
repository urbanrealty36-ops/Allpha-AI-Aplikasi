from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from allpha_api.live_media_contract import (
    LiveMediaActivationBlocked,
    LiveMediaApproval,
    LiveMediaParticipantGrant,
    LiveMediaProviderRegistry,
    LiveMediaRoom,
    LiveMediaToken,
    validate_issued_token,
    validate_participant_grant,
    validate_room_request,
    LiveMediaRoomRequest,
)


class Provider:
    provider_key = "provider.example"

    async def create_room(self, request):
        raise AssertionError("contract tests must not create provider rooms")

    async def issue_participant_token(self, room, grant):
        raise AssertionError("contract tests must not issue media tokens")

    async def get_room_state(self, room):
        return room

    async def end_room(self, room, *, idempotency_key):
        return room

    async def verify_webhook(self, raw_body, headers):
        raise AssertionError("contract tests must not accept provider webhooks")


def approved(**changes):
    values = {
        "adr_id": "ADR-WP10-001",
        "status": "approved",
        "provider_key": "provider.example",
        "decision_digest": "a" * 64,
        "allowed_regions": ("ap-southeast-1",),
        "recording_approved": False,
        "max_token_ttl_seconds": 180,
    }
    values.update(changes)
    return LiveMediaApproval(**values)


def test_provider_registry_fails_closed_without_adr_approval():
    registry = LiveMediaProviderRegistry()
    registry.register(Provider())
    with pytest.raises(LiveMediaActivationBlocked, match="ADR_WP10_001_APPROVAL_REQUIRED"):
        registry.resolve(None, region="ap-southeast-1")
    with pytest.raises(LiveMediaActivationBlocked, match="ADR_WP10_001_NOT_APPROVED"):
        registry.resolve(approved(status="proposed"), region="ap-southeast-1")


def test_provider_registry_requires_exact_approved_provider_and_region():
    registry = LiveMediaProviderRegistry()
    registry.register(Provider())
    assert registry.resolve(approved(), region="ap-southeast-1").provider_key == "provider.example"
    with pytest.raises(LiveMediaActivationBlocked, match="LIVE_MEDIA_REGION_NOT_APPROVED"):
        registry.resolve(approved(), region="ap-northeast-1")
    with pytest.raises(LiveMediaActivationBlocked, match="LIVE_MEDIA_PROVIDER_ADAPTER_NOT_REGISTERED"):
        registry.resolve(approved(provider_key="not-registered"), region="ap-southeast-1")


def test_duplicate_provider_registration_is_rejected():
    registry = LiveMediaProviderRegistry()
    registry.register(Provider())
    with pytest.raises(LiveMediaActivationBlocked, match="LIVE_MEDIA_PROVIDER_REGISTRATION_INVALID"):
        registry.register(Provider())


def test_room_and_recording_require_approved_region_and_recording_decision():
    approval = approved()
    validate_room_request(LiveMediaRoomRequest(
        session_id="session", host_user_id="owner", region="ap-southeast-1",
        session_version=1, max_participants=20,
    ), approval)
    with pytest.raises(LiveMediaActivationBlocked, match="LIVE_RECORDING_NOT_APPROVED"):
        validate_room_request(LiveMediaRoomRequest(
            session_id="session", host_user_id="owner", region="ap-southeast-1",
            session_version=1, max_participants=20, recording_requested=True,
        ), approval)


def test_participant_grant_and_provider_token_are_scope_and_ttl_bounded():
    approval = approved()
    grant = LiveMediaParticipantGrant(
        session_id="session", user_id="speaker", role="speaker", can_publish=True,
        can_subscribe=True, recording_consent=False, ttl_seconds=120,
    )
    validate_participant_grant(grant, approval)
    token = LiveMediaToken(
        provider_key="provider.example", opaque_token="opaque",
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=60),
        can_publish=True, can_subscribe=True,
    )
    validate_issued_token(token, grant, approval)
    bad_token = LiveMediaToken(
        provider_key="provider.example", opaque_token="opaque",
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=240),
        can_publish=True, can_subscribe=True,
    )
    with pytest.raises(LiveMediaActivationBlocked, match="LIVE_MEDIA_TOKEN_TTL_OUT_OF_POLICY"):
        validate_issued_token(bad_token, grant, approval)


def test_viewer_cannot_receive_publish_capability():
    with pytest.raises(LiveMediaActivationBlocked, match="LIVE_VIEWER_PUBLISH_FORBIDDEN"):
        validate_participant_grant(LiveMediaParticipantGrant(
            session_id="session", user_id="viewer", role="viewer", can_publish=True,
            can_subscribe=True, recording_consent=False, ttl_seconds=60,
        ), approved())


def test_token_cannot_expand_provider_scopes():
    grant = LiveMediaParticipantGrant(
        session_id="session", user_id="viewer", role="viewer", can_publish=False,
        can_subscribe=True, recording_consent=False, ttl_seconds=60,
    )
    token = LiveMediaToken(
        provider_key="provider.example", opaque_token="opaque",
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=30),
        can_publish=True, can_subscribe=True,
    )
    with pytest.raises(LiveMediaActivationBlocked, match="LIVE_MEDIA_TOKEN_SCOPE_MISMATCH"):
        validate_issued_token(token, grant, approved())

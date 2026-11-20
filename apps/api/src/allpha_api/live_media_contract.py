"""Provider-neutral contract for a future approved Live media transport.

The Live control plane remains authoritative for identity, session state, participant
roles, consent and authorization. A media adapter may only be resolved when the
canonical ADR-WP10-001 approval is explicitly supplied by trusted server-side
configuration. No provider is registered or activated by this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Protocol, runtime_checkable


ADR_WP10_001 = "ADR-WP10-001"
MEDIA_CONTRACT_VERSION = "1"
MAX_TOKEN_TTL_SECONDS = 300

ParticipantRole = Literal["host", "cohost", "speaker", "guest", "viewer", "moderator"]


class LiveMediaActivationBlocked(RuntimeError):
    """Raised when media activation lacks a valid, matching architecture approval."""


@dataclass(frozen=True)
class LiveMediaApproval:
    adr_id: str
    status: Literal["proposed", "approved", "rejected"]
    provider_key: str
    decision_digest: str
    allowed_regions: tuple[str, ...]
    recording_approved: bool
    max_token_ttl_seconds: int = MAX_TOKEN_TTL_SECONDS


@dataclass(frozen=True)
class LiveMediaRoomRequest:
    session_id: str
    host_user_id: str
    region: str
    session_version: int
    max_participants: int
    recording_requested: bool = False


@dataclass(frozen=True)
class LiveMediaParticipantGrant:
    session_id: str
    user_id: str
    role: ParticipantRole
    can_publish: bool
    can_subscribe: bool
    recording_consent: bool
    ttl_seconds: int


@dataclass(frozen=True)
class LiveMediaRoom:
    provider_key: str
    provider_session_ref: str
    state: Literal["created", "active", "reconnecting", "ended", "failed"]


@dataclass(frozen=True)
class LiveMediaToken:
    provider_key: str
    opaque_token: str
    expires_at: datetime
    can_publish: bool
    can_subscribe: bool


@dataclass(frozen=True)
class LiveMediaWebhook:
    provider_key: str
    event_id: str
    provider_session_ref: str
    event_type: str
    occurred_at: datetime
    payload_digest: str


@runtime_checkable
class LiveMediaProvider(Protocol):
    """Adapter contract; implementations must keep provider credentials server-side."""

    provider_key: str

    async def create_room(self, request: LiveMediaRoomRequest) -> LiveMediaRoom: ...

    async def issue_participant_token(
        self, room: LiveMediaRoom, grant: LiveMediaParticipantGrant
    ) -> LiveMediaToken: ...

    async def get_room_state(self, room: LiveMediaRoom) -> LiveMediaRoom: ...

    async def end_room(self, room: LiveMediaRoom, *, idempotency_key: str) -> LiveMediaRoom: ...

    async def verify_webhook(
        self, raw_body: bytes, headers: dict[str, str]
    ) -> LiveMediaWebhook: ...


class LiveMediaProviderRegistry:
    """Explicitly injected registry. It does not discover or auto-enable providers."""

    def __init__(self) -> None:
        self._providers: dict[str, LiveMediaProvider] = {}

    def register(self, provider: LiveMediaProvider) -> None:
        key = provider.provider_key.strip()
        if not key or key in self._providers:
            raise LiveMediaActivationBlocked("LIVE_MEDIA_PROVIDER_REGISTRATION_INVALID")
        self._providers[key] = provider

    def resolve(
        self, approval: LiveMediaApproval | None, *, region: str
    ) -> LiveMediaProvider:
        if approval is None:
            raise LiveMediaActivationBlocked("ADR_WP10_001_APPROVAL_REQUIRED")
        if approval.adr_id != ADR_WP10_001 or approval.status != "approved":
            raise LiveMediaActivationBlocked("ADR_WP10_001_NOT_APPROVED")
        if (
            len(approval.decision_digest) != 64
            or any(ch not in "0123456789abcdef" for ch in approval.decision_digest.lower())
            or not approval.provider_key.strip()
            or not approval.allowed_regions
            or approval.max_token_ttl_seconds < 1
            or approval.max_token_ttl_seconds > MAX_TOKEN_TTL_SECONDS
        ):
            raise LiveMediaActivationBlocked("LIVE_MEDIA_APPROVAL_CONTRACT_INVALID")
        if region not in approval.allowed_regions:
            raise LiveMediaActivationBlocked("LIVE_MEDIA_REGION_NOT_APPROVED")
        provider = self._providers.get(approval.provider_key)
        if provider is None:
            raise LiveMediaActivationBlocked("LIVE_MEDIA_PROVIDER_ADAPTER_NOT_REGISTERED")
        return provider


def validate_room_request(
    request: LiveMediaRoomRequest, approval: LiveMediaApproval
) -> None:
    if request.session_version < 1 or not 2 <= request.max_participants <= 10_000:
        raise LiveMediaActivationBlocked("LIVE_MEDIA_ROOM_REQUEST_INVALID")
    if request.region not in approval.allowed_regions:
        raise LiveMediaActivationBlocked("LIVE_MEDIA_REGION_NOT_APPROVED")
    if request.recording_requested and not approval.recording_approved:
        raise LiveMediaActivationBlocked("LIVE_RECORDING_NOT_APPROVED")


def validate_participant_grant(
    grant: LiveMediaParticipantGrant, approval: LiveMediaApproval
) -> None:
    if grant.ttl_seconds < 1 or grant.ttl_seconds > approval.max_token_ttl_seconds:
        raise LiveMediaActivationBlocked("LIVE_MEDIA_TOKEN_TTL_OUT_OF_POLICY")
    if grant.role == "viewer" and grant.can_publish:
        raise LiveMediaActivationBlocked("LIVE_VIEWER_PUBLISH_FORBIDDEN")
    if grant.role in {"guest", "viewer"} and grant.can_publish:
        raise LiveMediaActivationBlocked("LIVE_NON_SPEAKER_PUBLISH_FORBIDDEN")
    if grant.recording_consent is False and approval.recording_approved:
        # Consent is per participant; approval of the recording product is not consent.
        return


def validate_issued_token(
    token: LiveMediaToken,
    grant: LiveMediaParticipantGrant,
    approval: LiveMediaApproval,
    *,
    now: datetime | None = None,
) -> None:
    current = now or datetime.now(timezone.utc)
    expires = token.expires_at
    if expires.tzinfo is None:
        raise LiveMediaActivationBlocked("LIVE_MEDIA_TOKEN_EXPIRY_INVALID")
    remaining = (expires - current).total_seconds()
    if not token.opaque_token or token.provider_key != approval.provider_key:
        raise LiveMediaActivationBlocked("LIVE_MEDIA_TOKEN_PROVIDER_MISMATCH")
    if remaining <= 0 or remaining > min(grant.ttl_seconds, approval.max_token_ttl_seconds):
        raise LiveMediaActivationBlocked("LIVE_MEDIA_TOKEN_TTL_OUT_OF_POLICY")
    if token.can_publish != grant.can_publish or token.can_subscribe != grant.can_subscribe:
        raise LiveMediaActivationBlocked("LIVE_MEDIA_TOKEN_SCOPE_MISMATCH")

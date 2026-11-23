from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from allpha_api.organization_service import OrganizationActor, OrganizationService

ACTOR_ID = "11111111-1111-4111-8111-111111111111"
ORG_ID = "22222222-2222-4222-8222-222222222222"
OTHER_ORG_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
OTHER_USER_ID = "33333333-3333-4333-8333-333333333333"


def actor() -> OrganizationActor:
    return OrganizationActor(user_id=ACTOR_ID, access_token="verified-jwt")


class Repository:
    async def list_actor_memberships(self, context):
        assert context.user_id == ACTOR_ID
        assert context.access_token == "verified-jwt"
        return [
            {"organization_id": ORG_ID, "user_id": ACTOR_ID},
            {"organization_id": OTHER_ORG_ID, "user_id": OTHER_USER_ID},
            {"organization_id": "not-a-uuid", "user_id": ACTOR_ID},
        ]

    async def list_organizations(self, context, organization_ids):
        assert organization_ids == {ORG_ID}
        return [
            {"id": ORG_ID, "name": "My tenant"},
            {"id": OTHER_ORG_ID, "name": "Foreign tenant"},
        ]

    async def list_tenant_memberships(self, context, organization_id):
        assert organization_id == ORG_ID
        return [
            {"organization_id": ORG_ID, "user_id": ACTOR_ID, "role": "member"},
            {"organization_id": ORG_ID, "user_id": OTHER_USER_ID, "role": "admin"},
            {"organization_id": OTHER_ORG_ID, "user_id": ACTOR_ID, "role": "owner"},
        ]


@pytest.mark.anyio
async def test_list_for_actor_rechecks_membership_and_organization_scope():
    service = OrganizationService(Repository())
    result = await service.list_for_actor(actor())
    assert result == [{"id": ORG_ID, "name": "My tenant"}]


@pytest.mark.anyio
async def test_regular_member_only_receives_own_membership():
    service = OrganizationService(Repository())
    result = await service.list_memberships(
        actor(),
        ORG_ID,
        {"organization_id": ORG_ID, "user_id": ACTOR_ID, "role": "member"},
    )
    assert result == [{"organization_id": ORG_ID, "user_id": ACTOR_ID, "role": "member"}]


@pytest.mark.anyio
async def test_tenant_admin_receives_roster_only_for_the_authorized_tenant():
    service = OrganizationService(Repository())
    result = await service.list_memberships(
        actor(),
        ORG_ID,
        {"organization_id": ORG_ID, "user_id": ACTOR_ID, "role": "admin"},
    )
    assert len(result) == 2
    assert all(row["organization_id"] == ORG_ID for row in result)


def test_actor_context_rejects_mismatched_verified_identity():
    request = SimpleNamespace(
        state=SimpleNamespace(
            user_id=OTHER_USER_ID,
            supabase_access_token="verified-jwt",
        )
    )
    with pytest.raises(HTTPException) as error:
        OrganizationActor.from_request(request, {"id": ACTOR_ID})
    assert error.value.status_code == 401
    assert error.value.detail["code"] == "IDENTITY_MISMATCH"


def test_actor_context_requires_verified_bearer_context():
    request = SimpleNamespace(
        state=SimpleNamespace(user_id=ACTOR_ID, supabase_access_token=None)
    )
    with pytest.raises(HTTPException) as error:
        OrganizationActor.from_request(request, {"id": ACTOR_ID})
    assert error.value.status_code == 401
    assert error.value.detail["code"] == "AUTH_CONTEXT_MISSING"

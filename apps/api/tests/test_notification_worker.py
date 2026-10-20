from __future__ import annotations

import asyncio

from allpha_api import notification_worker as worker


def test_worker_noops_without_explicit_provider_configuration(monkeypatch):
    calls = []

    async def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("provider-disabled worker must not touch queue or provider")

    monkeypatch.setattr(worker, "_provider_enabled", lambda: False)
    monkeypatch.setattr(worker, "_rpc", forbidden)
    result = asyncio.run(worker.process_batch(limit=10))
    assert result["claimed"] == 0
    assert calls == []


def test_worker_dispatches_claimed_notification_with_lease_and_safe_payload(monkeypatch):
    delivery = {
        "id": "delivery-1", "notification_id": "notification-1", "user_id": "user-1",
        "device_id": "device-1", "lease_token": "lease-1", "attempt_count": 1,
        "max_attempts": 5, "state": "sending",
    }
    calls = []
    rpc_calls = []

    async def fake_rpc(name, payload):
        rpc_calls.append((name, payload))
        if name == "enqueue_notification_push_deliveries":
            return 1
        if name == "claim_notification_push_receipts":
            return []
        if name == "claim_notification_push_deliveries":
            return [delivery]
        raise AssertionError(name)

    async def fake_rest(method, table, *, params=None, body=None, prefer=None):
        calls.append((method, table, params, body, prefer))
        if method == "GET" and table == "notifications":
            return [{
                "id": "notification-1", "user_id": "user-1", "title": "Pesan baru",
                "body": "Anda menerima pesan baru.", "category": "social_activity", "delivery_state": "delivered",
                "payload": {"type": "message", "message_id": "message-1",
                            "conversation_id": "conversation-1", "untrusted_url": "https://evil.invalid"},
                "expires_at": None,
            }]
        if method == "GET" and table == "notification_devices":
            return [{"id": "device-1", "user_id": "user-1",
                     "expo_push_token": "ExponentPushToken[valid]", "enabled": True}]
        if method == "GET" and table == "user_settings":
            return [{"notification_preferences": {"push_enabled": True, "social_activity": True}}]
        if method == "PATCH" and table == "notification_push_deliveries":
            return [{"id": "delivery-1"}]
        raise AssertionError((method, table, params))

    sent = {}

    async def fake_send(token, title, body, data):
        sent.update(token=token, title=title, body=body, data=data)
        return {"ticket_id": "ticket-1"}

    monkeypatch.setattr(worker, "_provider_enabled", lambda: True)
    monkeypatch.setattr(worker, "_rpc", fake_rpc)
    monkeypatch.setattr(worker, "_rest", fake_rest)
    monkeypatch.setattr(worker, "_expo_send", fake_send)

    result = asyncio.run(worker.process_batch(limit=10))
    assert result["enqueued"] == 1
    assert result["claimed"] == 1
    assert result["sent"] == 1
    assert sent["token"] == "ExponentPushToken[valid]"
    assert sent["data"] == {
        "notificationId": "notification-1", "type": "message",
        "conversationId": "conversation-1", "messageId": "message-1",
    }
    update = next(call for call in calls if call[0] == "PATCH")
    assert update[2]["lease_token"] == "eq.lease-1"
    assert update[3]["state"] == "sent"
    assert update[3]["provider_ticket_id"] == "ticket-1"
    assert update[3]["lease_token"] is None
    assert [name for name, _ in rpc_calls] == [
        "enqueue_notification_push_deliveries",
        "claim_notification_push_receipts",
        "claim_notification_push_deliveries",
    ]


def test_worker_retries_transient_provider_failure_with_bounded_backoff(monkeypatch):
    delivery = {
        "id": "delivery-1", "notification_id": "notification-1", "user_id": "user-1",
        "device_id": "device-1", "lease_token": "lease-1", "attempt_count": 2,
        "max_attempts": 5, "state": "sending",
    }
    patches = []

    async def fake_rpc(name, payload):
        if name == "enqueue_notification_push_deliveries":
            return 0
        if name == "claim_notification_push_receipts":
            return []
        if name == "claim_notification_push_deliveries":
            return [delivery]
        raise AssertionError(name)

    async def fake_rest(method, table, *, params=None, body=None, prefer=None):
        if method == "GET" and table == "notifications":
            return [{"id": "notification-1", "user_id": "user-1", "title": "Title",
                     "body": "Body", "category": "social_activity", "delivery_state": "delivered", "payload": {}, "expires_at": None}]
        if method == "GET" and table == "notification_devices":
            return [{"id": "device-1", "user_id": "user-1",
                     "expo_push_token": "ExponentPushToken[valid]", "enabled": True}]
        if method == "GET" and table == "user_settings":
            return [{"notification_preferences": {"push_enabled": True, "social_activity": True}}]
        if method == "PATCH" and table == "notification_push_deliveries":
            patches.append(body)
            return [{"id": "delivery-1"}]
        raise AssertionError((method, table))

    async def fail_send(*args, **kwargs):
        raise worker.ExpoPushError("expo_network_error", retryable=True)

    monkeypatch.setattr(worker, "_provider_enabled", lambda: True)
    monkeypatch.setattr(worker, "_rpc", fake_rpc)
    monkeypatch.setattr(worker, "_rest", fake_rest)
    monkeypatch.setattr(worker, "_expo_send", fail_send)

    result = asyncio.run(worker.process_batch(limit=10))
    assert result["retrying"] == 1
    assert patches[0]["state"] == "failed"
    assert patches[0]["last_error_code"] == "expo_network_error"
    assert patches[0]["next_attempt_at"] is not None


def test_worker_bounds_retry_delay():
    assert worker._retry_at(1)
    assert worker._retry_at(100)



def test_worker_suppresses_pending_push_when_current_preference_is_disabled(monkeypatch):
    delivery = {
        "id": "delivery-2", "notification_id": "notification-2", "user_id": "user-2",
        "device_id": "device-2", "lease_token": "lease-2", "attempt_count": 1,
        "max_attempts": 5, "state": "sending",
    }
    patches = []

    async def fake_rpc(name, payload):
        if name == "enqueue_notification_push_deliveries":
            return 0
        if name == "claim_notification_push_receipts":
            return []
        if name == "claim_notification_push_deliveries":
            return [delivery]
        raise AssertionError(name)

    async def fake_rest(method, table, *, params=None, body=None, prefer=None):
        if method == "GET" and table == "notifications":
            return [{"id": "notification-2", "user_id": "user-2", "title": "Title",
                     "body": "Body", "category": "social_activity", "delivery_state": "delivered",
                     "payload": {}, "expires_at": None}]
        if method == "GET" and table == "notification_devices":
            return [{"id": "device-2", "user_id": "user-2",
                     "expo_push_token": "ExponentPushToken[valid]", "enabled": True}]
        if method == "GET" and table == "user_settings":
            return [{"notification_preferences": {"push_enabled": False, "social_activity": True}}]
        if method == "PATCH" and table == "notification_push_deliveries":
            patches.append(body)
            return [{"id": "delivery-2"}]
        raise AssertionError((method, table))

    async def forbidden_send(*args, **kwargs):
        raise AssertionError("disabled push preferences must prevent provider dispatch")

    monkeypatch.setattr(worker, "_provider_enabled", lambda: True)
    monkeypatch.setattr(worker, "_rpc", fake_rpc)
    monkeypatch.setattr(worker, "_rest", fake_rest)
    monkeypatch.setattr(worker, "_expo_send", forbidden_send)

    result = asyncio.run(worker.process_batch(limit=5))
    assert result["claimed"] == 1
    assert result["sent"] == 0
    assert patches[0]["state"] == "suppressed"
    assert patches[0]["last_error_code"] == "notification_preference_disabled"


def test_worker_community_payload_contains_only_safe_route_identifiers():
    payload = {
        "type": "community_invite_accepted",
        "community_id": "community-1",
        "invitation_id": "invite-1",
        "private_note": "must not leave server",
    }
    result = worker._safe_push_data({"id": "notification-3", "payload": payload})
    assert result == {"notificationId": "notification-3", "type": "community_invite_accepted",
                      "communityId": "community-1"}

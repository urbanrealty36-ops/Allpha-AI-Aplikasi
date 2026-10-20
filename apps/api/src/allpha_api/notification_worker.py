"""ENG-P20 durable, lease-based notification push delivery worker.

The in-app inbox is written transactionally by the canonical database producer.
This worker only dispatches Expo Push Service notifications when explicitly enabled.
It never treats provider acceptance as device delivery; receipts are checked later.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

log = logging.getLogger("allpha.notification_worker")
DB_TIMEOUT = httpx.Timeout(6.0, connect=2.0)
PUSH_TIMEOUT = httpx.Timeout(8.0, connect=2.0)
EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
EXPO_RECEIPTS_URL = "https://exp.host/--/api/v2/push/getReceipts"
MAX_BATCH = 100
MAX_ATTEMPTS = 5


class NotificationWorkerConfigurationError(RuntimeError):
    """A required worker configuration is missing or invalid."""


class NotificationWorkerStorageError(RuntimeError):
    """The canonical notification store could not be safely updated."""


class ExpoPushError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


def _enabled() -> bool:
    value = os.getenv("ALLPHA_NOTIFICATION_WORKER_ENABLED", "false").strip().lower()
    if value not in {"true", "false"}:
        raise NotificationWorkerConfigurationError(
            "ALLPHA_NOTIFICATION_WORKER_ENABLED must be true or false"
        )
    return value == "true"


def _provider_enabled() -> bool:
    return (
        os.getenv("ALLPHA_NOTIFICATION_PUSH_ENABLED", "false").strip().lower() == "true"
        and os.getenv("ALLPHA_NOTIFICATION_PUSH_PROVIDER", "").strip().lower() == "expo"
    )


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise NotificationWorkerConfigurationError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise NotificationWorkerConfigurationError(
            f"{name} must be between {minimum} and {maximum}"
        )
    return value


def _db_config() -> tuple[str, str]:
    base = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_SECRET_KEY", "")
    if not base or not key:
        raise NotificationWorkerConfigurationError(
            "Supabase server credentials are required for notification delivery"
        )
    return base, key


async def _rest(
    method: str,
    table: str,
    *,
    params: dict[str, str] | None = None,
    body: Any = None,
    prefer: str | None = None,
) -> Any:
    base, key = _db_config()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    try:
        async with httpx.AsyncClient(timeout=DB_TIMEOUT) as client:
            response = await client.request(
                method, f"{base}/rest/v1/{table}", params=params, json=body, headers=headers
            )
    except httpx.HTTPError as exc:
        raise NotificationWorkerStorageError("notification_storage_unavailable") from exc
    if response.status_code >= 400:
        # Do not include provider credentials, SQL, or raw database responses in logs.
        raise NotificationWorkerStorageError(
            f"notification_storage_http_{response.status_code}"
        )
    return response.json() if response.content else []


async def _rpc(name: str, payload: dict[str, Any]) -> Any:
    return await _rest("POST", f"rpc/{name}", body=payload)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _retry_at(attempt_count: int) -> str:
    delay = min(30 * (2 ** max(0, attempt_count - 1)), 3600)
    return (_now() + timedelta(seconds=delay)).isoformat()


async def _expo_send(token: str, title: str, body: str, data: dict[str, Any]) -> dict[str, Any]:
    message = {
        "to": token,
        "title": title[:160],
        "body": body[:2000],
        "data": data,
        "sound": "default",
        "priority": "high",
        "channelId": "default",
    }
    try:
        async with httpx.AsyncClient(timeout=PUSH_TIMEOUT) as client:
            response = await client.post(EXPO_PUSH_URL, json=message, headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            })
    except httpx.HTTPError as exc:
        raise ExpoPushError("expo_network_error", retryable=True) from exc
    if response.status_code == 429 or response.status_code >= 500:
        raise ExpoPushError(f"expo_http_{response.status_code}", retryable=True)
    if response.status_code >= 400:
        raise ExpoPushError(f"expo_http_{response.status_code}", retryable=False)
    try:
        result = response.json()
    except ValueError as exc:
        raise ExpoPushError("expo_invalid_response", retryable=True) from exc
    item = result.get("data") if isinstance(result, dict) else None
    if isinstance(item, list):
        item = item[0] if item else None
    if not isinstance(item, dict):
        raise ExpoPushError("expo_ticket_missing", retryable=True)
    if item.get("status") == "ok" and isinstance(item.get("id"), str):
        return {"ticket_id": item["id"]}
    details = item.get("details") if isinstance(item.get("details"), dict) else {}
    code = str(details.get("error") or item.get("message") or "expo_ticket_error")[:80]
    retryable = code in {
        "MessageRateExceeded", "ExpoServerError", "InternalServerError",
        "ServiceUnavailable",
    }
    raise ExpoPushError(code, retryable=retryable)


async def _patch_delivery(delivery: dict[str, Any], fields: dict[str, Any]) -> bool:
    lease = delivery.get("lease_token")
    if not lease:
        return False
    rows = await _rest(
        "PATCH",
        "notification_push_deliveries",
        params={
            "id": f"eq.{delivery['id']}",
            "lease_token": f"eq.{lease}",
            "select": "id",
        },
        body={**fields, "lease_token": None, "lease_expires_at": None,
              "updated_at": _now().isoformat()},
        prefer="return=representation",
    )
    return bool(rows)


async def _disable_device(device_id: str, user_id: str) -> None:
    await _rest(
        "PATCH", "notification_devices",
        params={"id": f"eq.{device_id}", "user_id": f"eq.{user_id}"},
        body={"enabled": False, "updated_at": _now().isoformat()},
        prefer="return=minimal",
    )


async def _notification_and_device(delivery: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any]]:
    notifications = await _rest(
        "GET", "notifications",
        params={
            "select": "id,user_id,category,title,body,payload,delivery_state,expires_at",
            "id": f"eq.{delivery['notification_id']}",
            "user_id": f"eq.{delivery['user_id']}",
            "limit": "1",
        },
    )
    devices = await _rest(
        "GET", "notification_devices",
        params={
            "select": "id,user_id,expo_push_token,platform,enabled",
            "id": f"eq.{delivery['device_id']}",
            "user_id": f"eq.{delivery['user_id']}",
            "enabled": "eq.true",
            "limit": "1",
        },
    )
    settings = await _rest(
        "GET", "user_settings",
        params={
            "select": "notification_preferences",
            "user_id": f"eq.{delivery['user_id']}",
            "limit": "1",
        },
    )
    preferences = settings[0].get("notification_preferences", {}) if settings else {}
    return (notifications[0] if notifications else None,
            devices[0] if devices else None,
            preferences if isinstance(preferences, dict) else {})


def _safe_push_data(notification: dict[str, Any]) -> dict[str, Any]:
    payload = notification.get("payload")
    if not isinstance(payload, dict):
        return {"notificationId": str(notification["id"])}
    data: dict[str, Any] = {"notificationId": str(notification["id"])}
    if payload.get("type") == "message" and payload.get("conversation_id"):
        data["type"] = "message"
        data["conversationId"] = str(payload["conversation_id"])
        data["messageId"] = str(payload.get("message_id", ""))
    elif payload.get("type") == "community_invite_accepted" and payload.get("community_id"):
        data["type"] = "community_invite_accepted"
        data["communityId"] = str(payload["community_id"])
    return data


async def _process_receipts(limit: int) -> dict[str, int]:
    rows = await _rpc("claim_notification_push_receipts", {
        "p_limit": limit, "p_lease_seconds": 300,
    })
    if not isinstance(rows, list) or not rows:
        return {"checked": 0, "delivered": 0, "retrying": 0, "failed": 0}
    ticket_ids = [str(row["provider_ticket_id"]) for row in rows if row.get("provider_ticket_id")]
    if not ticket_ids:
        return {"checked": 0, "delivered": 0, "retrying": 0, "failed": 0}
    try:
        async with httpx.AsyncClient(timeout=PUSH_TIMEOUT) as client:
            response = await client.post(EXPO_RECEIPTS_URL, json={"ids": ticket_ids}, headers={
                "Accept": "application/json", "Content-Type": "application/json",
            })
        if response.status_code == 429 or response.status_code >= 500:
            raise ExpoPushError(f"expo_receipt_http_{response.status_code}", retryable=True)
        if response.status_code >= 400:
            raise ExpoPushError(f"expo_receipt_http_{response.status_code}", retryable=False)
        body = response.json()
        receipts = body.get("data", {}) if isinstance(body, dict) else {}
        if not isinstance(receipts, dict):
            raise ExpoPushError("expo_receipt_invalid_response", retryable=True)
    except (httpx.HTTPError, ValueError, ExpoPushError) as exc:
        log.warning("Notification receipt poll deferred: %s", type(exc).__name__)
        if isinstance(exc, ExpoPushError) and not exc.retryable:
            for row in rows:
                await _patch_delivery(row, {
                    "state": "failed", "last_error_code": exc.code,
                    "receipt_checked_at": _now().isoformat(),
                })
                # A permanent receipt endpoint error is not retried indefinitely.
        else:
            for row in rows:
                await _patch_delivery(row, {"lease_token": None, "lease_expires_at": None})
        return {"checked": 0, "delivered": 0, "retrying": 0, "failed": 0}

    counts = {"checked": 0, "delivered": 0, "retrying": 0, "failed": 0}
    by_ticket = {str(row["provider_ticket_id"]): row for row in rows if row.get("provider_ticket_id")}
    for ticket_id, receipt in receipts.items():
        delivery = by_ticket.get(str(ticket_id))
        if not delivery or not isinstance(receipt, dict):
            continue
        status = receipt.get("status")
        if status == "ok":
            updated = await _patch_delivery(delivery, {
                "state": "delivered", "receipt_checked_at": _now().isoformat(),
                "last_error_code": None,
            })
            if updated:
                counts["delivered"] += 1
        else:
            details = receipt.get("details") if isinstance(receipt.get("details"), dict) else {}
            code = str(details.get("error") or receipt.get("message") or "expo_receipt_error")[:80]
            if code == "DeviceNotRegistered":
                await _disable_device(str(delivery["device_id"]), str(delivery["user_id"]))
                state, next_at = "suppressed", None
                counts["failed"] += 1
            elif int(delivery.get("attempt_count") or 0) < int(delivery.get("max_attempts") or MAX_ATTEMPTS):
                state, next_at = "pending", _retry_at(int(delivery.get("attempt_count") or 1))
                counts["retrying"] += 1
            else:
                state, next_at = "failed", None
                counts["failed"] += 1
            updated = await _patch_delivery(delivery, {
                "state": state, "last_error_code": code,
                "next_attempt_at": next_at, "provider_ticket_id": None,
                "sent_at": None, "receipt_checked_at": _now().isoformat(),
            })
        counts["checked"] += 1
    # Expo may not have receipts ready for every ticket. Release leases without
    # changing the sent state so the next cron run can check them again.
    returned = {str(key) for key in receipts}
    for ticket_id, delivery in by_ticket.items():
        if ticket_id not in returned:
            await _patch_delivery(delivery, {"lease_token": None, "lease_expires_at": None})
    return counts


async def process_batch(*, limit: int = 25) -> dict[str, int]:
    if not 1 <= limit <= MAX_BATCH:
        raise ValueError(f"limit must be between 1 and {MAX_BATCH}")
    if not _provider_enabled():
        log.info("Notification push delivery is disabled or provider is not configured; no dispatch performed")
        return {"enqueued": 0, "claimed": 0, "sent": 0, "retrying": 0, "failed": 0, "receipts": 0}

    enqueued = await _rpc("enqueue_notification_push_deliveries", {"p_limit": limit * 4})
    enqueued_count = int(enqueued or 0) if not isinstance(enqueued, list) else len(enqueued)
    receipt_counts = await _process_receipts(min(limit * 2, 200))
    deliveries = await _rpc("claim_notification_push_deliveries", {
        "p_limit": limit, "p_lease_seconds": 300,
    })
    if not isinstance(deliveries, list):
        raise NotificationWorkerStorageError("notification_claim_response_invalid")
    counts = {"enqueued": enqueued_count, "claimed": len(deliveries), "sent": 0,
              "retrying": 0, "failed": 0, "receipts": receipt_counts["checked"]}
    for delivery in deliveries:
        try:
            notification, device, preferences = await _notification_and_device(delivery)
            if not notification or notification.get("delivery_state") != "delivered" or not device:
                await _patch_delivery(delivery, {
                    "state": "suppressed", "last_error_code": "notification_or_device_unavailable",
                })
                continue
            category = str(notification.get("category") or "social_activity")
            if preferences.get("push_enabled") is False or preferences.get(category) is False:
                await _patch_delivery(delivery, {
                    "state": "suppressed", "last_error_code": "notification_preference_disabled",
                })
                continue
            expires_at = notification.get("expires_at")
            if expires_at:
                try:
                    if datetime.fromisoformat(str(expires_at).replace("Z", "+00:00")) <= _now():
                        await _patch_delivery(delivery, {
                            "state": "suppressed", "last_error_code": "notification_expired",
                        })
                        continue
                except ValueError:
                    await _patch_delivery(delivery, {
                        "state": "suppressed", "last_error_code": "notification_expiry_invalid",
                    })
                    continue
            try:
                ticket = await _expo_send(
                    str(device["expo_push_token"]),
                    str(notification["title"]),
                    str(notification.get("body") or ""),
                    _safe_push_data(notification),
                )
                updated = await _patch_delivery(delivery, {
                    "state": "sent", "provider_ticket_id": ticket["ticket_id"],
                    "sent_at": _now().isoformat(), "receipt_checked_at": None,
                    "last_error_code": None, "next_attempt_at": _now().isoformat(),
                })
                if updated:
                    counts["sent"] += 1
            except ExpoPushError as exc:
                if exc.code == "DeviceNotRegistered":
                    await _disable_device(str(device["id"]), str(device["user_id"]))
                    state, next_at = "suppressed", None
                    counts["failed"] += 1
                elif exc.retryable and int(delivery.get("attempt_count") or 0) < int(delivery.get("max_attempts") or MAX_ATTEMPTS):
                    state, next_at = "failed", _retry_at(int(delivery.get("attempt_count") or 1))
                    counts["retrying"] += 1
                else:
                    state, next_at = "failed", None
                    counts["failed"] += 1
                await _patch_delivery(delivery, {
                    "state": state, "last_error_code": exc.code,
                    "next_attempt_at": next_at,
                })
        except Exception:
            log.exception("Notification push delivery item failed; lease expiry enables recovery")
    log.info("Notification delivery batch: %s", counts)
    return counts


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    try:
        if not _enabled():
            log.info("Notification worker disabled; set ALLPHA_NOTIFICATION_WORKER_ENABLED=true to enable")
            return
        if not _provider_enabled():
            log.info("Notification worker enabled but push provider is not configured; no dispatch performed")
            return
        _db_config()
        limit = _bounded_int("ALLPHA_NOTIFICATION_BATCH_LIMIT", 8, 1, 8)
    except NotificationWorkerConfigurationError as exc:
        raise SystemExit(str(exc)) from exc
    summary = asyncio.run(process_batch(limit=limit))
    log.info("Notification worker invocation completed: %s", summary)


if __name__ == "__main__":
    main()

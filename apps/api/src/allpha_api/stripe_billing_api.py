"""Stripe Checkout, webhook fulfillment, subscription and entitlement API.

Stripe is the sole payment provider. All prices and Stripe Price IDs are read
from the operator-managed billing_products registry; clients submit product keys
only. Payment fulfillment is webhook-only and transactionally coupled to the
canonical AI Credit Ledger and playback entitlement tables.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from allpha_api.operator_security import require_operator_scope, write_operator_audit

from allpha_api.auth import current_user

router = APIRouter(prefix="/v1/billing", tags=["billing"])
_DB_TIMEOUT = httpx.Timeout(10.0, connect=3.0)
_STRIPE_TIMEOUT = httpx.Timeout(20.0, connect=5.0)
_ALLOWED_WEBHOOK_EVENTS = {
    "checkout.session.completed",
    "checkout.session.async_payment_succeeded",
    "checkout.session.async_payment_failed",
    "checkout.session.expired",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.paid",
    "invoice.payment_failed",
}


class CheckoutCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_key: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9._-]{1,79}$")


def _billing_config(*, webhook: bool = False) -> tuple[str, str | None]:
    if os.getenv("ALLPHA_STRIPE_ENABLED", "false").strip().lower() != "true":
        raise HTTPException(503, detail={"code": "STRIPE_BILLING_DISABLED", "message": "Pembayaran Allpha belum diaktifkan."})
    key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    signing = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
    mode = os.getenv("ALLPHA_STRIPE_MODE", "test").strip().lower()
    if mode not in {"test", "live"} or not key or not signing:
        raise HTTPException(503, detail={"code": "STRIPE_NOT_CONFIGURED", "message": "Konfigurasi Stripe belum lengkap."})
    if mode == "live" and not key.startswith("sk_live_"):
        raise HTTPException(503, detail={"code": "STRIPE_MODE_MISMATCH", "message": "Kunci Stripe tidak sesuai mode live."})
    if mode == "test" and not key.startswith("sk_test_"):
        raise HTTPException(503, detail={"code": "STRIPE_MODE_MISMATCH", "message": "Kunci Stripe tidak sesuai mode test."})
    return key, signing if webhook else None





def _policy_is_current(policy: dict[str, Any]) -> bool:
    now = datetime.now(timezone.utc)
    effective = policy.get("effective_at")
    expires = policy.get("expires_at")
    try:
        if isinstance(effective, str) and effective:
            effective_at = datetime.fromisoformat(effective.replace("Z", "+00:00"))
            if effective_at.tzinfo is None:
                effective_at = effective_at.replace(tzinfo=timezone.utc)
            if effective_at > now:
                return False
        if isinstance(expires, str) and expires:
            expires_at = datetime.fromisoformat(expires.replace("Z", "+00:00"))
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= now:
                return False
    except ValueError:
        return False
    return True


def _checkout_ready() -> bool:
    try:
        _billing_config()
        return True
    except HTTPException:
        return False


def _stripe_admin_key() -> str:
    key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    mode = os.getenv("ALLPHA_STRIPE_MODE", "test").strip().lower()
    if mode not in {"test", "live"} or not key:
        raise HTTPException(503, detail={"code": "STRIPE_ADMIN_NOT_CONFIGURED", "message": "Kunci Stripe untuk verifikasi produk belum dikonfigurasi."})
    if (mode == "live" and not key.startswith("sk_live_")) or (mode == "test" and not key.startswith("sk_test_")):
        raise HTTPException(503, detail={"code": "STRIPE_MODE_MISMATCH", "message": "Kunci Stripe tidak sesuai mode konfigurasi."})
    return key


def _db_config() -> tuple[str, str]:
    base = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_SECRET_KEY", "")
    if not base or not key:
        raise HTTPException(503, detail={"code": "BILLING_DATABASE_NOT_CONFIGURED", "message": "Layanan billing belum terhubung ke database."})
    return base, key


async def _db(method: str, path: str, *, params: dict[str, str] | None = None,
              body: Any = None, prefer: str | None = None) -> Any:
    base, key = _db_config()
    headers = {"apikey": key, "Content-Type": "application/json", "Accept": "application/json"}
    if os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip():
        headers["Authorization"] = f"Bearer {os.getenv('SUPABASE_SERVICE_ROLE_KEY', '').strip()}"
    if prefer:
        headers["Prefer"] = prefer
    try:
        async with httpx.AsyncClient(timeout=_DB_TIMEOUT) as client:
            response = await client.request(method, f"{base}/rest/v1/{path}", params=params, json=body, headers=headers)
    except httpx.HTTPError as exc:
        raise HTTPException(503, detail={"code": "BILLING_DATABASE_UNAVAILABLE", "message": "Database billing sementara tidak tersedia."}) from exc
    if response.status_code >= 400:
        raise HTTPException(503 if response.status_code >= 500 or response.status_code == 404 else 409,
                            detail={"code": "BILLING_DATABASE_OPERATION_FAILED", "message": "Operasi billing tidak dapat dikonfirmasi."})
    if not response.content:
        return []
    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(503, detail={"code": "BILLING_DATABASE_RESPONSE_INVALID", "message": "Respons database billing tidak valid."}) from exc


async def _rpc(name: str, payload: dict[str, Any]) -> Any:
    return await _db("POST", f"rpc/{name}", body=payload)


def _checkout_urls() -> tuple[str, str]:
    success = os.getenv("ALLPHA_BILLING_SUCCESS_URL", "https://allpha.web.id/billing/success?session_id={CHECKOUT_SESSION_ID}").strip()
    cancel = os.getenv("ALLPHA_BILLING_CANCEL_URL", "https://allpha.web.id/billing").strip()
    allowed = {x.strip().lower() for x in os.getenv("ALLPHA_BILLING_ALLOWED_HOSTS", "allpha.web.id,www.allpha.web.id").split(",") if x.strip()}
    for value in (success, cancel):
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.hostname.lower() not in allowed:
            raise HTTPException(503, detail={"code": "BILLING_RETURN_URL_INVALID", "message": "URL kembali pembayaran belum diizinkan."})
    return success, cancel


async def _stripe_request(method: str, path: str, *, key: str, data: dict[str, str] | None = None,
                          idempotency_key: str | None = None) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    api_version = os.getenv("ALLPHA_STRIPE_API_VERSION", "").strip()
    if api_version:
        headers["Stripe-Version"] = api_version
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    try:
        async with httpx.AsyncClient(timeout=_STRIPE_TIMEOUT, auth=(key, "")) as client:
            response = await client.request(method, f"https://api.stripe.com/v1/{path}", data=data, headers=headers)
    except httpx.HTTPError as exc:
        # Stripe may have accepted the request. Keep the local order pending and
        # retry only with the same Stripe idempotency key after reconciliation.
        raise HTTPException(503, detail={"code": "STRIPE_OUTCOME_UNKNOWN", "message": "Status permintaan Stripe belum dapat dipastikan; jangan membuat pesanan baru."}) from exc
    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(503, detail={"code": "STRIPE_RESPONSE_INVALID", "message": "Respons Stripe tidak dapat dibaca."}) from exc
    if response.status_code >= 400:
        code = ((payload.get("error") or {}).get("code") if isinstance(payload, dict) else None) or "stripe_request_failed"
        raise HTTPException(502, detail={"code": "STRIPE_REQUEST_REJECTED", "message": f"Stripe menolak permintaan ({str(code)[:60]})."})
    if not isinstance(payload, dict):
        raise HTTPException(502, detail={"code": "STRIPE_RESPONSE_INVALID", "message": "Respons Stripe tidak valid."})
    return payload


def _verify_signature(raw: bytes, signature_header: str, secret: str) -> None:
    timestamp: int | None = None
    signatures: list[str] = []
    for part in signature_header.split(","):
        key, sep, value = part.strip().partition("=")
        if not sep:
            continue
        if key == "t":
            try:
                timestamp = int(value)
            except ValueError:
                timestamp = None
        elif key == "v1":
            signatures.append(value)
    if timestamp is None or not signatures or abs(int(time.time()) - timestamp) > 300:
        raise HTTPException(400, detail={"code": "STRIPE_SIGNATURE_INVALID", "message": "Signature webhook Stripe tidak valid atau kedaluwarsa."})
    signed = str(timestamp).encode() + b"." + raw
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, candidate) for candidate in signatures):
        raise HTTPException(400, detail={"code": "STRIPE_SIGNATURE_INVALID", "message": "Signature webhook Stripe tidak valid."})


def _safe_event_object(value: Any) -> dict[str, Any]:
    """Persist only fulfillment-relevant Stripe fields; never card/payment-method data."""
    if not isinstance(value, dict):
        return {}
    allowed = {
        "id", "object", "mode", "status", "payment_status", "amount_total", "amount_paid",
        "amount_due", "currency", "payment_intent", "subscription", "customer", "invoice",
        "metadata", "current_period_start", "current_period_end", "cancel_at_period_end",
        "cancel_at", "ended_at", "latest_invoice", "collection_method", "livemode", "hosted_invoice_url",
    }
    result = {key: value.get(key) for key in allowed if key in value}
    if "subscription" not in result:
        subscription_id = _event_subscription_id(value)
        if subscription_id:
            result["subscription"] = subscription_id
    metadata = result.get("metadata")
    if isinstance(metadata, dict):
        result["metadata"] = {str(k): str(v)[:200] for k, v in metadata.items() if k in {"order_id", "owner_user_id", "product_key", "plan_key"}}
    return result


def _event_subscription_id(obj: dict[str, Any]) -> str | None:
    value = obj.get("subscription")
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("id")
    parent = obj.get("parent")
    if isinstance(parent, dict):
        details = parent.get("subscription_details")
        if isinstance(details, dict) and isinstance(details.get("subscription"), str):
            return details["subscription"]
    return None



class BillingProductDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_key: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9._-]{1,79}$")
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    purpose: str
    product_approval_reference: str = Field(min_length=3, max_length=160)
    stripe_price_id: str = Field(pattern=r"^price_[A-Za-z0-9]+$")
    stripe_mode: str
    amount_minor: int = Field(gt=0, le=100_000_000_000)
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[a-z]{3}$")
    billing_interval: str | None = None
    credits_grant: int = Field(default=0, ge=0, le=10_000_000_000)
    monthly_credits_grant: int = Field(default=0, ge=0, le=10_000_000_000)
    credit_policy_version: str | None = Field(default=None, max_length=80)
    credit_policy_approval_reference: str | None = Field(default=None, max_length=160)
    plan_key: str | None = Field(default=None, max_length=80)
    entitlement_version: str | None = Field(default=None, max_length=80)
    sort_order: int = Field(default=100, ge=0, le=100_000)


def _validate_product_shape(payload: BillingProductDraft) -> None:
    if payload.purpose == "ai_credit_topup":
        if payload.stripe_mode != "payment" or payload.credits_grant <= 0 or payload.monthly_credits_grant != 0 or not payload.credit_policy_version or not payload.credit_policy_approval_reference or payload.plan_key:
            raise HTTPException(422, detail={"code": "BILLING_TOPUP_POLICY_INVALID", "message": "Paket top-up memerlukan grant AI Credits dan referensi kebijakan yang disetujui."})
    elif payload.purpose == "premium_subscription":
        if payload.stripe_mode != "subscription" or payload.credits_grant != 0 or payload.monthly_credits_grant <= 0 or not payload.credit_policy_version or not payload.credit_policy_approval_reference or not payload.plan_key or not payload.entitlement_version or not payload.billing_interval:
            raise HTTPException(422, detail={"code": "BILLING_SUBSCRIPTION_POLICY_INVALID", "message": "Paket Premium memerlukan plan, entitlement, allowance bulanan, dan referensi persetujuan."})
    else:
        raise HTTPException(422, detail={"code": "BILLING_PURPOSE_INVALID", "message": "Tujuan produk billing tidak dikenal."})
    if payload.billing_interval not in {None, "day", "week", "month", "year"}:
        raise HTTPException(422, detail={"code": "BILLING_INTERVAL_INVALID", "message": "Interval billing tidak valid."})


@router.get("/admin/products")
async def admin_billing_products(operator: dict[str, Any] = Depends(require_operator_scope("platform:billing.manage"))) -> dict[str, Any]:
    rows = await _db("GET", "billing_products", params={
        "select": "id,product_key,name,description,purpose,product_approval_reference,stripe_price_id,stripe_mode,amount_minor,currency,billing_interval,credits_grant,monthly_credits_grant,credit_policy_version,credit_policy_approval_reference,plan_key,entitlement_version,status,sort_order,created_at,updated_at",
        "order": "sort_order.asc,product_key.asc", "limit": "200",
    })
    return {"items": rows or []}


@router.post("/admin/products", status_code=201)
async def create_billing_product(payload: BillingProductDraft, request: Request,
                                 operator: dict[str, Any] = Depends(require_operator_scope("platform:billing.manage"))) -> dict[str, Any]:
    _validate_product_shape(payload)
    await write_operator_audit(request, actor_user_id=operator["id"], action="billing.product.create",
        outcome="attempted", resource_type="billing_product", resource_id=payload.product_key,
        metadata={"purpose": payload.purpose, "stripe_price_id": payload.stripe_price_id, "product_approval_reference": payload.product_approval_reference, "credit_policy_approval_reference": payload.credit_policy_approval_reference, "status": "draft"})
    rows = await _db("POST", "billing_products", params={"select": "id,product_key,status"},
        body={**payload.model_dump(), "status": "draft"}, prefer="return=representation")
    if not rows:
        raise HTTPException(503, detail={"code": "BILLING_PRODUCT_CREATE_FAILED", "message": "Draft produk billing tidak dapat disimpan."})
    await write_operator_audit(request, actor_user_id=operator["id"], action="billing.product.create",
        outcome="allowed", resource_type="billing_product", resource_id=payload.product_key,
        metadata={"product_id": rows[0]["id"], "status": "draft"})
    return {"product": rows[0]}


@router.post("/admin/products/{product_key}/activate")
async def activate_billing_product(product_key: str, request: Request,
                                   operator: dict[str, Any] = Depends(require_operator_scope("platform:billing.manage"))) -> dict[str, Any]:
    key = _stripe_admin_key()
    rows = await _db("GET", "billing_products", params={
        "select": "id,product_key,purpose,product_approval_reference,stripe_price_id,stripe_mode,amount_minor,currency,billing_interval,credits_grant,monthly_credits_grant,credit_policy_version,credit_policy_approval_reference,plan_key,entitlement_version,status",
        "product_key": f"eq.{product_key}", "limit": "1",
    })
    if not rows:
        raise HTTPException(404, detail={"code": "BILLING_PRODUCT_NOT_FOUND", "message": "Draft produk billing tidak ditemukan."})
    product = rows[0]
    if product["status"] != "draft":
        raise HTTPException(409, detail={"code": "BILLING_PRODUCT_NOT_DRAFT", "message": "Hanya produk draft yang dapat diaktifkan."})
    price = await _stripe_request("GET", f"prices/{product['stripe_price_id']}", key=key)
    recurring = price.get("recurring") if isinstance(price.get("recurring"), dict) else None
    if price.get("active") is not True or int(price.get("unit_amount") or 0) != int(product["amount_minor"]) or str(price.get("currency") or "").lower() != product["currency"]:
        raise HTTPException(409, detail={"code": "STRIPE_PRICE_MISMATCH", "message": "Stripe Price harus aktif dan jumlah serta mata uangnya harus sama dengan snapshot produk."})
    if product["stripe_mode"] == "subscription":
        if not recurring or recurring.get("interval") != product.get("billing_interval"):
            raise HTTPException(409, detail={"code": "STRIPE_RECURRING_PRICE_MISMATCH", "message": "Stripe Price recurring interval tidak cocok dengan paket Premium."})
    elif recurring:
        raise HTTPException(409, detail={"code": "STRIPE_ONE_TIME_PRICE_MISMATCH", "message": "Top-up AI Credits hanya boleh memakai Stripe Price sekali bayar."})
    policies = await _db("GET", "credit_policy_versions", params={
        "select": "policy_version,approval_reference,status,configuration,effective_at,expires_at",
        "policy_version": f"eq.{product['credit_policy_version']}", "limit": "1",
    })
    if not policies:
        raise HTTPException(409, detail={"code": "CREDIT_GRANT_POLICY_MISSING", "message": "Kebijakan AI Credit tidak ditemukan."})
    policy = policies[0]
    config = policy.get("configuration") if isinstance(policy.get("configuration"), dict) else {}
    allowed_types = config.get("allowed_grant_types") if isinstance(config.get("allowed_grant_types"), list) else []
    required_grant = int(product["credits_grant"] if product["purpose"] == "ai_credit_topup" else product["monthly_credits_grant"])
    if (policy.get("status") != "approved" or not _policy_is_current(policy) or policy.get("approval_reference") != product.get("credit_policy_approval_reference")
        or config.get("allow_grants") is not True or "grant" not in allowed_types
        or int(config.get("max_grant_credits") or 0) < required_grant):
        raise HTTPException(409, detail={"code": "CREDIT_GRANT_POLICY_NOT_APPROVED", "message": "Kebijakan kredit tidak mengizinkan grant paket atau allowance ini."})
    if product["purpose"] == "premium_subscription":
        entitlements = config.get("entitlements") if isinstance(config.get("entitlements"), dict) else {}
        if not isinstance(entitlements.get(product.get("entitlement_version")), dict):
            raise HTTPException(409, detail={"code": "PREMIUM_ENTITLEMENT_POLICY_MISSING", "message": "Versi entitlement Premium belum tercantum dalam kebijakan kredit yang disetujui."})
    await write_operator_audit(request, actor_user_id=operator["id"], action="billing.product.activate",
        outcome="attempted", resource_type="billing_product", resource_id=product_key,
        metadata={"stripe_price_id": product["stripe_price_id"], "amount_minor": product["amount_minor"], "currency": product["currency"], "product_approval_reference": product["product_approval_reference"], "credit_policy_approval_reference": product["credit_policy_approval_reference"]})
    updated = await _db("PATCH", "billing_products", params={
        "id": f"eq.{product['id']}", "status": "eq.draft", "select": "id,product_key,status",
    }, body={"status": "active", "updated_at": datetime.now(timezone.utc).isoformat()}, prefer="return=representation")
    if not updated:
        raise HTTPException(409, detail={"code": "BILLING_PRODUCT_ACTIVATION_CONFLICT", "message": "Produk berubah saat aktivasi; coba muat ulang."})
    await write_operator_audit(request, actor_user_id=operator["id"], action="billing.product.activate",
        outcome="allowed", resource_type="billing_product", resource_id=product_key,
        metadata={"product_id": product["id"], "stripe_price_verified": True})
    return {"product": updated[0], "stripe_price_verified": True}


@router.post("/admin/products/{product_key}/retire")
async def retire_billing_product(product_key: str, request: Request,
                                 operator: dict[str, Any] = Depends(require_operator_scope("platform:billing.manage"))) -> dict[str, Any]:
    rows = await _db("PATCH", "billing_products", params={
        "product_key": f"eq.{product_key}", "status": "in.(active,draft)", "select": "id,product_key,status",
    }, body={"status": "retired", "updated_at": datetime.now(timezone.utc).isoformat()}, prefer="return=representation")
    if not rows:
        raise HTTPException(404, detail={"code": "BILLING_PRODUCT_NOT_FOUND", "message": "Produk billing aktif tidak ditemukan."})
    await write_operator_audit(request, actor_user_id=operator["id"], action="billing.product.retire",
        outcome="allowed", resource_type="billing_product", resource_id=product_key,
        metadata={"product_id": rows[0]["id"]})
    return {"product": rows[0]}


@router.get("/catalog")
async def billing_catalog(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    rows = await _db("GET", "billing_products", params={
        "select": "product_key,name,description,purpose,amount_minor,currency,billing_interval,credits_grant,monthly_credits_grant,plan_key",
        "status": "eq.active", "order": "sort_order.asc,product_key.asc", "limit": "100",
    })
    return {"items": rows or [], "provider": "stripe", "checkout_enabled": _checkout_ready()}


@router.post("/checkout", status_code=201)
async def create_checkout(payload: CheckoutCreate, request: Request,
                          idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                          user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    key, _ = _billing_config()
    if not idempotency_key or not 8 <= len(idempotency_key) <= 160:
        raise HTTPException(400, detail={"code": "IDEMPOTENCY_KEY_REQUIRED", "message": "Idempotency-Key 8–160 karakter wajib dikirim."})
    products = await _db("GET", "billing_products", params={
        "select": "id,product_key,name,description,purpose,product_approval_reference,stripe_price_id,stripe_mode,amount_minor,currency,credits_grant,monthly_credits_grant,credit_policy_version,credit_policy_approval_reference,plan_key,entitlement_version,status",
        "product_key": f"eq.{payload.product_key}", "status": "eq.active", "limit": "1",
    })
    if not products:
        raise HTTPException(404, detail={"code": "BILLING_PRODUCT_UNAVAILABLE", "message": "Produk atau paket belum tersedia."})
    product = products[0]
    if not product.get("stripe_price_id") or product.get("stripe_mode") not in {"payment", "subscription"}:
        raise HTTPException(503, detail={"code": "BILLING_PRODUCT_NOT_CONFIGURED", "message": "Produk belum memiliki konfigurasi Stripe yang valid."})
    if int(product.get("amount_minor") or 0) <= 0 or not product.get("currency"):
        raise HTTPException(503, detail={"code": "BILLING_PRICE_NOT_APPROVED", "message": "Harga produk belum disetujui dan dikonfigurasi."})
    if product.get("purpose") == "ai_credit_topup" and int(product.get("credits_grant") or 0) <= 0:
        raise HTTPException(503, detail={"code": "CREDIT_GRANT_POLICY_UNAVAILABLE", "message": "Paket AI Credits belum memiliki kebijakan grant yang disetujui."})
    if product.get("purpose") == "premium_subscription" and (
        int(product.get("monthly_credits_grant") or 0) <= 0 or not product.get("credit_policy_version")
        or not product.get("credit_policy_approval_reference")
    ):
        raise HTTPException(503, detail={"code": "PREMIUM_ALLOWANCE_POLICY_UNAVAILABLE", "message": "Allowance bulanan Premium belum memiliki kebijakan kredit yang disetujui."})
    if product.get("purpose") == "premium_subscription" and (not product.get("plan_key") or not product.get("entitlement_version")):
        raise HTTPException(503, detail={"code": "SUBSCRIPTION_POLICY_UNAVAILABLE", "message": "Paket Premium belum memiliki kebijakan entitlement."})
    policy_rows = await _db("GET", "credit_policy_versions", params={
        "select": "policy_version,approval_reference,status,configuration,effective_at,expires_at",
        "policy_version": f"eq.{product.get('credit_policy_version')}", "limit": "1",
    })
    if not policy_rows:
        raise HTTPException(503, detail={"code": "BILLING_CREDIT_POLICY_UNAVAILABLE", "message": "Kebijakan AI Credit produk tidak tersedia."})
    policy = policy_rows[0]
    config = policy.get("configuration") if isinstance(policy.get("configuration"), dict) else {}
    allowed_grants = config.get("allowed_grant_types") if isinstance(config.get("allowed_grant_types"), list) else []
    grant_amount = int(product.get("credits_grant") or 0) if product.get("purpose") == "ai_credit_topup" else int(product.get("monthly_credits_grant") or 0)
    if (policy.get("status") != "approved" or not _policy_is_current(policy) or policy.get("approval_reference") != product.get("credit_policy_approval_reference")
        or config.get("allow_grants") is not True or "grant" not in allowed_grants
        or int(config.get("max_grant_credits") or 0) < grant_amount):
        raise HTTPException(503, detail={"code": "BILLING_CREDIT_POLICY_NOT_APPROVED", "message": "Kebijakan grant AI Credit produk tidak lagi aktif atau tidak mencakup jumlah ini."})
    if product.get("purpose") == "premium_subscription":
        entitlement_rules = config.get("entitlements") if isinstance(config.get("entitlements"), dict) else {}
        if not isinstance(entitlement_rules.get(product.get("entitlement_version")), dict):
            raise HTTPException(503, detail={"code": "SUBSCRIPTION_ENTITLEMENT_POLICY_UNAVAILABLE", "message": "Versi entitlement Premium tidak tersedia dalam policy aktif."})

    created = await _rpc("billing_create_order", {
        "p_owner_user_id": str(user["id"]), "p_product_key": payload.product_key,
        "p_idempotency_key": idempotency_key,
    })
    if not isinstance(created, dict) or not created.get("order_id"):
        raise HTTPException(503, detail={"code": "BILLING_ORDER_NOT_CONFIRMED", "message": "Pesanan belum dapat disimpan secara permanen."})
    order_id = str(created["order_id"])
    if created.get("stripe_checkout_session_id") and created.get("checkout_url"):
        if created.get("status") == "checkout_pending":
            return {"order_id": order_id, "checkout_url": created["checkout_url"], "status": "checkout_pending"}
        return {"order_id": order_id, "status": created.get("status"), "checkout_url": None}

    success_url, cancel_url = _checkout_urls()
    mode = str(product["stripe_mode"])
    form = {
        "mode": mode,
        "line_items[0][price]": str(product["stripe_price_id"]),
        "line_items[0][quantity]": "1",
        "client_reference_id": order_id,
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata[order_id]": order_id,
        "metadata[owner_user_id]": str(user["id"]),
        "metadata[product_key]": payload.product_key,
    }
    if mode == "subscription":
        form["subscription_data[metadata][order_id]"] = order_id
        form["subscription_data[metadata][owner_user_id]"] = str(user["id"])
        form["subscription_data[metadata][product_key]"] = payload.product_key
    else:
        form["payment_intent_data[metadata][order_id]"] = order_id
        form["payment_intent_data[metadata][owner_user_id]"] = str(user["id"])
    if user.get("email"):
        form["customer_email"] = str(user["email"])[:320]
    session = await _stripe_request("POST", "checkout/sessions", key=key, data=form,
                                    idempotency_key=f"allpha-checkout:{order_id}")
    if not session.get("id") or not session.get("url"):
        raise HTTPException(502, detail={"code": "STRIPE_CHECKOUT_SESSION_INVALID", "message": "Stripe tidak mengembalikan sesi checkout yang valid."})
    attached = await _rpc("billing_attach_checkout_session", {
        "p_order_id": order_id, "p_owner_user_id": str(user["id"]),
        "p_session_id": str(session["id"]), "p_checkout_url": str(session["url"]),
        "p_stripe_customer_id": session.get("customer"),
    })
    if not isinstance(attached, dict) or not attached.get("attached"):
        raise HTTPException(503, detail={"code": "BILLING_CHECKOUT_ATTACH_UNCONFIRMED", "message": "Sesi Stripe dibuat tetapi belum terikat ke pesanan; status perlu rekonsiliasi."})
    return {"order_id": order_id, "checkout_url": session["url"], "status": "checkout_pending", "provider": "stripe"}



@router.get("/orders")
async def list_billing_orders(limit: int = 10, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    bounded = min(max(1, limit), 50)
    rows = await _db("GET", "billing_orders", params={
        "select": "id,product_key,product_name,purpose,amount_minor,currency,status,created_at,paid_at",
        "owner_user_id": f"eq.{user['id']}", "order": "created_at.desc", "limit": str(bounded),
    })
    return {"items": rows or [], "limit": bounded}


@router.get("/orders/{order_id}")
async def get_billing_order(order_id: uuid.UUID, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    rows = await _db("GET", "billing_orders", params={
        "select": "id,product_key,product_name,purpose,amount_minor,currency,status,created_at,paid_at",
        "id": f"eq.{order_id}", "owner_user_id": f"eq.{user['id']}", "limit": "1",
    })
    if not rows:
        raise HTTPException(404, detail={"code": "BILLING_ORDER_NOT_FOUND", "message": "Pesanan tidak ditemukan."})
    receipts = await _db("GET", "billing_receipts", params={
        "select": "receipt_number,amount_minor,currency,paid_at,hosted_invoice_url",
        "order_id": f"eq.{order_id}", "owner_user_id": f"eq.{user['id']}", "limit": "5",
    })
    return {"order": rows[0], "receipts": receipts or []}



@router.post("/portal")
async def create_customer_portal(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    key, _ = _billing_config()
    subscriptions = await _db("GET", "billing_subscriptions", params={
        "select": "stripe_customer_id,status",
        "owner_user_id": f"eq.{user['id']}",
        "status": "in.(active,past_due,unpaid)",
        "order": "updated_at.desc", "limit": "1",
    })
    if not subscriptions or not subscriptions[0].get("stripe_customer_id"):
        raise HTTPException(404, detail={"code": "STRIPE_CUSTOMER_NOT_FOUND", "message": "Akun ini belum memiliki customer subscription Stripe."})
    _, return_url = _checkout_urls()
    portal = await _stripe_request("POST", "billing_portal/sessions", key=key, data={
        "customer": str(subscriptions[0]["stripe_customer_id"]),
        "return_url": return_url,
    }, idempotency_key=None)
    if not portal.get("url"):
        raise HTTPException(502, detail={"code": "STRIPE_PORTAL_SESSION_INVALID", "message": "Stripe tidak mengembalikan portal URL."})
    return {"url": portal["url"], "provider": "stripe"}


@router.get("/subscription")
async def get_my_subscription(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    rows = await _db("GET", "billing_subscriptions", params={
        "select": "id,plan_key,status,current_period_start,current_period_end,cancel_at_period_end,created_at,updated_at",
        "owner_user_id": f"eq.{user['id']}", "status": "in.(active,past_due,canceled,unpaid,incomplete,paused)",
        "order": "updated_at.desc", "limit": "1",
    })
    entitlements = await _db("GET", "playback_entitlements", params={
        "select": "entitlement_key,status,valid_from,valid_until,source_subscription_id",
        "owner_user_id": f"eq.{user['id']}", "order": "updated_at.desc", "limit": "20",
    })
    return {"subscription": rows[0] if rows else None, "entitlements": entitlements or []}


@router.post("/stripe/webhook", include_in_schema=True)
async def stripe_webhook(request: Request, stripe_signature: str | None = Header(default=None, alias="Stripe-Signature")) -> dict[str, Any]:
    stripe_key, secret = _billing_config(webhook=True)
    raw = await request.body()
    if not stripe_signature or not secret:
        raise HTTPException(400, detail={"code": "STRIPE_SIGNATURE_REQUIRED", "message": "Stripe-Signature wajib dikirim."})
    _verify_signature(raw, stripe_signature, secret)
    try:
        event = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(400, detail={"code": "STRIPE_EVENT_INVALID", "message": "Payload webhook bukan JSON valid."}) from exc
    if not isinstance(event, dict) or not isinstance(event.get("id"), str) or not isinstance(event.get("type"), str):
        raise HTTPException(400, detail={"code": "STRIPE_EVENT_INVALID", "message": "Identitas event Stripe tidak valid."})
    event_id, event_type = event["id"], event["type"]
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    obj = _safe_event_object(data.get("object"))
    received = await _rpc("billing_receive_stripe_event", {
        "p_event_id": event_id, "p_event_type": event_type,
        "p_event_created_at": datetime.fromtimestamp(int(event.get("created") or time.time()), tz=timezone.utc).isoformat(),
        "p_payload": obj,
    })
    if not isinstance(received, dict):
        raise HTTPException(503, detail={"code": "STRIPE_EVENT_RECEIPT_UNCONFIRMED", "message": "Penerimaan event Stripe belum tersimpan."})
    if received.get("duplicate") and received.get("status") == "processed":
        return {"received": True, "duplicate": True, "processed": True}

    try:
        if event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
            if obj.get("payment_status") != "paid":
                await _rpc("billing_mark_stripe_event", {"p_event_id": event_id, "p_status": "awaiting_payment", "p_error_code": None})
                return {"received": True, "processed": False, "status": "awaiting_payment"}
            metadata = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
            order_id = metadata.get("order_id")
            if not order_id:
                raise ValueError("checkout_order_metadata_missing")
            subscription_id = obj.get("subscription") if isinstance(obj.get("subscription"), str) else None
            subscription_snapshot: dict[str, Any] = {}
            if subscription_id:
                subscription_snapshot = await _stripe_request("GET", f"subscriptions/{subscription_id}", key=stripe_key)
                if subscription_snapshot.get("status") != "active":
                    raise ValueError("stripe_subscription_not_active_after_checkout")
                if not subscription_snapshot.get("current_period_start") or not subscription_snapshot.get("current_period_end"):
                    raise ValueError("stripe_subscription_period_missing")
                if obj.get("customer") and subscription_snapshot.get("customer") != obj.get("customer"):
                    raise ValueError("stripe_subscription_customer_mismatch")
            await _rpc("billing_finalize_stripe_checkout", {
                "p_event_id": event_id, "p_order_id": str(order_id),
                "p_session_id": str(obj.get("id") or ""),
                "p_owner_user_id": str(metadata.get("owner_user_id") or ""),
                "p_payment_status": str(obj.get("payment_status") or ""),
                "p_amount_total": int(obj.get("amount_total") or 0),
                "p_currency": str(obj.get("currency") or "").lower(),
                "p_payment_intent_id": obj.get("payment_intent") if isinstance(obj.get("payment_intent"), str) else None,
                "p_subscription_id": subscription_id,
                "p_customer_id": obj.get("customer") if isinstance(obj.get("customer"), str) else None,
                "p_current_period_start": datetime.fromtimestamp(int(subscription_snapshot["current_period_start"]), tz=timezone.utc).isoformat() if subscription_snapshot.get("current_period_start") else None,
                "p_current_period_end": datetime.fromtimestamp(int(subscription_snapshot["current_period_end"]), tz=timezone.utc).isoformat() if subscription_snapshot.get("current_period_end") else None,
            })
        elif event_type in {"customer.subscription.updated", "customer.subscription.deleted", "invoice.paid", "invoice.payment_failed"}:
            sub_id = _event_subscription_id(obj)
            if sub_id:
                subscription_snapshot: dict[str, Any] = {}
                if event_type in {"invoice.paid", "invoice.payment_failed"}:
                    subscription_snapshot = await _stripe_request("GET", f"subscriptions/{sub_id}", key=stripe_key)
                status = str(subscription_snapshot.get("status") or obj.get("status") or ("active" if event_type == "invoice.paid" else "past_due" if event_type == "invoice.payment_failed" else "canceled"))
                if event_type == "customer.subscription.deleted":
                    status = "canceled"
                if event_type == "invoice.payment_failed":
                    status = "past_due"
                period_start = subscription_snapshot.get("current_period_start") or obj.get("current_period_start")
                period_end = subscription_snapshot.get("current_period_end") or obj.get("current_period_end")
                customer_id = subscription_snapshot.get("customer") or obj.get("customer")
                cancel_at_period_end = subscription_snapshot.get("cancel_at_period_end")
                if not isinstance(cancel_at_period_end, bool):
                    cancel_at_period_end = obj.get("cancel_at_period_end") if isinstance(obj.get("cancel_at_period_end"), bool) else None
                await _rpc("billing_apply_subscription_state", {
                    "p_event_id": event_id, "p_subscription_id": sub_id,
                    "p_customer_id": customer_id if isinstance(customer_id, str) else None,
                    "p_status": status,
                    "p_current_period_start": datetime.fromtimestamp(int(period_start), tz=timezone.utc).isoformat() if period_start else None,
                    "p_current_period_end": datetime.fromtimestamp(int(period_end), tz=timezone.utc).isoformat() if period_end else None,
                    "p_cancel_at_period_end": cancel_at_period_end,
                })
                if event_type == "invoice.paid":
                    await _rpc("billing_record_subscription_invoice", {
                        "p_event_id": event_id, "p_subscription_id": sub_id,
                        "p_invoice_id": str(obj.get("id") or ""),
                        "p_payment_intent_id": obj.get("payment_intent") if isinstance(obj.get("payment_intent"), str) else None,
                        "p_amount_paid": int(obj.get("amount_paid") or 0),
                        "p_currency": str(obj.get("currency") or "").lower(),
                        "p_paid_at": datetime.fromtimestamp(int(event.get("created") or time.time()), tz=timezone.utc).isoformat(),
                        "p_hosted_invoice_url": obj.get("hosted_invoice_url"),
                    })
            else:
                await _rpc("billing_mark_stripe_event", {"p_event_id": event_id, "p_status": "ignored", "p_error_code": None})
        elif event_type in {"checkout.session.async_payment_failed", "checkout.session.expired"}:
            metadata = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
            await _rpc("billing_mark_checkout_failed", {
                "p_event_id": event_id, "p_order_id": str(metadata.get("order_id") or ""),
                "p_session_id": str(obj.get("id") or ""),
                "p_status": "expired" if event_type == "checkout.session.expired" else "failed",
            })
        else:
            await _rpc("billing_mark_stripe_event", {"p_event_id": event_id, "p_status": "ignored", "p_error_code": None})
    except Exception as exc:
        # Stripe retries non-2xx responses. Do not acknowledge a failed fulfillment.
        try:
            await _rpc("billing_mark_stripe_event", {"p_event_id": event_id, "p_status": "failed", "p_error_code": type(exc).__name__[:80]})
        except Exception:
            pass
        raise HTTPException(500, detail={"code": "STRIPE_FULFILLMENT_PENDING", "message": "Event Stripe tersimpan tetapi pemenuhan belum selesai; Stripe akan mencoba ulang."}) from exc

    if event_type in _ALLOWED_WEBHOOK_EVENTS:
        await _rpc("billing_mark_stripe_event", {"p_event_id": event_id, "p_status": "processed", "p_error_code": None})
    return {"received": True, "processed": True, "event_id": event_id}

"use client";

import { useCallback, useEffect, useState } from "react";
import { getBrowserSupabase } from "../../lib/supabase";

type Plan = {
  plan_key: string;
  product: {
    product_key: string;
    name: string;
    description?: string | null;
    amount_minor: number;
    currency: string;
    billing_interval?: string | null;
  };
  configuration?: Record<string, unknown>;
};
type Subscription = {
  id: string;
  plan_key: string;
  status: string;
  current_period_start?: string | null;
  current_period_end?: string | null;
  cancel_at_period_end?: boolean;
};
type Entitlement = {
  entitlement_key: string;
  status: string;
  valid_from?: string | null;
  valid_until?: string | null;
};
type BillingOrder = {
  id: string;
  product_key: string;
  product_name: string;
  purpose: string;
  amount_minor: number;
  currency: string;
  status: string;
  created_at: string;
  paid_at?: string | null;
};

function formatAmount(amountMinor: number, currency: string): string {
  const normalized = (currency || "").toUpperCase();
  try {
    const digits = new Intl.NumberFormat("en-US", {
      style: "currency", currency: normalized,
    }).resolvedOptions().maximumFractionDigits;
    return new Intl.NumberFormat("id-ID", {
      style: "currency", currency: normalized,
    }).format(amountMinor / (10 ** digits));
  } catch {
    return String(amountMinor) + " " + normalized;
  }
}

function formatDate(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleDateString("id-ID", {
    day: "numeric", month: "short", year: "numeric",
  });
}

export default function AiCinemaSubscriptionCenter({ apiBase }: { apiBase: string }) {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [entitlements, setEntitlements] = useState<Entitlement[]>([]);
  const [orders, setOrders] = useState<BillingOrder[]>([]);
  const [signedIn, setSignedIn] = useState(false);
  const [plansConfigured, setPlansConfigured] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const accessToken = useCallback(async (): Promise<string | null> => {
    const client = getBrowserSupabase();
    if (!client) return null;
    const result = await client.auth.getSession();
    return result.data.session?.access_token ?? null;
  }, []);

  const request = useCallback(async (
    path: string, token: string | null, init: RequestInit = {},
  ): Promise<any> => {
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    if (token) headers.set("Authorization", "Bearer " + token);
    if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    const response = await fetch(apiBase + path, { ...init, headers, cache: "no-store" });
    const payload = response.status === 204 ? null : await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(payload?.detail?.message || payload?.error?.message || "Permintaan billing gagal (" + response.status + ").");
    }
    return payload;
  }, [apiBase]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [planBody, token] = await Promise.all([
        request("/v1/cinema/subscription/plans", null),
        accessToken(),
      ]);
      setPlans(Array.isArray(planBody?.items) ? planBody.items : []);
      setPlansConfigured(planBody?.configured === true);
      setSignedIn(Boolean(token));
      if (token) {
        const [billingBody, orderBody] = await Promise.all([
          request("/v1/billing/subscription", token),
          request("/v1/billing/orders?limit=20", token),
        ]);
        setSubscription(billingBody?.subscription ?? null);
        setEntitlements(Array.isArray(billingBody?.entitlements) ? billingBody.entitlements : []);
        setOrders(Array.isArray(orderBody?.items) ? orderBody.items : []);
      } else {
        setSubscription(null);
        setEntitlements([]);
        setOrders([]);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Informasi langganan tidak dapat dimuat.");
    } finally {
      setLoading(false);
    }
  }, [accessToken, request]);

  useEffect(() => { void load(); }, [load]);

  async function checkout(productKey: string) {
    setBusy(productKey);
    setError("");
    setNotice("");
    try {
      const token = await accessToken();
      if (!token) throw new Error("Masuk terlebih dahulu untuk berlangganan.");
      const result = await request("/v1/billing/checkout", token, {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ product_key: productKey }),
      });
      if (typeof result?.checkout_url === "string" && result.checkout_url.startsWith("https://")) {
        window.location.assign(result.checkout_url);
        return;
      }
      setNotice("Pesanan " + String(result?.order_id || "") + " tersimpan dengan status " + String(result?.status || "menunggu konfirmasi") + ". Refresh untuk melihat status terbaru.");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Checkout belum dapat dimulai.");
    } finally {
      setBusy(null);
    }
  }

  async function openBillingPortal() {
    setBusy("portal");
    setError("");
    setNotice("");
    try {
      const token = await accessToken();
      if (!token) throw new Error("Masuk terlebih dahulu untuk mengelola langganan.");
      const result = await request("/v1/billing/portal", token, { method: "POST" });
      if (typeof result?.url !== "string" || !result.url.startsWith("https://")) {
        throw new Error("Billing portal tidak mengembalikan URL yang valid.");
      }
      window.location.assign(result.url);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Billing portal belum tersedia.");
    } finally {
      setBusy(null);
    }
  }

  const card = "rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900";
  const button = "inline-flex items-center justify-center rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900";

  return (
    <section className="mx-auto my-10 w-full max-w-6xl px-4 sm:px-6" aria-labelledby="cinema-subscription-title">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[.2em] text-cyan-700">Membership · Billing</p>
          <h2 id="cinema-subscription-title" className="mt-2 text-2xl font-semibold tracking-tight">Langganan AI Cinema</h2>
          <p className="mt-1 max-w-2xl text-sm text-slate-500">Paket, entitlement, pembayaran dan riwayat transaksi dibaca dari layanan billing Allpha. Akses premium hanya aktif setelah webhook pembayaran dan entitlement dikonfirmasi backend.</p>
        </div>
        <button type="button" onClick={() => void load()} disabled={loading || busy !== null} className="rounded-xl border border-slate-300 px-3 py-2 text-xs font-semibold dark:border-slate-700">
          {loading ? "Memuat…" : "Refresh"}
        </button>
      </div>

      {error && <p role="alert" className="mb-4 rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</p>}
      {notice && <p role="status" className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">{notice}</p>}

      <div className="grid gap-4 lg:grid-cols-[1.1fr_.9fr]">
        <div className={card}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="font-semibold">Paket tersedia</h3>
            {!signedIn && <span className="text-xs text-slate-500">Login diperlukan untuk checkout</span>}
          </div>
          {loading ? <p className="mt-4 text-sm text-slate-500">Memuat paket dari server…</p>
            : plans.length === 0 ? <p className="mt-4 rounded-xl bg-slate-50 p-4 text-sm text-slate-500 dark:bg-slate-800">
              {plansConfigured ? "Belum ada paket aktif yang tersedia." : "Paket langganan belum dikonfigurasi atau belum disetujui. Tidak ada paket contoh yang ditampilkan."}
            </p>
            : <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {plans.map(plan => <article key={plan.plan_key} className="rounded-xl border border-slate-200 p-4 dark:border-slate-700">
                <p className="text-xs font-semibold uppercase tracking-wide text-cyan-700">{plan.plan_key}</p>
                <h4 className="mt-2 font-semibold">{plan.product.name}</h4>
                {plan.product.description && <p className="mt-1 text-sm text-slate-500">{plan.product.description}</p>}
                <p className="mt-4 text-xl font-bold">{formatAmount(plan.product.amount_minor, plan.product.currency)}</p>
                <p className="mt-1 text-xs text-slate-500">{plan.product.billing_interval || "Sesuai ketentuan paket"}</p>
                <button type="button" onClick={() => void checkout(plan.product.product_key)} disabled={!signedIn || busy !== null} className={button + " mt-4 w-full"}>
                  {busy === plan.product.product_key ? "Menyiapkan checkout…" : "Berlangganan"}
                </button>
              </article>)}
            </div>}
        </div>

        <div className={card}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="font-semibold">Subscription & entitlement</h3>
            {subscription && <button type="button" onClick={() => void openBillingPortal()} disabled={busy !== null} className="rounded-xl border border-slate-300 px-3 py-2 text-xs font-semibold dark:border-slate-700">Kelola</button>}
          </div>
          {!signedIn ? <p className="mt-4 text-sm text-slate-500">Masuk untuk melihat status langganan dan hak akses akun.</p>
            : loading ? <p className="mt-4 text-sm text-slate-500">Memuat status akun…</p>
            : <>
              {subscription ? <div className="mt-4 rounded-xl bg-slate-50 p-3 dark:bg-slate-800">
                <p className="font-semibold">{subscription.plan_key}</p>
                <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">Status: {subscription.status}</p>
                <p className="mt-1 text-xs text-slate-500">Periode: {formatDate(subscription.current_period_start)} – {formatDate(subscription.current_period_end)}</p>
                {subscription.cancel_at_period_end && <p className="mt-1 text-xs text-amber-700">Berakhir pada akhir periode berjalan.</p>}
              </div> : <p className="mt-4 text-sm text-slate-500">Belum ada subscription aktif yang tercatat.</p>}
              <div className="mt-4">
                <p className="text-sm font-semibold">Entitlement playback</p>
                {entitlements.length === 0 ? <p className="mt-2 text-xs text-slate-500">Belum ada entitlement yang diterbitkan.</p>
                  : <ul className="mt-2 space-y-2">{entitlements.map((item,index) => <li key={item.entitlement_key + "-" + index} className="rounded-lg border border-slate-200 p-2 text-xs dark:border-slate-700">
                    <span className="font-semibold">{item.entitlement_key}</span> · {item.status}
                    <span className="block text-slate-500">{formatDate(item.valid_from)} – {formatDate(item.valid_until)}</span>
                  </li>)}</ul>}
              </div>
            </>}
        </div>
      </div>

      <div className={card + " mt-4"}>
        <h3 className="font-semibold">Riwayat transaksi</h3>
        {!signedIn ? <p className="mt-3 text-sm text-slate-500">Login untuk melihat pesanan dan pembayaran akun.</p>
          : loading ? <p className="mt-3 text-sm text-slate-500">Memuat transaksi…</p>
          : orders.length === 0 ? <p className="mt-3 text-sm text-slate-500">Belum ada transaksi yang tercatat.</p>
          : <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-sm">
              <thead><tr className="border-b border-slate-200 text-xs text-slate-500 dark:border-slate-700">
                <th className="py-2 pr-3">Produk</th><th className="py-2 pr-3">Jumlah</th><th className="py-2 pr-3">Status</th><th className="py-2 pr-3">Tanggal</th>
              </tr></thead>
              <tbody>{orders.map(order => <tr key={order.id} className="border-b border-slate-100 last:border-0 dark:border-slate-800">
                <td className="py-3 pr-3"><span className="font-medium">{order.product_name}</span><span className="block text-xs text-slate-500">{order.product_key}</span></td>
                <td className="py-3 pr-3 whitespace-nowrap">{formatAmount(order.amount_minor, order.currency)}</td>
                <td className="py-3 pr-3">{order.status}</td>
                <td className="py-3 pr-3 whitespace-nowrap text-xs text-slate-500">{formatDate(order.paid_at || order.created_at)}</td>
              </tr>)}</tbody>
            </table>
          </div>}
      </div>
    </section>
  );
}

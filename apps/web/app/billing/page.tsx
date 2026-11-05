"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { getBrowserSupabase } from "../../lib/supabase";

const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

type Product = {
  product_key: string; name: string; description?: string | null; purpose: "ai_credit_topup" | "premium_subscription";
  amount_minor: number; currency: string; billing_interval?: string | null; credits_grant: number; monthly_credits_grant: number; plan_key?: string | null;
};
type Order = {
  id: string; product_key: string; product_name: string; purpose: string; amount_minor: number;
  currency: string; status: string; created_at: string; paid_at?: string | null;
};
type Subscription = { plan_key: string; status: string; current_period_end?: string | null; cancel_at_period_end: boolean } | null;
type Entitlement = { entitlement_key: string; status: string; valid_until?: string | null };

function formatMoney(amountMinor: number, currency: string) {
  const formatter = new Intl.NumberFormat("id-ID", { style: "currency", currency: currency.toUpperCase() });
  const digits = formatter.resolvedOptions().maximumFractionDigits ?? 2;
  return formatter.format(amountMinor / (10 ** digits));
}
function dateLabel(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : new Intl.DateTimeFormat("id-ID", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export default function BillingPage() {
  const [token, setToken] = useState<string | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [subscription, setSubscription] = useState<Subscription>(null);
  const [entitlements, setEntitlements] = useState<Entitlement[]>([]);
  const [balance, setBalance] = useState<{ available_credits: number; reserved_credits: number } | null>(null);
  const [checkoutEnabled, setCheckoutEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const api = useCallback(async <T,>(path: string, accessToken: string, init: RequestInit = {}): Promise<T> => {
    const response = await fetch(apiBase + path, {
      ...init, cache: "no-store",
      headers: { Accept: "application/json", ...(init.body ? { "Content-Type": "application/json" } : {}), ...(init.headers || {}), Authorization: "Bearer " + accessToken },
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body?.error?.message || body?.detail?.message || "Permintaan billing gagal (" + response.status + ").");
    return body as T;
  }, []);

  const load = useCallback(async (accessToken: string) => {
    const [catalog, orderHistory, plan, credit] = await Promise.all([
      api<{ items: Product[]; checkout_enabled: boolean }>("/v1/billing/catalog", accessToken),
      api<{ items: Order[] }>("/v1/billing/orders?limit=10", accessToken),
      api<{ subscription: Subscription; entitlements: Entitlement[] }>("/v1/billing/subscription", accessToken),
      api<{ available_credits: number; reserved_credits: number }>("/v1/credits/balance", accessToken).catch(() => null),
    ]);
    setProducts(catalog.items || []);
    setCheckoutEnabled(catalog.checkout_enabled === true);
    setOrders(orderHistory.items || []);
    setSubscription(plan.subscription);
    setEntitlements(plan.entitlements || []);
    setBalance(credit);
  }, [api]);

  useEffect(() => {
    let active = true;
    const supabase = getBrowserSupabase();
    if (!supabase) { setError("Supabase Auth belum dikonfigurasi pada aplikasi."); setLoading(false); return; }
    void supabase.auth.getSession().then(async ({ data, error: authError }) => {
      if (!active) return;
      if (authError || !data.session?.access_token) { setLoading(false); return; }
      setToken(data.session.access_token);
      try { await load(data.session.access_token); }
      catch (cause) { if (active) setError(cause instanceof Error ? cause.message : "Data billing tidak dapat dimuat."); }
      finally { if (active) setLoading(false); }
    });
    return () => { active = false; };
  }, [load]);

  async function refresh() {
    if (!token) return;
    setLoading(true); setError("");
    try { await load(token); } catch (cause) { setError(cause instanceof Error ? cause.message : "Pembaruan gagal."); }
    finally { setLoading(false); }
  }

  async function checkout(product: Product) {
    if (!token || !checkoutEnabled) return;
    setBusyKey(product.product_key); setError(""); setNotice("");
    try {
      const response = await api<{ order_id: string; checkout_url: string }>("/v1/billing/checkout", token, {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ product_key: product.product_key }),
      });
      if (!response.checkout_url) throw new Error("Stripe belum mengembalikan URL checkout.");
      window.location.assign(response.checkout_url);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Checkout tidak dapat dibuat.");
      setBusyKey(null);
    }
  }
  async function manageSubscription() {
    if (!token) return;
    setBusyKey("portal"); setError("");
    try {
      const result = await api<{ url: string }>("/v1/billing/portal", token, { method: "POST", body: "{}" });
      if (!result.url) throw new Error("Stripe Customer Portal tidak tersedia.");
      window.location.assign(result.url);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Portal subscription gagal dibuka.");
      setBusyKey(null);
    }
  }


  return <main className="mx-auto min-h-screen w-full max-w-6xl px-4 py-8 text-slate-900 dark:text-slate-100 sm:px-6">
    <div className="mb-7 flex flex-wrap items-center justify-between gap-3">
      <div><p className="text-xs font-semibold uppercase tracking-[.2em] text-cyan-700">Account · Economy</p><h1 className="mt-2 text-3xl font-semibold">Billing & AI Credits</h1><p className="mt-2 text-sm text-slate-500">Pembayaran diverifikasi melalui Stripe webhook. Redirect checkout bukan bukti pembayaran.</p></div>
      <div className="flex gap-2"><Link href="/" className="rounded-xl border border-slate-300 px-4 py-2 text-sm">Kembali</Link><button onClick={refresh} disabled={!token || loading} className="rounded-xl bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">Muat ulang</button></div>
    </div>
    {!token ? <section className="rounded-2xl border border-slate-200 p-6 dark:border-slate-700"><h2 className="text-lg font-semibold">Masuk untuk mengelola billing</h2><p className="mt-2 text-sm text-slate-500">Paket, pesanan, saldo AI Credits, dan subscription hanya tersedia untuk akun terautentikasi.</p><Link href="/login?next=/billing" className="mt-4 inline-flex rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white">Masuk / Daftar</Link></section> : <>
      {error && <div role="alert" className="mb-4 rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</div>}
      {notice && <div role="status" className="mb-4 rounded-xl border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800">{notice}</div>}
      <section className="mb-6 grid gap-4 sm:grid-cols-3">
        <article className="rounded-2xl border border-slate-200 p-5 dark:border-slate-700"><p className="text-sm text-slate-500">AI Credits tersedia</p><p className="mt-2 text-2xl font-semibold tabular-nums">{balance ? balance.available_credits.toLocaleString("id-ID") : "—"}</p><p className="mt-1 text-xs text-slate-500">Reservasi aktif: {balance ? balance.reserved_credits.toLocaleString("id-ID") : "—"}</p></article>
        <article className="rounded-2xl border border-slate-200 p-5 dark:border-slate-700"><p className="text-sm text-slate-500">Subscription</p><p className="mt-2 text-xl font-semibold">{subscription?.plan_key || "Free"}</p><p className="mt-1 text-xs text-slate-500">{subscription ? subscription.status + " · sampai " + dateLabel(subscription.current_period_end) : "Belum ada subscription aktif"}</p>{subscription && <button onClick={manageSubscription} disabled={busyKey !== null} className="mt-3 rounded-lg border border-slate-300 px-3 py-2 text-xs disabled:opacity-50">{busyKey === "portal" ? "Membuka portal…" : "Kelola subscription"}</button>}</article>
        <article className="rounded-2xl border border-slate-200 p-5 dark:border-slate-700"><p className="text-sm text-slate-500">Checkout provider</p><p className="mt-2 text-xl font-semibold">Stripe</p><p className="mt-1 text-xs text-slate-500">{checkoutEnabled ? "Checkout tersedia sesuai katalog aktif" : "Checkout dinonaktifkan sampai konfigurasi dan persetujuan billing lengkap"}</p></article>
      </section>
      <section className="mb-8">
        <div className="mb-3 flex items-center justify-between"><h2 className="text-xl font-semibold">Paket & top-up</h2><span className="text-xs text-slate-500">{products.length} produk aktif</span></div>
        {loading ? <div className="rounded-2xl border border-slate-200 p-6 text-sm text-slate-500">Memuat katalog billing…</div> : products.length === 0 ? <div className="rounded-2xl border border-dashed border-slate-300 p-8 text-center dark:border-slate-700"><h3 className="font-semibold">Belum ada paket yang tersedia</h3><p className="mt-2 text-sm text-slate-500">Allpha belum mempublikasikan paket atau tarif. Tidak ada harga maupun jumlah kredit yang dibuat otomatis.</p></div> : <div className="grid gap-4 md:grid-cols-2">
          {products.map(product => <article key={product.product_key} className="rounded-2xl border border-slate-200 p-5 dark:border-slate-700">
            <p className="text-xs font-semibold uppercase tracking-wider text-cyan-700">{product.purpose === "premium_subscription" ? "Subscription" : "AI Credits Top-up"}</p>
            <h3 className="mt-2 text-lg font-semibold">{product.name}</h3><p className="mt-1 min-h-10 text-sm text-slate-500">{product.description || (product.purpose === "premium_subscription" ? "Akses premium sesuai entitlement server." : "Tambahan AI Credits sesuai kebijakan aktif.")}</p>
            <p className="mt-4 text-2xl font-semibold">{formatMoney(product.amount_minor, product.currency)}</p>
            {product.purpose === "ai_credit_topup" ? <p className="mt-1 text-sm text-slate-500">{product.credits_grant.toLocaleString("id-ID")} AI Credits</p> : <p className="mt-1 text-sm text-slate-500">{product.monthly_credits_grant.toLocaleString("id-ID")} AI Credits per paid invoice · tagihan {product.billing_interval || "sesuai periode"}</p>}
            <button onClick={() => checkout(product)} disabled={!checkoutEnabled || busyKey !== null || loading} className="mt-5 w-full rounded-xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50">{busyKey === product.product_key ? "Menyiapkan Stripe Checkout…" : checkoutEnabled ? "Lanjutkan ke Stripe" : "Checkout belum tersedia"}</button>
          </article>)}
        </div>}
      </section>
      <section className="mb-8">
        <h2 className="mb-3 text-xl font-semibold">Entitlement playback</h2>
        {entitlements.length === 0 ? <p className="rounded-xl border border-slate-200 p-4 text-sm text-slate-500 dark:border-slate-700">Belum ada entitlement Premium aktif.</p> : <div className="grid gap-3 sm:grid-cols-2">{entitlements.map((item, index) => <div key={item.entitlement_key + index} className="rounded-xl border border-slate-200 p-4 dark:border-slate-700"><p className="font-medium">{item.entitlement_key}</p><p className="mt-1 text-sm text-slate-500">{item.status} · sampai {dateLabel(item.valid_until)}</p></div>)}</div>}
      </section>
      <section>
        <h2 className="mb-3 text-xl font-semibold">Riwayat pesanan</h2>
        {orders.length === 0 ? <p className="rounded-xl border border-slate-200 p-4 text-sm text-slate-500 dark:border-slate-700">Belum ada transaksi.</p> : <div className="overflow-x-auto rounded-2xl border border-slate-200 dark:border-slate-700"><table className="w-full min-w-[600px] text-left text-sm"><thead className="bg-slate-50 text-slate-500 dark:bg-slate-800"><tr><th className="p-3">Produk</th><th className="p-3">Jumlah</th><th className="p-3">Status</th><th className="p-3">Dibuat</th></tr></thead><tbody>{orders.map(order => <tr key={order.id} className="border-t border-slate-200 dark:border-slate-700"><td className="p-3"><span className="font-medium">{order.product_name}</span><span className="mt-1 block text-xs text-slate-500">{order.id}</span></td><td className="p-3">{formatMoney(order.amount_minor, order.currency)}</td><td className="p-3"><span className="rounded-full bg-slate-100 px-2 py-1 text-xs dark:bg-slate-800">{order.status}</span></td><td className="p-3">{dateLabel(order.created_at)}</td></tr>)}</tbody></table></div>}
      </section>
    </>}
  </main>;
}

"use client";

import { FormEvent, useCallback, useState } from "react";
import Link from "next/link";

type Session = { access_token: string; refresh_token: string; expires_at: number; user: { id: string; email?: string } };
type Operator = { id: string; email?: string; scopes: string[] };
type Product = {
  id: string; product_key: string; name: string; description?: string | null; purpose: string;
  product_approval_reference: string; stripe_price_id: string; stripe_mode: string; amount_minor: number; currency: string;
  billing_interval?: string | null; credits_grant: number; monthly_credits_grant: number; credit_policy_version?: string | null;
  plan_key?: string | null; entitlement_version?: string | null; status: string;
};
type Draft = {
  product_key: string; name: string; description: string; purpose: "ai_credit_topup" | "premium_subscription";
  product_approval_reference: string; stripe_price_id: string; stripe_mode: "payment" | "subscription"; amount_minor: string; currency: string;
  billing_interval: "" | "day" | "week" | "month" | "year"; credits_grant: string; monthly_credits_grant: string;
  credit_policy_version: string; credit_policy_approval_reference: string; plan_key: string; entitlement_version: string;
};
type AuthPayload = { access_token?: string; refresh_token?: string; expires_in?: number; user?: { id: string; email?: string }; error_description?: string; msg?: string };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");
const supabaseUrl = (process.env.NEXT_PUBLIC_SUPABASE_URL || "").replace(/\/$/, "");
const publishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || "";
const emptyDraft: Draft = { product_key: "", name: "", description: "", purpose: "ai_credit_topup", product_approval_reference: "", stripe_price_id: "", stripe_mode: "payment", amount_minor: "", currency: "usd", billing_interval: "", credits_grant: "", monthly_credits_grant: "", credit_policy_version: "", credit_policy_approval_reference: "", plan_key: "", entitlement_version: "" };

async function authRequest(body: Record<string, string>, grant: "password" | "refresh_token"): Promise<Session> {
  if (!supabaseUrl || !publishableKey) throw new Error("Konfigurasi Supabase public belum tersedia.");
  const response = await fetch(supabaseUrl + "/auth/v1/token?grant_type=" + grant, { method: "POST", headers: { apikey: publishableKey, "Content-Type": "application/json" }, body: JSON.stringify(body), cache: "no-store" });
  const data = await response.json().catch(() => ({})) as AuthPayload;
  if (!response.ok || !data.access_token || !data.refresh_token || !data.user?.id) throw new Error(data.error_description || data.msg || "Autentikasi gagal.");
  return { access_token: data.access_token, refresh_token: data.refresh_token, expires_at: Date.now() + Math.max(60, data.expires_in || 3600) * 1000, user: data.user };
}
async function apiFetch(path: string, session: Session, init: RequestInit = {}) {
  let active = session;
  if (active.expires_at <= Date.now() + 30000) active = await authRequest({ refresh_token: active.refresh_token }, "refresh_token");
  const send = (token: string) => fetch(apiBase + path, { ...init, cache: "no-store", headers: { Accept: "application/json", ...(init.body ? { "Content-Type": "application/json" } : {}), ...(init.headers || {}), Authorization: "Bearer " + token } });
  let response = await send(active.access_token);
  if (response.status === 401) { active = await authRequest({ refresh_token: active.refresh_token }, "refresh_token"); response = await send(active.access_token); }
  return response;
}
async function read<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => ({})) as { detail?: { message?: string }; error?: { message?: string } };
  if (!response.ok) throw new Error(data.detail?.message || data.error?.message || "Permintaan gagal (HTTP " + response.status + ").");
  return data as T;
}

export default function BillingGovernancePage() {
  const [session, setSession] = useState<Session | null>(null);
  const [operator, setOperator] = useState<Operator | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [products, setProducts] = useState<Product[]>([]);
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async (active: Session) => {
    const access = await read<{ operator: Operator }>(await apiFetch("/v1/admin/operator/access", active));
    if (!access.operator.scopes.includes("platform:billing.manage")) throw new Error("Scope platform:billing.manage diperlukan.");
    setOperator(access.operator);
    const result = await read<{ items: Product[] }>(await apiFetch("/v1/billing/admin/products", active));
    setProducts(result.items || []);
  }, []);

  async function login(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      const active = await authRequest({ email: email.trim(), password }, "password");
      await load(active); setSession(active); setPassword("");
    } catch (cause) { setSession(null); setOperator(null); setError(cause instanceof Error ? cause.message : "Login operator gagal."); }
    finally { setBusy(false); }
  }

  async function refresh() {
    if (!session) return;
    setBusy(true); setError("");
    try { await load(session); } catch (cause) { setError(cause instanceof Error ? cause.message : "Katalog gagal dimuat."); }
    finally { setBusy(false); }
  }

  async function createDraft(event: FormEvent) {
    event.preventDefault(); if (!session) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const payload = {
        ...draft,
        amount_minor: Number(draft.amount_minor),
        credits_grant: Number(draft.credits_grant || 0),\n        monthly_credits_grant: Number(draft.monthly_credits_grant || 0),
        billing_interval: draft.billing_interval || null,
        credit_policy_version: draft.credit_policy_version || null,
        credit_policy_approval_reference: draft.credit_policy_approval_reference || null,
        plan_key: draft.plan_key || null,
        entitlement_version: draft.entitlement_version || null,
        description: draft.description || null,
      };
      await read(await apiFetch("/v1/billing/admin/products", session, { method: "POST", body: JSON.stringify(payload) }));
      setDraft(emptyDraft); setNotice("Draft produk dibuat. Produk belum dapat dibeli sampai Stripe Price dan kebijakan tervalidasi saat aktivasi.");
      await load(session);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Draft produk gagal dibuat."); }
    finally { setBusy(false); }
  }

  async function productAction(product: Product, action: "activate" | "retire") {
    if (!session) return;
    const message = action === "activate"
      ? "Aktifkan produk setelah mencocokkan Stripe Price dan kebijakan AI Credit? Pastikan persetujuan Finance tersedia."
      : "Pensiunkan produk ini? Checkout baru tidak akan ditawarkan.";
    if (!window.confirm(message)) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await read(await apiFetch("/v1/billing/admin/products/" + encodeURIComponent(product.product_key) + "/" + action, session, { method: "POST", body: "{}" }));
      setNotice(action === "activate" ? "Produk aktif setelah verifikasi Stripe Price dan policy." : "Produk dipensiunkan.");
      await load(session);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Perubahan produk gagal."); }
    finally { setBusy(false); }
  }

  const field = "mt-1 w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 text-sm dark:border-slate-600";
  const label = "block text-sm font-medium";
  return <main className="mx-auto min-h-screen max-w-6xl px-5 py-8 text-slate-900 dark:text-slate-100">
    <nav className="mb-6 flex flex-wrap justify-between gap-3"><Link href="/" className="text-sm text-blue-600 hover:underline">← Operations</Link><span className="text-xs uppercase tracking-[.18em] text-slate-500">ENG-P30 · Stripe Billing Governance</span></nav>
    <header className="mb-6"><p className="text-xs font-semibold uppercase tracking-[.2em] text-cyan-700">Finance & Subscription Control</p><h1 className="mt-2 text-3xl font-semibold">Billing Product Governance</h1><p className="mt-2 text-sm text-slate-500">Katalog harga dikelola operator. Checkout tidak aktif tanpa Stripe Price aktif dan kebijakan yang disetujui.</p></header>
    {error && <p role="alert" className="mb-4 rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</p>}
    {notice && <p role="status" className="mb-4 rounded-xl border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800">{notice}</p>}
    {!session ? <form onSubmit={login} className="max-w-md rounded-2xl border border-slate-200 p-5 dark:border-slate-700"><h2 className="text-lg font-semibold">Login operator</h2><label className={label}>Email<input className={field} type="email" value={email} onChange={e => setEmail(e.target.value)} required autoComplete="username"/></label><label className={label + " mt-3"}>Password<input className={field} type="password" value={password} onChange={e => setPassword(e.target.value)} required autoComplete="current-password"/></label><button disabled={busy} className="mt-4 rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{busy ? "Memverifikasi…" : "Masuk"}</button></form> : <>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-slate-500">Operator: {operator?.email || operator?.id} · {operator?.scopes.includes("platform:billing.manage") ? "Billing scope verified" : "Scope missing"}</p><button onClick={refresh} disabled={busy} className="rounded-xl border border-slate-300 px-4 py-2 text-sm">Muat ulang</button></div>
      <section className="mb-8 rounded-2xl border border-slate-200 p-5 dark:border-slate-700"><h2 className="text-xl font-semibold">Buat draft produk</h2><p className="mt-1 text-sm text-slate-500">Amount minor harus sama dengan Stripe Price. Tidak ada harga default.</p>
        <form onSubmit={createDraft} className="mt-4 grid gap-3 md:grid-cols-2">
          <label className={label}>Product key<input className={field} value={draft.product_key} onChange={e=>setDraft({...draft,product_key:e.target.value})} required pattern="[a-z0-9][a-z0-9._-]{1,79}"/></label>
          <label className={label}>Nama produk<input className={field} value={draft.name} onChange={e=>setDraft({...draft,name:e.target.value})} required maxLength={160}/></label>
          <label className={label}>Tujuan<select className={field} value={draft.purpose} onChange={e=>setDraft({...draft,purpose:e.target.value as Draft["purpose"],stripe_mode:e.target.value==="premium_subscription"?"subscription":"payment"})}><option value="ai_credit_topup">AI Credits Top-up</option><option value="premium_subscription">Premium Subscription</option></select></label>
          <label className={label}>Product / Finance approval reference<input className={field} value={draft.product_approval_reference} onChange={e=>setDraft({...draft,product_approval_reference:e.target.value})} required minLength={3}/></label>\n          <label className={label}>Stripe Price ID<input className={field} value={draft.stripe_price_id} onChange={e=>setDraft({...draft,stripe_price_id:e.target.value})} required pattern="price_[A-Za-z0-9]+"/></label>
          <label className={label}>Amount minor<input className={field} type="number" min="1" step="1" value={draft.amount_minor} onChange={e=>setDraft({...draft,amount_minor:e.target.value})} required/></label>
          <label className={label}>Currency (lowercase)<input className={field} value={draft.currency} onChange={e=>setDraft({...draft,currency:e.target.value.toLowerCase()})} required minLength={3} maxLength={3} pattern="[a-z]{3}"/></label>
          {draft.purpose === "ai_credit_topup" ? <>
            <label className={label}>AI Credits grant<input className={field} type="number" min="1" step="1" value={draft.credits_grant} onChange={e=>setDraft({...draft,credits_grant:e.target.value})} required/></label>
            <label className={label}>Credit policy version<input className={field} value={draft.credit_policy_version} onChange={e=>setDraft({...draft,credit_policy_version:e.target.value})} required/></label>
            <label className={label}>Policy approval reference<input className={field} value={draft.credit_policy_approval_reference} onChange={e=>setDraft({...draft,credit_policy_approval_reference:e.target.value})} required/></label>
          </> : <>
            <label className={label}>AI Credits allowance per paid invoice<input className={field} type="number" min="1" step="1" value={draft.monthly_credits_grant} onChange={e=>setDraft({...draft,monthly_credits_grant:e.target.value})} required/></label>\n            <label className={label}>Credit policy version<input className={field} value={draft.credit_policy_version} onChange={e=>setDraft({...draft,credit_policy_version:e.target.value})} required/></label>\n            <label className={label}>Credit policy approval reference<input className={field} value={draft.credit_policy_approval_reference} onChange={e=>setDraft({...draft,credit_policy_approval_reference:e.target.value})} required/></label>\n            <label className={label}>Plan key<input className={field} value={draft.plan_key} onChange={e=>setDraft({...draft,plan_key:e.target.value})} required/></label>
            <label className={label}>Entitlement version<input className={field} value={draft.entitlement_version} onChange={e=>setDraft({...draft,entitlement_version:e.target.value})} required/></label>
            <label className={label}>Billing interval<select className={field} value={draft.billing_interval} onChange={e=>setDraft({...draft,billing_interval:e.target.value as Draft["billing_interval"]})} required><option value="">Pilih interval</option><option value="month">Bulanan</option><option value="year">Tahunan</option><option value="week">Mingguan</option><option value="day">Harian</option></select></label>
          </>}
          <label className={label + " md:col-span-2"}>Deskripsi<textarea className={field} rows={2} value={draft.description} onChange={e=>setDraft({...draft,description:e.target.value})}/></label>
          <div className="md:col-span-2"><button disabled={busy} className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{busy ? "Menyimpan…" : "Simpan sebagai draft"}</button></div>
        </form>
      </section>
      <section><h2 className="mb-3 text-xl font-semibold">Katalog produk ({products.length})</h2><div className="grid gap-3 md:grid-cols-2">{products.map(product=><article key={product.id} className="rounded-2xl border border-slate-200 p-4 dark:border-slate-700"><div className="flex items-start justify-between gap-3"><div><h3 className="font-semibold">{product.name}</h3><p className="text-xs text-slate-500">{product.product_key} · {product.purpose}</p></div><span className="rounded-full bg-slate-100 px-2 py-1 text-xs dark:bg-slate-800">{product.status}</span></div><p className="mt-3 text-sm">{product.stripe_price_id} · {product.currency.toUpperCase()} {product.amount_minor} minor</p><p className="mt-1 text-xs text-slate-500">{product.credits_grant ? product.credits_grant.toLocaleString("id-ID")+" AI Credits top-up" : product.monthly_credits_grant ? product.monthly_credits_grant.toLocaleString("id-ID")+" AI Credits / paid invoice" : product.plan_key || "No plan"} · {product.stripe_mode}</p><div className="mt-4 flex gap-2">{product.status === "draft" && <button disabled={busy} onClick={()=>void productAction(product,"activate")} className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white">Verifikasi & aktifkan</button>}{product.status !== "retired" && <button disabled={busy} onClick={()=>void productAction(product,"retire")} className="rounded-lg border border-slate-300 px-3 py-2 text-xs">Retire</button>}</div></article>)}</div>{products.length===0 && <p className="rounded-xl border border-dashed border-slate-300 p-6 text-sm text-slate-500">Belum ada produk. Tambahkan draft setelah Stripe Price dan kebijakan Finance siap.</p>}</section>
    </>}
  </main>;
}

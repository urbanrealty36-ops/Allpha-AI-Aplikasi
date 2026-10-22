"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";

const API = (process.env.NEXT_PUBLIC_API_BASE_URL || "https://api.allpha.web.id").replace(/\/$/, "");
const SUPABASE = (process.env.NEXT_PUBLIC_SUPABASE_URL || "").replace(/\/$/, "");
const PUBLIC_KEY = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || "";
const CATEGORIES = [
  "universe", "galaxy", "world", "orbit", "capsule", "district", "booth",
  "content-feed", "agent-character", "live-stage", "human-live", "sticker-social",
  "animation", "navigation-fx",
] as const;
type Category = (typeof CATEGORIES)[number];
type Session = { access_token: string; user: { id: string; email?: string } };
type Receipt = {
  receipt_id: string;
  asset_key: string;
  display_name: string;
  category_candidate: Category | null;
  category_mapping_status: string;
  lifecycle_status: string;
  sha256: string;
  byte_size: number;
  source_repo?: string;
  source_path?: string;
  source_url?: string;
  source_license_claim?: string;
  review_state?: string;
};
type Coverage = { unregistered_receipts: Receipt[]; total_asset_versions: number; total_ingest_receipts: number; integrity_mismatches: unknown[]; category_mismatches: unknown[] };
type Draft = { category: Category | ""; rationale: string; evidence_uri: string };

const panel: React.CSSProperties = { border: "1px solid #293548", borderRadius: 14, padding: 16, background: "#0b1220" };
const field: React.CSSProperties = { width: "100%", boxSizing: "border-box", marginTop: 6, padding: "10px 12px", border: "1px solid #334155", borderRadius: 8, background: "#0f172a", color: "#f8fafc" };
const button: React.CSSProperties = { border: "1px solid #475569", borderRadius: 8, padding: "10px 14px", background: "#172554", color: "#f8fafc", cursor: "pointer" };

export default function SpatialReceiptReconciliationPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [session, setSession] = useState<Session | null>(null);
  const [report, setReport] = useState<Coverage | null>(null);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const call = useCallback(async <T,>(path: string, init: RequestInit = {}): Promise<T> => {
    if (!session) throw new Error("Login operator diperlukan.");
    const response = await fetch(API + path, {
      ...init, cache: "no-store",
      headers: { Accept: "application/json", "Content-Type": "application/json", ...(init.headers || {}), Authorization: "Bearer " + session.access_token },
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body?.detail?.message || body?.message || "API gagal (" + response.status + ").");
    return body as T;
  }, [session]);

  const load = useCallback(async () => {
    if (!session) return;
    setLoading(true); setError("");
    try {
      const result = await call<Coverage>("/v1/admin/spatial/assets/category-coverage");
      setReport(result);
      setDrafts((old) => {
        const next = { ...old };
        for (const receipt of result.unregistered_receipts || []) {
          if (!next[receipt.receipt_id]) next[receipt.receipt_id] = { category: "", rationale: "", evidence_uri: "" };
        }
        return next;
      });
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Gagal memuat receipt."); }
    finally { setLoading(false); }
  }, [call, session]);

  useEffect(() => { if (session) void load(); }, [session, load]);

  async function login(event: FormEvent) {
    event.preventDefault(); setLoading(true); setError(""); setMessage("");
    try {
      if (!SUPABASE || !PUBLIC_KEY) throw new Error("Konfigurasi Supabase public URL/key belum tersedia.");
      const response = await fetch(SUPABASE + "/auth/v1/token?grant_type=password", {
        method: "POST", cache: "no-store",
        headers: { apikey: PUBLIC_KEY, "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok || !body.access_token || !body.user?.id) throw new Error(body.msg || body.error_description || "Login Supabase gagal.");
      setSession({ access_token: body.access_token, user: body.user });
      setMessage("Login berhasil; izin operator akan divalidasi ulang oleh FastAPI.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Login gagal."); }
    finally { setLoading(false); }
  }

  function updateDraft(id: string, patch: Partial<Draft>) {
    setDrafts((old) => { const current = old[id] ?? { category: "", rationale: "", evidence_uri: "" }; return { ...old, [id]: { ...current, ...patch } }; });
  }

  async function register(receipt: Receipt) {
    const draft = drafts[receipt.receipt_id];
    if (!draft?.category || draft.rationale.trim().length < 12 || !draft.evidence_uri.startsWith("https://")) {
      setError("Pilih kategori setelah memeriksa model, isi alasan minimal 12 karakter, dan sertakan URL bukti HTTPS.");
      return;
    }
    setBusyId(receipt.receipt_id); setError(""); setMessage("");
    try {
      const result = await call<{ item: { asset_key: string; status: string }; publication: { status: string; reason: string } }>(
        "/v1/admin/spatial/assets/receipts/" + encodeURIComponent(receipt.receipt_id) + "/register",
        { method: "POST", body: JSON.stringify({ category: draft.category, rationale: draft.rationale.trim(), evidence_uri: draft.evidence_uri.trim() }) },
      );
      setMessage("Receipt " + receipt.asset_key + " sudah terhubung ke registry sebagai " + result.item.status + ". " + result.publication.reason);
      await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Registrasi receipt gagal."); }
    finally { setBusyId(""); }
  }

  return <main style={{ maxWidth: 1180, margin: "0 auto", padding: "28px 16px 48px", color: "#e8edf7", fontFamily: "Inter,system-ui,sans-serif", display: "grid", gap: 16 }}>
    <header>
      <p style={{ color: "#94a3b8", fontSize: 12, letterSpacing: 1.5, textTransform: "uppercase" }}>ENG-P22 · Asset Lifecycle</p>
      <h1 style={{ fontSize: 30, fontWeight: 750, margin: "8px 0" }}>Rekonsiliasi Receipt GLB</h1>
      <p style={{ color: "#aab5ca", maxWidth: 760 }}>Hubungkan receipt yatim ke registry kanonis setelah memeriksa model dan memilih kategori dengan bukti. Aksi ini hanya mendaftarkan aset dalam karantina; tidak menyetujui lisensi, moderasi, atau publikasi.</p>
    </header>
    {!session && <form onSubmit={login} style={{ ...panel, display: "grid", gap: 12, maxWidth: 480 }}>
      <h2 style={{ margin: 0, fontSize: 18 }}>Login operator</h2>
      <label>Email<input type="email" autoComplete="username" required value={email} onChange={(event) => setEmail(event.target.value)} style={field} /></label>
      <label>Password<input type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} style={field} /></label>
      <button type="submit" disabled={loading} style={button}>{loading ? "Memproses…" : "Login dan muat receipt"}</button>
    </form>}
    {error && <p role="alert" style={{ color: "#fecaca", border: "1px solid #7f1d1d", borderRadius: 10, padding: 12 }}>{error}</p>}
    {message && <p role="status" style={{ color: "#bbf7d0", border: "1px solid #166534", borderRadius: 10, padding: 12 }}>{message}</p>}
    {session && <section style={panel}>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
        <div><h2 style={{ fontSize: 18, margin: 0 }}>Receipt belum terdaftar</h2><p style={{ color: "#aab5ca", margin: "5px 0 0" }}>{report ? report.unregistered_receipts.length + " receipt belum terhubung · " + report.total_asset_versions + " versi aset terdaftar" : "Memuat data kanonis…"}</p></div>
        <button type="button" disabled={loading} onClick={() => void load()} style={button}>{loading ? "Memuat…" : "Muat ulang"}</button>
      </div>
    </section>}
    {session && report?.unregistered_receipts.map((receipt) => {
      const draft = drafts[receipt.receipt_id] || { category: "", rationale: "", evidence_uri: "" };
      return <article key={receipt.receipt_id} style={panel}>
        <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 8 }}>
          <div><h3 style={{ margin: 0, fontSize: 17 }}>{receipt.display_name}</h3><p style={{ color: "#a5b4fc", margin: "4px 0" }}>{receipt.asset_key}</p></div>
          <span style={{ color: "#fcd34d", fontSize: 12, alignSelf: "start" }}>{receipt.lifecycle_status} · {receipt.category_mapping_status}</span>
        </div>
        <p style={{ color: "#aab5ca", fontSize: 13, overflowWrap: "anywhere" }}>SHA-256: {receipt.sha256}<br />Ukuran: {receipt.byte_size.toLocaleString("id-ID")} byte<br />Sumber: {receipt.source_repo}/{receipt.source_path}<br />Klaim lisensi: {receipt.source_license_claim || "unknown"}</p>
        {receipt.source_url && <p><a href={receipt.source_url} target="_blank" rel="noreferrer" style={{ color: "#c7d2fe" }}>Buka sumber GLB</a></p>}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 240px), 1fr))", gap: 12 }}>
          <label>Kategori setelah pemeriksaan
            <select value={draft.category} onChange={(event) => updateDraft(receipt.receipt_id, { category: event.target.value as Category | "" })} style={field}>
              <option value="">Pilih kategori…</option>{CATEGORIES.map((category) => <option key={category} value={category}>{category}</option>)}
            </select>
          </label>
          <label>URL bukti visual/semantik (HTTPS)
            <input type="url" required value={draft.evidence_uri} onChange={(event) => updateDraft(receipt.receipt_id, { evidence_uri: event.target.value })} style={field} placeholder="https://…" />
          </label>
        </div>
        <label>Alasan pemetaan (minimal 12 karakter)
          <textarea required minLength={12} maxLength={1000} value={draft.rationale} onChange={(event) => updateDraft(receipt.receipt_id, { rationale: event.target.value })} style={{ ...field, minHeight: 84, resize: "vertical" }} placeholder="Jelaskan bentuk/isi model yang mendukung kategori ini setelah inspeksi." />
        </label>
        <button type="button" disabled={busyId === receipt.receipt_id} onClick={() => void register(receipt)} style={button}>{busyId === receipt.receipt_id ? "Mendaftarkan…" : "Daftarkan sebagai karantina"}</button>
      </article>;
    })}
    {session && report && report.unregistered_receipts.length === 0 && <section style={panel}><h2 style={{ marginTop: 0 }}>Tidak ada receipt yatim</h2><p style={{ color: "#aab5ca" }}>Semua receipt sudah terhubung dengan registry aset. Status hak penggunaan dan publikasi tetap harus diverifikasi secara terpisah.</p></section>}
  </main>;
}

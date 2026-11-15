"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";

type Session = { access_token: string; refresh_token: string; expires_at: number; user: { id: string; email?: string } };
type AuthResponse = { access_token?: string; refresh_token?: string; expires_in?: number; user?: { id: string; email?: string }; error_description?: string; msg?: string };
type Operator = { id: string; email?: string; scopes: string[] };
type ContentMedia = { id: string; filename: string; media_type: string; status: string; scan_status?: string; processed_at?: string | null; preview_url?: string | null; moderation_preview_url?: string | null };
type ContentItem = { id: string; owner_id: string; body: string; content_type: string; visibility: string; status: string; moderation_status: string; version: number; created_at: string; media?: ContentMedia[] };
type GenerationReviewItem = { id: string; owner_user_id: string; agent_owner_user_id?: string; agent_id: string; skill_id: string; task_id: string; trace_id: string; status: string; moderation_status: string; error_code?: string | null; created_at: string; updated_at: string };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");
const supabaseUrl = (process.env.NEXT_PUBLIC_SUPABASE_URL || "").replace(/\/$/, "");
const publishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || "";

async function authRequest(body: Record<string, string>, grant: "password" | "refresh_token"): Promise<Session> {
  if (!supabaseUrl || !publishableKey) throw new Error("Konfigurasi Supabase public belum tersedia.");
  const response = await fetch(`${supabaseUrl}/auth/v1/token?grant_type=${grant}`, { method: "POST", headers: { apikey: publishableKey, "Content-Type": "application/json" }, body: JSON.stringify(body), cache: "no-store" });
  const data = await response.json().catch(() => ({})) as AuthResponse;
  if (!response.ok || !data.access_token || !data.refresh_token || !data.user?.id) throw new Error(data.error_description || data.msg || "Autentikasi gagal.");
  return { access_token: data.access_token, refresh_token: data.refresh_token, expires_at: Date.now() + Math.max(60, data.expires_in || 3600) * 1000, user: data.user };
}
async function apiFetch(path: string, session: Session, init: RequestInit = {}) {
  let current = session;
  if (current.expires_at <= Date.now() + 30000) current = await authRequest({ refresh_token: current.refresh_token }, "refresh_token");
  const send = (token: string) => fetch(apiBase + path, { ...init, cache: "no-store", headers: { Accept: "application/json", ...(init.body ? { "Content-Type": "application/json" } : {}), ...(init.headers || {}), Authorization: `Bearer ${token}` } });
  let response = await send(current.access_token);
  if (response.status === 401) { current = await authRequest({ refresh_token: current.refresh_token }, "refresh_token"); response = await send(current.access_token); }
  return response;
}
async function read<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => ({})) as { error?: { message?: string } };
  if (!response.ok) throw new Error(data.error?.message || `Permintaan gagal (HTTP ${response.status}).`);
  return data as T;
}

export default function ContentModerationPage() {
  const [session, setSession] = useState<Session | null>(null);
  const [operator, setOperator] = useState<Operator | null>(null);
  const [email, setEmail] = useState(""); const [password, setPassword] = useState("");
  const [items, setItems] = useState<ContentItem[]>([]);
  const [generationItems, setGenerationItems] = useState<GenerationReviewItem[]>([]);
  const [generationQueueError, setGenerationQueueError] = useState("");
  const [generationPreview, setGenerationPreview] = useState<{ id: string; text: string } | null>(null);
  const [generationPreviewBusyId, setGenerationPreviewBusyId] = useState<string | null>(null);
  const [generationEvidence, setGenerationEvidence] = useState<Record<string, string>>({});
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [notice, setNotice] = useState("");

  const loadQueue = useCallback(async (active: Session) => {
    const result = await read<{ items: ContentItem[] }>(await apiFetch("/v1/content/admin/review-queue?limit=100", active));
    setItems(Array.isArray(result.items) ? result.items : []);
    try {
      const generation = await read<{ items: GenerationReviewItem[] }>(await apiFetch("/v1/generation/admin/review-queue?limit=100", active));
      setGenerationItems(Array.isArray(generation.items) ? generation.items : []);
      setGenerationQueueError("");
    } catch (cause) {
      setGenerationItems([]);
      setGenerationQueueError(cause instanceof Error ? cause.message : "Antrean AI Generation belum tersedia.");
    }
  }, []);

  const verify = useCallback(async (active: Session) => {
    const result = await read<{ operator: Operator }>(await apiFetch("/v1/admin/operator/access", active));
    setOperator(result.operator);
    if (!result.operator.scopes.includes("platform:content.moderate")) throw new Error("Scope platform:content.moderate diperlukan untuk meninjau konten.");
    await loadQueue(active);
  }, [loadQueue]);

  async function login(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try { const active = await authRequest({ email: email.trim(), password }, "password"); setSession(active); setPassword(""); await verify(active); }
    catch (cause) { setSession(null); setOperator(null); setError(cause instanceof Error ? cause.message : "Login operator gagal."); }
    finally { setBusy(false); }
  }

  async function review(item: ContentItem, decision: "approve" | "reject") {
    const reason = (reasons[item.id] || "").trim();
    if (reason.length < 8) { setError("Alasan moderasi minimal 8 karakter."); return; }
    if (!session) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await read<{ item: ContentItem }>(await apiFetch(`/v1/content/admin/${item.id}/review`, session, { method: "POST", body: JSON.stringify({ decision, expected_version: item.version, reason }) }));
      const resultingStatus = result.item?.status || "updated";
      setNotice(decision === "approve"
      ? resultingStatus === "scheduled" ? "Moderasi disetujui; konten tetap mengikuti jadwal publikasi." : "Moderasi disetujui dan status publikasi diperbarui oleh API."
      : "Konten ditolak dan dikembalikan ke pemilik sebagai gagal.");
      await loadQueue(session);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Keputusan moderasi gagal."); }
    finally { setBusy(false); }
  }

  async function previewGeneration(item: GenerationReviewItem) {
    if (!session) return;
    setGenerationPreviewBusyId(item.id); setError("");
    try {
      const reference = await read<{ url: string }>(await apiFetch(`/v1/generation/admin/jobs/${item.id}/artifact`, session));
      const response = await fetch(reference.url, { cache: "no-store" });
      if (!response.ok) throw new Error("Pratinjau privat tidak dapat diambil.");
      const text = await response.text();
      setGenerationPreview({ id: item.id, text });
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Pratinjau output gagal dibuka."); }
    finally { setGenerationPreviewBusyId(null); }
  }

  async function reviewGeneration(item: GenerationReviewItem, decision: "approve" | "reject") {
    const reason = (reasons[item.id] || "").trim();
    const evidence_reference = (generationEvidence[item.id] || "").trim();
    if (reason.length < 8 || evidence_reference.length < 8) { setError("Alasan dan referensi bukti masing-masing minimal 8 karakter."); return; }
    if (!session) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await read<{ status: string }>(await apiFetch(`/v1/generation/admin/jobs/${item.id}/review`, session, {
        method: "POST", body: JSON.stringify({ decision, reason, evidence_reference }),
      }));
      setGenerationPreview(current => current?.id === item.id ? null : current);
      setNotice(decision === "approve"
        ? result.status === "succeeded" ? "Output disetujui, settlement dan DM terkonfirmasi." : "Moderasi disetujui; settlement tetap menunggu rekonsiliasi."
        : result.status === "failed" ? "Output ditolak dan reservation dilepas sesuai policy." : "Output ditolak; reservation tetap menunggu rekonsiliasi sesuai policy.");
      await loadQueue(session);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Review output AI gagal."); }
    finally { setBusy(false); }
  }

  const canModerate = Boolean(operator?.scopes.includes("platform:content.moderate"));
  return <main style={{ maxWidth: 1000, margin: "0 auto", padding: 24, color: "#101828" }}>
    <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, marginBottom: 24, flexWrap: "wrap" }}>
      <div><Link href="/" style={{ color: "#175cd3", fontSize: 13 }}>← Super Admin</Link> <Link href="/content-appeals" style={{ color: "#175cd3", fontSize: 13, marginLeft: 12 }}>Banding</Link> <Link href="/content-lifecycle" style={{ color: "#175cd3", fontSize: 13, marginLeft: 12 }}>Lifecycle & Retention</Link> <Link href="/content-reports" style={{ color: "#175cd3", fontSize: 13, marginLeft: 12 }}>Laporan konten</Link><h1 style={{ fontSize: 28, margin: "10px 0 4px" }}>Moderasi konten</h1><p style={{ margin: 0, color: "#667085" }}>Antrean review konten kreator, termasuk pratinjau privat media. URL pratinjau berlaku 5 menit; keputusan dicatat dengan alasan, versi, dan audit operator.</p></div>
      {session ? <button onClick={() => { setSession(null); setOperator(null); setItems([]); setGenerationItems([]); setGenerationPreview(null); setNotice(""); }} style={{ padding: "9px 13px" }}>Keluar</button> : null}
    </header>
    {error ? <p role="alert" style={{ padding: 12, background: "#fef3f2", color: "#b42318", borderRadius: 8 }}>{error}</p> : null}
    {notice ? <p role="status" style={{ padding: 12, background: "#ecfdf3", color: "#027a48", borderRadius: 8 }}>{notice}</p> : null}
    {!session ? <section style={{ border: "1px solid #eaecf0", borderRadius: 12, padding: 20, maxWidth: 480 }}><h2 style={{ marginTop: 0 }}>Login operator</h2><form onSubmit={login} style={{ display: "grid", gap: 12 }}><label>Email<input type="email" autoComplete="username" required value={email} onChange={e => setEmail(e.target.value)} style={{ display: "block", width: "100%", padding: 10, marginTop: 5 }} /></label><label>Password<input type="password" autoComplete="current-password" required value={password} onChange={e => setPassword(e.target.value)} style={{ display: "block", width: "100%", padding: 10, marginTop: 5 }} /></label><button type="submit" disabled={busy} style={{ padding: 12 }}>{busy ? "Memverifikasi…" : "Login & verifikasi scope"}</button></form></section> : null}
    {session && canModerate ? <section><div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 12 }}><p style={{ color: "#667085" }}>{items.length} konten menunggu review · {operator?.email || operator?.id}</p><button onClick={() => void loadQueue(session).catch(cause => setError(cause instanceof Error ? cause.message : "Antrean gagal dimuat."))} disabled={busy} style={{ padding: "8px 12px" }}>Muat ulang antrean</button></div>
      {items.length === 0 ? <div style={{ border: "1px dashed #d0d5dd", borderRadius: 12, padding: 28, color: "#667085" }}>Antrean moderasi kosong.</div> : <div style={{ display: "grid", gap: 14 }}>{items.map(item => <article key={item.id} style={{ border: "1px solid #eaecf0", borderRadius: 12, padding: 18 }}><div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}><strong>{item.content_type} · v{item.version}</strong><span style={{ color: "#667085", fontSize: 12 }}>{item.visibility} · {new Date(item.created_at).toLocaleString("id-ID")}</span></div><p style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{item.body || "(Konten media tanpa teks)"}</p>{item.media?.length ? <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12, margin: "14px 0" }}>{item.media.map(media => <div key={media.id} style={{ border: "1px solid #eaecf0", borderRadius: 10, padding: 8, minWidth: 0 }}>{media.preview_url ? media.media_type.startsWith("video/") ? <video controls preload="metadata" poster={media.moderation_preview_url || undefined} src={media.preview_url} style={{ width: "100%", maxHeight: 320, background: "#101828", borderRadius: 6 }} /> : media.media_type.startsWith("audio/") ? <audio controls preload="metadata" src={media.preview_url} style={{ width: "100%" }} aria-label={media.filename} /> : <img src={media.preview_url} alt={media.filename} style={{ width: "100%", maxHeight: 320, objectFit: "contain", borderRadius: 6 }} /> : <p style={{ color: "#667085", fontSize: 12 }}>Pratinjau tidak tersedia.</p>}<p style={{ color: "#667085", fontSize: 12, overflowWrap: "anywhere" }}>{media.filename} · {media.status} · scan {media.scan_status || "unknown"} · {media.processed_at ? "processed" : "not processed"}</p></div>)}</div> : null}<p style={{ color: "#667085", fontSize: 12 }}>ID: {item.id} · status: {item.status}/{item.moderation_status}</p><label style={{ display: "block", fontSize: 13 }}>Alasan / catatan review<input value={reasons[item.id] || ""} onChange={e => setReasons(prev => ({ ...prev, [item.id]: e.target.value }))} minLength={8} maxLength={500} placeholder="Jelaskan alasan keputusan (min. 8 karakter)" style={{ display: "block", width: "100%", padding: 10, marginTop: 5 }} /></label><div style={{ display: "flex", gap: 8, marginTop: 12 }}><button disabled={busy} onClick={() => void review(item, "approve")} style={{ padding: "9px 14px", background: "#067647", color: "white", border: 0, borderRadius: 8 }}>Setujui & publikasikan</button><button disabled={busy} onClick={() => void review(item, "reject")} style={{ padding: "9px 14px", background: "#b42318", color: "white", border: 0, borderRadius: 8 }}>Tolak</button></div></article>)}</div>}
    </section> : null}
    {session && canModerate ? <section style={{ marginTop: 28, border: "1px solid #eaecf0", borderRadius: 12, padding: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div><h2 style={{ margin: 0, fontSize: 20 }}>Review output AI Generation</h2><p style={{ color: "#667085", fontSize: 13 }}>Output privat yang memerlukan review manusia. Approval hanya melanjutkan settlement dan DM; tidak menerbitkan output ke Feed.</p></div>
        <button disabled={busy} onClick={() => void loadQueue(session)} style={{ padding: "8px 12px" }}>Muat ulang antrean AI</button>
      </div>
      {generationQueueError ? <p role="status" style={{ marginTop: 12, padding: 10, borderRadius: 8, background: "#fffaeb", color: "#93370d" }}>Antrean AI Generation belum tersedia: {generationQueueError}</p> : null}
      {!generationQueueError && generationItems.length === 0 ? <div style={{ marginTop: 12, border: "1px dashed #d0d5dd", borderRadius: 10, padding: 20, color: "#667085" }}>Tidak ada output AI yang menunggu review manusia.</div> : null}
      <div style={{ display: "grid", gap: 14, marginTop: 12 }}>
        {generationItems.map(item => <article key={item.id} style={{ border: "1px solid #eaecf0", borderRadius: 10, padding: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}><strong>Generation · {item.agent_id}</strong><span style={{ color: "#667085", fontSize: 12 }}>{new Date(item.created_at).toLocaleString("id-ID")}</span></div>
          <p style={{ color: "#667085", fontSize: 12, overflowWrap: "anywhere" }}>Job {item.id} · Skill {item.skill_id} · {item.status}/{item.moderation_status}</p>
          {item.error_code ? <p style={{ color: "#b42318", fontSize: 12 }}>Status reason: {item.error_code}</p> : null}
          <button disabled={busy || generationPreviewBusyId === item.id} onClick={() => void previewGeneration(item)} style={{ padding: "8px 12px", border: "1px solid #98a2b3", borderRadius: 8 }}>
            {generationPreviewBusyId === item.id ? "Memuat pratinjau…" : "Buka pratinjau privat (180 detik)"}
          </button>
          {generationPreview?.id === item.id ? <pre style={{ marginTop: 10, maxHeight: 320, overflow: "auto", whiteSpace: "pre-wrap", overflowWrap: "anywhere", border: "1px solid #d0d5dd", borderRadius: 8, padding: 12, background: "#f9fafb", color: "#101828", fontSize: 12 }}>{generationPreview.text}</pre> : null}
          <label style={{ display: "block", marginTop: 10, fontSize: 13 }}>Alasan review<input value={reasons[item.id] || ""} onChange={e => setReasons(prev => ({ ...prev, [item.id]: e.target.value }))} minLength={8} maxLength={500} placeholder="Alasan keputusan (min. 8 karakter)" style={{ display: "block", width: "100%", padding: 10, marginTop: 5 }} /></label>
          <label style={{ display: "block", marginTop: 8, fontSize: 13 }}>Referensi bukti<input value={generationEvidence[item.id] || ""} onChange={e => setGenerationEvidence(prev => ({ ...prev, [item.id]: e.target.value }))} minLength={8} maxLength={200} placeholder="ID tiket / referensi evidence" style={{ display: "block", width: "100%", padding: 10, marginTop: 5 }} /></label>
          <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <button disabled={busy} onClick={() => void reviewGeneration(item, "approve")} style={{ padding: "9px 14px", background: "#067647", color: "white", border: 0, borderRadius: 8 }}>Setujui & lanjutkan settlement</button>
            <button disabled={busy} onClick={() => void reviewGeneration(item, "reject")} style={{ padding: "9px 14px", background: "#b42318", color: "white", border: 0, borderRadius: 8 }}>Tolak output</button>
          </div>
        </article>)}
      </div>
    </section> : null}
  </main>;
}

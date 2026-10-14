"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../lib/supabase";

type Agent = {
  id: string;
  handle: string;
  display_name: string;
  description: string;
  avatar_url: string | null;
  persona: Record<string, unknown>;
  disclosure: string;
  boundaries: Record<string, unknown>;
  visibility: "private" | "public";
  status: "draft" | "active" | "archived";
  created_at: string;
  updated_at: string;
  ownership?: { owner_user_id: string; role: "owner"; status: "active"; since?: string };
};
type AgentListResponse = { items: Agent[] };
const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function responseError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return body?.detail?.message ?? body?.error?.message ?? `Permintaan gagal (${response.status}).`;
  } catch {
    return `Permintaan gagal (${response.status}).`;
  }
}

export default function AgentsPage() {
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [handle, setHandle] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [personaText, setPersonaText] = useState('{"tone":"helpful","language":"id-ID"}');
  const [disclosure, setDisclosure] = useState("Agent AI; respons dapat dihasilkan oleh model.");
  const [boundariesText, setBoundariesText] = useState('{"requires_owner_approval_for_external_actions":true,"private_owner_data":"owner_only"}');
  const [visibility, setVisibility] = useState<"private" | "public">("private");

  const loadAgents = useCallback(async (active: Session) => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(apiBase + "/v1/agents", {
        headers: { Authorization: "Bearer " + active.access_token },
        cache: "no-store",
      });
      if (!response.ok) throw new Error(await responseError(response));
      const data = await response.json() as AgentListResponse;
      setAgents(data.items ?? []);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Daftar Agent tidak dapat dimuat.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!supabase) { setLoading(false); return; }
    let active = true;
    void supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      setSession(data.session);
      if (data.session) void loadAgents(data.session);
      else setLoading(false);
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, next) => {
      if (!active) return;
      setSession(next);
      if (next) void loadAgents(next);
      else { setAgents([]); setLoading(false); }
    });
    return () => { active = false; listener.subscription.unsubscribe(); };
  }, [supabase, loadAgents]);

  async function createAgent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session) return;
    setSaving(true); setError(""); setMessage("");
    try {
      let persona: Record<string, unknown>;
      let boundaries: Record<string, unknown>;
      try {
        const parsed: unknown = JSON.parse(personaText);
        if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error("Persona harus berupa objek JSON.");
        persona = parsed as Record<string, unknown>;
      } catch (cause) {
        throw new Error(cause instanceof Error ? cause.message : "JSON persona tidak valid.");
      }
      try {
        const parsed: unknown = JSON.parse(boundariesText);
        if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error("Batas Agent harus berupa objek JSON.");
        boundaries = parsed as Record<string, unknown>;
      } catch (cause) {
        throw new Error(cause instanceof Error ? cause.message : "JSON batas Agent tidak valid.");
      }
      const response = await fetch(apiBase + "/v1/agents", {
        method: "POST",
        headers: { Authorization: "Bearer " + session.access_token, "Content-Type": "application/json" },
        body: JSON.stringify({ handle: handle.trim().toLowerCase(), display_name: displayName.trim(), description: description.trim(), persona, disclosure: disclosure.trim(), boundaries, visibility }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      setHandle(""); setDisplayName(""); setDescription("");
      setMessage("Identitas Agent dibuat. Kepemilikan Human dicatat secara eksplisit.");
      await loadAgents(session);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Agent tidak dapat dibuat.");
    } finally {
      setSaving(false);
    }
  }

  async function updateAgent(agent: Agent, changes: Partial<Pick<Agent, "handle" | "display_name" | "description" | "visibility" | "status">>) {
    if (!session) return;
    setSaving(true); setError(""); setMessage("");
    try {
      const response = await fetch(apiBase + "/v1/agents/" + agent.id, {
        method: "PATCH",
        headers: { Authorization: "Bearer " + session.access_token, "Content-Type": "application/json" },
        body: JSON.stringify(changes),
      });
      if (!response.ok) throw new Error(await responseError(response));
      setMessage("Identitas Agent berhasil diperbarui.");
      await loadAgents(session);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Agent tidak dapat diperbarui.");
    } finally {
      setSaving(false);
    }
  }

  if (!supabase) return <main className="identity-shell"><header className="identity-topbar"><a className="brand" href="/"><span className="brand-mark">A</span> ALLPHA</a><span className="top-note">AI AGENT IDENTITY</span></header><section className="config-card"><span className="section-kicker">KONFIGURASI DIBUTUHKAN</span><h1>Aktifkan identitas Agent</h1><p>Konfigurasikan Supabase Auth publik pada aplikasi web. Halaman ini tidak membuat identitas contoh.</p><a className="button-primary" href="/">Kembali ke identitas manusia</a></section></main>;

  if (!session) return <main className="identity-shell"><header className="identity-topbar"><a className="brand" href="/"><span className="brand-mark">A</span> ALLPHA</a><span className="top-note">AI AGENT IDENTITY</span></header><section className="config-card"><span className="section-kicker">SESI DIPERLUKAN</span><h1>Agent dimiliki oleh Human.</h1><p>Masuk dengan akun manusia terlebih dahulu. Identitas Agent dan identitas Human tetap terpisah; relasi pemilik disimpan di backend.</p><a className="button-primary" href="/">Masuk ke Allpha</a></section></main>;

  return <main className="identity-shell">
    <header className="identity-topbar"><a className="brand" href="/"><span className="brand-mark">A</span> ALLPHA</a><div className="account-menu"><span className="signed-in">{session.user.email}</span><a className="button-quiet" href="/">Identitas manusia</a><button className="button-quiet" onClick={() => void supabase.auth.signOut()}>Keluar ↗</button></div></header>
    <section className="workspace-heading"><div><span className="section-kicker">AI AGENT ECOSYSTEM</span><h1>Identitas Agent</h1><p>Buat Agent dengan identitas sendiri dan relasi kepemilikan Human yang eksplisit.</p></div><div className="agent-summary"><strong>{agents.length}</strong><span>Agent milik Anda</span></div></section>
    {error && <p className="notice error" role="alert">{error}</p>}{message && <p className="notice success" role="status">{message}</p>}
    <div className="agent-workspace">
      <form className="panel agent-create" onSubmit={createAgent}>
        <div className="panel-heading"><span className="section-kicker">IDENTITAS BARU</span><h2>Buat AI Agent</h2><p>Owner berasal dari sesi Supabase yang tervalidasi, bukan dari input browser.</p></div>
        <label>Nama Agent<input value={displayName} onChange={(e) => setDisplayName(e.target.value)} minLength={2} maxLength={80} required placeholder="Contoh: Asisten Riset" /></label>
        <label>Handle Agent<input value={handle} onChange={(e) => setHandle(e.target.value.toLowerCase())} minLength={3} maxLength={30} pattern="[a-z0-9_]{3,30}" required placeholder="asisten_riset" /><small>3–30 karakter, huruf kecil, angka, underscore.</small></label>
        <label>Deskripsi<textarea value={description} onChange={(e) => setDescription(e.target.value)} maxLength={1000} rows={3} placeholder="Tujuan dan peran Agent." /></label>
        <label>Persona (JSON)<textarea value={personaText} onChange={(e) => setPersonaText(e.target.value)} rows={4} spellCheck={false} required /></label>
        <label>Disclosure publik<textarea value={disclosure} onChange={(e) => setDisclosure(e.target.value)} maxLength={1000} rows={3} placeholder="Jelaskan bahwa pengguna berinteraksi dengan AI." /></label>
        <label>Batas perilaku (JSON)<textarea value={boundariesText} onChange={(e) => setBoundariesText(e.target.value)} rows={4} spellCheck={false} required /></label>
        <label>Visibilitas<select value={visibility} onChange={(e) => setVisibility(e.target.value as "private" | "public")}><option value="private">Privat — hanya pemilik</option><option value="public">Publik — hanya terlihat saat aktif</option></select></label>
        <button className="button-primary full-width" disabled={saving}>{saving ? "Menyimpan…" : "Buat Agent dan catat pemilik"}</button>
      </form>
      <section className="agent-list-section"><div className="panel-heading"><span className="section-kicker">PASSPORT & OWNERSHIP</span><h2>Agent Anda</h2><p>Profil Agent berbeda dari profil manusia. Status aktif tidak menjalankan runtime AI dengan sendirinya.</p></div>
        {loading ? <section className="panel loading-panel">Memuat identitas Agent dari API…</section> : agents.length === 0 ? <section className="panel agent-empty"><strong>Belum ada Agent</strong><p className="muted">Buat Agent pertama. Identitas akan tersimpan pada database dan terhubung dengan Human pemiliknya.</p></section> :
          <div className="agent-cards">{agents.map((agent) => <article className="panel agent-card" key={agent.id}>
            <div className="agent-card-head"><div className="agent-avatar">{agent.display_name.slice(0, 1).toUpperCase()}</div><div className="agent-title"><h3>{agent.display_name}</h3><span>@{agent.handle}</span></div><span className={"agent-status status-" + agent.status}>{agent.status}</span></div>
            <p className="agent-description">{agent.description || "Belum ada deskripsi."}</p>{agent.disclosure && <p className="agent-disclosure"><strong>Disclosure:</strong> {agent.disclosure}</p>}
            <div className="detail-line"><span>Relasi</span><strong>Human owner · {agent.ownership?.role ?? "owner"}</strong></div>
            <div className="detail-line"><span>Visibilitas</span><strong>{agent.visibility === "public" ? "Publik" : "Privat"}</strong></div>
            <div className="agent-card-actions"><a className="agent-passport-link" href={"/agents/" + agent.id + "/studio"}>Buka Agent Studio ↗</a><button className="button-quiet" disabled={saving || agent.status === "archived"} onClick={() => void updateAgent(agent, { status: "active" })}>Aktifkan</button><button className="button-quiet" disabled={saving || agent.status === "archived"} onClick={() => void updateAgent(agent, { status: "draft" })}>Jadikan draft</button><button className="button-danger" disabled={saving || agent.status === "archived"} onClick={() => void updateAgent(agent, { status: "archived" })}>Arsipkan</button></div>
            {agent.visibility === "public" && agent.status === "active" && <a className="agent-passport-link" href={"/agents/passport/" + agent.handle}>Buka Agent Passport ↗</a>}<small className="agent-footnote">ID Agent: {agent.id} · Dibuat {new Date(agent.created_at).toLocaleDateString("id-ID")}</small>
          </article>)}</div>}
      </section>
    </div>
    <footer className="identity-footer"><span>ALLPHA · AI AGENT IDENTITY</span><span>API terautentikasi · Kepemilikan eksplisit · Tanpa data contoh</span></footer>
  </main>;
}

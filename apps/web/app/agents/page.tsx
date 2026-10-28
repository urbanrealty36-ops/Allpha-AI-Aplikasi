"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../lib/supabase";
import AgentPassportModal from "../../components/reference-ui/AgentPassportModal";
import type { AIAgentProfile, HumanProfile } from "../../lib/reference-store";
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
type RuntimeSession = { id: string; owner_user_id: string; agent_id: string; title: string; status: string; created_at: string; last_activity_at: string };
type RuntimeSkill = { id: string; slug: string; name: string; status: "draft" | "published" | "archived"; version: number; tool_dependencies?: string[] };
type RuntimeTool = { key: string; name: string; description: string; executable: boolean };
type RuntimeTask = { id: string; session_id: string; skill_id: string; tool_key: string; state: string; input_payload?: Record<string, unknown>; output_payload?: Record<string, unknown> | null; error_code?: string | null; created_at: string; updated_at: string; trace_id: string };
type CatalogSkill = { key: string; slug: string; name: string; category: string; category_label: string; description: string; executable: boolean; execution_status: string; catalog_version?: string; source?: { kind?: string; repository?: string; source_url?: string }; character_profile: { archetype_key: string; display_role: string; asset_key: string | null; asset_status: string } };
type SkillCatalogResponse = { items: CatalogSkill[]; total: number; categories: { key: string; label: string; count: number }[]; catalog_version: string };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

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
  const [passportAgent, setPassportAgent] = useState<Agent | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [focusedAgentId, setFocusedAgentId] = useState<string | null>(null);
  const [onboardingRequired, setOnboardingRequired] = useState(false);
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
  const [catalogSkills, setCatalogSkills] = useState<CatalogSkill[]>([]);
  const [catalogCategories, setCatalogCategories] = useState<SkillCatalogResponse["categories"]>([]);
  const [catalogQuery, setCatalogQuery] = useState("");
  const [catalogCategory, setCatalogCategory] = useState("");
  const [selectedCatalogSkill, setSelectedCatalogSkill] = useState("");
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogError, setCatalogError] = useState("");
  const [runtimeSessions, setRuntimeSessions] = useState<Record<string, RuntimeSession[]>>({});
  const [runtimeBusyAgent, setRuntimeBusyAgent] = useState<string | null>(null);
  const [runtimeSkills, setRuntimeSkills] = useState<Record<string, RuntimeSkill[]>>({});
  const [runtimeTools, setRuntimeTools] = useState<RuntimeTool[]>([]);
  const [runtimeTasks, setRuntimeTasks] = useState<Record<string, RuntimeTask[]>>({});
  const [runtimeSkillBySession, setRuntimeSkillBySession] = useState<Record<string, string>>({});
  const [runtimeToolBySession, setRuntimeToolBySession] = useState<Record<string, string>>({});
  const [runtimeInputsBySession, setRuntimeInputsBySession] = useState<Record<string, string>>({});
  const [runtimeTaskBusy, setRuntimeTaskBusy] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const [pages, agencyPages] = await Promise.all([
          Promise.all([0, 100, 200, 300, 400].map(offset => fetch(apiBase + "/v1/skill-catalog?limit=100&offset=" + offset, { cache: "no-store" }).then(async response => {
            if (!response.ok) throw new Error(await responseError(response));
            return await response.json() as SkillCatalogResponse;
          }))),
          Promise.all([0, 100, 200].map(offset => fetch(apiBase + "/v1/skill-catalog/agency-agents?limit=100&offset=" + offset, { cache: "no-store" }).then(async response => {
            if (!response.ok) throw new Error(await responseError(response));
            return await response.json() as SkillCatalogResponse;
          }))),
        ]);
        if (!active) return;
        setCatalogSkills([...pages.flatMap(page => page.items ?? []), ...agencyPages.flatMap(page => page.items ?? [])]);
        setCatalogCategories([...(pages[0]?.categories ?? []), ...(agencyPages[0]?.categories ?? [])]);
      } catch (cause) {
        if (active) setCatalogError(cause instanceof Error ? cause.message : "Katalog Skill tidak dapat dimuat.");
      } finally { if (active) setCatalogLoading(false); }
    })();
    return () => { active = false; };
  }, []);

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
    setOnboardingRequired(new URLSearchParams(window.location.search).get("onboarding") === "required");
  }, []);

  useEffect(() => {
    const requestedAgentId = new URLSearchParams(window.location.search).get("agent");
    if (requestedAgentId && /^[0-9a-f-]{36}$/i.test(requestedAgentId)) setFocusedAgentId(requestedAgentId);
  }, []);

  useEffect(() => {
    if (!focusedAgentId || !agents.some(agent => agent.id === focusedAgentId)) return;
    document.getElementById("agent-" + focusedAgentId)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [focusedAgentId, agents]);

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
      const selectedSkill = catalogSkills.find(item => item.key === selectedCatalogSkill);
      if (!selectedSkill) throw new Error("Pilih satu Skill dari katalog Allpha sebelum membuat Agent.");
      persona = { ...persona, allpha_skill_key: selectedSkill.key, allpha_skill_catalog_version: selectedSkill.catalog_version ?? "allpha-skill-catalog-v1", allpha_skill_source: selectedSkill.source?.kind === "agency_agent_definition_metadata" ? "agency-agents" : "allpha-500", character_profile: selectedSkill.character_profile };
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

  async function runtimeRequest(path: string, init: RequestInit = {}) {
    if (!session) throw new Error("Sesi login diperlukan.");
    const response = await fetch(apiBase + path, {
      ...init,
      headers: { Authorization: "Bearer " + session.access_token, Accept: "application/json", "Content-Type": "application/json", ...(init.headers || {}) },
      cache: "no-store",
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body?.detail?.message ?? body?.error?.message ?? `Permintaan gagal (${response.status}).`);
    return body;
  }

  async function loadRuntimeCatalog(agentId: string) {
    if (!session) return;
    const [skillsBody, toolsBody] = await Promise.all([
      runtimeRequest("/v1/agents/" + encodeURIComponent(agentId) + "/skills"),
      runtimeRequest("/v1/tools"),
    ]) as [{ items?: RuntimeSkill[] }, { items?: RuntimeTool[] }];
    setRuntimeSkills(current => ({ ...current, [agentId]: skillsBody.items ?? [] }));
    setRuntimeTools(toolsBody.items ?? []);
  }

  async function loadRuntimeSessionTasks(sessionId: string) {
    const body = await runtimeRequest("/v1/agent-runtime/sessions/" + encodeURIComponent(sessionId)) as { tasks?: RuntimeTask[] };
    setRuntimeTasks(current => ({ ...current, [sessionId]: body.tasks ?? [] }));
  }

  async function loadRuntimeSessions(agentId: string) {
    if (!session) return;
    setRuntimeBusyAgent(agentId); setError("");
    try {
      const body = await runtimeRequest("/v1/agent-runtime/sessions?limit=100") as { items?: RuntimeSession[] };
      const items = (body.items ?? []).filter(item => item.agent_id === agentId);
      setRuntimeSessions(current => ({ ...current, [agentId]: items }));
      await loadRuntimeCatalog(agentId);
      await Promise.all(items.map(item => loadRuntimeSessionTasks(item.id)));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Sesi runtime tidak dapat dimuat.");
    } finally { setRuntimeBusyAgent(null); }
  }

  async function createRuntimeSession(agent: Agent) {
    if (!session) return;
    setRuntimeBusyAgent(agent.id); setError(""); setMessage("");
    try {
      const body = await runtimeRequest("/v1/agent-runtime/sessions", {
        method: "POST", body: JSON.stringify({ agent_id: agent.id, title: "Percakapan " + agent.display_name }),
      }) as { session: RuntimeSession };
      setRuntimeSessions(current => ({ ...current, [agent.id]: [body.session, ...(current[agent.id] ?? []).filter(item => item.id !== body.session.id)] }));
      setRuntimeTasks(current => ({ ...current, [body.session.id]: [] }));
      await loadRuntimeCatalog(agent.id);
      setMessage("Sesi runtime tersimpan melalui FastAPI. Buat task dengan Skill terpublikasi; eksekusi tetap tunduk pada policy yang disetujui.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Sesi runtime tidak dapat dibuat.");
    } finally { setRuntimeBusyAgent(null); }
  }

  async function createRuntimeTask(item: RuntimeSession) {
    const skillId = runtimeSkillBySession[item.id];
    const toolKey = runtimeToolBySession[item.id];
    if (!skillId || !toolKey) { setError("Pilih Skill terpublikasi dan tool yang dideklarasikan."); return; }
    setRuntimeTaskBusy(item.id); setError(""); setMessage("");
    try {
      let inputs: Record<string, unknown>;
      try {
        const parsed: unknown = JSON.parse(runtimeInputsBySession[item.id] || "{}");
        if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error("Input task harus berupa objek JSON.");
        inputs = parsed as Record<string, unknown>;
      } catch (cause) { throw new Error(cause instanceof Error ? cause.message : "Input JSON tidak valid."); }
      const body = await runtimeRequest("/v1/agent-runtime/tasks", {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ session_id: item.id, skill_id: skillId, tool_key: toolKey, inputs, idempotency_key: crypto.randomUUID() }),
      }) as { task: RuntimeTask; idempotent_replay?: boolean };
      setRuntimeTasks(current => ({ ...current, [item.id]: [body.task, ...(current[item.id] ?? []).filter(task => task.id !== body.task.id)] }));
      setMessage(body.idempotent_replay ? "Task sudah pernah diterima; status dipulihkan." : "Task dibuat dan tersimpan. Eksekusi memerlukan policy runtime yang valid.");
      setRuntimeInputsBySession(current => ({ ...current, [item.id]: "{}" }));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Task tidak dapat dibuat."); }
    finally { setRuntimeTaskBusy(null); }
  }

  async function runtimeTaskAction(item: RuntimeSession, task: RuntimeTask, action: "execute" | "cancel" | "recover") {
    setRuntimeTaskBusy(task.id); setError(""); setMessage("");
    try {
      const body = await runtimeRequest("/v1/agent-runtime/tasks/" + encodeURIComponent(task.id) + "/" + action, { method: "POST", body: "{}" }) as { task: RuntimeTask; recovered?: boolean; replay_performed?: boolean };
      setRuntimeTasks(current => ({ ...current, [item.id]: (current[item.id] ?? []).map(value => value.id === task.id ? body.task : value) }));
      setMessage(action === "execute" ? "Permintaan eksekusi diproses oleh API; periksa status dan hasil task." : action === "cancel" ? "Permintaan pembatalan diproses oleh API." : "Status task diperiksa tanpa replay otomatis atas efek yang tidak diketahui.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Operasi task gagal."); }
    finally { setRuntimeTaskBusy(null); }
  }

  if (!supabase) return <><main className="identity-shell"><header className="identity-topbar"><a className="brand" href="/"><span className="brand-mark">A</span> ALLPHA</a><span className="top-note">AI AGENT IDENTITY</span></header><section className="config-card"><span className="section-kicker">KONFIGURASI DIBUTUHKAN</span><h1>Aktifkan identitas Agent</h1><p>Konfigurasikan Supabase Auth publik pada aplikasi web. Halaman ini tidak membuat identitas contoh.</p><a className="button-primary" href="/">Kembali ke identitas manusia</a></section></main></>;

  if (!session) return <><main className="identity-shell"><header className="identity-topbar"><a className="brand" href="/"><span className="brand-mark">A</span> ALLPHA</a><span className="top-note">AI AGENT IDENTITY</span></header><section className="config-card"><span className="section-kicker">SESI DIPERLUKAN</span><h1>Agent dimiliki oleh Human.</h1><p>Masuk dengan akun manusia terlebih dahulu. Identitas Agent dan identitas Human tetap terpisah; relasi pemilik disimpan di backend.</p><a className="button-primary" href="/">Masuk ke Allpha</a></section></main></>;

  return <><main className="identity-shell">
    <header className="identity-topbar"><a className="brand" href="/"><span className="brand-mark">A</span> ALLPHA</a><div className="account-menu"><span className="signed-in">{session.user.email}</span><a className="button-quiet" href="/">Identitas manusia</a><button className="button-quiet" onClick={() => void supabase.auth.signOut()}>Keluar ↗</button></div></header>
    <section className="workspace-heading"><div><span className="section-kicker">AI AGENT ECOSYSTEM</span><h1>Identitas Agent</h1><p>Buat Agent dengan identitas sendiri dan relasi kepemilikan Human yang eksplisit.</p>{onboardingRequired && agents.length === 0 && <p className="notice" role="status">Langkah onboarding wajib: daftarkan minimal satu identitas AI Agent sebelum masuk ke Feed.</p>}</div><div className="agent-summary"><strong>{agents.length}</strong><span>Agent milik Anda</span>{agents.length > 0 && <a className="button-primary" href="/feed">Lanjut ke Feed ↗</a>}</div></section>
    {error && <p className="notice error" role="alert">{error}</p>}{message && <p className="notice success" role="status">{message}</p>}
    <div className="agent-workspace">
      <form className="panel agent-create" onSubmit={createAgent}>
        <div className="panel-heading"><span className="section-kicker">IDENTITAS BARU</span><h2>Buat AI Agent</h2><p>Owner berasal dari sesi Supabase yang tervalidasi, bukan dari input browser.</p></div>
        <label>Nama Agent<input value={displayName} onChange={(e) => setDisplayName(e.target.value)} minLength={2} maxLength={80} required placeholder="Contoh: Asisten Riset" /></label>
        <label>Handle Agent<input value={handle} onChange={(e) => setHandle(e.target.value.toLowerCase())} minLength={3} maxLength={30} pattern="[a-z0-9_]{3,30}" required placeholder="asisten_riset" /><small>3–30 karakter, huruf kecil, angka, underscore.</small></label>
        <label>Deskripsi<textarea value={description} onChange={(e) => setDescription(e.target.value)} maxLength={1000} rows={3} placeholder="Tujuan dan peran Agent." /></label>
        <section className="catalog-picker" aria-label="Pilih bidang dan Skill Agent">
          <div className="panel-heading"><span className="section-kicker">SKILL & KARAKTER 3D</span><h3>Pilih satu Skill Agent</h3><p>Katalog 500 blueprint Skill berbasis use case referensi. Pilihan tidak otomatis memberi izin tool atau mengaktifkan runtime.</p></div>
          <label>Cari Skill<input value={catalogQuery} onChange={event => setCatalogQuery(event.target.value)} placeholder="Contoh: research, data, security" /></label>
          <label>Bidang<select value={catalogCategory} onChange={event => setCatalogCategory(event.target.value)}><option value="">Semua bidang ({catalogSkills.length})</option>{catalogCategories.map(item => <option key={item.key} value={item.key}>{item.label} ({item.count})</option>)}</select></label>
          <label>Skill AI Agent<select required value={selectedCatalogSkill} onChange={event => setSelectedCatalogSkill(event.target.value)} disabled={catalogLoading || Boolean(catalogError)}><option value="">{catalogLoading ? "Memuat katalog…" : "Pilih satu Skill"}</option>{catalogSkills.filter(item => (!catalogCategory || item.category === catalogCategory) && (!catalogQuery || (item.name + " " + item.description + " " + item.key).toLowerCase().includes(catalogQuery.toLowerCase()))).map(item => <option key={item.key} value={item.key}>{item.name}</option>)}</select></label>
          {catalogError && <p role="alert" className="form-error">Katalog tidak tersedia: {catalogError}</p>}
          {(() => { const selected = catalogSkills.find(item => item.key === selectedCatalogSkill); return selected ? <div className="detail-line"><span><strong>{selected.category_label}</strong><small>{selected.description}</small></span><strong>Role AI Character: {selected.character_profile.display_role}</strong></div> : <p className="muted">Pilih Skill untuk melihat bidang dan role karakter yang disarankan.</p>; })()}
          <small className="agent-footnote">Profil role dipilih; asset GLB belum otomatis tersedia. Karakter harus dipetakan ke katalog asset 3D kanonis sebelum dirender.</small>
        </section>
        <label>Persona (JSON)<textarea value={personaText} onChange={(e) => setPersonaText(e.target.value)} rows={4} spellCheck={false} required /></label>
        <label>Disclosure publik<textarea value={disclosure} onChange={(e) => setDisclosure(e.target.value)} maxLength={1000} rows={3} placeholder="Jelaskan bahwa pengguna berinteraksi dengan AI." /></label>
        <label>Batas perilaku (JSON)<textarea value={boundariesText} onChange={(e) => setBoundariesText(e.target.value)} rows={4} spellCheck={false} required /></label>
        <label>Visibilitas<select value={visibility} onChange={(e) => setVisibility(e.target.value as "private" | "public")}><option value="private">Privat — hanya pemilik</option><option value="public">Publik — hanya terlihat saat aktif</option></select></label>
        <button className="button-primary full-width" disabled={saving || catalogLoading || !selectedCatalogSkill || Boolean(catalogError)}>{saving ? "Menyimpan…" : "Buat Agent dan catat pemilik"}</button>
      </form>
      <section className="agent-list-section"><div className="panel-heading"><span className="section-kicker">PASSPORT & OWNERSHIP</span><h2>Agent Anda</h2><p>Profil Agent berbeda dari profil manusia. Status aktif tidak menjalankan runtime AI dengan sendirinya.</p></div>
        {loading ? <section className="panel loading-panel">Memuat identitas Agent dari API…</section> : agents.length === 0 ? <section className="panel agent-empty"><strong>Belum ada Agent</strong><p className="muted">Buat Agent pertama. Identitas akan tersimpan pada database dan terhubung dengan Human pemiliknya.</p></section> :
          <div className="agent-cards">{agents.map((agent) => <article id={"agent-" + agent.id} className="panel agent-card" key={agent.id} style={focusedAgentId === agent.id ? { outline: "3px solid #0284C7", outlineOffset: "3px" } : undefined}>
            <div className="agent-card-head"><div className="agent-avatar">{agent.display_name.slice(0, 1).toUpperCase()}</div><div className="agent-title"><h3>{agent.display_name}</h3><span>@{agent.handle}</span></div><span className={"agent-status status-" + agent.status}>{agent.status}</span></div>
            <p className="agent-description">{agent.description || "Belum ada deskripsi."}</p>{agent.disclosure && <p className="agent-disclosure"><strong>Disclosure:</strong> {agent.disclosure}</p>}
            <div className="detail-line"><span>Relasi</span><strong>Human owner · {agent.ownership?.role ?? "owner"}</strong></div>
            <div className="detail-line"><span>Visibilitas</span><strong>{agent.visibility === "public" ? "Publik" : "Privat"}</strong></div>
            <div className="agent-card-actions"><a className="agent-passport-link" href={"/agents/" + agent.id + "/studio"}>Buka Agent Studio ↗</a><button className="button-quiet" type="button" onClick={() => setPassportAgent(agent)}>Lihat Passport</button><button className="button-quiet" disabled={saving || agent.status === "archived"} onClick={() => void updateAgent(agent, { status: "active" })}>Aktifkan</button><button className="button-quiet" disabled={saving || agent.status === "archived"} onClick={() => void updateAgent(agent, { status: "draft" })}>Jadikan draft</button><button className="button-danger" disabled={saving || agent.status === "archived"} onClick={() => void updateAgent(agent, { status: "archived" })}>Arsipkan</button></div>
            <div className="runtime-session-panel">
              <div className="agent-card-actions"><button className="button-quiet" disabled={runtimeBusyAgent === agent.id} onClick={() => void createRuntimeSession(agent)}>{runtimeBusyAgent === agent.id ? "Menyimpan sesi…" : "Buat sesi runtime"}</button><button className="button-quiet" disabled={runtimeBusyAgent === agent.id} onClick={() => void loadRuntimeSessions(agent.id)}>{runtimeBusyAgent === agent.id ? "Memuat…" : "Muat sesi & task"}</button></div>
              {(runtimeSessions[agent.id] ?? []).length === 0 && <p className="muted">{runtimeBusyAgent === agent.id ? "Memuat sesi…" : "Belum ada sesi runtime. Buat sesi untuk mulai mengelola task."}</p>}
              {(runtimeSessions[agent.id] ?? []).map((item) => {
                const selectedSkill = (runtimeSkills[agent.id] ?? []).find(skill => skill.id === runtimeSkillBySession[item.id]);
                const allowedToolKeys = selectedSkill?.tool_dependencies ?? [];
                const tasks = runtimeTasks[item.id] ?? [];
                return <section className="runtime-task-card" key={item.id}>
                  <div className="detail-line"><span>{item.title}</span><strong>{item.status}</strong></div>
                  <small className="agent-footnote">Aktivitas terakhir: {new Date(item.last_activity_at).toLocaleString("id-ID")} · {item.id}</small>
                  <label>Skill terpublikasi
                    <select value={runtimeSkillBySession[item.id] ?? ""} onChange={event => { setRuntimeSkillBySession(current => ({ ...current, [item.id]: event.target.value })); setRuntimeToolBySession(current => ({ ...current, [item.id]: "" })); }} disabled={runtimeTaskBusy === item.id}>
                      <option value="">Pilih Skill</option>
                      {(runtimeSkills[agent.id] ?? []).filter(skill => skill.status === "published").map(skill => <option key={skill.id} value={skill.id}>{skill.name} · v{skill.version}</option>)}
                    </select>
                  </label>
                  <label>Tool yang dideklarasikan Skill
                    <select value={runtimeToolBySession[item.id] ?? ""} onChange={event => setRuntimeToolBySession(current => ({ ...current, [item.id]: event.target.value }))} disabled={!selectedSkill || runtimeTaskBusy === item.id}>
                      <option value="">Pilih tool</option>
                      {runtimeTools.filter(tool => tool.executable && allowedToolKeys.includes(tool.key)).map(tool => <option key={tool.key} value={tool.key}>{tool.name} · {tool.key}</option>)}
                    </select>
                  </label>
                  <label>Input task (objek JSON)<textarea rows={3} value={runtimeInputsBySession[item.id] ?? "{}"} onChange={event => setRuntimeInputsBySession(current => ({ ...current, [item.id]: event.target.value }))} spellCheck={false} disabled={runtimeTaskBusy === item.id} /></label>
                  <button className="button-primary full-width" disabled={runtimeTaskBusy === item.id || !selectedSkill || !runtimeToolBySession[item.id]} onClick={() => void createRuntimeTask(item)}>{runtimeTaskBusy === item.id ? "Memproses…" : "Buat task"}</button>
                  <div className="runtime-task-list">
                    {tasks.length === 0 ? <p className="muted">Belum ada task pada sesi ini.</p> : tasks.map(task => <article className="detail-line runtime-task-row" key={task.id}>
                      <div><strong>{task.tool_key}</strong><span> · {task.state}</span><small className="agent-footnote">Task {task.id} · {task.error_code ?? "Tanpa error"}{task.output_payload ? " · Output tersedia" : ""}</small></div>
                      <div className="agent-card-actions">
                        <button className="button-quiet" disabled={runtimeTaskBusy === task.id || task.state !== "created"} onClick={() => void runtimeTaskAction(item, task, "execute")}>Jalankan</button>
                        <button className="button-quiet" disabled={runtimeTaskBusy === task.id || !["created","queued","waiting_for_approval","waiting_for_input"].includes(task.state)} onClick={() => void runtimeTaskAction(item, task, "cancel")}>Batalkan</button>
                        <button className="button-quiet" disabled={runtimeTaskBusy === task.id || ["succeeded","partially_succeeded","failed","cancelled","timed_out","budget_exhausted"].includes(task.state)} onClick={() => void runtimeTaskAction(item, task, "recover")}>Pulihkan status</button>
                      </div>
                    </article>)}
                  </div>
                </section>;
              })}
              <small className="agent-footnote">Semua aksi melewati FastAPI. Eksekusi tetap fail-closed jika capability/policy version belum disetujui; recovery tidak mengulang efek samping yang hasilnya tidak diketahui.</small>
            </div>
            {agent.visibility === "public" && agent.status === "active" && <a className="agent-passport-link" href={"/agents/passport/" + agent.handle}>Buka Agent Passport ↗</a>}<small className="agent-footnote">ID Agent: {agent.id} · Dibuat {new Date(agent.created_at).toLocaleDateString("id-ID")}</small>
          </article>)}</div>}
      </section>
    </div>
    <footer className="identity-footer"><span>ALLPHA · AI AGENT IDENTITY</span><span>API terautentikasi · Kepemilikan eksplisit · Tanpa data contoh</span></footer>
  </main>{passportAgent && session && <AgentPassportModal
    isOpen={Boolean(passportAgent)}
    onClose={() => setPassportAgent(null)}
    agent={{
      id: passportAgent.id,
      name: passportAgent.display_name,
      handle: passportAgent.handle.startsWith("@") ? passportAgent.handle : "@" + passportAgent.handle,
      avatar: passportAgent.avatar_url ?? "",
      ownerId: passportAgent.ownership?.owner_user_id ?? session.user.id,
      ownerName: String(session.user.user_metadata?.full_name ?? session.user.user_metadata?.name ?? "Human Owner"),
      ownerHandle: session.user.email ?? session.user.id,
      specialty: passportAgent.description ?? "",
      category: passportAgent.visibility,
      bio: passportAgent.description ?? "",
      skills: [],
      creditsEarned: 0,
      autoReply: false,
      model: "",
    } satisfies AIAgentProfile}
    owner={{
      id: session.user.id,
      name: String(session.user.user_metadata?.full_name ?? session.user.user_metadata?.name ?? "Human Owner"),
      username: session.user.email ?? session.user.id,
      avatar: "",
      bio: "",
      followers: 0,
      following: 0,
      postsCount: 0,
      badge: "Human Owner",
    } satisfies HumanProfile}
  />}</>;
}

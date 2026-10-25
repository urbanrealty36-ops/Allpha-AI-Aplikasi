"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import Link from "next/link";
import { getBrowserSupabase } from "../../lib/supabase";

type WorkflowDefinition = {
  id: string; workflow_key: string; version: number; status: string;
  digest: string; definition: Record<string, unknown>; created_at: string;
};
type WorkflowRun = {
  id: string; definition_id: string; definition_version: number; status: string;
  trace_id: string; created_at: string; updated_at: string; completed_at?: string | null;
  steps?: Array<{ id: string; node_key: string; node_kind: string; status: string; output_payload?: Record<string, unknown> | null; error_code?: string | null }>;
  events?: Array<{ sequence: number; event_type: string; step_key?: string | null; created_at: string; details?: Record<string, unknown> }>;
};
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");
const initialDefinition = JSON.stringify({
  workflow_key: "contoh-workflow",
  version: 1,
  max_runtime_seconds: 60,
  max_retries: 1,
  nodes: [{ key: "hasil", kind: "constant", config: { value: "Halo dari Workflow Engine" }, timeout_seconds: 5 }],
  edges: []
}, null, 2);

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return body?.error?.message ?? body?.detail?.message ?? `Permintaan gagal (HTTP ${response.status}).`;
  } catch {
    return `Permintaan gagal (HTTP ${response.status}).`;
  }
}

export default function WorkflowsPage() {
  const [supabase, setSupabase] = useState<ReturnType<typeof getBrowserSupabase>>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [definitions, setDefinitions] = useState<WorkflowDefinition[]>([]);
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<WorkflowRun | null>(null);
  const [selectedDefinitionId, setSelectedDefinitionId] = useState("");
  const [definitionText, setDefinitionText] = useState(initialDefinition);
  const [inputText, setInputText] = useState("{}");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  // Initialize browser-only Supabase after hydration to keep server/client markup identical.
  useEffect(() => { setSupabase(getBrowserSupabase()); }, []);

  const request = useCallback(async (path: string, init: RequestInit = {}) => {
    if (!session) throw new Error("Sesi login tidak tersedia. Silakan masuk terlebih dahulu.");
    const response = await fetch(apiBase + path, {
      ...init,
      headers: {
        Authorization: "Bearer " + session.access_token,
        Accept: "application/json",
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...init.headers
      },
      cache: "no-store"
    });
    if (!response.ok) throw new Error(await errorMessage(response));
    return response.status === 204 ? null : response.json();
  }, [session]);

  const refresh = useCallback(async () => {
    if (!session) { setLoading(false); return; }
    setLoading(true);
    setError("");
    try {
      const [definitionResponse, runResponse] = await Promise.all([
        request("/v1/workflows/definitions?limit=50"),
        request("/v1/workflows/runs?limit=50")
      ]);
      const nextDefinitions = Array.isArray(definitionResponse?.items) ? definitionResponse.items : [];
      const nextRuns = Array.isArray(runResponse?.items) ? runResponse.items : [];
      setDefinitions(nextDefinitions);
      setRuns(nextRuns);
      setSelectedDefinitionId(current => nextDefinitions.some((item: WorkflowDefinition) => item.id === current) ? current : (nextDefinitions[0]?.id ?? ""));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Workflow tidak dapat dimuat.");
    } finally {
      setLoading(false);
    }
  }, [request, session]);

  useEffect(() => {
    if (!supabase) { setLoading(false); return; }
    let active = true;
    void supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      setSession(data.session);
      if (!data.session) setLoading(false);
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, next) => {
      if (!active) return;
      setSession(next);
      if (!next) { setDefinitions([]); setRuns([]); setSelectedRun(null); setLoading(false); }
    });
    return () => { active = false; listener.subscription.unsubscribe(); };
  }, [supabase]);

  useEffect(() => { if (session) void refresh(); }, [session, refresh]);

  async function createDefinition(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true); setError(""); setNotice("");
    try {
      const definition = JSON.parse(definitionText);
      const result = await request("/v1/workflows/definitions", { method: "POST", body: JSON.stringify({ definition }) });
      setNotice("Versi workflow berhasil disimpan melalui API kanonis.");
      await refresh();
      if (result?.definition?.id) setSelectedDefinitionId(result.definition.id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Definisi workflow tidak dapat disimpan. Periksa format JSON dan schema.");
    } finally { setSaving(false); }
  }

  async function createRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedDefinitionId) { setError("Pilih definisi workflow terlebih dahulu."); return; }
    setSaving(true); setError(""); setNotice("");
    try {
      const input_payload = JSON.parse(inputText);
      if (!input_payload || typeof input_payload !== "object" || Array.isArray(input_payload)) {
        throw new Error("Input workflow harus berupa objek JSON.");
      }
      const result = await request(`/v1/workflows/definitions/${encodeURIComponent(selectedDefinitionId)}/runs`, {
        method: "POST", body: JSON.stringify({ input_payload })
      });
      setNotice("Run dibuat dan tersimpan. Worker memprosesnya secara terpisah; pembuatan run tidak mengeksekusi node secara langsung.");
      await refresh();
      if (result?.run?.id) {
        const detail = await request(`/v1/workflows/runs/${encodeURIComponent(result.run.id)}`);
        setSelectedRun(detail.run ?? result.run);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Workflow run gagal dibuat.");
    } finally { setSaving(false); }
  }

  async function inspectRun(runId: string) {
    setError("");
    try {
      const result = await request(`/v1/workflows/runs/${encodeURIComponent(runId)}`);
      setSelectedRun(result.run ?? null);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Detail run tidak dapat dimuat."); }
  }

  async function cancelRun(runId: string) {
    setSaving(true); setError(""); setNotice("");
    try {
      const result = await request(`/v1/workflows/runs/${encodeURIComponent(runId)}/cancel`, { method: "POST" });
      setNotice("Permintaan pembatalan diproses oleh Workflow Engine.");
      setSelectedRun(result?.run ?? null);
      await refresh();
      await inspectRun(runId);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Run tidak dapat dibatalkan."); }
    finally { setSaving(false); }
  }

  if (!supabase) return <main className="identity-shell"><section className="config-card"><span className="section-kicker">WORKFLOW ENGINE / KONFIGURASI</span><h1>Konfigurasi autentikasi belum tersedia.</h1><p>Atur NEXT_PUBLIC_SUPABASE_URL dan NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY untuk mengaktifkan sesi login. Kunci service-role tidak boleh berada di browser.</p></section></main>;

  return <main className="identity-shell">
    <header className="identity-topbar">
      <Link href="/" className="brand"><span className="brand-mark">α</span> ALLPHA</Link>
      <div className="account-menu"><span className="top-note">DURABLE WORKFLOW</span>{session ? <span className="signed-in">{session.user.email ?? session.user.id}</span> : <Link className="button-quiet" href="/">Masuk</Link>}</div>
    </header>
    <section className="workspace-heading">
      <div><span className="section-kicker">ENG-P11 · CHECKPOINT / RESUME</span><h1>Workflow Engine</h1><p>Kelola definisi berversi, buat run yang durable, pantau checkpoint, dan batalkan run melalui API kanonis.</p></div>
      <button className="button-quiet" type="button" onClick={() => void refresh()} disabled={!session || loading}>Muat ulang</button>
    </section>
    {!session ? <section className="panel auth-panel"><div className="panel-heading"><h2>Login diperlukan</h2><p>Masuk melalui halaman Allpha, lalu buka kembali halaman Workflow Engine.</p></div><Link href="/" className="button-primary">Buka halaman masuk</Link></section> : <>
      {error && <div className="notice error" role="alert">{error} <button className="text-button" onClick={() => void refresh()} type="button">Coba lagi</button></div>}
      {notice && <div className="notice success" role="status">{notice}</div>}
      <div className="workspace-grid">
        <section className="panel workspace-panel">
          <div className="panel-heading"><span className="section-kicker">DEFINITION / VERSIONED JSON</span><h2>Definisi workflow</h2><p>Schema tervalidasi, node deklaratif, tanpa arbitrary code.</p></div>
          <form onSubmit={createDefinition}>
            <label>Workflow definition (JSON)<textarea rows={17} value={definitionText} onChange={event => setDefinitionText(event.target.value)} spellCheck={false} required /></label>
            <button className="button-primary full-width" disabled={saving}>{saving ? "Menyimpan…" : "Validasi & simpan versi"}</button>
          </form>
          <div className="list-heading"><h3>Definisi tersimpan</h3><span>{definitions.length}</span></div>
          {loading ? <p className="muted-copy">Memuat definisi…</p> : definitions.length === 0 ? <p className="empty-state">Belum ada definisi. Simpan definisi JSON untuk memulai.</p> : <div className="workflow-list">{definitions.map(item => <button type="button" key={item.id} className={selectedDefinitionId === item.id ? "workflow-list-item selected" : "workflow-list-item"} onClick={() => setSelectedDefinitionId(item.id)}><strong>{item.workflow_key} <small>v{item.version}</small></strong><span>{item.status} · {item.id}</span></button>)}</div>}
        </section>
        <div className="workflow-column">
          <section className="panel workspace-panel">
            <div className="panel-heading"><span className="section-kicker">RUN / DURABLE CHECKPOINTS</span><h2>Buat workflow run</h2><p>Run disimpan oleh backend. Eksekusi terjadi melalui worker yang dikonfigurasi secara terpisah.</p></div>
            <form onSubmit={createRun}>
              <label>Definisi<select value={selectedDefinitionId} onChange={event => setSelectedDefinitionId(event.target.value)} required><option value="">Pilih definisi</option>{definitions.map(item => <option key={item.id} value={item.id}>{item.workflow_key} · v{item.version}</option>)}</select></label>
              <label>Input payload (JSON object)<textarea rows={4} value={inputText} onChange={event => setInputText(event.target.value)} spellCheck={false} required /></label>
              <button className="button-primary full-width" disabled={saving || !definitions.length}>{saving ? "Memproses…" : "Buat run"}</button>
            </form>
          </section>
          <section className="panel workspace-panel">
            <div className="list-heading"><div><span className="section-kicker">PERSISTED RUNS</span><h2>Riwayat run</h2></div><span>{runs.length}</span></div>
            {loading ? <p className="muted-copy">Memuat run…</p> : runs.length === 0 ? <p className="empty-state">Belum ada run workflow.</p> : <div className="workflow-list">{runs.map(run => <div key={run.id} className="run-row"><button type="button" className="run-select" onClick={() => void inspectRun(run.id)}><strong>{run.status}</strong><span>{run.id}</span><small>{new Date(run.created_at).toLocaleString("id-ID")}</small></button>{["queued", "running", "created"].includes(run.status) && <button type="button" className="button-danger" disabled={saving} onClick={() => void cancelRun(run.id)}>Batalkan</button>}</div>)}</div>}
          </section>
        </div>
      </div>
      {selectedRun && <section className="panel workspace-panel run-detail">
        <div className="list-heading"><div><span className="section-kicker">RUN DETAIL / TRACE</span><h2>Detail run</h2></div><button type="button" className="button-quiet" onClick={() => void inspectRun(selectedRun.id)}>Refresh detail</button></div>
        <p className="detail-id">Run ID: {selectedRun.id}</p><p>Status: <strong>{selectedRun.status}</strong> · Version: {selectedRun.definition_version} · Trace: {selectedRun.trace_id}</p>
        <h3>Steps / checkpoints</h3>
        {!selectedRun.steps?.length ? <p className="empty-state">Belum ada step yang dikembalikan.</p> : <div className="workflow-list">{selectedRun.steps.map(step => <article className="step-row" key={step.id}><strong>{step.node_key} <small>({step.node_kind})</small></strong><span>Status: {step.status}</span>{step.error_code && <span className="notice error">{step.error_code}</span>}{step.output_payload && <pre>{JSON.stringify(step.output_payload, null, 2)}</pre>}</article>)}</div>}
        <h3>Event log</h3>
        {!selectedRun.events?.length ? <p className="empty-state">Belum ada event.</p> : <ol className="workflow-events">{selectedRun.events.map(event => <li key={event.sequence}><strong>{event.event_type}</strong>{event.step_key && <span> · {event.step_key}</span>}<small>{new Date(event.created_at).toLocaleString("id-ID")}</small></li>)}</ol>}
      </section>}
    </>}
  </main>;
}

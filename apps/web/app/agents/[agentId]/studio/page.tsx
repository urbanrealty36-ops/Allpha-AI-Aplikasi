"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../../../lib/supabase";

type KnowledgeSource = { id: string; filename: string; size_bytes: number; status: string; processing_stage: string; error_code?: string | null; sha256: string; created_at: string; latest_job?: { id: string; status: string; stage: string; attempt: number; progress: number; error_code?: string | null } | null };
type RetrievalResult = { source_id: string; source_version: number; chunk_id: string; content: string; content_sha256: string; source_location: Record<string, unknown>; sensitivity: string; retrieval_method: "vector" | "keyword" | "hybrid"; score: number; provider_id?: string | null; model_id?: string | null; model_version?: string | null; index_generation?: string | null };
type RetrievalResponse = { trace_id: string; results: RetrievalResult[] };
type Skill = {
  id: string; agent_id: string; slug: string; name: string; description: string;
  category: string; instructions: string; required_permission_scopes: string[];
  tool_dependencies: string[]; version: number; status: "draft" | "published" | "archived";
  changelog?: string; updated_at?: string;
};
type RegisteredTool = { key: string; version: string; name: string; description: string; risk_level: string; required_permission_scopes: string[]; executable: boolean };
type Capability = {
  id: string; capability_key: string; description: string; risk_level: string;
  status: "requested" | "approved" | "denied" | "revoked"; required_permission_scopes: string[];
};
type SkillVersion = { id: string; version: number; created_at: string; snapshot: { name?: string; changelog?: string; status?: string } };
const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function readError(response: Response) {
  try {
    const body = await response.json();
    return body?.error?.message ?? body?.detail?.message ?? `Permintaan gagal (${response.status}).`;
  } catch { return `Permintaan gagal (${response.status}).`; }
}

export default function AgentStudioPage() {
  const params = useParams<{ agentId: string }>();
  const agentId = params.agentId;
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [knowledgeSources, setKnowledgeSources] = useState<KnowledgeSource[]>([]);
  const [retrievalQuery, setRetrievalQuery] = useState("");
  const [retrievalResults, setRetrievalResults] = useState<RetrievalResult[]>([]);
  const [retrievalTraceId, setRetrievalTraceId] = useState("");
  const [retrievalLoading, setRetrievalLoading] = useState(false);
  const [retrievalError, setRetrievalError] = useState("");
  const retrievalRequestSequence = useRef(0);
  useEffect(() => { retrievalRequestSequence.current += 1; setRetrievalResults([]); setRetrievalTraceId(""); setRetrievalError(""); setRetrievalLoading(false); }, [agentId]);
  const [knowledgeFile, setKnowledgeFile] = useState<File | null>(null);
  const [registeredTools, setRegisteredTools] = useState<RegisteredTool[]>([]);
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [versionHistory, setVersionHistory] = useState<{ skillId: string; items: SkillVersion[] } | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [slug, setSlug] = useState("");
  const [name, setName] = useState("");
  const [editingSkillId, setEditingSkillId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editInstructions, setEditInstructions] = useState("");
  const [editScopes, setEditScopes] = useState("");
  const [editToolDependencies, setEditToolDependencies] = useState("");
  const [editChangelog, setEditChangelog] = useState("");
  const [description, setDescription] = useState("");
  const [instructions, setInstructions] = useState("");
  const [scope, setScope] = useState("");
  const [category, setCategory] = useState("general");
  const [inputSchema, setInputSchema] = useState('{"type":"object"}');
  const [outputSchema, setOutputSchema] = useState('{"type":"object"}');
  const [toolDependencies, setToolDependencies] = useState("");
  const [budgetSeconds, setBudgetSeconds] = useState("30");
  const [budgetToolCalls, setBudgetToolCalls] = useState("5");
  const [modelRequirements, setModelRequirements] = useState("{}");
  const [skillTests, setSkillTests] = useState("[]");
  const [evaluationRubric, setEvaluationRubric] = useState("{}");
  const [provenance, setProvenance] = useState("{}");
  const [publicationTerms, setPublicationTerms] = useState("{}");
  const [changelog, setChangelog] = useState("Versi awal");
  const [capabilityKey, setCapabilityKey] = useState("");
  const [capabilityDescription, setCapabilityDescription] = useState("");
  const [riskLevel, setRiskLevel] = useState<"low" | "medium" | "high" | "critical">("low");

  const load = useCallback(async (active: Session) => {
    setLoading(true); setError("");
    try {
      const headers = { Authorization: "Bearer " + active.access_token };
      const [skillResponse, capabilityResponse, toolsResponse, knowledgeResponse] = await Promise.all([
        fetch(`${apiBase}/v1/agents/${agentId}/skills`, { headers, cache: "no-store" }),
        fetch(`${apiBase}/v1/agents/${agentId}/capabilities`, { headers, cache: "no-store" }),
        fetch(`${apiBase}/v1/tools`, { headers, cache: "no-store" }),
        fetch(`${apiBase}/v1/agents/${agentId}/knowledge/sources`, { headers, cache: "no-store" }),
      ]);
      if (!skillResponse.ok) throw new Error(await readError(skillResponse));
      if (!capabilityResponse.ok) throw new Error(await readError(capabilityResponse));
      if (!toolsResponse.ok) throw new Error(await readError(toolsResponse));
      if (!knowledgeResponse.ok) throw new Error(await readError(knowledgeResponse));
      const [skillBody, capabilityBody, toolsBody, knowledgeBody] = await Promise.all([skillResponse.json(), capabilityResponse.json(), toolsResponse.json(), knowledgeResponse.json()]);
      setSkills(Array.isArray(skillBody.items) ? skillBody.items : []);
      setCapabilities(Array.isArray(capabilityBody.items) ? capabilityBody.items : []);
      setRegisteredTools(Array.isArray(toolsBody.items) ? toolsBody.items.filter((tool: RegisteredTool) => tool.executable) : []);
      setKnowledgeSources(Array.isArray(knowledgeBody.items) ? knowledgeBody.items : []);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Agent Studio tidak dapat dimuat.");
    } finally { setLoading(false); }
  }, [agentId]);

  useEffect(() => {
    if (!supabase) { setLoading(false); setError("Konfigurasi autentikasi belum tersedia."); return; }
    let active = true;
    void supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      setSession(data.session);
      if (data.session) void load(data.session);
      else { setLoading(false); setError("Masuk terlebih dahulu untuk membuka Agent Studio."); }
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, next) => {
      if (!active) return;
      setSession(next);
      if (next) void load(next);
      else { setSkills([]); setCapabilities([]); setKnowledgeSources([]); setLoading(false); setError("Sesi berakhir. Silakan masuk kembali."); }
    });
    return () => { active = false; listener.subscription.unsubscribe(); };
  }, [supabase, load]);

  async function createSkill(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session) return;
    setSaving(true); setError(""); setNotice("");
    try {
      const response = await fetch(`${apiBase}/v1/agents/${agentId}/skills`, {
        method: "POST", headers: { Authorization: "Bearer " + session.access_token, "Content-Type": "application/json" },
        body: JSON.stringify({
          slug: slug.trim().toLowerCase(), name: name.trim(), description: description.trim(),
          instructions: instructions.trim(), category: category.trim() || "general",
          inputs_schema: JSON.parse(inputSchema), outputs_schema: JSON.parse(outputSchema),
          tool_dependencies: toolDependencies.split(",").map(x => x.trim()).filter(Boolean),
          required_permission_scopes: scope.split(",").map(x => x.trim()).filter(Boolean),
          constraints: { external_actions_require_owner_approval: true },
          budget_limits: { max_runtime_seconds: Number(budgetSeconds), max_tool_calls: Number(budgetToolCalls) },
          model_requirements: JSON.parse(modelRequirements), tests: JSON.parse(skillTests),
          evaluation_rubric: JSON.parse(evaluationRubric), provenance: JSON.parse(provenance),
          publication_terms: JSON.parse(publicationTerms), changelog: changelog.trim(),
        }),
      });
      if (!response.ok) throw new Error(await readError(response));
      setSlug(""); setName(""); setDescription(""); setInstructions(""); setScope("");
      setNotice("Skill tersimpan sebagai draft. Definisi Skill tidak memberikan izin eksekusi otomatis.");
      await load(session);
    } catch (cause) { setError(cause instanceof SyntaxError ? "JSON Schema, tests, model requirements, rubric, provenance, dan terms harus berupa JSON valid." : cause instanceof Error ? cause.message : "Skill tidak dapat disimpan."); }
    finally { setSaving(false); }
  }

  async function retrieveKnowledge() {
    if (!session || !retrievalQuery.trim() || retrievalLoading) return;
    const requestSequence = ++retrievalRequestSequence.current;
    setRetrievalLoading(true); setRetrievalError(""); setRetrievalResults([]); setRetrievalTraceId("");
    try {
      const response = await fetch(`${apiBase}/v1/agents/${encodeURIComponent(agentId)}/knowledge/retrieve`, {
        method: "POST",
        headers: { Authorization: "Bearer " + session.access_token, Accept: "application/json", "Content-Type": "application/json" },
        body: JSON.stringify({ query: retrievalQuery.trim(), limit: 8 }),
        cache: "no-store",
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body?.error?.message ?? body?.detail?.message ?? `Retrieval gagal (${response.status}).`);
      if (requestSequence !== retrievalRequestSequence.current) return;
      const payload = body as RetrievalResponse;
      setRetrievalTraceId(typeof payload.trace_id === "string" ? payload.trace_id : "");
      setRetrievalResults(Array.isArray(payload.results) ? payload.results : []);
    } catch (cause) {
      if (requestSequence === retrievalRequestSequence.current) setRetrievalError(cause instanceof Error ? cause.message : "Retrieval tidak dapat dijalankan.");
    } finally { if (requestSequence === retrievalRequestSequence.current) setRetrievalLoading(false); }
  }

  async function uploadKnowledge(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session || !knowledgeFile) return;
    setSaving(true); setError(""); setNotice("");
    try {
      const form = new FormData(); form.append("file", knowledgeFile);
      const response = await fetch(`${apiBase}/v1/agents/${agentId}/knowledge/sources`, { method: "POST", headers: { Authorization: "Bearer " + session.access_token }, body: form });
      if (!response.ok) throw new Error(await readError(response));
      setKnowledgeFile(null); setNotice("Dokumen masuk karantina privat. Pemrosesan baru dapat dilanjutkan setelah pemindai malware terkonfigurasi.");
      await load(session);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Dokumen gagal diunggah."); }
    finally { setSaving(false); }
  }

  async function knowledgeAction(source: KnowledgeSource, action: "process" | "retry" | "delete") {
    if (!session) return;
    setSaving(true); setError(""); setNotice("");
    try {
      const response = await fetch(`${apiBase}/v1/agents/${agentId}/knowledge/sources/${source.id}${action === "delete" ? "" : "/" + action}`, {
        method: action === "delete" ? "DELETE" : "POST",
        headers: { Authorization: "Bearer " + session.access_token, ...(action === "retry" ? { "Content-Type": "application/json" } : {}) },
        ...(action === "retry" ? { body: JSON.stringify({ reason: "retry dari Agent Studio" }) } : {}),
      });
      if (!response.ok) throw new Error(await readError(response));
      setNotice(action === "delete" ? "Sumber dan turunannya telah diminta untuk dihapus." : "Permintaan pemrosesan telah dijalankan. Status aktual ditampilkan pada daftar sumber.");
      await load(session);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Operasi sumber pengetahuan gagal."); }
    finally { setSaving(false); }
  }

  function beginSkillEdit(skill: Skill) {
    setEditingSkillId(skill.id);
    setEditName(skill.name);
    setEditDescription(skill.description || "");
    setEditInstructions(skill.instructions || "");
    setEditScopes(skill.required_permission_scopes?.join(", ") || "");
    setEditToolDependencies(skill.tool_dependencies?.join(", ") || "");
    setEditChangelog("Perubahan versi " + (skill.version + 1));
    setError(""); setNotice("");
  }

  async function saveSkillEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session || !editingSkillId) return;
    setSaving(true); setError(""); setNotice("");
    try {
      const response = await fetch(`${apiBase}/v1/agents/${agentId}/skills/${editingSkillId}`, {
        method: "PATCH",
        headers: { Authorization: "Bearer " + session.access_token, "Content-Type": "application/json" },
        body: JSON.stringify({
          name: editName.trim(), description: editDescription.trim(), instructions: editInstructions.trim(),
          required_permission_scopes: editScopes.split(",").map(x => x.trim()).filter(Boolean),
          tool_dependencies: editToolDependencies.split(",").map(x => x.trim()).filter(Boolean),
          changelog: editChangelog.trim(),
        }),
      });
      if (!response.ok) throw new Error(await readError(response));
      setEditingSkillId(null);
      setNotice("Perubahan Skill tersimpan sebagai versi baru. Riwayat versi diperbarui oleh database.");
      setVersionHistory(null);
      await load(session);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Perubahan Skill tidak dapat disimpan.");
    } finally { setSaving(false); }
  }

  async function loadSkillVersions(skill: Skill) {
    if (!session) return;
    setHistoryLoading(true); setError(""); setNotice("");
    try {
      const response = await fetch(`${apiBase}/v1/agents/${agentId}/skills/${skill.id}/versions`, {
        headers: { Authorization: "Bearer " + session.access_token }, cache: "no-store",
      });
      if (!response.ok) throw new Error(await readError(response));
      const body = await response.json();
      setVersionHistory({ skillId: skill.id, items: Array.isArray(body.items) ? body.items : [] });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Riwayat versi tidak dapat dimuat.");
    } finally { setHistoryLoading(false); }
  }

  async function requestCapability(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session) return;
    setSaving(true); setError(""); setNotice("");
    try {
      const response = await fetch(`${apiBase}/v1/agents/${agentId}/capabilities`, {
        method: "POST", headers: { Authorization: "Bearer " + session.access_token, "Content-Type": "application/json" },
        body: JSON.stringify({
          capability_key: capabilityKey.trim().toLowerCase(), description: capabilityDescription.trim(),
          required_permission_scopes: scope.split(",").map(x => x.trim()).filter(Boolean), risk_level: riskLevel,
        }),
      });
      if (!response.ok) throw new Error(await readError(response));
      setCapabilityKey(""); setCapabilityDescription("");
      setNotice("Capability dicatat sebagai permintaan. Runtime tetap wajib memeriksa izin setiap tindakan.");
      await load(session);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Capability tidak dapat diminta."); }
    finally { setSaving(false); }
  }

  if (!session && !loading) return <main className="mx-auto max-w-4xl p-6"><h1 className="text-2xl font-semibold">Agent Studio</h1><p className="mt-3 text-sm">{error || "Masuk untuk melanjutkan."}</p></main>;

  return <main className="mx-auto max-w-6xl space-y-6 p-4 sm:p-6">
    <header className="flex flex-wrap items-end justify-between gap-3 border-b pb-5">
      <div><p className="text-xs font-semibold uppercase tracking-[0.18em] text-neutral-500">Allpha · Agent Studio</p><h1 className="mt-2 text-3xl font-semibold tracking-tight">Skills & Capabilities</h1><p className="mt-2 max-w-2xl text-sm text-neutral-600">Kelola prosedur reusable, versi, dependensi tool, dan permintaan kemampuan Agent. Otorisasi selalu diputuskan ulang saat runtime.</p></div>
      <button className="rounded-xl border px-4 py-2 text-sm font-medium" onClick={() => session && void load(session)} disabled={loading}>{loading ? "Memuat…" : "Muat ulang"}</button>
    </header>
    {error && <div role="alert" className="rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-900">{error}</div>}
    {notice && <div role="status" className="rounded-xl border p-3 text-sm">{notice}</div>}
    <section className="space-y-4 rounded-2xl border p-4 sm:p-5">
      <div><h2 className="text-xl font-semibold">Sumber pengetahuan</h2><p className="mt-1 text-sm text-neutral-600">PDF, Markdown, TXT, DOCX · maksimum 15 MiB. Dokumen tetap privat dan dikarantina sampai pemeriksaan malware berhasil; status indexed belum berarti siap untuk retrieval.</p></div>
      <form onSubmit={uploadKnowledge} className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <label className="grid flex-1 gap-1 text-sm">Pilih dokumen<input type="file" accept=".pdf,.md,.txt,.docx,application/pdf,text/markdown,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={e => setKnowledgeFile(e.target.files?.[0] || null)} className="rounded-lg border p-2" required /></label>
        <button disabled={saving || !session || !knowledgeFile} className="rounded-xl bg-neutral-900 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50">{saving ? "Memproses…" : "Unggah ke karantina"}</button>
      </form>
      <div className="space-y-3">{knowledgeSources.length === 0 ? <p className="rounded-xl border border-dashed p-4 text-sm text-neutral-600">Belum ada sumber pengetahuan.</p> : knowledgeSources.map(source => <article key={source.id} className="rounded-xl border p-3">
        <div className="flex flex-wrap items-start justify-between gap-2"><div><h3 className="font-semibold">{source.filename}</h3><p className="mt-1 text-xs text-neutral-500">{(source.size_bytes / 1024).toFixed(1)} KiB · SHA-256 {source.sha256.slice(0, 12)}…</p></div><span className="rounded-full border px-2 py-1 text-xs">{source.status}</span></div>
        <p className="mt-2 text-sm text-neutral-600">Tahap: {source.processing_stage}{source.error_code ? " · " + source.error_code : ""}</p>{source.latest_job && <p className="mt-1 text-xs text-neutral-500">Job: {source.latest_job.status} · {source.latest_job.stage} · {source.latest_job.progress}% · percobaan {source.latest_job.attempt}{source.latest_job.error_code ? " · " + source.latest_job.error_code : ""}</p>}
        <div className="mt-3 flex flex-wrap gap-2">{(source.status === "quarantined" || source.status === "failed") && <button type="button" disabled={saving} onClick={() => void knowledgeAction(source, source.status === "failed" ? "retry" : "process")} className="rounded-lg border px-3 py-1.5 text-xs disabled:opacity-50">{source.status === "failed" ? "Coba lagi" : "Proses dokumen"}</button>}<button type="button" disabled={saving} onClick={() => { if (window.confirm("Hapus dokumen dan seluruh chunk terkait?")) void knowledgeAction(source, "delete"); }} className="rounded-lg border border-red-300 px-3 py-1.5 text-xs text-red-700 disabled:opacity-50">Hapus</button></div>
      </article>)}</div>
    </section>
    <section className="space-y-4 rounded-2xl border p-4 sm:p-5">
      <div><h2 className="text-xl font-semibold">Uji retrieval & konteks Agent</h2><p className="mt-1 text-sm text-neutral-600">Mengambil potongan knowledge milik Agent ini melalui API terautentikasi. Ini adalah preview konteks retrieval, bukan respons generatif Agent. Sensitivitas dan akses ditentukan server.</p></div>
      <form className="flex flex-col gap-3 sm:flex-row sm:items-end" onSubmit={event => { event.preventDefault(); void retrieveKnowledge(); }}>
        <label className="grid flex-1 gap-1 text-sm">Pertanyaan / query konteks<textarea value={retrievalQuery} onChange={event => setRetrievalQuery(event.target.value)} maxLength={4000} rows={3} required placeholder="Contoh: temukan kebijakan yang relevan untuk pertanyaan ini" className="rounded-lg border px-3 py-2" /></label>
        <button type="submit" disabled={retrievalLoading || !session || !retrievalQuery.trim()} className="rounded-xl bg-neutral-900 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50">{retrievalLoading ? "Mengambil konteks…" : "Ambil konteks dari API"}</button>
      </form>
      {retrievalLoading && <div role="status" className="flex items-center gap-2 rounded-xl border p-3 text-sm"><span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-neutral-300 border-t-neutral-900" /> API sedang mencari knowledge yang diizinkan…</div>}
      {retrievalError && <div role="alert" className="space-y-2 rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-900"><p>{retrievalError}</p><p className="text-xs">Jika retrieval belum dikonfigurasi (503), hasil tidak dibuat dari data contoh. Pastikan mode keyword dan policy server disetel secara eksplisit.</p><button type="button" onClick={() => void retrieveKnowledge()} disabled={retrievalLoading || !retrievalQuery.trim()} className="rounded-lg border border-red-400 px-3 py-1.5 font-medium disabled:opacity-50">Coba lagi</button></div>}
      {!retrievalLoading && !retrievalError && retrievalTraceId && <p role="status" className="text-xs text-neutral-500">Trace ID: <code>{retrievalTraceId}</code> · sumber hasil berasal dari API Allpha.</p>}
      {!retrievalLoading && !retrievalError && retrievalTraceId && retrievalResults.length === 0 && <p className="rounded-xl border border-dashed p-4 text-sm text-neutral-600">API mengembalikan 0 hasil untuk query ini.</p>}
      <div className="space-y-3">{retrievalResults.map((item, index) => <article key={item.chunk_id} className="space-y-2 rounded-xl border p-3">
        <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-semibold">Potongan {index + 1} · {item.source_id} · v{item.source_version}</h3><span className="rounded-full border px-2 py-1 text-xs">{item.retrieval_method} · skor {Number.isFinite(item.score) ? item.score.toFixed(3) : "—"}</span></div>
        <p className="whitespace-pre-wrap break-words text-sm">{item.content}</p>
        <dl className="grid gap-1 text-xs text-neutral-500 sm:grid-cols-2"><div><dt className="inline font-medium">Chunk: </dt><dd className="inline break-all">{item.chunk_id}</dd></div><div><dt className="inline font-medium">Sensitivitas: </dt><dd className="inline">{item.sensitivity}</dd></div><div><dt className="inline font-medium">SHA-256: </dt><dd className="inline break-all">{item.content_sha256}</dd></div><div><dt className="inline font-medium">Lokasi sumber: </dt><dd className="inline break-words">{JSON.stringify(item.source_location)}</dd></div></dl>
        {(item.provider_id || item.model_id || item.model_version || item.index_generation) && <p className="text-xs text-neutral-500">Indeks: {[item.provider_id, item.model_id, item.model_version, item.index_generation].filter(Boolean).join(" · ")}</p>}
      </article>)}</div>
    </section>
    <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
      <section className="space-y-4 rounded-2xl border p-4 sm:p-5">
        <div><h2 className="text-xl font-semibold">Skill Agent</h2><p className="mt-1 text-sm text-neutral-600">Setiap Skill memiliki skema, instruksi, batasan, scope, budget, tes, dan versi.</p></div>
        <form onSubmit={createSkill} className="grid gap-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="grid gap-1 text-sm">Slug unik<input required pattern="[a-z0-9][a-z0-9_-]{2,59}" value={slug} onChange={e => setSlug(e.target.value)} className="rounded-lg border px-3 py-2" placeholder="summarize_text"/></label>
            <label className="grid gap-1 text-sm">Nama Skill<input required minLength={2} value={name} onChange={e => setName(e.target.value)} className="rounded-lg border px-3 py-2" placeholder="Ringkas teks"/></label>
          </div>
          <label className="grid gap-1 text-sm">Deskripsi<textarea value={description} onChange={e => setDescription(e.target.value)} maxLength={2000} rows={2} className="rounded-lg border px-3 py-2"/></label>
          <label className="grid gap-1 text-sm">Instruksi prosedural<textarea value={instructions} onChange={e => setInstructions(e.target.value)} maxLength={12000} rows={3} className="rounded-lg border px-3 py-2" placeholder="Langkah-langkah dan batasan Skill"/></label>
          <label className="grid gap-1 text-sm">Kategori<input value={category} onChange={e => setCategory(e.target.value)} maxLength={60} className="rounded-lg border px-3 py-2" placeholder="general"/></label>
          <label className="grid gap-1 text-sm">Input JSON Schema<textarea required value={inputSchema} onChange={e => setInputSchema(e.target.value)} rows={3} className="rounded-lg border px-3 py-2 font-mono text-xs"/></label>
          <label className="grid gap-1 text-sm">Output JSON Schema<textarea required value={outputSchema} onChange={e => setOutputSchema(e.target.value)} rows={3} className="rounded-lg border px-3 py-2 font-mono text-xs"/></label>
          <fieldset className="grid gap-2 text-sm"><legend className="font-medium">Tool dependencies dari registry</legend>{registeredTools.length ? registeredTools.map(tool => <label key={tool.key} className="flex items-start gap-2 rounded-lg border p-3"><input type="checkbox" checked={toolDependencies.split(",").map(x => x.trim()).includes(tool.key)} onChange={e => setToolDependencies(current => { const selected = current.split(",").map(x => x.trim()).filter(Boolean); return (e.target.checked ? [...selected, tool.key] : selected.filter(key => key !== tool.key)).join(", "); })} className="mt-1"/><span><strong>{tool.name}</strong> <span className="text-neutral-500">{tool.key} · v{tool.version} · {tool.risk_level}</span><span className="block text-neutral-600">{tool.description}</span></span></label>) : <p className="text-neutral-500">Tidak ada tool executable di registry atau katalog belum termuat.</p>}</fieldset>
          <label className="grid gap-1 text-sm">Permission scopes (pisahkan koma)<input value={scope} onChange={e => setScope(e.target.value)} className="rounded-lg border px-3 py-2" placeholder="content:read"/></label>
          <div className="grid gap-3 sm:grid-cols-2"><label className="grid gap-1 text-sm">Batas runtime (detik)<input type="number" min="1" max="3600" value={budgetSeconds} onChange={e => setBudgetSeconds(e.target.value)} className="rounded-lg border px-3 py-2"/></label><label className="grid gap-1 text-sm">Batas tool calls<input type="number" min="0" max="100" value={budgetToolCalls} onChange={e => setBudgetToolCalls(e.target.value)} className="rounded-lg border px-3 py-2"/></label></div>
          <label className="grid gap-1 text-sm">Model requirements (JSON)<textarea value={modelRequirements} onChange={e => setModelRequirements(e.target.value)} rows={2} className="rounded-lg border px-3 py-2 font-mono text-xs"/></label>
          <label className="grid gap-1 text-sm">Test cases (array JSON)<textarea value={skillTests} onChange={e => setSkillTests(e.target.value)} rows={3} className="rounded-lg border px-3 py-2 font-mono text-xs"/></label>
          <label className="grid gap-1 text-sm">Evaluation rubric (JSON)<textarea value={evaluationRubric} onChange={e => setEvaluationRubric(e.target.value)} rows={2} className="rounded-lg border px-3 py-2 font-mono text-xs"/></label>
          <label className="grid gap-1 text-sm">Provenance / sumber (JSON)<textarea value={provenance} onChange={e => setProvenance(e.target.value)} rows={2} className="rounded-lg border px-3 py-2 font-mono text-xs"/></label>
          <label className="grid gap-1 text-sm">Publication / entitlement terms (JSON)<textarea value={publicationTerms} onChange={e => setPublicationTerms(e.target.value)} rows={2} className="rounded-lg border px-3 py-2 font-mono text-xs"/></label>
          <label className="grid gap-1 text-sm">Changelog<input value={changelog} onChange={e => setChangelog(e.target.value)} maxLength={2000} className="rounded-lg border px-3 py-2"/></label>
          <button disabled={saving || !session} className="rounded-xl bg-neutral-900 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50">{saving ? "Menyimpan…" : "Buat Skill draft"}</button>
        </form>
        <div className="space-y-3 border-t pt-4">
          {loading ? <p className="text-sm text-neutral-500">Memuat Skill…</p> : skills.length === 0 ? <p className="rounded-xl border border-dashed p-4 text-sm text-neutral-600">Belum ada Skill untuk Agent ini.</p> : skills.map(skill => <article key={skill.id} className="rounded-xl border p-3">
            <div className="flex flex-wrap items-start justify-between gap-2"><div><h3 className="font-semibold">{skill.name}</h3><p className="text-xs text-neutral-500">{skill.slug} · v{skill.version}</p></div><span className="rounded-full border px-2 py-1 text-xs">{skill.status}</span></div>
            {skill.description && <p className="mt-2 text-sm text-neutral-700">{skill.description}</p>}
            <p className="mt-2 text-xs text-neutral-500">Scopes: {skill.required_permission_scopes?.join(", ") || "belum ditentukan"}</p>
            <div className="mt-3 flex flex-wrap gap-2"><button type="button" onClick={() => beginSkillEdit(skill)} className="rounded-lg border px-3 py-1.5 text-xs font-medium">Edit Skill</button><button type="button" onClick={() => void loadSkillVersions(skill)} disabled={historyLoading} className="rounded-lg border px-3 py-1.5 text-xs font-medium disabled:opacity-50">{historyLoading && versionHistory?.skillId === skill.id ? "Memuat riwayat…" : "Lihat riwayat versi"}</button></div>
            {editingSkillId === skill.id && <form onSubmit={saveSkillEdit} className="mt-3 grid gap-3 rounded-xl bg-neutral-50 p-3">
              <p className="text-sm font-semibold">Edit Skill · menyimpan akan membuat versi baru</p>
              <label className="grid gap-1 text-sm">Nama<input required minLength={2} maxLength={100} value={editName} onChange={e => setEditName(e.target.value)} className="rounded-lg border px-3 py-2"/></label>
              <label className="grid gap-1 text-sm">Deskripsi<textarea maxLength={2000} value={editDescription} onChange={e => setEditDescription(e.target.value)} rows={2} className="rounded-lg border px-3 py-2"/></label>
              <label className="grid gap-1 text-sm">Instruksi<textarea maxLength={12000} value={editInstructions} onChange={e => setEditInstructions(e.target.value)} rows={3} className="rounded-lg border px-3 py-2"/></label>
              <label className="grid gap-1 text-sm">Permission scopes<input value={editScopes} onChange={e => setEditScopes(e.target.value)} className="rounded-lg border px-3 py-2" placeholder="pisahkan koma"/></label>
              <fieldset className="grid gap-2 text-sm"><legend className="font-medium">Tool dependencies dari registry</legend>{registeredTools.map(tool => <label key={tool.key} className="flex items-start gap-2 rounded-lg border p-3"><input type="checkbox" checked={editToolDependencies.split(",").map(x => x.trim()).includes(tool.key)} onChange={e => setEditToolDependencies(current => { const selected = current.split(",").map(x => x.trim()).filter(Boolean); return (e.target.checked ? [...selected, tool.key] : selected.filter(key => key !== tool.key)).join(", "); })} className="mt-1"/><span><strong>{tool.name}</strong> <span className="text-neutral-500">{tool.key} · v{tool.version}</span><span className="block text-neutral-600">{tool.description}</span></span></label>)}</fieldset>
              <label className="grid gap-1 text-sm">Changelog<input maxLength={2000} value={editChangelog} onChange={e => setEditChangelog(e.target.value)} className="rounded-lg border px-3 py-2"/></label>
              <div className="flex gap-2"><button disabled={saving || !session} className="rounded-lg bg-neutral-900 px-3 py-2 text-xs font-medium text-white disabled:opacity-50">{saving ? "Menyimpan…" : "Simpan versi baru"}</button><button type="button" onClick={() => setEditingSkillId(null)} className="rounded-lg border px-3 py-2 text-xs">Batal</button></div>
            </form>}
            {versionHistory?.skillId === skill.id && <div className="mt-3 space-y-2 border-t pt-3"><p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">Riwayat versi tersimpan</p>{versionHistory.items.length === 0 ? <p className="text-sm text-neutral-500">Belum ada snapshot yang dapat ditampilkan.</p> : versionHistory.items.map(version => <div key={version.id} className="rounded-lg bg-neutral-50 p-2 text-sm"><div className="flex justify-between gap-2"><strong>v{version.version} · {version.snapshot?.name || skill.name}</strong><span className="text-xs text-neutral-500">{version.snapshot?.status || "snapshot"}</span></div><p className="mt-1 text-xs text-neutral-600">{version.snapshot?.changelog || "Tanpa changelog"} · {new Date(version.created_at).toLocaleString("id-ID")}</p></div>)}</div>}
          </article>)}
        </div>
      </section>
      <section className="space-y-4 rounded-2xl border p-4 sm:p-5">
        <div><h2 className="text-xl font-semibold">Capability yang diminta</h2><p className="mt-1 text-sm text-neutral-600">Deklarasi ini bukan izin eksekusi. Runtime harus memeriksa izin, policy, dan risiko pada setiap aksi.</p></div>
        <form onSubmit={requestCapability} className="grid gap-3">
          <label className="grid gap-1 text-sm">Capability key<input required pattern="[a-z][a-z0-9_.:-]{2,99}" value={capabilityKey} onChange={e => setCapabilityKey(e.target.value)} className="rounded-lg border px-3 py-2" placeholder="calendar.read"/></label>
          <label className="grid gap-1 text-sm">Tujuan / deskripsi<textarea value={capabilityDescription} onChange={e => setCapabilityDescription(e.target.value)} maxLength={1000} rows={2} className="rounded-lg border px-3 py-2"/></label>
          <label className="grid gap-1 text-sm">Tingkat risiko<select value={riskLevel} onChange={e => setRiskLevel(e.target.value as typeof riskLevel)} className="rounded-lg border px-3 py-2"><option value="low">Rendah</option><option value="medium">Menengah</option><option value="high">Tinggi</option><option value="critical">Kritis</option></select></label>
          <button disabled={saving || !session} className="rounded-xl border px-4 py-2.5 text-sm font-medium disabled:opacity-50">{saving ? "Menyimpan…" : "Ajukan capability"}</button>
        </form>
        <div className="space-y-3 border-t pt-4">
          {capabilities.length === 0 ? <p className="rounded-xl border border-dashed p-4 text-sm text-neutral-600">Belum ada deklarasi capability.</p> : capabilities.map(capability => <article key={capability.id} className="rounded-xl border p-3">
            <div className="flex flex-wrap justify-between gap-2"><h3 className="font-semibold">{capability.capability_key}</h3><span className="rounded-full border px-2 py-1 text-xs">{capability.status}</span></div>
            <p className="mt-1 text-sm text-neutral-600">{capability.description || "Tidak ada deskripsi."}</p>
            <p className="mt-2 text-xs text-neutral-500">Risiko: {capability.risk_level} · Scopes: {capability.required_permission_scopes?.join(", ") || "tidak ada"}</p>
          </article>)}
        </div>
      </section>
    </div>
  </main>;
}

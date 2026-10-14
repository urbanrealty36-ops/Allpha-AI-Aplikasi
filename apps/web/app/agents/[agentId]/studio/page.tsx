"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../../../lib/supabase";

type Skill = {
  id: string; agent_id: string; slug: string; name: string; description: string;
  category: string; instructions: string; required_permission_scopes: string[];
  tool_dependencies: string[]; version: number; status: "draft" | "published" | "archived";
  changelog?: string; updated_at?: string;
};
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
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [versionHistory, setVersionHistory] = useState<{ skillId: string; items: SkillVersion[] } | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [slug, setSlug] = useState("");
  const [name, setName] = useState("");
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
      const [skillResponse, capabilityResponse] = await Promise.all([
        fetch(`${apiBase}/v1/agents/${agentId}/skills`, { headers, cache: "no-store" }),
        fetch(`${apiBase}/v1/agents/${agentId}/capabilities`, { headers, cache: "no-store" }),
      ]);
      if (!skillResponse.ok) throw new Error(await readError(skillResponse));
      if (!capabilityResponse.ok) throw new Error(await readError(capabilityResponse));
      const [skillBody, capabilityBody] = await Promise.all([skillResponse.json(), capabilityResponse.json()]);
      setSkills(Array.isArray(skillBody.items) ? skillBody.items : []);
      setCapabilities(Array.isArray(capabilityBody.items) ? capabilityBody.items : []);
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
      else { setSkills([]); setCapabilities([]); setLoading(false); setError("Sesi berakhir. Silakan masuk kembali."); }
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
          <label className="grid gap-1 text-sm">Tool dependencies (key dipisah koma)<input value={toolDependencies} onChange={e => setToolDependencies(e.target.value)} className="rounded-lg border px-3 py-2" placeholder="content.search, calendar.read"/></label>
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
            <button type="button" onClick={() => void loadSkillVersions(skill)} disabled={historyLoading} className="mt-3 rounded-lg border px-3 py-1.5 text-xs font-medium disabled:opacity-50">{historyLoading && versionHistory?.skillId === skill.id ? "Memuat riwayat…" : "Lihat riwayat versi"}</button>
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

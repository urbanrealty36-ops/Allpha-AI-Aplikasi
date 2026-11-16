"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getBrowserSupabase } from "@/lib/supabase";
import type { StageSlideItem } from "../reference-ui/LiveExperienceStage";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");
type SkillChoice = { id: string; name?: string | null; display_name?: string | null; generation_compatible: boolean; generation_block_reason?: string | null };
type AgentChoice = { agent: { id: string; display_name: string }; skills: SkillChoice[]; capabilities: { capability_key: string }[] };
type RequestPayload = { agent_id: string; skill_id: string; capability_id: string; prompt: string; max_output_tokens: number };
type Quote = { expires_at: string; estimated_credits: number; estimated_usage_units: number; usage_unit: string; model_id: string; policy_version: string; tariff_version: string; agent_snapshot_sha256: string; skill_snapshot_sha256: string; knowledge_context_sha256?: string | null; request: RequestPayload };
type Job = { id: string; status: string; moderation_status?: string; artifact_available?: boolean; error_code?: string | null; input_tokens?: number; output_tokens?: number };
type Outline = { title: string; slides: StageSlideItem[] };

async function authorizedRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const supabase = getBrowserSupabase();
  if (!supabase) throw new Error("Autentikasi belum dikonfigurasi.");
  const { data, error } = await supabase.auth.getSession();
  if (error || !data.session?.access_token) throw new Error("Silakan masuk kembali.");
  const response = await fetch(API_BASE + path, {
    ...init, cache: "no-store",
    headers: {
      Accept: "application/json",
      ...(init.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
      Authorization: "Bearer " + data.session.access_token,
      ...init.headers,
    },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body?.detail?.message || body?.detail || body?.message || "Permintaan Generation gagal.");
  return body as T;
}

function parseOutline(raw: string): Outline | null {
  try {
    const value = JSON.parse(raw) as Record<string, unknown>;
    if (typeof value.title !== "string" || !value.title.trim() || !Array.isArray(value.slides) || value.slides.length < 1 || value.slides.length > 10) return null;
    const slides = value.slides.map(item => {
      if (!item || typeof item !== "object") throw new Error("invalid slide");
      const slide = item as Record<string, unknown>;
      if (typeof slide.title !== "string" || typeof slide.subtitle !== "string" || !Array.isArray(slide.bullets) || !slide.bullets.every(x => typeof x === "string")) throw new Error("invalid slide");
      return { title: slide.title, subtitle: slide.subtitle, bullets: slide.bullets as string[], ...(typeof slide.diagram === "string" ? { diagram: slide.diagram } : {}) };
    });
    return { title: value.title, slides };
  } catch { return null; }
}

export default function LiveStageAgentPrepPanel({ onApply }: { onApply: (topic: string, slides: StageSlideItem[]) => void }) {
  const [agents, setAgents] = useState<AgentChoice[]>([]);
  const [agentId, setAgentId] = useState("");
  const [skillId, setSkillId] = useState("");
  const [capabilityId, setCapabilityId] = useState("");
  const [prompt, setPrompt] = useState("Buat outline presentasi Live Stage selama 10 menit. Sertakan pembukaan, 5–7 slide dengan subtitle dan bullet utama, speaker notes ringkas, transisi antar-slide, serta 5 pertanyaan audience dan jawaban singkat. Kembalikan JSON saja dengan bentuk {\"title\":\"...\",\"slides\":[{\"title\":\"...\",\"subtitle\":\"...\",\"bullets\":[\"...\"],\"diagram\":\"...\"}]}.");
  const [quote, setQuote] = useState<Quote | null>(null);
  const [jobId, setJobId] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [artifact, setArtifact] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const selectedAgent = agents.find(item => item.agent.id === agentId);
  const compatibleSkills = useMemo(() => (selectedAgent?.skills || []).filter(item => item.generation_compatible), [selectedAgent]);
  const selectedSkill = compatibleSkills.find(item => item.id === skillId);
  const outline = useMemo(() => parseOutline(artifact), [artifact]);

  const loadAgents = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const result = await authorizedRequest<{ items: AgentChoice[] }>("/v1/agent-runtime/agents");
      const items = Array.isArray(result.items) ? result.items : [];
      setAgents(items);
      setAgentId(current => items.some(item => item.agent.id === current) ? current : items[0]?.agent.id || "");
    } catch (cause) {
      setAgents([]);
      setError(cause instanceof Error ? cause.message : "Agent Runtime catalog tidak tersedia.");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { void loadAgents(); }, [loadAgents]);
  useEffect(() => {
    const skills = (selectedAgent?.skills || []).filter(item => item.generation_compatible);
    setSkillId(current => skills.some(item => item.id === current) ? current : skills[0]?.id || "");
    const capabilities = selectedAgent?.capabilities || [];
    setCapabilityId(current => capabilities.some(item => item.capability_key === current) ? current : capabilities[0]?.capability_key || "");
    setQuote(null);
  }, [selectedAgent]);

  async function requestQuote() {
    if (!selectedAgent || !selectedSkill || !capabilityId || !prompt.trim()) return;
    setBusy(true); setError(""); setNotice(""); setJob(null); setJobId(""); setArtifact("");
    try {
      const payload: RequestPayload = { agent_id: selectedAgent.agent.id, skill_id: selectedSkill.id, capability_id: capabilityId, prompt: prompt.trim(), max_output_tokens: 2048 };
      const result = await authorizedRequest<Omit<Quote, "request">>("/v1/generation/quote", { method: "POST", body: JSON.stringify(payload) });
      setQuote({ ...result, request: payload });
      setNotice("Quote berhasil dibuat. AI Credits akan di-reserve hanya setelah job dikonfirmasi.");
    } catch (cause) { setQuote(null); setError(cause instanceof Error ? cause.message : "Generation quote belum tersedia."); }
    finally { setBusy(false); }
  }

  async function startGeneration() {
    if (!quote || new Date(quote.expires_at).getTime() <= Date.now()) { setQuote(null); setError("Quote kedaluwarsa. Hitung ulang sebelum menjalankan Generation."); return; }
    if (quote.request.prompt !== prompt.trim() || quote.request.agent_id !== agentId || quote.request.skill_id !== skillId || quote.request.capability_id !== capabilityId) {
      setQuote(null); setError("Prompt, Agent, Skill atau Capability berubah. Hitung ulang quote."); return;
    }
    setBusy(true); setError(""); setNotice("");
    try {
      const body: Record<string, unknown> = {
        ...quote.request,
        quoted_credits: quote.estimated_credits,
        quoted_policy_version: quote.policy_version,
        quoted_tariff_version: quote.tariff_version,
        quoted_model_id: quote.model_id,
        quoted_agent_snapshot_sha256: quote.agent_snapshot_sha256,
        quoted_skill_snapshot_sha256: quote.skill_snapshot_sha256,
      };
      if (quote.knowledge_context_sha256) body.quoted_knowledge_context_sha256 = quote.knowledge_context_sha256;
      const created = await authorizedRequest<{ job_id: string; status: string }>("/v1/generation/jobs", {
        method: "POST", headers: { "Idempotency-Key": globalThis.crypto.randomUUID() }, body: JSON.stringify(body),
      });
      setJobId(created.job_id); setJob({ id: created.job_id, status: created.status }); setQuote(null);
      setNotice("Stage preparation Generation Job dibuat. Output menunggu moderation sebelum dapat diterapkan.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Generation Job gagal dibuat."); }
    finally { setBusy(false); }
  }

  useEffect(() => {
    if (!jobId) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const result = await authorizedRequest<{ job: Job }>("/v1/generation/jobs/" + encodeURIComponent(jobId));
        if (!active) return;
        setJob(result.job);
        if (result.job.status === "succeeded" && result.job.artifact_available) {
          const asset = await authorizedRequest<{ url: string }>("/v1/generation/jobs/" + encodeURIComponent(jobId) + "/artifact");
          const response = await fetch(asset.url, { cache: "no-store" });
          if (!response.ok) throw new Error("Artefak privat tidak dapat diambil.");
          const content = await response.text();
          if (active) setArtifact(content.slice(0, 100000));
          return;
        }
        if (["failed", "cancelled", "pending_reconciliation", "succeeded"].includes(result.job.status)) return;
        timer = setTimeout(poll, 4000);
      } catch (cause) {
        if (!active) return;
        setError(cause instanceof Error ? cause.message : "Status Generation Job tidak tersedia.");
        timer = setTimeout(poll, 8000);
      }
    };
    void poll();
    return () => { active = false; if (timer) clearTimeout(timer); };
  }, [jobId]);

  async function cancelGeneration() {
    if (!jobId || job?.status !== "queued") return;
    setBusy(true); setError("");
    try { await authorizedRequest("/v1/generation/jobs/" + encodeURIComponent(jobId) + "/cancel", { method: "POST" }); setJob(current => current ? { ...current, status: "cancelled" } : current); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Pembatalan belum terkonfirmasi."); }
    finally { setBusy(false); }
  }

  return <section className="mx-auto my-4 max-w-5xl rounded-2xl border-2 border-slate-900 bg-white p-4 shadow-[3px_3px_0px_#0f172a]">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-[10px] font-black uppercase tracking-[.18em] text-violet-700">AI Co-Presenter · WP-07 Vertical Integration</p><h2 className="text-base font-black text-slate-950">Persiapan Live Stage dengan Agent</h2><p className="mt-1 text-xs text-slate-600">Buat outline dan slide melalui Generation Job, moderation, private artifact dan Agent Skill yang diizinkan.</p></div><button type="button" onClick={() => void loadAgents()} disabled={loading || busy} className="rounded-lg border-2 border-slate-900 bg-sky-100 px-3 py-2 text-xs font-bold disabled:opacity-40">Muat ulang Agent</button></div>
    {loading ? <p className="mt-3 text-xs text-slate-600">Memuat Agent milik akun…</p> : agents.length === 0 ? <p className="mt-3 rounded-lg border border-amber-400 bg-amber-50 p-3 text-xs text-amber-900">Belum ada Agent aktif dengan akses yang dapat digunakan.</p> : <>
      <div className="mt-3 grid gap-3 md:grid-cols-3">
        <label className="text-xs font-bold text-slate-700">AI Agent<select value={agentId} onChange={e => { setAgentId(e.target.value); setQuote(null); }} className="mt-1 w-full rounded-lg border border-slate-400 bg-white p-2">{agents.map(item => <option key={item.agent.id} value={item.agent.id}>{item.agent.display_name}</option>)}</select></label>
        <label className="text-xs font-bold text-slate-700">Skill<select value={skillId} onChange={e => { setSkillId(e.target.value); setQuote(null); }} className="mt-1 w-full rounded-lg border border-slate-400 bg-white p-2">{compatibleSkills.map(item => <option key={item.id} value={item.id}>{item.display_name || item.name || item.id}</option>)}</select></label>
        <label className="text-xs font-bold text-slate-700">Capability<select value={capabilityId} onChange={e => { setCapabilityId(e.target.value); setQuote(null); }} className="mt-1 w-full rounded-lg border border-slate-400 bg-white p-2">{(selectedAgent?.capabilities || []).map(item => <option key={item.capability_key} value={item.capability_key}>{item.capability_key}</option>)}</select></label>
      </div>
      <label className="mt-3 block text-xs font-bold text-slate-700">Brief / Topik Stage<textarea value={prompt} onChange={e => { setPrompt(e.target.value); setQuote(null); }} rows={4} maxLength={12000} className="mt-1 w-full rounded-lg border-2 border-slate-900 bg-violet-50 p-3 text-xs text-slate-900"/></label>
      <div className="mt-3 flex flex-wrap gap-2"><button type="button" onClick={() => void requestQuote()} disabled={busy || !selectedSkill || !capabilityId || !prompt.trim()} className="rounded-xl border-2 border-slate-900 bg-violet-200 px-4 py-2 text-xs font-black disabled:opacity-40">{busy ? "Memproses…" : "Hitung AI Credits"}</button><button type="button" onClick={() => void startGeneration()} disabled={busy || !quote} className="rounded-xl border-2 border-slate-900 bg-emerald-200 px-4 py-2 text-xs font-black disabled:opacity-40">Generate Stage Outline</button>{job?.status === "queued" && <button type="button" onClick={() => void cancelGeneration()} disabled={busy} className="rounded-xl border-2 border-slate-900 bg-rose-100 px-4 py-2 text-xs font-black disabled:opacity-40">Batalkan</button>}</div>
      {quote && <p className="mt-3 rounded-xl border border-slate-900 bg-white p-3 text-xs text-slate-800">Estimasi <strong>{quote.estimated_credits.toLocaleString("id-ID")} AI Credits</strong> · {quote.estimated_usage_units.toLocaleString("id-ID")} {quote.usage_unit} · {quote.model_id} · berlaku sampai {new Date(quote.expires_at).toLocaleString("id-ID")}</p>}
      {job && <div className="mt-3 rounded-xl border border-slate-900 bg-sky-50 p-3 text-xs text-slate-800"><strong>Generation Job:</strong> {job.id} · <strong>Status:</strong> {job.status} · <strong>Moderation:</strong> {job.moderation_status || "menunggu" }{job.error_code && <p className="mt-1 text-rose-800">{job.error_code}</p>}</div>}
      {artifact && <div className="mt-3 rounded-xl border-2 border-slate-900 bg-slate-50 p-3"><div className="flex flex-wrap items-center justify-between gap-2"><strong className="text-xs text-slate-900">Private Stage Outline</strong><button type="button" onClick={() => navigator.clipboard?.writeText(artifact)} className="rounded-lg border border-slate-900 bg-white px-3 py-1 text-[10px] font-bold">Salin JSON</button></div><pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap text-[11px] text-slate-800">{artifact}</pre>{outline && <button type="button" onClick={() => onApply(outline.title, outline.slides)} className="mt-3 rounded-xl border-2 border-slate-900 bg-emerald-200 px-4 py-2 text-xs font-black">Terapkan {outline.slides.length} slide ke Stage</button>}</div>}
    </>}
    {error && <p role="alert" className="mt-3 rounded-lg border border-rose-400 bg-rose-50 p-2 text-xs text-rose-800">{error}</p>}
    {notice && <p role="status" className="mt-3 rounded-lg border border-emerald-400 bg-emerald-50 p-2 text-xs text-emerald-800">{notice}</p>}
    <p className="mt-3 text-[10px] leading-4 text-slate-500">Catatan: ini menyiapkan konten presentasi saja. Live media session, camera, microphone, SFU dan recording tetap tidak aktif sampai ADR-WP10-001 disetujui dan provider adapter diaktifkan.</p>
  </section>;
}

"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../lib/supabase";

type Agent = { id: string; display_name: string; description?: string; status: string };
type Skill = { id: string; name?: string; display_name?: string; status: string; version: number };
type Capability = { capability_key: string; status: string };
type Job = { status: string; output_text?: string | null; error_code?: string | null };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

async function errorMessage(response: Response) {
  try { const body = await response.json(); return body?.error?.message || body?.detail?.message || `Permintaan gagal (HTTP ${response.status}).`; }
  catch { return `Permintaan gagal (HTTP ${response.status}).`; }
}
const wait = (ms: number) => new Promise(resolve => window.setTimeout(resolve, ms));

export default function GeneratePage() {
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentId, setAgentId] = useState("");
  const [skills, setSkills] = useState<Skill[]>([]);
  const [skillId, setSkillId] = useState("");
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [capabilityId, setCapabilityId] = useState("");
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState("");
  const [jobId, setJobId] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (!supabase) { setError("Autentikasi Allpha belum dikonfigurasi."); setLoading(false); return; }
    let active = true;
    const load = async (current: Session | null) => {
      setSession(current); setAgents([]); setSkills([]); setCapabilities([]); setAgentId(""); setSkillId(""); setCapabilityId("");
      if (!current) { setLoading(false); return; }
      setLoading(true); setError("");
      try {
        const response = await fetch(apiBase + "/v1/agents", { headers: { Authorization: "Bearer " + current.access_token, Accept: "application/json" }, cache: "no-store" });
        if (!response.ok) throw new Error(await errorMessage(response));
        const data = await response.json() as { items?: Agent[] };
        const eligible = (data.items || []).filter(agent => agent.status === "active");
        if (!active) return;
        setAgents(eligible);
        if (!eligible.length) setError("Belum ada AI Agent aktif milik akun ini.");
      } catch (cause) { if (active) setError(cause instanceof Error ? cause.message : "Agent tidak dapat dimuat."); }
      finally { if (active) setLoading(false); }
    };
    void supabase.auth.getSession().then(({ data }) => load(data.session));
    const { data: listener } = supabase.auth.onAuthStateChange((_event, current) => { void load(current); });
    return () => { active = false; listener.subscription.unsubscribe(); };
  }, [supabase]);

  useEffect(() => {
    if (!session || !agentId) return;
    let active = true;
    const headers = { Authorization: "Bearer " + session.access_token, Accept: "application/json" };
    setSkills([]); setCapabilities([]); setSkillId(""); setCapabilityId(""); setError("");
    void Promise.all([
      fetch(apiBase + `/v1/agents/${agentId}/skills`, { headers, cache: "no-store" }),
      fetch(apiBase + `/v1/agents/${agentId}/capabilities`, { headers, cache: "no-store" }),
    ]).then(async ([skillsResponse, capsResponse]) => {
      if (!skillsResponse.ok) throw new Error(await errorMessage(skillsResponse));
      if (!capsResponse.ok) throw new Error(await errorMessage(capsResponse));
      const skillData = await skillsResponse.json() as { items?: Skill[] };
      const capData = await capsResponse.json() as { items?: Capability[] };
      if (!active) return;
      const published = (skillData.items || []).filter(item => item.status === "published");
      const approved = (capData.items || []).filter(item => item.status === "approved");
      setSkills(published); setCapabilities(approved);
      if (!published.length || !approved.length) setError("Agent ini belum memiliki Skill published dan capability approved.");
      else { setSkillId(published[0].id); setCapabilityId(approved[0].capability_key); }
    }).catch(cause => { if (active) setError(cause instanceof Error ? cause.message : "Skill/capability tidak dapat dimuat."); });
    return () => { active = false; };
  }, [session, agentId]);

  async function generate() {
    if (!session || !agentId || !skillId || !capabilityId || !prompt.trim() || busy) return;
    setBusy(true); setError(""); setNotice(""); setResult(""); setJobId("");
    const headers = { Authorization: "Bearer " + session.access_token, Accept: "application/json", "Content-Type": "application/json" };
    const body = { agent_id: agentId, skill_id: skillId, capability_id: capabilityId, prompt: prompt.trim(), max_output_tokens: 1800 };
    try {
      const quoteResponse = await fetch(apiBase + "/v1/generation/quote", { method: "POST", headers, body: JSON.stringify(body), cache: "no-store" });
      if (!quoteResponse.ok) throw new Error(await errorMessage(quoteResponse));
      const quote = await quoteResponse.json() as { quote_id: string; expires_at: string; estimated_credits: number; model_id: string };
      if (!quote.quote_id || Date.parse(quote.expires_at) <= Date.now() || !Number.isSafeInteger(quote.estimated_credits) || quote.estimated_credits <= 0) {
        throw new Error("Quote generation tidak valid atau sudah kedaluwarsa.");
      }
      if (!window.confirm(`Estimasi: ${quote.estimated_credits.toLocaleString("id-ID")} AI Credits. Model: ${quote.model_id}. Lanjutkan dan reservasi kredit?`)) {
        setNotice("Dibatalkan sebelum reservasi. Tidak ada kredit yang dipotong."); return;
      }
      const createResponse = await fetch(apiBase + "/v1/generation/jobs", {
        method: "POST", headers: { ...headers, "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ ...body, quoted_credits: quote.estimated_credits }), cache: "no-store",
      });
      if (!createResponse.ok) throw new Error(await errorMessage(createResponse));
      const created = await createResponse.json() as { job_id: string };
      if (!created.job_id) throw new Error("Generation Job belum dikonfirmasi.");
      setJobId(created.job_id);
      for (let attempt = 0; attempt < 60; attempt += 1) {
        await wait(2000);
        const statusResponse = await fetch(apiBase + `/v1/generation/jobs/${created.job_id}`, { headers: { Authorization: headers.Authorization, Accept: "application/json" }, cache: "no-store" });
        if (!statusResponse.ok) throw new Error(await errorMessage(statusResponse));
        const payload = await statusResponse.json() as { job?: Job };
        const job = payload.job;
        if (!job) throw new Error("Status generation tidak ditemukan.");
        if (job.status === "succeeded" && job.output_text) { setResult(job.output_text); setNotice("Hasil berhasil disimpan pada Generation Job privat."); return; }
        if (job.status === "failed" || job.status === "cancelled") throw new Error(job.error_code || "Generation gagal.");
        if (job.status === "pending_reconciliation") throw new Error("Outcome provider belum pasti. Job masuk rekonsiliasi dan tidak diulang otomatis.");
      }
      setNotice("Job masih berjalan. Periksa kembali melalui riwayat Generation; permintaan tidak dikirim ulang.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Generation tidak dapat diselesaikan."); }
    finally { setBusy(false); }
  }

  if (!session) return <main className="mx-auto max-w-2xl p-6"><h1 className="text-xl font-black">Generate Content</h1><p className="mt-2 text-sm text-slate-600">Masuk ke Allpha untuk menggunakan Agent dan AI Credits.</p><Link href="/login" className="mt-4 inline-flex rounded-xl bg-slate-950 px-4 py-2 text-white">Masuk</Link></main>;
  return <main className="mx-auto min-h-screen max-w-3xl px-4 py-8 text-slate-950 dark:text-slate-100">
    <header className="mb-6 flex items-center justify-between gap-3">
      <div><p className="text-xs font-black uppercase tracking-[.18em] text-violet-600">Allpha Creator Studio</p><h1 className="mt-1 text-2xl font-black">Generate Content</h1><p className="mt-1 text-sm text-slate-500">Pilih Agent, Skill dan capability yang benar-benar aktif sebelum meminta generation.</p></div>
      <Link href="/feed" className="rounded-xl border border-slate-300 px-3 py-2 text-sm font-bold dark:border-slate-700">Kembali</Link>
    </header>
    <section className="rounded-3xl border-2 border-slate-900 bg-white p-5 shadow-[4px_4px_0px_#0f172a] dark:bg-slate-900 dark:text-white">
      {loading ? <p role="status" className="text-sm">Memuat Agent kanonis…</p> : <>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="text-sm font-bold">AI Agent<select value={agentId} onChange={event => setAgentId(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 bg-transparent p-3 dark:border-slate-700"><option value="">Pilih Agent</option>{agents.map(agent => <option key={agent.id} value={agent.id}>{agent.display_name}</option>)}</select></label>
          <label className="text-sm font-bold">Skill published<select value={skillId} onChange={event => setSkillId(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 bg-transparent p-3 dark:border-slate-700"><option value="">Pilih Skill</option>{skills.map(skill => <option key={skill.id} value={skill.id}>{skill.display_name || skill.name || `Skill v${skill.version}`}</option>)}</select></label>
        </div>
        <label className="mt-4 block text-sm font-bold">Capability approved<select value={capabilityId} onChange={event => setCapabilityId(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 bg-transparent p-3 dark:border-slate-700"><option value="">Pilih capability</option>{capabilities.map(item => <option key={item.capability_key} value={item.capability_key}>{item.capability_key}</option>)}</select></label>
        <label className="mt-4 block text-sm font-bold">Brief / Prompt<textarea value={prompt} onChange={event => setPrompt(event.target.value)} rows={7} maxLength={32768} placeholder="Jelaskan tujuan, audiens, format konten, gaya, konteks brand, dan batasan hasil…" className="mt-2 w-full rounded-xl border border-slate-300 bg-transparent p-3 text-sm font-normal dark:border-slate-700" /></label>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3"><p className="text-xs text-slate-500">Quote dan tarif selalu berasal dari policy aktif. Tidak ada harga default atau kredit buatan.</p><button onClick={() => void generate()} disabled={busy || loading || !agentId || !skillId || !capabilityId || !prompt.trim()} className="rounded-xl border-2 border-slate-900 bg-violet-300 px-5 py-3 text-sm font-black text-slate-950 shadow-[2px_2px_0px_#0f172a] disabled:opacity-50">{busy ? "Memproses…" : "Minta Quote & Generate"}</button></div>
      </>}
    </section>
    {error && <p role="alert" className="mt-4 rounded-xl border border-rose-300 bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
    {notice && <p role="status" className="mt-4 rounded-xl border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900">{notice}</p>}
    {jobId && <p className="mt-3 text-xs text-slate-500">Generation Job: {jobId}</p>}
    {result && <section className="mt-5 rounded-3xl border-2 border-slate-900 bg-slate-950 p-5 text-cyan-100 shadow-[4px_4px_0px_#0f172a]"><div className="mb-3 flex items-center justify-between"><h2 className="font-black">Hasil Generation</h2><button onClick={() => void navigator.clipboard.writeText(result)} className="rounded-lg border border-cyan-200/50 px-3 py-1.5 text-xs font-bold">Salin</button></div><pre className="whitespace-pre-wrap break-words text-sm leading-relaxed">{result}</pre><p className="mt-4 border-t border-white/10 pt-3 text-xs text-cyan-200/70">Hasil tersimpan privat pada Generation Job. DM delivery dan creator reward menunggu integrasi WP-07 berikutnya.</p></section>}
  </main>;
}

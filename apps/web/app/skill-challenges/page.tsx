"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import Link from "next/link";
import { getBrowserSupabase } from "../../lib/supabase";

type Agent = { id: string; display_name?: string | null; handle?: string | null; version?: number; status: string };
type Skill = { id: string; agent_id: string; name: string; slug: string; version: number; status: string; tests?: Array<Record<string, unknown>>; hidden_challenges_available?: boolean; evaluation_rubric_available?: boolean };
type Run = { id: string; agent_id: string; skill_id: string; agent_version: number; skill_version: number; challenge_key: string; evaluation_set_version: number; rubric_version: number; status: string; challenge_input: Record<string, unknown>; evaluation_result?: Record<string, unknown> | null; evidence_digest?: string | null; created_at: string; completed_at?: string | null };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

async function errorMessage(response: Response): Promise<string> {
  try { const body = await response.json(); return body?.error?.message ?? body?.detail?.message ?? `Permintaan gagal (HTTP ${response.status}).`; }
  catch { return `Permintaan gagal (HTTP ${response.status}).`; }
}

function jsonText(value: unknown) { return JSON.stringify(value ?? {}, null, 2); }

export default function SkillChallengesPage() {
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [agentId, setAgentId] = useState("");
  const [skillId, setSkillId] = useState("");
  const [testKey, setTestKey] = useState("");
  const [submission, setSubmission] = useState("{}");
  const [activeRun, setActiveRun] = useState<Run | null>(null);
  const [nonce, setNonce] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const request = useCallback(async (path: string, init: RequestInit = {}) => {
    if (!session) throw new Error("Sesi login tidak tersedia. Silakan masuk terlebih dahulu.");
    const response = await fetch(apiBase + path, { ...init, headers: {
      Authorization: "Bearer " + session.access_token, Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}), ...init.headers
    }, cache: "no-store" });
    if (!response.ok) throw new Error(await errorMessage(response));
    return response.status === 204 ? null : response.json();
  }, [session]);

  const refreshRuns = useCallback(async () => {
    if (!session) return;
    const result = await request("/v1/skill-challenges/runs?limit=50");
    setRuns(Array.isArray(result?.items) ? result.items : []);
  }, [request, session]);

  useEffect(() => {
    if (!supabase) { setLoading(false); setError("Konfigurasi autentikasi belum tersedia."); return; }
    let active = true;
    void supabase.auth.getSession().then(({ data }) => { if (active) { setSession(data.session); if (!data.session) setLoading(false); } });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, next) => {
      if (!active) return;
      setSession(next);
      if (!next) { setAgents([]); setSkills([]); setRuns([]); setActiveRun(null); setNonce(""); setLoading(false); }
    });
    return () => { active = false; listener.subscription.unsubscribe(); };
  }, [supabase]);

  useEffect(() => {
    if (!session) return;
    let active = true;
    setLoading(true); setError("");
    void Promise.all([request("/v1/agents"), request("/v1/skill-challenges/runs?limit=50")])
      .then(([agentResult, runResult]) => {
        if (!active) return;
        const nextAgents = Array.isArray(agentResult?.items) ? agentResult.items : [];
        setAgents(nextAgents); setAgentId(current => nextAgents.some((item: Agent) => item.id === current) ? current : (nextAgents[0]?.id ?? ""));
        setRuns(Array.isArray(runResult?.items) ? runResult.items : []);
      }).catch(cause => { if (active) setError(cause instanceof Error ? cause.message : "Data challenge tidak dapat dimuat."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [session, request]);

  useEffect(() => {
    if (!session || !agentId) { setSkills([]); setSkillId(""); return; }
    let active = true;
    setError("");
    void request(`/v1/skill-challenges/catalog?agent_id=${encodeURIComponent(agentId)}`)
      .then(result => {
        if (!active) return;
        const next = Array.isArray(result?.items) ? result.items : [];
        setSkills(next);
        setSkillId(current => next.some((item: Skill) => item.id === current) ? current : (next[0]?.id ?? ""));
      }).catch(cause => { if (active) setError(cause instanceof Error ? cause.message : "Skill tidak dapat dimuat."); });
    return () => { active = false; };
  }, [agentId, request, session]);

  const selectedSkill = skills.find(skill => skill.id === skillId);
  const availableTests = (selectedSkill?.tests ?? []).filter(item => item && typeof item.key === "string" && (item.input ?? item.inputs) !== null && typeof (item.input ?? item.inputs) === "object");
  const currentTest = availableTests.find(item => item.key === testKey);
  useEffect(() => {
    if (testKey === "__hidden__" && selectedSkill?.hidden_challenges_available) return;
    if (availableTests.some(item => item.key === testKey)) return;
    if (availableTests.length) setTestKey(String(availableTests[0].key));
    else setTestKey(selectedSkill?.hidden_challenges_available ? "__hidden__" : "");
  }, [skillId, availableTests.length, testKey, selectedSkill?.hidden_challenges_available]);

  async function issueChallenge(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setNotice(""); setNonce(""); setActiveRun(null);
    try {
      const result = await request("/v1/skill-challenges/runs", { method: "POST", body: JSON.stringify({
        agent_id: agentId, skill_id: skillId, test_key: testKey === "__hidden__" ? null : testKey, idempotency_key: crypto.randomUUID()
      }) });
      const run = result?.run as Run;
      setActiveRun(run); setNonce(result?.nonce ?? "");
      setSubmission(jsonText(run?.challenge_input ?? {}));
      setNotice(result?.nonce ? "Challenge diterbitkan. Kirim jawaban sebelum nonce kedaluwarsa." : "Challenge sudah ada dari permintaan sebelumnya. Untuk menghindari replay, terbitkan challenge baru jika nonce tidak tersedia.");
      await refreshRuns();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Challenge tidak dapat diterbitkan."); }
    finally { setBusy(false); }
  }

  async function submitAnswer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeRun || !nonce) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const parsed = JSON.parse(submission);
      if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error("Jawaban harus berupa JSON object.");
      const result = await request(`/v1/skill-challenges/runs/${activeRun.id}/submit`, { method: "POST", body: JSON.stringify({ nonce, submission: parsed }) });
      setActiveRun(result.run); setNonce("");
      setNotice(result.run?.status === "passed" ? "Evaluasi lulus. Bukti achievement tersimpan; reward finansial tidak diterbitkan tanpa kebijakan yang disetujui." : "Evaluasi selesai. Hasil dan bukti tersimpan secara persisten.");
      await refreshRuns();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Jawaban tidak dapat dievaluasi."); }
    finally { setBusy(false); }
  }

  return <main className="page-shell">
    <header className="page-header">
      <div><p className="eyebrow">ALLPHA · AGENT STUDIO</p><h1>Skill Challenge</h1><p className="muted">Uji versi Skill dengan test case yang dipatok, hasil deterministik, dan bukti yang dapat ditelusuri.</p></div>
      <Link className="button button-secondary" href="/">Kembali ke beranda</Link>
    </header>
    {error && <div className="notice notice-error" role="alert">{error}</div>}
    {notice && <div className="notice notice-success" role="status">{notice}</div>}
    {!session && !loading && <section className="panel"><h2>Login diperlukan</h2><p>Masuk ke Allpha untuk mengakses Skill dan challenge milik Anda.</p></section>}
    {session && <div className="challenge-layout">
      <section className="panel">
        <h2>Terbitkan challenge</h2>
        <p className="muted">Challenge hanya memakai test case dari snapshot Skill yang tersimpan. Expected output tidak dikirim ke browser. Pada slice ini pengguna mengirimkan output kandidat; eksekusi Skill/Agent otomatis belum diaktifkan.</p>
        <form onSubmit={issueChallenge} className="stack-form">
          <label>Agent<select value={agentId} onChange={event => setAgentId(event.target.value)} required><option value="">Pilih Agent</option>{agents.map(agent => <option key={agent.id} value={agent.id}>{agent.display_name || agent.handle || agent.id} · v{agent.version ?? "—"}</option>)}</select></label>
          <label>Skill<select value={skillId} onChange={event => setSkillId(event.target.value)} required><option value="">Pilih Skill</option>{skills.map(skill => <option key={skill.id} value={skill.id}>{skill.name} · v{skill.version} · {skill.status}</option>)}</select></label>
          <label>Test case<select value={testKey} onChange={event => setTestKey(event.target.value)} required><option value="">Pilih test case</option>{availableTests.map(item => <option key={String(item.key)} value={String(item.key)}>{String(item.key)}</option>)}{selectedSkill?.hidden_challenges_available && <option value="__hidden__">Tantangan tersembunyi acak</option>}</select></label>
          {currentTest && <div className="challenge-input"><strong>Input challenge</strong><pre>{jsonText(currentTest.input ?? currentTest.inputs)}</pre></div>}
          {selectedSkill && !selectedSkill.evaluation_rubric_available && <p className="notice notice-warning">Skill ini belum memiliki rubrik evaluasi.</p>}
          {selectedSkill && availableTests.length === 0 && !selectedSkill.hidden_challenges_available && <p className="notice notice-warning">Skill ini belum memiliki test case dengan key, input, dan expected output object.</p>}
          <button className="button button-primary" disabled={busy || loading || !agentId || !skillId || !testKey || (!availableTests.length && !selectedSkill?.hidden_challenges_available)}>Terbitkan challenge</button>
        </form>
      </section>
      <section className="panel">
        <h2>Jawaban & evaluasi</h2>
        {!activeRun && <p className="muted">Terbitkan challenge terlebih dahulu untuk membuka sesi jawaban.</p>}
        {activeRun && <div className="run-meta"><span>Status: <strong>{activeRun.status}</strong></span><span>Agent v{activeRun.agent_version} · Skill v{activeRun.skill_version}</span><span>Rubrik v{activeRun.rubric_version}</span></div>}
        <form onSubmit={submitAnswer} className="stack-form">
          <label>Output JSON<textarea rows={10} value={submission} onChange={event => setSubmission(event.target.value)} spellCheck={false} required /></label>
          <button className="button button-primary" disabled={busy || !activeRun || !nonce}>{busy ? "Memproses…" : "Kirim untuk evaluasi"}</button>
        </form>
        {activeRun?.evaluation_result && <div className="challenge-result"><h3>Hasil evaluasi</h3><pre>{jsonText(activeRun.evaluation_result)}</pre><p className="muted">Evidence SHA-256: {activeRun.evidence_digest || "belum tersedia"}</p></div>}
      </section>
    </div>}
    <section className="panel history-panel">
      <div className="section-heading"><h2>Riwayat challenge</h2><button className="button button-secondary" disabled={busy} onClick={() => void refreshRuns().catch(cause => setError(cause instanceof Error ? cause.message : "Riwayat gagal dimuat."))}>Muat ulang</button></div>
      {loading ? <p className="muted">Memuat data dari API…</p> : runs.length === 0 ? <p className="muted">Belum ada challenge run tersimpan.</p> : <div className="challenge-history">{runs.map(run => <button key={run.id} className="history-row" onClick={() => { setActiveRun(run); setNonce(""); setSubmission(jsonText(run.challenge_input)); }}>
        <span><strong>{run.challenge_key}</strong><small>Agent v{run.agent_version} · Skill v{run.skill_version} · {new Date(run.created_at).toLocaleString("id-ID")}</small></span>
        <span className={"status-pill status-" + run.status}>{run.status}</span>
      </button>)}</div>}
    </section>
    <section className="panel">
      <h2>Achievement & reward</h2>
      <p>Challenge yang lulus menghasilkan bukti achievement non-moneter yang terkait dengan run dan digest evaluasi. Tidak ada AI Credits, uang, payout, atau reward finansial yang diterbitkan pada fase ini. Reward hanya dapat diproses melalui ledger kanonis setelah kebijakan ekonomi disetujui.</p>
    </section>
  </main>;
}

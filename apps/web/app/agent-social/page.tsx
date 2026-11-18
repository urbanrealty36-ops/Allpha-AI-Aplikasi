"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../lib/supabase";
import TakeoverModal from "../../components/reference-ui/TakeoverModal";

type Agent = { id: string; display_name: string; handle: string; status: string };
type Policy = { id?: string; allowed_actions: string[]; approval_mode: string; disclosure_text: string; is_enabled: boolean; version: number };
type Automation = { version: number; auto_reply_channels: string[]; blocked_topics: string[]; reply_tone: string; allowed_tool_scopes: string[]; max_replies_per_minute: number; daily_credit_budget: number; quiet_hours: Record<string, unknown>; escalation_rules: Record<string, unknown>; takeover_active: boolean; automation_version: number };
type Approval = { id: string; agent_id: string; content_id: string; target_content_id?: string | null; target_comment_id?: string | null; action_type: string; status: string; disclosure_snapshot: string; requested_at: string; execution_result?: Record<string, unknown> };
type DecisionResult = { outcome: string; execution?: { kind?: string; message_id?: string; conversation_id?: string; story_id?: string; comment_id?: string; share_id?: string; content_id?: string; next_action?: string }; approval?: { status?: string } };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");
const choices = ["draft_post", "draft_comment", "draft_reply", "suggest_repost", "draft_story"];

export default function AgentSocialPage() {
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentId, setAgentId] = useState("");
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [automation, setAutomation] = useState<Automation | null>(null);
  const [autoReplyRuntimeEnabled, setAutoReplyRuntimeEnabled] = useState(false);
  const [blockedTopicsText, setBlockedTopicsText] = useState("");
  const [channels, setChannels] = useState<string[]>([]);
  const [replyTone, setReplyTone] = useState("friendly_concise");
  const [dailyBudget, setDailyBudget] = useState("0");
  const [takeoverBusy, setTakeoverBusy] = useState(false);
  const [takeoverModalOpen, setTakeoverModalOpen] = useState(false);
  const [actions, setActions] = useState<string[]>(["draft_post"]);
  const [mode, setMode] = useState("every_post");
  const [disclosure, setDisclosure] = useState("Dibuat bersama AI Agent");
  const [enabled, setEnabled] = useState(true);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const api = useCallback(async (path: string, init: RequestInit = {}) => {
    if (!session) throw new Error("Silakan masuk terlebih dahulu.");
    const response = await fetch(apiBase + path, { ...init, cache: "no-store", headers: { Authorization: "Bearer " + session.access_token, Accept: "application/json", "Content-Type": "application/json", ...(init.headers || {}) } });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data?.detail?.message || data?.error?.message || "Permintaan gagal.");
    return data;
  }, [session]);

  useEffect(() => {
    if (!supabase) { setLoading(false); return; }
    let active = true;
    void supabase.auth.getSession().then(({ data }) => { if (active) setSession(data.session); });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, next) => { if (active) setSession(next); });
    return () => { active = false; listener.subscription.unsubscribe(); };
  }, [supabase]);

  const load = useCallback(async () => {
    if (!session) return;
    setLoading(true); setError("");
    try {
      const [agentData, approvalData] = await Promise.all([api("/v1/agents"), api("/v1/agent-social/approvals")]);
      const activeAgents = (agentData.items || []).filter((item: Agent) => item.status === "active");
      setAgents(activeAgents); setApprovals(approvalData.items || []);
      const selected = agentId && activeAgents.some((item: Agent) => item.id === agentId) ? agentId : activeAgents[0]?.id || "";
      setAgentId(selected);
      if (selected) {
        const [policyData, automationData] = await Promise.all([
          api("/v1/agent-social/policy?agent_id=" + encodeURIComponent(selected)),
          api("/v1/agent-social/automation?agent_id=" + encodeURIComponent(selected)),
        ]);
        const p = policyData.policy as Policy | null;
        const a = automationData.policy as Automation | null;
        setPolicy(p); setActions(p?.allowed_actions || ["draft_post"]);
        setMode(p?.approval_mode === "disabled" ? "disabled" : "every_post"); setDisclosure(p?.disclosure_text || "Dibuat bersama AI Agent"); setEnabled(p?.is_enabled ?? true);
        setAutomation(a); setAutoReplyRuntimeEnabled(automationData.auto_reply_runtime_enabled === true); setChannels(a?.auto_reply_channels || []);
        setBlockedTopicsText((a?.blocked_topics || []).join(", "));
        setReplyTone(a?.reply_tone || "friendly_concise");
        setDailyBudget(String(a?.daily_credit_budget ?? 0));
      } else { setPolicy(null); setAutomation(null); setAutoReplyRuntimeEnabled(false); setChannels([]); setBlockedTopicsText(""); setReplyTone("friendly_concise"); setDailyBudget("0"); }
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Data tidak dapat dimuat."); }
    finally { setLoading(false); }
  }, [session, api, agentId]);

  useEffect(() => { if (session) void load(); else { setLoading(false); setApprovals([]); setAgents([]); } }, [session, load]);

  async function save() {
    if (!agentId) return; setBusy(true); setError(""); setNotice("");
    try {
      const data = await api("/v1/agent-social/policy/" + agentId, { method: "PUT", body: JSON.stringify({ allowed_actions: actions, approval_mode: mode, disclosure_text: disclosure, is_enabled: enabled, expected_version: policy?.version ?? null }) });
      setPolicy(data.policy); setNotice("Kebijakan berhasil disimpan."); await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Kebijakan gagal disimpan."); }
    finally { setBusy(false); }
  }

  async function decide(id: string, decision: "approve" | "reject") {
    setBusy(true); setError(""); setNotice("");
    try { const result = await api("/v1/agent-social/approvals/" + id + "/decision", { method: "POST", body: JSON.stringify({ decision, reason: decision === "approve" ? "Disetujui pemilik" : "Ditolak pemilik" }) }) as DecisionResult; const execution = result.execution; const detail = execution?.kind === "story_dm" ? "DM Story dibuat dan tertaut ke Story (percakapan " + execution.conversation_id + ")." : execution?.kind === "comment" ? "Komentar/reply Agent tercatat dengan atribusi (komentar " + execution.comment_id + ")." : execution?.kind === "post_moderation" ? "Draft dikirim ke antrean moderasi; belum dipublikasikan." : execution?.kind === "agent_repost" ? "Repost Agent tercatat dengan atribusi dan disclosure." : result.approval?.status === "approved" ? "Approval tercatat; lifecycle konten tetap berlaku." : "Permintaan ditolak."; setNotice((result.outcome === "replayed" ? "Hasil transaksi sebelumnya dipulihkan. " : "") + detail); await load(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Keputusan gagal."); }
    finally { setBusy(false); }
  }

  async function revoke(id: string) {
    setBusy(true);
    try { const result = await api("/v1/agent-social/approvals/" + id + "/revoke", { method: "POST" }); setNotice(result.outcome === "replayed" ? "Pencabutan sebelumnya sudah tercatat." : "Persetujuan dicabut dan audit/notifikasi tersimpan."); await load(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Pencabutan gagal."); }
    finally { setBusy(false); }
  }

  async function toggleTakeover() {
    if (!agentId || !automation || takeoverBusy) return;
    setTakeoverBusy(true); setError(""); setNotice("");
    try {
      const active = !automation.takeover_active;
      const data = await api("/v1/agent-social/takeover/" + agentId, {
        method: "POST",
        body: JSON.stringify({ takeover_active: active, reason: active ? "owner_manual_takeover" : "owner_released_takeover" }),
      });
      setAutomation(data.policy);
      setAutoReplyRuntimeEnabled(data.auto_reply_enabled === true);
      setNotice(active ? "Takeover aktif. Approval pending dicabut." : "Takeover dilepas; Auto Reply tetap nonaktif sampai runtime diaktifkan.");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Takeover gagal diperbarui.");
    } finally { setTakeoverBusy(false); }
  }

  if (!session) return <main className="min-h-screen bg-slate-50 p-6"><section className="mx-auto max-w-xl rounded-3xl border-2 border-slate-900 bg-white p-8 shadow-[3px_3px_0px_#0f172a]"><h1 className="text-2xl font-black">Human + AI Agent Social</h1><p className="mt-2 text-sm text-slate-600">Masuk untuk mengelola kebijakan dan persetujuan Agent.</p><a className="mt-5 inline-flex rounded-full bg-slate-900 px-5 py-3 font-bold text-white" href="/account">Masuk / Akun</a></section></main>;

  return <main className="min-h-screen bg-slate-50 px-4 py-6 pb-24 sm:px-6"><div className="mx-auto max-w-5xl space-y-6">
    <header><p className="text-xs font-black uppercase tracking-widest text-indigo-600">Allpha · Human Control</p><h1 className="mt-1 text-3xl font-black text-slate-950">Kehadiran Sosial AI Agent</h1><p className="mt-2 text-sm text-slate-600">Kelola izin tindakan, disclosure, dan persetujuan Agent.</p></header>
    {error && <p role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</p>}
    {notice && <p role="status" className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">{notice}</p>}
    <section className="rounded-3xl border-2 border-slate-900 bg-white p-5 shadow-[3px_3px_0px_#0f172a] sm:p-6">
      <h2 className="text-xl font-black">Kebijakan Agent</h2>
      {loading ? <p className="py-8 text-sm text-slate-500">Memuat…</p> : agents.length === 0 ? <p className="py-8 text-sm text-slate-600">Belum ada Agent aktif.</p> : <>
        <label className="mt-4 block text-xs font-bold">Pilih Agent</label><select value={agentId} onChange={event => setAgentId(event.target.value)} className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-white p-3">{agents.map(agent => <option key={agent.id} value={agent.id}>{agent.display_name} · @{agent.handle}</option>)}</select>
        <div className="mt-5 grid gap-3 sm:grid-cols-2">{choices.map(choice => <label key={choice} className="flex items-center gap-3 rounded-xl border-2 border-slate-200 p-3 text-sm font-semibold"><input type="checkbox" checked={actions.includes(choice)} onChange={event => setActions(old => event.target.checked ? [...old, choice] : old.filter(item => item !== choice))} />{choice.replaceAll("_", " ")}</label>)}</div>
        <label className="mt-5 block text-xs font-bold">Approval mode</label><select value={mode} onChange={event => setMode(event.target.value)} className="mt-1 w-full rounded-xl border-2 border-slate-900 p-3"><option value="every_post">Setiap tindakan wajib disetujui</option><option value="high_risk_only" disabled>High risk only (belum didukung)</option><option value="disabled">Disabled</option></select>
        <label className="mt-5 block text-xs font-bold">Disclosure publik</label><input value={disclosure} onChange={event => setDisclosure(event.target.value)} maxLength={180} className="mt-1 w-full rounded-xl border-2 border-slate-900 p-3" />
        <label className="mt-5 flex items-center gap-3 text-sm font-bold"><input type="checkbox" checked={enabled} onChange={event => setEnabled(event.target.checked)} />Aktifkan kebijakan</label>
        <button disabled={busy || !agentId} onClick={save} className="mt-5 rounded-full border-2 border-slate-900 bg-slate-900 px-6 py-3 text-sm font-black text-white disabled:opacity-50">{busy ? "Menyimpan…" : "Simpan Kebijakan"}</button>
      </>}
    </section>

    <section className="rounded-3xl border-2 border-slate-900 bg-white p-5 shadow-[3px_3px_0px_#0f172a] sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><p className="text-xs font-black uppercase tracking-widest text-sky-700">Human takeover · Auto Reply policy</p><h2 className="mt-1 text-xl font-black">Kontrol Otomatisasi Agent</h2><p className="mt-1 text-sm text-slate-600">Pengaturan disimpan melalui FastAPI. Eksekusi Auto Reply tetap nonaktif sampai event consumer dan policy runtime tersambung.</p></div>
        <div className="flex flex-wrap items-center gap-2">
          <span className={"rounded-full border-2 border-slate-900 px-3 py-1 text-xs font-black " + (automation?.takeover_active ? "bg-purple-100 text-purple-900" : "bg-sky-100 text-sky-900")}>{automation?.takeover_active ? "TAKEOVER HUMAN" : "AUTO REPLY DISABLED"}</span>
          <button type="button" onClick={() => setTakeoverModalOpen(true)} disabled={!automation || busy || takeoverBusy} className="rounded-full border-2 border-slate-900 bg-amber-200 px-3 py-2 text-xs font-black shadow-[1px_1px_0px_#0f172a] disabled:opacity-50">Kontrol Takeover</button>
        </div>
      </div>
      {!automation && !loading && <p className="mt-4 rounded-xl border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">Policy otomasi kanonis belum tersedia untuk Agent ini. Perubahan Auto Reply dan Takeover dinonaktifkan sampai record policy dibuat oleh lifecycle backend.</p>}
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {["comments","mentions","dm","live_chat"].map(channel => <label key={channel} className="flex items-center gap-3 rounded-xl border-2 border-slate-200 p-3 text-sm font-semibold"><input type="checkbox" checked={channels.includes(channel)} onChange={e => setChannels(old => e.target.checked ? [...old,channel] : old.filter(x => x !== channel))}/>{channel.replace("_"," ")}</label>)}
      </div>
      <label className="mt-4 block text-xs font-bold">Topik yang diblokir (pisahkan dengan koma)</label>
      <input value={blockedTopicsText} onChange={e => setBlockedTopicsText(e.target.value)} className="mt-1 w-full rounded-xl border-2 border-slate-900 p-3 text-sm" placeholder="mis. data pribadi, instruksi berbahaya"/>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <label className="block text-xs font-bold">Gaya komunikasi<select value={replyTone} onChange={e => setReplyTone(e.target.value)} className="mt-1 w-full rounded-xl border-2 border-slate-900 p-3"><option value="friendly_concise">Ramah & ringkas</option><option value="professional">Profesional</option><option value="warm">Hangat</option><option value="formal">Formal</option></select></label>
        <label className="block text-xs font-bold">Batas budget harian (AI Credits)<input type="number" min="0" step="1" value={dailyBudget} onChange={e => setDailyBudget(e.target.value)} className="mt-1 w-full rounded-xl border-2 border-slate-900 p-3"/></label>
      </div>
      <p className="mt-3 rounded-xl border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">Auto Reply belum dapat diaktifkan: runtime event consumer, quota reservation dan output moderation belum terhubung. Takeover selalu menghentikan Auto Reply dan mencabut approval pending.</p>
      <div className="mt-4 flex flex-wrap gap-2">
        <button disabled={busy || !agentId || !automation} onClick={async () => { setBusy(true); setError(""); try { const data = await api("/v1/agent-social/automation/" + agentId,{method:"PUT",body:JSON.stringify({auto_reply_channels:channels,blocked_topics:blockedTopicsText.split(",").map(x=>x.trim()).filter(Boolean),reply_tone:replyTone,allowed_tool_scopes:[],max_replies_per_minute:1,daily_credit_budget:Math.max(0,Math.floor(Number(dailyBudget)||0)),quiet_hours:{},escalation_rules:{},expected_version:automation?.version ?? 1})}); setAutomation(data.policy); setAutoReplyRuntimeEnabled(data.auto_reply_runtime_enabled === true); setNotice("Konfigurasi Auto Reply tersimpan; eksekusi tetap nonaktif."); await load(); } catch(e) { setError(e instanceof Error?e.message:"Konfigurasi gagal disimpan."); } finally { setBusy(false); } }} className="rounded-full border-2 border-slate-900 bg-sky-300 px-5 py-3 text-sm font-black">Simpan Pengaturan Auto Reply</button>
        <button disabled={busy || takeoverBusy || !agentId || !automation} onClick={() => void toggleTakeover()} className={"rounded-full border-2 border-slate-900 px-5 py-3 text-sm font-black " + (automation?.takeover_active ? "bg-purple-200" : "bg-white")}>{takeoverBusy?"Memproses…":automation?.takeover_active?"Lepas Takeover":"Ambil Alih Sekarang"}</button>
      </div>
    </section>

    <section className="rounded-3xl border-2 border-slate-900 bg-white p-5 shadow-[3px_3px_0px_#0f172a] sm:p-6"><div className="flex justify-between gap-3"><h2 className="text-xl font-black">Kotak Persetujuan</h2><span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-bold">{approvals.filter(item => item.status === "pending").length} menunggu</span></div>
      {loading ? <p className="py-8 text-sm text-slate-500">Memuat…</p> : approvals.length === 0 ? <p className="py-8 text-sm text-slate-600">Belum ada permintaan persetujuan.</p> : <div className="mt-4 space-y-3">{approvals.map(item => <article key={item.id} className="rounded-2xl border-2 border-slate-200 p-4"><div className="flex flex-wrap justify-between gap-2"><strong>{item.action_type.replaceAll("_", " ")}</strong><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold">{item.status}</span></div><p className="mt-2 text-xs text-slate-500">{new Date(item.requested_at).toLocaleString("id-ID")} · {item.content_id}</p><p className="mt-2 text-sm text-slate-600">{item.disclosure_snapshot}</p>{item.status === "pending" && <div className="mt-4 flex gap-2"><button disabled={busy} onClick={() => decide(item.id, "approve")} className="rounded-full border-2 border-slate-900 bg-slate-900 px-4 py-2 text-xs font-bold text-white">Setujui</button><button disabled={busy} onClick={() => decide(item.id, "reject")} className="rounded-full border-2 border-slate-900 px-4 py-2 text-xs font-bold">Tolak</button></div>}{item.status === "approved" && <button disabled={busy} onClick={() => revoke(item.id)} className="mt-3 rounded-full border-2 border-rose-700 px-4 py-2 text-xs font-bold text-rose-700">Cabut persetujuan</button>}</article>)}</div>}
    </section>
    <TakeoverModal
      isOpen={takeoverModalOpen}
      onClose={() => setTakeoverModalOpen(false)}
      isTakeoverActive={!!automation?.takeover_active}
      onToggleTakeover={() => { void toggleTakeover(); }}
      agentName={agents.find(item => item.id === agentId)?.display_name || "AI Agent"}
      actionsEnabled={!!automation && !busy && !takeoverBusy}
      autoReplyRuntimeEnabled={autoReplyRuntimeEnabled}
    />
  </div></main>;
}

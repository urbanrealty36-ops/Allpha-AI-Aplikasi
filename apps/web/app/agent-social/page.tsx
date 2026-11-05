"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../lib/supabase";

type Agent = { id: string; display_name: string; handle: string; status: string };
type Policy = { id?: string; allowed_actions: string[]; approval_mode: string; disclosure_text: string; is_enabled: boolean; version: number };
type Approval = { id: string; agent_id: string; content_id: string; action_type: string; status: string; disclosure_snapshot: string; requested_at: string };\ntype DecisionResult = { outcome: string; execution?: { kind?: string; message_id?: string; conversation_id?: string; story_id?: string; comment_id?: string }; approval?: { status?: string } };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
const choices = ["draft_post", "draft_comment", "draft_reply", "suggest_repost", "draft_story"];

export default function AgentSocialPage() {
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentId, setAgentId] = useState("");
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
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
        const data = await api("/v1/agent-social/policy?agent_id=" + encodeURIComponent(selected));
        const p = data.policy as Policy | null; setPolicy(p); setActions(p?.allowed_actions || ["draft_post"]);
        setMode(p?.approval_mode || "every_post"); setDisclosure(p?.disclosure_text || "Dibuat bersama AI Agent"); setEnabled(p?.is_enabled ?? true);
      } else setPolicy(null);
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
    try { const result = await api("/v1/agent-social/approvals/" + id + "/decision", { method: "POST", body: JSON.stringify({ decision, reason: decision === "approve" ? "Disetujui pemilik" : "Ditolak pemilik" }) }) as DecisionResult; const execution = result.execution; const detail = execution?.kind === "story_dm" ? "DM Story dibuat dan tertaut ke Story (percakapan " + execution.conversation_id + ")." : execution?.kind === "comment" ? "Balasan komentar tercatat (komentar " + execution.comment_id + ")." : result.approval?.status === "approved" ? "Draft disetujui; tahap moderasi/publikasi tetap mengikuti lifecycle konten." : "Permintaan ditolak."; setNotice((result.outcome === "replayed" ? "Hasil transaksi sebelumnya dipulihkan. " : "") + detail); await load(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Keputusan gagal."); }
    finally { setBusy(false); }
  }

  async function revoke(id: string) {
    setBusy(true);
    try { const result = await api("/v1/agent-social/approvals/" + id + "/revoke", { method: "POST" }); setNotice(result.outcome === "replayed" ? "Pencabutan sebelumnya sudah tercatat." : "Persetujuan dicabut dan audit/notifikasi tersimpan."); await load(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Pencabutan gagal."); }
    finally { setBusy(false); }
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
        <label className="mt-5 block text-xs font-bold">Approval mode</label><select value={mode} onChange={event => setMode(event.target.value)} className="mt-1 w-full rounded-xl border-2 border-slate-900 p-3"><option value="every_post">Setiap tindakan wajib disetujui</option><option value="high_risk_only">High risk only (approval masih konservatif)</option><option value="disabled">Disabled</option></select>
        <label className="mt-5 block text-xs font-bold">Disclosure publik</label><input value={disclosure} onChange={event => setDisclosure(event.target.value)} maxLength={180} className="mt-1 w-full rounded-xl border-2 border-slate-900 p-3" />
        <label className="mt-5 flex items-center gap-3 text-sm font-bold"><input type="checkbox" checked={enabled} onChange={event => setEnabled(event.target.checked)} />Aktifkan kebijakan</label>
        <button disabled={busy || !agentId} onClick={save} className="mt-5 rounded-full border-2 border-slate-900 bg-slate-900 px-6 py-3 text-sm font-black text-white disabled:opacity-50">{busy ? "Menyimpan…" : "Simpan Kebijakan"}</button>
      </>}
    </section>
    <section className="rounded-3xl border-2 border-slate-900 bg-white p-5 shadow-[3px_3px_0px_#0f172a] sm:p-6"><div className="flex justify-between gap-3"><h2 className="text-xl font-black">Kotak Persetujuan</h2><span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-bold">{approvals.filter(item => item.status === "pending").length} menunggu</span></div>
      {loading ? <p className="py-8 text-sm text-slate-500">Memuat…</p> : approvals.length === 0 ? <p className="py-8 text-sm text-slate-600">Belum ada permintaan persetujuan.</p> : <div className="mt-4 space-y-3">{approvals.map(item => <article key={item.id} className="rounded-2xl border-2 border-slate-200 p-4"><div className="flex flex-wrap justify-between gap-2"><strong>{item.action_type.replaceAll("_", " ")}</strong><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold">{item.status}</span></div><p className="mt-2 text-xs text-slate-500">{new Date(item.requested_at).toLocaleString("id-ID")} · {item.content_id}</p><p className="mt-2 text-sm text-slate-600">{item.disclosure_snapshot}</p>{item.status === "pending" && <div className="mt-4 flex gap-2"><button disabled={busy} onClick={() => decide(item.id, "approve")} className="rounded-full border-2 border-slate-900 bg-slate-900 px-4 py-2 text-xs font-bold text-white">Setujui</button><button disabled={busy} onClick={() => decide(item.id, "reject")} className="rounded-full border-2 border-slate-900 px-4 py-2 text-xs font-bold">Tolak</button></div>}{item.status === "approved" && <button disabled={busy} onClick={() => revoke(item.id)} className="mt-3 rounded-full border-2 border-rose-700 px-4 py-2 text-xs font-bold text-rose-700">Cabut persetujuan</button>}</article>)}</div>}
    </section>
  </div></main>;
}

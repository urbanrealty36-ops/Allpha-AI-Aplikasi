"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../../lib/supabase";

type Agent = { id: string; handle: string; display_name: string; status: string; visibility: string };
type Transfer = { id: string; agent_id: string; from_owner_user_id: string; to_owner_user_id: string; status: "pending"|"accepted"|"rejected"|"cancelled"|"expired"; expires_at: string; created_at: string };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

export default function AgentOwnershipTransfersPage() {
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [outgoing, setOutgoing] = useState<Transfer[]>([]);
  const [incoming, setIncoming] = useState<Transfer[]>([]);
  const [agentId, setAgentId] = useState("");
  const [recipientUserId, setRecipientUserId] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const api = useCallback(async <T,>(path: string, init: RequestInit = {}): Promise<T> => {
    if (!session) throw new Error("Sesi login diperlukan.");
    const headers = new Headers(init.headers);
    headers.set("Authorization", "Bearer " + session.access_token);
    headers.set("Accept", "application/json");
    if (init.body) headers.set("Content-Type", "application/json");
    const response = await fetch(apiBase + path, { ...init, headers, cache: "no-store" });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body?.detail?.message || body?.error?.message || "Permintaan transfer kepemilikan gagal.");
    return body as T;
  }, [session]);

  const load = useCallback(async () => {
    if (!session) return;
    setLoading(true); setError("");
    try {
      const [agentResult, transferResult] = await Promise.all([
        api<{items: Agent[]}>("/v1/agents"),
        api<{outgoing: Transfer[]; incoming: Transfer[]}>("/v1/agent-ownership-transfers"),
      ]);
      setAgents(agentResult.items || []);
      setOutgoing(transferResult.outgoing || []);
      setIncoming(transferResult.incoming || []);
      setAgentId(current => current || agentResult.items?.[0]?.id || "");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Data kepemilikan Agent tidak dapat dimuat.");
    } finally { setLoading(false); }
  }, [api, session]);

  useEffect(() => {
    if (!supabase) { setLoading(false); setError("Konfigurasi autentikasi belum tersedia."); return; }
    let active = true;
    void supabase.auth.getSession().then(({data}) => { if (active) setSession(data.session); });
    const {data: listener} = supabase.auth.onAuthStateChange((_event, next) => { if (active) setSession(next); });
    return () => { active = false; listener.subscription.unsubscribe(); };
  }, [supabase]);
  useEffect(() => { if (session) void load(); else setLoading(false); }, [session, load]);

  async function requestTransfer(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError(""); setNotice("");
    try {
      const result = await api<{status: string}>("/v1/agents/" + encodeURIComponent(agentId) + "/ownership-transfers", {
        method: "POST",
        body: JSON.stringify({ recipient_user_id: recipientUserId.trim(), idempotency_key: crypto.randomUUID() }),
      });
      setNotice("Permintaan transfer dikirim. Kepemilikan baru aktif setelah penerima menyetujui.");
      setRecipientUserId(""); await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Transfer tidak dapat diminta."); }
    finally { setSaving(false); }
  }

  async function respond(id: string, accept: boolean) {
    setSaving(true); setError(""); setNotice("");
    try {
      const result = await api<{status: string}>("/v1/agent-ownership-transfers/" + encodeURIComponent(id) + "/respond", {
        method: "POST", body: JSON.stringify({accept}),
      });
      setNotice(result.status === "accepted"
        ? "Kepemilikan Agent berpindah. Publikasi, grant konsumen, grant resource, policy runtime, dan social automation lama telah dicabut untuk persetujuan ulang."
        : "Permintaan transfer ditolak.");
      await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Respons transfer gagal."); }
    finally { setSaving(false); }
  }

  async function cancel(id: string) {
    setSaving(true); setError(""); setNotice("");
    try {
      await api("/v1/agent-ownership-transfers/" + encodeURIComponent(id) + "/cancel", {method:"POST"});
      setNotice("Permintaan transfer dibatalkan."); await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Pembatalan transfer gagal."); }
    finally { setSaving(false); }
  }

  const agentName = (id: string) => agents.find(agent => agent.id === id)?.display_name || id;
  const pending = (status: string) => status === "pending";
  return <main className="mx-auto max-w-4xl px-4 py-8 text-slate-900">
    <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
      <div><p className="text-xs font-bold uppercase tracking-widest text-indigo-700">Allpha · Agent Identity</p><h1 className="text-2xl font-black">Transfer Kepemilikan Agent</h1><p className="mt-1 text-sm text-slate-600">Transfer memerlukan persetujuan Human Owner saat ini dan penerima.</p></div>
      <Link href="/profile" className="rounded-xl border border-slate-300 px-4 py-2 text-sm font-bold">Kembali ke Profil</Link>
    </header>
    {error && <p role="alert" className="mb-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
    {notice && <p role="status" className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</p>}
    {!session && <section className="rounded-2xl border border-slate-200 bg-white p-5">Masuk untuk mengelola transfer kepemilikan Agent.</section>}
    {session && <>
      <form onSubmit={requestTransfer} className="mb-6 grid gap-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="font-bold">Ajukan transfer</h2>
        <label className="grid gap-1 text-sm font-semibold">Agent
          <select value={agentId} onChange={event=>setAgentId(event.target.value)} required className="rounded-xl border border-slate-300 bg-white p-3">
            <option value="">Pilih Agent</option>{agents.map(agent=><option key={agent.id} value={agent.id}>{agent.display_name} · @{agent.handle}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-sm font-semibold">User ID penerima
          <input value={recipientUserId} onChange={event=>setRecipientUserId(event.target.value)} required minLength={36} maxLength={36} placeholder="UUID akun Allpha penerima" className="rounded-xl border border-slate-300 p-3 font-mono text-sm"/>
        </label>
        <p className="text-xs leading-5 text-slate-500">Penerima harus memiliki akun Allpha aktif. Setelah menerima transfer, seluruh grant akses dan policy runtime sebelumnya dicabut; Agent kembali privat/draft dan harus dipublikasikan ulang oleh pemilik baru.</p>
        <button disabled={saving || loading || !agentId || recipientUserId.trim().length!==36} className="w-fit rounded-xl bg-indigo-700 px-5 py-2.5 text-sm font-bold text-white disabled:opacity-50">{saving?"Memproses…":"Kirim permintaan transfer"}</button>
      </form>
      <section className="mb-6 rounded-2xl border border-slate-200 bg-white p-5">
        <h2 className="mb-3 font-bold">Permintaan masuk</h2>
        {loading ? <p className="text-sm text-slate-500">Memuat…</p> : incoming.length===0 ? <p className="text-sm text-slate-500">Tidak ada permintaan masuk.</p> : <div className="space-y-3">{incoming.map(item=><article key={item.id} className="rounded-xl border border-slate-200 p-3"><div className="flex flex-wrap items-center justify-between gap-2"><strong>{agentName(item.agent_id)}</strong><span className="text-xs font-semibold uppercase text-slate-500">{item.status}</span></div><p className="mt-1 text-xs text-slate-500">Dari: {item.from_owner_user_id} · Berlaku sampai {new Date(item.expires_at).toLocaleString("id-ID")}</p>{pending(item.status)&&<div className="mt-3 flex gap-2"><button disabled={saving} onClick={()=>void respond(item.id,true)} className="rounded-lg bg-emerald-700 px-3 py-2 text-xs font-bold text-white">Terima transfer</button><button disabled={saving} onClick={()=>void respond(item.id,false)} className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-bold">Tolak</button></div>}</article>)}</div>}
      </section>
      <section className="rounded-2xl border border-slate-200 bg-white p-5">
        <h2 className="mb-3 font-bold">Permintaan keluar</h2>
        {outgoing.length===0 ? <p className="text-sm text-slate-500">Belum ada permintaan transfer.</p> : <div className="space-y-3">{outgoing.map(item=><article key={item.id} className="rounded-xl border border-slate-200 p-3"><div className="flex flex-wrap items-center justify-between gap-2"><strong>{agentName(item.agent_id)}</strong><span className="text-xs font-semibold uppercase text-slate-500">{item.status}</span></div><p className="mt-1 text-xs text-slate-500">Penerima: {item.to_owner_user_id} · Dibuat {new Date(item.created_at).toLocaleString("id-ID")}</p>{pending(item.status)&&<button disabled={saving} onClick={()=>void cancel(item.id)} className="mt-3 rounded-lg border border-rose-300 px-3 py-2 text-xs font-bold text-rose-700">Batalkan permintaan</button>}</article>)}</div>}
      </section>
    </>}
  </main>;
}

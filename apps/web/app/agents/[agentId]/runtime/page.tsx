"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../../../lib/supabase";

type Task = {
  id: string; session_id: string; agent_id: string; skill_id: string;
  agent_version: number; skill_version: number; state: string; tool_key: string;
  trace_id: string; created_at: string; updated_at: string; completed_at?: string | null;
  error_code?: string | null; execution_event_seq?: number;
};
type TraceEvent = {
  id: string; sequence: number; trace_id: string; event_type: string; state: string;
  step_key: string; details: Record<string, unknown>; created_at: string;
};
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

async function responseError(response: Response) {
  try { const body = await response.json(); return body?.error?.message ?? body?.detail?.message ?? `Permintaan gagal (${response.status}).`; }
  catch { return `Permintaan gagal (${response.status}).`; }
}

export default function AgentRuntimeTracePage() {
  const params = useParams<{ agentId: string }>();
  const agentId = params.agentId;
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selectedTask, setSelectedTask] = useState("");
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [traceLoading, setTraceLoading] = useState(false);
  const [error, setError] = useState("");
  const [traceError, setTraceError] = useState("");

  const loadTasks = useCallback(async (active: Session) => {
    setLoading(true); setError("");
    try {
      const response = await fetch(`${apiBase}/v1/agent-runtime/tasks?agent_id=${encodeURIComponent(agentId)}&limit=100`, {
        headers: { Authorization: "Bearer " + active.access_token }, cache: "no-store",
      });
      if (!response.ok) throw new Error(await responseError(response));
      const body = await response.json();
      const rows: Task[] = Array.isArray(body.items) ? body.items : [];
      setTasks(rows);
      setSelectedTask(current => rows.some(row => row.id === current) ? current : rows[0]?.id ?? "");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Riwayat Agent Runtime tidak dapat dimuat."); }
    finally { setLoading(false); }
  }, [agentId]);

  useEffect(() => {
    if (!supabase) { setLoading(false); setError("Konfigurasi autentikasi belum tersedia."); return; }
    let active = true;
    void supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      setSession(data.session);
      if (data.session) void loadTasks(data.session);
      else { setLoading(false); setError("Masuk terlebih dahulu untuk melihat execution trace."); }
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, next) => {
      if (!active) return;
      setSession(next);
      if (next) void loadTasks(next);
      else { setTasks([]); setEvents([]); setLoading(false); setError("Sesi berakhir. Silakan masuk kembali."); }
    });
    return () => { active = false; listener.subscription.unsubscribe(); };
  }, [supabase, loadTasks]);

  useEffect(() => {
    if (!session || !selectedTask) { setEvents([]); return; }
    let active = true;
    setTraceLoading(true); setTraceError("");
    void fetch(`${apiBase}/v1/agent-runtime/tasks/${encodeURIComponent(selectedTask)}/events`, {
      headers: { Authorization: "Bearer " + session.access_token }, cache: "no-store",
    }).then(async response => {
      if (!response.ok) throw new Error(await responseError(response));
      const body = await response.json();
      if (active) setEvents(Array.isArray(body.items) ? body.items : []);
    }).catch(cause => { if (active) setTraceError(cause instanceof Error ? cause.message : "Trace tidak dapat dimuat."); })
      .finally(() => { if (active) setTraceLoading(false); });
    return () => { active = false; };
  }, [session, selectedTask]);

  const selected = tasks.find(task => task.id === selectedTask);
  return <main className="mx-auto max-w-6xl space-y-6 p-4 sm:p-6">
    <header className="flex flex-wrap items-end justify-between gap-3 border-b pb-5">
      <div><p className="text-xs font-semibold uppercase tracking-[0.18em] text-neutral-500">Allpha · Agent Runtime</p><h1 className="mt-2 text-3xl font-semibold tracking-tight">Execution Trace</h1><p className="mt-2 max-w-2xl text-sm text-neutral-600">Riwayat task, state transition, dan trace yang tersimpan secara durable. Input, output, prompt, serta konten Memory privat tidak ditampilkan di timeline.</p></div>
      <div className="flex flex-wrap gap-2"><Link href={`/agents/${agentId}/studio`} className="rounded-xl border px-4 py-2 text-sm font-medium">Agent Studio</Link><Link href={`/agents/${agentId}/memory`} className="rounded-xl border px-4 py-2 text-sm font-medium">Memory Studio</Link><button onClick={() => session && void loadTasks(session)} disabled={loading} className="rounded-xl border px-4 py-2 text-sm font-medium disabled:opacity-50">{loading ? "Memuat…" : "Muat ulang"}</button></div>
    </header>
    {error && <div role="alert" className="rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-900">{error}</div>}
    <div className="grid gap-4 lg:grid-cols-[minmax(260px,0.85fr)_minmax(0,1.5fr)]">
      <section className="space-y-3 rounded-2xl border p-4">
        <div className="flex items-center justify-between gap-2"><h2 className="text-lg font-semibold">Task history</h2><span className="text-xs text-neutral-500">{tasks.length} task</span></div>
        {loading ? <p className="text-sm text-neutral-500">Memuat task…</p> : tasks.length === 0 ? <p className="rounded-xl border border-dashed p-4 text-sm text-neutral-500">Belum ada task Agent Runtime yang tercatat.</p> : <div className="space-y-2">{tasks.map(task => <button key={task.id} onClick={() => setSelectedTask(task.id)} className={`w-full rounded-xl border p-3 text-left transition ${selectedTask === task.id ? "border-neutral-900 bg-neutral-50" : "hover:bg-neutral-50"}`}>
          <div className="flex items-center justify-between gap-2"><span className="text-sm font-semibold">{task.tool_key}</span><span className="rounded-full border px-2 py-0.5 text-[11px]">{task.state}</span></div>
          <p className="mt-1 break-all font-mono text-[11px] text-neutral-500">{task.id}</p>
          <p className="mt-1 text-xs text-neutral-500">{new Date(task.created_at).toLocaleString("id-ID")} · {task.execution_event_seq ?? 0} event</p>
          {task.error_code && <p className="mt-1 text-xs text-red-700">{task.error_code}</p>}
        </button>)}</div>}
      </section>
      <section className="space-y-4 rounded-2xl border p-4 sm:p-5">
        <div><h2 className="text-lg font-semibold">Trace timeline</h2><p className="mt-1 text-xs text-neutral-500">{selected ? `Trace ID: ${selected.trace_id}` : "Pilih task untuk melihat timeline."}</p></div>
        {traceError && <p role="alert" className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-900">{traceError}</p>}
        {traceLoading ? <p className="text-sm text-neutral-500">Memuat execution events…</p> : !selected ? <p className="text-sm text-neutral-500">Belum ada task yang dipilih.</p> : events.length === 0 ? <p className="rounded-xl border border-dashed p-4 text-sm text-neutral-500">Belum ada event trace durable untuk task ini. Task lama mungkin hanya memiliki event_log legacy.</p> : <ol className="space-y-3">{events.map(event => <li key={event.id} className="relative flex gap-3">
          <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs font-semibold">{event.sequence}</div>
          <div className="min-w-0 flex-1 rounded-xl border p-3"><div className="flex flex-wrap items-center justify-between gap-2"><strong className="text-sm">{event.state}</strong><span className="text-[11px] text-neutral-500">{new Date(event.created_at).toLocaleString("id-ID")}</span></div><p className="mt-1 break-all font-mono text-xs text-neutral-600">{event.step_key}</p>{typeof event.details?.reason_code === "string" && <p className="mt-1 text-xs text-neutral-500">Reason: {event.details.reason_code}</p>}</div>
        </li>)}</ol>}
      </section>
    </div>
  </main>;
}

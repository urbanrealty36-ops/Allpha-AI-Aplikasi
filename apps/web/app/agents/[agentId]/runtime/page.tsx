"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
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
type Skill = {
  id: string; name: string; status: string; version: number;
  tool_dependencies: string[]; budget_limits?: { max_runtime_seconds?: number; max_tool_calls?: number };
};
type RegisteredTool = {
  key: string; name: string; description: string; version: string;
  execution_class: string; executable: boolean;
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
  const [skills, setSkills] = useState<Skill[]>([]);
  const [tools, setTools] = useState<RegisteredTool[]>([]);
  const [selectedSkillId, setSelectedSkillId] = useState("");
  const [planJson, setPlanJson] = useState('[\n  {\n    "step_id": "normalize",\n    "tool_key": "text.normalize",\n    "inputs": { "text": "  Contoh   input  " },\n    "bindings": {}\n  },\n  {\n    "step_id": "truncate",\n    "tool_key": "text.truncate",\n    "inputs": { "max_chars": 80 },\n    "bindings": { "text": { "step_id": "normalize", "path": "text" } }\n  }\n]');
  const [catalogError, setCatalogError] = useState("");
  const [notice, setNotice] = useState("");
  const [creating, setCreating] = useState(false);

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

  const loadCatalog = useCallback(async (active: Session) => {
    setCatalogError("");
    try {
      const headers = { Authorization: "Bearer " + active.access_token };
      const [skillResponse, toolResponse] = await Promise.all([
        fetch(`${apiBase}/v1/agents/${agentId}/skills`, { headers, cache: "no-store" }),
        fetch(`${apiBase}/v1/tools`, { headers, cache: "no-store" }),
      ]);
      if (!skillResponse.ok) throw new Error(await responseError(skillResponse));
      if (!toolResponse.ok) throw new Error(await responseError(toolResponse));
      const [skillBody, toolBody] = await Promise.all([skillResponse.json(), toolResponse.json()]);
      const nextSkills: Skill[] = Array.isArray(skillBody.items)
        ? skillBody.items.filter((item: Skill) => item.status === "published") : [];
      const nextTools: RegisteredTool[] = Array.isArray(toolBody.items)
        ? toolBody.items.filter((item: RegisteredTool) => item.executable) : [];
      setSkills(nextSkills);
      setTools(nextTools);
      setSelectedSkillId(current => nextSkills.some(item => item.id === current) ? current : nextSkills[0]?.id ?? "");
    } catch (cause) {
      setSkills([]); setTools([]);
      setCatalogError(cause instanceof Error ? cause.message : "Katalog Skill dan Tool tidak dapat dimuat.");
    }
  }, [agentId]);

  useEffect(() => {
    if (!supabase) { setLoading(false); setError("Konfigurasi autentikasi belum tersedia."); return; }
    let active = true;
    void supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      setSession(data.session);
      if (data.session) { void loadTasks(data.session); void loadCatalog(data.session); }
      else { setLoading(false); setError("Masuk terlebih dahulu untuk melihat execution trace."); }
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, next) => {
      if (!active) return;
      setSession(next);
      if (next) { void loadTasks(next); void loadCatalog(next); }
      else { setTasks([]); setEvents([]); setSkills([]); setTools([]); setLoading(false); setError("Sesi berakhir. Silakan masuk kembali."); }
    });
    return () => { active = false; listener.subscription.unsubscribe(); };
  }, [supabase, loadTasks, loadCatalog]);

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
  const selectedSkill = skills.find(skill => skill.id === selectedSkillId);

  async function runToolPlan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session || !selectedSkill) return;
    setCreating(true); setError(""); setNotice("");
    let taskId = "";
    try {
      const parsedPlan = JSON.parse(planJson);
      if (!Array.isArray(parsedPlan) || parsedPlan.length < 1 || parsedPlan.length > 5) {
        throw new Error("Rencana harus berisi 1 sampai 5 langkah.");
      }
      const allowed = new Set(selectedSkill.tool_dependencies ?? []);
      for (const step of parsedPlan) {
        if (!step || typeof step !== "object" || typeof step.step_id !== "string" ||
            typeof step.tool_key !== "string" || !allowed.has(step.tool_key)) {
          throw new Error("Setiap tool harus tercantum pada Skill terpilih.");
        }
      }
      const maxCalls = Math.min(5, Number(selectedSkill.budget_limits?.max_tool_calls ?? parsedPlan.length));
      const maxRuntime = Math.min(30, Number(selectedSkill.budget_limits?.max_runtime_seconds ?? 30));
      if (maxCalls < parsedPlan.length) throw new Error("Budget Skill belum mengizinkan jumlah langkah pada rencana.");

      const sessionResponse = await fetch(`${apiBase}/v1/agent-runtime/sessions`, {
        method: "POST",
        headers: { Authorization: "Bearer " + session.access_token, "Content-Type": "application/json" },
        body: JSON.stringify({ agent_id: agentId, title: "Tool Plan · " + selectedSkill.name }),
      });
      if (!sessionResponse.ok) throw new Error(await responseError(sessionResponse));
      const sessionBody = await sessionResponse.json();
      const runtimeSessionId = sessionBody?.session?.id;
      if (typeof runtimeSessionId !== "string") throw new Error("Sesi Agent Runtime tidak mengembalikan ID yang valid.");

      const taskResponse = await fetch(`${apiBase}/v1/agent-runtime/tasks`, {
        method: "POST",
        headers: { Authorization: "Bearer " + session.access_token, "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: runtimeSessionId, skill_id: selectedSkill.id, tool_plan: parsedPlan,
          idempotency_key: globalThis.crypto.randomUUID(),
          budget_limits: { max_runtime_seconds: maxRuntime, max_tool_calls: parsedPlan.length },
        }),
      });
      if (!taskResponse.ok) throw new Error(await responseError(taskResponse));
      const taskBody = await taskResponse.json();
      taskId = taskBody?.task?.id;
      if (typeof taskId !== "string") throw new Error("Task tidak mengembalikan ID yang valid.");
      setSelectedTask(taskId);

      const executeResponse = await fetch(`${apiBase}/v1/agent-runtime/tasks/${encodeURIComponent(taskId)}/execute`, {
        method: "POST", headers: { Authorization: "Bearer " + session.access_token },
      });
      if (!executeResponse.ok) throw new Error(await responseError(executeResponse));
      setNotice("Rencana tool selesai diproses oleh Agent Runtime. Lihat urutan langkah pada Execution Trace.");
      await loadTasks(session);
      setSelectedTask(taskId);
    } catch (cause) {
      if (session) await loadTasks(session);
      if (taskId) setSelectedTask(taskId);
      setError(cause instanceof Error ? cause.message : "Rencana tool tidak dapat dijalankan.");
    } finally { setCreating(false); }
  }

  return <main className="mx-auto max-w-6xl space-y-6 p-4 sm:p-6">
    <header className="flex flex-wrap items-end justify-between gap-3 border-b pb-5">
      <div><p className="text-xs font-semibold uppercase tracking-[0.18em] text-neutral-500">Allpha · Agent Runtime</p><h1 className="mt-2 text-3xl font-semibold tracking-tight">Execution Trace</h1><p className="mt-2 max-w-2xl text-sm text-neutral-600">Riwayat task, state transition, dan trace yang tersimpan secara durable. Input, output, prompt, serta konten Memory privat tidak ditampilkan di timeline.</p></div>
      <div className="flex flex-wrap gap-2"><Link href={`/agents/${agentId}/studio`} className="rounded-xl border px-4 py-2 text-sm font-medium">Agent Studio</Link><Link href={`/agents/${agentId}/memory`} className="rounded-xl border px-4 py-2 text-sm font-medium">Memory Studio</Link><button onClick={() => session && void loadTasks(session)} disabled={loading} className="rounded-xl border px-4 py-2 text-sm font-medium disabled:opacity-50">{loading ? "Memuat…" : "Muat ulang"}</button></div>
    </header>
    {error && <div role="alert" className="rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-900">{error}</div>}
    {notice && <div role="status" className="rounded-xl border-2 border-slate-900 bg-emerald-100 p-3 text-sm font-bold text-slate-900 shadow-[2px_2px_0px_#0f172a]">{notice}</div>}
    <section className="space-y-4 rounded-3xl border-2 border-slate-900 bg-white p-4 shadow-[3px_3px_0px_#0f172a] sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><p className="text-[10px] font-black uppercase tracking-[0.18em] text-sky-700">Owner controlled · FastAPI</p><h2 className="mt-1 text-lg font-black uppercase text-slate-950">Tool Plan Composer</h2><p className="mt-1 max-w-3xl text-xs text-slate-600">Susun 1–5 langkah tool terdaftar. Output langkah sebelumnya dapat dipetakan ke input langkah berikutnya. Backend memeriksa ulang Skill, capability, policy, schema, dan budget sebelum eksekusi.</p></div>
        <span className="rounded-lg border-2 border-slate-900 bg-amber-200 px-2.5 py-1 text-[10px] font-black uppercase text-slate-950">Pure tools only</span>
      </div>
      {catalogError && <p role="alert" className="rounded-xl border border-rose-300 bg-rose-50 p-3 text-xs text-rose-800">{catalogError}</p>}
      <div className="flex flex-wrap gap-2">
        {tools.map(tool => <span key={tool.key} title={tool.description} className="rounded-lg border-2 border-slate-900 bg-slate-50 px-2.5 py-1 text-[10px] font-bold text-slate-800">{tool.key} · v{tool.version}</span>)}
      </div>
      <form onSubmit={runToolPlan} className="grid gap-3 lg:grid-cols-[minmax(220px,0.7fr)_minmax(0,1.5fr)]">
        <div className="space-y-2">
          <label htmlFor="runtime-skill" className="block text-xs font-black uppercase text-slate-800">Published Skill</label>
          <select id="runtime-skill" value={selectedSkillId} onChange={event => setSelectedSkillId(event.target.value)} disabled={creating || skills.length === 0} className="w-full rounded-xl border-2 border-slate-900 bg-white p-3 text-sm font-semibold text-slate-900 disabled:opacity-50">
            {skills.length === 0 ? <option value="">Tidak ada Skill published</option> : skills.map(skill => <option key={skill.id} value={skill.id}>{skill.name} · v{skill.version}</option>)}
          </select>
          {selectedSkill && <div className="rounded-xl border-2 border-slate-900 bg-slate-50 p-3 text-xs text-slate-700"><p className="font-bold">Tool yang diizinkan Skill</p><p className="mt-1 break-words">{selectedSkill.tool_dependencies.join(", ") || "Tidak ada dependensi tool"}</p><p className="mt-2">Budget: {selectedSkill.budget_limits?.max_tool_calls ?? 1} calls · {selectedSkill.budget_limits?.max_runtime_seconds ?? 30}s</p></div>}
          <p className="text-[11px] text-slate-500">Hanya Skill published milik Agent ini yang dapat dipilih.</p>
        </div>
        <div className="space-y-2">
          <label htmlFor="runtime-plan-json" className="block text-xs font-black uppercase text-slate-800">Rencana JSON</label>
          <textarea id="runtime-plan-json" value={planJson} onChange={event => setPlanJson(event.target.value)} rows={10} spellCheck={false} disabled={creating} className="w-full rounded-xl border-2 border-slate-900 bg-slate-950 p-3 font-mono text-xs text-slate-100 disabled:opacity-50" />
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-[11px] text-slate-500">Bindings: {"{ step_id, path }"} · Maksimal 5 langkah · Tanpa efek samping.</p>
            <button type="submit" disabled={creating || !session || !selectedSkill} className="rounded-xl border-2 border-slate-900 bg-[#0284C7] px-4 py-2 text-xs font-black text-white shadow-[2px_2px_0px_#0f172a] transition hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-50">{creating ? "Menjalankan…" : "Buat & Jalankan Plan"}</button>
          </div>
        </div>
      </form>
    </section>
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

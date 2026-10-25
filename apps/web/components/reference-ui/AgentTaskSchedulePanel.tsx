"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";

type SkillOption = {
  id: string; name: string; version: number; status: "draft" | "published" | "archived";
  required_permission_scopes: string[]; tool_dependencies: string[];
};
type ToolOption = { key: string; name: string; description: string; executable: boolean };
type Schedule = {
  id: string; title: string; agent_id: string; skill_id: string; tool_key: string;
  task_type: string; schedule_kind: "once" | "daily" | "weekly"; timezone_name: string;
  local_time: string; weekdays: number[]; next_run_at: string | null; last_run_at: string | null;
  status: string; require_approval: boolean; run_count: number; last_runtime_task_id?: string | null;
};
type ScheduleRun = { id: string; status: string; scheduled_for: string; result_summary?: string | null; error_code?: string | null; runtime_task_id?: string | null; trace_id: string };
const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const taskTypes = [
  ["SCHEDULING_POST", "Scheduling Postingan"], ["BROADCAST_INFO", "Broadcast Informasi"],
  ["KNOWLEDGE_DISPATCH", "Distribusi Knowledge"], ["ANALYTICS_REPORT", "Laporan Analitik"],
  ["SKILL_EXECUTION", "Eksekusi Skill"],
] as const;
const weekdays = [["0","Senin"],["1","Selasa"],["2","Rabu"],["3","Kamis"],["4","Jumat"],["5","Sabtu"],["6","Minggu"]] as const;

async function errorMessage(response: Response) {
  try { const body = await response.json(); return body?.error?.message ?? body?.detail?.message ?? `Permintaan gagal (${response.status}).`; }
  catch { return `Permintaan gagal (${response.status}).`; }
}

export default function AgentTaskSchedulePanel({ agentId, session, skills, tools }: {
  agentId: string; session: Session | null; skills: SkillOption[]; tools: ToolOption[];
}) {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [selectedSkill, setSelectedSkill] = useState("");
  const [selectedTool, setSelectedTool] = useState("");
  const [title, setTitle] = useState("");
  const [instructions, setInstructions] = useState("");
  const [taskType, setTaskType] = useState<(typeof taskTypes)[number][0]>("SKILL_EXECUTION");
  const [frequency, setFrequency] = useState<"once" | "daily" | "weekly">("daily");
  const [localTime, setLocalTime] = useState("18:00");
  const [runDate, setRunDate] = useState("");
  const [timezoneName, setTimezoneName] = useState("Asia/Jakarta");
  const [days, setDays] = useState<number[]>([0,1,2,3,4]);
  const [selectedScopes, setSelectedScopes] = useState<string[]>([]);
  const [requireApproval, setRequireApproval] = useState(true);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [runsBySchedule, setRunsBySchedule] = useState<Record<string, ScheduleRun[]>>({});

  const activeSkills = skills.filter(skill => skill.status === "published");
  const skill = activeSkills.find(item => item.id === selectedSkill);
  const availableTools = tools.filter(tool => tool.executable && (skill?.tool_dependencies ?? []).includes(tool.key));

  useEffect(() => {
    if (!skill) { setSelectedTool(""); setSelectedScopes([]); return; }
    if (!availableTools.some(tool => tool.key === selectedTool)) setSelectedTool(availableTools[0]?.key ?? "");
    setSelectedScopes(current => current.filter(scope => skill.required_permission_scopes.includes(scope)));
  }, [selectedSkill, skills]);

  const load = useCallback(async () => {
    if (!session) { setSchedules([]); return; }
    setLoading(true); setError("");
    try {
      const response = await fetch(`${apiBase}/v1/agent-task-schedules?limit=100`, {
        headers: { Authorization: "Bearer " + session.access_token }, cache: "no-store",
      });
      if (!response.ok) throw new Error(await errorMessage(response));
      const body = await response.json();
      const ownSchedules = (Array.isArray(body.items) ? body.items : []).filter((item: Schedule) => item.agent_id === agentId);
      setSchedules(ownSchedules);
      const histories = await Promise.all(ownSchedules.map(async (item: Schedule) => {
        const historyResponse = await fetch(`${apiBase}/v1/agent-task-schedules/${item.id}/runs?limit=5`, {
          headers: { Authorization: "Bearer " + session.access_token }, cache: "no-store",
        });
        if (!historyResponse.ok) return [item.id, []] as const;
        const history = await historyResponse.json();
        return [item.id, Array.isArray(history.items) ? history.items : []] as const;
      }));
      setRunsBySchedule(Object.fromEntries(histories));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Jadwal Task tidak dapat dimuat."); }
    finally { setLoading(false); }
  }, [agentId, session]);

  useEffect(() => { void load(); }, [load]);

  async function createSchedule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session || !skill || !selectedTool) return;
    setSaving(true); setError(""); setNotice("");
    try {
      const sessionResponse = await fetch(`${apiBase}/v1/agent-runtime/sessions`, {
        method: "POST",
        headers: { Authorization: "Bearer " + session.access_token, "Content-Type": "application/json" },
        body: JSON.stringify({ agent_id: agentId, title: `Task Schedule: ${title.trim().slice(0, 90)}` }),
      });
      if (!sessionResponse.ok) throw new Error(await errorMessage(sessionResponse));
      const sessionBody = await sessionResponse.json();
      const runtimeSessionId = sessionBody?.session?.id;
      if (typeof runtimeSessionId !== "string") throw new Error("Backend tidak mengembalikan ID sesi Agent Runtime.");

      const payload: Record<string, unknown> = {
        agent_id: agentId, session_id: runtimeSessionId, skill_id: skill.id, tool_key: selectedTool,
        title: title.trim(), instructions: instructions.trim(), task_type: taskType,
        schedule_kind: frequency, timezone_name: timezoneName, local_time: localTime,
        weekdays: frequency === "weekly" ? days : [],
        require_approval: requireApproval,
        granted_permission_scopes: selectedScopes,
        budget_limit: { max_runtime_seconds: 30, max_tool_calls: 1 },
        input_payload: { human_owner_instructions: instructions.trim() },
      };
      if (frequency === "once") {
        if (!runDate) throw new Error("Pilih tanggal dan waktu eksekusi satu kali.");
        const offset = timezoneName === "Asia/Jakarta" ? "+07:00" : "Z";
        payload.run_at = `${runDate}:${localTime}:00`.replace("::", ":") + offset;
      }
      const response = await fetch(`${apiBase}/v1/agent-task-schedules`, {
        method: "POST",
        headers: { Authorization: "Bearer " + session.access_token, "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(await errorMessage(response));
      setTitle(""); setInstructions(""); setNotice("Jadwal tersimpan di backend. Eksekusi hanya dimulai worker setelah policy dan izin lolos.");
      await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Task Schedule tidak dapat disimpan."); }
    finally { setSaving(false); }
  }

  async function updateStatus(schedule: Schedule, status: "active" | "paused" | "cancelled") {
    if (!session) return;
    setSaving(true); setError(""); setNotice("");
    try {
      const response = await fetch(`${apiBase}/v1/agent-task-schedules/${schedule.id}/status`, {
        method: "PATCH", headers: { Authorization: "Bearer " + session.access_token, "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      if (!response.ok) throw new Error(await errorMessage(response));
      setNotice("Status jadwal diperbarui oleh backend."); await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Status jadwal tidak dapat diperbarui."); }
    finally { setSaving(false); }
  }

  async function approveRun(schedule: Schedule, run: ScheduleRun) {
    if (!session) return;
    setSaving(true); setError(""); setNotice("");
    try {
      const response = await fetch(`${apiBase}/v1/agent-task-schedules/${schedule.id}/runs/${run.id}/approve`, {
        method: "POST", headers: { Authorization: "Bearer " + session.access_token },
      });
      if (!response.ok) throw new Error(await errorMessage(response));
      setNotice("Persetujuan Human Owner tersimpan. Worker akan mengambil eksekusi sesuai antrean persisten."); await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Persetujuan tidak dapat disimpan."); }
    finally { setSaving(false); }
  }

  const inputClass = "w-full rounded-xl border-2 border-slate-900 bg-white px-3 py-2 text-xs font-bold text-slate-900 outline-none focus:ring-2 focus:ring-sky-300";
  const labelClass = "mb-1 block text-[10px] font-black uppercase tracking-wide text-slate-700";
  const buttonClass = "rounded-xl border-2 border-slate-900 bg-[#0284C7] px-3 py-2 text-xs font-black text-white shadow-[2px_2px_0px_#0f172a] transition disabled:opacity-50";
  return <section className="space-y-4 rounded-3xl border-2 border-slate-900 bg-white p-4 shadow-[4px_4px_0px_#0f172a] sm:p-5">
    <header className="flex flex-wrap items-start justify-between gap-3 border-b-2 border-slate-900 pb-3">
      <div className="flex items-center gap-2.5">
        <div className="flex h-10 w-10 items-center justify-center rounded-2xl border-2 border-slate-900 bg-amber-200 text-slate-950 shadow-[1.5px_1.5px_0px_#0f172a]">◷</div>
        <div><h2 className="text-sm font-black uppercase text-slate-900">Task Scheduling AI Agent</h2><p className="text-[11px] font-bold text-slate-500">Jadwal persisten · Workflow Engine · Agent Runtime</p></div>
      </div>
      <button type="button" onClick={() => void load()} disabled={loading} className="rounded-xl border-2 border-slate-900 bg-white px-3 py-1.5 text-xs font-black text-slate-800 shadow-[1.5px_1.5px_0px_#0f172a] disabled:opacity-50">{loading ? "Memuat…" : "Muat Ulang"}</button>
    </header>
    {error && <div role="alert" className="rounded-xl border-2 border-rose-500 bg-rose-50 p-3 text-xs font-bold text-rose-900">{error}</div>}
    {notice && <div role="status" className="rounded-xl border-2 border-emerald-600 bg-emerald-50 p-3 text-xs font-bold text-emerald-900">{notice}</div>}
    <form onSubmit={createSchedule} className="space-y-3">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label><span className={labelClass}>Nama Task</span><input required maxLength={160} value={title} onChange={e => setTitle(e.target.value)} className={inputClass} placeholder="Contoh: Laporan analitik harian" /></label>
        <label><span className={labelClass}>Jenis Task</span><select value={taskType} onChange={e => setTaskType(e.target.value as typeof taskType)} className={inputClass}>{taskTypes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label className="sm:col-span-2"><span className={labelClass}>Instruksi Human Owner</span><textarea required maxLength={8000} value={instructions} onChange={e => setInstructions(e.target.value)} rows={3} className={inputClass} placeholder="Instruksi, batasan, sumber yang boleh dipakai, dan hasil yang diharapkan." /></label>
        <label><span className={labelClass}>Skill Terpublikasi</span><select required value={selectedSkill} onChange={e => setSelectedSkill(e.target.value)} className={inputClass}><option value="">Pilih Skill</option>{activeSkills.map(item => <option key={item.id} value={item.id}>{item.name} · v{item.version}</option>)}</select></label>
        <label><span className={labelClass}>Tool Terdaftar</span><select required value={selectedTool} onChange={e => setSelectedTool(e.target.value)} className={inputClass}><option value="">Pilih Tool</option>{availableTools.map(item => <option key={item.key} value={item.key}>{item.name} ({item.key})</option>)}</select></label>
        <label><span className={labelClass}>Frekuensi</span><select value={frequency} onChange={e => setFrequency(e.target.value as typeof frequency)} className={inputClass}><option value="once">Sekali</option><option value="daily">Harian</option><option value="weekly">Mingguan</option></select></label>
        <label><span className={labelClass}>Zona Waktu (IANA)</span><input required value={timezoneName} onChange={e => setTimezoneName(e.target.value)} className={inputClass} placeholder="Asia/Jakarta" /></label>
        {frequency === "once" && <label><span className={labelClass}>Tanggal Eksekusi</span><input required type="date" value={runDate} onChange={e => setRunDate(e.target.value)} className={inputClass} /></label>}
        <label><span className={labelClass}>Waktu Lokal</span><input required type="time" value={localTime} onChange={e => setLocalTime(e.target.value)} className={inputClass} /></label>
      </div>
      {frequency === "weekly" && <fieldset className="space-y-2"><legend className={labelClass}>Hari Aktif</legend><div className="flex flex-wrap gap-2">{weekdays.map(([value, label]) => <label key={value} className="flex items-center gap-1.5 rounded-lg border border-slate-400 px-2 py-1 text-[11px] font-bold"><input type="checkbox" checked={days.includes(Number(value))} onChange={e => setDays(current => e.target.checked ? [...current, Number(value)].sort() : current.filter(day => day !== Number(value))} />{label}</label>)}</div></fieldset>}
      {skill && <fieldset className="space-y-2"><legend className={labelClass}>Izin yang diberikan untuk Task</legend>{skill.required_permission_scopes.length ? <div className="flex flex-wrap gap-2">{skill.required_permission_scopes.map(scope => <label key={scope} className="flex items-center gap-1.5 rounded-lg border border-slate-400 px-2 py-1 text-[11px] font-bold"><input type="checkbox" checked={selectedScopes.includes(scope)} onChange={e => setSelectedScopes(current => e.target.checked ? [...current, scope] : current.filter(item => item !== scope))} />{scope}</label>)}</div> : <p className="text-xs text-slate-500">Skill ini tidak meminta scope izin eksplisit.</p>}</fieldset>}
      <label className="flex items-start gap-2 rounded-xl border-2 border-slate-900 bg-amber-50 p-3 text-xs font-bold text-slate-800"><input type="checkbox" checked={requireApproval} onChange={e => setRequireApproval(e.target.checked)} className="mt-0.5" /><span>Wajib persetujuan Human Owner sebelum setiap eksekusi. Jika dinonaktifkan, task tetap harus lolos policy, izin, dan budget Agent Runtime.</span></label>
      <button type="submit" disabled={!session || saving || !skill || !selectedTool || (frequency === "weekly" && days.length === 0)} className={buttonClass}>{saving ? "Menyimpan…" : "Simpan Jadwal Task"}</button>
      {(!activeSkills.length || !tools.length) && <p className="text-[11px] font-bold text-amber-800">Jadwal memerlukan Skill terpublikasi dan katalog Tool kanonis yang tersedia.</p>}
    </form>
    <div className="space-y-3 border-t-2 border-slate-900 pt-4">
      <div className="flex items-center justify-between"><h3 className="text-xs font-black uppercase text-slate-900">Daftar Jadwal & Hasil Aktual</h3><span className="text-[10px] font-bold text-slate-500">{schedules.length} jadwal</span></div>
      {!schedules.length && <div className="rounded-2xl border-2 border-dashed border-slate-400 p-4 text-xs font-bold text-slate-500">{loading ? "Memuat jadwal…" : "Belum ada jadwal task tersimpan untuk Agent ini."}</div>}
      {schedules.map(schedule => <article key={schedule.id} className="space-y-2 rounded-2xl border-2 border-slate-900 bg-slate-50 p-3 shadow-[2px_2px_0px_#0f172a]">
        <div className="flex flex-wrap items-start justify-between gap-2"><div><h4 className="text-xs font-black text-slate-900">{schedule.title}</h4><p className="mt-1 text-[10px] font-bold text-slate-600">{schedule.task_type} · {schedule.schedule_kind} · {schedule.local_time} {schedule.timezone_name}</p></div><span className="rounded-lg border border-slate-900 bg-amber-200 px-2 py-0.5 text-[10px] font-black">{schedule.status}</span></div>
        <div className="grid grid-cols-1 gap-2 text-[10px] sm:grid-cols-2"><p><b>Eksekusi terakhir:</b> {schedule.last_run_at ? new Date(schedule.last_run_at).toLocaleString("id-ID") : "Belum pernah"}</p><p><b>Jadwal berikutnya:</b> {schedule.next_run_at ? new Date(schedule.next_run_at).toLocaleString("id-ID") : "Tidak ada jadwal berikutnya"}</p></div>
        <div className="flex flex-wrap gap-2">{schedule.status === "paused" ? <button type="button" disabled={saving} onClick={() => void updateStatus(schedule, "active")} className={buttonClass}>Lanjutkan</button> : schedule.status === "active" && <button type="button" disabled={saving} onClick={() => void updateStatus(schedule, "paused")} className="rounded-xl border-2 border-slate-900 bg-white px-3 py-2 text-xs font-black text-slate-800 shadow-[2px_2px_0px_#0f172a]">Jeda</button>}{["active","paused"].includes(schedule.status) && <button type="button" disabled={saving} onClick={() => void updateStatus(schedule, "cancelled")} className="rounded-xl border-2 border-slate-900 bg-rose-100 px-3 py-2 text-xs font-black text-rose-900 shadow-[2px_2px_0px_#0f172a]">Batalkan</button>}</div>
        <div className="space-y-2 border-t border-slate-300 pt-2"><p className="text-[10px] font-black uppercase text-slate-700">Riwayat Eksekusi</p>{(runsBySchedule[schedule.id] ?? []).length ? (runsBySchedule[schedule.id] ?? []).map(run => <div key={run.id} className="rounded-xl border border-slate-300 bg-white p-2 text-[10px]"><div className="flex flex-wrap justify-between gap-2"><b>{run.status}</b><span>{new Date(run.scheduled_for).toLocaleString("id-ID")}</span></div>{run.result_summary && <p className="mt-1">{run.result_summary}</p>}{run.error_code && <p className="mt-1 text-rose-700">Kode error: {run.error_code}</p>}{run.status === "waiting_for_approval" && <button type="button" disabled={saving} onClick={() => void approveRun(schedule, run)} className={buttonClass}>Setujui Eksekusi</button>}<p className="mt-1 text-slate-500">Trace: {run.trace_id}</p></div>) : <p className="text-[10px] text-slate-500">Belum ada catatan eksekusi.</p>}</div>
      </article>)}
    </div>
  </section>;
}

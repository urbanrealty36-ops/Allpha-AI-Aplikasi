'use client';

import React, { useState } from 'react';
import { 
  Target, 
  CheckCircle2, 
  X, 
  Play, 
  Plus, 
  Calendar, 
  Clock, 
  Bot, 
  Sparkles, 
  Zap, 
  Radio, 
  AlertCircle, 
  RotateCw, 
  Trash2,
  Check,
  Send,
  FileText,
  TrendingUp,
  Cpu,
  BarChart3,
  Flame
} from 'lucide-react';
import type { AgentGoalItem, AgentTaskItem, AIAgentProfile } from '@/lib/reference-store';

interface AgentGoalsTasksModalProps {
  isOpen: boolean;
  onClose: () => void;
  agent: AIAgentProfile;
  onUpdateAgent: (updatedAgent: AIAgentProfile) => void;
  onToast: (msg: string) => void;
}

export default function AgentGoalsTasksModal({
  isOpen,
  onClose,
  agent,
  onUpdateAgent,
  onToast,
}: AgentGoalsTasksModalProps) {
  const [activeTab, setActiveTab] = useState<'TASKS' | 'GOALS'>('TASKS');

  const [goals, setGoals] = useState<AgentGoalItem[]>(
    agent.goals ?? []
  );

  const [tasks, setTasks] = useState<AgentTaskItem[]>(
    agent.tasks ?? []
  );

  // New Task Form Modal State
  const [isCreatingTask, setIsCreatingTask] = useState(false);
  const [newTaskTitle, setNewTaskTitle] = useState('');
  const [newTaskType, setNewTaskType] = useState<AgentTaskItem['type']>('SCHEDULING_POST');
  const [newTaskFrequency, setNewTaskFrequency] = useState<AgentTaskItem['frequency']>('Harian');
  const [newTaskScheduledTime, setNewTaskScheduledTime] = useState('18:00 WIB');
  const [newTaskAutonomous, setNewTaskAutonomous] = useState(true);

  // New Goal Form State
  const [isCreatingGoal, setIsCreatingGoal] = useState(false);
  const [newGoalTitle, setNewGoalTitle] = useState('');
  const [newGoalPriority, setNewGoalPriority] = useState<'HIGH' | 'MEDIUM' | 'LOW'>('HIGH');
  const [newGoalTargetDate, setNewGoalTargetDate] = useState('2026-11-30');

  // Running task state simulator
  const [runningTaskId, setRunningTaskId] = useState<string | null>(null);

  if (!isOpen) return null;

  // Toggle Autonomous Execution
  const handleToggleAutonomous = (taskId: string) => {
    const updated = tasks.map((t) => {
      if (t.id === taskId) {
        const nextState = !t.autonomousExecution;
        onToast(
          nextState
            ? `Mode Otonom AKTIF: AI Agent ${agent.name} akan mengeksekusi tugas ini otomatis.`
            : `Mode Otonom NON-AKTIF: Tugas ini memerlukan persetujuan manual Anda.`
        );
        return { ...t, autonomousExecution: nextState };
      }
      return t;
    });

    setTasks(updated);
    onUpdateAgent({ ...agent, tasks: updated });
  };

  // Run Task Instantly
  const handleRunTaskNow = (task: AgentTaskItem) => {
    setRunningTaskId(task.id);
    onToast(`Memulai eksekusi tugas "${task.title}" oleh ${agent.name}...`);

    setTimeout(() => {
      const now = new Date().toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' });
      const updated = tasks.map((t) => {
        if (t.id === task.id) {
          return {
            ...t,
            status: 'COMPLETED' as const,
            lastRun: `Hari ini, ${now} WIB`,
            outputSummary: `Eksekusi otonom berhasil! Draf dan log terkirim ke sistem Allpha.`,
          };
        }
        return t;
      });

      setTasks(updated);
      setRunningTaskId(null);
      onUpdateAgent({ ...agent, tasks: updated });
      onToast(`Tugas "${task.title}" selesai dieksekusi oleh AI Agent!`);
    }, 1800);
  };

  // Delete Task
  const handleDeleteTask = (taskId: string) => {
    const updated = tasks.filter((t) => t.id !== taskId);
    setTasks(updated);
    onUpdateAgent({ ...agent, tasks: updated });
    onToast('Tugas berhasil dihapus.');
  };

  // Create New Task
  const handleCreateTask = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTaskTitle.trim()) return;

    const newTask: AgentTaskItem = {
      id: `t-${Date.now()}`,
      title: newTaskTitle.trim(),
      type: newTaskType,
      frequency: newTaskFrequency,
      status: 'IN_PROGRESS',
      autonomousExecution: newTaskAutonomous,
      scheduledTime: newTaskScheduledTime,
      lastRun: 'Baru dibuat',
      nextRun: `Hari ini, ${newTaskScheduledTime}`,
      outputSummary: 'Tugas sedang dipantau oleh mesin penalaran otonom Allpha.',
    };

    const updated = [newTask, ...tasks];
    setTasks(updated);
    onUpdateAgent({ ...agent, tasks: updated });
    setIsCreatingTask(false);
    setNewTaskTitle('');
    onToast(`Tugas otonom baru berhasil ditugaskan ke ${agent.name}!`);
  };

  // Create New Goal
  const handleCreateGoal = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newGoalTitle.trim()) return;

    const newGoal: AgentGoalItem = {
      id: `g-${Date.now()}`,
      title: newGoalTitle.trim(),
      bidang: agent.bidang || 'Desain Grafis',
      targetDate: newGoalTargetDate,
      priority: newGoalPriority,
      status: 'ACTIVE',
      progress: 20,
    };

    const updated = [newGoal, ...goals];
    setGoals(updated);
    onUpdateAgent({ ...agent, goals: updated });
    setIsCreatingGoal(false);
    setNewGoalTitle('');
    onToast(`Target strategis baru berhasil ditetapkan untuk ${agent.name}!`);
  };

  const getTypeBadge = (type: AgentTaskItem['type']) => {
    switch (type) {
      case 'SCHEDULING_POST':
        return { label: '📅 Scheduling Postingan', color: 'bg-blue-50 text-blue-700 border-blue-200' };
      case 'BROADCAST_INFO':
        return { label: '📢 Broadcast Informasi', color: 'bg-purple-50 text-purple-700 border-purple-200' };
      case 'SKILL_EXECUTION':
        return { label: '⚡ Eksekusi Skill Brand', color: 'bg-amber-50 text-amber-700 border-amber-200' };
      case 'ANALYTICS_REPORT':
        return { label: '📊 Laporan Analitik', color: 'bg-emerald-50 text-emerald-700 border-emerald-200' };
      default:
        return { label: '🤖 Tugas AI', color: 'bg-slate-100 text-slate-700 border-slate-200' };
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-slate-900/80 backdrop-blur-xs animate-fade-in">
      <div className="w-full max-w-xl rounded-3xl bg-white shadow-[6px_6px_0px_#0f172a] border-3 border-slate-900 p-5 max-h-[92vh] overflow-y-auto space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b-2 border-slate-900">
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-2xl bg-amber-200 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] text-slate-950 flex items-center justify-center">
              <Target className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-black text-slate-900 uppercase">
                Pusat Target & Tugas Otonom AI Agent
              </h2>
              <p className="text-[11px] font-bold text-slate-500">
                Berikan tugas mandiri ke {agent.name} ({agent.handle}) sesuai bidang {agent.bidang || 'Kreatif'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-slate-700 hover:bg-slate-100 transition active:translate-x-0.5 active:translate-y-0.5"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab Switcher: Tasks vs Goals */}
        <div className="flex p-1 rounded-2xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-xs font-black">
          <button
            onClick={() => setActiveTab('TASKS')}
            className={`flex-1 py-2 rounded-xl transition flex items-center justify-center gap-1.5 active:translate-x-0.5 active:translate-y-0.5 ${
              activeTab === 'TASKS'
                ? 'bg-[#0284C7] text-white border-2 border-slate-900 shadow-[1px_1px_0px_#0f172a]'
                : 'text-slate-700 hover:bg-slate-50'
            }`}
          >
            <Zap className="w-3.5 h-3.5" />
            <span>Tugas Otonom ({tasks.length})</span>
          </button>
          <button
            onClick={() => setActiveTab('GOALS')}
            className={`flex-1 py-2 rounded-xl transition flex items-center justify-center gap-1.5 active:translate-x-0.5 active:translate-y-0.5 ${
              activeTab === 'GOALS'
                ? 'bg-purple-600 text-white border-2 border-slate-900 shadow-[1px_1px_0px_#0f172a]'
                : 'text-slate-700 hover:bg-slate-50'
            }`}
          >
            <Target className="w-3.5 h-3.5" />
            <span>Target & Goals ({goals.length})</span>
          </button>
        </div>

        {/* ======================================================== */}
        {/* TAB 1: AUTONOMOUS TASKS                                 */}
        {/* ======================================================== */}
        {activeTab === 'TASKS' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xs font-black text-slate-900 uppercase">Daftar Tugas Mandiri AI Agent</h3>
                <p className="text-[11px] font-bold text-slate-500">
                  Tugas yang dijalankan secara terjadwal atau otonom oleh AI tanpa intervensi manual
                </p>
              </div>
              <button
                onClick={() => setIsCreatingTask(true)}
                className="px-3.5 py-1.5 rounded-xl bg-[#0284C7] hover:bg-sky-600 text-white font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] transition flex items-center gap-1 active:translate-x-0.5 active:translate-y-0.5"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Tambah Tugas</span>
              </button>
            </div>

            {/* Tasks List */}
            <div className="space-y-3">
              {tasks.map((task) => {
                const badge = getTypeBadge(task.type);
                const isRunning = runningTaskId === task.id;

                return (
                  <div
                    key={task.id}
                    className="p-4 rounded-2xl bg-slate-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] space-y-2.5"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="space-y-1">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className={`text-[10px] px-2.5 py-0.5 rounded-lg font-black border border-slate-900 ${badge.color}`}>
                            {badge.label}
                          </span>
                          <span className="text-[10px] px-2 py-0.5 rounded-lg bg-amber-200 text-slate-950 font-black border border-slate-900">
                            {task.frequency}
                          </span>
                          {task.scheduledTime && (
                            <span className="text-[10px] text-slate-700 font-mono font-bold flex items-center gap-0.5">
                              <Clock className="w-3 h-3 text-slate-900" />
                              {task.scheduledTime}
                            </span>
                          )}
                        </div>
                        <h4 className="text-xs font-black text-slate-900">{task.title}</h4>
                      </div>

                      {/* Autonomous Toggle Switch */}
                      <button
                        onClick={() => handleToggleAutonomous(task.id)}
                        className={`shrink-0 px-2.5 py-1 rounded-xl text-[10px] font-black transition flex items-center gap-1 border-2 border-slate-900 active:translate-x-0.5 active:translate-y-0.5 ${
                          task.autonomousExecution
                            ? 'bg-emerald-200 text-slate-950 shadow-[1.5px_1.5px_0px_#0f172a]'
                            : 'bg-white text-slate-700'
                        }`}
                        title="Klik untuk mengubah mode otonom"
                      >
                        <span className={`w-2 h-2 rounded-full border border-slate-900 ${task.autonomousExecution ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400'}`} />
                        <span>{task.autonomousExecution ? 'Otonom Aktif' : 'Manual'}</span>
                      </button>
                    </div>

                    {/* Output log / last run */}
                    <div className="p-2.5 rounded-xl bg-white border border-slate-300 text-[10px] text-slate-700 font-medium space-y-1">
                      <div className="flex justify-between text-slate-500 font-bold">
                        <span>Terakhir Dieksekusi: <strong className="text-slate-900">{task.lastRun || 'Belum pernah'}</strong></span>
                        <span>Jadwal Berikutnya: <strong className="text-slate-900">{task.nextRun || 'Sesuai jadwal'}</strong></span>
                      </div>
                      {task.outputSummary && (
                        <p className="text-slate-900 font-bold pt-1 border-t border-slate-100">
                          {task.outputSummary}
                        </p>
                      )}
                    </div>

                    {/* Action Bar */}
                    <div className="flex items-center justify-between pt-1 text-xs">
                      <span className={`text-[10px] font-black ${
                        task.status === 'COMPLETED' ? 'text-emerald-700' : 'text-blue-700'
                      }`}>
                        Status: {task.status === 'COMPLETED' ? '✓ Siap / Selesai' : '⏳ Siaga / Menunggu Jadwal'}
                      </span>

                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={() => handleRunTaskNow(task)}
                          disabled={isRunning}
                          className="px-3 py-1.5 rounded-xl bg-[#0284C7] hover:bg-sky-600 text-white text-[10px] font-black transition flex items-center gap-1 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 disabled:opacity-50"
                        >
                          {isRunning ? (
                            <>
                              <RotateCw className="w-3 h-3 animate-spin" />
                              <span>Mengeksekusi...</span>
                            </>
                          ) : (
                            <>
                              <Play className="w-3 h-3 fill-white" />
                              <span>Jalankan Sekarang</span>
                            </>
                          )}
                        </button>
                        <button
                          onClick={() => handleDeleteTask(task.id)}
                          className="p-1.5 rounded-xl bg-white hover:bg-rose-100 text-rose-600 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] transition active:translate-x-0.5 active:translate-y-0.5"
                          title="Hapus Tugas"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ======================================================== */}
        {/* TAB 2: LONG-TERM GOALS                                  */}
        {/* ======================================================== */}
        {activeTab === 'GOALS' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xs font-black text-slate-900">Target Strategis (Goals) AI Agent</h3>
                <p className="text-[11px] text-slate-500">
                  Arahkan fokus pencapaian AI Agent untuk engagement, brand monetization, dan followers
                </p>
              </div>
              <button
                onClick={() => setIsCreatingGoal(true)}
                className="px-3.5 py-1.5 rounded-xl bg-purple-300 hover:bg-purple-400 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] transition flex items-center gap-1 active:translate-x-0.5 active:translate-y-0.5 cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5 stroke-[3px]" />
                <span>Tambah Goal</span>
              </button>
            </div>

            <div className="space-y-3">
              {goals.map((goal) => (
                <div
                  key={goal.id}
                  className="p-4 rounded-2xl bg-white border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] space-y-2.5"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-1.5 mb-1 flex-wrap">
                        <span className={`text-[9.5px] px-2.5 py-0.5 rounded-lg font-black border border-slate-900 ${
                          goal.priority === 'HIGH'
                            ? 'bg-rose-200 text-rose-950'
                            : 'bg-sky-200 text-sky-950'
                        }`}>
                          Prioritas {goal.priority}
                        </span>
                        <span className="text-[10px] text-slate-900 font-mono font-bold bg-amber-100 px-2 py-0.5 rounded-lg border border-slate-900">
                          Bidang: {goal.bidang}
                        </span>
                      </div>
                      <h4 className="text-xs font-black text-slate-950">{goal.title}</h4>
                    </div>

                    <span className="font-mono text-xs font-black text-slate-950 bg-sky-200 px-2 py-0.5 rounded-lg border border-slate-900">
                      {goal.progress}%
                    </span>
                  </div>

                  {/* Progress Bar */}
                  <div className="w-full h-3 rounded-full bg-slate-100 border-2 border-slate-900 overflow-hidden shadow-2xs">
                    <div
                      className="h-full bg-sky-400 rounded-full transition-all duration-500 border-r border-slate-900"
                      style={{ width: `${goal.progress}%` }}
                    />
                  </div>

                  <div className="flex items-center justify-between text-[11px] font-bold text-slate-600">
                    <span>Target: <strong className="text-slate-950">{goal.targetDate}</strong></span>
                    <button
                      onClick={() => {
                        const nextProg = Math.min(100, goal.progress + 15);
                        const updated = goals.map(g => g.id === goal.id ? { ...g, progress: nextProg } : g);
                        setGoals(updated);
                        onUpdateAgent({ ...agent, goals: updated });
                        onToast(`Progres target ditingkatkan menjadi ${nextProg}%!`);
                      }}
                      className="text-sky-700 font-black hover:underline cursor-pointer"
                    >
                      + Tambah Progres Capaian
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ======================================================== */}
        {/* MODAL / FORM: TAMBAH TUGAS OTONOM BARU                  */}
        {/* ======================================================== */}
        {isCreatingTask && (
          <div className="p-4 rounded-3xl bg-sky-50 border-2 border-slate-900 shadow-[4px_4px_0px_#0f172a] space-y-3 animate-fade-in text-xs">
            <div className="flex items-center justify-between">
              <h4 className="font-black text-slate-950 flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-sky-700 stroke-[2.5px]" />
                <span>Buat Tugas Mandiri Otonom Baru</span>
              </h4>
              <button
                onClick={() => setIsCreatingTask(false)}
                className="w-7 h-7 rounded-xl bg-white border-2 border-slate-900 text-slate-950 font-black flex items-center justify-center cursor-pointer shadow-[1px_1px_0px_#0f172a]"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateTask} className="space-y-3">
              <div>
                <label className="font-black text-slate-900 block mb-1">Judul / Instruksi Tugas:</label>
                <input
                  type="text"
                  required
                  value={newTaskTitle}
                  onChange={(e) => setNewTaskTitle(e.target.value)}
                  placeholder="Misal: Jadwalkan postingan tips arsitektur 3D"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-white border-2 border-slate-900 font-bold text-slate-950 outline-none shadow-[1.5px_1.5px_0px_#0f172a]"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="font-black text-slate-900 block mb-1">Jenis Tugas:</label>
                  <select
                    value={newTaskType}
                    onChange={(e) => setNewTaskType(e.target.value as AgentTaskItem['type'])}
                    className="w-full px-3 py-2 rounded-xl bg-white border-2 border-slate-900 font-black text-xs text-slate-950 shadow-[1.5px_1.5px_0px_#0f172a]"
                  >
                    <option value="SCHEDULING_POST">📅 Scheduling Postingan</option>
                    <option value="BROADCAST_INFO">📢 Broadcast Informasi</option>
                    <option value="SKILL_EXECUTION">⚡ Eksekusi Skill Brand</option>
                    <option value="ANALYTICS_REPORT">📊 Laporan Analitik</option>
                  </select>
                </div>
                <div>
                  <label className="font-black text-slate-900 block mb-1">Frekuensi:</label>
                  <select
                    value={newTaskFrequency}
                    onChange={(e) => setNewTaskFrequency(e.target.value as AgentTaskItem['frequency'])}
                    className="w-full px-3 py-2 rounded-xl bg-white border-2 border-slate-900 font-black text-xs text-slate-950 shadow-[1.5px_1.5px_0px_#0f172a]"
                  >
                    <option value="Harian">Harian</option>
                    <option value="Mingguan">Mingguan</option>
                    <option value="Sekali">Sekali Saja</option>
                    <option value="Real-time Event">Real-time Siaga</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="font-black text-slate-900 block mb-1">Waktu Eksekusi:</label>
                  <input
                    type="text"
                    value={newTaskScheduledTime}
                    onChange={(e) => setNewTaskScheduledTime(e.target.value)}
                    placeholder="Contoh: 19:00 WIB"
                    className="w-full px-3 py-2 rounded-xl bg-white border-2 border-slate-900 font-bold text-slate-950 text-xs shadow-[1.5px_1.5px_0px_#0f172a]"
                  />
                </div>
                <div className="flex items-center gap-2 pt-5">
                  <input
                    type="checkbox"
                    id="autonomousCheck"
                    checked={newTaskAutonomous}
                    onChange={(e) => setNewTaskAutonomous(e.target.checked)}
                    className="w-4.5 h-4.5 accent-sky-500 rounded border-2 border-slate-900 cursor-pointer"
                  />
                  <label htmlFor="autonomousCheck" className="font-black text-slate-950 text-[11px] cursor-pointer">
                    Eksekusi Otonom (AI Auto-Pilot)
                  </label>
                </div>
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  type="submit"
                  className="flex-1 py-2.5 rounded-xl bg-sky-300 hover:bg-sky-400 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
                >
                  Tugaskan ke {agent.name}
                </button>
                <button
                  type="button"
                  onClick={() => setIsCreatingTask(false)}
                  className="px-4 py-2.5 rounded-xl bg-white hover:bg-slate-50 border-2 border-slate-900 text-slate-950 font-black text-xs shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 cursor-pointer"
                >
                  Batal
                </button>
              </div>
            </form>
          </div>
        )}

        {/* ======================================================== */}
        {/* MODAL / FORM: TAMBAH GOAL STRATEGIS BARU                */}
        {/* ======================================================== */}
        {isCreatingGoal && (
          <div className="p-4 rounded-3xl bg-purple-50 border-2 border-slate-900 shadow-[4px_4px_0px_#0f172a] space-y-3 animate-fade-in text-xs">
            <div className="flex items-center justify-between">
              <h4 className="font-black text-slate-950 flex items-center gap-1.5">
                <Target className="w-4 h-4 text-purple-700 stroke-[2.5px]" />
                <span>Buat Target Strategis (Goal) Baru</span>
              </h4>
              <button
                onClick={() => setIsCreatingGoal(false)}
                className="w-7 h-7 rounded-xl bg-white border-2 border-slate-900 text-slate-950 font-black flex items-center justify-center cursor-pointer shadow-[1px_1px_0px_#0f172a]"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateGoal} className="space-y-3">
              <div>
                <label className="font-black text-slate-900 block mb-1">Judul Target:</label>
                <input
                  type="text"
                  required
                  value={newGoalTitle}
                  onChange={(e) => setNewGoalTitle(e.target.value)}
                  placeholder="Misal: Mencapai 50K followers dan 500 AI Credits dari sesi konsultasi"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-white border-2 border-slate-900 font-bold text-slate-950 outline-none shadow-[1.5px_1.5px_0px_#0f172a]"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="font-black text-slate-900 block mb-1">Prioritas:</label>
                  <select
                    value={newGoalPriority}
                    onChange={(e) => setNewGoalPriority(e.target.value as 'HIGH' | 'MEDIUM' | 'LOW')}
                    className="w-full px-3 py-2 rounded-xl bg-white border-2 border-slate-900 font-black text-xs text-slate-950 shadow-[1.5px_1.5px_0px_#0f172a]"
                  >
                    <option value="HIGH">Tinggi (High)</option>
                    <option value="MEDIUM">Sedang (Medium)</option>
                    <option value="LOW">Rendah (Low)</option>
                  </select>
                </div>
                <div>
                  <label className="font-black text-slate-900 block mb-1">Target Selesai:</label>
                  <input
                    type="date"
                    value={newGoalTargetDate}
                    onChange={(e) => setNewGoalTargetDate(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-white border-2 border-slate-900 font-bold text-xs text-slate-950 shadow-[1.5px_1.5px_0px_#0f172a]"
                  />
                </div>
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  type="submit"
                  className="flex-1 py-2.5 rounded-xl bg-purple-300 hover:bg-purple-400 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
                >
                  Simpan Target
                </button>
                <button
                  type="button"
                  onClick={() => setIsCreatingGoal(false)}
                  className="px-4 py-2.5 rounded-xl bg-white hover:bg-slate-50 border-2 border-slate-900 text-slate-950 font-black text-xs shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 cursor-pointer"
                >
                  Batal
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Footer */}
        <div className="pt-2 flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2.5 rounded-2xl bg-white hover:bg-slate-50 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
          >
            Tutup
          </button>
        </div>
      </div>
    </div>
  );
}

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
import { 
  AgentGoalItem, 
  AgentTaskItem, 
  AIAgentProfile, 
  INITIAL_AGENT_GOALS, 
  INITIAL_AGENT_TASKS 
} from '@/lib/reference-store';

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
    agent.goals && agent.goals.length > 0 ? agent.goals : INITIAL_AGENT_GOALS
  );

  const [tasks, setTasks] = useState<AgentTaskItem[]>(
    agent.tasks && agent.tasks.length > 0 ? agent.tasks : INITIAL_AGENT_TASKS
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/60 backdrop-blur-xs animate-fade-in">
      <div className="w-full max-w-xl rounded-3xl bg-white shadow-2xl border border-slate-200 p-5 max-h-[92vh] overflow-y-auto space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-2xl bg-gradient-to-tr from-cyan-600 to-blue-600 text-white flex items-center justify-center shadow-md">
              <Target className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-black text-slate-900">
                Pusat Target & Tugas Otonom AI Agent
              </h2>
              <p className="text-[11px] text-slate-500">
                Berikan tugas mandiri ke {agent.name} ({agent.handle}) sesuai bidang {agent.bidang || 'Kreatif'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-full text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab Switcher: Tasks vs Goals */}
        <div className="flex p-1 rounded-2xl bg-slate-100 text-xs font-bold">
          <button
            onClick={() => setActiveTab('TASKS')}
            className={`flex-1 py-2 rounded-xl transition flex items-center justify-center gap-1.5 ${
              activeTab === 'TASKS'
                ? 'bg-blue-600 text-white shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Zap className="w-3.5 h-3.5" />
            <span>Tugas Otonom ({tasks.length})</span>
          </button>
          <button
            onClick={() => setActiveTab('GOALS')}
            className={`flex-1 py-2 rounded-xl transition flex items-center justify-center gap-1.5 ${
              activeTab === 'GOALS'
                ? 'bg-blue-600 text-white shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
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
                <h3 className="text-xs font-black text-slate-900">Daftar Tugas Mandiri AI Agent</h3>
                <p className="text-[11px] text-slate-500">
                  Tugas yang dijalankan secara terjadwal atau otonom oleh AI tanpa intervensi manual
                </p>
              </div>
              <button
                onClick={() => setIsCreatingTask(true)}
                className="px-3 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs shadow-xs transition flex items-center gap-1"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Tambah Tugas</span>
              </button>
            </div>

            {/* Tasks List */}
            <div className="space-y-2.5">
              {tasks.map((task) => {
                const badge = getTypeBadge(task.type);
                const isRunning = runningTaskId === task.id;

                return (
                  <div
                    key={task.id}
                    className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200 hover:border-blue-300 transition space-y-2.5"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="space-y-1">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className={`text-[9px] px-2 py-0.5 rounded-full font-bold border ${badge.color}`}>
                            {badge.label}
                          </span>
                          <span className="text-[9px] px-2 py-0.5 rounded-full bg-slate-200 text-slate-700 font-bold">
                            {task.frequency}
                          </span>
                          {task.scheduledTime && (
                            <span className="text-[9px] text-slate-500 font-mono flex items-center gap-0.5">
                              <Clock className="w-2.5 h-2.5" />
                              {task.scheduledTime}
                            </span>
                          )}
                        </div>
                        <h4 className="text-xs font-black text-slate-900">{task.title}</h4>
                      </div>

                      {/* Autonomous Toggle Switch */}
                      <button
                        onClick={() => handleToggleAutonomous(task.id)}
                        className={`shrink-0 px-2.5 py-1 rounded-xl text-[10px] font-bold transition flex items-center gap-1 border ${
                          task.autonomousExecution
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-300 shadow-2xs'
                            : 'bg-slate-100 text-slate-600 border-slate-200'
                        }`}
                        title="Klik untuk mengubah mode otonom"
                      >
                        <span className={`w-2 h-2 rounded-full ${task.autonomousExecution ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400'}`} />
                        <span>{task.autonomousExecution ? 'Otonom Aktif' : 'Manual'}</span>
                      </button>
                    </div>

                    {/* Output log / last run */}
                    <div className="p-2 rounded-xl bg-white border border-slate-200/80 text-[10px] text-slate-600 space-y-1">
                      <div className="flex justify-between text-slate-400">
                        <span>Terakhir Dieksekusi: <strong>{task.lastRun || 'Belum pernah'}</strong></span>
                        <span>Jadwal Berikutnya: <strong>{task.nextRun || 'Sesuai jadwal'}</strong></span>
                      </div>
                      {task.outputSummary && (
                        <p className="text-slate-700 font-medium pt-0.5 border-t border-slate-100">
                          {task.outputSummary}
                        </p>
                      )}
                    </div>

                    {/* Action Bar */}
                    <div className="flex items-center justify-between pt-1 text-xs">
                      <span className={`text-[10px] font-bold ${
                        task.status === 'COMPLETED' ? 'text-emerald-600' : 'text-blue-600'
                      }`}>
                        Status: {task.status === 'COMPLETED' ? '✓ Siap / Selesai' : '⏳ Siaga / Menunggu Jadwal'}
                      </span>

                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={() => handleRunTaskNow(task)}
                          disabled={isRunning}
                          className="px-2.5 py-1 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-[10px] font-bold transition flex items-center gap-1 shadow-2xs disabled:opacity-50"
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
                          className="p-1 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition"
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
                className="px-3 py-1.5 rounded-xl bg-purple-600 hover:bg-purple-700 text-white font-bold text-xs shadow-xs transition flex items-center gap-1"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Tambah Goal</span>
              </button>
            </div>

            <div className="space-y-2.5">
              {goals.map((goal) => (
                <div
                  key={goal.id}
                  className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200 space-y-2.5"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-1.5 mb-0.5">
                        <span className={`text-[9px] px-2 py-0.5 rounded-full font-bold ${
                          goal.priority === 'HIGH'
                            ? 'bg-rose-50 text-rose-700 border border-rose-200'
                            : 'bg-blue-50 text-blue-700 border border-blue-200'
                        }`}>
                          Prioritas {goal.priority}
                        </span>
                        <span className="text-[10px] text-slate-500 font-mono">
                          Bidang: {goal.bidang}
                        </span>
                      </div>
                      <h4 className="text-xs font-black text-slate-900">{goal.title}</h4>
                    </div>

                    <span className="font-mono text-xs font-black text-blue-600">
                      {goal.progress}%
                    </span>
                  </div>

                  {/* Progress Bar */}
                  <div className="w-full h-2 rounded-full bg-slate-200 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-blue-600 to-purple-600 rounded-full transition-all duration-500"
                      style={{ width: `${goal.progress}%` }}
                    />
                  </div>

                  <div className="flex items-center justify-between text-[10px] text-slate-500">
                    <span>Target Selesai: <strong>{goal.targetDate}</strong></span>
                    <button
                      onClick={() => {
                        const nextProg = Math.min(100, goal.progress + 15);
                        const updated = goals.map(g => g.id === goal.id ? { ...g, progress: nextProg } : g);
                        setGoals(updated);
                        onUpdateAgent({ ...agent, goals: updated });
                        onToast(`Progres target ditingkatkan menjadi ${nextProg}%!`);
                      }}
                      className="text-blue-600 font-bold hover:underline"
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
          <div className="p-4 rounded-3xl bg-blue-50/80 border border-blue-200 space-y-3 animate-fade-in text-xs">
            <div className="flex items-center justify-between">
              <h4 className="font-black text-slate-900 flex items-center gap-1.5">
                <Sparkles className="w-4 h-4 text-blue-600" />
                <span>Buat Tugas Mandiri Otonom Baru</span>
              </h4>
              <button
                onClick={() => setIsCreatingTask(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateTask} className="space-y-2.5">
              <div>
                <label className="font-bold text-slate-700 block mb-1">Judul / Instruksi Tugas:</label>
                <input
                  type="text"
                  required
                  value={newTaskTitle}
                  onChange={(e) => setNewTaskTitle(e.target.value)}
                  placeholder="Misal: Jadwalkan postingan edukasi seputar tips kesehatan di era kerja hybrid"
                  className="w-full px-3 py-2 rounded-xl bg-white border border-slate-200 focus:border-blue-500 outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="font-bold text-slate-700 block mb-1">Jenis Tugas:</label>
                  <select
                    value={newTaskType}
                    onChange={(e) => setNewTaskType(e.target.value as AgentTaskItem['type'])}
                    className="w-full px-2.5 py-1.5 rounded-xl bg-white border border-slate-200 text-xs"
                  >
                    <option value="SCHEDULING_POST">📅 Scheduling Postingan</option>
                    <option value="BROADCAST_INFO">📢 Broadcast Informasi</option>
                    <option value="SKILL_EXECUTION">⚡ Eksekusi Skill Brand</option>
                    <option value="ANALYTICS_REPORT">📊 Laporan Analitik</option>
                  </select>
                </div>
                <div>
                  <label className="font-bold text-slate-700 block mb-1">Frekuensi:</label>
                  <select
                    value={newTaskFrequency}
                    onChange={(e) => setNewTaskFrequency(e.target.value as AgentTaskItem['frequency'])}
                    className="w-full px-2.5 py-1.5 rounded-xl bg-white border border-slate-200 text-xs"
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
                  <label className="font-bold text-slate-700 block mb-1">Waktu Eksekusi:</label>
                  <input
                    type="text"
                    value={newTaskScheduledTime}
                    onChange={(e) => setNewTaskScheduledTime(e.target.value)}
                    placeholder="Contoh: 19:00 WIB"
                    className="w-full px-2.5 py-1.5 rounded-xl bg-white border border-slate-200 text-xs"
                  />
                </div>
                <div className="flex items-center gap-2 pt-5">
                  <input
                    type="checkbox"
                    id="autonomousCheck"
                    checked={newTaskAutonomous}
                    onChange={(e) => setNewTaskAutonomous(e.target.checked)}
                    className="w-4 h-4 text-blue-600 rounded"
                  />
                  <label htmlFor="autonomousCheck" className="font-bold text-slate-800 text-[11px] cursor-pointer">
                    Eksekusi Otonom (AI Auto-Pilot)
                  </label>
                </div>
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  type="submit"
                  className="flex-1 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs shadow-xs transition"
                >
                  Tugaskan ke {agent.name}
                </button>
                <button
                  type="button"
                  onClick={() => setIsCreatingTask(false)}
                  className="px-3 py-2 rounded-xl bg-white border border-slate-200 text-slate-700 font-bold text-xs"
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
          <div className="p-4 rounded-3xl bg-purple-50/80 border border-purple-200 space-y-3 animate-fade-in text-xs">
            <div className="flex items-center justify-between">
              <h4 className="font-black text-slate-900 flex items-center gap-1.5">
                <Target className="w-4 h-4 text-purple-600" />
                <span>Buat Target Strategis (Goal) Baru</span>
              </h4>
              <button
                onClick={() => setIsCreatingGoal(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateGoal} className="space-y-2.5">
              <div>
                <label className="font-bold text-slate-700 block mb-1">Judul Target:</label>
                <input
                  type="text"
                  required
                  value={newGoalTitle}
                  onChange={(e) => setNewGoalTitle(e.target.value)}
                  placeholder="Misal: Mencapai 50K followers dan 500 AI Credits dari sesi konsultasi"
                  className="w-full px-3 py-2 rounded-xl bg-white border border-slate-200 focus:border-purple-500 outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="font-bold text-slate-700 block mb-1">Prioritas:</label>
                  <select
                    value={newGoalPriority}
                    onChange={(e) => setNewGoalPriority(e.target.value as 'HIGH' | 'MEDIUM' | 'LOW')}
                    className="w-full px-2.5 py-1.5 rounded-xl bg-white border border-slate-200 text-xs"
                  >
                    <option value="HIGH">Tinggi (High)</option>
                    <option value="MEDIUM">Sedang (Medium)</option>
                    <option value="LOW">Rendah (Low)</option>
                  </select>
                </div>
                <div>
                  <label className="font-bold text-slate-700 block mb-1">Target Selesai:</label>
                  <input
                    type="date"
                    value={newGoalTargetDate}
                    onChange={(e) => setNewGoalTargetDate(e.target.value)}
                    className="w-full px-2.5 py-1.5 rounded-xl bg-white border border-slate-200 text-xs"
                  />
                </div>
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  type="submit"
                  className="flex-1 py-2 rounded-xl bg-purple-600 hover:bg-purple-700 text-white font-bold text-xs shadow-xs transition"
                >
                  Simpan Target
                </button>
                <button
                  type="button"
                  onClick={() => setIsCreatingGoal(false)}
                  className="px-3 py-2 rounded-xl bg-white border border-slate-200 text-slate-700 font-bold text-xs"
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
            className="px-5 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs transition"
          >
            Tutup
          </button>
        </div>
      </div>
    </div>
  );
}

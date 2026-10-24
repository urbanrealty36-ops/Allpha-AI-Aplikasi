'use client';

import React, { useState } from 'react';
import { 
  Bot, 
  Sparkles, 
  X, 
  Check, 
  Box, 
  Shield, 
  ChevronRight, 
  Layers, 
  Eye,
  Sliders,
  CheckCircle2,
  Cpu,
  Palette,
  HeartPulse,
  Camera,
  GraduationCap,
  Briefcase,
  Brain,
  BarChart2,
  BookOpen,
  Scale,
  Music
} from 'lucide-react';
import { 
  AIAgentProfile, 
  AgentBidang, 
  AVATAR_3D_CATALOG, 
  BIDANG_SKILLS_CATALOG,
  Avatar3DItem 
} from '@/lib/reference-store';

interface AgentIdentityModalProps {
  isOpen: boolean;
  onClose: () => void;
  agent: AIAgentProfile;
  onSaveAgent: (updatedAgent: AIAgentProfile) => void;
}

export default function AgentIdentityModal({
  isOpen,
  onClose,
  agent,
  onSaveAgent,
}: AgentIdentityModalProps) {
  const [name, setName] = useState(agent.name);
  const [handle, setHandle] = useState(agent.handle);
  const [selectedBidang, setSelectedBidang] = useState<AgentBidang>(
    (agent.bidang as AgentBidang) || 'Desain Grafis'
  );
  const [selectedAvatarId, setSelectedAvatarId] = useState<string>(
    agent.avatar3DCodename || 'av-luna-valkyrie'
  );
  const [selectedSkills, setSelectedSkills] = useState<string[]>(
    agent.skills && agent.skills.length > 0
      ? agent.skills
      : BIDANG_SKILLS_CATALOG[selectedBidang]?.skills.slice(0, 4) || []
  );
  const [bio, setBio] = useState(agent.bio);
  const [model, setModel] = useState(agent.model || 'Allpha Neural Omni v3');
  const [autoReply, setAutoReply] = useState(agent.autoReply ?? true);

  // Modal to inspect full 3D Avatar turnarounds
  const [inspectingAvatar, setInspectingAvatar] = useState<Avatar3DItem | null>(null);

  if (!isOpen) return null;

  const currentAvatar = AVATAR_3D_CATALOG.find(a => a.id === selectedAvatarId || a.codename === selectedAvatarId) || AVATAR_3D_CATALOG[0];

  const handleSelectBidang = (bidang: AgentBidang) => {
    setSelectedBidang(bidang);
    // Suggest relevant skills from the catalog
    const suggested = BIDANG_SKILLS_CATALOG[bidang]?.skills.slice(0, 4) || [];
    setSelectedSkills(suggested);
  };

  const toggleSkill = (skill: string) => {
    if (selectedSkills.includes(skill)) {
      setSelectedSkills(selectedSkills.filter(s => s !== skill));
    } else {
      setSelectedSkills([...selectedSkills, skill]);
    }
  };

  const handleSave = () => {
    const chosenAvatar = AVATAR_3D_CATALOG.find(a => a.id === selectedAvatarId) || currentAvatar;

    const updated: AIAgentProfile = {
      ...agent,
      name,
      handle: handle.startsWith('@') ? handle : `@${handle}`,
      avatar: chosenAvatar.image,
      avatar3DCodename: chosenAvatar.id,
      avatar3DImage: chosenAvatar.image,
      bidang: selectedBidang,
      specialty: BIDANG_SKILLS_CATALOG[selectedBidang]?.label || 'Kreativitas & Desain 3D',
      skills: selectedSkills,
      bio,
      model,
      autoReply,
    };

    onSaveAgent(updated);
    onClose();
  };

  const bidangList: AgentBidang[] = [
    'Health',
    'IT',
    'Desain Grafis',
    'Photographer',
    'Mentor',
    'Pengusaha',
    'Psikolog',
    'Analis',
    'Dosen',
    'Hukum',
    'Musisi',
  ];

  const getBidangIcon = (b: AgentBidang) => {
    switch (b) {
      case 'Health': return HeartPulse;
      case 'IT': return Cpu;
      case 'Desain Grafis': return Palette;
      case 'Photographer': return Camera;
      case 'Mentor': return GraduationCap;
      case 'Pengusaha': return Briefcase;
      case 'Psikolog': return Brain;
      case 'Analis': return BarChart2;
      case 'Dosen': return BookOpen;
      case 'Hukum': return Scale;
      case 'Musisi': return Music;
      default: return Bot;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/60 backdrop-blur-xs animate-fade-in">
      <div className="w-full max-w-xl rounded-3xl bg-white shadow-2xl border border-slate-200 p-5 max-h-[92vh] overflow-y-auto space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-600 text-white flex items-center justify-center shadow-md">
              <Bot className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-black text-slate-900">
                AI Agent Identity & 3D Avatar Studio
              </h2>
              <p className="text-[11px] text-slate-500">
                Pilih Avatar 3D, Bidang Profesi, dan Katalog Skills resmi AI Agent Anda
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

        {/* 1. KATALOG AVATAR 3D RESMI (Screenshot Reference Sheet) */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-xs font-extrabold text-slate-900 flex items-center gap-1.5">
              <Box className="w-3.5 h-3.5 text-blue-600" />
              <span>Katalog Model Avatar 3D (Multi-Angle Rigged)</span>
            </label>
            <span className="text-[10px] text-blue-600 font-bold">
              {AVATAR_3D_CATALOG.length} Avatar 3D
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 max-h-56 overflow-y-auto p-1">
            {AVATAR_3D_CATALOG.map((av) => {
              const isSelected = selectedAvatarId === av.id || selectedAvatarId === av.codename;

              return (
                <div
                  key={av.id}
                  onClick={() => setSelectedAvatarId(av.id)}
                  className={`relative p-2 rounded-2xl border text-left cursor-pointer transition flex flex-col justify-between group ${
                    isSelected
                      ? 'border-blue-600 bg-blue-50/50 ring-2 ring-blue-500/30 shadow-xs'
                      : 'border-slate-200 bg-white hover:border-blue-300'
                  }`}
                >
                  <div className="relative h-28 rounded-xl overflow-hidden bg-slate-950 mb-1.5">
                    <img
                      src={av.image}
                      alt={av.name}
                      className="w-full h-full object-cover object-top group-hover:scale-105 transition duration-300"
                    />
                    <div className="absolute top-1 left-1">
                      <span className="text-[8px] font-bold px-1.5 py-0.2 rounded-full bg-slate-900/80 text-white backdrop-blur">
                        {av.rarity}
                      </span>
                    </div>

                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setInspectingAvatar(av);
                      }}
                      className="absolute bottom-1 right-1 p-1 rounded-md bg-black/60 text-white hover:bg-black/90 text-[9px] transition flex items-center gap-0.5"
                      title="Lihat Turnaround Lembar Model"
                    >
                      <Eye className="w-3 h-3" />
                      <span>3D Sheet</span>
                    </button>
                  </div>

                  <div>
                    <h4 className="text-xs font-black text-slate-900 truncate">{av.name}</h4>
                    <p className="text-[10px] text-slate-500 font-mono truncate">{av.codename}</p>
                  </div>

                  {isSelected && (
                    <div className="absolute top-1 right-1 w-4 h-4 rounded-full bg-blue-600 text-white flex items-center justify-center text-[9px]">
                      ✓
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* 2. PILIH BIDANG (Health, IT, Desain Grafis, Photographer, Mentor, etc.) */}
        <div className="space-y-2">
          <label className="text-xs font-extrabold text-slate-900 flex items-center gap-1.5">
            <Sliders className="w-3.5 h-3.5 text-purple-600" />
            <span>Pilih Bidang Utama AI Agent:</span>
          </label>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
            {bidangList.map((bidang) => {
              const Icon = getBidangIcon(bidang);
              const isSelected = selectedBidang === bidang;

              return (
                <button
                  key={bidang}
                  type="button"
                  onClick={() => handleSelectBidang(bidang)}
                  className={`p-2 rounded-xl text-xs font-bold transition flex items-center gap-2 border text-left ${
                    isSelected
                      ? 'bg-purple-600 text-white border-purple-600 shadow-xs'
                      : 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-purple-50 hover:border-purple-200'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5 shrink-0" />
                  <span className="truncate">{bidang}</span>
                </button>
              );
            })}
          </div>

          <p className="text-[11px] text-slate-500 italic">
            {BIDANG_SKILLS_CATALOG[selectedBidang]?.description}
          </p>
        </div>

        {/* 3. KATALOG SKILLS BERDASARKAN BIDANG */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-xs font-extrabold text-slate-900 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-amber-500" />
              <span>Katalog Skills Bidang {selectedBidang}:</span>
            </label>
            <span className="text-[10px] text-slate-500">
              {selectedSkills.length} Aktif
            </span>
          </div>

          <div className="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto p-1">
            {BIDANG_SKILLS_CATALOG[selectedBidang]?.skills.map((skill) => {
              const isSelected = selectedSkills.includes(skill);

              return (
                <button
                  key={skill}
                  type="button"
                  onClick={() => toggleSkill(skill)}
                  className={`px-2.5 py-1.5 rounded-xl text-xs font-semibold border transition flex items-center gap-1.5 ${
                    isSelected
                      ? 'bg-amber-500 text-white border-amber-500 shadow-2xs font-bold'
                      : 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100'
                  }`}
                >
                  {isSelected ? <Check className="w-3 h-3" /> : <span>+</span>}
                  <span>{skill}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* 4. DETAIL IDENTITAS NAMA, HANDLE, DAN BIO */}
        <div className="space-y-3 pt-2 border-t border-slate-100 text-xs">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="font-bold text-slate-700 block mb-1">Nama AI Agent</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-200 focus:bg-white focus:border-blue-500 outline-none"
              />
            </div>
            <div>
              <label className="font-bold text-slate-700 block mb-1">Handle (@handle)</label>
              <input
                type="text"
                value={handle}
                onChange={(e) => setHandle(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-200 focus:bg-white focus:border-blue-500 outline-none"
              />
            </div>
          </div>

          <div>
            <label className="font-bold text-slate-700 block mb-1">Bio & Kepribadian Agen</label>
            <input
              type="text"
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-200 focus:bg-white focus:border-blue-500 outline-none"
            />
          </div>

          {/* Model AI Engine */}
          <div className="flex items-center justify-between p-3 rounded-2xl bg-slate-50 border border-slate-200">
            <div>
              <p className="font-bold text-slate-900">Model Neural Engine</p>
              <p className="text-[10px] text-slate-500">Didukung oleh Gemini 2.5 Flash Allpha Gateway</p>
            </div>
            <span className="font-mono text-xs font-extrabold text-blue-600 bg-blue-50 px-2 py-1 rounded-lg border border-blue-200">
              {model}
            </span>
          </div>
        </div>

        {/* Footer Action Buttons */}
        <div className="pt-2 flex gap-2">
          <button
            onClick={handleSave}
            className="flex-1 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs shadow-md transition flex items-center justify-center gap-1.5"
          >
            <CheckCircle2 className="w-4 h-4" />
            <span>Simpan Identitas & Avatar 3D</span>
          </button>
          <button
            onClick={onClose}
            className="px-4 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs transition"
          >
            Batal
          </button>
        </div>
      </div>

      {/* MODAL INSPEKSI LEMBAR TURNAROUND 3D */}
      {inspectingAvatar && (
        <div className="fixed inset-0 z-60 flex items-center justify-center p-3 sm:p-5 bg-black/80 backdrop-blur-md">
          <div className="w-full max-w-2xl bg-slate-900 rounded-3xl p-4 sm:p-6 text-white border border-slate-800 space-y-4 max-h-[95vh] overflow-y-auto">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[10px] font-mono text-cyan-400 font-bold">
                  {inspectingAvatar.codename} • {inspectingAvatar.rarity}
                </span>
                <h3 className="text-base font-black text-white mt-0.5">
                  {inspectingAvatar.name} — Lembar Turnaround 3D
                </h3>
              </div>
              <button
                onClick={() => setInspectingAvatar(null)}
                className="p-1 text-slate-400 hover:text-white transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="rounded-2xl overflow-hidden border border-slate-800 bg-black">
              <img
                src={inspectingAvatar.turnaroundImage || inspectingAvatar.image}
                alt={inspectingAvatar.name}
                className="w-full object-contain max-h-[60vh] mx-auto"
              />
            </div>

            <div className="space-y-1.5 text-xs">
              <p className="text-slate-300">{inspectingAvatar.style}</p>
              <div className="flex flex-wrap gap-1.5 pt-1">
                {inspectingAvatar.features.map((f) => (
                  <span
                    key={f}
                    className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-cyan-300 border border-slate-700"
                  >
                    ✓ {f}
                  </span>
                ))}
              </div>
            </div>

            <div className="flex justify-between items-center pt-2 border-t border-slate-800">
              <span className="text-xs text-slate-400">
                Distrik Asal: <strong className="text-white">{inspectingAvatar.district}</strong>
              </span>
              <button
                onClick={() => {
                  setSelectedAvatarId(inspectingAvatar.id);
                  setInspectingAvatar(null);
                }}
                className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold shadow-md transition"
              >
                Pilih Avatar Ini
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

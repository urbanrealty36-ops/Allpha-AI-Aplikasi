'use client';

import React, { useState } from 'react';
import { 
  Sparkles, 
  User, 
  Bot, 
  ArrowRight, 
  CheckCircle2, 
  ShieldCheck, 
  Compass, 
  Coins, 
  Radio, 
  Box, 
  Zap, 
  Globe, 
  Layers,
  Heart,
  X,
  Lock,
  Mail,
  Check
} from 'lucide-react';
import { 
  HumanProfile, 
  AIAgentProfile, 
  AgentBidang, 
  AVATAR_3D_CATALOG, 
  BIDANG_SKILLS_CATALOG 
} from '@/lib/store';

interface AuthOnboardingFlowProps {
  isOpen: boolean;
  onClose: () => void;
  onComplete: (user: HumanProfile, agent: AIAgentProfile, bonusCredits: number) => void;
  currentUser: HumanProfile;
  currentAgent: AIAgentProfile;
}

export type OnboardingStep = 'SPLASH' | 'HUMAN_REGISTER' | 'AGENT_ONBOARDING' | 'SUCCESS';

export default function AuthOnboardingFlow({
  isOpen,
  onClose,
  onComplete,
  currentUser,
  currentAgent,
}: AuthOnboardingFlowProps) {
  const [step, setStep] = useState<OnboardingStep>('SPLASH');
  const [authMode, setAuthMode] = useState<'REGISTER' | 'LOGIN'>('REGISTER');

  // Human Identity Form State
  const [humanName, setHumanName] = useState(currentUser.name);
  const [humanHandle, setHumanHandle] = useState(currentUser.username);
  const [humanEmail, setHumanEmail] = useState('alex.tamara@example.com');
  const [humanPassword, setHumanPassword] = useState('••••••••••••');
  const [humanBio, setHumanBio] = useState(currentUser.bio);
  const [selectedAvatar, setSelectedAvatar] = useState(currentUser.avatar);
  const [selectedInterests, setSelectedInterests] = useState<string[]>([
    'Kesehatan',
    'IT & Teknologi',
    '3D Spatial',
    'Kreator Konten'
  ]);

  // AI Agent Identity Form State
  const [agentName, setAgentName] = useState(currentAgent.name);
  const [agentHandle, setAgentHandle] = useState(currentAgent.handle);
  const [selectedBidang, setSelectedBidang] = useState<AgentBidang>(
    (currentAgent.bidang as AgentBidang) || 'Desain Grafis'
  );
  const [selectedSkills, setSelectedSkills] = useState<string[]>(
    currentAgent.skills || ['Brand Identity & Custom Logo 3D Vector', 'Desain Feed & Storyboard Reels Dinamis']
  );
  const [agentSpecialty, setAgentSpecialty] = useState(currentAgent.specialty);
  const [agentCategory, setAgentCategory] = useState<'Kesehatan' | 'IT & Teknologi' | 'Marketing' | 'Kreativitas' | 'Gaming & 3D'>('Kreativitas');
  const [agentPersona, setAgentPersona] = useState('Ramah & Kreatif');
  const [selectedAgentAvatar, setSelectedAgentAvatar] = useState(
    currentAgent.avatar3DImage || currentAgent.avatar || AVATAR_3D_CATALOG[0].image
  );
  const [selectedAvatarCodename, setSelectedAvatarCodename] = useState(
    currentAgent.avatar3DCodename || AVATAR_3D_CATALOG[0].id
  );
  const [isAutoReplyEnabled, setIsAutoReplyEnabled] = useState(true);

  if (!isOpen) return null;

  const humanAvatars = [
    { label: 'Alex (Tech & Spatial)', url: 'https://picsum.photos/seed/alex-tamara/200/200' },
    { label: 'Raka (Builder & Product)', url: 'https://picsum.photos/seed/raka/200/200' },
    { label: 'Sari (Fashion & 3D)', url: 'https://picsum.photos/seed/sari/200/200' },
    { label: 'Mika (Digital Artist)', url: 'https://picsum.photos/seed/mika/200/200' },
    { label: 'Dr. Andi (Medical Health)', url: 'https://picsum.photos/seed/drandi/200/200' },
  ];

  const availableInterests = [
    'Kesehatan',
    'IT & Teknologi',
    '3D Spatial',
    'Kreator Konten',
    'Bisnis & Finansial',
    'Desain & UI/UX',
    'Edukasi & Riset',
    'Gaming & Metaverse',
  ];

  const toggleInterest = (interest: string) => {
    setSelectedInterests(prev => 
      prev.includes(interest) ? prev.filter(i => i !== interest) : [...prev, interest]
    );
  };

  const handleFinishOnboarding = () => {
    const updatedHuman: HumanProfile = {
      ...currentUser,
      name: humanName,
      username: humanHandle.startsWith('@') ? humanHandle : `@${humanHandle}`,
      avatar: selectedAvatar,
      bio: humanBio,
    };

    const updatedAgent: AIAgentProfile = {
      ...currentAgent,
      name: agentName,
      handle: agentHandle.startsWith('@') ? agentHandle : `@${agentHandle}`,
      avatar: selectedAgentAvatar,
      avatar3DImage: selectedAgentAvatar,
      avatar3DCodename: selectedAvatarCodename,
      ownerName: updatedHuman.name,
      ownerHandle: updatedHuman.username,
      specialty: BIDANG_SKILLS_CATALOG[selectedBidang]?.label || agentSpecialty,
      category: agentCategory,
      bidang: selectedBidang,
      skills: selectedSkills,
      autoReply: isAutoReplyEnabled,
    };

    onComplete(updatedHuman, updatedAgent, 50);
    setStep('SUCCESS');
    setTimeout(() => {
      onClose();
    }, 1800);
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/80 backdrop-blur-md flex items-center justify-center p-3 sm:p-5">
      <div className="relative w-full max-w-xl bg-white rounded-3xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[92vh]">
        {/* Top Dismiss Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 z-20 w-8 h-8 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-600 flex items-center justify-center transition"
          aria-label="Tutup"
        >
          <X className="w-4 h-4" />
        </button>

        {/* ======================================================== */}
        {/* STEP 1: SPLASH ONBOARDING HERO                          */}
        {/* ======================================================== */}
        {step === 'SPLASH' && (
          <div className="p-6 sm:p-8 flex flex-col items-center text-center space-y-6 overflow-y-auto">
            {/* Logo Lockup */}
            <div className="flex flex-col items-center gap-2">
              <div className="w-16 h-16 rounded-3xl bg-gradient-to-tr from-blue-600 via-sky-500 to-indigo-600 flex items-center justify-center shadow-xl shadow-blue-500/25">
                <span className="text-white font-black text-3xl tracking-tighter">A</span>
              </div>
              <div className="flex items-center gap-2 mt-1">
                <h1 className="text-2xl font-black tracking-tight text-slate-900">ALLPHA UNIVERSE</h1>
                <span className="text-[10px] font-extrabold px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 tracking-wider uppercase border border-blue-200">
                  2026
                </span>
              </div>
              <p className="text-xs font-semibold text-blue-600 tracking-wider uppercase">
                PEOPLE × AI AGENTS × WORLDS × OPPORTUNITIES
              </p>
            </div>

            {/* Headline & Subhead from Pitch Deck */}
            <div className="space-y-2 max-w-md">
              <h2 className="text-lg font-bold text-slate-900">
                Satu Ekosistem untuk Manusia dan AI Agent
              </h2>
              <p className="text-xs text-slate-600 leading-relaxed">
                Terhubung, Berkreasi, Berkolaborasi, dan Membuka Peluang Baru di Dunia Digital, Social Threads, dan 3D Spatial Living World.
              </p>
            </div>

            {/* Feature Highlights Grid */}
            <div className="grid grid-cols-2 gap-2.5 w-full text-left">
              <div className="p-3 rounded-2xl bg-slate-50 border border-slate-200/80 flex items-start gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-blue-100 text-blue-600 flex items-center justify-center shrink-0">
                  <User className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-xs font-bold text-slate-900">Dual Identity Feed</h3>
                  <p className="text-[10px] text-slate-500 mt-0.5">Postingan bersama Human Owner & AI Agent.</p>
                </div>
              </div>

              <div className="p-3 rounded-2xl bg-slate-50 border border-slate-200/80 flex items-start gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-purple-100 text-purple-600 flex items-center justify-center shrink-0">
                  <Box className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-xs font-bold text-slate-900">3D Spatial Universe</h3>
                  <p className="text-[10px] text-slate-500 mt-0.5">Eksplorasi Crystal City, Booths, & Avatar 3D.</p>
                </div>
              </div>

              <div className="p-3 rounded-2xl bg-slate-50 border border-slate-200/80 flex items-start gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-rose-100 text-rose-600 flex items-center justify-center shrink-0">
                  <Radio className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-xs font-bold text-slate-900">Live Stage Podcast</h3>
                  <p className="text-[10px] text-slate-500 mt-0.5">Streaming interaktif Human & AI kembar suara.</p>
                </div>
              </div>

              <div className="p-3 rounded-2xl bg-slate-50 border border-slate-200/80 flex items-start gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-amber-100 text-amber-600 flex items-center justify-center shrink-0">
                  <Coins className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-xs font-bold text-slate-900">AI Credits Economy</h3>
                  <p className="text-[10px] text-slate-500 mt-0.5">Raih reward saat AI Anda membantu user lain.</p>
                </div>
              </div>
            </div>

            {/* CTAs */}
            <div className="w-full space-y-2 pt-2">
              <button
                onClick={() => {
                  setAuthMode('REGISTER');
                  setStep('HUMAN_REGISTER');
                }}
                className="w-full py-3 px-4 rounded-2xl bg-blue-600 hover:bg-blue-700 active:scale-[0.99] text-white font-bold text-xs shadow-lg shadow-blue-500/25 flex items-center justify-center gap-2 transition"
              >
                <span>Mulai Sekarang / Daftar Human Identity</span>
                <ArrowRight className="w-4 h-4" />
              </button>

              <button
                onClick={() => {
                  setAuthMode('LOGIN');
                  setStep('HUMAN_REGISTER');
                }}
                className="w-full py-2.5 px-4 rounded-2xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs transition"
              >
                Sudah Punya Akun? Masuk di Sini
              </button>

              <button
                onClick={onClose}
                className="text-[11px] text-slate-500 hover:text-slate-800 underline transition pt-1"
              >
                Jelajahi Dulu sebagai Tamu (Guest Mode)
              </button>
            </div>
          </div>
        )}

        {/* ======================================================== */}
        {/* STEP 2: HUMAN IDENTITY LOGIN & REGISTER                 */}
        {/* ======================================================== */}
        {step === 'HUMAN_REGISTER' && (
          <div className="p-6 sm:p-7 flex flex-col space-y-5 overflow-y-auto">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <span className="text-[10px] font-bold text-blue-600 tracking-wider uppercase">Langkah 1 dari 2</span>
                <h2 className="text-base font-black text-slate-900">
                  {authMode === 'REGISTER' ? 'Registrasi Human Identity' : 'Masuk ke Human Identity'}
                </h2>
              </div>
              <div className="flex rounded-xl bg-slate-100 p-0.5 text-xs font-bold">
                <button
                  onClick={() => setAuthMode('REGISTER')}
                  className={`px-3 py-1 rounded-lg transition ${authMode === 'REGISTER' ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-500'}`}
                >
                  Daftar
                </button>
                <button
                  onClick={() => setAuthMode('LOGIN')}
                  className={`px-3 py-1 rounded-lg transition ${authMode === 'LOGIN' ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-500'}`}
                >
                  Masuk
                </button>
              </div>
            </div>

            {/* Avatar Selector */}
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                <User className="w-3.5 h-3.5 text-blue-600" />
                <span>Pilih Foto Avatar Human Anda</span>
              </label>
              <div className="flex items-center gap-3 overflow-x-auto py-1">
                {humanAvatars.map((av) => (
                  <button
                    key={av.url}
                    type="button"
                    onClick={() => setSelectedAvatar(av.url)}
                    className={`relative rounded-full p-0.5 transition shrink-0 ${
                      selectedAvatar === av.url ? 'ring-3 ring-blue-600 scale-105' : 'opacity-70 hover:opacity-100'
                    }`}
                  >
                    <img src={av.url} alt={av.label} className="w-12 h-12 rounded-full object-cover" />
                    {selectedAvatar === av.url && (
                      <span className="absolute bottom-0 right-0 w-4 h-4 rounded-full bg-blue-600 text-white flex items-center justify-center text-[9px]">
                        ✓
                      </span>
                    )}
                  </button>
                ))}
              </div>
            </div>

            {/* Form Fields */}
            <div className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] font-bold text-slate-700">Nama Lengkap</label>
                  <input
                    type="text"
                    value={humanName}
                    onChange={(e) => setHumanName(e.target.value)}
                    placeholder="Contoh: Alex Tamara"
                    className="w-full mt-1 px-3 py-2 rounded-xl border border-slate-200 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-bold text-slate-700">Username (@handle)</label>
                  <input
                    type="text"
                    value={humanHandle}
                    onChange={(e) => setHumanHandle(e.target.value)}
                    placeholder="@alextamara"
                    className="w-full mt-1 px-3 py-2 rounded-xl border border-slate-200 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div>
                <label className="text-[11px] font-bold text-slate-700">Email</label>
                <div className="relative mt-1">
                  <Mail className="absolute left-3 top-2.5 w-3.5 h-3.5 text-slate-400" />
                  <input
                    type="email"
                    value={humanEmail}
                    onChange={(e) => setHumanEmail(e.target.value)}
                    placeholder="nama@domain.com"
                    className="w-full pl-9 pr-3 py-2 rounded-xl border border-slate-200 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div>
                <label className="text-[11px] font-bold text-slate-700">Password</label>
                <div className="relative mt-1">
                  <Lock className="absolute left-3 top-2.5 w-3.5 h-3.5 text-slate-400" />
                  <input
                    type="password"
                    value={humanPassword}
                    onChange={(e) => setHumanPassword(e.target.value)}
                    placeholder="Min. 8 karakter"
                    className="w-full pl-9 pr-3 py-2 rounded-xl border border-slate-200 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div>
                <label className="text-[11px] font-bold text-slate-700">Bio Singkat</label>
                <input
                  type="text"
                  value={humanBio}
                  onChange={(e) => setHumanBio(e.target.value)}
                  placeholder="Ceritakan tentang passion atau fokus Anda..."
                  className="w-full mt-1 px-3 py-2 rounded-xl border border-slate-200 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {/* Interest Tags */}
              <div>
                <label className="text-[11px] font-bold text-slate-700">Pilih Minat & Topik Utama</label>
                <div className="flex flex-wrap gap-1.5 mt-1.5">
                  {availableInterests.map((interest) => {
                    const isSelected = selectedInterests.includes(interest);
                    return (
                      <button
                        key={interest}
                        type="button"
                        onClick={() => toggleInterest(interest)}
                        className={`px-2.5 py-1 rounded-lg text-[11px] font-medium transition ${
                          isSelected
                            ? 'bg-blue-600 text-white font-bold'
                            : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                        }`}
                      >
                        {isSelected ? `✓ ${interest}` : `+ ${interest}`}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Navigation Buttons */}
            <div className="flex items-center justify-between pt-3 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setStep('SPLASH')}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 transition"
              >
                ← Kembali
              </button>
              <button
                type="button"
                onClick={() => setStep('AGENT_ONBOARDING')}
                className="px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold shadow-md shadow-blue-500/20 flex items-center gap-1.5 transition"
              >
                <span>Lanjut: Setup AI Agent</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}

        {/* ======================================================== */}
        {/* STEP 3: ONBOARDING AI AGENT IDENTITY                    */}
        {/* ======================================================== */}
        {step === 'AGENT_ONBOARDING' && (
          <div className="p-6 sm:p-7 flex flex-col space-y-5 overflow-y-auto">
            {/* Header */}
            <div className="border-b border-slate-100 pb-3">
              <span className="text-[10px] font-bold text-purple-600 tracking-wider uppercase">Langkah 2 dari 2</span>
              <h2 className="text-base font-black text-slate-900 flex items-center gap-2">
                <span>Konfigurasi AI Agent Identity Pertama Anda</span>
                <Bot className="w-4 h-4 text-purple-600" />
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                AI Agent ini akan mewakili Anda di Threads Feed, berinteraksi di 3D Universe, dan menghasilkan AI Credits.
              </p>
            </div>

            {/* AI 3D Avatar Catalog Selector */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-extrabold text-slate-800 flex items-center gap-1.5">
                  <Box className="w-3.5 h-3.5 text-purple-600" />
                  <span>Katalog Avatar 3D Resmi (Model Sheet Rigged)</span>
                </label>
                <span className="text-[10px] text-purple-600 font-bold">
                  {AVATAR_3D_CATALOG.length} Avatar 3D
                </span>
              </div>
              
              <div className="flex items-center gap-2.5 overflow-x-auto py-1.5 no-scrollbar">
                {AVATAR_3D_CATALOG.map((av) => {
                  const isSelected = selectedAgentAvatar === av.image;

                  return (
                    <button
                      key={av.id}
                      type="button"
                      onClick={() => {
                        setSelectedAgentAvatar(av.image);
                        setSelectedAvatarCodename(av.id);
                      }}
                      className={`relative rounded-2xl p-1 transition shrink-0 text-left border flex flex-col items-center w-24 ${
                        isSelected 
                          ? 'border-purple-600 bg-purple-50 ring-2 ring-purple-500/30 shadow-xs' 
                          : 'border-slate-200 bg-white hover:border-purple-300'
                      }`}
                    >
                      <div className="w-20 h-20 rounded-xl overflow-hidden bg-slate-950 mb-1">
                        <img 
                          src={av.image} 
                          alt={av.name} 
                          className="w-full h-full object-cover object-top hover:scale-105 transition" 
                        />
                      </div>
                      <p className="text-[10px] font-bold text-slate-900 truncate w-full text-center">
                        {av.name}
                      </p>
                      <span className="text-[8px] px-1 py-0.2 rounded bg-slate-100 text-slate-600 font-mono">
                        {av.rarity}
                      </span>
                      {isSelected && (
                        <span className="absolute top-1.5 right-1.5 w-4 h-4 rounded-full bg-purple-600 text-white flex items-center justify-center text-[9px] shadow-xs">
                          ✓
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* AI Agent Fields */}
            <div className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] font-bold text-slate-700">Nama AI Agent</label>
                  <input
                    type="text"
                    value={agentName}
                    onChange={(e) => setAgentName(e.target.value)}
                    placeholder="Contoh: Luna AI"
                    className="w-full mt-1 px-3 py-2 rounded-xl border border-slate-200 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-purple-500"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-bold text-slate-700">Handle AI Agent</label>
                  <input
                    type="text"
                    value={agentHandle}
                    onChange={(e) => setAgentHandle(e.target.value)}
                    placeholder="@luna.ai"
                    className="w-full mt-1 px-3 py-2 rounded-xl border border-slate-200 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-purple-500"
                  />
                </div>
              </div>

              {/* 11 BIDANG SELECTION (Health, IT, Desain Grafis, Photographer, Mentor, etc.) */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-[11px] font-bold text-slate-700">
                    Pilih Bidang Profesi AI Agent:
                  </label>
                  <span className="text-[10px] text-purple-600 font-bold">
                    {selectedBidang}
                  </span>
                </div>
                <div className="grid grid-cols-3 sm:grid-cols-4 gap-1.5">
                  {([
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
                    'Musisi'
                  ] as AgentBidang[]).map((b) => {
                    const isSelected = selectedBidang === b;
                    return (
                      <button
                        key={b}
                        type="button"
                        onClick={() => {
                          setSelectedBidang(b);
                          setSelectedSkills(BIDANG_SKILLS_CATALOG[b]?.skills.slice(0, 3) || []);
                          setAgentSpecialty(BIDANG_SKILLS_CATALOG[b]?.label || b);
                        }}
                        className={`py-1.5 px-2 rounded-xl text-[11px] font-bold border transition text-center truncate ${
                          isSelected
                            ? 'bg-purple-600 text-white border-purple-600 shadow-2xs'
                            : 'border-slate-200 text-slate-600 hover:bg-purple-50'
                        }`}
                      >
                        {b}
                      </button>
                    );
                  })}
                </div>
                <p className="text-[10px] text-slate-500 mt-1 italic">
                  {BIDANG_SKILLS_CATALOG[selectedBidang]?.description}
                </p>
              </div>

              {/* SKILLS CATALOG PER BIDANG */}
              <div>
                <label className="text-[11px] font-bold text-slate-700 block mb-1">
                  Katalog Skills Terpilih ({selectedSkills.length}):
                </label>
                <div className="flex flex-wrap gap-1.5 max-h-28 overflow-y-auto p-1 bg-slate-50 rounded-xl border border-slate-200">
                  {BIDANG_SKILLS_CATALOG[selectedBidang]?.skills.map((skill) => {
                    const isSelected = selectedSkills.includes(skill);
                    return (
                      <button
                        key={skill}
                        type="button"
                        onClick={() => {
                          if (isSelected) {
                            setSelectedSkills(selectedSkills.filter(s => s !== skill));
                          } else {
                            setSelectedSkills([...selectedSkills, skill]);
                          }
                        }}
                        className={`px-2 py-1 rounded-lg text-[10px] font-medium transition ${
                          isSelected
                            ? 'bg-purple-600 text-white font-bold'
                            : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
                        }`}
                      >
                        {isSelected ? `✓ ${skill}` : `+ ${skill}`}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Persona Switcher */}
              <div>
                <label className="text-[11px] font-bold text-slate-700">Gaya Komunikasi & Persona</label>
                <div className="flex gap-2 mt-1.5">
                  {['Ramah & Kreatif', 'Formal & Analitis', 'Ceria & Inspiratif'].map((p) => (
                    <button
                      key={p}
                      type="button"
                      onClick={() => setAgentPersona(p)}
                      className={`flex-1 py-1.5 px-2 rounded-xl text-xs font-medium border transition ${
                        agentPersona === p
                          ? 'bg-purple-600 text-white border-purple-600 font-bold shadow-sm'
                          : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                      }`}
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </div>

              {/* Auto Reply & Takeover Switch */}
              <div className="p-3.5 rounded-2xl bg-purple-50 border border-purple-200/80 flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-bold text-purple-900">Mode Auto-Reply Aktif</h4>
                  <p className="text-[11px] text-purple-700 mt-0.5">
                    AI otomatis menjawab pertanyaan di Feed. Anda dapat Takeover kapan saja.
                  </p>
                </div>
                <input
                  type="checkbox"
                  checked={isAutoReplyEnabled}
                  onChange={(e) => setIsAutoReplyEnabled(e.target.checked)}
                  className="w-5 h-5 text-purple-600 rounded-md focus:ring-purple-500"
                />
              </div>

              {/* Bonus Gift Card */}
              <div className="p-3 rounded-2xl bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-amber-500/20 text-amber-600 flex items-center justify-center font-bold text-sm">
                  🎁
                </div>
                <div className="text-xs">
                  <p className="font-bold text-amber-900">Bonus Selamat Datang: +50 AI Credits</p>
                  <p className="text-[10px] text-amber-700">Langsung aktif untuk modal interaksi pertama Anda!</p>
                </div>
              </div>
            </div>

            {/* Navigation Buttons */}
            <div className="flex items-center justify-between pt-3 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setStep('HUMAN_REGISTER')}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 transition"
              >
                ← Kembali
              </button>
              <button
                type="button"
                onClick={handleFinishOnboarding}
                className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white text-xs font-bold shadow-lg shadow-purple-500/20 flex items-center gap-1.5 transition"
              >
                <span>Selesai & Masuk ke Universe 🚀</span>
              </button>
            </div>
          </div>
        )}

        {/* ======================================================== */}
        {/* STEP 4: SUCCESS CONGRATULATIONS                          */}
        {/* ======================================================== */}
        {step === 'SUCCESS' && (
          <div className="p-10 flex flex-col items-center justify-center text-center space-y-4">
            <div className="w-16 h-16 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center animate-bounce">
              <Check className="w-8 h-8 stroke-[3]" />
            </div>
            <h2 className="text-lg font-black text-slate-900">Selamat Datang di ALLPHA UNIVERSE!</h2>
            <p className="text-xs text-slate-600 max-w-sm">
              Identitas Human <strong className="text-slate-900">{humanName}</strong> dan AI Agent <strong className="text-purple-600">{agentName}</strong> siap menjelajahi Universe.
            </p>
            <span className="px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs font-bold border border-emerald-200">
              +50 AI Credits Dikreditkan
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

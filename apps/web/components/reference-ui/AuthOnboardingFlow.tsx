'use client';

import React, { useEffect, useState } from 'react';
import { usePWAInstall } from '@/hooks/usePWAInstall';
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
  type HumanProfile, 
  type AIAgentProfile, 
  type AgentBidang, 
  AVATAR_3D_CATALOG, 
  BIDANG_SKILLS_CATALOG 
} from '@/lib/reference-store';

type SkillCatalogEntry = {
  key: string;
  name: string;
  slug: string;
  category: string;
  catalog_version?: string;
  source?: { kind?: string };
  character_profile?: Record<string, unknown>;
};
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === 'production' ? 'https://api.allpha.web.id' : 'http://localhost:8000')).replace(/\/$/, '');

interface AuthOnboardingFlowProps {
  isOpen: boolean;
  onClose: () => void;
  onComplete: (payload: {
    user: HumanProfile;
    agent: AIAgentProfile;
    email: string;
    password: string;
    authMode: 'REGISTER' | 'LOGIN';
    interests: string[];
    persona: string;
  }) => Promise<void>;
  currentUser: HumanProfile;
  currentAgent: AIAgentProfile;
  onGoogleSignIn?: () => Promise<void>;
  initialAuthMode?: 'REGISTER' | 'LOGIN';
}

export type OnboardingStep = 'SPLASH' | 'HUMAN_REGISTER' | 'AGENT_ONBOARDING' | 'SUCCESS';

export default function AuthOnboardingFlow({
  isOpen,
  onClose,
  onComplete,
  currentUser,
  currentAgent,
  onGoogleSignIn,
  initialAuthMode,
}: AuthOnboardingFlowProps) {
  const [step, setStep] = useState<OnboardingStep>('SPLASH');
  const [authMode, setAuthMode] = useState<'REGISTER' | 'LOGIN'>(initialAuthMode ?? 'REGISTER');

  useEffect(() => {
    if (!isOpen || !initialAuthMode) return;
    setAuthMode(initialAuthMode);
    setStep('HUMAN_REGISTER');
  }, [initialAuthMode, isOpen]);
  const [selectedLang, setSelectedLang] = useState<'id' | 'en' | 'ja' | 'ms'>('id');
  const [isGoogleLoading, setIsGoogleLoading] = useState(false);
  const [flowToast, setFlowToast] = useState<string | null>(null);
  const pwaInstall = usePWAInstall();

  const showFlowToast = (message: string) => {
    setFlowToast(message);
    window.setTimeout(() => setFlowToast(null), 3000);
  };

  const handleGoogleSignIn = async () => {
    if (!onGoogleSignIn) {
      showFlowToast('Google Sign-In belum dikonfigurasi.');
      return;
    }
    setIsGoogleLoading(true);
    try {
      await onGoogleSignIn();
    } catch (cause) {
      setIsGoogleLoading(false);
      showFlowToast(cause instanceof Error ? cause.message : 'Google Sign-In gagal.');
    }
  };

  const handleAndroidInstall = async () => {
    if (pwaInstall.isInstalled) {
      showFlowToast('Allpha sudah terpasang di perangkat ini.');
      return;
    }
    if (!pwaInstall.isInstallable) {
      showFlowToast('Browser belum menawarkan dialog instalasi. Buka menu browser dan pilih Install app jika tersedia.');
      return;
    }
    try {
      const accepted = await pwaInstall.install();
      showFlowToast(accepted ? 'Permintaan instalasi diterima oleh browser.' : 'Instalasi tidak diselesaikan.');
    } catch {
      showFlowToast('Browser tidak dapat memulai instalasi. Coba melalui menu browser.');
    }
  };

  const handleIOSInstall = () => {
    if (pwaInstall.isInstalled) {
      showFlowToast('Allpha sudah terpasang di perangkat ini.');
      return;
    }
    if (pwaInstall.isIOS) {
      showFlowToast('Di Safari, tekan Bagikan lalu pilih Tambahkan ke Layar Utama.');
      return;
    }
    void handleAndroidInstall();
  };

  // Human Identity Form State
  const [humanName, setHumanName] = useState(currentUser.name);
  const [humanHandle, setHumanHandle] = useState(currentUser.username);
  const [humanEmail, setHumanEmail] = useState('');
  const [humanPassword, setHumanPassword] = useState('');
  const [humanBio, setHumanBio] = useState(currentUser.bio);
  const [selectedAvatar, setSelectedAvatar] = useState(currentUser.avatar);
  const [selectedInterests, setSelectedInterests] = useState<string[]>([]);

  // AI Agent Identity Form State
  const [agentName, setAgentName] = useState(currentAgent.name);
  const [agentHandle, setAgentHandle] = useState(currentAgent.handle);
  const [selectedBidang, setSelectedBidang] = useState<AgentBidang>(
    (currentAgent.bidang as AgentBidang) || 'Desain Grafis'
  );
  const [selectedSkills, setSelectedSkills] = useState<string[]>(
    currentAgent.skills || []
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
  const [isAutoReplyEnabled, setIsAutoReplyEnabled] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submissionError, setSubmissionError] = useState('');
  const [skillsLoading, setSkillsLoading] = useState(true);
  const [skillsError, setSkillsError] = useState('');
  const [availableSkills, setAvailableSkills] = useState<SkillCatalogEntry[]>([]);

  useEffect(() => {
    let active = true;
    const loadSkills = async () => {
      setSkillsLoading(true);
      setSkillsError('');
      try {
        const pages = await Promise.all([0, 100, 200, 300, 400].map(async (offset) => {
          const response = await fetch(apiBase + '/v1/skill-catalog?limit=100&offset=' + offset, { cache: 'no-store' });
          if (!response.ok) throw new Error(`Katalog Skill tidak tersedia (HTTP ${response.status}).`);
          return await response.json() as { items?: SkillCatalogEntry[] };
        }));
        const unique = new Map<string, SkillCatalogEntry>();
        for (const item of pages.flatMap(page => page.items ?? [])) {
          const key = item.key?.trim();
          if (key && item.name?.trim()) unique.set(key, item);
        }
        if (active) {
          setAvailableSkills(Array.from(unique.values()));
          if (!unique.size) setSkillsError('Katalog Skill kanonis belum memiliki item yang dapat dipilih.');
        }
      } catch (cause) {
        if (active) setSkillsError(cause instanceof Error ? cause.message : 'Katalog Skill gagal dimuat.');
      } finally {
        if (active) setSkillsLoading(false);
      }
    };
    void loadSkills();
    return () => { active = false; };
  }, []);

  if (!isOpen) return null;

  const humanAvatars = [
    { label: 'Alex (Tech & Spatial)', url: '/icon.svg' },
    { label: 'Raka (Builder & Product)', url: '/icon.svg' },
    { label: 'Sari (Fashion & 3D)', url: '/icon.svg' },
    { label: 'Mika (Digital Artist)', url: '/icon.svg' },
    { label: 'Dr. Andi (Medical Health)', url: '/icon.svg' },
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

  const handleFinishOnboarding = async () => {
    if (isSubmitting) return;
    setSubmissionError('');
    if (!humanEmail.trim() || !humanPassword) {
      setSubmissionError('Masukkan email dan password untuk melanjutkan.');
      setStep('HUMAN_REGISTER');
      return;
    }
    if (authMode === 'REGISTER' && humanPassword.length < 8) {
      setSubmissionError('Password pendaftaran minimal 8 karakter.');
      setStep('HUMAN_REGISTER');
      return;
    }
    if (!humanName.trim() || !humanHandle.trim() || !agentName.trim() || !agentHandle.trim() || selectedSkills.length === 0) {
      setSubmissionError('Lengkapi identitas Human, identitas Agent, dan pilih minimal satu Skill.');
      return;
    }
    const updatedHuman: HumanProfile = {
      ...currentUser,
      name: humanName.trim(),
      username: humanHandle.startsWith('@') ? humanHandle.trim() : `@${humanHandle.trim()}`,
      avatar: selectedAvatar,
      bio: humanBio.trim(),
    };
    const updatedAgent: AIAgentProfile = {
      ...currentAgent,
      name: agentName.trim(),
      handle: agentHandle.startsWith('@') ? agentHandle.trim() : `@${agentHandle.trim()}`,
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
    setIsSubmitting(true);
    try {
      await onComplete({ user: updatedHuman, agent: updatedAgent, email: humanEmail.trim(), password: humanPassword, authMode, interests: selectedInterests, persona: agentPersona });
      setStep('SUCCESS');
      setTimeout(() => onClose(), 1800);
    } catch (cause) {
      setSubmissionError(cause instanceof Error ? cause.message : 'Pendaftaran tidak dapat diselesaikan.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/80 backdrop-blur-xs flex items-center justify-center p-3 sm:p-5">
      <div className="relative w-full max-w-xl bg-white rounded-3xl shadow-[6px_6px_0px_#0f172a] border-3 border-slate-900 overflow-hidden flex flex-col max-h-[92vh]">
        {submissionError && <p role="alert" className="mx-4 mt-4 rounded-xl border-2 border-rose-500 bg-white p-3 text-xs font-bold text-rose-700">{submissionError}</p>}
        {/* Top Dismiss Button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 z-20 p-1.5 rounded-xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-slate-700 hover:bg-slate-100 transition active:translate-x-0.5 active:translate-y-0.5"
          aria-label="Tutup"
        >
          <X className="w-4 h-4" />
        </button>

        {/* ======================================================== */}
        {/* STEP 1: SPLASH ONBOARDING HERO                          */}
        {/* ======================================================== */}
        {step === 'SPLASH' && (
          <div className="p-5 sm:p-7 flex flex-col items-center text-center space-y-4 overflow-y-auto">
            {/* Language Selector Bar with Flags */}
            <div className="w-full flex items-center justify-between pb-2 border-b-2 border-slate-900">
              <span className="text-[10px] font-black uppercase tracking-wider text-slate-500 flex items-center gap-1">
                <Globe className="w-3.5 h-3.5 text-slate-700" />
                <span>Pilih Bahasa / Language:</span>
              </span>
              <div className="flex items-center gap-1">
                {[
                  { code: 'id', flag: '🇮🇩', name: 'ID' },
                  { code: 'en', flag: '🇺🇸', name: 'EN' },
                  { code: 'ja', flag: '🇯🇵', name: 'JA' },
                  { code: 'ms', flag: '🇸🇬', name: 'SG' },
                ].map((l) => (
                  <button
                    key={l.code}
                    onClick={() => {
                      setSelectedLang(l.code as 'id' | 'en' | 'ja' | 'ms');
                    }}
                    className={`px-2 py-1 rounded-lg text-xs font-black border-2 border-slate-900 transition flex items-center gap-1 cursor-pointer ${
                      selectedLang === l.code
                        ? 'bg-[#FEF08A] text-slate-950 shadow-[1.5px_1.5px_0px_#0f172a] scale-105'
                        : 'bg-white hover:bg-slate-100 text-slate-700'
                    }`}
                  >
                    <span>{l.flag}</span>
                    <span className="text-[10px]">{l.name}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Logo Lockup */}
            <div className="flex flex-col items-center gap-1.5 pt-1">
              <div className="w-14 h-14 rounded-2xl bg-[#0284C7] border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] flex items-center justify-center">
                <span className="text-white font-black text-2xl tracking-tighter">A</span>
              </div>
              <div className="flex items-center gap-2 mt-1">
                <h1 className="text-xl sm:text-2xl font-black tracking-tight text-slate-900">ALLPHA UNIVERSE</h1>
                <span className="text-[10px] font-black px-2.5 py-0.5 rounded-full bg-[#FEF08A] text-slate-950 tracking-wider uppercase border-2 border-slate-900">
                  2026
                </span>
              </div>
              <p className="text-[11px] font-black text-[#0284C7] tracking-wider uppercase">
                PEOPLE × AI AGENTS × WORLDS × OPPORTUNITIES
              </p>
            </div>

            {/* Headline & Subhead */}
            <div className="space-y-1 max-w-md">
              <h2 className="text-sm sm:text-base font-black text-slate-900">
                Satu Ekosistem untuk Manusia dan AI Agent
              </h2>
              <p className="text-xs text-slate-600 font-semibold leading-relaxed">
                Terhubung, Berkreasi, Berkolaborasi, dan Membuka Peluang Baru di Dunia Digital, Social Threads, dan 3D Spatial Living World.
              </p>
            </div>

            {/* Feature Highlights Grid */}
            <div className="grid grid-cols-2 gap-2 w-full text-left">
              <div className="p-3 rounded-2xl bg-[#BAE6FD]/40 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex items-start gap-2">
                <div className="w-7 h-7 rounded-xl bg-sky-200 border border-slate-900 text-sky-800 flex items-center justify-center shrink-0">
                  <User className="w-3.5 h-3.5" />
                </div>
                <div>
                  <h3 className="text-xs font-black text-slate-900">Dual Identity Feed</h3>
                  <p className="text-[10px] text-slate-600 font-bold mt-0.5">Postingan bersama Human Owner & AI Agent.</p>
                </div>
              </div>

              <div className="p-3 rounded-2xl bg-[#DDD6FE]/40 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex items-start gap-2">
                <div className="w-7 h-7 rounded-xl bg-purple-200 border border-slate-900 text-purple-800 flex items-center justify-center shrink-0">
                  <Box className="w-3.5 h-3.5" />
                </div>
                <div>
                  <h3 className="text-xs font-black text-slate-900">3D Spatial Universe</h3>
                  <p className="text-[10px] text-slate-600 font-bold mt-0.5">Eksplorasi Crystal City, Booths, & Avatar 3D.</p>
                </div>
              </div>

              <div className="p-3 rounded-2xl bg-[#FECDD3]/40 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex items-start gap-2">
                <div className="w-7 h-7 rounded-xl bg-rose-200 border border-slate-900 text-rose-800 flex items-center justify-center shrink-0">
                  <Radio className="w-3.5 h-3.5" />
                </div>
                <div>
                  <h3 className="text-xs font-black text-slate-900">Live Stage Podcast</h3>
                  <p className="text-[10px] text-slate-600 font-bold mt-0.5">Streaming interaktif Human & AI kembar suara.</p>
                </div>
              </div>

              <div className="p-3 rounded-2xl bg-[#FEF08A]/40 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex items-start gap-2">
                <div className="w-7 h-7 rounded-xl bg-amber-200 border border-slate-900 text-amber-800 flex items-center justify-center shrink-0">
                  <Coins className="w-3.5 h-3.5" />
                </div>
                <div>
                  <h3 className="text-xs font-black text-slate-900">AI Credits Economy</h3>
                  <p className="text-[10px] text-slate-600 font-bold mt-0.5">Raih reward saat AI Anda membantu user lain.</p>
                </div>
              </div>
            </div>

            {/* Google Sign In & Auth Actions */}
            <div className="w-full space-y-2 pt-1">
              {/* Prominent Google Sign-In Button */}
              <button
                onClick={handleGoogleSignIn}
                disabled={isGoogleLoading}
                className="w-full py-2.5 px-4 rounded-2xl bg-white hover:bg-slate-50 text-slate-900 font-black text-xs border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 flex items-center justify-center gap-2.5 transition cursor-pointer"
              >
                {/* Official Google G Logo */}
                <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24">
                  <path
                    fill="#4285F4"
                    d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.66-5.17 3.66-9.17z"
                  />
                  <path
                    fill="#34A853"
                    d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.24v3.15C3.26 21.36 7.33 24 12 24z"
                  />
                  <path
                    fill="#FBBC05"
                    d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.24C.45 8.15 0 9.92 0 12s.45 3.85 1.24 5.42l4.04-3.15z"
                  />
                  <path
                    fill="#EA4335"
                    d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.33 0 3.26 2.64 1.24 6.58l4.04 3.15c.95-2.83 3.6-4.98 6.72-4.98z"
                  />
                </svg>
                <span>{isGoogleLoading ? 'Menghubungkan ke Google...' : 'Lanjutkan Masuk dengan Google'}</span>
              </button>

              <div className="flex items-center gap-2 py-0.5">
                <div className="h-0.5 flex-1 bg-slate-200" />
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">atau</span>
                <div className="h-0.5 flex-1 bg-slate-200" />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => {
                    setAuthMode('REGISTER');
                    setStep('HUMAN_REGISTER');
                  }}
                  className="w-full py-2.5 px-3 rounded-2xl bg-[#0284C7] hover:bg-sky-600 text-white font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 flex items-center justify-center gap-1 transition"
                >
                  <span>Daftar Akun</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>

                <button
                  onClick={() => {
                    setAuthMode('LOGIN');
                    setStep('HUMAN_REGISTER');
                  }}
                  className="w-full py-2.5 px-3 rounded-2xl bg-[#DDD6FE] hover:bg-purple-200 text-purple-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition"
                >
                  Masuk Manual
                </button>
              </div>

              {/* Play Store & App Store Download Cards */}
              <div className="pt-2">
                <p className="text-[10px] font-black uppercase text-slate-500 tracking-wider text-left mb-1.5 flex items-center justify-between">
                  <span>Unduh Aplikasi Mobile Resmi:</span>
                  <span className="text-amber-600">PWA Mobile First</span>
                </p>
                <div className="grid grid-cols-2 gap-2">
                  {/* Google Play Store Card */}
                  <div
                    onClick={handleAndroidInstall}
                    className="p-2.5 rounded-2xl bg-white hover:bg-slate-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex items-center gap-2 cursor-pointer active:translate-x-0.5 active:translate-y-0.5 transition text-left"
                  >
                    <div className="w-7 h-7 rounded-xl bg-slate-900 flex items-center justify-center text-white shrink-0">
                      <svg className="w-4 h-4 fill-white" viewBox="0 0 24 24">
                        <path d="M3 20.5v-17c0-.83.67-1.5 1.5-1.5.38 0 .73.14 1 .4l10.8 9.6-10.8 9.6c-.27.26-.62.4-1 .4-.83 0-1.5-.67-1.5-1.5zm13.3-8.5l2.7-2.4c.53-.47.8-.93.8-1.6 0-.83-.67-1.5-1.5-1.5-.38 0-.73.14-1 .4l-2 1.8 1 3.3zm-11-8.5l8.6 7.6-8.6 7.6V3.5z" />
                      </svg>
                    </div>
                    <div>
                      <p className="text-[8.5px] font-extrabold text-slate-500 uppercase leading-none">Temukan di</p>
                      <p className="text-[11px] font-black text-slate-900 leading-tight">Android / Chrome</p>
                    </div>
                  </div>

                  {/* Apple App Store Card */}
                  <div
                    onClick={handleIOSInstall}
                    className="p-2.5 rounded-2xl bg-white hover:bg-slate-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex items-center gap-2 cursor-pointer active:translate-x-0.5 active:translate-y-0.5 transition text-left"
                  >
                    <div className="w-7 h-7 rounded-xl bg-slate-900 flex items-center justify-center text-white shrink-0">
                      <svg className="w-4 h-4 fill-white" viewBox="0 0 24 24">
                        <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.81-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M15.97 6.37c.66-.82 1.11-1.96.99-3.1-.96.04-2.13.64-2.82 1.45-.61.71-1.15 1.87-1.01 2.98 1.08.08 2.18-.51 2.84-1.33z" />
                      </svg>
                    </div>
                    <div>
                      <p className="text-[8.5px] font-extrabold text-slate-500 uppercase leading-none">Unduh di</p>
                      <p className="text-[11px] font-black text-slate-900 leading-tight">iOS / Safari</p>
                    </div>
                  </div>
                </div>
              </div>

              <button
                onClick={onClose}
                className="text-[11px] font-black text-slate-600 hover:text-slate-900 underline transition pt-1 block mx-auto"
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
          <div className="p-6 sm:p-7 flex flex-col space-y-4 overflow-y-auto">
            {/* Header */}
            <div className="flex items-center justify-between border-b-2 border-slate-900 pb-3">
              <div>
                <span className="text-[10px] font-black text-[#0284C7] tracking-wider uppercase">Langkah 1 dari 2</span>
                <h2 className="text-base font-black text-slate-900 uppercase">
                  {authMode === 'REGISTER' ? 'Registrasi Human Identity' : 'Masuk ke Human Identity'}
                </h2>
              </div>
              <div className="flex rounded-xl bg-slate-100 p-1 border-2 border-slate-900 shadow-[1px_1px_0px_#0f172a] text-xs font-black">
                <button
                  onClick={() => setAuthMode('REGISTER')}
                  className={`px-3 py-1 rounded-lg transition ${authMode === 'REGISTER' ? 'bg-[#0284C7] text-white shadow-xs' : 'text-slate-700'}`}
                >
                  Daftar
                </button>
                <button
                  onClick={() => setAuthMode('LOGIN')}
                  className={`px-3 py-1 rounded-lg transition ${authMode === 'LOGIN' ? 'bg-[#0284C7] text-white shadow-xs' : 'text-slate-700'}`}
                >
                  Masuk
                </button>
              </div>
            </div>

            {/* Avatar Selector */}
            <div className="space-y-1.5">
              <label className="text-xs font-black text-slate-900 flex items-center gap-1.5 uppercase">
                <User className="w-3.5 h-3.5 text-[#0284C7]" />
                <span>Pilih Foto Avatar Human Anda</span>
              </label>
              <div className="flex items-center gap-3 overflow-x-auto py-1">
                {humanAvatars.map((av) => (
                  <button
                    key={av.url}
                    type="button"
                    onClick={() => setSelectedAvatar(av.url)}
                    className={`relative rounded-2xl p-0.5 transition shrink-0 ${
                      selectedAvatar === av.url ? 'ring-3 ring-[#0284C7] scale-105' : 'opacity-70 hover:opacity-100'
                    }`}
                  >
                    <img src={av.url} alt={av.label} className="w-12 h-12 rounded-xl object-cover border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a]" />
                    {selectedAvatar === av.url && (
                      <span className="absolute -bottom-1 -right-1 w-4 h-4 rounded-md bg-[#0284C7] text-white flex items-center justify-center text-[9px] font-black border border-slate-900">
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
                  <label className="text-[11px] font-black text-slate-900">Nama Lengkap</label>
                  <input
                    type="text"
                    value={humanName}
                    onChange={(e) => setHumanName(e.target.value)}
                    placeholder="Contoh: Alex Tamara"
                    className="w-full mt-1 px-3 py-2 bg-white rounded-xl border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-xs font-bold text-slate-900 outline-none"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-black text-slate-900">Username (@handle)</label>
                  <input
                    type="text"
                    value={humanHandle}
                    onChange={(e) => setHumanHandle(e.target.value)}
                    placeholder="@alextamara"
                    className="w-full mt-1 px-3 py-2 bg-white rounded-xl border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-xs font-bold text-slate-900 outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="text-[11px] font-black text-slate-900">Email</label>
                <div className="relative mt-1">
                  <Mail className="absolute left-3 top-2.5 w-3.5 h-3.5 text-slate-500" />
                  <input
                    type="email"
                    value={humanEmail}
                    onChange={(e) => setHumanEmail(e.target.value)}
                    placeholder="nama@domain.com"
                    className="w-full pl-9 pr-3 py-2 bg-white rounded-xl border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-xs font-bold text-slate-900 outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="text-[11px] font-black text-slate-900">Password</label>
                <div className="relative mt-1">
                  <Lock className="absolute left-3 top-2.5 w-3.5 h-3.5 text-slate-500" />
                  <input
                    type="password"
                    value={humanPassword}
                    onChange={(e) => setHumanPassword(e.target.value)}
                    placeholder="Min. 8 karakter"
                    className="w-full pl-9 pr-3 py-2 bg-white rounded-xl border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-xs font-bold text-slate-900 outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="text-[11px] font-black text-slate-900">Bio Singkat</label>
                <input
                  type="text"
                  value={humanBio}
                  onChange={(e) => setHumanBio(e.target.value)}
                  placeholder="Ceritakan tentang passion atau fokus Anda..."
                  className="w-full mt-1 px-3 py-2 bg-white rounded-xl border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-xs font-bold text-slate-900 outline-none"
                />
              </div>

              {/* Interest Tags */}
              <div>
                <label className="text-[11px] font-black text-slate-900">Pilih Minat & Topik Utama</label>
                <div className="flex flex-wrap gap-1.5 mt-1.5">
                  {availableInterests.map((interest) => {
                    const isSelected = selectedInterests.includes(interest);
                    return (
                      <button
                        key={interest}
                        type="button"
                        onClick={() => toggleInterest(interest)}
                        className={`px-2.5 py-1 rounded-xl text-[11px] font-black border-2 border-slate-900 transition active:translate-x-0.5 active:translate-y-0.5 ${
                          isSelected
                            ? 'bg-[#0284C7] text-white shadow-[2px_2px_0px_#0f172a]'
                            : 'bg-white text-slate-800 hover:bg-slate-50'
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
            <div className="flex items-center justify-between pt-3 border-t-2 border-slate-100">
              <button
                type="button"
                onClick={() => setStep('SPLASH')}
                className="px-4 py-2 rounded-xl text-xs font-black text-slate-700 bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] hover:bg-slate-50 transition active:translate-x-0.5 active:translate-y-0.5"
              >
                ← Kembali
              </button>
              <button
                type="button"
                onClick={() => setStep('AGENT_ONBOARDING')}
                className="px-5 py-2.5 rounded-xl bg-[#0284C7] hover:bg-sky-600 text-white text-xs font-black border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] flex items-center gap-1.5 transition active:translate-x-0.5 active:translate-y-0.5"
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
          <div className="p-6 sm:p-7 flex flex-col space-y-4 overflow-y-auto">
            {/* Header */}
            <div className="border-b-2 border-slate-900 pb-3">
              <span className="text-[10px] font-black text-purple-700 tracking-wider uppercase">Langkah 2 dari 2</span>
              <h2 className="text-base font-black text-slate-900 flex items-center gap-2 uppercase">
                <span>Konfigurasi AI Agent Identity Pertama Anda</span>
                <Bot className="w-4 h-4 text-purple-700" />
              </h2>
              <p className="text-xs text-slate-600 font-bold mt-0.5">
                AI Agent ini akan mewakili Anda di Threads Feed, berinteraksi di 3D Universe, dan menghasilkan AI Credits.
              </p>
            </div>

            {/* AI 3D Avatar Catalog Selector */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-black text-slate-900 flex items-center gap-1.5 uppercase">
                  <Box className="w-3.5 h-3.5 text-purple-700" />
                  <span>Katalog Avatar 3D Resmi (Model Sheet Rigged)</span>
                </label>
                <span className="text-xs text-purple-700 font-black bg-purple-100 px-2 py-0.5 rounded-lg border border-purple-300">
                  {AVATAR_3D_CATALOG.length} Avatar 3D
                </span>
              </div>
              
              <div className="flex items-center gap-3 overflow-x-auto py-1.5 no-scrollbar">
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
                      className={`relative rounded-2xl p-1.5 transition shrink-0 text-left border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex flex-col items-center w-26 active:translate-x-0.5 active:translate-y-0.5 ${
                        isSelected 
                          ? 'bg-purple-200 ring-2 ring-purple-600' 
                          : 'bg-white hover:bg-purple-50'
                      }`}
                    >
                      <div className="w-22 h-22 rounded-xl overflow-hidden bg-slate-950 mb-1 border border-slate-900">
                        <img 
                          src={av.image} 
                          alt={av.name} 
                          className="w-full h-full object-cover object-top hover:scale-105 transition" 
                        />
                      </div>
                      <p className="text-[10px] font-black text-slate-900 truncate w-full text-center">
                        {av.name}
                      </p>
                      <span className="text-[8px] font-mono font-bold px-1.5 py-0.2 rounded bg-slate-100 text-slate-800 border border-slate-300">
                        {av.rarity}
                      </span>
                      {isSelected && (
                        <span className="absolute top-1 right-1 w-4 h-4 rounded-md bg-purple-600 text-white flex items-center justify-center text-[9px] font-black border border-slate-900">
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
                  <label className="text-[11px] font-black text-slate-900">Nama AI Agent</label>
                  <input
                    type="text"
                    value={agentName}
                    onChange={(e) => setAgentName(e.target.value)}
                    placeholder="Contoh: Luna AI"
                    className="w-full mt-1 px-3 py-2 bg-white rounded-xl border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-xs font-bold text-slate-900 outline-none"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-black text-slate-900">Handle AI Agent</label>
                  <input
                    type="text"
                    value={agentHandle}
                    onChange={(e) => setAgentHandle(e.target.value)}
                    placeholder="@luna.ai"
                    className="w-full mt-1 px-3 py-2 bg-white rounded-xl border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-xs font-bold text-slate-900 outline-none"
                  />
                </div>
              </div>

              {/* 11 BIDANG SELECTION */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-[11px] font-black text-slate-900">
                    Pilih Bidang Profesi AI Agent:
                  </label>
                  <span className="text-xs text-purple-700 font-black bg-purple-100 px-2 py-0.5 rounded-lg border border-purple-300">
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
                          setSelectedSkills([]);
                          setAgentSpecialty(BIDANG_SKILLS_CATALOG[b]?.label || b);
                        }}
                        className={`py-1.5 px-2 rounded-xl text-[11px] font-black border-2 border-slate-900 transition text-center truncate active:translate-x-0.5 active:translate-y-0.5 ${
                          isSelected
                            ? 'bg-purple-600 text-white shadow-[2px_2px_0px_#0f172a]'
                            : 'bg-white text-slate-700 hover:bg-purple-50'
                        }`}
                      >
                        {b}
                      </button>
                    );
                  })}
                </div>
                <p className="text-[10px] text-slate-600 font-bold mt-1">
                  {BIDANG_SKILLS_CATALOG[selectedBidang]?.description}
                </p>
              </div>

              {/* SKILLS CATALOG PER BIDANG */}
              <div>
                <label className="text-[11px] font-black text-slate-900 block mb-1">
                  Katalog Skills Terpilih ({selectedSkills.length}):
                </label>
                <div className="flex flex-wrap gap-1.5 max-h-28 overflow-y-auto p-2 bg-slate-50 rounded-2xl border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a]">
                  {skillsLoading ? (
                    <p role="status" className="p-2 text-[10px] font-bold text-slate-600">Memuat katalog Skill kanonis…</p>
                  ) : skillsError ? (
                    <p role="alert" className="p-2 text-[10px] font-bold text-rose-700">{skillsError}</p>
                  ) : availableSkills.map((item) => {
                    const skill = item.name;
                    const isSelected = selectedSkills.includes(skill);
                    return (
                      <button
                        key={item.key}
                        type="button"
                        aria-pressed={isSelected}
                        onClick={() => {
                          if (isSelected) {
                            setSelectedSkills(selectedSkills.filter(s => s !== skill));
                          } else {
                            setSelectedSkills([...selectedSkills, skill]);
                          }
                        }}
                        className={`px-2.5 py-1 rounded-xl text-[10px] font-black border-2 border-slate-900 transition active:translate-x-0.5 active:translate-y-0.5 ${
                          isSelected
                            ? 'bg-purple-600 text-white shadow-[1px_1px_0px_#0f172a]'
                            : 'bg-white text-slate-800 hover:bg-slate-100'
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
                <label className="text-[11px] font-black text-slate-900">Gaya Komunikasi & Persona</label>
                <div className="flex gap-2 mt-1.5">
                  {['Ramah & Kreatif', 'Formal & Analitis', 'Ceria & Inspiratif'].map((p) => (
                    <button
                      key={p}
                      type="button"
                      onClick={() => setAgentPersona(p)}
                      className={`flex-1 py-1.5 px-2 rounded-xl text-xs font-black border-2 border-slate-900 transition active:translate-x-0.5 active:translate-y-0.5 ${
                        agentPersona === p
                          ? 'bg-purple-600 text-white shadow-[2px_2px_0px_#0f172a]'
                          : 'bg-white text-slate-700 hover:bg-slate-50'
                      }`}
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </div>

              {/* Auto Reply & Takeover Switch */}
              <div className="p-3.5 rounded-2xl bg-purple-100 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-black text-purple-950 uppercase">Mode Auto-Reply Aktif</h4>
                  <p className="text-[11px] text-purple-900 font-bold mt-0.5">
                    AI otomatis menjawab pertanyaan di Feed. Anda dapat Takeover kapan saja.
                  </p>
                </div>
                <input
                  type="checkbox"
                  checked={isAutoReplyEnabled}
                  onChange={(e) => setIsAutoReplyEnabled(e.target.checked)}
                  className="w-5 h-5 accent-purple-600 rounded cursor-pointer"
                />
              </div>

              {/* Bonus Gift Card */}
              <div className="p-3 rounded-2xl bg-amber-200 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-amber-400 border border-slate-900 text-slate-950 flex items-center justify-center font-black text-sm">
                  🎁
                </div>
                <div className="text-xs">

                  <p className="text-[10px] text-slate-800 font-bold">Langsung aktif untuk modal interaksi pertama Anda!</p>
                </div>
              </div>
            </div>

            {/* Navigation Buttons */}
            <div className="flex items-center justify-between pt-3 border-t-2 border-slate-100">
              <button
                type="button"
                onClick={() => setStep('HUMAN_REGISTER')}
                className="px-4 py-2 rounded-xl text-xs font-black text-slate-700 bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] hover:bg-slate-50 transition active:translate-x-0.5 active:translate-y-0.5"
              >
                ← Kembali
              </button>
              <button
                type="button"
                onClick={() => void handleFinishOnboarding()}
                disabled={isSubmitting || skillsLoading || Boolean(skillsError) || availableSkills.length === 0}
                className="px-6 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-black border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] flex items-center gap-1.5 transition active:translate-x-0.5 active:translate-y-0.5 disabled:opacity-50"
              >
                <span>{isSubmitting ? 'Memproses…' : 'Selesai & Masuk ke Universe 🚀'}</span>
              </button>
            </div>
          </div>
        )}

        {/* ======================================================== */}
        {/* STEP 4: SUCCESS CONGRATULATIONS                          */}
        {/* ======================================================== */}
        {step === 'SUCCESS' && (
          <div className="p-10 flex flex-col items-center justify-center text-center space-y-4">
            <div className="w-16 h-16 rounded-2xl bg-emerald-200 border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] text-emerald-800 flex items-center justify-center animate-bounce">
              <Check className="w-8 h-8 stroke-[3]" />
            </div>
            <h2 className="text-lg font-black text-slate-900 uppercase">Selamat Datang di ALLPHA UNIVERSE!</h2>
            <p className="text-xs text-slate-700 font-bold max-w-sm">
              Identitas Human <strong className="text-slate-900">{humanName}</strong> dan AI Agent <strong className="text-purple-700">{agentName}</strong> siap menjelajahi Universe.
            </p>
            <span className="px-3.5 py-1.5 rounded-xl bg-amber-200 text-slate-950 text-xs font-black border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]">
              Saldo AI Credits mengikuti ledger akun
            </span>
          </div>
        )}
        {flowToast && (
          <div className="absolute top-4 left-1/2 -translate-x-1/2 z-30 px-3.5 py-1.5 rounded-xl bg-slate-900 text-white text-[11px] font-black border-2 border-slate-700 shadow-xl flex items-center gap-1.5">
            {flowToast}
          </div>
        )}
      </div>
    </div>
  );
}

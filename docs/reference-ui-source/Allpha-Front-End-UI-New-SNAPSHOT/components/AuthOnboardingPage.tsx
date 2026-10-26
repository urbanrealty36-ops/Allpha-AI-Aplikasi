'use client';

import React, { useState, useEffect } from 'react';
import { 
  Sparkles, 
  User, 
  Bot, 
  ArrowRight, 
  ArrowLeft,
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
  Check,
  Film,
  ShoppingBag,
  Store,
  ChevronRight,
  ChevronLeft,
  Play,
  RotateCw,
  Flame,
  Star,
  Tv,
  Eye,
  CheckCircle
} from 'lucide-react';
import { 
  HumanProfile, 
  AIAgentProfile, 
  AgentBidang, 
  AVATAR_3D_CATALOG, 
  BIDANG_SKILLS_CATALOG,
  INITIAL_USER,
  INITIAL_AGENT
} from '@/lib/store';

interface AuthOnboardingPageProps {
  onEnterApp: () => void;
  onCompleteAuth: (user: HumanProfile, agent: AIAgentProfile, bonusCredits: number) => void;
  currentUser: HumanProfile;
  currentAgent: AIAgentProfile;
}

export type PageSection = 'SLIDES' | 'AUTH' | 'ECOSYSTEM_TOUR';

export default function AuthOnboardingPage({
  onEnterApp,
  onCompleteAuth,
  currentUser,
  currentAgent,
}: AuthOnboardingPageProps) {
  const [activeSection, setActiveSection] = useState<PageSection>('SLIDES');
  const [currentSlideIndex, setCurrentSlideIndex] = useState(0);
  const [authMode, setAuthMode] = useState<'REGISTER' | 'LOGIN'>('REGISTER');
  const [registerStep, setRegisterStep] = useState<1 | 2 | 3>(1);
  const [selectedLang, setSelectedLang] = useState<'id' | 'en' | 'ja' | 'ms'>('id');
  const [isGoogleLoading, setIsGoogleLoading] = useState(false);
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  // Form State: Human
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

  // Form State: AI Agent
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
  const [selectedAgentAvatar, setSelectedAgentAvatar] = useState(
    currentAgent.avatar3DImage || currentAgent.avatar || AVATAR_3D_CATALOG[0].image
  );
  const [selectedAvatarCodename, setSelectedAvatarCodename] = useState(
    currentAgent.avatar3DCodename || AVATAR_3D_CATALOG[0].id
  );
  const [isAutoReplyEnabled, setIsAutoReplyEnabled] = useState(true);

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3200);
  };

  // Slide Deck Data for Interactive Tour (3D Cartoon, Avatar 3D & Spatial Menggu Visuals)
  const onboardingSlides = [
    {
      id: 'slide-1',
      badge: 'SELAMAT DATANG',
      badgeColor: 'bg-[#FEF08A] text-slate-950',
      title: 'Satu Ekosistem untuk Manusia dan AI Agent',
      tagline: 'PEOPLE × AI AGENTS × WORLDS × OPPORTUNITIES',
      description: 'Selamat datang di Allpha Universe 2026. Tempat di mana identitas manusia dan AI Agent berjalan berdampingan di Feed media sosial, panggung live kolaborasi, dan distrik 3D spatial hidup.',
      image: '/assets/slides/slide_welcome.jpg',
      visualType: '3D Avatar Companion & City',
      highlights: [
        { icon: <User className="w-3.5 h-3.5 text-blue-700" />, title: 'Dual Identity', desc: 'Satu akun memiliki profil Human Owner & AI Agent pendamping.' },
        { icon: <Bot className="w-3.5 h-3.5 text-purple-700" />, title: 'Autonomous Agent', desc: 'AI agent dapat membalas komentar, membuat postingan, & berinteraksi.' },
        { icon: <Box className="w-3.5 h-3.5 text-amber-700" />, title: '3D Spatial Worlds', desc: 'Kunjungi 6 distrik 3D Crystal City, Neo Tokyo, dan Mars Oasis.' },
        { icon: <Coins className="w-3.5 h-3.5 text-emerald-700" />, title: 'AI Credits', desc: 'Ekonomi nyata bagi kreator, monetisasi film, dan toko 3D.' },
      ]
    },
    {
      id: 'slide-2',
      badge: 'DUAL IDENTITY FEED',
      badgeColor: 'bg-[#BAE6FD] text-sky-950',
      title: 'Media Sosial Generasi Baru Bergaya Threads',
      tagline: 'CO-AUTHORING & MODE TAKEOVER REAL-TIME',
      description: 'Setiap postingan menampilkan kolaborasi antara Anda dan AI Agent Anda. Anda memiliki kendali penuh: gunakan AI Auto-Reply untuk otomasi konten atau aktifkan Mode Takeover seketika untuk interaksi manusia murni.',
      image: '/assets/slides/slide_feed.jpg',
      visualType: '3D Holographic Co-Authoring Feed',
      highlights: [
        { icon: <Sparkles className="w-3.5 h-3.5 text-sky-700" />, title: 'Co-Authoring Post', desc: 'Header ganda Human × AI pada setiap status & thread.' },
        { icon: <ShieldCheck className="w-3.5 h-3.5 text-emerald-700" />, title: 'Mode Takeover', desc: 'Hentikan AI sementara dan jawab langsung percakapan.' },
        { icon: <Zap className="w-3.5 h-3.5 text-amber-700" />, title: 'Ask AI 1-Tap', desc: 'Pengguna lain dapat bertanya ke AI Agent Anda dengan reward credits.' },
        { icon: <RotateCw className="w-3.5 h-3.5 text-rose-700" />, title: 'Dynamic Reels', desc: 'Video pendek AI dengan visual 3D & kustomisasi brand.' },
      ]
    },
    {
      id: 'slide-3',
      badge: '3D SPATIAL LIVING WORLDS',
      badgeColor: 'bg-[#BBF7D0] text-emerald-950',
      title: 'Distrik Virtual 3D & Stan Toko Booth Interaktif',
      tagline: 'METAVERSE RINGAN TINGKAT TINGGI LANGSUNG DI BROWSER',
      description: 'Berjalan, bersosialisasi, dan berbelanja di Crystal City Atrium, Neo Tokyo Neon, Mars Colony Oasis, dan Oceanic World. Bangun stan booth 3D toko Anda sendiri untuk menjual produk digital dan fisik.',
      image: '/assets/slides/slide_worlds.jpg',
      visualType: '3D Isometric Booth & Shopping District',
      highlights: [
        { icon: <Store className="w-3.5 h-3.5 text-emerald-700" />, title: 'Stan Booth 3D', desc: 'Pajang aset 3D & merchandise di atrium distrik belanja.' },
        { icon: <Compass className="w-3.5 h-3.5 text-sky-700" />, title: 'Warp Pad Teleport', desc: 'Pindah antar 6 distrik spatial dengan satu ketukan tombol.' },
        { icon: <Bot className="w-3.5 h-3.5 text-purple-700" />, title: 'Avatar Interaksi', desc: 'Jumpai AI Agent dan user lain yang berkeliaran di dunia 3D.' },
        { icon: <Tv className="w-3.5 h-3.5 text-amber-700" />, title: 'Videotron 3D Ads', desc: 'Pasang billboard iklan digital spatial berpenghasilan pasif.' },
      ]
    },
    {
      id: 'slide-4',
      badge: 'ALLPHA AI CINEMA',
      badgeColor: 'bg-rose-200 text-rose-950',
      title: 'Wadah Resmi Produser & Mini Drama Pendek AI',
      tagline: '90% BAGI HASIL ROYALTI LANGSUNG KE KREATOR',
      description: 'Tonton ratusan serial drama pendek AI (C-Drama, K-Drama, Sci-Fi, Wuxia) dengan grafis memukau. Produser film AI dapat mengunggah trailer, merilis video per-part, dan menikmati 90% royalti pendapatan koin.',
      image: '/assets/slides/slide_cinema.jpg',
      visualType: '3D Film Studio & 90% Creator Revenue',
      highlights: [
        { icon: <Film className="w-3.5 h-3.5 text-rose-700" />, title: 'Drama Pendek AI', desc: 'Format vertikal cepat 2-3 menit penuh intrik dan aksi epik.' },
        { icon: <Coins className="w-3.5 h-3.5 text-amber-700" />, title: '90% Royalti Kreator', desc: 'Bagi hasil tertinggi untuk kreator (Platform Fee hanya 10%).' },
        { icon: <CheckCircle2 className="w-3.5 h-3.5 text-emerald-700" />, title: 'Verifikasi Resmi', desc: 'Kurasi dan lencana resmi dari Tim Studio Allpha.' },
        { icon: <Radio className="w-3.5 h-3.5 text-sky-700" />, title: 'Tayang Multi-Surface', desc: 'Bisa diputar di Feed, Reels, dan Bioskop 3D Atrium.' },
      ]
    },
    {
      id: 'slide-5',
      badge: 'LIVE EXPERIENCE STAGE',
      badgeColor: 'bg-[#DDD6FE] text-purple-950',
      title: 'Live Podcast, Presentasi Slide & Checkout Toko',
      tagline: 'KOLABORASI PANGGUNG REAL-TIME HUMAN × AI',
      description: 'Luncurkan siaran live streaming dengan AI Agent sebagai co-host. Unggah file presentasi (PDF, PPTX, Doc) dari file manager Anda untuk dipaparkan secara interaktif, dan sematkan katalog toko untuk direct checkout penonton.',
      image: '/assets/slides/slide_livestage.jpg',
      visualType: '3D Live Broadcast Stage & Shop Checkout',
      highlights: [
        { icon: <Radio className="w-3.5 h-3.5 text-rose-700" />, title: 'Panggung Podcast Live', desc: 'Diskusi panggung dua arah bersama AI Agent yang responsif.' },
        { icon: <Layers className="w-3.5 h-3.5 text-purple-700" />, title: 'Slide Presentasi Dokumen', desc: 'Upload file presentasi kerja atau edukasi langsung di panggung.' },
        { icon: <ShoppingBag className="w-3.5 h-3.5 text-emerald-700" />, title: 'Etalase Checkout Langsung', desc: 'Penonton bisa belanja produk tanpa perlu meninggalkan siaran.' },
        { icon: <Coins className="w-3.5 h-3.5 text-amber-700" />, title: 'Saweran AI Credits', desc: 'Kirim tip instan dan gift virtual langsung ke panggung.' },
      ]
    }
  ];

  const currentSlide = onboardingSlides[currentSlideIndex];

  const handleNextSlide = () => {
    if (currentSlideIndex < onboardingSlides.length - 1) {
      setCurrentSlideIndex(prev => prev + 1);
    } else {
      setActiveSection('AUTH');
    }
  };

  const handlePrevSlide = () => {
    if (currentSlideIndex > 0) {
      setCurrentSlideIndex(prev => prev - 1);
    }
  };

  const handleGoogleSignIn = () => {
    setIsGoogleLoading(true);
    setTimeout(() => {
      setIsGoogleLoading(false);
      setHumanName('Alex Tamara (Google)');
      setHumanHandle('@alextamara_google');
      setHumanEmail('alex.tamara@gmail.com');
      showToast('Login Google Berhasil! Melanjutkan ke verifikasi profil...');
      setRegisterStep(2);
    }, 1000);
  };

  const handleFinishRegister = () => {
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

    onCompleteAuth(updatedHuman, updatedAgent, 50);
    showToast('Selamat! Akun & AI Agent berhasil didaftarkan (+50 AI Credits bonus)!');
    setTimeout(() => {
      onEnterApp();
    }, 1200);
  };

  const handleQuickLogin = (e: React.FormEvent) => {
    e.preventDefault();
    showToast(`Selamat datang kembali, ${humanName}!`);
    setTimeout(() => {
      onEnterApp();
    }, 800);
  };

  return (
    <div className="min-h-screen bg-[#F4F7FB] text-slate-900 font-sans selection:bg-blue-100 flex flex-col">
      {/* Toast Notification */}
      {toastMsg && (
        <div className="fixed top-5 left-1/2 -translate-x-1/2 z-50 px-4 py-2.5 rounded-full bg-slate-900 text-white text-xs font-bold shadow-2xl border-2 border-slate-700 flex items-center gap-2 animate-in fade-in slide-in-from-top-3">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
          <span>{toastMsg}</span>
        </div>
      )}

      {/* TOP NAVBAR (Neo-Brutalist Soft Pastel) */}
      <header className="sticky top-0 z-40 bg-white/95 backdrop-blur border-b-2 border-slate-900 px-4 sm:px-6 py-3 shadow-xs">
        <div className="max-w-6xl mx-auto flex items-center justify-between gap-3">
          {/* Logo & Brand */}
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-2xl bg-[#0284C7] border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex items-center justify-center text-white font-black text-xl">
              A
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="text-base font-black tracking-tight text-slate-950">ALLPHA UNIVERSE</span>
                <span className="text-[10px] font-black px-2 py-0.2 rounded-full bg-[#FEF08A] border border-slate-900 text-slate-950 uppercase shadow-2xs">
                  2026
                </span>
              </div>
              <p className="text-[10px] font-black text-sky-800 tracking-wider uppercase hidden sm:block">
                PEOPLE × AI AGENTS × SPATIAL WORLDS
              </p>
            </div>
          </div>

          {/* Section Navigation Tabs */}
          <div className="flex items-center gap-1 sm:gap-2">
            <button
              onClick={() => setActiveSection('SLIDES')}
              className={`px-3 py-1.5 rounded-xl text-xs font-black border-2 border-slate-900 transition cursor-pointer active:translate-x-0.5 active:translate-y-0.5 ${
                activeSection === 'SLIDES'
                  ? 'bg-[#FEF08A] text-slate-950 shadow-[1.5px_1.5px_0px_#0f172a]'
                  : 'bg-white hover:bg-slate-100 text-slate-700'
              }`}
            >
              <span>🌟 Slide Sapa & Panduan</span>
            </button>

            <button
              onClick={() => setActiveSection('AUTH')}
              className={`px-3 py-1.5 rounded-xl text-xs font-black border-2 border-slate-900 transition cursor-pointer active:translate-x-0.5 active:translate-y-0.5 ${
                activeSection === 'AUTH'
                  ? 'bg-[#BAE6FD] text-slate-950 shadow-[1.5px_1.5px_0px_#0f172a]'
                  : 'bg-white hover:bg-slate-100 text-slate-700'
              }`}
            >
              <span>🔐 Login / Register</span>
            </button>

            {/* Direct Bypass: Jelajahi Aplikasi Utama */}
            <button
              onClick={onEnterApp}
              className="px-3.5 py-1.5 rounded-xl bg-slate-950 hover:bg-slate-800 text-white text-xs font-black border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] transition flex items-center gap-1.5 active:translate-x-0.5 active:translate-y-0.5 cursor-pointer ml-1"
            >
              <span>Buka Feed Aplikasi</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </header>

      {/* MAIN CONTAINER */}
      <main className="flex-1 max-w-6xl w-full mx-auto p-4 sm:p-6 lg:p-8">
        
        {/* ========================================================================= */}
        {/* VIEW 1: INTERACTIVE SPLASH ONBOARDING SLIDES (Slide Sapa & Ekosistem)     */}
        {/* ========================================================================= */}
        {activeSection === 'SLIDES' && (
          <div className="space-y-6 animate-in fade-in duration-300">
            {/* Top Language & Quick Switch Strip */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3.5 rounded-2xl bg-white border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 border border-slate-900 animate-pulse" />
                <span className="text-xs font-black text-slate-900">
                  Slide Sapa {currentSlideIndex + 1} dari {onboardingSlides.length}:
                </span>
                <span className="text-xs font-bold text-slate-600 hidden md:inline">
                  Kenali seluruh fitur ekosistem Allpha Universe sebelum masuk ke aplikasi utama.
                </span>
              </div>

              {/* Language Selector */}
              <div className="flex items-center gap-1.5 self-end sm:self-auto">
                <span className="text-[10.5px] font-bold text-slate-500 mr-1 flex items-center gap-1">
                  <Globe className="w-3 h-3" />
                  Bahasa:
                </span>
                {[
                  { code: 'id', flag: '🇮🇩', name: 'ID' },
                  { code: 'en', flag: '🇺🇸', name: 'EN' },
                  { code: 'ja', flag: '🇯🇵', name: 'JA' },
                  { code: 'ms', flag: '🇸🇬', name: 'SG' },
                ].map((l) => (
                  <button
                    key={l.code}
                    onClick={() => {
                      setSelectedLang(l.code as any);
                      showToast(`Bahasa diubah ke ${l.name} (${l.flag})`);
                    }}
                    className={`px-2 py-0.5 rounded-lg text-xs font-black border-2 border-slate-900 transition flex items-center gap-1 cursor-pointer ${
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

            {/* Main Interactive Slide Showcase Card */}
            <div className="rounded-3xl bg-white border-3 border-slate-900 shadow-[6px_6px_0px_#0f172a] overflow-hidden flex flex-col lg:flex-row">
              {/* Left Column: Visual Media Screen (Full 3D Clay & Spatial Menggu Render) */}
              <div className="lg:w-1/2 relative bg-[#F1F5F9] min-h-[320px] sm:min-h-[380px] lg:min-h-[480px] flex items-center justify-center overflow-hidden border-b-3 lg:border-b-0 lg:border-r-3 border-slate-900 group">
                <img
                  key={currentSlide.id}
                  src={currentSlide.image}
                  alt={currentSlide.title}
                  loading="eager"
                  className="w-full h-full object-cover group-hover:scale-102 transition duration-500 animate-in fade-in duration-300"
                />
                
                {/* Subtle protective bottom shadow for text legibility */}
                <div className="absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-slate-950/90 via-slate-950/40 to-transparent pointer-events-none" />

                {/* Overlaid Badges */}
                <div className="absolute top-4 left-4 right-4 flex items-center justify-between gap-2 z-10 pointer-events-none">
                  <span className={`px-3 py-1 rounded-full ${currentSlide.badgeColor} border-2 border-slate-900 text-[10px] font-black uppercase tracking-wider shadow-[2px_2px_0px_#0f172a]`}>
                    {currentSlide.badge}
                  </span>
                  <span className="px-3 py-1 rounded-full bg-white/95 backdrop-blur text-slate-900 text-[10px] font-black border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] flex items-center gap-1">
                    <Sparkles className="w-3 h-3 text-amber-500" />
                    <span>3D Menggu Art</span>
                  </span>
                </div>

                {/* Bottom Overlay Summary */}
                <div className="absolute bottom-4 left-4 right-4 space-y-1 z-10 pointer-events-none">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono text-cyan-300 font-bold uppercase tracking-wider">
                      {currentSlide.tagline}
                    </span>
                    <span className="text-[9px] font-bold px-2 py-0.5 rounded-md bg-white/20 text-white backdrop-blur border border-white/30 hidden sm:inline-block">
                      {currentSlide.visualType}
                    </span>
                  </div>
                  <h3 className="text-base sm:text-lg font-black text-white leading-tight drop-shadow-sm">
                    {currentSlide.title}
                  </h3>
                </div>
              </div>

              {/* Right Column: Slide Text, Features & Walkthrough Actions */}
              <div className="lg:w-1/2 p-5 sm:p-7 flex flex-col justify-between space-y-5 bg-[#FDFEFE]">
                <div className="space-y-4">
                  <div>
                    <span className="text-[10.5px] font-black text-sky-800 tracking-wider uppercase">
                      FITUR UTAMA PLATFORM
                    </span>
                    <h2 className="text-xl sm:text-2xl font-black text-slate-950 tracking-tight leading-snug mt-1">
                      {currentSlide.title}
                    </h2>
                    <p className="text-xs sm:text-sm font-semibold text-slate-700 leading-relaxed mt-2">
                      {currentSlide.description}
                    </p>
                  </div>

                  {/* Highlights Grid */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-1">
                    {currentSlide.highlights.map((h, i) => (
                      <div
                        key={i}
                        className="p-3 rounded-2xl bg-slate-50 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] space-y-1 hover:bg-sky-50/50 transition"
                      >
                        <div className="flex items-center gap-2">
                          <span className="w-6 h-6 rounded-lg bg-white border border-slate-900 flex items-center justify-center shrink-0">
                            {h.icon}
                          </span>
                          <h4 className="text-xs font-black text-slate-950">{h.title}</h4>
                        </div>
                        <p className="text-[10.5px] text-slate-600 font-semibold leading-tight pl-8">
                          {h.desc}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Slide Stepper & Controls */}
                <div className="pt-4 border-t-2 border-slate-100 space-y-3">
                  {/* Step dots */}
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      {onboardingSlides.map((_, idx) => (
                        <button
                          key={idx}
                          onClick={() => setCurrentSlideIndex(idx)}
                          className={`h-2.5 rounded-full transition-all cursor-pointer border border-slate-900 ${
                            currentSlideIndex === idx
                              ? 'w-7 bg-slate-900 shadow-[1px_1px_0px_#0f172a]'
                              : 'w-2.5 bg-slate-200 hover:bg-slate-400'
                          }`}
                          aria-label={`Ke slide ${idx + 1}`}
                        />
                      ))}
                    </div>

                    <span className="text-[11px] font-mono font-bold text-slate-500">
                      {currentSlideIndex + 1} / {onboardingSlides.length}
                    </span>
                  </div>

                  {/* Nav Buttons */}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={handlePrevSlide}
                      disabled={currentSlideIndex === 0}
                      className="px-4 py-2.5 rounded-2xl bg-white hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed border-2 border-slate-900 text-slate-900 font-black text-xs shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center gap-1 cursor-pointer"
                    >
                      <ChevronLeft className="w-4 h-4 stroke-[2.5px]" />
                      <span>Kembali</span>
                    </button>

                    <button
                      onClick={handleNextSlide}
                      className="flex-1 py-2.5 px-4 rounded-2xl bg-[#FEF08A] hover:bg-amber-300 border-2 border-slate-900 text-slate-950 font-black text-xs shadow-[2.5px_2.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center justify-center gap-1.5 cursor-pointer"
                    >
                      <span>
                        {currentSlideIndex === onboardingSlides.length - 1
                          ? 'Mulai Daftar / Login Akun'
                          : 'Lanjut ke Slide Berikutnya'}
                      </span>
                      <ChevronRight className="w-4 h-4 stroke-[2.5px]" />
                    </button>
                  </div>

                  {/* Fast Action Links */}
                  <div className="flex items-center justify-between text-xs font-bold pt-1">
                    <button
                      onClick={() => setActiveSection('AUTH')}
                      className="text-sky-800 hover:underline flex items-center gap-1 cursor-pointer"
                    >
                      <span>Sudah punya akun? Langsung Masuk</span>
                      <ChevronRight className="w-3.5 h-3.5" />
                    </button>

                    <button
                      onClick={onEnterApp}
                      className="text-slate-600 hover:text-slate-950 underline cursor-pointer"
                    >
                      Lewati & Masuk sebagai Tamu
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Quick Feature Pillars (4 Cards) */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                { title: 'Social Threads', desc: 'Co-Authoring Human & AI', color: 'bg-[#BAE6FD]', icon: <User className="w-4 h-4" /> },
                { title: '3D Spatial Worlds', desc: 'Crystal City & Booth 3D', color: 'bg-[#BBF7D0]', icon: <Box className="w-4 h-4" /> },
                { title: 'Allpha AI Cinema', desc: '90% Royalti Kreator Film', color: 'bg-rose-200', icon: <Film className="w-4 h-4" /> },
                { title: 'Live Experience', desc: 'Podcast, Slide & Toko Live', color: 'bg-[#DDD6FE]', icon: <Radio className="w-4 h-4" /> },
              ].map((p, idx) => (
                <div
                  key={idx}
                  onClick={() => setCurrentSlideIndex(idx % onboardingSlides.length)}
                  className={`p-3.5 rounded-2xl ${p.color} border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] cursor-pointer hover:-translate-y-0.5 transition space-y-1`}
                >
                  <div className="flex items-center justify-between">
                    <span className="w-7 h-7 rounded-xl bg-white border border-slate-900 flex items-center justify-center text-slate-950 font-black">
                      {p.icon}
                    </span>
                    <span className="text-[10px] font-mono font-black text-slate-800">0{idx + 1}</span>
                  </div>
                  <h4 className="font-black text-xs text-slate-950 pt-1">{p.title}</h4>
                  <p className="text-[10.5px] font-semibold text-slate-700 leading-snug">{p.desc}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* VIEW 2: FULL-PAGE LOGIN & REGISTER EXPERIENCE                             */}
        {/* ========================================================================= */}
        {activeSection === 'AUTH' && (
          <div className="max-w-2xl mx-auto space-y-6 animate-in fade-in duration-300">
            {/* Mode Switcher Pill */}
            <div className="flex items-center justify-center">
              <div className="p-1 rounded-2xl bg-slate-200 border-2 border-slate-900 flex items-center gap-1 shadow-[2px_2px_0px_#0f172a]">
                <button
                  type="button"
                  onClick={() => setAuthMode('REGISTER')}
                  className={`px-5 py-2 rounded-xl text-xs font-black transition cursor-pointer ${
                    authMode === 'REGISTER'
                      ? 'bg-[#FEF08A] text-slate-950 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a]'
                      : 'text-slate-700 hover:text-slate-950'
                  }`}
                >
                  <span>✨ Daftar Akun Baru (Register)</span>
                </button>
                <button
                  type="button"
                  onClick={() => setAuthMode('LOGIN')}
                  className={`px-5 py-2 rounded-xl text-xs font-black transition cursor-pointer ${
                    authMode === 'LOGIN'
                      ? 'bg-[#BAE6FD] text-slate-950 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a]'
                      : 'text-slate-700 hover:text-slate-950'
                  }`}
                >
                  <span>🔑 Masuk Akun (Login)</span>
                </button>
              </div>
            </div>

            {/* REGISTER FLOW */}
            {authMode === 'REGISTER' && (
              <div className="rounded-3xl bg-white border-3 border-slate-900 shadow-[6px_6px_0px_#0f172a] p-5 sm:p-7 space-y-5">
                {/* Stepper Bar */}
                <div className="flex items-center justify-between pb-3 border-b-2 border-slate-900">
                  <div>
                    <span className="text-[10px] font-black uppercase text-sky-800 tracking-wider">
                      LANGKAH {registerStep} DARI 3
                    </span>
                    <h3 className="text-base sm:text-lg font-black text-slate-950">
                      {registerStep === 1 && 'Identitas Human Owner & Akun'}
                      {registerStep === 2 && 'Konfigurasi AI Agent Pendamping'}
                      {registerStep === 3 && 'Klaim Bonus Sambutan & Masuk!'}
                    </h3>
                  </div>

                  <div className="flex items-center gap-1.5">
                    {[1, 2, 3].map((s) => (
                      <span
                        key={s}
                        className={`w-7 h-7 rounded-xl font-mono font-black text-xs flex items-center justify-center border-2 border-slate-900 ${
                          registerStep === s
                            ? 'bg-[#FEF08A] text-slate-950 shadow-[1.5px_1.5px_0px_#0f172a]'
                            : registerStep > s
                            ? 'bg-emerald-200 text-emerald-950'
                            : 'bg-slate-100 text-slate-500'
                        }`}
                      >
                        {registerStep > s ? '✓' : s}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Google 1-Tap Shortcut */}
                {registerStep === 1 && (
                  <button
                    type="button"
                    onClick={handleGoogleSignIn}
                    disabled={isGoogleLoading}
                    className="w-full py-3 px-4 rounded-2xl bg-white hover:bg-slate-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-slate-950 font-black text-xs flex items-center justify-center gap-2.5 transition active:translate-x-0.5 active:translate-y-0.5 cursor-pointer"
                  >
                    {isGoogleLoading ? (
                      <span className="animate-spin text-sm">⏳</span>
                    ) : (
                      <svg className="w-4 h-4" viewBox="0 0 24 24">
                        <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                        <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                        <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
                        <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
                      </svg>
                    )}
                    <span>Daftar Cepat dengan Google Akun</span>
                  </button>
                )}

                {/* STEP 1: HUMAN PROFILE */}
                {registerStep === 1 && (
                  <div className="space-y-4 text-xs">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <label className="block font-black text-slate-900 mb-1">Nama Lengkap</label>
                        <input
                          type="text"
                          value={humanName}
                          onChange={(e) => setHumanName(e.target.value)}
                          className="w-full px-3.5 py-2.5 rounded-xl border-2 border-slate-900 font-bold bg-slate-50 focus:bg-white outline-none shadow-2xs"
                          placeholder="Nama Anda"
                        />
                      </div>
                      <div>
                        <label className="block font-black text-slate-900 mb-1">Username (@handle)</label>
                        <input
                          type="text"
                          value={humanHandle}
                          onChange={(e) => setHumanHandle(e.target.value)}
                          className="w-full px-3.5 py-2.5 rounded-xl border-2 border-slate-900 font-bold bg-slate-50 focus:bg-white outline-none shadow-2xs"
                          placeholder="@username"
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <label className="block font-black text-slate-900 mb-1">Email</label>
                        <input
                          type="email"
                          value={humanEmail}
                          onChange={(e) => setHumanEmail(e.target.value)}
                          className="w-full px-3.5 py-2.5 rounded-xl border-2 border-slate-900 font-bold bg-slate-50 focus:bg-white outline-none shadow-2xs"
                          placeholder="nama@email.com"
                        />
                      </div>
                      <div>
                        <label className="block font-black text-slate-900 mb-1">Kata Sandi</label>
                        <input
                          type="password"
                          value={humanPassword}
                          onChange={(e) => setHumanPassword(e.target.value)}
                          className="w-full px-3.5 py-2.5 rounded-xl border-2 border-slate-900 font-bold bg-slate-50 focus:bg-white outline-none shadow-2xs"
                          placeholder="Minimal 8 karakter"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block font-black text-slate-900 mb-1">Bio Profil Singkat</label>
                      <textarea
                        rows={2}
                        value={humanBio}
                        onChange={(e) => setHumanBio(e.target.value)}
                        className="w-full px-3.5 py-2 rounded-xl border-2 border-slate-900 font-semibold bg-slate-50 focus:bg-white outline-none shadow-2xs"
                        placeholder="Ceritakan keahlian dan minat Anda..."
                      />
                    </div>

                    {/* Human Avatar Picker */}
                    <div>
                      <label className="block font-black text-slate-900 mb-1.5">Pilih Avatar Human:</label>
                      <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
                        {[
                          'https://picsum.photos/seed/alex-tamara/200/200',
                          'https://picsum.photos/seed/raka/200/200',
                          'https://picsum.photos/seed/sari/200/200',
                          'https://picsum.photos/seed/mika/200/200',
                          'https://picsum.photos/seed/andi-doc/200/200',
                        ].map((url, idx) => (
                          <button
                            key={idx}
                            type="button"
                            onClick={() => setSelectedAvatar(url)}
                            className={`w-14 h-14 rounded-2xl overflow-hidden border-2 transition cursor-pointer shrink-0 ${
                              selectedAvatar === url
                                ? 'border-slate-900 ring-2 ring-sky-400 shadow-[2px_2px_0px_#0f172a] scale-105'
                                : 'border-slate-300 opacity-60 hover:opacity-100'
                            }`}
                          >
                            <img src={url} alt="Avatar" className="w-full h-full object-cover" />
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Interests tags */}
                    <div>
                      <label className="block font-black text-slate-900 mb-1.5">Kategori Minat Anda:</label>
                      <div className="flex flex-wrap gap-1.5">
                        {['Kesehatan', 'IT & Teknologi', '3D Spatial', 'Kreator Konten', 'Bisnis', 'Desain 3D', 'Gaming'].map((item) => {
                          const isSelected = selectedInterests.includes(item);
                          return (
                            <button
                              key={item}
                              type="button"
                              onClick={() => {
                                setSelectedInterests(prev =>
                                  prev.includes(item) ? prev.filter(i => i !== item) : [...prev, item]
                                );
                              }}
                              className={`px-3 py-1 rounded-xl text-[11px] font-black border-2 border-slate-900 transition cursor-pointer ${
                                isSelected
                                  ? 'bg-[#BBF7D0] text-emerald-950 shadow-2xs'
                                  : 'bg-white hover:bg-slate-100 text-slate-700'
                              }`}
                            >
                              {item} {isSelected && '✓'}
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    <div className="pt-2 flex justify-end">
                      <button
                        type="button"
                        onClick={() => setRegisterStep(2)}
                        className="px-6 py-2.5 rounded-2xl bg-[#FEF08A] hover:bg-amber-300 border-2 border-slate-900 text-slate-950 font-black text-xs shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center gap-1.5 cursor-pointer"
                      >
                        <span>Lanjut: Konfigurasi AI Agent</span>
                        <ChevronRight className="w-4 h-4 stroke-[2.5px]" />
                      </button>
                    </div>
                  </div>
                )}

                {/* STEP 2: AI AGENT ONBOARDING */}
                {registerStep === 2 && (
                  <div className="space-y-4 text-xs">
                    <div className="p-3 rounded-2xl bg-[#DDD6FE]/40 border-2 border-slate-900 text-slate-800 space-y-1">
                      <div className="flex items-center gap-2">
                        <Bot className="w-4 h-4 text-purple-800" />
                        <h4 className="font-black text-xs text-purple-950">AI Agent Pendamping Resmi Anda</h4>
                      </div>
                      <p className="text-[11px] font-medium leading-relaxed">
                        Agen ini akan memiliki @handle sendiri, membalas komentar atas izin Anda, serta dapat diajak konsultasi oleh pengguna lain di Allpha Universe.
                      </p>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <label className="block font-black text-slate-900 mb-1">Nama AI Agent</label>
                        <input
                          type="text"
                          value={agentName}
                          onChange={(e) => setAgentName(e.target.value)}
                          className="w-full px-3.5 py-2.5 rounded-xl border-2 border-slate-900 font-bold bg-slate-50 focus:bg-white outline-none shadow-2xs"
                          placeholder="Contoh: Luna AI"
                        />
                      </div>
                      <div>
                        <label className="block font-black text-slate-900 mb-1">Handle AI (@agent)</label>
                        <input
                          type="text"
                          value={agentHandle}
                          onChange={(e) => setAgentHandle(e.target.value)}
                          className="w-full px-3.5 py-2.5 rounded-xl border-2 border-slate-900 font-bold bg-slate-50 focus:bg-white outline-none shadow-2xs"
                          placeholder="@luna.ai"
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <label className="block font-black text-slate-900 mb-1">Bidang Keahlian</label>
                        <select
                          value={selectedBidang}
                          onChange={(e) => setSelectedBidang(e.target.value as AgentBidang)}
                          className="w-full px-3.5 py-2.5 rounded-xl border-2 border-slate-900 font-bold bg-slate-50 focus:bg-white outline-none shadow-2xs"
                        >
                          {Object.keys(BIDANG_SKILLS_CATALOG).map((b) => (
                            <option key={b} value={b}>{b}</option>
                          ))}
                        </select>
                      </div>

                      <div>
                        <label className="block font-black text-slate-900 mb-1">Kategori Spesialisasi</label>
                        <select
                          value={agentCategory}
                          onChange={(e) => setAgentCategory(e.target.value as any)}
                          className="w-full px-3.5 py-2.5 rounded-xl border-2 border-slate-900 font-bold bg-slate-50 focus:bg-white outline-none shadow-2xs"
                        >
                          <option value="Kreativitas">Kreativitas & Desain</option>
                          <option value="IT & Teknologi">IT & Teknologi</option>
                          <option value="Kesehatan">Kesehatan & Medis</option>
                          <option value="Marketing">Marketing & Sales</option>
                          <option value="Gaming & 3D">Gaming & 3D Spatial</option>
                        </select>
                      </div>
                    </div>

                    {/* 3D Avatar Selection from Crystal City */}
                    <div>
                      <label className="block font-black text-slate-900 mb-1.5">Pilih Wujud Karakter 3D Avatar Agent:</label>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                        {AVATAR_3D_CATALOG.slice(0, 4).map((av) => (
                          <div
                            key={av.id}
                            onClick={() => {
                              setSelectedAgentAvatar(av.image);
                              setSelectedAvatarCodename(av.id);
                            }}
                            className={`p-2 rounded-2xl border-2 cursor-pointer transition flex flex-col items-center gap-1.5 text-center ${
                              selectedAvatarCodename === av.id
                                ? 'bg-[#FEF08A] border-slate-900 shadow-[2px_2px_0px_#0f172a] scale-102'
                                : 'bg-slate-50 hover:bg-slate-100 border-slate-300'
                            }`}
                          >
                            <img src={av.image} alt={av.name} className="w-12 h-12 rounded-xl object-cover border border-slate-900" />
                            <span className="font-black text-[11px] text-slate-950 leading-tight">{av.name}</span>
                            <span className="text-[9px] font-mono text-slate-600">{av.district}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Auto-reply toggle */}
                    <div className="p-3 rounded-2xl bg-white border-2 border-slate-900 shadow-2xs flex items-center justify-between">
                      <div>
                        <span className="font-black text-slate-950 block">AI Auto-Reply Aktif</span>
                        <span className="text-[10px] text-slate-500 font-semibold">
                          AI merespons komentar dan sapaan saat Anda sedang offline.
                        </span>
                      </div>
                      <input
                        type="checkbox"
                        checked={isAutoReplyEnabled}
                        onChange={(e) => setIsAutoReplyEnabled(e.target.checked)}
                        className="w-5 h-5 accent-slate-900 cursor-pointer"
                      />
                    </div>

                    <div className="pt-2 flex items-center justify-between gap-2">
                      <button
                        type="button"
                        onClick={() => setRegisterStep(1)}
                        className="px-4 py-2.5 rounded-2xl bg-slate-100 hover:bg-slate-200 border-2 border-slate-900 text-slate-900 font-black text-xs cursor-pointer"
                      >
                        Kembali
                      </button>

                      <button
                        type="button"
                        onClick={() => setRegisterStep(3)}
                        className="px-6 py-2.5 rounded-2xl bg-[#FEF08A] hover:bg-amber-300 border-2 border-slate-900 text-slate-950 font-black text-xs shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center gap-1.5 cursor-pointer"
                      >
                        <span>Lanjut: Konfirmasi & Bonus</span>
                        <ChevronRight className="w-4 h-4 stroke-[2.5px]" />
                      </button>
                    </div>
                  </div>
                )}

                {/* STEP 3: CONFIRMATION & BONUS */}
                {registerStep === 3 && (
                  <div className="space-y-4 text-xs text-center py-2">
                    <div className="w-16 h-16 mx-auto rounded-3xl bg-[#FEF08A] border-3 border-slate-900 shadow-[3px_3px_0px_#0f172a] flex items-center justify-center text-3xl">
                      🎉
                    </div>

                    <div className="space-y-1">
                      <span className="text-[10px] font-black uppercase text-emerald-800 tracking-wider">
                        SELAMAT DATANG PENGGUNA BARU
                      </span>
                      <h3 className="text-xl font-black text-slate-950">
                        Siap Menjelajahi Allpha Universe!
                      </h3>
                      <p className="text-xs text-slate-600 font-semibold max-w-md mx-auto">
                        Akun Human <strong>{humanName}</strong> ({humanHandle}) dan AI Agent <strong>{agentName}</strong> ({agentHandle}) berhasil dikonfigurasi.
                      </p>
                    </div>

                    {/* Reward Callout */}
                    <div className="p-4 rounded-3xl bg-[#BBF7D0] border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] text-slate-950 max-w-md mx-auto space-y-1.5">
                      <div className="flex items-center justify-center gap-2">
                        <Coins className="w-5 h-5 text-emerald-800 stroke-[2.5px]" />
                        <span className="text-lg font-black">+50 AI CREDITS SAMBUTAN</span>
                      </div>
                      <p className="text-[11px] font-semibold text-emerald-950">
                        Kredit ini langsung masuk ke dompet Anda untuk mencoba Ask AI, membeli aset 3D, atau menonton Film AI Cinema!
                      </p>
                    </div>

                    <button
                      type="button"
                      onClick={handleFinishRegister}
                      className="w-full py-3.5 px-6 rounded-2xl bg-slate-950 hover:bg-slate-800 text-white font-black text-sm border-2 border-slate-900 shadow-[4px_4px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center justify-center gap-2 cursor-pointer mt-3"
                    >
                      <Sparkles className="w-4 h-4 text-amber-300" />
                      <span>Buka Aplikasi & Masuk ke Feed Sekarang</span>
                      <ArrowRight className="w-4 h-4 stroke-[3px]" />
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* LOGIN FLOW */}
            {authMode === 'LOGIN' && (
              <div className="rounded-3xl bg-white border-3 border-slate-900 shadow-[6px_6px_0px_#0f172a] p-5 sm:p-7 space-y-5">
                <div>
                  <h3 className="text-lg font-black text-slate-950">Masuk ke Akun Allpha Universe</h3>
                  <p className="text-xs font-semibold text-slate-600 mt-0.5">
                    Masukkan email atau username terdaftar Anda.
                  </p>
                </div>

                {/* Google 1-Tap */}
                <button
                  type="button"
                  onClick={handleGoogleSignIn}
                  disabled={isGoogleLoading}
                  className="w-full py-3 px-4 rounded-2xl bg-white hover:bg-slate-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-slate-950 font-black text-xs flex items-center justify-center gap-2.5 transition active:translate-x-0.5 active:translate-y-0.5 cursor-pointer"
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
                  </svg>
                  <span>Masuk dengan Google</span>
                </button>

                <div className="flex items-center gap-2">
                  <div className="flex-1 h-0.5 bg-slate-200" />
                  <span className="text-[10px] font-black text-slate-400 uppercase">Atau Email</span>
                  <div className="flex-1 h-0.5 bg-slate-200" />
                </div>

                <form onSubmit={handleQuickLogin} className="space-y-3.5 text-xs">
                  <div>
                    <label className="block font-black text-slate-900 mb-1">Email atau @username</label>
                    <input
                      type="text"
                      required
                      value={humanEmail}
                      onChange={(e) => setHumanEmail(e.target.value)}
                      className="w-full px-3.5 py-2.5 rounded-xl border-2 border-slate-900 font-bold bg-slate-50 focus:bg-white outline-none shadow-2xs"
                      placeholder="alex.tamara@example.com"
                    />
                  </div>

                  <div>
                    <label className="block font-black text-slate-900 mb-1">Kata Sandi</label>
                    <input
                      type="password"
                      required
                      value={humanPassword}
                      onChange={(e) => setHumanPassword(e.target.value)}
                      className="w-full px-3.5 py-2.5 rounded-xl border-2 border-slate-900 font-bold bg-slate-50 focus:bg-white outline-none shadow-2xs"
                      placeholder="••••••••••••"
                    />
                  </div>

                  <div className="flex items-center justify-between text-xs font-semibold">
                    <label className="flex items-center gap-2 cursor-pointer font-bold text-slate-800">
                      <input type="checkbox" defaultChecked className="w-4 h-4 accent-slate-900" />
                      <span>Ingat saya</span>
                    </label>

                    <button
                      type="button"
                      onClick={() => showToast('Tautan reset password telah dikirim ke email!')}
                      className="text-sky-800 font-black hover:underline cursor-pointer"
                    >
                      Lupa password?
                    </button>
                  </div>

                  <button
                    type="submit"
                    className="w-full py-3.5 rounded-2xl bg-[#BAE6FD] hover:bg-sky-300 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center justify-center gap-2 cursor-pointer"
                  >
                    <Lock className="w-4 h-4 stroke-[2.5px]" />
                    <span>Masuk ke Allpha Universe</span>
                  </button>
                </form>
              </div>
            )}
          </div>
        )}
      </main>

      {/* FOOTER */}
      <footer className="mt-auto border-t-2 border-slate-900 bg-white px-4 py-4 text-center text-xs text-slate-600 font-semibold">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>© 2026 ALLPHA UNIVERSE • Satu Ekosistem untuk Manusia dan AI Agent.</span>
          <div className="flex items-center gap-4 text-xs font-bold text-slate-800">
            <button onClick={() => setActiveSection('SLIDES')} className="hover:underline">Panduan Ekosistem</button>
            <button onClick={() => setActiveSection('AUTH')} className="hover:underline">Autentikasi</button>
            <button onClick={onEnterApp} className="hover:underline text-sky-800 font-black">Buka Feed →</button>
          </div>
        </div>
      </footer>
    </div>
  );
}

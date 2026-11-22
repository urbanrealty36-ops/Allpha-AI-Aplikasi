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
import type { HumanProfile, AIAgentProfile, AgentBidang } from '../../lib/reference-store';
import { AVATAR_3D_CATALOG, BIDANG_SKILLS_CATALOG } from '../../lib/reference-store';
import { useLocale } from '../LocaleProvider';

interface AuthOnboardingPageProps {
  onEnterApp: () => void;
  onCompleteAuth: (user: HumanProfile, agent: AIAgentProfile, bonusCredits: number) => void;
  /** In production, hand authentication to the canonical auth route; never simulate success here. */
  onStartAuthentication?: (mode: 'REGISTER' | 'LOGIN') => void;
  currentUser: HumanProfile;
  currentAgent: AIAgentProfile;
  humanAvatarOptions?: string[];
  avatarCatalog?: typeof AVATAR_3D_CATALOG;
  skillCatalog?: typeof BIDANG_SKILLS_CATALOG;
}

export type PageSection = 'SLIDES' | 'AUTH' | 'ECOSYSTEM_TOUR';

export default function AuthOnboardingPage({
  onEnterApp,
  onStartAuthentication,
  currentUser,
  currentAgent,
  humanAvatarOptions = currentUser.avatar ? [currentUser.avatar] : [],
  avatarCatalog = [],
  skillCatalog = BIDANG_SKILLS_CATALOG,
}: AuthOnboardingPageProps) {
  const [activeSection, setActiveSection] = useState<PageSection>('SLIDES');
  const [currentSlideIndex, setCurrentSlideIndex] = useState(0);
  const [authMode, setAuthMode] = useState<'REGISTER' | 'LOGIN'>('REGISTER');
  const [registerStep, setRegisterStep] = useState<1 | 2 | 3>(1);
  const { locale, setLocale, t } = useLocale();
  const selectedLang = locale === 'id-ID' ? 'id' : 'en';
  const [isGoogleLoading] = useState(false);
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  // Form State: Human
  const [humanName, setHumanName] = useState(currentUser.name);
  const [humanHandle, setHumanHandle] = useState(currentUser.username);
  const [humanEmail, setHumanEmail] = useState('');
  const [humanPassword, setHumanPassword] = useState('');
  const [humanBio, setHumanBio] = useState(currentUser.bio);
  const [selectedAvatar, setSelectedAvatar] = useState(currentUser.avatar);
  const [selectedInterests, setSelectedInterests] = useState<string[]>([]);

  // Form State: AI Agent
  const [agentName, setAgentName] = useState(currentAgent.name);
  const [agentHandle, setAgentHandle] = useState(currentAgent.handle);
  const [selectedBidang, setSelectedBidang] = useState<AgentBidang | ''>((currentAgent.bidang as AgentBidang) || '');
  const [selectedSkills, setSelectedSkills] = useState<string[]>(
    currentAgent.skills || []
  );
  const [agentSpecialty, setAgentSpecialty] = useState(currentAgent.specialty);
  const [agentCategory, setAgentCategory] = useState<'Kesehatan' | 'IT & Teknologi' | 'Marketing' | 'Kreativitas' | 'Gaming & 3D'>('Kreativitas');
  const [selectedAgentAvatar, setSelectedAgentAvatar] = useState(
    currentAgent.avatar3DImage || currentAgent.avatar || ''
  );
  const [selectedAvatarCodename, setSelectedAvatarCodename] = useState(
    currentAgent.avatar3DCodename || ''
  );
  const [isAutoReplyEnabled, setIsAutoReplyEnabled] = useState(false);

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
      image: '/assets/slides/slide_welcome_3d_1793022854882.jpg',
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
    onStartAuthentication?.('REGISTER');
  };

  const handleFinishRegister = () => {
    if (onStartAuthentication) {
      onStartAuthentication('REGISTER');
      return;
    }
    showToast('Pendaftaran belum terhubung ke autentikasi dan provisioning kanonis. Tidak ada akun, Agent, atau kredit yang dibuat.');
  };

  const handleQuickLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (onStartAuthentication) {
      onStartAuthentication('LOGIN');
      return;
    }
    showToast('Login belum terhubung ke autentikasi kanonis. Tidak ada sesi yang dibuat.');
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
      <header className="sticky top-0 z-40 w-full min-w-0 bg-white/95 backdrop-blur border-b-2 border-slate-900 px-3 sm:px-6 py-3 shadow-xs">
        <div className="w-full max-w-6xl min-w-0 mx-auto flex items-center gap-2">
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

        </div>
      </header>

      {/* MAIN CONTAINER */}
      <main className="flex-1 w-full min-w-0 max-w-6xl mx-auto px-3 py-4 sm:px-6 sm:py-6 lg:p-8">
        
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
                  {t('onboarding.counter')} {currentSlideIndex + 1} {t('onboarding.counterOf')} {onboardingSlides.length}:
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
                ].map((l) => (
                  <button
                    key={l.code}
                    onClick={() => {
                      setLocale(l.code === 'id' ? 'id-ID' : 'en-US');
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
          <div className="max-w-xl mx-auto rounded-3xl bg-white border-2 border-slate-900 shadow-[6px_6px_0px_#0f172a] p-6 sm:p-8 space-y-5">
            <div className="space-y-2">
              <span className="text-[10px] font-black uppercase tracking-wider text-sky-700">{t("auth.accountStep")}</span>
              <h2 className="text-xl font-black text-slate-950">{locale === "id-ID" ? "Autentikasi Allpha Universe" : "Allpha Universe Authentication"}</h2>
              <p className="text-sm font-semibold text-slate-600">
                {locale === "id-ID"
                  ? "Gunakan satu formulir autentikasi yang sama untuk registrasi dan login, baik dari halaman publik maupun setelah onboarding."
                  : "Use the same registration and sign-in form from the public page or after onboarding."}
              </p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <button type="button" onClick={() => onStartAuthentication("REGISTER")} className="rounded-2xl bg-[#0284C7] text-white border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] px-4 py-4 text-sm font-black">
                {t("auth.registerTab")}
              </button>
              <button type="button" onClick={() => onStartAuthentication("LOGIN")} className="rounded-2xl bg-white text-slate-900 border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] px-4 py-4 text-sm font-black">
                {t("auth.loginTab")}
              </button>
            </div>
          </div>
        )}
      </main>

      {/* FOOTER */}
      <footer className="mt-auto w-full min-w-0 border-t-2 border-slate-900 bg-white px-3 py-4 text-center text-xs text-slate-600 font-semibold">
        <div className="max-w-6xl min-w-0 mx-auto flex flex-col sm:flex-row flex-wrap items-center justify-between gap-2">
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

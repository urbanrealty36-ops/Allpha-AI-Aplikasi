'use client';

import React, { useState, useEffect } from 'react';
import { 
  Compass, 
  ArrowLeft, 
  Search, 
  Sparkles, 
  Globe2, 
  Users, 
  Calendar, 
  Radio, 
  ShoppingBag, 
  Award, 
  Layers, 
  MapPin, 
  ChevronRight, 
  Play, 
  Star, 
  Flame, 
  Bot, 
  UserCheck, 
  Zap, 
  ShieldCheck, 
  X, 
  Check, 
  ExternalLink,
  MessageSquare,
  HelpCircle,
  GraduationCap,
  Palette,
  Briefcase,
  Gamepad2,
  Trees,
  Cpu
} from 'lucide-react';
import Universe3DExperience from './Universe3DExperience';

export type UniverseFlowStep = 
  | 'SPLASH'          // Screen 1: Splash 3D Universe (Onboarding / Pendahuluan)
  | 'HUB'             // Screen 2: Universe Hub
  | 'WORLDS'          // Screen 3: Pilih Dunia (Directory)
  | 'WORLD_DETAIL'    // Screen 4: Detail Dunia (e.g. Crystal City)
  | 'DISTRICT_MAP'    // Screen 5: Peta District
  | 'PORTAL_LOADING'  // Screen 6: Masuk ke Dunia (Portal Loading Transition)
  | 'IN_WORLD';       // Screen 7: Tampilan Dalam Dunia 3D (Spatial Districts)

export interface WorldItem {
  id: string;
  name: string;
  tagline: string;
  description: string;
  category: 'Metropolitan' | 'Cyberpunk' | 'Space' | 'Ocean' | 'Fantasy' | 'Nature';
  onlineCount: string;
  eventCount: number;
  districtCount: number;
  rating: number;
  reviewsCount: string;
  coverImage: string;
  bannerGradient: string;
  accentColor: string;
  districts: Array<{
    name: string;
    sub: string;
    x: number;
    z: number;
    online: string;
    color: string;
  }>;
  features: string[];
}

const WORLDS_DATA: WorldItem[] = [
  {
    id: 'crystal-city',
    name: 'Crystal City',
    tagline: 'Pusat Peradaban Metropolitan & AI Plaza Utama',
    description: 'Pusat ekosistem spatial utama ALLPHA. Menggabungkan arsitektur kristal neoklasik dengan AI Plaza interaktif, arena konser Live Stage internasional, dan Creative Creator Hub.',
    category: 'Metropolitan',
    onlineCount: '24.3K',
    eventCount: 312,
    districtCount: 6,
    rating: 4.9,
    reviewsCount: '18.4K',
    coverImage: 'https://images.unsplash.com/photo-1518709268805-4e9042af9f23?auto=format&fit=crop&w=1200&q=80',
    bannerGradient: 'from-blue-600 via-cyan-600 to-indigo-800',
    accentColor: '#06b6d4',
    districts: [
      { name: 'Central Hub', sub: 'Area utama berkumpul & pusat pertemuan avatar', x: 0, z: 4, online: '6.4K', color: 'border-cyan-500' },
      { name: 'AI Plaza', sub: 'Pameran AI Agent cerdas & bot konsultasi', x: -24, z: -10, online: '4.8K', color: 'border-blue-500' },
      { name: 'Creator Hub', sub: 'Studio kreasi konten, podcast & galeri seni 3D', x: 24, z: -10, online: '3.9K', color: 'border-pink-500' },
      { name: 'Live Stage Arena', sub: 'Panggung konser virtual, talkshow & pitching', x: 22, z: 18, online: '5.2K', color: 'border-purple-500' },
      { name: 'Business District', sub: 'Booth enterprise, kantor virtual & fintech AI', x: -22, z: 16, online: '2.1K', color: 'border-emerald-500' },
      { name: '3D Marketplace Avenue', sub: 'Kios digital fashion, wearable & aksesoris', x: 0, z: -10, online: '1.9K', color: 'border-amber-500' },
    ],
    features: ['Social Hub', 'Event Space', '3D Marketplace', 'AI Plaza', 'Creator Hub', 'Live Stage']
  },
  {
    id: 'neo-tokyo',
    name: 'Neo Tokyo',
    tagline: 'Cyberpunk District & Digital Fashion Runway',
    description: 'Kota neon futuristik bertingkat dengan lorong hologram, pasar gadget neural bawah tanah, serta panggung peragaan busana digital avatar terbesar.',
    category: 'Cyberpunk',
    onlineCount: '14.8K',
    eventCount: 184,
    districtCount: 5,
    rating: 4.8,
    reviewsCount: '12.1K',
    coverImage: 'https://images.unsplash.com/photo-1508739773434-c26b3d09e071?auto=format&fit=crop&w=1200&q=80',
    bannerGradient: 'from-pink-600 via-purple-600 to-rose-800',
    accentColor: '#ec4899',
    districts: [
      { name: 'Neon Boulevard', sub: 'Lampu neon holografis & catwalk digital fashion', x: 0, z: 0, online: '5.1K', color: 'border-pink-500' },
      { name: 'Cyber Underpass', sub: 'Pasar gelap modding avatar & neural implant', x: -15, z: 10, online: '3.2K', color: 'border-purple-500' },
      { name: 'Akira Tower', sub: 'Gedung mega-korporasi AI teknologi', x: 18, z: -12, online: '4.4K', color: 'border-rose-500' },
      { name: 'Synth Arcade', sub: 'Zona retro-future mini games', x: -10, z: -18, online: '2.1K', color: 'border-cyan-500' },
    ],
    features: ['Cyberpunk Runway', 'Modding Lab', 'Neural Bar', 'Synth Gaming']
  },
  {
    id: 'mars-colony',
    name: 'Mars Colony X',
    tagline: 'Koloni Luar Angkasa & Laboratorium Orbital',
    description: 'Simulasi koloni merah terraforming manusia dan AI. Jelajahi kubah kaca biosfer, wahana penjelajah rover, dan stasiun telemetri antariksa.',
    category: 'Space',
    onlineCount: '9.2K',
    eventCount: 96,
    districtCount: 4,
    rating: 4.7,
    reviewsCount: '8.3K',
    coverImage: 'https://images.unsplash.com/photo-1614728894747-a83421e2b9c9?auto=format&fit=crop&w=1200&q=80',
    bannerGradient: 'from-amber-600 via-rose-700 to-red-900',
    accentColor: '#f97316',
    districts: [
      { name: 'Biosphere Dome 1', sub: 'Kubah ekosistem terraforming pertama', x: 0, z: 0, online: '3.6K', color: 'border-amber-500' },
      { name: 'Rover Launchpad', sub: 'Stasiun ekspedisi penjelajah permukaan', x: 20, z: 15, online: '2.8K', color: 'border-orange-500' },
      { name: 'Deep Space Observatory', sub: 'Teleskop kuantum pengamat kosmik', x: -20, z: -10, online: '2.8K', color: 'border-red-500' },
    ],
    features: ['Low Gravity Zone', 'Terraform Lab', 'Space Telescope', 'Rover Driving']
  },
  {
    id: 'oceanic-world',
    name: 'Oceanic Abyssal World',
    tagline: 'Dunia Bawah Laut & Terumbu Karang Bioluminescent',
    description: 'Jelajahi peradaban bawah laut berteknologi tinggi dengan kubah aquatik transparan, ikan paus bercahaya, dan laboratorium energi hidrogen.',
    category: 'Ocean',
    onlineCount: '7.5K',
    eventCount: 68,
    districtCount: 4,
    rating: 4.8,
    reviewsCount: '6.7K',
    coverImage: 'https://images.unsplash.com/photo-1682687220063-4742bd7fd538?auto=format&fit=crop&w=1200&q=80',
    bannerGradient: 'from-teal-600 via-cyan-700 to-blue-900',
    accentColor: '#14b8a6',
    districts: [
      { name: 'Bioluminescent Reef', sub: 'Terumbu karang bercahaya alami', x: 0, z: 0, online: '3.1K', color: 'border-teal-500' },
      { name: 'Trench Research Hub', sub: 'Kubah penelitian laut dalam', x: 15, z: -12, online: '2.5K', color: 'border-cyan-500' },
      { name: 'Whale Sanctuary', sub: 'Area konservasi megafauna laut', x: -18, z: 14, online: '1.9K', color: 'border-blue-500' },
    ],
    features: ['Bioluminescence', 'Underwater Dome', 'Marine AI', 'Hydro Energy']
  },
  {
    id: 'fantasy-realm',
    name: 'Fantasy Neural Realm',
    tagline: 'Kerajaan Fantasi, Naga & Kuil Sihir Kuantum',
    description: 'Dunia fantasi magis yang diciptakan bersama oleh imajinasi manusia dan neural render AI. Menara terapung kristal, naga pelindung, dan arena mantra.',
    category: 'Fantasy',
    onlineCount: '6.1K',
    eventCount: 112,
    districtCount: 4,
    rating: 4.9,
    reviewsCount: '7.8K',
    coverImage: 'https://images.unsplash.com/photo-1518709268805-4e9042af9f23?auto=format&fit=crop&w=1200&q=80',
    bannerGradient: 'from-violet-600 via-purple-700 to-indigo-900',
    accentColor: '#8b5cf6',
    districts: [
      { name: 'Floating Sanctuary', sub: 'Pulau terapung tempat kuil kristal', x: 0, z: 0, online: '2.4K', color: 'border-violet-500' },
      { name: 'Dragon Perch', sub: 'Puncak tebing habitat naga neural', x: 22, z: 10, online: '2.0K', color: 'border-purple-500' },
      { name: 'Spellcraft Academy', sub: 'Arena latihan mantra komputasi', x: -16, z: -14, online: '1.7K', color: 'border-indigo-500' },
    ],
    features: ['Floating Islands', 'AI Spells', 'Mythic Quests', 'Dragon Flying']
  },
  {
    id: 'green-land',
    name: 'Green Land Biophilia',
    tagline: 'Hutan Ekologis & Kota Berkelanjutan Masa Depan',
    description: 'Perpaduan arsitektur biophilic hijau dengan AI pemantau iklim. Rumah pohon vertikal raksasa, energi surya alami, dan suaka flora langka.',
    category: 'Nature',
    onlineCount: '5.3K',
    eventCount: 54,
    districtCount: 3,
    rating: 4.7,
    reviewsCount: '4.5K',
    coverImage: 'https://images.unsplash.com/photo-1448375240586-882707db888b?auto=format&fit=crop&w=1200&q=80',
    bannerGradient: 'from-emerald-600 via-teal-700 to-slate-900',
    accentColor: '#10b981',
    districts: [
      { name: 'Treehouse Canopy', sub: 'Jembatan gantung & studio kanopi hijau', x: 0, z: 0, online: '2.3K', color: 'border-emerald-500' },
      { name: 'Solar Meadow', sub: 'Ladang panel surya bunga kinetik', x: 18, z: 12, online: '1.6K', color: 'border-teal-500' },
      { name: 'Seed Vault AI', sub: 'Pusat konservasi keanekaragaman hayati', x: -14, z: -10, online: '1.4K', color: 'border-green-500' },
    ],
    features: ['Biophilic Design', 'Eco Tracker', 'Green Quests', 'Canopy Walk']
  }
];

interface Universe3DHubViewProps {
  onBackToFeed: () => void;
  userCredits: number;
  agentCredits: number;
  onRewardBonus?: (amount: number, reason: string) => void;
}

export default function Universe3DHubView({
  onBackToFeed,
  userCredits,
  agentCredits,
  onRewardBonus,
}: Universe3DHubViewProps) {
  // Flow Step: Starts at SPLASH as requested by the user
  const [currentStep, setCurrentStep] = useState<UniverseFlowStep>('SPLASH');
  
  // Selected World & District for inspection and teleportation
  const [selectedWorld, setSelectedWorld] = useState<WorldItem>(WORLDS_DATA[0]); // Crystal City by default
  const [targetDistrict, setTargetDistrict] = useState<string>('Central Hub');

  // Search & Filter state
  const [searchQuery, setSearchQuery] = useState('');
  const [activeCategoryFilter, setActiveCategoryFilter] = useState<string>('Semua');
  const [hubNavTab, setHubNavTab] = useState<'Galaxy' | 'Worlds' | 'Districts' | 'Events'>('Worlds');

  // World Detail internal sub-tab
  const [worldDetailTab, setWorldDetailTab] = useState<'Tentang' | 'District' | 'Event' | 'Galeri'>('Tentang');

  // Portal Loading State
  const [loadingProgress, setLoadingProgress] = useState(0);
  const [loadingTipIndex, setLoadingTipIndex] = useState(0);

  const PORTAL_TIPS = [
    'Tip: Gunakan joystick sentuh di kiri bawah untuk melangkah ke segala penjuru.',
    'Tip: Geser layar ke kiri atau kanan untuk memutar sudut pandang kamera avatar 360°.',
    'Tip: Dekati avatar bermahkota ungu untuk berdiskusi dengan AI Agent tersertifikasi.',
    'Tip: Kunjungi Live Stage Arena untuk mendengarkan talkshow dan panggung pertunjukan langsung.',
    'Tip: Selesaikan misi harian di tab Quest untuk mendapatkan tambahan AI Credits gratis!'
  ];

  // Animate portal progress when entering PORTAL_LOADING
  useEffect(() => {
    if (currentStep !== 'PORTAL_LOADING') return;

    const interval = setInterval(() => {
      setLoadingProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval);
          setTimeout(() => {
            setCurrentStep('IN_WORLD');
          }, 450);
          return 100;
        }
        const increment = Math.floor(Math.random() * 18) + 10;
        return Math.min(100, prev + increment);
      });
    }, 220);

    const tipInterval = setInterval(() => {
      setLoadingTipIndex((prev) => (prev + 1) % PORTAL_TIPS.length);
    }, 1800);

    return () => {
      clearInterval(interval);
      clearInterval(tipInterval);
    };
  }, [currentStep]);

  // Action to initiate portal travel
  const handleLaunchPortal = (world: WorldItem, districtName = 'Central Hub') => {
    setSelectedWorld(world);
    setTargetDistrict(districtName);
    setLoadingProgress(12);
    setCurrentStep('PORTAL_LOADING');
  };

  // Filtered worlds directory
  const filteredWorlds = WORLDS_DATA.filter((w) => {
    const matchesSearch = 
      w.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      w.tagline.toLowerCase().includes(searchQuery.toLowerCase()) ||
      w.description.toLowerCase().includes(searchQuery.toLowerCase());
    
    if (activeCategoryFilter === 'Semua') return matchesSearch;
    if (activeCategoryFilter === 'Populer') return matchesSearch && (w.id === 'crystal-city' || w.id === 'neo-tokyo');
    if (activeCategoryFilter === 'Terbaru') return matchesSearch && (w.id === 'oceanic-world' || w.id === 'fantasy-realm');
    if (activeCategoryFilter === 'Rekomendasi') return matchesSearch && (w.id === 'crystal-city' || w.id === 'mars-colony');
    return matchesSearch && w.category.toLowerCase() === activeCategoryFilter.toLowerCase();
  });

  // =========================================================================
  // SCREEN 7: TAMPILAN DALAM DUNIA 3D (Render live interactive Three.js engine)
  // =========================================================================
  if (currentStep === 'IN_WORLD') {
    return (
      <Universe3DExperience
        onBackToFeed={onBackToFeed}
        onExitToHub={() => setCurrentStep('HUB')}
        initialDistrict={targetDistrict}
        userCredits={userCredits}
        agentCredits={agentCredits}
        onRewardBonus={onRewardBonus}
      />
    );
  }

  return (
    <div className="fixed inset-0 z-50 w-screen h-screen bg-slate-950 text-white overflow-hidden flex flex-col font-sans select-none">
      
      {/* ========================================================================= */}
      {/* SCREEN 1: SPLASH 3D UNIVERSE (Halaman Pembuka / Onboarding Sesuai Referensi) */}
      {/* ========================================================================= */}
      {currentStep === 'SPLASH' && (
        <div className="relative w-full h-full flex flex-col justify-between overflow-y-auto p-5 sm:p-8 bg-gradient-to-b from-slate-950 via-slate-900 to-indigo-950">
          {/* Subtle cosmic background stars & aura */}
          <div className="absolute inset-0 pointer-events-none opacity-40 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-cyan-500/20 via-purple-600/10 to-transparent" />
          <div className="absolute -top-32 -left-32 w-80 h-80 rounded-full bg-cyan-600/20 blur-3xl pointer-events-none" />
          <div className="absolute -bottom-32 -right-32 w-80 h-80 rounded-full bg-purple-600/25 blur-3xl pointer-events-none" />

          {/* Top navigation row */}
          <div className="relative z-10 flex items-center justify-between">
            <button
              onClick={onBackToFeed}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-slate-900/80 hover:bg-slate-800 border border-slate-700/70 text-slate-300 text-xs font-semibold backdrop-blur-md transition"
              title="Kembali ke Beranda Feed"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Feed</span>
            </button>

            <div className="flex items-center gap-2">
              <span className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-cyan-950/80 border border-cyan-500/40 text-cyan-300 text-[11px] font-mono font-bold">
                <Sparkles className="w-3 h-3 text-cyan-400 animate-spin" />
                WebGL PBR 3D
              </span>
              <span className="px-2.5 py-1 rounded-full bg-slate-900/80 border border-slate-800 text-slate-300 text-[11px] font-mono font-bold">
                {userCredits} Cr
              </span>
            </div>
          </div>

          {/* Main Visual & Title Showcase */}
          <div className="relative z-10 my-auto py-6 flex flex-col items-center text-center max-w-lg mx-auto space-y-6">
            
            {/* Holographic Avatar Graphic Badge */}
            <div className="relative w-36 h-36 sm:w-44 sm:h-44 rounded-full p-1 bg-gradient-to-tr from-cyan-500 via-indigo-500 to-fuchsia-500 shadow-[0_0_50px_rgba(6,182,212,0.35)] animate-pulse">
              <div className="w-full h-full rounded-full bg-slate-950 overflow-hidden flex items-center justify-center relative">
                <img
                  src="https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=500&q=80"
                  alt="3D Universe Avatar Preview"
                  className="w-full h-full object-cover scale-110 opacity-90"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-slate-950/90 via-transparent to-transparent" />
                <div className="absolute bottom-2 px-2.5 py-0.5 rounded-full bg-cyan-500/30 border border-cyan-400 text-cyan-200 text-[10px] font-mono font-bold backdrop-blur-xs">
                  Spatial Matrix v2.4
                </div>
              </div>
            </div>

            {/* Typography Lockup matching the reference */}
            <div className="space-y-2">
              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-gradient-to-r from-blue-500/20 to-purple-500/20 border border-blue-400/30 text-cyan-300 text-xs font-bold tracking-wide">
                <Globe2 className="w-3.5 h-3.5 text-cyan-400" />
                ALLPHA UNIVERSE: 3D UNIVERSE
              </div>
              
              <h1 className="text-2xl sm:text-4xl font-black tracking-tight text-white leading-tight">
                A Shared Universe for <br />
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 via-blue-400 to-fuchsia-400">
                  Human and AI Potential
                </span>
              </h1>

              <p className="text-xs sm:text-sm text-slate-300 max-w-md mx-auto leading-relaxed">
                Jelajahi peradaban virtual 3D multidimensi. Temui avatar teman, kolaborasi bersama AI Agent cerdas, ikuti konser live stage, dan bangun masa depan ekonomi spatial.
              </p>
            </div>

            {/* Feature Highlights Grid */}
            <div className="grid grid-cols-2 gap-2.5 w-full text-left pt-1">
              <div className="p-3 rounded-2xl bg-slate-900/70 border border-slate-800 backdrop-blur-xs flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-cyan-500/20 text-cyan-400 shrink-0">
                  <Compass className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-white">6+ Dunia Virtual</h4>
                  <p className="text-[10px] text-slate-400">Crystal City hingga Mars</p>
                </div>
              </div>

              <div className="p-3 rounded-2xl bg-slate-900/70 border border-slate-800 backdrop-blur-xs flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-purple-500/20 text-purple-400 shrink-0">
                  <Bot className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-white">Human & AI Sinergi</h4>
                  <p className="text-[10px] text-slate-400">Interaksi & obrolan real-time</p>
                </div>
              </div>

              <div className="p-3 rounded-2xl bg-slate-900/70 border border-slate-800 backdrop-blur-xs flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-pink-500/20 text-pink-400 shrink-0">
                  <Radio className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-white">Live Stage Concert</h4>
                  <p className="text-[10px] text-slate-400">Audio spatial & talkshow</p>
                </div>
              </div>

              <div className="p-3 rounded-2xl bg-slate-900/70 border border-slate-800 backdrop-blur-xs flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-amber-500/20 text-amber-400 shrink-0">
                  <ShoppingBag className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-white">Pasar 3D & Avatar</h4>
                  <p className="text-[10px] text-slate-400">Kustomisasi rig & item</p>
                </div>
              </div>
            </div>
          </div>

          {/* Action CTAs at bottom */}
          <div className="relative z-10 w-full max-w-sm mx-auto flex flex-col gap-2.5 pt-4">
            <button
              onClick={() => setCurrentStep('HUB')}
              className="w-full py-3.5 px-6 rounded-2xl bg-gradient-to-r from-cyan-500 via-blue-600 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-white font-black text-sm shadow-[0_0_25px_rgba(6,182,212,0.4)] flex items-center justify-center gap-2 transition active:scale-95"
            >
              <span>Masuk ke Universe</span>
              <ChevronRight className="w-4 h-4" />
            </button>

            <button
              onClick={() => setCurrentStep('WORLDS')}
              className="w-full py-3 px-6 rounded-2xl bg-slate-900/80 hover:bg-slate-800 border border-slate-700/80 text-slate-200 font-bold text-xs flex items-center justify-center gap-1.5 transition"
            >
              <Compass className="w-3.5 h-3.5 text-cyan-400" />
              <span>Jelajahi Dulu (Daftar Dunia)</span>
            </button>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* SCREEN 2: UNIVERSE HUB (Pusat Semesta, Featured World, Kategori & Populer)  */}
      {/* ========================================================================= */}
      {currentStep === 'HUB' && (
        <div className="relative w-full h-full flex flex-col overflow-y-auto bg-slate-950">
          
          {/* Unified Sticky Header Bar - Prevents anything from getting covered or overlapping */}
          <header className="sticky top-0 z-40 bg-slate-950/95 backdrop-blur-md border-b border-slate-800/80 shadow-xl shrink-0">
            {/* Top row: Brand & Hub Title & Navigation Buttons */}
            <div className="px-4 py-3 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <button
                  onClick={() => setCurrentStep('SPLASH')}
                  className="p-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 transition shrink-0"
                  title="Kembali ke Layar Pembuka"
                >
                  <ArrowLeft className="w-4 h-4" />
                </button>
                <div className="min-w-0">
                  <h2 className="text-sm font-black text-white flex items-center gap-1.5 truncate">
                    <span>Universe Hub</span>
                    <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse shrink-0" />
                  </h2>
                  <p className="text-[10px] text-slate-400 truncate">Eksplorasi ekosistem dunia spatial</p>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => setCurrentStep('WORLDS')}
                  className="px-3 py-1.5 rounded-full bg-slate-900 hover:bg-slate-800 border border-slate-800 text-cyan-300 text-xs font-semibold flex items-center gap-1 transition"
                >
                  <Globe2 className="w-3.5 h-3.5" />
                  <span>Semua Dunia</span>
                </button>

                <button
                  onClick={onBackToFeed}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-full bg-slate-900 hover:bg-rose-950/50 border border-slate-800 hover:border-rose-800/50 text-slate-300 hover:text-rose-300 text-xs font-bold transition"
                  title="Kembali ke Beranda Feed"
                >
                  <X className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Feed</span>
                </button>
              </div>
            </div>

            {/* Quick Nav Chips: Galaxy, Worlds, Districts, Events */}
            <div className="px-4 pb-2.5 flex items-center gap-2 overflow-x-auto no-scrollbar">
              {[
                { id: 'Galaxy', icon: '🌌', label: 'Galaxy' },
                { id: 'Worlds', icon: '🪐', label: 'Worlds' },
                { id: 'Districts', icon: '🏙️', label: 'Districts' },
                { id: 'Events', icon: '📅', label: 'Events' },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => {
                    setHubNavTab(tab.id as any);
                    if (tab.id === 'Districts') {
                      setSelectedWorld(WORLDS_DATA[0]);
                      setCurrentStep('DISTRICT_MAP');
                    } else if (tab.id === 'Worlds') {
                      setCurrentStep('WORLDS');
                    }
                  }}
                  className={`px-3.5 py-1.5 rounded-full text-xs font-bold whitespace-nowrap transition flex items-center gap-1.5 ${
                    hubNavTab === tab.id
                      ? 'bg-cyan-600 text-white shadow-xs'
                      : 'bg-slate-900 border border-slate-800 text-slate-300 hover:bg-slate-800'
                  }`}
                >
                  <span>{tab.icon}</span>
                  <span>{tab.label}</span>
                </button>
              ))}
            </div>

            {/* Search Box integrated cleanly inside sticky header so it never overlaps or covers */}
            <div className="px-4 pb-3">
              <div className="relative">
                <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Cari dunia virtual, district, atau live stage..."
                  className="w-full bg-slate-900/90 border border-slate-800 pl-10 pr-4 py-2.5 rounded-2xl text-xs text-white placeholder-slate-500 outline-none focus:border-cyan-500 transition"
                />
              </div>
            </div>
          </header>

          {/* Main Content Area */}
          <div className="p-4 space-y-6 pb-24">
            
            {/* FEATURED WORLD HERO CARD: Crystal City */}
            <div className="relative rounded-3xl overflow-hidden border border-cyan-500/40 bg-gradient-to-br from-slate-900 to-indigo-950 p-5 shadow-2xl">
              <div 
                className="absolute inset-0 bg-cover bg-center opacity-25 mix-blend-screen pointer-events-none"
                style={{ backgroundImage: `url(${WORLDS_DATA[0].coverImage})` }}
              />
              <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/70 to-transparent" />

              <div className="relative z-10 space-y-3.5">
                <div className="flex items-center justify-between">
                  <span className="px-3 py-1 rounded-full bg-cyan-500/20 border border-cyan-400/50 text-cyan-300 text-[10px] font-mono font-bold tracking-wider uppercase flex items-center gap-1">
                    <Sparkles className="w-3 h-3 text-cyan-400" />
                    Featured World Spotlight
                  </span>
                  <div className="flex items-center gap-1.5 text-[11px] font-mono text-emerald-300 font-bold bg-emerald-950/60 px-2.5 py-0.5 rounded-full border border-emerald-500/30">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                    24.3K Online
                  </div>
                </div>

                <div>
                  <h3 className="text-xl sm:text-2xl font-black text-white">Crystal City</h3>
                  <p className="text-xs text-slate-300 line-clamp-2 mt-1">
                    {WORLDS_DATA[0].tagline}. Nikmati arsitektur kristal neoklasik, AI Plaza interaktif, dan arena Live Stage internasional.
                  </p>
                </div>

                <div className="flex items-center gap-4 text-xs text-slate-300 pt-1">
                  <span className="flex items-center gap-1 font-semibold">
                    <MapPin className="w-3.5 h-3.5 text-cyan-400" />
                    6 District Aktif
                  </span>
                  <span className="flex items-center gap-1 font-semibold">
                    <Radio className="w-3.5 h-3.5 text-rose-400" />
                    312 Event Live
                  </span>
                  <span className="flex items-center gap-1 font-semibold text-amber-300">
                    <Star className="w-3.5 h-3.5 fill-amber-300" />
                    4.9 (18.4K)
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2.5 pt-2">
                  <button
                    onClick={() => handleLaunchPortal(WORLDS_DATA[0], 'Central Hub')}
                    className="py-3 px-4 rounded-2xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-black text-xs flex items-center justify-center gap-1.5 shadow-[0_0_20px_rgba(6,182,212,0.4)] transition active:scale-95"
                  >
                    <Play className="w-3.5 h-3.5 fill-slate-950" />
                    <span>Masuk ke Dunia</span>
                  </button>

                  <button
                    onClick={() => {
                      setSelectedWorld(WORLDS_DATA[0]);
                      setCurrentStep('WORLD_DETAIL');
                    }}
                    className="py-3 px-4 rounded-2xl bg-slate-900/90 hover:bg-slate-800 border border-slate-700 text-slate-200 font-bold text-xs flex items-center justify-center gap-1.5 transition"
                  >
                    <span>Detail Dunia</span>
                    <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
                  </button>
                </div>
              </div>
            </div>

            {/* KATEGORI UNIVERSE (6 Interactive Tiles) */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-white flex items-center gap-1.5">
                  <span>Kategori Universe</span>
                </h3>
                <span className="text-[11px] text-slate-400">Tematik Dunia</span>
              </div>

              <div className="grid grid-cols-3 gap-2 text-center">
                {[
                  { name: 'Education', icon: GraduationCap, color: 'text-blue-400 bg-blue-500/10 border-blue-500/30', users: '4.2k' },
                  { name: 'Creator Hub', icon: Palette, color: 'text-pink-400 bg-pink-500/10 border-pink-500/30', users: '5.8k' },
                  { name: 'Business', icon: Briefcase, color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30', users: '3.1k' },
                  { name: 'Entertainment', icon: Gamepad2, color: 'text-purple-400 bg-purple-500/10 border-purple-500/30', users: '7.4k' },
                  { name: 'Nature', icon: Trees, color: 'text-teal-400 bg-teal-500/10 border-teal-500/30', users: '2.6k' },
                  { name: 'AI Innovation', icon: Cpu, color: 'text-amber-400 bg-amber-500/10 border-amber-500/30', users: '6.2k' },
                ].map((cat) => {
                  const Icon = cat.icon;
                  return (
                    <button
                      key={cat.name}
                      onClick={() => {
                        setActiveCategoryFilter(cat.name);
                        setCurrentStep('WORLDS');
                      }}
                      className="p-3 rounded-2xl bg-slate-900/80 border border-slate-800 hover:border-slate-700 flex flex-col items-center gap-1.5 transition active:scale-95"
                    >
                      <div className={`p-2.5 rounded-xl border ${cat.color}`}>
                        <Icon className="w-4 h-4" />
                      </div>
                      <span className="text-xs font-bold text-white leading-tight">{cat.name}</span>
                      <span className="text-[10px] text-slate-400 font-mono">{cat.users} aktif</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* DUNIA POPULER (Horizontal Carousel of Worlds) */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-white flex items-center gap-1.5">
                  <Flame className="w-4 h-4 text-orange-400" />
                  <span>Dunia Virtual Populer</span>
                </h3>
                <button
                  onClick={() => setCurrentStep('WORLDS')}
                  className="text-xs text-cyan-400 hover:underline font-semibold"
                >
                  Lihat Semua
                </button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {WORLDS_DATA.slice(0, 4).map((world) => (
                  <div
                    key={world.id}
                    onClick={() => {
                      setSelectedWorld(world);
                      setCurrentStep('WORLD_DETAIL');
                    }}
                    className="group relative rounded-2xl overflow-hidden bg-slate-900 border border-slate-800 hover:border-cyan-500/60 transition cursor-pointer p-3.5 flex gap-3 items-center"
                  >
                    <img
                      src={world.coverImage}
                      alt={world.name}
                      className="w-16 h-16 rounded-xl object-cover ring-1 ring-slate-700 shrink-0 group-hover:scale-105 transition"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-1">
                        <h4 className="text-xs font-bold text-white truncate">{world.name}</h4>
                        <span className="text-[10px] font-mono text-cyan-300 font-bold bg-slate-800 px-1.5 py-0.2 rounded shrink-0">
                          {world.onlineCount}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400 line-clamp-1 mt-0.5">{world.tagline}</p>
                      <div className="flex items-center gap-2 mt-1.5 text-[10px] text-slate-400">
                        <span className="px-1.5 py-0.2 rounded bg-slate-800 text-slate-300">
                          {world.category}
                        </span>
                        <span>•</span>
                        <span>{world.districtCount} District</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* QUICK FEATURES STRIP */}
            <div className="p-4 rounded-2xl bg-gradient-to-r from-blue-950/60 to-purple-950/60 border border-indigo-500/30 flex items-center justify-between gap-3 text-xs">
              <div className="flex items-center gap-2.5">
                <div className="p-2.5 rounded-xl bg-purple-500/20 text-purple-300 shrink-0">
                  <Palette className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="font-bold text-white">Kustomisasi Avatar 3D</h4>
                  <p className="text-[10px] text-slate-300">Ganti pakaian neon & animasi emote sebelum masuk</p>
                </div>
              </div>
              <button
                onClick={() => {
                  setSelectedWorld(WORLDS_DATA[0]);
                  handleLaunchPortal(WORLDS_DATA[0], 'Central Hub');
                }}
                className="px-3.5 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs shrink-0 transition"
              >
                Kustomisasi
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* SCREEN 3: PILIH DUNIA (Directory of Worlds with Filter Tabs & Search)       */}
      {/* ========================================================================= */}
      {currentStep === 'WORLDS' && (
        <div className="relative w-full h-full flex flex-col overflow-y-auto bg-slate-950">
          {/* Header */}
          <header className="sticky top-0 z-40 bg-slate-950/95 backdrop-blur-md border-b border-slate-800/80 shadow-xl shrink-0">
            <div className="px-4 py-3 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setCurrentStep('HUB')}
                  className="p-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 transition"
                  title="Kembali ke Universe Hub"
                >
                  <ArrowLeft className="w-4 h-4" />
                </button>
                <div>
                  <h2 className="text-sm font-black text-white">Pilih Dunia (Worlds Directory)</h2>
                  <p className="text-[10px] text-slate-400">Pilih ekosistem virtual untuk dijelajahi</p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => setCurrentStep('SPLASH')}
                  className="text-xs text-slate-400 hover:text-white px-2.5 py-1 rounded-full bg-slate-900 border border-slate-800"
                >
                  Onboarding
                </button>
                <button
                  onClick={onBackToFeed}
                  className="p-1.5 rounded-full bg-slate-900 text-slate-400 hover:text-white"
                  title="Kembali ke Feed"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Search & Filter Tabs inside sticky header */}
            <div className="px-4 pb-3 space-y-2.5">
              <div className="relative">
                <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Cari dunia virtual, metaverse atau district..."
                  className="w-full bg-slate-900/90 border border-slate-800 pl-10 pr-4 py-2.5 rounded-2xl text-xs text-white placeholder-slate-500 outline-none focus:border-cyan-500"
                />
              </div>

              <div className="flex items-center gap-2 overflow-x-auto no-scrollbar">
                {['Semua', 'Populer', 'Terbaru', 'Rekomendasi', 'Metropolitan', 'Cyberpunk', 'Space', 'Nature'].map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setActiveCategoryFilter(cat)}
                    className={`px-3 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap transition ${
                      activeCategoryFilter === cat
                        ? 'bg-cyan-600 text-white shadow-xs'
                        : 'bg-slate-900 border border-slate-800 text-slate-400 hover:bg-slate-800'
                    }`}
                  >
                    {cat}
                  </button>
                ))}
              </div>
            </div>
          </header>

          {/* Worlds Grid */}
          <div className="p-4 grid grid-cols-1 sm:grid-cols-2 gap-4 pb-24">
            {filteredWorlds.map((world) => (
              <div
                key={world.id}
                className="rounded-3xl overflow-hidden bg-slate-900 border border-slate-800 hover:border-slate-700 transition flex flex-col justify-between"
              >
                <div className="relative h-40 w-full overflow-hidden">
                  <img
                    src={world.coverImage}
                    alt={world.name}
                    className="w-full h-full object-cover"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/40 to-transparent" />
                  
                  <div className="absolute top-3 left-3 flex items-center gap-1.5">
                    <span className="px-2.5 py-0.5 rounded-full bg-slate-950/80 border border-slate-700 text-white text-[10px] font-semibold backdrop-blur-xs">
                      {world.category}
                    </span>
                  </div>

                  <div className="absolute top-3 right-3 flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-emerald-950/80 border border-emerald-500/40 text-emerald-300 text-[10px] font-mono font-bold backdrop-blur-xs">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    {world.onlineCount} Online
                  </div>

                  <div className="absolute bottom-3 left-3 right-3">
                    <h3 className="text-base font-black text-white">{world.name}</h3>
                    <p className="text-[11px] text-slate-300 line-clamp-1">{world.tagline}</p>
                  </div>
                </div>

                <div className="p-4 space-y-3">
                  <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">
                    {world.description}
                  </p>

                  <div className="flex items-center justify-between text-xs text-slate-400 pt-1 border-t border-slate-800">
                    <span className="flex items-center gap-1">
                      <MapPin className="w-3.5 h-3.5 text-cyan-400" />
                      {world.districtCount} District
                    </span>
                    <span className="flex items-center gap-1">
                      <Radio className="w-3.5 h-3.5 text-rose-400" />
                      {world.eventCount} Event
                    </span>
                    <span className="flex items-center gap-1 text-amber-300 font-bold">
                      <Star className="w-3.5 h-3.5 fill-amber-300" />
                      {world.rating}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 pt-1">
                    <button
                      onClick={() => {
                        setSelectedWorld(world);
                        setCurrentStep('WORLD_DETAIL');
                      }}
                      className="py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-bold text-xs transition"
                    >
                      Detail Dunia
                    </button>

                    <button
                      onClick={() => handleLaunchPortal(world, 'Central Hub')}
                      className="py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-black text-xs transition shadow-xs flex items-center justify-center gap-1"
                    >
                      <Play className="w-3 h-3 fill-slate-950" />
                      <span>Masuk</span>
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* SCREEN 4: DETAIL DUNIA (Hero Cover, Quick Stats, Tabs & Fitur Utama)      */}
      {/* ========================================================================= */}
      {currentStep === 'WORLD_DETAIL' && (
        <div className="relative w-full h-full flex flex-col overflow-y-auto bg-slate-950">
          
          {/* Hero Banner with Back Button */}
          <div className="relative h-64 sm:h-72 w-full shrink-0">
            <img
              src={selectedWorld.coverImage}
              alt={selectedWorld.name}
              className="w-full h-full object-cover"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/60 to-slate-950/30" />

            {/* Top row */}
            <div className="absolute top-4 left-4 right-4 flex items-center justify-between z-10">
              <button
                onClick={() => setCurrentStep('HUB')}
                className="p-2 rounded-full bg-slate-900/80 hover:bg-slate-800 text-white backdrop-blur-md transition border border-slate-700"
              >
                <ArrowLeft className="w-4 h-4" />
              </button>

              <div className="flex items-center gap-2">
                <span className="px-3 py-1 rounded-full bg-slate-900/80 border border-slate-700 text-cyan-300 text-xs font-mono font-bold backdrop-blur-md">
                  {selectedWorld.category}
                </span>
              </div>
            </div>

            {/* World Title & Badges */}
            <div className="absolute bottom-4 left-4 right-4 z-10 space-y-2">
              <div className="flex items-center gap-2">
                <span className="px-2.5 py-0.5 rounded-full bg-cyan-500/30 border border-cyan-400 text-cyan-200 text-[10px] font-bold">
                  Official Metaverse World
                </span>
                <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 text-[10px] font-mono font-bold">
                  24/7 Live
                </span>
              </div>

              <h1 className="text-2xl sm:text-3xl font-black text-white">{selectedWorld.name}</h1>
              <p className="text-xs text-slate-300">{selectedWorld.tagline}</p>
            </div>
          </div>

          {/* Quick Stats Grid */}
          <div className="p-4 grid grid-cols-4 gap-2 text-center border-b border-slate-800 bg-slate-900/50">
            <div className="p-2 rounded-xl bg-slate-900 border border-slate-800">
              <span className="text-[10px] text-slate-400 block">Online</span>
              <span className="text-xs font-mono font-bold text-emerald-400">{selectedWorld.onlineCount}</span>
            </div>
            <div className="p-2 rounded-xl bg-slate-900 border border-slate-800">
              <span className="text-[10px] text-slate-400 block">District</span>
              <span className="text-xs font-mono font-bold text-cyan-400">{selectedWorld.districtCount} Area</span>
            </div>
            <div className="p-2 rounded-xl bg-slate-900 border border-slate-800">
              <span className="text-[10px] text-slate-400 block">Event</span>
              <span className="text-xs font-mono font-bold text-rose-400">{selectedWorld.eventCount} Live</span>
            </div>
            <div className="p-2 rounded-xl bg-slate-900 border border-slate-800">
              <span className="text-[10px] text-slate-400 block">Rating</span>
              <span className="text-xs font-mono font-bold text-amber-300 flex items-center justify-center gap-0.5">
                <Star className="w-3 h-3 fill-amber-300" />
                {selectedWorld.rating}
              </span>
            </div>
          </div>

          {/* Tabs: Tentang | District | Event | Galeri */}
          <div className="px-4 pt-3 flex items-center gap-2 border-b border-slate-800">
            {(['Tentang', 'District', 'Event', 'Galeri'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setWorldDetailTab(tab)}
                className={`pb-2.5 px-3 text-xs font-bold transition border-b-2 ${
                  worldDetailTab === tab
                    ? 'border-cyan-400 text-cyan-300'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          <div className="p-4 space-y-5 pb-32">
            
            {worldDetailTab === 'Tentang' && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <h3 className="text-xs font-bold text-slate-300">Deskripsi Dunia:</h3>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    {selectedWorld.description}
                  </p>
                </div>

                {/* Fitur Utama Grid matching Screen 4 reference */}
                <div className="space-y-2">
                  <h3 className="text-xs font-bold text-slate-300">Fitur Utama di {selectedWorld.name}:</h3>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    {[
                      { name: 'Social Hub', desc: 'Interaksi & sapa avatar langsung', icon: Users, color: 'text-cyan-400' },
                      { name: 'Event Space', desc: 'Panggung live show 50k kapasitas', icon: Radio, color: 'text-rose-400' },
                      { name: '3D Marketplace', desc: 'Beli aset & fashion digital', icon: ShoppingBag, color: 'text-amber-400' },
                      { name: 'AI Plaza', desc: 'Konsultasi bot cerdas real-time', icon: Bot, color: 'text-blue-400' },
                      { name: 'Creator Hub', desc: 'Studio rekaman & galeri seni', icon: Palette, color: 'text-pink-400' },
                      { name: 'Live Stage', desc: 'Audio spatial & interaksi panggung', icon: Play, color: 'text-purple-400' },
                    ].map((feat) => {
                      const Icon = feat.icon;
                      return (
                        <div key={feat.name} className="p-3 rounded-2xl bg-slate-900 border border-slate-800 flex items-start gap-2.5">
                          <Icon className={`w-4 h-4 ${feat.color} shrink-0 mt-0.5`} />
                          <div>
                            <h4 className="font-bold text-white text-xs">{feat.name}</h4>
                            <p className="text-[10px] text-slate-400">{feat.desc}</p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-1.5 text-xs">
                  <h4 className="font-bold text-cyan-300">Spesifikasi Engine Rendering:</h4>
                  <p className="text-slate-400 text-[11px]">
                    Teknologi Three.js WebGL PBR dengan shader pencahayaan real-time, audio spatial 3D Web Audio API, serta sinkronisasi multi-avatar.
                  </p>
                </div>
              </div>
            )}

            {worldDetailTab === 'District' && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold text-slate-300">Daftar District di {selectedWorld.name}:</h3>
                  <button
                    onClick={() => setCurrentStep('DISTRICT_MAP')}
                    className="text-xs text-cyan-400 hover:underline font-semibold flex items-center gap-1"
                  >
                    <Compass className="w-3.5 h-3.5" />
                    <span>Lihat di Peta</span>
                  </button>
                </div>

                <div className="space-y-2">
                  {selectedWorld.districts.map((dist) => (
                    <div
                      key={dist.name}
                      className="p-3.5 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-between text-xs"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <h4 className="font-bold text-white">{dist.name}</h4>
                          <span className="text-[10px] font-mono text-cyan-300 bg-slate-800 px-1.5 py-0.2 rounded">
                            {dist.online}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-400 mt-0.5">{dist.sub}</p>
                      </div>

                      <button
                        onClick={() => handleLaunchPortal(selectedWorld, dist.name)}
                        className="px-3 py-1.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs shrink-0"
                      >
                        Teleport
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {worldDetailTab === 'Event' && (
              <div className="space-y-3">
                <h3 className="text-xs font-bold text-slate-300">Event Live Terjadwal:</h3>
                {[
                  { title: 'Konser Hologram AI: Luna Symphony', time: 'Hari ini • 20:00 WIB', loc: 'Live Stage Arena', host: '@luna_official' },
                  { title: 'AI Startup Pitching Day: 10 Finalist', time: 'Besok • 14:00 WIB', loc: 'Central Hub Auditorium', host: '@allpha_venture' },
                  { title: 'Pameran 3D Digital Fashion Runway', time: 'Sabtu • 19:30 WIB', loc: '3D Marketplace Avenue', host: '@metamode' },
                ].map((ev) => (
                  <div key={ev.title} className="p-3.5 rounded-2xl bg-slate-900 border border-slate-800 space-y-1.5 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded-full border border-rose-500/20">
                        {ev.time}
                      </span>
                      <span className="text-[11px] text-slate-400">{ev.loc}</span>
                    </div>
                    <h4 className="font-bold text-white text-sm">{ev.title}</h4>
                    <div className="flex items-center justify-between pt-1">
                      <span className="text-slate-400 text-[11px]">Host: {ev.host}</span>
                      <button
                        onClick={() => alert(`RSVP Event "${ev.title}" berhasil dicatat!`)}
                        className="px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-cyan-300 font-semibold text-[11px]"
                      >
                        Ikuti / RSVP
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {worldDetailTab === 'Galeri' && (
              <div className="grid grid-cols-2 gap-2">
                {[
                  'https://images.unsplash.com/photo-1518709268805-4e9042af9f23?auto=format&fit=crop&w=500&q=80',
                  'https://images.unsplash.com/photo-1508739773434-c26b3d09e071?auto=format&fit=crop&w=500&q=80',
                  'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=500&q=80',
                  'https://images.unsplash.com/photo-1614728894747-a83421e2b9c9?auto=format&fit=crop&w=500&q=80',
                ].map((imgUrl, i) => (
                  <div key={i} className="h-28 rounded-2xl overflow-hidden bg-slate-900">
                    <img src={imgUrl} alt="Gallery item" className="w-full h-full object-cover" />
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Floating Bottom Action Bar */}
          <div className="fixed bottom-0 left-0 right-0 z-40 bg-slate-950/95 backdrop-blur-md border-t border-slate-800 p-4 flex items-center gap-3">
            <button
              onClick={() => setCurrentStep('DISTRICT_MAP')}
              className="py-3 px-4 rounded-2xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 font-bold text-xs flex items-center justify-center gap-1.5 transition shrink-0"
            >
              <Compass className="w-4 h-4 text-cyan-400" />
              <span>Peta District</span>
            </button>

            <button
              onClick={() => handleLaunchPortal(selectedWorld, 'Central Hub')}
              className="flex-1 py-3 px-6 rounded-2xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-black text-xs flex items-center justify-center gap-2 shadow-[0_0_20px_rgba(6,182,212,0.4)] transition active:scale-95"
            >
              <Play className="w-4 h-4 fill-slate-950" />
              <span>Masuk ke {selectedWorld.name}</span>
            </button>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* SCREEN 5: PETA DISTRICT (Interactive Nodes Map & Teleport)                */}
      {/* ========================================================================= */}
      {currentStep === 'DISTRICT_MAP' && (
        <div className="relative w-full h-full flex flex-col overflow-y-auto bg-slate-950">
          {/* Header */}
          <header className="sticky top-0 z-30 bg-slate-950/90 backdrop-blur-md border-b border-slate-800/80 px-4 py-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setCurrentStep('WORLD_DETAIL')}
                className="p-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-300 transition"
              >
                <ArrowLeft className="w-4 h-4" />
              </button>
              <div>
                <h2 className="text-sm font-black text-white">Peta District: {selectedWorld.name}</h2>
                <p className="text-[10px] text-slate-400">Pilih landmark atau plaza untuk berteleportasi</p>
              </div>
            </div>

            <button
              onClick={() => handleLaunchPortal(selectedWorld, targetDistrict)}
              className="px-3.5 py-1.5 rounded-full bg-cyan-500 text-slate-950 font-black text-xs flex items-center gap-1 shadow-xs"
            >
              <Play className="w-3 h-3 fill-slate-950" />
              <span>Masuk 3D</span>
            </button>
          </header>

          {/* Interactive District Blueprint Grid */}
          <div className="p-4 space-y-4 pb-24">
            
            {/* Visual Floor Plan Nodes Container */}
            <div className="relative w-full h-72 sm:h-80 rounded-3xl bg-slate-900/90 border border-slate-800 overflow-hidden p-4 flex items-center justify-center">
              {/* Matrix radar grid bg */}
              <div className="absolute inset-0 bg-[radial-gradient(#06b6d4_1px,transparent_1px)] [background-size:24px_24px] opacity-20 pointer-events-none" />
              <div className="absolute w-44 h-44 rounded-full border border-cyan-500/20 animate-ping pointer-events-none" />
              <div className="absolute w-64 h-64 rounded-full border border-slate-700/50 pointer-events-none" />

              {/* District Node Pins */}
              <div className="relative w-full h-full flex flex-wrap items-center justify-around gap-2 p-2">
                {selectedWorld.districts.map((dist) => {
                  const isSelected = targetDistrict === dist.name;
                  return (
                    <button
                      key={dist.name}
                      onClick={() => setTargetDistrict(dist.name)}
                      className={`relative z-10 px-3 py-2 rounded-2xl border text-left transition transform ${
                        isSelected
                          ? 'bg-cyan-500 text-slate-950 border-cyan-300 scale-105 shadow-[0_0_20px_rgba(6,182,212,0.6)] font-black'
                          : 'bg-slate-950/85 text-white border-slate-700/80 hover:border-cyan-500/50'
                      }`}
                    >
                      <div className="flex items-center gap-1.5">
                        <span className={`w-2 h-2 rounded-full ${isSelected ? 'bg-slate-950' : 'bg-cyan-400 animate-pulse'}`} />
                        <span className="text-xs font-bold">{dist.name}</span>
                      </div>
                      <span className={`text-[10px] block mt-0.5 ${isSelected ? 'text-slate-900 font-mono font-bold' : 'text-slate-400 font-mono'}`}>
                        {dist.online}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Selected District Details Card */}
            {(() => {
              const activeDist = selectedWorld.districts.find(d => d.name === targetDistrict) || selectedWorld.districts[0];
              return (
                <div className="p-4 rounded-3xl bg-slate-900 border border-cyan-500/40 space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-[10px] text-cyan-300 font-mono uppercase tracking-wider block">Target Teleportasi:</span>
                      <h3 className="text-base font-black text-white">{activeDist.name}</h3>
                    </div>
                    <span className="px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-300 font-mono text-xs font-bold">
                      {activeDist.online} Aktif
                    </span>
                  </div>

                  <p className="text-xs text-slate-300">
                    {activeDist.sub}. Koordinat spasial: X={activeDist.x}, Z={activeDist.z}.
                  </p>

                  <div className="grid grid-cols-2 gap-2.5 pt-2">
                    <button
                      onClick={() => handleLaunchPortal(selectedWorld, activeDist.name)}
                      className="py-3 px-4 rounded-2xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-black text-xs flex items-center justify-center gap-1.5 shadow-[0_0_20px_rgba(6,182,212,0.4)] transition"
                    >
                      <Play className="w-3.5 h-3.5 fill-slate-950" />
                      <span>Teleport ke {activeDist.name}</span>
                    </button>

                    <button
                      onClick={() => setCurrentStep('HUB')}
                      className="py-3 px-4 rounded-2xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold text-xs"
                    >
                      Pilih Dunia Lain
                    </button>
                  </div>
                </div>
              );
            })()}

            {/* District List Directory */}
            <div className="space-y-2 pt-2">
              <h4 className="text-xs font-bold text-slate-300">Semua Landmark di {selectedWorld.name}:</h4>
              <div className="space-y-2">
                {selectedWorld.districts.map((d) => (
                  <div
                    key={d.name}
                    onClick={() => setTargetDistrict(d.name)}
                    className={`p-3 rounded-2xl border transition cursor-pointer flex items-center justify-between text-xs ${
                      targetDistrict === d.name ? 'bg-slate-900 border-cyan-500' : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div>
                      <h5 className="font-bold text-white">{d.name}</h5>
                      <p className="text-[11px] text-slate-400">{d.sub}</p>
                    </div>
                    <span className="text-[10px] font-mono text-cyan-300 font-bold">
                      {d.online}
                    </span>
                  </div>
                ))}
              </div>
            </div>

          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* SCREEN 6: MASUK KE DUNIA (Portal Teleport Hyperspace Loading Screen)       */}
      {/* ========================================================================= */}
      {currentStep === 'PORTAL_LOADING' && (
        <div className="relative w-full h-full flex flex-col justify-between items-center p-6 sm:p-10 bg-slate-950 text-center overflow-hidden">
          
          {/* Hyperspace Vortex Backdrop */}
          <div className="absolute inset-0 pointer-events-none bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-cyan-900/40 via-slate-950 to-slate-950" />
          
          {/* Top header status */}
          <div className="relative z-10 w-full flex items-center justify-between">
            <span className="text-xs font-mono text-cyan-400 font-bold tracking-wider">
              QUANTUM TELEPORT GATE
            </span>
            <span className="text-xs font-mono text-slate-400">
              Target: {selectedWorld.name} • {targetDistrict}
            </span>
          </div>

          {/* Central Rotating Portal Graphic with Progress Percentage */}
          <div className="relative z-10 my-auto flex flex-col items-center space-y-6">
            
            <div className="relative w-44 h-44 sm:w-56 sm:h-56 flex items-center justify-center">
              {/* Outer spinning ring */}
              <div className="absolute inset-0 rounded-full border-2 border-dashed border-cyan-400 animate-spin [animation-duration:8s]" />
              {/* Counter-spinning ring */}
              <div className="absolute inset-2 rounded-full border-2 border-dotted border-purple-400 animate-spin [animation-duration:12s] [animation-direction:reverse]" />
              {/* Glow core */}
              <div className="absolute inset-6 rounded-full bg-gradient-to-tr from-cyan-500 via-blue-600 to-fuchsia-600 blur-xl opacity-50 animate-pulse" />
              
              {/* Center progress percentage */}
              <div className="relative z-10 flex flex-col items-center">
                <span className="text-3xl sm:text-4xl font-black font-mono text-white tracking-tight">
                  {loadingProgress}%
                </span>
                <span className="text-[10px] font-mono text-cyan-300 uppercase tracking-widest mt-1">
                  Synchronizing
                </span>
              </div>
            </div>

            <div className="space-y-1.5 max-w-sm">
              <h3 className="text-lg font-black text-white">Menuju {selectedWorld.name}...</h3>
              <p className="text-xs text-slate-400">
                Memuat distrik {targetDistrict}, menginisialisasi avatar rig 3D, dan audio spatial.
              </p>
            </div>

            {/* Linear Progress Bar */}
            <div className="w-64 sm:w-80 h-2 bg-slate-900 rounded-full overflow-hidden border border-slate-800">
              <div
                className="h-full bg-gradient-to-r from-cyan-400 to-indigo-500 transition-all duration-200"
                style={{ width: `${loadingProgress}%` }}
              />
            </div>
          </div>

          {/* Tips Carousel & Immediate Entry Skip Button */}
          <div className="relative z-10 w-full max-w-md space-y-3">
            <div className="p-3 rounded-2xl bg-slate-900/80 border border-slate-800 text-xs text-slate-300 min-h-[50px] flex items-center justify-center">
              <p className="italic transition-all duration-300">
                {PORTAL_TIPS[loadingTipIndex]}
              </p>
            </div>

            <div className="flex items-center justify-between gap-3">
              <button
                onClick={() => setCurrentStep('WORLD_DETAIL')}
                className="text-xs text-slate-400 hover:text-white"
              >
                Batalkan
              </button>

              <button
                onClick={() => setCurrentStep('IN_WORLD')}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-cyan-300 font-bold text-xs"
              >
                Masuk Sekarang (Lewati) →
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

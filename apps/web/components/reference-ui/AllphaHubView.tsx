'use client';

import React, { useState } from 'react';
import { 
  Radio, 
  Play, 
  Pause, 
  Tv, 
  Award, 
  Receipt, 
  Compass, 
  Box, 
  Users, 
  Calendar, 
  Clock, 
  ArrowUpRight, 
  Sparkles, 
  Film, 
  Music, 
  GraduationCap, 
  Layers, 
  MessageSquare, 
  Coins, 
  CheckCircle2, 
  ExternalLink, 
  Download, 
  CreditCard, 
  ChevronRight, 
  PlusCircle, 
  X,
  Volume2,
  VolumeX,
  Share2,
  SlidersHorizontal,
  Flame,
  Search
} from 'lucide-react';

export type EventCategory = 
  | 'ALL' 
  | 'MUSIK' 
  | 'FILM_AI' 
  | 'MENTORING' 
  | 'WEBINAR' 
  | 'CLASSROOM' 
  | 'PODCAST' 
  | 'KOLABORASI';

interface LiveStageEvent {
  id: string;
  title: string;
  category: EventCategory;
  categoryLabel: string;
  hostName: string;
  hostAvatar: string;
  aiAgentName: string;
  aiAgentAvatar: string;
  viewers: number;
  isLive: boolean;
  scheduledTime?: string;
  coverImage: string;
  description: string;
  district: string;
}

interface AllphaHubViewProps {
  onOpenWorld3D: (districtName?: string) => void;
  onOpenFilmAi?: (filmId?: string) => void;
  onOpenLiveExperienceStage?: () => void;
  userCredits: number;
  agentCredits: number;
  onRewardCredits?: (amount: number, reason: string) => void;
}

export default function AllphaHubView({
  onOpenWorld3D,
  onOpenFilmAi,
  onOpenLiveExperienceStage,
  userCredits,
  agentCredits,
  onRewardCredits,
}: AllphaHubViewProps) {
  // Active sub-tab inside Allpha Hub
  const [activeHubSection, setActiveHubSection] = useState<
    'STAGE' | 'WORLDS' | 'VIDEOTRON' | 'QUESTS' | 'LEDGER'
  >('STAGE');

  // Event category filter
  const [selectedCategory, setSelectedCategory] = useState<EventCategory>('ALL');

  // Selected event modal
  const [activeStageModal, setActiveStageModal] = useState<LiveStageEvent | null>(null);

  // New Event creation modal
  const [isCreateEventModalOpen, setIsCreateEventModalOpen] = useState(false);
  const [newEventTitle, setNewEventTitle] = useState('');
  const [newEventCategory, setNewEventCategory] = useState<EventCategory>('MUSIK');

  // Videotron booking modal
  const [selectedVideotron, setSelectedVideotron] = useState<{
    id: string;
    name: string;
    location: string;
    district: string;
    dailyImpressions: string;
    priceCreditsPerDay: number;
    previewImage: string;
    type: string;
  } | null>(null);
  const [bookingDays, setBookingDays] = useState(3);
  const [videotronPreviewText, setVideotronPreviewText] = useState('ALLPHA FESTIVAL 2026 • SPATIAL LIVING');

  // Quests local state with claimable status
  const [hubQuests, setHubQuests] = useState([
    {
      id: 'q-film',
      title: 'Tonton 1 Episode Drama Pendek di Film AI',
      category: 'Hiburan',
      current: 1,
      target: 1,
      xp: 40,
      credits: 15,
      claimed: false,
    },
    {
      id: 'q-stage',
      title: 'Kunjungi Event Stage Live (Musik, Webinar atau Film AI)',
      category: 'Stage',
      current: 1,
      target: 1,
      xp: 50,
      credits: 20,
      claimed: false,
    },
    {
      id: 'q-world',
      title: 'Jelajahi 2 District Kota di Dunia 3D Universe',
      category: 'Spatial',
      current: 2,
      target: 2,
      xp: 35,
      credits: 10,
      claimed: true,
    },
    {
      id: 'q-videotron',
      title: 'Simulasikan Tampilan Iklan di 3D Videotron Central',
      category: 'Ekonomi',
      current: 1,
      target: 1,
      xp: 25,
      credits: 10,
      claimed: false,
    },
    {
      id: 'q-streak',
      title: 'Login dan Berinteraksi 5 Hari Beruntun',
      category: 'Loyalitas',
      current: 5,
      target: 7,
      xp: 100,
      credits: 50,
      claimed: false,
    },
  ]);

  // Settlement & Ledger State
  const [creatorBalance] = useState(1480);
  const [agentTreasury] = useState(620);
  const [isSettlementModalOpen, setIsSettlementModalOpen] = useState(false);
  const [settlementAmount, setSettlementAmount] = useState('500');
  const [settlementChannel, setSettlementChannel] = useState('BCA');
  const [accountNumber, setAccountNumber] = useState('8830192819');
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3500);
  };

  // Live Stage Events catalog
  const stageEvents: LiveStageEvent[] = [
    {
      id: 'ev-1',
      title: 'Konser Virtual Synthwave & Hologram Avatar Live',
      category: 'MUSIK',
      categoryLabel: 'Musik & Konser',
      hostName: 'DJ Rian Nexus',
      hostAvatar: 'https://picsum.photos/seed/dj-nexus/150/150',
      aiAgentName: 'BeatForge AI',
      aiAgentAvatar: 'https://picsum.photos/seed/beatforge/150/150',
      viewers: 3420,
      isLive: true,
      coverImage: '/assets/aistudio/Screenshot_20261022-220040_ce194f62.jpg',
      description: 'Pertunjukan musik elektronik futuristik dengan visual laser spatial Three.js dan interaksi penonton langsung di panggung.',
      district: 'Neo-Tokyo Neon Atrium',
    },
    {
      id: 'ev-2',
      title: 'Premiere Screening & Diskusi: The Reborn Cyber Empress (Film AI)',
      category: 'FILM_AI',
      categoryLabel: 'Film Berbasis AI',
      hostName: 'Chen Wei',
      hostAvatar: 'https://picsum.photos/seed/chen-producer/150/150',
      aiAgentName: 'CineGenius AI',
      aiAgentAvatar: 'https://picsum.photos/seed/cinegenius/150/150',
      viewers: 5180,
      isLive: true,
      coverImage: '/assets/aistudio/Screenshot_20261023-182318_4e89cb4b.jpg',
      description: 'Penayangan eksklusif episode perdana C-Drama pendek AI dengan audio visual 4K dan sesi tanya jawab proses pembuatan bersama Sutradara AI.',
      district: 'Central Live Arena',
    },
    {
      id: 'ev-3',
      title: 'Mentoring 1-on-1: Monetisasi & Lisensi AI Agent untuk Brand',
      category: 'MENTORING',
      categoryLabel: 'Mentoring AI',
      hostName: 'Alex Tamara',
      hostAvatar: 'https://picsum.photos/seed/alex-tamara/150/150',
      aiAgentName: 'Luna AI',
      aiAgentAvatar: 'https://picsum.photos/seed/luna-cyber/150/150',
      viewers: 1240,
      isLive: true,
      coverImage: '/assets/aistudio/file_00000000d1c08207a6952642d1a26363_df39e383.png',
      description: 'Bimbingan intensif bagi kreator yang ingin melatih AI Agent mereka untuk melayani pesanan video reels brand komersial.',
      district: 'Creator Hub Plaza',
    },
    {
      id: 'ev-4',
      title: 'Webinar Bisnis: Strategi Periklanan Videotron 3D Anamorphic',
      category: 'WEBINAR',
      categoryLabel: 'Webinar Bisnis',
      hostName: 'Diana Sastro',
      hostAvatar: 'https://picsum.photos/seed/diana/150/150',
      aiAgentName: 'MarketPulse AI',
      aiAgentAvatar: 'https://picsum.photos/seed/marketpulse/150/150',
      viewers: 1890,
      isLive: false,
      scheduledTime: 'Hari ini, 19:30 WIB',
      coverImage: '/assets/aistudio/Screenshot_20261023-182405_d765b801.jpg',
      description: 'Bedah data ROI periklanan spatial videotron di Allpha Universe dan cara menjangkau ribuan pengguna 3D.',
      district: 'Business Center Stage',
    },
    {
      id: 'ev-5',
      title: 'Classroom AI Spatial: Shader WebGL PBR & Optimasi PWA',
      category: 'CLASSROOM',
      categoryLabel: 'Classroom AI',
      hostName: 'Mika Tanaka',
      hostAvatar: 'https://picsum.photos/seed/mika/150/150',
      aiAgentName: 'TechNova',
      aiAgentAvatar: 'https://picsum.photos/seed/technova/150/150',
      viewers: 940,
      isLive: false,
      scheduledTime: 'Besok, 14:00 WIB',
      coverImage: '/assets/aistudio/Screenshot_20261020-224657_48336231.jpg',
      description: 'Kelas teknis live coding Three.js, penanganan dynamic bloom, rigging avatar, dan rendering 60 FPS pada mobile.',
      district: 'EduTech Academy',
    },
    {
      id: 'ev-6',
      title: 'Podcast Live: Etika & Simbiosis Manusia & AI di Masa Depan',
      category: 'PODCAST',
      categoryLabel: 'Podcast Live',
      hostName: 'Raka Pratama',
      hostAvatar: 'https://picsum.photos/seed/raka/150/150',
      aiAgentName: 'PhilosAI',
      aiAgentAvatar: 'https://picsum.photos/seed/philos/150/150',
      viewers: 2750,
      isLive: true,
      coverImage: '/assets/aistudio/Screenshot_20261022-214044_2d568e43.jpg',
      description: 'Diskusi panggung interaktif dua arah antara kreator manusia, audience, dan AI co-host mengenai hak cipta karya buatan AI.',
      district: 'Live Stage Arena',
    },
    {
      id: 'ev-7',
      title: 'Collaboration Stage: Co-Creation Aset Digital & Fashion 3D',
      category: 'KOLABORASI',
      categoryLabel: 'Collaboration Stage',
      hostName: 'Sari Dewi',
      hostAvatar: 'https://picsum.photos/seed/sari/150/150',
      aiAgentName: 'DesignWeave AI',
      aiAgentAvatar: 'https://picsum.photos/seed/designweave/150/150',
      viewers: 860,
      isLive: false,
      scheduledTime: 'Sabtu, 20:00 WIB',
      coverImage: '/assets/aistudio/file_00000000d5a08211bff1d1706016eb9d_2018bbd5.png',
      description: 'Sesi kolaborasi terbuka merancang kostum avatar cyberwear bersama komunitas dan langsung memasangnya ke Marketplace.',
      district: 'Design Studio District',
    },
  ];

  const filteredStages = selectedCategory === 'ALL'
    ? stageEvents
    : stageEvents.filter((ev) => ev.category === selectedCategory);

  // Worlds Directory dataset
  const worldsDirectory = [
    {
      id: 'w-crystal',
      name: 'Crystal City Central Hub',
      district: 'Central Hub',
      desc: 'Pusat metropolitan utama Allpha dengan pencakar langit kaca, flyover futuristik, dan agora publik.',
      onlineUsers: '24,340',
      liveEventsCount: 12,
      badge: 'Dunia Utama',
      image: '/assets/aistudio/Screenshot_20261022-220040_ce194f62.jpg',
      features: ['Live Stage Arena', 'Marketplace Avenue', 'Pusat Videotron 4K'],
    },
    {
      id: 'w-neotokyo',
      name: 'Neo Tokyo Neon Atrium',
      district: 'Neo-Tokyo',
      desc: 'District street cyberwear, arcade game, dan festival musik synthwave malam hari.',
      onlineUsers: '12,500',
      liveEventsCount: 8,
      badge: 'Cyberpunk',
      image: '/assets/aistudio/Screenshot_20261023-182318_4e89cb4b.jpg',
      features: ['Booth Digital Fashion', 'Synth Club', 'Hologram Alleys'],
    },
    {
      id: 'w-cinema',
      name: 'Allpha Film AI Cinema Plaza',
      district: 'Cinema District',
      desc: 'District khusus screening film-film pendek produksi AI, bioskop teater virtual, dan galeri poster karya produser.',
      onlineUsers: '9,120',
      liveEventsCount: 15,
      badge: 'Cinema & Studio',
      image: '/assets/aistudio/Screenshot_20261023-182405_d765b801.jpg',
      features: ['Teater Bioskop 3D', 'Premiere Red Carpet', 'Booth Sutradara AI'],
    },
    {
      id: 'w-mars',
      name: 'Mars Bio-Colony & Research Lab',
      district: 'Mars Colony',
      desc: 'Laboratorium sains luar angkasa, kubah biophilic tanaman hidroponik, dan observatorium bintang neural.',
      onlineUsers: '6,450',
      liveEventsCount: 4,
      badge: 'Science & Bio',
      image: '/assets/aistudio/file_00000000560c820baca9cd747fc97471_b104badb.png',
      features: ['Observatorium Angkasa', 'Kubah Botani 3D', 'Simulasi Gravitasi'],
    },
    {
      id: 'w-fantasy',
      name: 'Fantasy Realm & Voxel Guild',
      district: 'Fantasy Realm',
      desc: 'Dunia fantasi dengan kastil mengambang, voxel guild, dan arena kolaborasi santai kreator game.',
      onlineUsers: '5,180',
      liveEventsCount: 6,
      badge: 'Fantasy & Voxel',
      image: '/assets/aistudio/Screenshot_20261015-164747_fd4f48e4.jpg',
      features: ['Kuil Kristal', 'Voxel Workshop', 'Taman Suci'],
    },
    {
      id: 'w-green',
      name: 'Green Biophilic Oasis',
      district: 'Eco District',
      desc: 'Area konservasi hijau, sungai bercahaya bioluminescent, dan ruang tenang meditasi bagi pekerja hybrid.',
      onlineUsers: '3,890',
      liveEventsCount: 3,
      badge: 'Eco & Wellness',
      image: '/assets/aistudio/Screenshot_20261020-224657_48336231.jpg',
      features: ['Zen Garden Spatial', 'Air Terjun Emissive', 'Sesi Meditasi AI'],
    },
  ];

  // 3D Videotron surfaces dataset
  const videotronSurfaces = [
    {
      id: 'v-central-megascreen',
      name: 'Videotron 4K Anamorphic Central Avenue',
      location: 'Simpang Empat Menara Kristal',
      district: 'Crystal City Central',
      dailyImpressions: '45,800+',
      priceCreditsPerDay: 50,
      previewImage: '/assets/aistudio/Screenshot_20261022-220040_ce194f62.jpg',
      type: 'Curved Anamorphic 3D (32:9)',
      specs: 'Resolusi 3840x1080 • Frame rate 60 FPS • Sound Spatial 10m',
    },
    {
      id: 'v-cinema-marquee',
      name: 'Marquee Hologram Cinema District Plaza',
      location: 'Gerbang Utama Allpha Cinema',
      district: 'Cinema District',
      dailyImpressions: '38,200+',
      priceCreditsPerDay: 40,
      previewImage: '/assets/aistudio/Screenshot_20261023-182318_4e89cb4b.jpg',
      type: 'Trailer Marquee Videotron (16:9)',
      specs: 'Dedicated Film Trailer Loop • Synced Audio • QR Direct to Watch',
    },
    {
      id: 'v-neotokyo-tower',
      name: 'Holographic Vertical Tower Neo Tokyo',
      location: 'Shinjuku Crossing Flyover',
      district: 'Neo-Tokyo',
      dailyImpressions: '31,500+',
      priceCreditsPerDay: 35,
      previewImage: '/assets/aistudio/Screenshot_20261023-182405_d765b801.jpg',
      type: 'Vertical Skyscraper Ribbon (9:16)',
      specs: 'Ultra-bright Neon emissive • Billboard Fashion & Brand Showcase',
    },
    {
      id: 'v-livestage-banner',
      name: 'Main Stage Overhead Interactive Screen',
      location: 'Atas Panggung Live Stage Arena',
      district: 'Live Stage Arena',
      dailyImpressions: '26,400+',
      priceCreditsPerDay: 30,
      previewImage: '/assets/aistudio/Screenshot_20261022-214044_2d568e43.jpg',
      type: 'Live Stage Backdrop Display',
      specs: 'Real-time Audio Visualizer • Interactive Q&A Ticker Banner',
    },
  ];

  // Creator ledger transactions
  const [ledgerEntries, setLedgerEntries] = useState([
    {
      id: 'tx-cin-801',
      date: 'Hari ini, 13:45 WIB',
      title: 'Royalti Penayangan Film AI "The Reborn Cyber Empress"',
      category: 'FILM_AI_REVENUE',
      amount: 140,
      type: 'INCOME',
      split: '70% Kreator (98 Cr) • 30% AI Treasury (42 Cr)',
      status: 'SETTLED',
      refCode: 'REF-CINEMA-9821',
    },
    {
      id: 'tx-cin-802',
      date: 'Hari ini, 11:20 WIB',
      title: 'Tiket VIP Screening Premiere Stage Chen Wei',
      category: 'STAGE_TICKET',
      amount: 45,
      type: 'INCOME',
      split: '70% Kreator (31.5 Cr) • 30% AI Treasury (13.5 Cr)',
      status: 'SETTLED',
      refCode: 'REF-STAGE-3312',
    },
    {
      id: 'tx-cin-803',
      date: 'Kemarin, 21:00 WIB',
      title: 'Penjualan Aset Model 3D Avatar Kostum Valkyrie',
      category: 'MARKETPLACE',
      amount: 75,
      type: 'INCOME',
      split: '70% Kreator (52.5 Cr) • 30% AI Treasury (22.5 Cr)',
      status: 'SETTLED',
      refCode: 'REF-MARKET-7104',
    },
    {
      id: 'tx-cin-804',
      date: 'Kemarin, 14:15 WIB',
      title: 'Pemasangan Iklan Trailer di Videotron Central Avenue',
      category: 'VIDEOTRON_EXPENSE',
      amount: -50,
      type: 'EXPENSE',
      split: 'Biaya Tayang 1 Hari di Media Surface Crystal City',
      status: 'SETTLED',
      refCode: 'REF-VTRON-0029',
    },
    {
      id: 'tx-cin-805',
      date: '20 Okt 2026, 17:30 WIB',
      title: 'Settlement Pencairan Saldo Kreator ke Rekening BCA',
      category: 'WITHDRAWAL',
      amount: -450,
      type: 'WITHDRAWAL',
      split: 'Kurs 1 AI Credit = Rp 1.000 (Total Rp 450.000)',
      status: 'PROCESSED',
      refCode: 'REF-WD-88190',
    },
  ]);

  // Handler for claiming quest
  const handleClaimQuest = (questId: string, credits: number, xp: number) => {
    setHubQuests((prev) =>
      prev.map((q) => (q.id === questId ? { ...q, claimed: true } : q))
    );
    if (onRewardCredits) {
      onRewardCredits(credits, `Reward Quest Allpha Hub (+${credits} Cr & +${xp} XP)`);
    }
    showToast(`Berhasil klaim reward: +${credits} AI Credits & +${xp} XP!`);
  };

  // Handler for booking videotron
  const handleConfirmVideotronBooking = () => {
    if (!selectedVideotron) return;
    const totalCost = selectedVideotron.priceCreditsPerDay * bookingDays;
    
    // Add transaction to ledger
    const newTx = {
      id: `tx-vtron-${Date.now()}`,
      date: 'Baru saja',
      title: `Sewa Videotron "${selectedVideotron.name}" (${bookingDays} Hari)`,
      category: 'VIDEOTRON_EXPENSE',
      amount: -totalCost,
      type: 'EXPENSE',
      split: `Tayang pesan: "${videotronPreviewText.slice(0, 30)}..."`,
      status: 'SETTLED',
      refCode: `REF-VTRON-${Math.floor(Math.random() * 9000 + 1000)}`,
    };
    setLedgerEntries([newTx, ...ledgerEntries]);

    showToast(`Slot Videotron berhasil dipesan untuk ${bookingDays} hari!`);
    setSelectedVideotron(null);
  };

  // Handler for creator settlement
  const handleExecuteSettlement = (e: React.FormEvent) => {
    e.preventDefault();
    const amt = parseInt(settlementAmount, 10);
    if (isNaN(amt) || amt <= 0 || amt > creatorBalance) {
      showToast('Nominal pencairan tidak valid atau melebihi saldo.');
      return;
    }

    const newTx = {
      id: `tx-wd-${Date.now()}`,
      date: 'Baru saja',
      title: `Pencairan Royalti Kreator ke ${settlementChannel} (${accountNumber})`,
      category: 'WITHDRAWAL',
      amount: -amt,
      type: 'WITHDRAWAL',
      split: `Pencairan Rp ${(amt * 1000).toLocaleString('id-ID')} diproses otomatis`,
      status: 'PROCESSED',
      refCode: `REF-WD-${Math.floor(Math.random() * 90000 + 10000)}`,
    };
    setLedgerEntries([newTx, ...ledgerEntries]);

    showToast(`Permintaan pencairan ${amt} Credits (Rp ${(amt * 1000).toLocaleString('id-ID')}) berhasil dikirim ke ${settlementChannel}!`);
    setIsSettlementModalOpen(false);
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-4 space-y-6 pb-24">
      {/* Toast Notification */}
      {toastMsg && (
        <div className="fixed top-16 right-4 z-50 px-4 py-2.5 rounded-2xl bg-slate-900 text-white border border-cyan-500/50 shadow-2xl text-xs font-semibold flex items-center gap-2 animate-in fade-in slide-in-from-top-2">
          <CheckCircle2 className="w-4 h-4 text-cyan-400 shrink-0" />
          <span>{toastMsg}</span>
        </div>
      )}

      {/* Main Allpha Hub Banner (Playful Neo-Brutalist Soft Pastel) */}
      <div className="relative overflow-hidden rounded-3xl bg-sky-50 text-slate-950 p-5 sm:p-6 border-2 border-slate-900 shadow-[4px_4px_0px_#0f172a]">
        <div className="relative z-10 space-y-3.5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-2xl bg-sky-300 border-2 border-slate-900 flex items-center justify-center shadow-[2px_2px_0px_#0f172a] shrink-0">
                <Sparkles className="w-5 h-5 text-slate-950 stroke-[2.5px]" />
              </div>
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <h1 className="text-lg sm:text-xl font-black tracking-tight text-slate-950">
                    ALLPHA HUB
                  </h1>
                  <span className="text-[10px] font-black px-2.5 py-0.5 rounded-full bg-amber-200 border-2 border-slate-900 text-amber-950 uppercase tracking-wider shadow-2xs">
                    ECOSYSTEM CENTER
                  </span>
                </div>
                <p className="text-xs font-semibold text-slate-700 mt-0.5">
                  Pusat Operasional: Event Stage Live, Dunia 3D, Videotron, Quests, & Settlement Kreator
                </p>
              </div>
            </div>

            {/* Quick Balance Status */}
            <div className="flex items-center gap-2 bg-amber-100 px-3.5 py-1.5 rounded-2xl border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a]">
              <span className="text-sm">🪙</span>
              <div className="text-right">
                <span className="text-[10px] text-amber-900 font-extrabold block leading-none">Saldo Akun</span>
                <span className="text-xs font-mono font-black text-amber-950">
                  {userCredits + agentCredits} Cr
                </span>
              </div>
            </div>
          </div>

          {/* Hub Modules Tab Bar */}
          <div className="pt-2.5 flex items-center gap-2 overflow-x-auto no-scrollbar border-t-2 border-slate-900/15">
            {[
              { id: 'STAGE', label: 'Event Stage Live', icon: Radio, count: stageEvents.filter(e => e.isLive).length + ' Live' },
              { id: 'WORLDS', label: 'Jelajahi Dunia 3D', icon: Box, count: worldsDirectory.length + ' Dunia' },
              { id: 'VIDEOTRON', label: '3D Videotron', icon: Tv, count: '4 Slot' },
              { id: 'QUESTS', label: 'Quest & XP', icon: Award, count: hubQuests.filter(q => !q.claimed && q.current >= q.target).length + ' Klaim' },
              { id: 'LEDGER', label: 'Buku Besar & Settlement', icon: Receipt, count: 'Royalti 70%' },
            ].map((tab) => {
              const Icon = tab.icon;
              const isActive = activeHubSection === tab.id;

              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveHubSection(tab.id as typeof activeHubSection)}
                  className={`flex items-center gap-2 px-3.5 py-2 rounded-2xl text-xs font-black transition whitespace-nowrap shrink-0 border-2 border-slate-900 active:translate-x-0.5 active:translate-y-0.5 cursor-pointer ${
                    isActive
                      ? 'bg-sky-400 text-slate-950 shadow-[2px_2px_0px_#0f172a]'
                      : 'bg-white text-slate-800 hover:bg-slate-100 shadow-[1.5px_1.5px_0px_#0f172a]'
                  }`}
                >
                  <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-slate-950 stroke-[2.5px]' : 'text-slate-700'}`} />
                  <span>{tab.label}</span>
                  {tab.count && (
                    <span className={`text-[9.5px] px-1.5 py-0.2 rounded-full font-mono font-black border ${
                      isActive ? 'bg-white text-slate-950 border-slate-900' : 'bg-slate-200 text-slate-800 border-slate-400'
                    }`}>
                      {tab.count}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* ======================================================== */}
      {/* 1. EVENT STAGE LIVE (Musik, Film AI, Mentoring, Webinar, Classroom, Podcast, Kolaborasi) */}
      {/* ======================================================== */}
      {activeHubSection === 'STAGE' && (
        <section className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-3xl bg-white border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a]">
            <div>
              <div className="flex items-center gap-2">
                <span className="w-8 h-8 rounded-xl bg-rose-200 border-2 border-slate-900 flex items-center justify-center shadow-[1.5px_1.5px_0px_#0f172a]">
                  <Radio className="w-4 h-4 text-rose-700 animate-pulse stroke-[2.5px]" />
                </span>
                <h2 className="text-base font-black text-slate-950">
                  Event Stage Live Allpha Universe
                </h2>
              </div>
              <p className="text-xs font-semibold text-slate-600 mt-1">
                Panggung interaktif virtual untuk Konser Musik, Screening Film AI, Mentoring, Webinar, Kelas AI, dan Podcast.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setIsCreateEventModalOpen(true)}
                className="px-3.5 py-2 rounded-2xl bg-sky-200 hover:bg-sky-300 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center gap-1.5 cursor-pointer"
              >
                <PlusCircle className="w-3.5 h-3.5 stroke-[2.5px]" />
                <span>Buat Event Stage</span>
              </button>
              {onOpenLiveExperienceStage && (
                <button
                  onClick={onOpenLiveExperienceStage}
                  className="px-3.5 py-2 rounded-2xl bg-rose-400 hover:bg-rose-500 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center gap-1.5 cursor-pointer"
                >
                  <Flame className="w-3.5 h-3.5 stroke-[2.5px]" />
                  <span>Masuk Stage Utama</span>
                </button>
              )}
            </div>
          </div>

          {/* Categories Filter Strip */}
          <div className="flex items-center gap-2 overflow-x-auto no-scrollbar py-1">
            {[
              { id: 'ALL' as EventCategory, label: 'Semua Event' },
              { id: 'MUSIK' as EventCategory, label: 'Musik & Konser' },
              { id: 'FILM_AI' as EventCategory, label: 'Film Berbasis AI' },
              { id: 'MENTORING' as EventCategory, label: 'Mentoring AI' },
              { id: 'WEBINAR' as EventCategory, label: 'Webinar Bisnis' },
              { id: 'CLASSROOM' as EventCategory, label: 'Classroom AI' },
              { id: 'PODCAST' as EventCategory, label: 'Podcast Live' },
              { id: 'KOLABORASI' as EventCategory, label: 'Collaboration Stage' },
            ].map((cat) => (
              <button
                key={cat.id}
                onClick={() => setSelectedCategory(cat.id)}
                className={`px-3.5 py-1.5 rounded-2xl text-xs font-black transition whitespace-nowrap shrink-0 border-2 border-slate-900 cursor-pointer active:translate-x-0.5 active:translate-y-0.5 ${
                  selectedCategory === cat.id
                    ? 'bg-slate-950 text-white shadow-[2px_2px_0px_#0f172a]'
                    : 'bg-white text-slate-800 hover:bg-slate-100 shadow-[1.5px_1.5px_0px_#0f172a]'
                }`}
              >
                {cat.label}
              </button>
            ))}
          </div>

          {/* Stage Cards Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {filteredStages.map((stage) => (
              <div
                key={stage.id}
                className="rounded-3xl bg-white border-2 border-slate-900 overflow-hidden shadow-[3px_3px_0px_#0f172a] hover:shadow-[5px_5px_0px_#0f172a] transition group flex flex-col justify-between"
              >
                <div>
                  {/* Stage Visual Thumbnail */}
                  <div className="relative h-40 bg-slate-900 overflow-hidden border-b-2 border-slate-900">
                    <img
                      src={stage.coverImage}
                      alt={stage.title}
                      className="w-full h-full object-cover group-hover:scale-105 transition duration-500"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent" />

                    {/* Top Badges */}
                    <div className="absolute top-2.5 left-2.5 right-2.5 flex items-center justify-between">
                      <span className="px-2.5 py-1 rounded-xl bg-sky-200 text-slate-950 font-black text-[10px] border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a]">
                        {stage.categoryLabel}
                      </span>
                      {stage.isLive ? (
                        <span className="px-2.5 py-1 rounded-xl bg-rose-400 text-slate-950 font-black text-[10px] flex items-center gap-1 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] animate-pulse">
                          <Radio className="w-3 h-3 stroke-[3px]" />
                          <span>LIVE</span>
                        </span>
                      ) : (
                        <span className="px-2.5 py-1 rounded-xl bg-amber-200 text-slate-950 font-black text-[10px] border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a]">
                          {stage.scheduledTime}
                        </span>
                      )}
                    </div>

                    {/* Bottom Metadata inside thumbnail */}
                    <div className="absolute bottom-2 left-2.5 right-2.5 flex items-center justify-between text-white text-[10px]">
                      <span className="flex items-center gap-1 font-mono font-bold bg-slate-900/80 px-2 py-0.5 rounded-lg border border-slate-700">
                        <Users className="w-3 h-3 text-cyan-400" />
                        <span>{stage.viewers.toLocaleString('id-ID')} Penonton</span>
                      </span>
                      <span className="bg-slate-900/80 px-2 py-0.5 rounded-lg border border-slate-700 text-slate-200 truncate max-w-[130px] font-bold">
                        📍 {stage.district}
                      </span>
                    </div>
                  </div>

                  {/* Stage Body */}
                  <div className="p-4 space-y-2.5">
                    <h3 className="font-black text-sm text-slate-950 group-hover:text-blue-600 transition line-clamp-2 leading-snug">
                      {stage.title}
                    </h3>
                    <p className="text-slate-600 text-xs font-semibold line-clamp-2 leading-relaxed">
                      {stage.description}
                    </p>

                    {/* Host & AI Co-Host Duo */}
                    <div className="flex items-center justify-between pt-2 border-t-2 border-slate-100 text-xs">
                      <div className="flex items-center gap-2.5 min-w-0">
                        <div className="relative">
                          <img
                            src={stage.hostAvatar}
                            alt={stage.hostName}
                            className="w-8 h-8 rounded-xl object-cover border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a]"
                          />
                          <img
                            src={stage.aiAgentAvatar}
                            alt={stage.aiAgentName}
                            className="w-4 h-4 rounded-full object-cover border border-slate-900 absolute -bottom-1 -right-1"
                          />
                        </div>
                        <div className="min-w-0">
                          <p className="font-black text-slate-950 text-xs truncate">
                            {stage.hostName}
                          </p>
                          <p className="text-[10px] text-cyan-700 font-bold truncate">
                            & {stage.aiAgentName} (AI Co-Host)
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Stage CTA Action */}
                <div className="p-4 pt-0 flex gap-2">
                  <button
                    onClick={() => setActiveStageModal(stage)}
                    className="flex-1 py-2 px-3 rounded-2xl bg-slate-100 hover:bg-slate-200 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition text-center cursor-pointer"
                  >
                    Detail Panggung
                  </button>
                  <button
                    onClick={() => {
                      if (stage.category === 'FILM_AI' && onOpenFilmAi) {
                        onOpenFilmAi('film-1');
                      } else if (onOpenLiveExperienceStage) {
                        onOpenLiveExperienceStage();
                      } else {
                        onOpenWorld3D(stage.district);
                      }
                    }}
                    className={`py-2 px-4 rounded-2xl font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center justify-center gap-1.5 cursor-pointer ${
                      stage.isLive
                        ? 'bg-rose-400 hover:bg-rose-500 text-slate-950'
                        : 'bg-sky-300 hover:bg-sky-400 text-slate-950'
                    }`}
                  >
                    <span>{stage.isLive ? 'Gabung Live 🎙️' : 'Set Pengingat 🔔'}</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ======================================================== */}
      {/* 2. JELAJAHI DUNIA 3D (WORLDS DIRECTORY)                   */}
      {/* ======================================================== */}
      {activeHubSection === 'WORLDS' && (
        <section className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-3xl bg-white border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a]">
            <div>
              <div className="flex items-center gap-2">
                <span className="w-8 h-8 rounded-xl bg-purple-200 border-2 border-slate-900 flex items-center justify-center shadow-[1.5px_1.5px_0px_#0f172a]">
                  <Box className="w-4 h-4 text-purple-900 stroke-[2.5px]" />
                </span>
                <h2 className="text-base font-black text-slate-950">
                  Jelajahi Dunia 3D (Worlds Directory)
                </h2>
              </div>
              <p className="text-xs font-semibold text-slate-600 mt-1">
                Daftar lengkap dunia virtual, distrik metropolitan, dan area publik Allpha Universe dengan teleportasi instan.
              </p>
            </div>
            <button
              onClick={() => onOpenWorld3D('Central Hub')}
              className="px-4 py-2 rounded-2xl bg-purple-300 hover:bg-purple-400 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center gap-1.5 self-start sm:self-auto cursor-pointer"
            >
              <span>Buka Canvas 3D Universe</span>
              <ArrowUpRight className="w-3.5 h-3.5 stroke-[2.5px]" />
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {worldsDirectory.map((world) => (
              <div
                key={world.id}
                className="rounded-3xl bg-white border-2 border-slate-900 overflow-hidden shadow-[3px_3px_0px_#0f172a] hover:shadow-[5px_5px_0px_#0f172a] transition group flex flex-col justify-between"
              >
                <div>
                  <div className="relative h-40 bg-slate-950 overflow-hidden border-b-2 border-slate-900">
                    <img
                      src={world.image}
                      alt={world.name}
                      className="w-full h-full object-cover group-hover:scale-105 transition duration-500"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/30 to-transparent" />
                    
                    <div className="absolute top-2.5 left-2.5">
                      <span className="px-2.5 py-1 rounded-xl bg-sky-200 text-slate-950 font-black text-[10px] border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a]">
                        {world.badge}
                      </span>
                    </div>

                    <div className="absolute bottom-2 left-2.5 right-2.5 flex items-center justify-between text-white text-[10px]">
                      <span className="flex items-center gap-1 font-mono font-bold bg-slate-900/80 px-2 py-0.5 rounded-lg border border-slate-700 text-cyan-300">
                        <Users className="w-3 h-3" />
                        <span>{world.onlineUsers} Pengguna Aktif</span>
                      </span>
                      <span className="flex items-center gap-1 font-mono font-bold bg-slate-900/80 px-2 py-0.5 rounded-lg border border-slate-700 text-amber-300">
                        <Radio className="w-3 h-3" />
                        <span>{world.liveEventsCount} Stage Aktif</span>
                      </span>
                    </div>
                  </div>

                  <div className="p-4 space-y-2.5">
                    <h3 className="font-black text-sm text-slate-950 group-hover:text-blue-600 transition">
                      {world.name}
                    </h3>
                    <p className="text-slate-600 text-xs font-semibold leading-relaxed">
                      {world.desc}
                    </p>

                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {world.features.map((feat) => (
                        <span
                          key={feat}
                          className="text-[10px] font-black px-2.5 py-0.5 rounded-xl bg-purple-50 text-purple-900 border border-slate-900 shadow-2xs"
                        >
                          {feat}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="p-4 pt-0">
                  <button
                    onClick={() => onOpenWorld3D(world.district)}
                    className="w-full py-2.5 rounded-2xl bg-amber-300 hover:bg-amber-400 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center justify-center gap-1.5 cursor-pointer"
                  >
                    <span>Masuk ke {world.name}</span>
                    <ArrowUpRight className="w-3.5 h-3.5 stroke-[2.5px]" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ======================================================== */}
      {/* 3. 3D VIDEOTRON & MEDIA SURFACES ENGINE                  */}
      {/* ======================================================== */}
      {activeHubSection === 'VIDEOTRON' && (
        <section className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-3xl bg-white border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a]">
            <div>
              <div className="flex items-center gap-2">
                <span className="w-8 h-8 rounded-xl bg-purple-200 border-2 border-slate-900 flex items-center justify-center shadow-[1.5px_1.5px_0px_#0f172a]">
                  <Tv className="w-4 h-4 text-purple-900 stroke-[2.5px]" />
                </span>
                <h2 className="text-base font-black text-slate-950">
                  3D Videotron & Media Surfaces Engine
                </h2>
              </div>
              <p className="text-xs font-semibold text-slate-600 mt-1">
                Engine penayangan materi iklan, video trailer, dan kampanye brand pada layar 4K & videotron anamorphic di Crystal City.
              </p>
            </div>
            <span className="text-xs font-mono font-black text-purple-950 bg-purple-100 px-3 py-1.5 rounded-2xl border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] self-start sm:self-auto">
              Total Impresi Harian: 141.9K
            </span>
          </div>

          {/* Interactive Videotron Live Simulator Card */}
          <div className="p-5 rounded-3xl bg-slate-950 text-white border-2 border-slate-900 shadow-[4px_4px_0px_#0f172a] space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping" />
                <h3 className="font-black text-xs text-purple-200 uppercase tracking-wider">
                  Live Videotron Screen Simulator
                </h3>
              </div>
              <span className="text-[10px] text-slate-400 font-mono font-bold">
                Location: Central Avenue Junction
              </span>
            </div>

            {/* Simulated 3D Billboard Screen Display */}
            <div className="relative rounded-2xl h-44 bg-gradient-to-r from-purple-900 via-indigo-950 to-slate-900 overflow-hidden border-2 border-purple-400/50 flex flex-col items-center justify-center p-4 text-center shadow-2xl">
              <div className="absolute inset-0 opacity-20 bg-[radial-gradient(#38bdf8_1px,transparent_1px)] [background-size:16px_16px]" />
              <div className="relative z-10 space-y-2 max-w-md">
                <span className="text-[10px] font-mono font-black tracking-widest text-cyan-300 uppercase px-2.5 py-0.5 rounded-lg bg-cyan-950/80 border border-cyan-500/40">
                  4K 60FPS ANAMORPHIC SURFACE
                </span>
                <h4 className="text-base sm:text-lg font-black text-white tracking-wide drop-shadow-md">
                  {videotronPreviewText}
                </h4>
                <p className="text-[11px] font-medium text-slate-300">
                  Iklan Anda dilihat oleh 45,800 avatar pengguna dan AI Agent yang melintas di Central Avenue setiap harinya.
                </p>
              </div>

              <div className="absolute bottom-2 right-2 text-[9px] font-mono font-bold text-slate-300 bg-black/70 px-2 py-0.5 rounded border border-slate-700">
                Loop: 15s • Spatial Audio 5.1
              </div>
            </div>

            {/* Customizer Input for Videotron */}
            <div className="flex flex-col sm:flex-row gap-2 pt-1">
              <input
                type="text"
                value={videotronPreviewText}
                onChange={(e) => setVideotronPreviewText(e.target.value)}
                placeholder="Tulis pesan promosi atau nama brand Anda di simulator..."
                className="flex-1 px-3.5 py-2 rounded-2xl bg-slate-900 border-2 border-slate-700 text-xs text-white placeholder:text-slate-500 outline-none focus:border-cyan-400 font-semibold"
              />
              <button
                onClick={() => showToast('Simulasi tampilan videotron diperbarui!')}
                className="px-4 py-2 rounded-2xl bg-cyan-400 hover:bg-cyan-500 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
              >
                Terapkan ke Simulator
              </button>
            </div>
          </div>

          {/* List of Available Media Surfaces */}
          <div className="space-y-3">
            <h3 className="font-black text-sm text-slate-950">
              Pilihan Slot Videotron & Media Surfaces Tersedia
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {videotronSurfaces.map((surf) => (
                <div
                  key={surf.id}
                  className="p-4 rounded-3xl bg-white border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] hover:shadow-[5px_5px_0px_#0f172a] transition flex flex-col justify-between space-y-3"
                >
                  <div className="space-y-2.5">
                    <div className="relative h-32 rounded-2xl overflow-hidden bg-slate-900 border-2 border-slate-900">
                      <img
                        src={surf.previewImage}
                        alt={surf.name}
                        className="w-full h-full object-cover"
                      />
                      <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between text-[10px] text-white bg-black/75 backdrop-blur-sm px-2.5 py-1 rounded-xl border border-slate-700">
                        <span className="font-bold">{surf.type}</span>
                        <span className="font-mono font-black text-cyan-300">{surf.dailyImpressions} imp/hari</span>
                      </div>
                    </div>

                    <div>
                      <h4 className="font-black text-xs text-slate-950">{surf.name}</h4>
                      <p className="text-[11px] font-semibold text-slate-600 mt-0.5">{surf.district} • {surf.location}</p>
                      <p className="text-[10px] font-medium text-slate-500 mt-1">{surf.specs}</p>
                    </div>
                  </div>

                  <div className="pt-2.5 border-t-2 border-slate-100 flex items-center justify-between">
                    <div>
                      <span className="text-[10px] font-bold text-slate-500 block">Tarif Slot</span>
                      <span className="text-xs font-mono font-black text-amber-900">
                        {surf.priceCreditsPerDay} AI Credits / hari
                      </span>
                    </div>
                    <button
                      onClick={() => setSelectedVideotron(surf)}
                      className="px-3.5 py-1.5 rounded-2xl bg-purple-300 hover:bg-purple-400 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
                    >
                      Pesan Slot Iklan
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* ======================================================== */}
      {/* 4. QUEST HARIAN & REWARD XP                              */}
      {/* ======================================================== */}
      {activeHubSection === 'QUESTS' && (
        <section className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-3xl bg-white border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a]">
            <div>
              <div className="flex items-center gap-2">
                <span className="w-8 h-8 rounded-xl bg-amber-200 border-2 border-slate-900 flex items-center justify-center shadow-[1.5px_1.5px_0px_#0f172a]">
                  <Award className="w-4 h-4 text-amber-900 stroke-[2.5px]" />
                </span>
                <h2 className="text-base font-black text-slate-950">
                  Quest Harian & Reward XP
                </h2>
              </div>
              <p className="text-xs font-semibold text-slate-600 mt-1">
                Selesaikan misi eksplorasi dan interaksi di Allpha Universe untuk mengumpulkan AI Credits & menaikkan Level Kreator Anda.
              </p>
            </div>

            {/* Streak Counter */}
            <div className="flex items-center gap-2 px-3.5 py-2 rounded-2xl bg-amber-200 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-slate-950 text-xs font-black self-start sm:self-auto">
              <Flame className="w-4 h-4 text-amber-700 fill-amber-500 animate-bounce" />
              <span>Streak 5 Hari Beruntun 🔥</span>
            </div>
          </div>

          {/* Level Progress Card */}
          <div className="p-5 rounded-3xl bg-amber-100 border-2 border-slate-900 shadow-[4px_4px_0px_#0f172a] space-y-3">
            <div className="flex items-center justify-between text-xs font-black text-slate-950">
              <span className="uppercase tracking-wide">Level 8 — Spatial Architect</span>
              <span className="font-mono bg-white px-2.5 py-0.5 rounded-xl border-2 border-slate-900">1,850 / 2,500 XP</span>
            </div>
            <div className="w-full h-3 rounded-full bg-white border-2 border-slate-900 overflow-hidden p-0.5">
              <div className="h-full bg-amber-400 rounded-full transition-all duration-500" style={{ width: '74%' }} />
            </div>
            <p className="text-xs font-semibold text-slate-800">
              Selesaikan 2 misi lagi hari ini untuk membuka lencana eksklusif &quot;Cyber District Pioneer&quot; dan bonus 50 AI Credits.
            </p>
          </div>

          {/* Quests List */}
          <div className="space-y-3">
            {hubQuests.map((quest) => {
              const isCompleted = quest.current >= quest.target;

              return (
                <div
                  key={quest.id}
                  className="p-4 rounded-3xl bg-white border-2 border-slate-900 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-[3px_3px_0px_#0f172a] hover:shadow-[4px_4px_0px_#0f172a] transition"
                >
                  <div className="space-y-2 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-black px-2.5 py-0.5 rounded-xl bg-sky-100 text-sky-950 border border-slate-900">
                        {quest.category}
                      </span>
                      <h4 className="font-black text-xs text-slate-950">{quest.title}</h4>
                    </div>

                    {/* Progress Bar */}
                    <div className="flex items-center gap-3">
                      <div className="flex-1 max-w-xs h-2 rounded-full bg-slate-100 border border-slate-900 overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-300 ${
                            isCompleted ? 'bg-emerald-400' : 'bg-sky-400'
                          }`}
                          style={{ width: `${Math.min(100, (quest.current / quest.target) * 100)}%` }}
                        />
                      </div>
                      <span className="text-[11px] font-mono text-slate-800 font-black">
                        {quest.current}/{quest.target}
                      </span>
                    </div>

                    <div className="flex items-center gap-3 text-[11px] font-black text-slate-800">
                      <span className="text-amber-900 flex items-center gap-1 bg-amber-100 px-2 py-0.5 rounded-lg border border-slate-900">
                        <Coins className="w-3 h-3 text-amber-700" />
                        +{quest.credits} Credits
                      </span>
                      <span className="text-purple-900 bg-purple-100 px-2 py-0.5 rounded-lg border border-slate-900">
                        +{quest.xp} XP
                      </span>
                    </div>
                  </div>

                  <div>
                    {quest.claimed ? (
                      <span className="px-3.5 py-2 rounded-2xl bg-slate-100 text-slate-500 font-black text-xs border-2 border-slate-400 inline-flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 stroke-[2.5px]" />
                        Telah Diklaim
                      </span>
                    ) : isCompleted ? (
                      <button
                        onClick={() => handleClaimQuest(quest.id, quest.credits, quest.xp)}
                        className="w-full sm:w-auto px-4 py-2 rounded-2xl bg-emerald-300 hover:bg-emerald-400 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
                      >
                        Klaim Hadiah 🎁
                      </button>
                    ) : (
                      <span className="px-3.5 py-2 rounded-2xl bg-slate-100 text-slate-600 font-bold text-xs border-2 border-slate-300">
                        Sedang Berjalan
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* ======================================================== */}
      {/* 5. BUKU BESAR MUTASI & SETTLEMENT CREATOR               */}
      {/* ======================================================== */}
      {activeHubSection === 'LEDGER' && (
        <section className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-3xl bg-white border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a]">
            <div>
              <div className="flex items-center gap-2">
                <span className="w-8 h-8 rounded-xl bg-indigo-200 border-2 border-slate-900 flex items-center justify-center shadow-[1.5px_1.5px_0px_#0f172a]">
                  <Receipt className="w-4 h-4 text-indigo-900 stroke-[2.5px]" />
                </span>
                <h2 className="text-base font-black text-slate-950">
                  Buku Besar Mutasi & Settlement Creator
                </h2>
              </div>
              <p className="text-xs font-semibold text-slate-600 mt-1">
                Pencatatan transparan seluruh mutasi pendapatan Film AI, tiket panggung, dan pembagian royalti (70% Human Kreator / 30% AI Treasury).
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  const csvData = "Tanggal,Judul,Kategori,Nominal,Status\n" + ledgerEntries.map(e => `"${e.date}","${e.title}","${e.category}",${e.amount},"${e.status}"`).join("\n");
                  const blob = new Blob([csvData], { type: 'text/csv' });
                  const url = window.URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `Allpha_Settlement_Ledger_${Date.now()}.csv`;
                  a.click();
                  showToast('Laporan Rekening Koran CSV berhasil diunduh!');
                }}
                className="px-3.5 py-2 rounded-2xl bg-white hover:bg-slate-100 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center gap-1.5 cursor-pointer"
                title="Download CSV"
              >
                <Download className="w-3.5 h-3.5 stroke-[2.5px]" />
                <span>Unduh CSV</span>
              </button>
              <button
                onClick={() => setIsSettlementModalOpen(true)}
                className="px-4 py-2 rounded-2xl bg-indigo-300 hover:bg-indigo-400 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center gap-1.5 cursor-pointer"
              >
                <CreditCard className="w-3.5 h-3.5 stroke-[2.5px]" />
                <span>Tarik Saldo / Settlement</span>
              </button>
            </div>
          </div>

          {/* Financial Overview Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="p-4 rounded-3xl bg-emerald-50 border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] space-y-1">
              <span className="text-[11px] font-black text-emerald-950 uppercase tracking-wider">
                Saldo Kreator Human (70%)
              </span>
              <p className="text-xl font-mono font-black text-emerald-950">
                {creatorBalance.toLocaleString('id-ID')} <span className="text-xs font-bold text-slate-600">Credits</span>
              </p>
              <p className="text-xs text-emerald-800 font-bold">
                ≈ Rp {(creatorBalance * 1000).toLocaleString('id-ID')} Siap Tarik
              </p>
            </div>

            <div className="p-4 rounded-3xl bg-purple-50 border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] space-y-1">
              <span className="text-[11px] font-black text-purple-950 uppercase tracking-wider">
                AI Agent Treasury (30%)
              </span>
              <p className="text-xl font-mono font-black text-purple-950">
                {agentTreasury.toLocaleString('id-ID')} <span className="text-xs font-bold text-slate-600">Credits</span>
              </p>
              <p className="text-xs text-purple-800 font-bold">
                Alokasi upgrade memori & komputasi agen
              </p>
            </div>

            <div className="p-4 rounded-3xl bg-sky-50 border-2 border-slate-900 shadow-[3px_3px_0px_#0f172a] space-y-1">
              <span className="text-[11px] font-black text-sky-950 uppercase tracking-wider">
                Total Mutasi Tercatat
              </span>
              <p className="text-xl font-mono font-black text-sky-950">
                {ledgerEntries.length} <span className="text-xs font-bold text-slate-600">Transaksi</span>
              </p>
              <p className="text-xs text-sky-800 font-bold">
                Audit otomatis terverifikasi
              </p>
            </div>
          </div>

          {/* Ledger Table */}
          <div className="rounded-3xl bg-white border-2 border-slate-900 overflow-hidden shadow-[3px_3px_0px_#0f172a]">
            <div className="p-3.5 bg-slate-100 border-b-2 border-slate-900 flex items-center justify-between text-xs font-black text-slate-950">
              <span>Mutasi Transaksi & Riwayat Pembayaran</span>
              <span className="text-slate-600 font-bold">Real-time settlement</span>
            </div>

            <div className="divide-y-2 divide-slate-100">
              {ledgerEntries.map((item) => (
                <div
                  key={item.id}
                  className="p-3.5 sm:p-4 hover:bg-slate-50 transition flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 text-xs"
                >
                  <div className="space-y-1 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-slate-500 font-mono font-bold">{item.date}</span>
                      <span className="text-[9px] px-1.5 py-0.2 rounded bg-slate-100 text-slate-800 font-mono font-black border border-slate-300">
                        {item.refCode}
                      </span>
                    </div>
                    <p className="font-black text-slate-950">{item.title}</p>
                    <p className="text-[11px] text-slate-600 font-medium">{item.split}</p>
                  </div>

                  <div className="flex sm:flex-col items-center sm:items-end justify-between gap-1">
                    <span className={`font-mono font-black text-sm ${
                      item.amount > 0 ? 'text-emerald-700' : 'text-slate-950'
                    }`}>
                      {item.amount > 0 ? `+${item.amount}` : item.amount} Cr
                    </span>
                    <span className={`text-[10px] px-2.5 py-0.5 rounded-xl font-black font-mono border-2 border-slate-900 shadow-2xs ${
                      item.status === 'SETTLED'
                        ? 'bg-emerald-200 text-emerald-950'
                        : 'bg-amber-200 text-amber-950'
                    }`}>
                      {item.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* ======================================================== */}
      {/* MODAL 1: DETAIL EVENT STAGE & JOIN                      */}
      {/* ======================================================== */}
      {activeStageModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg rounded-3xl bg-white border-2 border-slate-900 shadow-[6px_6px_0px_#0f172a] overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="relative h-44 bg-slate-950 border-b-2 border-slate-900">
              <img
                src={activeStageModal.coverImage}
                alt={activeStageModal.title}
                className="w-full h-full object-cover"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/30 to-transparent" />
              <button
                onClick={() => setActiveStageModal(null)}
                className="absolute top-3 right-3 w-8 h-8 rounded-xl bg-white/90 hover:bg-white text-slate-950 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] flex items-center justify-center transition cursor-pointer"
              >
                <X className="w-4 h-4 stroke-[2.5px]" />
              </button>
              <div className="absolute bottom-3 left-4 right-4 text-white">
                <span className="text-[10px] px-2.5 py-0.5 rounded-xl bg-rose-400 text-slate-950 border-2 border-slate-900 font-black uppercase shadow-2xs">
                  {activeStageModal.categoryLabel}
                </span>
                <h3 className="font-black text-base mt-1 line-clamp-1">{activeStageModal.title}</h3>
              </div>
            </div>

            <div className="p-5 space-y-4 text-xs">
              <p className="text-slate-700 font-semibold leading-relaxed">
                {activeStageModal.description}
              </p>

              <div className="p-3.5 rounded-2xl bg-sky-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-slate-600 font-bold">Lokasi Panggung:</span>
                  <span className="font-black text-slate-950">📍 {activeStageModal.district}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-600 font-bold">Host Utama:</span>
                  <span className="font-black text-slate-950">{activeStageModal.hostName}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-600 font-bold">AI Agent Co-Host:</span>
                  <span className="font-black text-cyan-800">{activeStageModal.aiAgentName}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-600 font-bold">Penonton Saat Ini:</span>
                  <span className="font-mono font-black text-slate-950">{activeStageModal.viewers.toLocaleString('id-ID')} Orang</span>
                </div>
              </div>

              <div className="flex gap-2.5 pt-2">
                <button
                  onClick={() => setActiveStageModal(null)}
                  className="flex-1 py-2.5 rounded-2xl bg-slate-100 hover:bg-slate-200 text-slate-950 font-black border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
                >
                  Tutup
                </button>
                <button
                  onClick={() => {
                    const st = activeStageModal;
                    setActiveStageModal(null);
                    if (st.category === 'FILM_AI' && onOpenFilmAi) {
                      onOpenFilmAi('film-1');
                    } else if (onOpenLiveExperienceStage) {
                      onOpenLiveExperienceStage();
                    } else {
                      onOpenWorld3D(st.district);
                    }
                  }}
                  className="flex-1 py-2.5 rounded-2xl bg-rose-400 hover:bg-rose-500 text-slate-950 font-black border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition flex items-center justify-center gap-1.5 cursor-pointer"
                >
                  <Radio className="w-3.5 h-3.5 stroke-[2.5px]" />
                  <span>Masuk ke Panggung Live</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* MODAL 2: SEWA VIDEOTRON SLOT                            */}
      {/* ======================================================== */}
      {selectedVideotron && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md rounded-3xl bg-white border-2 border-slate-900 shadow-[6px_6px_0px_#0f172a] p-5 space-y-4 animate-in fade-in zoom-in-95 duration-200 text-xs">
            <div className="flex items-start justify-between pb-2 border-b-2 border-slate-100">
              <div>
                <span className="text-[10px] font-black text-purple-900 uppercase">Pemesanan Media Surface</span>
                <h3 className="font-black text-sm text-slate-950 mt-0.5">{selectedVideotron.name}</h3>
              </div>
              <button
                onClick={() => setSelectedVideotron(null)}
                className="w-7 h-7 rounded-xl bg-slate-100 hover:bg-slate-200 border-2 border-slate-900 flex items-center justify-center text-slate-900 cursor-pointer"
              >
                <X className="w-3.5 h-3.5 stroke-[2.5px]" />
              </button>
            </div>

            <div className="p-3.5 rounded-2xl bg-purple-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] space-y-1.5 text-[11px] font-semibold text-slate-800">
              <p>📍 <strong>Lokasi:</strong> {selectedVideotron.location} ({selectedVideotron.district})</p>
              <p>👥 <strong>Estimasi Impresi:</strong> {selectedVideotron.dailyImpressions} avatar/hari</p>
              <p>🪙 <strong>Tarif:</strong> {selectedVideotron.priceCreditsPerDay} AI Credits / hari</p>
            </div>

            <div className="space-y-1.5">
              <label className="font-black text-slate-900">Durasi Penayangan (Hari):</label>
              <div className="flex gap-2">
                {[1, 3, 7, 14, 30].map((d) => (
                  <button
                    key={d}
                    type="button"
                    onClick={() => setBookingDays(d)}
                    className={`flex-1 py-1.5 rounded-xl font-black border-2 border-slate-900 transition active:translate-x-0.5 active:translate-y-0.5 cursor-pointer ${
                      bookingDays === d
                        ? 'bg-purple-300 text-slate-950 shadow-[1.5px_1.5px_0px_#0f172a]'
                        : 'bg-white text-slate-700 hover:bg-slate-100'
                    }`}
                  >
                    {d} Hari
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="font-black text-slate-900">Teks / Pesan Kampanye:</label>
              <input
                type="text"
                value={videotronPreviewText}
                onChange={(e) => setVideotronPreviewText(e.target.value)}
                className="w-full px-3 py-2 rounded-2xl bg-slate-50 border-2 border-slate-900 text-slate-950 font-bold outline-none"
              />
            </div>

            <div className="p-3.5 rounded-2xl bg-amber-100 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] flex items-center justify-between text-amber-950">
              <span className="font-bold text-xs">Total Biaya ({bookingDays} hari):</span>
              <span className="font-mono font-black text-sm">
                {selectedVideotron.priceCreditsPerDay * bookingDays} AI Credits
              </span>
            </div>

            <div className="flex gap-2 pt-1">
              <button
                onClick={() => setSelectedVideotron(null)}
                className="flex-1 py-2.5 rounded-2xl bg-slate-100 hover:bg-slate-200 text-slate-950 font-black border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
              >
                Batal
              </button>
              <button
                onClick={handleConfirmVideotronBooking}
                className="flex-1 py-2.5 rounded-2xl bg-purple-300 hover:bg-purple-400 text-slate-950 font-black border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
              >
                Konfirmasi & Bayar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* MODAL 3: PENCAIRAN SALDO / SETTLEMENT KREATOR            */}
      {/* ======================================================== */}
      {isSettlementModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <form
            onSubmit={handleExecuteSettlement}
            className="w-full max-w-md rounded-3xl bg-white border-2 border-slate-900 shadow-[6px_6px_0px_#0f172a] p-5 space-y-4 animate-in fade-in zoom-in-95 duration-200 text-xs"
          >
            <div className="flex items-start justify-between pb-2 border-b-2 border-slate-100">
              <div>
                <span className="text-[10px] font-black text-indigo-900 uppercase">Settlement Royalti Kreator</span>
                <h3 className="font-black text-sm text-slate-950 mt-0.5">Tarik Saldo Royalti 70%</h3>
              </div>
              <button
                type="button"
                onClick={() => setIsSettlementModalOpen(false)}
                className="w-7 h-7 rounded-xl bg-slate-100 hover:bg-slate-200 border-2 border-slate-900 flex items-center justify-center text-slate-900 cursor-pointer"
              >
                <X className="w-3.5 h-3.5 stroke-[2.5px]" />
              </button>
            </div>

            <div className="p-3.5 rounded-2xl bg-indigo-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] space-y-1 text-indigo-950">
              <span className="text-[10px] uppercase font-black text-indigo-800">Saldo Tersedia untuk Dicairkan</span>
              <p className="text-xl font-mono font-black">{creatorBalance.toLocaleString('id-ID')} Credits</p>
              <p className="text-xs text-indigo-800 font-bold">Kurs Tetap: 1 Credit = Rp 1.000 (Setara Rp {(creatorBalance * 1000).toLocaleString('id-ID')})</p>
            </div>

            <div className="space-y-1.5">
              <label className="font-black text-slate-900">Jumlah Credits yang Dicairkan:</label>
              <input
                type="number"
                min="50"
                max={creatorBalance}
                value={settlementAmount}
                onChange={(e) => setSettlementAmount(e.target.value)}
                className="w-full px-3 py-2 rounded-2xl bg-slate-50 border-2 border-slate-900 text-slate-950 font-mono font-black outline-none"
              />
              <p className="text-[10px] text-slate-600 font-bold">
                Nilai yang diterima: Rp {(parseInt(settlementAmount || '0', 10) * 1000).toLocaleString('id-ID')}
              </p>
            </div>

            <div className="space-y-1.5">
              <label className="font-black text-slate-900">Metode Pencairan (Bank / e-Wallet):</label>
              <div className="grid grid-cols-4 gap-2">
                {['BCA', 'Mandiri', 'GoPay', 'OVO'].map((ch) => (
                  <button
                    key={ch}
                    type="button"
                    onClick={() => setSettlementChannel(ch)}
                    className={`py-1.5 rounded-xl font-black border-2 border-slate-900 transition active:translate-x-0.5 active:translate-y-0.5 cursor-pointer ${
                      settlementChannel === ch
                        ? 'bg-indigo-300 text-slate-950 shadow-[1.5px_1.5px_0px_#0f172a]'
                        : 'bg-white text-slate-700 hover:bg-slate-100'
                    }`}
                  >
                    {ch}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="font-black text-slate-900">Nomor Rekening / Akun Tujuan:</label>
              <input
                type="text"
                value={accountNumber}
                onChange={(e) => setAccountNumber(e.target.value)}
                className="w-full px-3 py-2 rounded-2xl bg-slate-50 border-2 border-slate-900 text-slate-950 font-mono font-bold outline-none"
              />
            </div>

            <div className="flex gap-2 pt-2">
              <button
                type="button"
                onClick={() => setIsSettlementModalOpen(false)}
                className="flex-1 py-2.5 rounded-2xl bg-slate-100 hover:bg-slate-200 text-slate-950 font-black border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
              >
                Batal
              </button>
              <button
                type="submit"
                className="flex-1 py-2.5 rounded-2xl bg-indigo-300 hover:bg-indigo-400 text-slate-950 font-black border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
              >
                Kirim Pengajuan
              </button>
            </div>
          </form>
        </div>
      )}

      {/* ======================================================== */}
      {/* MODAL 4: BUAT EVENT STAGE BARU                          */}
      {/* ======================================================== */}
      {isCreateEventModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md rounded-3xl bg-white border-2 border-slate-900 shadow-[6px_6px_0px_#0f172a] p-5 space-y-4 animate-in fade-in zoom-in-95 duration-200 text-xs">
            <div className="flex items-start justify-between pb-2 border-b-2 border-slate-100">
              <div>
                <span className="text-[10px] font-black text-sky-900 uppercase">Panggung Virtual</span>
                <h3 className="font-black text-sm text-slate-950 mt-0.5">Buat Event Stage Baru</h3>
              </div>
              <button
                onClick={() => setIsCreateEventModalOpen(false)}
                className="w-7 h-7 rounded-xl bg-slate-100 hover:bg-slate-200 border-2 border-slate-900 flex items-center justify-center text-slate-900 cursor-pointer"
              >
                <X className="w-3.5 h-3.5 stroke-[2.5px]" />
              </button>
            </div>

            <div className="space-y-1.5">
              <label className="font-black text-slate-900">Judul Event Stage:</label>
              <input
                type="text"
                value={newEventTitle}
                onChange={(e) => setNewEventTitle(e.target.value)}
                placeholder="Contoh: Screening Film AI Drama Korea & Q&A Sutradara..."
                className="w-full px-3 py-2 rounded-2xl bg-slate-50 border-2 border-slate-900 text-slate-950 font-bold outline-none"
              />
            </div>

            <div className="space-y-1.5">
              <label className="font-black text-slate-900">Kategori Event:</label>
              <select
                value={newEventCategory}
                onChange={(e) => setNewEventCategory(e.target.value as EventCategory)}
                className="w-full px-3 py-2 rounded-2xl bg-slate-50 border-2 border-slate-900 text-slate-950 font-black outline-none"
              >
                <option value="MUSIK">Musik & Konser Virtual</option>
                <option value="FILM_AI">Film Berbasis AI Screening</option>
                <option value="MENTORING">Mentoring AI 1-on-1</option>
                <option value="WEBINAR">Webinar Bisnis & Edukasi</option>
                <option value="CLASSROOM">Classroom AI Spatial</option>
                <option value="PODCAST">Podcast Live Interaktif</option>
                <option value="KOLABORASI">Collaboration Stage</option>
              </select>
            </div>

            <div className="p-3.5 rounded-2xl bg-sky-50 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] text-[11px] text-sky-950 space-y-1 font-semibold">
              <p className="font-black">✨ Keuntungan Event Stage di Allpha Hub:</p>
              <p>• AI Co-Host Anda otomatis aktif menemani & berdialog dengan audiens.</p>
              <p>• Royalti tiket atau donasi 70% langsung masuk ke saldo settlement Anda.</p>
            </div>

            <div className="flex gap-2 pt-2">
              <button
                onClick={() => setIsCreateEventModalOpen(false)}
                className="flex-1 py-2.5 rounded-2xl bg-slate-100 hover:bg-slate-200 text-slate-950 font-black border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
              >
                Batal
              </button>
              <button
                onClick={() => {
                  if (!newEventTitle.trim()) {
                    showToast('Harap masukkan judul event.');
                    return;
                  }
                  showToast(`Event "${newEventTitle}" berhasil didaftarkan di Allpha Hub!`);
                  setIsCreateEventModalOpen(false);
                  setNewEventTitle('');
                }}
                className="flex-1 py-2.5 rounded-2xl bg-sky-300 hover:bg-sky-400 text-slate-950 font-black border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] active:translate-x-0.5 active:translate-y-0.5 transition cursor-pointer"
              >
                Publikasikan Event
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

'use client';

import React, { useState } from 'react';
import { 
  Sparkles, 
  MapPin, 
  Layers, 
  ExternalLink, 
  Play, 
  Eye, 
  Check, 
  ChevronRight, 
  Building2, 
  Tv, 
  Store, 
  Compass, 
  Box, 
  X,
  Maximize2,
  Info,
  Radio,
  Star,
  Zap,
  Globe2,
  Download,
  Loader2
} from 'lucide-react';
import Menggu3DViewerModal, { MengguViewerItem } from './Menggu3DViewerModal';
import { 
  generateMengguAssetGLB, 
  downloadGLBBlob, 
  getMengguModelByType,
  MENGGU_PALETTE 
} from '@/lib/menggu3dEngine';

export interface MengguAssetHighlight {
  id: string;
  name: string;
  categoryTag: string;
  categoryNumber: number;
  badge: string;
  badgeColor: string;
  image: string;
  tagline: string;
  description: string;
  districtCoordinates: string;
  targetDistrict: string;
  features: string[];
  specs: {
    polycount: string;
    textures: string;
    format: string;
    materials: string;
  };
}

export interface CanonicalCategory3D {
  id: number;
  name: string;
  englishTitle: string;
  icon: string;
  badge: string;
  color: string;
  description: string;
  itemsSample: string[];
  prdSection: string;
  modelCount: number;
}

export const MENGGU_SPATIAL_ASSETS: MengguAssetHighlight[] = [
  {
    id: 'district-spatial',
    name: 'Metropolis Spatial District',
    categoryTag: '3. District & Landmark',
    categoryNumber: 3,
    badge: '🏙️ SPATIAL DISTRICT',
    badgeColor: 'bg-[#FEF08A] text-slate-950',
    image: '/assets/menggu3d/district_spatial.jpg',
    tagline: 'Blok Kota Futuristik & Jalur Monorail Bubble Pods',
    description: 'Tata ruang distrik spatial 3D Menggu dengan arsitektur clay pastel butter yellow & lavender. Menghubungkan gedung bertingkat dengan elevated monorail melayang, jembatan pejalan kaki bertingkat, pohon kristal pendaran lembut, dan pertokoan interaktif.',
    districtCoordinates: 'Crystal City Atrium #M-01',
    targetDistrict: 'Central Hub',
    features: ['Elevated Monorail Bubble Pods', 'Kristal Luminescent Trees', 'Double-Deck Pedestrian Bridge', 'PBR Clay Soft Shading'],
    specs: {
      polycount: '38.4K Polygons',
      textures: '2K PBR Diffuse / Roughness',
      format: 'GLTF / Three.js Mesh Group',
      materials: 'Pastel Soft Clay PBR'
    }
  },
  {
    id: 'landmark-citadel',
    name: 'Crystal Citadel & AI Spire Tower',
    categoryTag: '3. District & Landmark',
    categoryNumber: 3,
    badge: '🗼 LANDMARK & GEDUNG',
    badgeColor: 'bg-[#DDD6FE] text-purple-950',
    image: '/assets/menggu3d/landmark_citadel.jpg',
    tagline: 'Menara Ikonik Pusat Komputasi AI & Observatorium',
    description: 'Pencakar langit futuristik bertingkat dengan puncak kristal turkis bercahaya yang memancarkan pendaran spatial. Dilengkapi ramp pejalan kaki heliks melingkar, dek observasi berteropong, dan armada drone kurir AI otonom.',
    districtCoordinates: 'Crystal City Business Center #T-08',
    targetDistrict: 'Business District',
    features: ['Translucent Quartz Spire 3D', 'Spiral Pedestrian Helix Ramp', 'Telescope Observation Decks', 'Autonomous Courier Drones'],
    specs: {
      polycount: '42.1K Polygons',
      textures: '2K Emissive & Quartz Specular',
      format: 'GLTF 2.0 Rigged Mesh',
      materials: 'Lilac Clay & Glass Translucent'
    }
  },
  {
    id: 'plaza-fountain',
    name: 'AI Central Plaza & Holographic Fountain',
    categoryTag: '3. District & Landmark',
    categoryNumber: 3,
    badge: '⛲ PLAZA & FOUNTAIN',
    badgeColor: 'bg-[#BAE6FD] text-sky-950',
    image: '/assets/menggu3d/ai_plaza.jpg',
    tagline: 'Alun-Alun Terbuka Pertemuan Avatar & AI Concierge',
    description: 'Plaza sosial interaktif dengan air mancur holografis melayang di titik tengah yang memancarkan tetesan air kaca bercahaya. Dikelilingi bangku taman pastel melengkung, lentera bola hangat, dan robot pendamping AI yang menyapa ramah.',
    districtCoordinates: 'Crystal City Central Plaza #P-03',
    targetDistrict: 'AI Plaza',
    features: ['Holographic Droplets FX', 'Curved Pastel Social Benches', 'Autonomous Robot Concierge', 'Ambient Spatial Chat Nodes'],
    specs: {
      polycount: '34.6K Polygons',
      textures: 'Water Shader GLSL + 2K Clay',
      format: 'Three.js Group Component',
      materials: 'Turquoise Hologram + Peach Clay'
    }
  },
  {
    id: 'billboard-videotron',
    name: 'Floating Curved Holographic Videotron Ads',
    categoryTag: '11. UI Props & Holograms',
    categoryNumber: 11,
    badge: '📺 BILLBOARD ADS 3D',
    badgeColor: 'bg-[#FECDD3] text-rose-950',
    image: '/assets/menggu3d/billboard_ads.jpg',
    tagline: 'Papan Reklame Spatial Melayang untuk Siaran Langsung & Iklan',
    description: 'Layar videotron melengkung raksasa berskala kota yang menayangkan siaran langsung Allpha 3D Live. Terintegrasi dengan drone kamera spatial dan audio directional 3D yang dinikmati seluruh avatar pengunjung distrik.',
    districtCoordinates: 'Neo Tokyo / Crystal Highway #B-99',
    targetDistrict: 'Creator Hub',
    features: ['Curved Emissive Videotron Surface', 'Allpha 3D Live Multi-Stream', 'Spatial Cam Drones Broadcast', 'Directional 3D Web Audio'],
    specs: {
      polycount: '18.2K Polygons',
      textures: 'Dynamic Canvas Emissive Video',
      format: 'Custom Spatial Mesh',
      materials: 'Curved Neon Clay Frame'
    }
  },
  {
    id: 'booth-tenant',
    name: 'Interactive 3D Tenant Booth & Showcase',
    categoryTag: '4. Booth & Tenant',
    categoryNumber: 4,
    badge: '🛍️ BOOTH 3D & KIOS',
    badgeColor: 'bg-[#BBF7D0] text-emerald-950',
    image: '/assets/menggu3d/booth_3d.jpg',
    tagline: 'Paviliun Toko Spatial untuk Penjualan Produk & Aset 3D',
    description: 'Stan toko modular 3D Menggu dengan logo neon custom, meja pamer hologram untuk preview aset atau hewan peliharaan virtual, dan etalase interaktif untuk checkout langsung via AI Credits atau Rupiah.',
    districtCoordinates: 'Crystal City Marketplace #K-12',
    targetDistrict: '3D Marketplace Avenue',
    features: ['Hologram Product Display Table', 'Virtual Pet & Rig Preview', 'Custom Neon Signage', 'Instant Checkout 1-Tap'],
    specs: {
      polycount: '26.8K Polygons',
      textures: 'PBR Neon Emissive + Clay',
      format: 'Modular Tenant GLB',
      materials: 'Mint & Coral Menggu Pastel'
    }
  },
  {
    id: 'avatar-menggu',
    name: 'Articulated Avatar 3D Menggu & AI Companion',
    categoryTag: '7. Human Avatar & Uniform',
    categoryNumber: 7,
    badge: '🧑‍🚀 AVATAR 3D MENGGU',
    badgeColor: 'bg-[#FEF08A] text-amber-950',
    image: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=800&q=80',
    tagline: 'Karakter Humanoid & AI Agent Artikulasi Menggu Pastel',
    description: 'Model avatar 3D berestetika clay Menggu dengan proporsi ramah, visor kaca kuantum pendar, sendi tangan yang dapat melambai (waving), dan perlengkapan streetwear cyber pastel yang siap diekspor ke format GLB.',
    districtCoordinates: 'Crystal City Avatar Studio #A-07',
    targetDistrict: 'Central Hub',
    features: ['Articulated Bone Rigging', 'Pastel Cyber Streetwear', 'Translucent Visor 3D', 'Emote Animation Wave & Idle'],
    specs: {
      polycount: '24.2K Polygons',
      textures: '2K Soft Clay PBR',
      format: 'GLTF / GLB Rigged Skeleton',
      materials: 'Pastel Yellow & Slate Clay'
    }
  }
];

export const CANONICAL_14_CATEGORIES_3D: CanonicalCategory3D[] = [
  {
    id: 1,
    name: 'Universe & Galaxy',
    englishTitle: 'Cosmic & Orbital Elements',
    icon: '🌌',
    badge: 'KOSMIK',
    color: 'from-indigo-500 to-purple-600',
    description: 'Cosmic environment, planet, cincin orbit, gugusan galaksi, dan elemen navigasi rasi bintang spatial.',
    itemsSample: ['Planetarium Kubah', 'Cincin Orbit Satelit', 'Peta Bintang 3D', 'Gerbang Galaksi'],
    prdSection: 'PRD Sec 53.1',
    modelCount: 142
  },
  {
    id: 2,
    name: 'World & Environment',
    englishTitle: 'Terrain, Atmosphere & Sky',
    icon: '🪐',
    badge: 'LINGKUNGAN',
    color: 'from-sky-500 to-teal-600',
    description: 'Topografi dataran soft clay, kubah langit biophilic, vegetasi kanopi, atmosfer cuaca, dan horizon dunia.',
    itemsSample: ['Bukit Clay Kontur', 'Kubah Langit Aurora', 'Pohon Kristal Biophilic', 'Awan Volumetrik'],
    prdSection: 'PRD Sec 53.2',
    modelCount: 285
  },
  {
    id: 3,
    name: 'District & Landmark',
    englishTitle: 'City Blocks, Towers & Plazas',
    icon: '🏙️',
    badge: 'DISTRIK & LANDMARK',
    color: 'from-amber-500 to-orange-600',
    description: 'Blok kota metropolitan, jalanan pedestrian, gedung pencakar langit futuristik, alun-alun plaza, dan monumen.',
    itemsSample: ['Crystal Citadel Tower', 'AI Central Plaza', 'Jalur Monorail Bubble', 'Jembatan Bertingkat'],
    prdSection: 'PRD Sec 53.3',
    modelCount: 418
  },
  {
    id: 4,
    name: 'Booth & Tenant',
    englishTitle: 'Shops, Kiosks & Pavilions',
    icon: '🛍️',
    badge: 'BOOTH & TENANT',
    color: 'from-emerald-500 to-teal-600',
    description: 'Stan toko interaktif, kios modular, paviliun brand, interior retail, dan etalase produk digital/fisik.',
    itemsSample: ['Kios Pop-up Menggu', 'Meja Pajang Hologram', 'Rak Digital Fashion', 'Neon Shop Signage'],
    prdSection: 'PRD Sec 53.4',
    modelCount: 326
  },
  {
    id: 5,
    name: 'Live Experience Stage',
    englishTitle: 'Stages, Studios & Arenas',
    icon: '🎙️',
    badge: 'LIVE STAGE',
    color: 'from-rose-500 to-pink-600',
    description: 'Panggung podcast live, studio talkshow, arena presentasi dokumen, ruang kuliah tutor, dan konser musik virtual.',
    itemsSample: ['Studio Podcast Menggu', 'Panggung Presentasi Slide', 'Amfiteater Diskusi', 'Layar Proyektor Raksasa'],
    prdSection: 'PRD Sec 53.5',
    modelCount: 194
  },
  {
    id: 6,
    name: 'AI Character & Animation',
    englishTitle: 'Rigged Agents & Skeletal Bots',
    icon: '🤖',
    badge: 'AI AGENTS',
    color: 'from-purple-500 to-indigo-600',
    description: 'Model 3D AI Agent bertulang (rigged), animasi skeletal gerak, ekspresi wajah visemes, dan gestur interaktif.',
    itemsSample: ['Robot Concierge Menggu', 'Drone Asisten Melayang', 'Animasi Melambai & Emote', 'Avatar Maskot 3D'],
    prdSection: 'PRD Sec 53.6',
    modelCount: 512
  },
  {
    id: 7,
    name: 'Human Avatar & Uniform',
    englishTitle: 'Bases, Streetwear & Outfits',
    icon: '🧑‍🚀',
    badge: 'AVATAR MANUSIA',
    color: 'from-blue-500 to-cyan-600',
    description: 'Basis avatar pengguna manusia, busana kasual streetwear, seragam formal, hero suit, dan motif Nusantara modern.',
    itemsSample: ['Set Pakaian Streetwear Clay', 'Hoodie Cyber Neon', 'Seragam Batik Futuristik', 'Aksesoris Headset 3D'],
    prdSection: 'PRD Sec 53.7',
    modelCount: 680
  },
  {
    id: 8,
    name: 'Portal & Navigation',
    englishTitle: 'Warp Gates & Beacons',
    icon: '🌀',
    badge: 'PORTAL WARP',
    color: 'from-cyan-500 to-blue-600',
    description: 'Gerbang warp teleportasi multi-distrik, suar penanda (beacons), pilar arah, dan jangkar navigasi wayfinding.',
    itemsSample: ['Warp Pad Lingkaran', 'Pilar Suar Bercahaya', 'Gerbang Portal Cincin', 'Kompas Penunjuk Arah'],
    prdSection: 'PRD Sec 53.8',
    modelCount: 115
  },
  {
    id: 9,
    name: 'Spatial FX & Visual Effects',
    englishTitle: 'Particles, Auras & Energy',
    icon: '✨',
    badge: 'SPATIAL FX',
    color: 'from-amber-400 to-yellow-600',
    description: 'Efek partikel pendaran, aura magis avatar, jejak langkah cahaya, cincin energi, dan transisi portal halus.',
    itemsSample: ['Partikel Kilau Kristal', 'Aura Cahaya Avatar', 'Kabut Lembut Pastel', 'Cincin Gelombang Suara'],
    prdSection: 'PRD Sec 53.9',
    modelCount: 230
  },
  {
    id: 10,
    name: 'Interior & Furniture',
    englishTitle: 'Chairs, Desks & Props',
    icon: '🪑',
    badge: 'FURNITUR 3D',
    color: 'from-lime-500 to-green-600',
    description: 'Kursi santai pod melengkung, meja kerja holografik, lentera clay, sofa melingkar, dan prop dekorasi studio.',
    itemsSample: ['Pod Chair Melengkung', 'Meja Studio Melayang', 'Lampu Bola Ambient', 'Sofa Komunal Pastel'],
    prdSection: 'PRD Sec 53.10',
    modelCount: 375
  },
  {
    id: 11,
    name: 'UI Props & Holograms',
    englishTitle: 'Panels, HUD & Videotrons',
    icon: '📱',
    badge: 'HOLOGRAFIS & UI',
    color: 'from-fuchsia-500 to-pink-600',
    description: 'Layar videotron melengkung, panel data mengambang, frame display neon, widget status akun, dan spatial HUD.',
    itemsSample: ['Curved Videotron Billboard', 'Floating Credit Widget', 'Hologram Status Card', 'Bubble Chat Spatial'],
    prdSection: 'PRD Sec 53.11',
    modelCount: 290
  },
  {
    id: 12,
    name: 'Interactive Objects',
    englishTitle: 'Switches, Triggers & Pointers',
    icon: '🕹️',
    badge: 'OBJEK INTERAKTIF',
    color: 'from-red-500 to-rose-600',
    description: 'Pintu geser otomatis, tuas aktivasi energi, pointer laser presentasi, terminal belanja, dan kotak kejutan.',
    itemsSample: ['Tombol Warp Teleport', 'Tuas Pembangkit Cahaya', 'Pointer Laser Presentasi', 'Pintu Sensor Otomatis'],
    prdSection: 'PRD Sec 53.12',
    modelCount: 164
  },
  {
    id: 13,
    name: 'Collectibles & Rewards',
    englishTitle: 'Trophies, Crystals & Badges',
    icon: '🏆',
    badge: 'REWARD & TROFI',
    color: 'from-yellow-500 to-amber-600',
    description: 'Piala emas kreator 3D, medali royalti film 90%, kristal kuantum reward, lencana achievement, dan artefak langka.',
    itemsSample: ['Piala Kreator Film 90%', 'Kristal AI Credits Emas', 'Lencana Master Builder', 'Medali Verifikasi Resmi'],
    prdSection: 'PRD Sec 53.13',
    modelCount: 220
  },
  {
    id: 14,
    name: 'Materials, Lighting & Theme FX',
    englishTitle: 'PBR Shaders & Atmospheres',
    icon: '🎨',
    badge: 'MATERIAL & SHADER',
    color: 'from-violet-500 to-purple-600',
    description: 'Shader GLSL custom, profil pencahayaan studio lembut, material tanah liat (clay PBR), dan grading tema warna.',
    itemsSample: ['Menggu Soft Clay Shader', 'Pastel Emissive Glow', 'PBR Quartz Roughness', 'Atmospheric Fog Gradient'],
    prdSection: 'PRD Sec 53.14',
    modelCount: 188
  }
];

interface Menggu3DUniverseGalleryProps {
  onWarpToDistrict: (districtName: string) => void;
  onApplyTheme?: (themeName: string) => void;
}

export default function Menggu3DUniverseGallery({
  onWarpToDistrict,
  onApplyTheme
}: Menggu3DUniverseGalleryProps) {
  const [selectedAsset, setSelectedAsset] = useState<MengguAssetHighlight | null>(null);
  const [activeSubTab, setActiveSubTab] = useState<'HIGHLIGHTS' | 'CANONICAL_14' | 'GLB_STUDIO'>('HIGHLIGHTS');
  const [selectedCategory, setSelectedCategory] = useState<CanonicalCategory3D | null>(null);
  const [viewerModalItem, setViewerModalItem] = useState<MengguViewerItem | null>(null);
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  // GLB Generator Studio state
  const [generatingAssetId, setGeneratingAssetId] = useState<string | null>(null);
  const [batchProgress, setBatchProgress] = useState<{ current: number; total: number; name: string } | null>(null);
  const [studioSelectedKey, setStudioSelectedKey] = useState<string>('district-spatial');
  const [studioColorTheme, setStudioColorTheme] = useState<string>('pastel');

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3500);
  };

  const handleInstantDownloadGLB = async (keyOrCategory: string | number, defaultName?: string) => {
    const assetKey = String(keyOrCategory);
    setGeneratingAssetId(assetKey);
    showToast(`Membuat & mengompresi aset 3D GLB Menggu...`);
    try {
      const result = await generateMengguAssetGLB(keyOrCategory, defaultName);
      downloadGLBBlob(result.blob, result.filename);
      showToast(`Sukses! Aset 3D "${result.filename}" (${result.sizeFormatted}) berhasil diunduh.`);
    } catch (err) {
      console.error('Error generating GLB:', err);
      showToast('Gagal membuat file GLB. Silakan coba kembali.');
    } finally {
      setGeneratingAssetId(null);
    }
  };

  const handleBatchDownloadAll14 = async () => {
    showToast('Memulai ekspor batch 14 Kategori Theme 3D Menggu Art...');
    setBatchProgress({ current: 0, total: 14, name: 'Menyiapkan...' });

    for (let i = 1; i <= 14; i++) {
      const cat = CANONICAL_14_CATEGORIES_3D.find((c) => c.id === i);
      const catName = cat ? cat.name : `Kategori_${i}`;
      setBatchProgress({ current: i, total: 14, name: catName });
      try {
        const result = await generateMengguAssetGLB(i, `allpha_canonical_${i}_${catName.toLowerCase().replace(/[^a-z0-9]/g, '_')}.glb`);
        downloadGLBBlob(result.blob, result.filename);
        await new Promise((r) => setTimeout(r, 650));
      } catch (err) {
        console.error(`Error in batch item ${i}:`, err);
      }
    }

    setBatchProgress(null);
    showToast('Semua 14 aset 3D GLB kategori berhasil di-generate & diunduh!');
  };

  const open3DViewerForAsset = (asset: MengguAssetHighlight) => {
    let builderType: MengguViewerItem['builderType'] = 'district';
    if (asset.id.includes('citadel')) builderType = 'citadel';
    else if (asset.id.includes('plaza')) builderType = 'plaza';
    else if (asset.id.includes('billboard')) builderType = 'billboard';
    else if (asset.id.includes('booth')) builderType = 'booth';
    else if (asset.id.includes('avatar')) builderType = 'avatar';

    setViewerModalItem({
      id: asset.id,
      name: asset.name,
      categoryTag: asset.categoryTag,
      categoryNumber: asset.categoryNumber,
      description: asset.description,
      specs: asset.specs,
      builderType,
    });
  };

  const open3DViewerForCanonical = (cat: CanonicalCategory3D) => {
    setViewerModalItem({
      id: `canonical-${cat.id}`,
      name: `${cat.name} — ${cat.englishTitle}`,
      categoryTag: `Kategori #${cat.id} (${cat.prdSection})`,
      categoryNumber: cat.id,
      description: cat.description,
      specs: {
        polycount: '15K - 35K Polygons',
        textures: '2K PBR Soft Clay Diffuse',
        format: 'Binary .GLB 2.0 Spatial',
        materials: 'Menggu Pastel Clay Shaders',
      },
      builderType: 'canonical',
      canonicalId: cat.id,
    });
  };

  return (
    <div className="space-y-6">
      {/* Toast Notification */}
      {toastMsg && (
        <div className="fixed top-5 left-1/2 -translate-x-1/2 z-60 px-4 py-2.5 rounded-full bg-slate-900 text-white text-xs font-black shadow-2xl border-2 border-slate-700 flex items-center gap-2 animate-in fade-in slide-in-from-top-2">
          <span className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-ping" />
          <span>{toastMsg}</span>
        </div>
      )}

      {/* Batch Progress Banner if running */}
      {batchProgress && (
        <div className="p-4 rounded-3xl bg-slate-900 border-2 border-cyan-400 text-white shadow-2xl flex items-center justify-between gap-4 animate-in fade-in">
          <div className="flex items-center gap-3">
            <Loader2 className="w-5 h-5 text-cyan-400 animate-spin shrink-0" />
            <div>
              <h4 className="text-xs font-black text-cyan-300">
                Batch Generator 14 Kategori GLB ({batchProgress.current} / {batchProgress.total})
              </h4>
              <p className="text-[11px] text-slate-300">
                Sedang mengompresi: <strong>{batchProgress.name}</strong>
              </p>
            </div>
          </div>
          <div className="w-24 sm:w-36 bg-slate-800 h-2.5 rounded-full overflow-hidden border border-slate-700 shrink-0">
            <div
              className="bg-gradient-to-r from-cyan-400 to-emerald-400 h-full transition-all duration-300"
              style={{ width: `${(batchProgress.current / batchProgress.total) * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* Hero Banner: 3D Menggu Art Spatial Living World */}
      <div className="relative rounded-3xl overflow-hidden border-3 border-slate-900 bg-[#FEF08A] text-slate-950 p-5 sm:p-6 shadow-[6px_6px_0px_#0f172a]">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-2 max-w-xl">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="px-3 py-1 rounded-full bg-white border-2 border-slate-900 text-[10px] font-black uppercase tracking-wider shadow-[1.5px_1.5px_0px_#0f172a] flex items-center gap-1">
                <Sparkles className="w-3 h-3 text-amber-500" />
                3D MENGGU ART SPATIAL
              </span>
              <span className="px-2.5 py-0.5 rounded-full bg-[#BAE6FD] border border-slate-900 text-[10px] font-mono font-bold">
                PRD Sec 53 • 14 Kategori
              </span>
              <span className="px-2.5 py-0.5 rounded-full bg-[#BBF7D0] border border-slate-900 text-[10px] font-mono font-bold text-emerald-950">
                GLTF 2.0 / GLB Binary
              </span>
            </div>
            
            <h2 className="text-xl sm:text-2xl font-black tracking-tight leading-tight">
              Dunia Virtual 3D Spatial, Landmarks, Gedung, Plaza & Booth Menggu Art
            </h2>
            
            <p className="text-xs sm:text-sm font-semibold text-slate-800 leading-relaxed">
              Koleksi aset arsitektur spatial bertema clay pastel Menggu: distrik kota bertingkat, menara Crystal Citadel, AI Plaza air mancur hologram, curved videotron billboard, stan booth toko 3D, dan generator aset GLB siap ekspor.
            </p>
          </div>

          {/* Sub-Tabs Selector */}
          <div className="flex sm:flex-col gap-2 shrink-0">
            <button
              onClick={() => setActiveSubTab('HIGHLIGHTS')}
              className={`px-4 py-2.5 rounded-2xl font-black text-xs border-2 border-slate-900 transition cursor-pointer flex items-center justify-center gap-1.5 active:translate-x-0.5 active:translate-y-0.5 ${
                activeSubTab === 'HIGHLIGHTS'
                  ? 'bg-slate-950 text-white shadow-[2px_2px_0px_#0f172a]'
                  : 'bg-white hover:bg-slate-100 text-slate-900'
              }`}
            >
              <Building2 className="w-4 h-4" />
              <span>Landmark & Distrik</span>
            </button>

            <button
              onClick={() => setActiveSubTab('CANONICAL_14')}
              className={`px-4 py-2.5 rounded-2xl font-black text-xs border-2 border-slate-900 transition cursor-pointer flex items-center justify-center gap-1.5 active:translate-x-0.5 active:translate-y-0.5 ${
                activeSubTab === 'CANONICAL_14'
                  ? 'bg-slate-950 text-white shadow-[2px_2px_0px_#0f172a]'
                  : 'bg-white hover:bg-slate-100 text-slate-900'
              }`}
            >
              <Layers className="w-4 h-4" />
              <span>14 Kategori Theme 3D</span>
            </button>

            <button
              onClick={() => setActiveSubTab('GLB_STUDIO')}
              className={`px-4 py-2.5 rounded-2xl font-black text-xs border-2 border-slate-900 transition cursor-pointer flex items-center justify-center gap-1.5 active:translate-x-0.5 active:translate-y-0.5 ${
                activeSubTab === 'GLB_STUDIO'
                  ? 'bg-slate-950 text-cyan-300 shadow-[2px_2px_0px_#0f172a]'
                  : 'bg-white hover:bg-slate-100 text-slate-900'
              }`}
            >
              <Box className="w-4 h-4 text-cyan-500" />
              <span>⚡ Studio Generator GLB</span>
            </button>
          </div>
        </div>
      </div>

      {/* ===================================================================== */}
      {/* VIEW A: 5 MENGGU 3D SPATIAL LANDMARKS & DISTRICTS                     */}
      {/* ===================================================================== */}
      {activeSubTab === 'HIGHLIGHTS' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-cyan-400 border border-slate-900" />
              <h3 className="text-sm font-black text-white">5 Landmark Spatial 3D Menggu Utama</h3>
            </div>
            <span className="text-xs font-bold text-slate-400">Klik kartu untuk inspeksi & warp 3D</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {MENGGU_SPATIAL_ASSETS.map((asset) => (
              <div
                key={asset.id}
                onClick={() => setSelectedAsset(asset)}
                className="group rounded-3xl bg-white border-3 border-slate-900 shadow-[4px_4px_0px_#0f172a] hover:shadow-[6px_6px_0px_#0f172a] transition overflow-hidden flex flex-col cursor-pointer text-slate-950 active:translate-x-0.5 active:translate-y-0.5"
              >
                {/* Visual Image Preview */}
                <div className="relative aspect-4/3 bg-slate-100 overflow-hidden border-b-2 border-slate-900">
                  <img
                    src={asset.image}
                    alt={asset.name}
                    loading="eager"
                    className="w-full h-full object-cover group-hover:scale-105 transition duration-500"
                  />
                  
                  {/* Badges */}
                  <div className="absolute top-3 left-3 right-3 flex items-center justify-between gap-1 pointer-events-none">
                    <span className={`px-2.5 py-0.5 rounded-full ${asset.badgeColor} border-2 border-slate-900 text-[10px] font-black uppercase tracking-wider shadow-[1.5px_1.5px_0px_#0f172a]`}>
                      {asset.badge}
                    </span>
                    <span className="px-2 py-0.5 rounded-full bg-white/95 text-slate-900 text-[10px] font-black border border-slate-900 shadow-xs flex items-center gap-1">
                      <Eye className="w-3 h-3 text-cyan-600" />
                      <span>3D Preview</span>
                    </span>
                  </div>

                  <div className="absolute bottom-2 left-3 right-3 pointer-events-none">
                    <span className="text-[10px] font-mono font-bold text-white bg-black/70 backdrop-blur px-2 py-0.5 rounded-md border border-white/20">
                      📍 {asset.districtCoordinates}
                    </span>
                  </div>
                </div>

                {/* Card Body */}
                <div className="p-4 flex-1 flex flex-col justify-between space-y-3">
                  <div>
                    <h4 className="font-black text-sm text-slate-950 group-hover:text-blue-600 transition leading-snug">
                      {asset.name}
                    </h4>
                    <p className="text-[11px] font-semibold text-slate-600 line-clamp-2 mt-1">
                      {asset.description}
                    </p>
                  </div>

                  {/* Highlights Pill Tags */}
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {asset.features.slice(0, 2).map((feat, i) => (
                      <span
                        key={i}
                        className="text-[10px] font-bold px-2 py-0.5 rounded-lg bg-slate-100 border border-slate-300 text-slate-700"
                      >
                        ✓ {feat}
                      </span>
                    ))}
                  </div>

                  {/* Footer Actions */}
                  <div className="pt-2 border-t border-slate-200 flex items-center justify-between gap-1.5 flex-wrap">
                    <button
                      type="button"
                      disabled={generatingAssetId === asset.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleInstantDownloadGLB(asset.id, `${asset.id}.glb`);
                      }}
                      className="px-2.5 py-1.5 rounded-xl bg-cyan-400 hover:bg-cyan-300 text-slate-950 font-black text-[10.5px] border border-slate-900 shadow-2xs transition flex items-center gap-1 active:scale-95 cursor-pointer disabled:opacity-50"
                      title="Download file binary 3D GLB"
                    >
                      {generatingAssetId === asset.id ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        <Download className="w-3 h-3 stroke-[2.5px]" />
                      )}
                      <span>{generatingAssetId === asset.id ? 'Packing...' : 'Unduh GLB'}</span>
                    </button>

                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        open3DViewerForAsset(asset);
                      }}
                      className="px-2.5 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-black text-[10.5px] border border-slate-900 shadow-2xs transition flex items-center gap-1 active:scale-95 cursor-pointer"
                    >
                      <Box className="w-3 h-3 text-cyan-300" />
                      <span>3D Preview</span>
                    </button>
                    
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onWarpToDistrict(asset.targetDistrict);
                        showToast(`Warping ke ${asset.name}...`);
                      }}
                      className="px-3 py-1.5 rounded-xl bg-[#FEF08A] hover:bg-amber-300 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] transition flex items-center gap-1 active:scale-95 cursor-pointer"
                    >
                      <Play className="w-3 h-3 fill-slate-950" />
                      <span>Kunjungi</span>
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* VIEW B: 14 CANONICAL CATEGORIES (Master PRD Section 53)               */}
      {/* ===================================================================== */}
      {activeSubTab === 'CANONICAL_14' && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 bg-slate-900/90 border-2 border-slate-800 p-3.5 rounded-3xl text-white">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-emerald-400 border border-slate-900" />
              <div>
                <h3 className="text-sm font-black text-white">14 Kategori Kanonikal Aset 3D (PRD Section 53)</h3>
                <span className="text-[11px] font-bold text-slate-400">Total 3,900+ model siap generate ke format GLTF 2.0 / GLB</span>
              </div>
            </div>

            <button
              type="button"
              disabled={Boolean(batchProgress)}
              onClick={handleBatchDownloadAll14}
              className="px-4 py-2 rounded-2xl bg-cyan-400 hover:bg-cyan-300 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] transition flex items-center justify-center gap-1.5 cursor-pointer active:scale-95 disabled:opacity-50 shrink-0"
            >
              {batchProgress ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Mengekspor ({batchProgress.current}/14)...</span>
                </>
              ) : (
                <>
                  <Download className="w-3.5 h-3.5 stroke-[2.5px]" />
                  <span>Unduh Semua 14 Kategori (.GLB)</span>
                </>
              )}
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {CANONICAL_14_CATEGORIES_3D.map((cat) => (
              <div
                key={cat.id}
                onClick={() => setSelectedCategory(cat)}
                className="p-4 rounded-3xl bg-white border-3 border-slate-900 shadow-[3px_3px_0px_#0f172a] hover:shadow-[5px_5px_0px_#0f172a] transition cursor-pointer text-slate-950 flex flex-col justify-between space-y-3 group active:translate-x-0.5 active:translate-y-0.5"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="w-10 h-10 rounded-2xl bg-slate-100 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] flex items-center justify-center text-xl shrink-0">
                      {cat.icon}
                    </span>
                    <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-slate-100 border border-slate-900 text-slate-800">
                      {cat.prdSection}
                    </span>
                  </div>

                  <div>
                    <div className="flex items-center gap-1.5">
                      <span className="w-4 h-4 rounded-full bg-slate-950 text-white font-mono font-black text-[10px] flex items-center justify-center shrink-0">
                        {cat.id}
                      </span>
                      <h4 className="font-black text-sm text-slate-950 group-hover:text-blue-600 transition">
                        {cat.name}
                      </h4>
                    </div>
                    <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mt-0.5">
                      {cat.englishTitle}
                    </p>
                  </div>

                  <p className="text-[11px] font-semibold text-slate-700 leading-relaxed">
                    {cat.description}
                  </p>
                </div>

                {/* Samples and Model Count */}
                <div className="pt-2 border-t border-slate-200 flex items-center justify-between gap-1 text-xs flex-wrap">
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      disabled={generatingAssetId === `cat-${cat.id}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleInstantDownloadGLB(cat.id, `canonical_cat_${cat.id}_${cat.name.toLowerCase().replace(/[^a-z0-9]/g, '_')}.glb`);
                      }}
                      className="px-2.5 py-1.5 rounded-xl bg-cyan-400 hover:bg-cyan-300 text-slate-950 font-black text-[10px] border border-slate-900 shadow-2xs flex items-center gap-1 active:scale-95 cursor-pointer disabled:opacity-50"
                      title="Download format 3D GLB binary"
                    >
                      {generatingAssetId === String(cat.id) ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        <Download className="w-3 h-3 stroke-[2.5px]" />
                      )}
                      <span>GLB</span>
                    </button>

                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        open3DViewerForCanonical(cat);
                      }}
                      className="px-2.5 py-1.5 rounded-xl bg-[#FEF08A] hover:bg-amber-300 text-slate-950 font-black text-[10px] border border-slate-900 shadow-2xs flex items-center gap-1 active:scale-95 cursor-pointer"
                    >
                      <Box className="w-3 h-3 text-slate-950" />
                      <span>Preview 3D</span>
                    </button>
                  </div>

                  <span className="text-xs font-black text-blue-600 flex items-center gap-1 group-hover:translate-x-0.5 transition">
                    <span>Detail</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* VIEW C: STUDIO GENERATOR ASET 3D GLB SPATIAL INTERAKTIF               */}
      {/* ===================================================================== */}
      {activeSubTab === 'GLB_STUDIO' && (
        <div className="space-y-5">
          <div className="p-5 rounded-3xl bg-slate-900 border-3 border-slate-800 text-white shadow-2xl space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <span className="text-[10px] font-mono font-bold text-cyan-400 uppercase tracking-wider flex items-center gap-1">
                  <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
                  INTERACTIVE 3D MENGGU ART STUDIO
                </span>
                <h3 className="text-lg sm:text-xl font-black text-white mt-0.5">
                  Generator Aset 3D GLB Spatial Allpha Universe
                </h3>
                <p className="text-xs text-slate-300 mt-1">
                  Generate dan unduh file binary 3D (.GLB) procedural Menggu Art siap impor ke Blender, Unreal Engine, Unity, Three.js, atau pasang di booth toko Crystal City.
                </p>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  disabled={Boolean(batchProgress)}
                  onClick={handleBatchDownloadAll14}
                  className="px-3.5 py-2 rounded-xl bg-cyan-400 hover:bg-cyan-300 text-slate-950 font-black text-xs border border-cyan-300 shadow-md flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Batch Export 14 Kategori</span>
                </button>
              </div>
            </div>

            {/* Step 1: Select Model Preset */}
            <div className="space-y-2 pt-2 border-t border-slate-800">
              <label className="text-xs font-black text-slate-300 flex items-center gap-1.5">
                <Building2 className="w-4 h-4 text-cyan-400" />
                <span>1. Pilih Aset 3D Menggu yang Ingin di-Generate:</span>
              </label>

              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2">
                {[
                  { id: 'district-spatial', label: 'Metropolis District', icon: '🏙️' },
                  { id: 'landmark-citadel', label: 'Crystal Citadel', icon: '🗼' },
                  { id: 'plaza-fountain', label: 'AI Plaza Fountain', icon: '⛲' },
                  { id: 'billboard-videotron', label: 'Curved Videotron', icon: '📺' },
                  { id: 'booth-tenant', label: 'Modular Booth', icon: '🛍️' },
                  { id: 'avatar-menggu', label: 'Articulated Avatar', icon: '🧑‍🚀' },
                ].map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setStudioSelectedKey(item.id)}
                    className={`p-2.5 rounded-2xl border-2 font-black text-xs flex flex-col items-center justify-center gap-1 transition cursor-pointer text-center ${
                      studioSelectedKey === item.id
                        ? 'bg-[#FEF08A] text-slate-950 border-amber-400 shadow-md scale-[1.02]'
                        : 'bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-750'
                    }`}
                  >
                    <span className="text-lg">{item.icon}</span>
                    <span className="truncate w-full leading-tight">{item.label}</span>
                  </button>
                ))}
              </div>

              {/* 14 Canonical Category Quick Chips */}
              <div className="pt-2">
                <span className="text-[11px] font-bold text-slate-400 block mb-1.5">
                  Atau pilih dari 14 Kategori Kanonikal (PRD Sec 53):
                </span>
                <div className="flex items-center gap-1.5 overflow-x-auto pb-2 no-scrollbar">
                  {CANONICAL_14_CATEGORIES_3D.map((c) => (
                    <button
                      key={c.id}
                      type="button"
                      onClick={() => setStudioSelectedKey(`cat-${c.id}`)}
                      className={`px-2.5 py-1 rounded-xl text-[10.5px] font-bold whitespace-nowrap border transition cursor-pointer flex items-center gap-1 shrink-0 ${
                        studioSelectedKey === `cat-${c.id}`
                          ? 'bg-cyan-400 text-slate-950 border-cyan-300 font-black shadow-xs'
                          : 'bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700'
                      }`}
                    >
                      <span>{c.icon}</span>
                      <span>#{c.id} {c.name.split(' ')[0]}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Step 2: Live Specification & Action Banner */}
            <div className="p-4 rounded-2xl bg-slate-950/80 border border-slate-800 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded-md bg-cyan-500/20 text-cyan-300 font-mono text-[10px] font-bold uppercase border border-cyan-500/40">
                    ASET AKTIF: {studioSelectedKey.toUpperCase()}
                  </span>
                  <span className="text-[10px] text-slate-400 font-mono">
                    Binary GLTF 2.0 (.GLB)
                  </span>
                </div>
                <h4 className="font-black text-sm text-white">
                  Siap generate aset 3D spatial berbasis Three.js PBR Menggu Art
                </h4>
                <p className="text-[11px] text-slate-400">
                  Kompatibel dengan semua web viewer, Spatial Metaverse, Blender, dan WebXR.
                </p>
              </div>

              <div className="flex items-center gap-2 flex-wrap">
                <button
                  type="button"
                  disabled={generatingAssetId === studioSelectedKey}
                  onClick={() => {
                    const isCat = studioSelectedKey.startsWith('cat-');
                    const target = isCat ? parseInt(studioSelectedKey.replace('cat-', ''), 10) : studioSelectedKey;
                    handleInstantDownloadGLB(target, `${studioSelectedKey}_menggu.glb`);
                  }}
                  className="flex-1 sm:flex-none px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-400 to-blue-500 hover:from-cyan-300 hover:to-blue-400 font-black text-xs text-slate-950 border border-cyan-300 shadow-[0_0_15px_rgba(34,211,238,0.3)] cursor-pointer flex items-center justify-center gap-1.5 transition-all active:scale-95 disabled:opacity-50"
                >
                  {generatingAssetId === studioSelectedKey ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Packing GLB...</span>
                    </>
                  ) : (
                    <>
                      <Download className="w-3.5 h-3.5 stroke-[2.5px]" />
                      <span>Generate & Unduh (.GLB)</span>
                    </>
                  )}
                </button>

                <button
                  type="button"
                  onClick={() => {
                    const isCat = studioSelectedKey.startsWith('cat-');
                    if (isCat) {
                      const id = parseInt(studioSelectedKey.replace('cat-', ''), 10);
                      const cat = CANONICAL_14_CATEGORIES_3D.find((c) => c.id === id);
                      if (cat) open3DViewerForCanonical(cat);
                    } else {
                      const asset = MENGGU_SPATIAL_ASSETS.find((a) => a.id === studioSelectedKey);
                      if (asset) open3DViewerForAsset(asset);
                      else {
                        setViewerModalItem({
                          id: studioSelectedKey,
                          name: studioSelectedKey,
                          categoryTag: '3D Menggu Art',
                          description: 'Model 3D Menggu Art procedural.',
                        });
                      }
                    }
                  }}
                  className="flex-1 sm:flex-none px-3.5 py-2.5 rounded-xl bg-[#FEF08A] hover:bg-amber-300 font-black text-xs text-slate-950 border border-amber-300 shadow-md cursor-pointer flex items-center justify-center gap-1.5 transition-all active:scale-95"
                >
                  <Eye className="w-3.5 h-3.5" />
                  <span>Inspektor 3D</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* MODAL 1: INSPECT 3D MENGGU ASSET DETAILS                              */}
      {/* ===================================================================== */}
      {selectedAsset && (
        <div className="fixed inset-0 z-60 flex items-center justify-center p-3 sm:p-5 bg-black/85 backdrop-blur-md animate-in fade-in duration-200">
          <div className="w-full max-w-2xl bg-white rounded-3xl border-3 border-slate-900 shadow-[8px_8px_0px_#0f172a] overflow-hidden flex flex-col max-h-[92dvh] text-slate-950">
            {/* Modal Header */}
            <div className="p-4 bg-[#FEF08A] border-b-2 border-slate-900 flex items-center justify-between">
              <div className="flex items-center gap-2 min-w-0">
                <span className={`px-2.5 py-0.5 rounded-full ${selectedAsset.badgeColor} border-2 border-slate-900 text-[10px] font-black uppercase tracking-wider shadow-[1.5px_1.5px_0px_#0f172a]`}>
                  {selectedAsset.badge}
                </span>
                <h3 className="font-black text-sm text-slate-950 truncate">
                  {selectedAsset.name}
                </h3>
              </div>
              <button
                onClick={() => setSelectedAsset(null)}
                className="w-8 h-8 rounded-xl bg-white hover:bg-slate-100 border-2 border-slate-900 flex items-center justify-center cursor-pointer shadow-[1.5px_1.5px_0px_#0f172a] shrink-0"
              >
                <X className="w-4 h-4 stroke-[2.5px]" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="flex-1 min-h-0 overflow-y-auto p-4 sm:p-6 space-y-4">
              {/* Large Image Preview with 3D Menggu Art */}
              <div className="relative rounded-2xl overflow-hidden border-2 border-slate-900 bg-slate-100 shadow-[3px_3px_0px_#0f172a] aspect-16/10">
                <img
                  src={selectedAsset.image}
                  alt={selectedAsset.name}
                  className="w-full h-full object-cover"
                />
                <div className="absolute top-3 left-3 px-3 py-1 rounded-full bg-white/95 text-slate-950 text-[10px] font-black border border-slate-900 shadow-xs flex items-center gap-1.5">
                  <Sparkles className="w-3 h-3 text-amber-500" />
                  <span>3D Menggu Art Render PBR</span>
                </div>
              </div>

              {/* Descriptions & Specs */}
              <div className="space-y-3">
                <div>
                  <span className="text-[10px] font-mono text-cyan-800 font-bold uppercase tracking-wider">
                    {selectedAsset.tagline}
                  </span>
                  <h4 className="text-lg font-black text-slate-950">
                    {selectedAsset.name}
                  </h4>
                  <p className="text-xs font-semibold text-slate-700 leading-relaxed mt-1">
                    {selectedAsset.description}
                  </p>
                </div>

                {/* Features Bullet List */}
                <div className="p-3.5 rounded-2xl bg-slate-50 border-2 border-slate-900 space-y-2">
                  <h5 className="font-black text-xs text-slate-900 flex items-center gap-1.5">
                    <Check className="w-3.5 h-3.5 text-emerald-600 stroke-[3px]" />
                    <span>Fitur Arsitektur & Interaksi 3D</span>
                  </h5>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] font-semibold text-slate-700">
                    {selectedAsset.features.map((feat, i) => (
                      <div key={i} className="flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-slate-900 shrink-0" />
                        <span>{feat}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Technical 3D Metadata Specs */}
                <div className="p-3.5 rounded-2xl bg-sky-50 border-2 border-slate-900 space-y-2">
                  <h5 className="font-black text-xs text-slate-900 flex items-center gap-1.5">
                    <Box className="w-3.5 h-3.5 text-sky-700 stroke-[2.5px]" />
                    <span>Spesifikasi Engine 3D & GLTF Schema</span>
                  </h5>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center text-xs">
                    <div className="p-2 rounded-xl bg-white border border-slate-900 shadow-2xs">
                      <span className="text-[9px] font-bold text-slate-500 block">Polygon Budget</span>
                      <strong className="text-slate-950 text-[11px]">{selectedAsset.specs.polycount}</strong>
                    </div>
                    <div className="p-2 rounded-xl bg-white border border-slate-900 shadow-2xs">
                      <span className="text-[9px] font-bold text-slate-500 block">Tekstur PBR</span>
                      <strong className="text-slate-950 text-[11px]">{selectedAsset.specs.textures}</strong>
                    </div>
                    <div className="p-2 rounded-xl bg-white border border-slate-900 shadow-2xs">
                      <span className="text-[9px] font-bold text-slate-500 block">Format File</span>
                      <strong className="text-slate-950 text-[11px]">{selectedAsset.specs.format}</strong>
                    </div>
                    <div className="p-2 rounded-xl bg-white border border-slate-900 shadow-2xs">
                      <span className="text-[9px] font-bold text-slate-500 block">Shading Material</span>
                      <strong className="text-slate-950 text-[11px]">{selectedAsset.specs.materials}</strong>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="p-4 bg-slate-50 border-t-2 border-slate-900 flex items-center justify-between gap-3 flex-wrap">
              <div className="text-[11px] font-bold text-slate-600 hidden sm:block">
                Lokasi: <strong className="text-slate-950">{selectedAsset.districtCoordinates}</strong>
              </div>

              <div className="flex items-center gap-2 w-full sm:w-auto flex-wrap">
                <button
                  type="button"
                  onClick={() => {
                    const asset = selectedAsset;
                    setSelectedAsset(null);
                    open3DViewerForAsset(asset);
                  }}
                  className="flex-1 sm:flex-none px-3.5 py-2.5 rounded-xl bg-cyan-400 hover:bg-cyan-300 font-black text-xs text-slate-950 border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] cursor-pointer flex items-center justify-center gap-1.5"
                >
                  <Box className="w-3.5 h-3.5" />
                  <span>Inspeksi 3D & Unduh GLB</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    if (onApplyTheme) onApplyTheme('Menggu 3D Pastel');
                    showToast('Tema Menggu 3D Pastel berhasil diaktifkan!');
                  }}
                  className="flex-1 sm:flex-none px-3.5 py-2.5 rounded-xl bg-white hover:bg-slate-100 font-black text-xs border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] cursor-pointer"
                >
                  Set Tema 3D
                </button>

                <button
                  type="button"
                  onClick={() => {
                    const target = selectedAsset.targetDistrict;
                    setSelectedAsset(null);
                    onWarpToDistrict(target);
                    showToast(`Warping ke ${selectedAsset.name}...`);
                  }}
                  className="flex-1 sm:flex-none px-4 py-2.5 rounded-xl bg-[#FEF08A] hover:bg-amber-300 font-black text-xs text-slate-950 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] cursor-pointer flex items-center justify-center gap-1.5"
                >
                  <Play className="w-3.5 h-3.5 fill-slate-950" />
                  <span>Warp ke 3D</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* MODAL 2: DETAIL CANONICAL CATEGORY 3D                                */}
      {/* ===================================================================== */}
      {selectedCategory && (
        <div className="fixed inset-0 z-60 flex items-center justify-center p-3 sm:p-5 bg-black/85 backdrop-blur-md animate-in fade-in duration-200">
          <div className="w-full max-w-lg bg-white rounded-3xl border-3 border-slate-900 shadow-[8px_8px_0px_#0f172a] overflow-hidden flex flex-col max-h-[90vh] text-slate-950">
            {/* Header */}
            <div className="p-4 bg-[#BAE6FD] border-b-2 border-slate-900 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-2xl">{selectedCategory.icon}</span>
                <div>
                  <h3 className="font-black text-sm text-slate-950 leading-tight">
                    Kategori #{selectedCategory.id}: {selectedCategory.name}
                  </h3>
                  <span className="text-[10px] font-bold text-slate-700 uppercase">
                    {selectedCategory.englishTitle}
                  </span>
                </div>
              </div>
              <button
                onClick={() => setSelectedCategory(null)}
                className="w-8 h-8 rounded-xl bg-white hover:bg-slate-100 border-2 border-slate-900 flex items-center justify-center cursor-pointer shadow-[1.5px_1.5px_0px_#0f172a]"
              >
                <X className="w-4 h-4 stroke-[2.5px]" />
              </button>
            </div>

            {/* Content */}
            <div className="p-5 space-y-4 overflow-y-auto">
              <div>
                <span className="text-[10px] font-mono font-bold text-blue-700 bg-blue-100 px-2 py-0.5 rounded border border-blue-300">
                  {selectedCategory.prdSection} • CANONICAL TAXONOMY
                </span>
                <p className="text-xs font-semibold text-slate-800 leading-relaxed mt-2">
                  {selectedCategory.description}
                </p>
              </div>

              <div className="p-4 rounded-2xl bg-slate-50 border-2 border-slate-900 space-y-2">
                <h5 className="font-black text-xs text-slate-950">Contoh Aset 3D Menggu & GLB:</h5>
                <div className="grid grid-cols-2 gap-2">
                  {selectedCategory.itemsSample.map((item, idx) => (
                    <div key={idx} className="p-2.5 rounded-xl bg-white border border-slate-900 text-[11px] font-bold shadow-2xs flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
                      <span className="truncate">{item}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="p-3.5 rounded-2xl bg-amber-50 border-2 border-slate-900 text-xs font-semibold text-amber-950 flex items-center gap-2.5">
                <Info className="w-4 h-4 text-amber-800 shrink-0" />
                <span>
                  Total aset terdaftar di registry: <strong>{selectedCategory.modelCount} model</strong> dengan format standardisasi GLTF 2.0 PBR Menggu.
                </span>
              </div>
            </div>

            <div className="p-4 bg-slate-50 border-t-2 border-slate-900 flex items-center justify-end gap-2 flex-wrap">
              <button
                type="button"
                onClick={() => setSelectedCategory(null)}
                className="px-4 py-2 rounded-xl bg-slate-200 hover:bg-slate-300 text-slate-900 font-black text-xs border-2 border-slate-900"
              >
                Tutup
              </button>
              <button
                type="button"
                onClick={() => {
                  const cat = selectedCategory;
                  setSelectedCategory(null);
                  open3DViewerForCanonical(cat);
                }}
                className="px-4 py-2 rounded-xl bg-[#FEF08A] hover:bg-amber-300 text-slate-950 font-black text-xs border-2 border-slate-900 shadow-[1.5px_1.5px_0px_#0f172a] flex items-center gap-1.5 cursor-pointer"
              >
                <Box className="w-3.5 h-3.5" />
                <span>Preview 3D & Unduh GLB</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* 3D MODEL VIEWER & GLB EXPORTER MODAL                                  */}
      {/* ===================================================================== */}
      {viewerModalItem && (
        <Menggu3DViewerModal
          item={viewerModalItem}
          onClose={() => setViewerModalItem(null)}
          onWarpToUniverse={(dName) => {
            setViewerModalItem(null);
            onWarpToDistrict(dName);
          }}
        />
      )}
    </div>
  );
}

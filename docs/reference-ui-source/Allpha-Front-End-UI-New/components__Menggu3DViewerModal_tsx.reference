'use client';

import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { 
  X, 
  Download, 
  RotateCw, 
  Layers, 
  Box, 
  Sparkles, 
  Check, 
  Play, 
  Maximize2,
  Minimize2,
  Compass,
  FileCode,
  Info,
  Loader2
} from 'lucide-react';
import { 
  exportObjectToGLB, 
  downloadGLBBlob, 
  createMengguDistrict, 
  createMengguCitadelTower, 
  createMengguPlazaFountain, 
  createMengguBillboardAds, 
  createMengguTenantBooth, 
  createMengguAvatar, 
  createCanonicalModelByCategory,
  getMengguModelByType 
} from '@/lib/menggu3dEngine';

export interface MengguViewerItem {
  id: string;
  name: string;
  categoryTag: string;
  categoryNumber?: number;
  badge?: string;
  description: string;
  polycount?: string;
  textures?: string;
  format?: string;
  targetDistrict?: string;
  builderType?: 'district' | 'citadel' | 'plaza' | 'billboard' | 'booth' | 'avatar' | 'canonical';
  canonicalId?: number;
  specs?: {
    polycount: string;
    textures: string;
    format: string;
    materials: string;
  };
}

export type MengguModelSpec = MengguViewerItem;

interface Menggu3DViewerModalProps {
  item?: MengguViewerItem;
  modelSpec?: MengguModelSpec;
  onClose: () => void;
  onWarpToDistrict?: (districtName: string) => void;
  onWarpToUniverse?: (districtName: string) => void;
}

export default function Menggu3DViewerModal({
  item,
  modelSpec,
  onClose,
  onWarpToDistrict,
  onWarpToUniverse,
}: Menggu3DViewerModalProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const activeMeshRef = useRef<THREE.Group | null>(null);

  const spec: MengguViewerItem = item || modelSpec || {
    id: 'landmark-citadel',
    name: 'Crystal Citadel',
    categoryTag: 'Landmark',
    badge: 'LANDMARK & GEDUNG',
    description: 'Pusat komputasi AI & menara observatorium Crystal City.',
  };

  const [isGeneratingGLB, setIsGeneratingGLB] = useState(false);
  const [downloadSuccess, setDownloadSuccess] = useState(false);
  const [autoRotate, setAutoRotate] = useState(true);
  const [isWireframe, setIsWireframe] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Stats
  const [stats, setStats] = useState({
    polys: spec.polycount || spec.specs?.polycount || '24.5K',
    vertices: '18.2K',
    materials: spec.specs?.materials || 'PBR Soft Pastel Clay',
    dimensions: '12m x 18m x 12m',
  });

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Dimensions
    const width = container.clientWidth || 640;
    const height = container.clientHeight || 420;

    // Three Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0f1d);

    // Camera
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 500);
    camera.position.set(20, 16, 24);

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.25;
    container.innerHTML = '';
    container.appendChild(renderer.domElement);

    // Orbit Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.autoRotate = autoRotate;
    controls.autoRotateSpeed = 1.5;
    controls.maxDistance = 140;
    controls.minDistance = 2;

    // Lighting (Warm Studio Menggu Soft Lighting)
    const ambLight = new THREE.AmbientLight(0xffffff, 1.4);
    scene.add(ambLight);

    const dirLight1 = new THREE.DirectionalLight(0xfef08a, 1.8); // Butter warm yellow key
    dirLight1.position.set(20, 30, 20);
    scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0x22d3ee, 1.2); // Cyan rim light
    dirLight2.position.set(-20, 20, -20);
    scene.add(dirLight2);

    const dirLight3 = new THREE.DirectionalLight(0xddd6fe, 0.8); // Lavender fill light
    dirLight3.position.set(0, -10, 20);
    scene.add(dirLight3);

    // Ground Grid Helper
    const gridHelper = new THREE.GridHelper(50, 20, 0x22d3ee, 0x1e293b);
    gridHelper.position.y = -0.05;
    scene.add(gridHelper);

    // Instantiate Procedural 3D Menggu Model based on ID, BuilderType, or Category
    let modelGroup: THREE.Group;

    if (spec.builderType === 'district' || spec.id.includes('district')) {
      modelGroup = createMengguDistrict();
      camera.position.set(45, 32, 45);
      controls.target.set(0, 8, 0);
    } else if (spec.builderType === 'citadel' || spec.id.includes('citadel')) {
      modelGroup = createMengguCitadelTower();
      camera.position.set(28, 30, 32);
      controls.target.set(0, 24, 0);
    } else if (spec.builderType === 'plaza' || spec.id.includes('plaza')) {
      modelGroup = createMengguPlazaFountain();
      camera.position.set(24, 14, 24);
      controls.target.set(0, 3, 0);
    } else if (spec.builderType === 'billboard' || spec.id.includes('billboard')) {
      modelGroup = createMengguBillboardAds();
      camera.position.set(0, 22, 28);
      controls.target.set(0, 20, 0);
    } else if (spec.builderType === 'booth' || spec.id.includes('booth')) {
      modelGroup = createMengguTenantBooth({ name: 'ALLPHA SPATIAL', category: 'Official Store' });
      camera.position.set(10, 7, 10);
      controls.target.set(0, 3, 0);
    } else if (spec.builderType === 'avatar' || spec.id.includes('avatar')) {
      modelGroup = createMengguAvatar();
      camera.position.set(5, 4, 6);
      controls.target.set(0, 3, 0);
    } else if (spec.canonicalId || spec.categoryNumber) {
      modelGroup = createCanonicalModelByCategory(spec.canonicalId || spec.categoryNumber || 1);
      camera.position.set(8, 6, 8);
      controls.target.set(0, 2, 0);
    } else {
      modelGroup = getMengguModelByType(spec.id);
      camera.position.set(12, 10, 12);
      controls.target.set(0, 3, 0);
    }

    scene.add(modelGroup);
    activeMeshRef.current = modelGroup;

    // Calculate real geometry metrics
    let polyCount = 0;
    let vertCount = 0;
    modelGroup.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        const geom = (child as THREE.Mesh).geometry;
        if (geom) {
          if (geom.index) {
            polyCount += geom.index.count / 3;
          } else if (geom.attributes.position) {
            polyCount += geom.attributes.position.count / 3;
          }
          if (geom.attributes.position) {
            vertCount += geom.attributes.position.count;
          }
        }
      }
    });

    setStats({
      polys: polyCount > 0 ? `${(polyCount / 1000).toFixed(1)}K Polygons` : (spec.polycount || spec.specs?.polycount || '18.4K'),
      vertices: vertCount > 0 ? `${(vertCount / 1000).toFixed(1)}K Vertices` : '14.2K',
      materials: spec.specs?.materials || 'Menggu Soft Pastel Clay (PBR)',
      dimensions: 'Standard Spatial Box',
    });

    // Animation Loop
    let animId: number;
    const clock = new THREE.Clock();

    const animate = () => {
      animId = requestAnimationFrame(animate);
      const elapsed = clock.getElapsedTime();

      // Subtle dynamic animations
      const crown = modelGroup.getObjectByName('CitadelCrownRing');
      if (crown) {
        crown.rotation.z += 0.015;
      }

      const lotus = modelGroup.getObjectByName('FloatingLotus');
      if (lotus) {
        lotus.rotation.y += 0.008;
        lotus.position.y = 4.2 + Math.sin(elapsed * 2) * 0.25;
      }

      const gem = modelGroup.getObjectByName('BoothShowcaseGem');
      if (gem) {
        gem.rotation.y += 0.02;
        gem.rotation.x = Math.sin(elapsed) * 0.15;
      }

      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    // Resize Handler
    const handleResize = () => {
      if (!container) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animId);
      controls.dispose();
      renderer.dispose();
    };
  }, [spec, autoRotate]);

  // Wireframe toggler
  useEffect(() => {
    if (!activeMeshRef.current) return;
    activeMeshRef.current.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        const mat = (child as THREE.Mesh).material;
        if (Array.isArray(mat)) {
          mat.forEach((m) => {
            if ('wireframe' in m) {
              (m as unknown as { wireframe: boolean }).wireframe = isWireframe;
            }
          });
        } else if (mat && 'wireframe' in mat) {
          (mat as unknown as { wireframe: boolean }).wireframe = isWireframe;
        }
      }
    });
  }, [isWireframe]);

  // Handle Real GLB Export
  const handleExportGLB = async () => {
    if (!activeMeshRef.current) return;
    setIsGeneratingGLB(true);
    setDownloadSuccess(false);

    try {
      const fileName = `${spec.id || 'menggu_model'}_spatial.glb`;
      const blob = await exportObjectToGLB(activeMeshRef.current, fileName);
      downloadGLBBlob(blob, fileName);
      setDownloadSuccess(true);
      setTimeout(() => setDownloadSuccess(false), 4000);
    } catch (err) {
      console.error('Failed to export GLB:', err);
    } finally {
      setIsGeneratingGLB(false);
    }
  };

  const handleWarp = () => {
    const target = spec.targetDistrict || 'Central Hub';
    onClose();
    if (onWarpToUniverse) {
      onWarpToUniverse(target);
    } else if (onWarpToDistrict) {
      onWarpToDistrict(target);
    }
  };

  return (
    <div className="fixed inset-0 z-70 flex items-center justify-center p-2 sm:p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div 
        className={`w-full bg-slate-900 border-3 border-slate-950 rounded-3xl shadow-[8px_8px_0px_#020617] overflow-hidden flex flex-col transition-all duration-300 ${
          isFullscreen ? 'max-w-none h-full' : 'max-w-4xl max-h-[92vh] h-[720px]'
        }`}
      >
        {/* Header Bar */}
        <div className="p-3.5 sm:p-4 bg-gradient-to-r from-cyan-900 via-slate-900 to-indigo-950 border-b-2 border-slate-800 flex items-center justify-between text-white">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-9 h-9 rounded-xl bg-cyan-400 text-slate-950 flex items-center justify-center font-black shrink-0 border border-white/20 shadow-xs">
              <Box className="w-5 h-5" />
            </div>
            <div className="truncate">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded-full bg-cyan-400/20 text-cyan-300 border border-cyan-400/40">
                  {spec.badge || '3D MENGGU ART'}
                </span>
                <span className="text-[10px] text-slate-400 font-mono hidden sm:inline">
                  {spec.categoryTag}
                </span>
              </div>
              <h3 className="font-black text-sm sm:text-base text-white truncate">
                {spec.name} — 3D Menggu Art Inspector
              </h3>
            </div>
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            <button
              type="button"
              onClick={() => setIsFullscreen(!isFullscreen)}
              className="w-8 h-8 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center justify-center cursor-pointer transition-colors"
              title={isFullscreen ? 'Keluar Fullscreen' : 'Fullscreen'}
            >
              {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="w-8 h-8 rounded-xl bg-rose-500/20 hover:bg-rose-500 text-rose-300 hover:text-white border border-rose-500/40 flex items-center justify-center cursor-pointer transition-colors"
              title="Tutup"
            >
              <X className="w-4 h-4 stroke-[2.5px]" />
            </button>
          </div>
        </div>

        {/* Viewport & Controls Canvas */}
        <div className="flex-1 relative bg-gradient-to-b from-slate-950 to-slate-900 min-h-0 overflow-hidden">
          {/* 3D WebGL Canvas */}
          <div ref={containerRef} className="w-full h-full cursor-grab active:cursor-grabbing" />

          {/* Quick HUD Overlays (Top Left) */}
          <div className="absolute top-3 left-3 flex flex-col gap-1.5 pointer-events-none">
            <div className="pointer-events-auto px-3 py-1.5 rounded-xl bg-slate-900/90 backdrop-blur-md border border-cyan-500/30 text-white text-[11px] font-bold shadow-lg flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
              <span>3D Menggu Art Real-Time Engine</span>
            </div>
            <div className="pointer-events-auto px-2.5 py-1 rounded-lg bg-black/70 backdrop-blur-md border border-slate-700 text-[10px] text-slate-300 font-mono">
              Orbit: Drag mouse • Zoom: Scroll • Pan: Right Click
            </div>
          </div>

          {/* Viewport Control Toggles (Top Right) */}
          <div className="absolute top-3 right-3 flex items-center gap-2">
            <button
              type="button"
              onClick={() => setAutoRotate(!autoRotate)}
              className={`px-2.5 py-1.5 rounded-xl text-xs font-bold border transition-colors cursor-pointer flex items-center gap-1.5 backdrop-blur-md ${
                autoRotate
                  ? 'bg-cyan-500 text-slate-950 border-cyan-400 shadow-[0_0_12px_rgba(34,211,238,0.4)]'
                  : 'bg-slate-900/80 text-slate-300 border-slate-700 hover:bg-slate-800'
              }`}
            >
              <RotateCw className={`w-3.5 h-3.5 ${autoRotate ? 'animate-spin' : ''}`} />
              <span className="hidden sm:inline">Auto Rotate</span>
            </button>

            <button
              type="button"
              onClick={() => setIsWireframe(!isWireframe)}
              className={`px-2.5 py-1.5 rounded-xl text-xs font-bold border transition-colors cursor-pointer flex items-center gap-1.5 backdrop-blur-md ${
                isWireframe
                  ? 'bg-amber-400 text-slate-950 border-amber-300 shadow-[0_0_12px_rgba(251,191,36,0.4)]'
                  : 'bg-slate-900/80 text-slate-300 border-slate-700 hover:bg-slate-800'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Wireframe</span>
            </button>
          </div>

          {/* Bottom Left Technical Specs Overlay */}
          <div className="absolute bottom-3 left-3 max-w-sm hidden sm:block pointer-events-none">
            <div className="p-3 rounded-2xl bg-slate-900/90 backdrop-blur-md border border-slate-700 text-white space-y-1.5 shadow-xl">
              <div className="text-[10px] uppercase font-mono text-cyan-400 font-bold flex items-center gap-1">
                <FileCode className="w-3 h-3" />
                <span>Format: GLTF / GLB Binary PBR</span>
              </div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px] font-mono text-slate-300">
                <div>Polygons: <strong className="text-white">{stats.polys}</strong></div>
                <div>Vertices: <strong className="text-white">{stats.vertices}</strong></div>
                <div className="col-span-2 text-[10px] text-slate-400 truncate">
                  Shading: {stats.materials}
                </div>
              </div>
            </div>
          </div>

          {/* Download Success Banner */}
          {downloadSuccess && (
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 px-5 py-3 rounded-2xl bg-emerald-500 text-slate-950 font-black text-sm border-2 border-slate-900 shadow-2xl flex items-center gap-2 animate-in zoom-in duration-200">
              <Check className="w-5 h-5 stroke-[3px]" />
              <span>File 3D (.GLB) Berhasil Dibuat & Diunduh!</span>
            </div>
          )}
        </div>

        {/* Action Bar Footer */}
        <div className="p-3.5 sm:p-4 bg-slate-950 border-t-2 border-slate-800 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 text-white">
          <div className="text-xs text-slate-300 flex items-center gap-2">
            <Info className="w-4 h-4 text-cyan-400 shrink-0" />
            <span className="line-clamp-1">
              Aset ini di-generate dari Three.js Procedural PBR Menggu Art & siap diekspor ke Blender/Unity/Web.
            </span>
          </div>

          <div className="flex items-center gap-2">
            {/* Generate & Download GLB button */}
            <button
              type="button"
              disabled={isGeneratingGLB}
              onClick={handleExportGLB}
              className="flex-1 sm:flex-none px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-400 to-blue-500 hover:from-cyan-300 hover:to-blue-400 font-black text-xs text-slate-950 border border-cyan-300 shadow-[0_0_15px_rgba(34,211,238,0.3)] cursor-pointer flex items-center justify-center gap-2 disabled:opacity-50 transition-all"
            >
              {isGeneratingGLB ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Packing GLB...</span>
                </>
              ) : (
                <>
                  <Download className="w-4 h-4 stroke-[2.5px]" />
                  <span>Unduh 3D (.GLB)</span>
                </>
              )}
            </button>

            {/* Warp to District button */}
            {(onWarpToUniverse || onWarpToDistrict) && (
              <button
                type="button"
                onClick={handleWarp}
                className="flex-1 sm:flex-none px-4 py-2.5 rounded-xl bg-[#FEF08A] hover:bg-amber-300 font-black text-xs text-slate-950 border border-amber-300 shadow-[0_0_15px_rgba(254,240,138,0.3)] cursor-pointer flex items-center justify-center gap-1.5 transition-all"
              >
                <Play className="w-3.5 h-3.5 fill-slate-950" />
                <span>Masuk ke 3D Universe</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

'use client';

import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { 
  Building2, 
  ShoppingBag, 
  User, 
  Radio, 
  MapPin, 
  Compass, 
  Users, 
  Award, 
  Sparkles, 
  Volume2, 
  ChevronDown, 
  ChevronUp, 
  Play, 
  Pause, 
  ArrowLeft, 
  Send, 
  Mic, 
  Heart, 
  MessageSquare, 
  Share2, 
  ExternalLink, 
  Check, 
  Eye, 
  ShieldCheck, 
  Bot, 
  Smile, 
  CheckCircle2, 
  Flame, 
  Search,
  Filter,
  Box,
  Download,
  Layers,
  Camera,
  RotateCw,
  Loader2
} from 'lucide-react';
import { 
  createMengguDistrict, 
  createMengguCitadelTower, 
  createMengguPlazaFountain, 
  createMengguBillboardAds, 
  createMengguTenantBooth, 
  exportObjectToGLB, 
  downloadGLBBlob,
  MENGGU_PALETTE 
} from '@/lib/menggu3dEngine';
import Menggu3DViewerModal, { MengguViewerItem } from './Menggu3DViewerModal';

export type UniverseSubView = 
  | 'IN_WORLD'           // 7. Tampilan Dalam Dunia 3D
  | 'UNIVERSE_HUB'       // 2 & 3. Universe Hub & Pilih Dunia
  | 'DISTRICT_MAP'       // 5. Peta District
  | 'AVATAR_CUSTOMIZE'   // 8. Avatar Saya & Kustomisasi
  | 'LIVE_STAGE'         // 10 & 11. Live Stage Arena & Event Detail
  | 'MARKETPLACE_3D'     // 12. Marketplace 3D Asset
  | 'QUEST_REWARD'       // 13. Quest & Reward
  | 'NEARBY_PEOPLE';     // 14. Orang di Sekitar

interface Universe3DExperienceProps {
  onBackToFeed: () => void;
  userCredits: number;
  agentCredits: number;
  onRewardBonus?: (amount: number, reason: string) => void;
  onExitToHub?: () => void;
  initialDistrict?: string;
}

export default function Universe3DExperience({
  onBackToFeed,
  userCredits,
  agentCredits,
  onRewardBonus,
  onExitToHub,
  initialDistrict = 'Central Hub',
}: Universe3DExperienceProps) {
  const mountRef = useRef<HTMLDivElement>(null);
  const [subView, setSubView] = useState<UniverseSubView>('IN_WORLD');

  // Avatar in-world position and controls
  const [avatarPos, setAvatarPos] = useState<{ x: number; z: number }>({ x: 0, z: 0 });
  const [isWalking, setIsWalking] = useState(false);
  const [currentDistrict, setCurrentDistrict] = useState(initialDistrict);
  
  // Nearby encounter state (when near an avatar)
  const [nearbyEncounter, setNearbyEncounter] = useState<{
    name: string;
    handle: string;
    type: 'Human' | 'AI Agent';
    owner?: string;
    specialty?: string;
    avatar: string;
    distance: string;
  } | null>(null);

  // Ref to track permanently dismissed proximity encounters in this session
  const permanentlyDismissedEncountersRef = useRef<Set<string>>(new Set());
  const [isEncounterCardMuted, setIsEncounterCardMuted] = useState<boolean>(false);

  // Avatar Customizer State
  const [selectedOutfit, setSelectedOutfit] = useState('cyber-suit-blue');
  const [avatarArmorColor, setAvatarArmorColor] = useState('#06b6d4'); // Cyan default
  const [avatarEmote, setAvatarEmote] = useState<'idle' | 'walk' | 'wave' | 'dance'>('idle');

  // Live Stage State
  const [isLiveStagePlaying, setIsLiveStagePlaying] = useState(true);
  const [stageLikes, setStageLikes] = useState(2400);
  const [chatMessage, setChatMessage] = useState('');
  const [liveChatFeed, setLiveChatFeed] = useState<Array<{ sender: string; text: string; isAi?: boolean }>>([
    { sender: 'Raka Pratama', text: 'Keren banget panggung 3D-nya! Suaranya jernih' },
    { sender: 'Luna AI', text: 'Terima kasih semuanya! Selamat datang di Live Stage Crystal City', isAi: true },
    { sender: 'Sari Dewi', text: 'Visualizer audio di background panggung responsif banget ✨' },
    { sender: 'TechNova', text: 'Pipeline WebGL PBR ter-sync dengan baik di mobile PWA', isAi: true },
  ]);

  // Quests State
  const [quests, setQuests] = useState([
    { id: 'q1', title: 'Jelajahi 3 District Berbeda', current: 2, target: 3, xp: 100, credits: 15, done: false },
    { id: 'q2', title: 'Ikuti Live Stage Event selama 10 Menit', current: 10, target: 10, xp: 50, credits: 10, done: true },
    { id: 'q3', title: 'Beli / Coba Aset 3D di Marketplace Booth', current: 0, target: 1, xp: 100, credits: 25, done: false },
    { id: 'q4', title: 'Sapa 1 Teman atau AI Agent di District', current: 1, target: 1, xp: 150, credits: 20, done: true },
  ]);

  const [expToast, setExpToast] = useState<string | null>(null);
  const [isExportingGLB, setIsExportingGLB] = useState<boolean>(false);
  const [inspectMengguItem, setInspectMengguItem] = useState<MengguViewerItem | null>(null);

  const showExpToast = (msg: string) => {
    setExpToast(msg);
    setTimeout(() => setExpToast(null), 3200);
  };

  // Three.js instances ref
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const playerMeshRef = useRef<THREE.Group | null>(null);
  const otherAvatarsGroupRef = useRef<THREE.Group | null>(null);

  // Export 3D District to standard GLB
  const handleExportDistrictGLB = async () => {
    if (!sceneRef.current) return;
    setIsExportingGLB(true);
    try {
      const blob = await exportObjectToGLB(sceneRef.current, 'allpha_menggu_universe_3d.glb');
      downloadGLBBlob(blob, 'allpha_menggu_universe_3d.glb');
      showExpToast('File 3D Universe GLB berhasil di-generate & diunduh!');
    } catch (err) {
      console.error(err);
      showExpToast('Gagal mengekspor GLB.');
    } finally {
      setIsExportingGLB(false);
    }
  };

  // Quick Camera Tour presets
  const handleTourCamera = (target: 'OVERVIEW' | 'CITADEL' | 'PLAZA' | 'BILLBOARD' | 'BOOTH' | 'AVATAR') => {
    if (!cameraRef.current || !controlsRef.current) return;
    const cam = cameraRef.current;
    const ctrl = controlsRef.current;
    if (target === 'OVERVIEW') {
      cam.position.set(0, 32, 48);
      ctrl.target.set(0, 8, 0);
      showExpToast('Kamera: Overview Metropolis Spatial');
    } else if (target === 'CITADEL') {
      cam.position.set(0, 26, -16);
      ctrl.target.set(0, 38, -45);
      showExpToast('Kamera: Crystal Citadel Spire Tower');
    } else if (target === 'PLAZA') {
      cam.position.set(-24, 12, 12);
      ctrl.target.set(-24, 4, -4);
      showExpToast('Kamera: AI Central Plaza & Fountain');
    } else if (target === 'BILLBOARD') {
      cam.position.set(24, 18, 24);
      ctrl.target.set(24, 14, 4);
      showExpToast('Kamera: Curved Videotron Billboard Ads');
    } else if (target === 'BOOTH') {
      cam.position.set(10, 8, -4);
      ctrl.target.set(10, 3, -16);
      showExpToast('Kamera: 3D Tenant Booth & Showcase');
    } else if (target === 'AVATAR') {
      cam.position.set(animRef.current.avatarX, 4, animRef.current.avatarZ + 8);
      ctrl.target.set(animRef.current.avatarX, 2.5, animRef.current.avatarZ);
      showExpToast('Kamera: Avatar 3D');
    }
    ctrl.update();
  };

  // Mutable animation state
  const animRef = useRef({
    time: 0,
    avatarX: 0,
    avatarZ: 0,
    targetRotY: 0,
    currentRotY: 0,
    isWalking: false,
    emote: 'idle',
    armorColor: '#06b6d4',
  });

  // Virtual Joystick directional button
  const handleVirtualMove = (dx: number, dz: number) => {
    animRef.current.avatarX += dx;
    animRef.current.avatarZ += dz;
    animRef.current.targetRotY = Math.atan2(dx, dz);
    animRef.current.isWalking = true;
    setAvatarPos({ x: animRef.current.avatarX, z: animRef.current.avatarZ });
    setIsWalking(true);

    setTimeout(() => {
      animRef.current.isWalking = false;
      setIsWalking(false);
    }, 300);
  };

  // Teleport to district
  const handleTeleport = (districtName: string, x: number, z: number) => {
    animRef.current.avatarX = x;
    animRef.current.avatarZ = z;
    setAvatarPos({ x, z });
    setCurrentDistrict(districtName);
    setSubView('IN_WORLD');
  };

  useEffect(() => {
    animRef.current.emote = avatarEmote;
    animRef.current.armorColor = avatarArmorColor;
  }, [avatarEmote, avatarArmorColor]);

  // Initialize Three.js scene
  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    // Detect software WebGL as per guidelines
    const isSoftwareGl = (() => {
      const gl = document.createElement('canvas').getContext('webgl2');
      if (!gl) return true;
      const ext = gl.getExtension('WEBGL_debug_renderer_info');
      const param = ext ? ext.UNMASKED_RENDERER_WEBGL : gl.RENDERER;
      const gpu = String(gl.getParameter(param));
      gl.getExtension('WEBGL_lose_context')?.loseContext();
      return /SwiftShader|llvmpipe|softpipe|Software|Basic Render/i.test(gpu);
    })();

    // 1. Scene setup
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x060913); // Deep cosmic navy
    scene.fog = new THREE.FogExp2(0x060913, 0.012);
    sceneRef.current = scene;

    // 2. Camera setup
    const w = container.clientWidth || window.innerWidth;
    const h = container.clientHeight || window.innerHeight;
    const camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 500);
    camera.position.set(0, 7, 16);
    cameraRef.current = camera;

    // 3. Renderer setup
    const renderer = new THREE.WebGLRenderer({
      antialias: !isSoftwareGl,
      powerPreference: 'high-performance',
    });
    renderer.setSize(w, h);
    renderer.setPixelRatio(isSoftwareGl ? 1 : Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;
    renderer.shadowMap.enabled = !isSoftwareGl;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    rendererRef.current = renderer;
    container.appendChild(renderer.domElement);

    // 4. Orbit Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = !isSoftwareGl;
    controls.dampingFactor = 0.05;
    controls.maxPolarAngle = Math.PI / 2 - 0.04;
    controls.minDistance = 3;
    controls.maxDistance = 80;
    controls.target.set(0, 2.5, 0);
    controlsRef.current = controls;

    // 5. Studio Environment & PBR Lighting
    const pmremGenerator = new THREE.PMREMGenerator(renderer);
    scene.environment = pmremGenerator.fromScene(new RoomEnvironment(), 0.04).texture;
    pmremGenerator.dispose();

    const ambientLight = new THREE.HemisphereLight(0x38bdf8, 0x0f172a, 0.85);
    scene.add(ambientLight);

    const dirLight = new THREE.DirectionalLight(0xffffff, 2.2);
    dirLight.position.set(20, 30, 20);
    dirLight.castShadow = !isSoftwareGl;
    if (!isSoftwareGl) {
      dirLight.shadow.mapSize.width = 1024;
      dirLight.shadow.mapSize.height = 1024;
      dirLight.shadow.bias = -0.0005;
      dirLight.shadow.normalBias = 0.02;
    }
    scene.add(dirLight);

    const cyanRim = new THREE.DirectionalLight(0x06b6d4, 1.8);
    cyanRim.position.set(-20, 15, -15);
    scene.add(cyanRim);

    const violetRim = new THREE.DirectionalLight(0xa855f7, 1.4);
    violetRim.position.set(15, 10, -20);
    scene.add(violetRim);

    // ==========================================
    // PROCEDURAL TEXTURE GENERATORS
    // ==========================================
    const createNeonSign = (title: string, sub: string, color: string) => {
      const canvas = document.createElement('canvas');
      canvas.width = 512;
      canvas.height = 256;
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.fillStyle = '#050711';
        ctx.fillRect(0, 0, 512, 256);

        ctx.strokeStyle = color;
        ctx.lineWidth = 12;
        ctx.strokeRect(16, 16, 480, 224);

        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 44px sans-serif';
        ctx.textAlign = 'center';
        ctx.shadowColor = color;
        ctx.shadowBlur = 24;
        ctx.fillText(title, 256, 110);

        ctx.font = '24px sans-serif';
        ctx.fillStyle = color;
        ctx.fillText(sub, 256, 175);
      }
      const tex = new THREE.CanvasTexture(canvas);
      tex.colorSpace = THREE.SRGBColorSpace;
      tex.anisotropy = renderer.capabilities.getMaxAnisotropy();
      return tex;
    };

    // Reflective Ground Plane
    const groundGeo = new THREE.PlaneGeometry(160, 160);
    const groundMat = new THREE.MeshStandardMaterial({
      color: 0x090e17,
      metalness: 0.88,
      roughness: 0.18,
    });
    const ground = new THREE.Mesh(groundGeo, groundMat);
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = 0;
    ground.receiveShadow = !isSoftwareGl;
    scene.add(ground);

    // Ground Neon Grid Lines
    const gridHelper = new THREE.GridHelper(160, 40, 0x00f2fe, 0x1e293b);
    gridHelper.position.y = 0.02;
    scene.add(gridHelper);

    // ==========================================
    // 1. CRYSTAL CITY SKYSCRAPERS & LANDMARKS
    // ==========================================
    const districtGroup = new THREE.Group();
    scene.add(districtGroup);

    const towers = [
      { x: -24, z: -16, w: 10, h: 42, d: 10, name: 'AI PLAZA', color: '#00f2fe' },
      { x: -22, z: 20, w: 12, h: 32, d: 12, name: 'CENTRAL HUB', color: '#38bdf8' },
      { x: 24, z: -16, w: 10, h: 46, d: 10, name: 'CREATOR HUB', color: '#ec4899' },
      { x: 22, z: 20, w: 12, h: 35, d: 12, name: 'LIVE STAGE ARENA', color: '#a855f7' },
    ];

    towers.forEach((t) => {
      const bG = new THREE.Group();
      bG.position.set(t.x, 0, t.z);

      const hull = new THREE.Mesh(
        new THREE.BoxGeometry(t.w, t.h, t.d),
        new THREE.MeshStandardMaterial({ color: 0x0b1120, metalness: 0.9, roughness: 0.2 })
      );
      hull.position.y = t.h / 2;
      hull.castShadow = !isSoftwareGl;
      hull.receiveShadow = !isSoftwareGl;
      bG.add(hull);

      // Glass vertical accent
      const accent = new THREE.Mesh(
        new THREE.BoxGeometry(t.w * 0.2, t.h * 0.9, t.d + 0.1),
        new THREE.MeshPhysicalMaterial({ color: 0x00f2fe, emissive: 0x00f2fe, emissiveIntensity: 0.6 })
      );
      accent.position.y = t.h / 2;
      bG.add(accent);

      // Neon sign on facade
      const signTex = createNeonSign(t.name, 'DISTRICT 01', t.color);
      const sign = new THREE.Mesh(
        new THREE.PlaneGeometry(8, 4),
        new THREE.MeshBasicMaterial({ map: signTex, side: THREE.DoubleSide })
      );
      sign.position.set(0, t.h * 0.5, t.x < 0 ? t.d / 2 + 0.1 : -t.d / 2 - 0.1);
      sign.rotation.y = t.x < 0 ? 0 : Math.PI;
      bG.add(sign);

      districtGroup.add(bG);
    });

    // Elevated Skywalk connecting towers
    const skywalk = new THREE.Mesh(
      new THREE.BoxGeometry(44, 2, 4.5),
      new THREE.MeshPhysicalMaterial({
        color: 0x1e293b,
        metalness: 0.9,
        roughness: 0.15,
        transparent: true,
        opacity: 0.9,
      })
    );
    skywalk.position.set(0, 16, -16);
    districtGroup.add(skywalk);

    // Glowing handrails
    const railG = new THREE.BoxGeometry(44, 0.4, 0.4);
    const railM = new THREE.MeshBasicMaterial({ color: 0x00f2fe });
    const r1 = new THREE.Mesh(railG, railM);
    r1.position.set(0, 17.5, -13.8);
    const r2 = new THREE.Mesh(railG, railM);
    r2.position.set(0, 17.5, -18.2);
    districtGroup.add(r1, r2);

    // ==========================================
    // 3D MENGGU ART SPATIAL STRUCTURES
    // ==========================================
    // 1. Crystal Citadel & AI Spire Tower Landmark (Peak Landmark)
    const citadelTower = createMengguCitadelTower();
    citadelTower.position.set(0, 0, -45);
    citadelTower.scale.set(0.9, 0.9, 0.9);
    districtGroup.add(citadelTower);

    // 2. AI Central Plaza & Holographic Fountain (AI Plaza District)
    const plazaFountain = createMengguPlazaFountain();
    plazaFountain.position.set(-24, 0, 4);
    plazaFountain.scale.set(0.88, 0.88, 0.88);
    districtGroup.add(plazaFountain);

    // 3. Floating Curved Holographic Billboard Ads (Creator Hub)
    const billboardAds = createMengguBillboardAds('ALLPHA 3D SPATIAL UNIVERSE', 'Metropolis Living Hub • 14 Theme 3D');
    billboardAds.position.set(24, 0, 4);
    billboardAds.scale.set(0.92, 0.92, 0.92);
    billboardAds.rotation.y = -Math.PI / 4;
    districtGroup.add(billboardAds);

    // 4. Elevated Monorail Track Circle with Bubble Pods
    const monorailTrackGeo = new THREE.TorusGeometry(38, 0.45, 12, 64);
    const monorailTrackMat = new THREE.MeshStandardMaterial({
      color: MENGGU_PALETTE.lilacLavender,
      metalness: 0.35,
      roughness: 0.25,
    });
    const monorailTrack = new THREE.Mesh(monorailTrackGeo, monorailTrackMat);
    monorailTrack.rotation.x = Math.PI / 2;
    monorailTrack.position.y = 13.5;
    districtGroup.add(monorailTrack);

    // Monorail Bubble Pods Group
    const monorailPodGroup = new THREE.Group();
    monorailPodGroup.name = 'MonorailPodGroup';

    const createPod = (color: number) => {
      const p = new THREE.Group();
      const cab = new THREE.Mesh(
        new THREE.CapsuleGeometry(1.5, 3.2, 16, 20),
        new THREE.MeshStandardMaterial({ color, roughness: 0.35, metalness: 0.1 })
      );
      cab.rotation.z = Math.PI / 2;
      p.add(cab);

      const vis = new THREE.Mesh(
        new THREE.SphereGeometry(1.3, 16, 12, 0, Math.PI, 0, Math.PI),
        new THREE.MeshPhysicalMaterial({ color: 0x22d3ee, transmission: 0.8, transparent: true, opacity: 0.85 })
      );
      vis.rotation.x = -Math.PI / 2;
      vis.position.x = 1.6;
      p.add(vis);
      return p;
    };

    const pod1 = createPod(MENGGU_PALETTE.butterYellow);
    pod1.position.set(38, 14.8, 0);
    monorailPodGroup.add(pod1);

    const pod2 = createPod(MENGGU_PALETTE.softMint);
    pod2.position.set(-38, 14.8, 0);
    monorailPodGroup.add(pod2);
    districtGroup.add(monorailPodGroup);

    // ==========================================
    // 5. 3D MENGGU MODULAR TENANT BOOTHS
    // ==========================================
    const boothConfigs = [
      { name: 'NEXUS WEAR', color: MENGGU_PALETTE.softMint, x: -10, z: 2 },
      { name: 'PIXEL PETS', color: MENGGU_PALETTE.coralPeach, x: 10, z: 2 },
      { name: 'CYBER RIGS', color: MENGGU_PALETTE.lilacLavender, x: -10, z: -16 },
      { name: 'AI AVATARS', color: MENGGU_PALETTE.butterYellow, x: 10, z: -16 },
    ];

    boothConfigs.forEach((cfg) => {
      const booth = createMengguTenantBooth(cfg.name, cfg.color);
      booth.position.set(cfg.x, 0, cfg.z);
      districtGroup.add(booth);
    });

    // ==========================================
    // ==========================================
    // 3. REALISTIC ARTICULATED AVATAR RIG (Player)
    // ==========================================
    const playerGroup = new THREE.Group();
    playerGroup.position.set(0, 0, 4);

    // Contact shadow
    const shadowMesh = new THREE.Mesh(
      new THREE.CircleGeometry(1.3, 32),
      new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.55 })
    );
    shadowMesh.rotation.x = -Math.PI / 2;
    shadowMesh.position.y = 0.02;
    playerGroup.add(shadowMesh);

    // Torso Group
    const torsoGroup = new THREE.Group();
    torsoGroup.position.y = 3.2;
    playerGroup.add(torsoGroup);

    // Cyber Armor Jacket
    const torsoMesh = new THREE.Mesh(
      new THREE.CylinderGeometry(0.85, 0.65, 2.1, 24),
      new THREE.MeshStandardMaterial({
        color: 0x0f172a,
        metalness: 0.85,
        roughness: 0.25,
      })
    );
    torsoGroup.add(torsoMesh);

    // Glowing Reactor Core (AI Neural Link)
    const coreMat = new THREE.MeshBasicMaterial({ color: 0x06b6d4 });
    const chestCore = new THREE.Mesh(new THREE.BoxGeometry(0.38, 0.45, 0.22), coreMat);
    chestCore.position.set(0, 0.2, 0.68);
    torsoGroup.add(chestCore);

    // Neon Spine Rail on the back
    const spineGlow = new THREE.Mesh(
      new THREE.BoxGeometry(0.12, 1.6, 0.1),
      coreMat
    );
    spineGlow.position.set(0, 0, -0.72);
    torsoGroup.add(spineGlow);

    // Head Group
    const headGroup = new THREE.Group();
    headGroup.position.y = 4.8;
    playerGroup.add(headGroup);

    const headMesh = new THREE.Mesh(
      new THREE.SphereGeometry(0.58, 24, 24),
      new THREE.MeshStandardMaterial({ color: 0xfde047, roughness: 0.6, metalness: 0.1 })
    );
    headMesh.scale.set(1, 1.15, 1);
    headGroup.add(headMesh);

    // Cyber Holographic Visor
    const visorMat = new THREE.MeshPhysicalMaterial({
      color: 0x06b6d4,
      emissive: 0x06b6d4,
      emissiveIntensity: 0.8,
      roughness: 0.1,
      metalness: 0.9,
      transmission: 0.5,
      transparent: true,
      opacity: 0.9,
    });
    const visorMesh = new THREE.Mesh(
      new THREE.BoxGeometry(0.85, 0.32, 0.4),
      visorMat
    );
    visorMesh.position.set(0, 0.1, 0.45);
    headGroup.add(visorMesh);

    // Audio Headset Ring
    const headset = new THREE.Mesh(
      new THREE.TorusGeometry(0.66, 0.08, 12, 32, Math.PI),
      new THREE.MeshStandardMaterial({ color: 0x0284c7, metalness: 0.9, roughness: 0.2 })
    );
    headset.rotation.z = Math.PI;
    headset.position.set(0, 0.15, 0);
    headGroup.add(headset);

    const earL = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.22, 0.15, 16), coreMat);
    earL.rotation.z = Math.PI / 2;
    earL.position.set(-0.65, 0.1, 0);
    const earR = earL.clone();
    earR.position.x = 0.65;
    headGroup.add(earL, earR);

    // Articulated Shoulders & Arms
    const limbMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, metalness: 0.8, roughness: 0.3 });
    const armorPlateMat = new THREE.MeshStandardMaterial({ color: 0x334155, metalness: 0.9, roughness: 0.2 });

    // Left Shoulder Pivot
    const leftShoulderGroup = new THREE.Group();
    leftShoulderGroup.position.set(-1.12, 4.0, 0);
    playerGroup.add(leftShoulderGroup);

    const pauldronL = new THREE.Mesh(new THREE.SphereGeometry(0.35, 16, 16), armorPlateMat);
    pauldronL.scale.set(1.1, 0.8, 1.1);
    leftShoulderGroup.add(pauldronL);

    const armL = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.15, 1.7, 16), limbMat);
    armL.position.y = -0.85;
    leftShoulderGroup.add(armL);

    const handL = new THREE.Mesh(new THREE.SphereGeometry(0.2, 12, 12), armorPlateMat);
    handL.position.y = -1.75;
    leftShoulderGroup.add(handL);

    // Right Shoulder Pivot
    const rightShoulderGroup = new THREE.Group();
    rightShoulderGroup.position.set(1.12, 4.0, 0);
    playerGroup.add(rightShoulderGroup);

    const pauldronR = pauldronL.clone();
    rightShoulderGroup.add(pauldronR);

    const armR = armL.clone();
    rightShoulderGroup.add(armR);

    const handR = handL.clone();
    rightShoulderGroup.add(handR);

    // Articulated Hips & Legs
    // Left Hip Pivot
    const leftHipGroup = new THREE.Group();
    leftHipGroup.position.set(-0.45, 2.15, 0);
    playerGroup.add(leftHipGroup);

    const legL = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.18, 2.1, 16), limbMat);
    legL.position.y = -1.0;
    leftHipGroup.add(legL);

    // Cyber Boot with Neon Sole
    const bootL = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.35, 0.75), armorPlateMat);
    bootL.position.set(0, -2.0, 0.12);
    leftHipGroup.add(bootL);

    const soleL = new THREE.Mesh(new THREE.BoxGeometry(0.44, 0.08, 0.78), coreMat);
    soleL.position.set(0, -2.18, 0.12);
    leftHipGroup.add(soleL);

    // Right Hip Pivot
    const rightHipGroup = new THREE.Group();
    rightHipGroup.position.set(0.45, 2.15, 0);
    playerGroup.add(rightHipGroup);

    const legR = legL.clone();
    rightHipGroup.add(legR);

    const bootR = bootL.clone();
    rightHipGroup.add(bootR);

    const soleR = soleL.clone();
    rightHipGroup.add(soleR);

    scene.add(playerGroup);
    playerMeshRef.current = playerGroup;

    // ==========================================
    // 4. WANDERING AVATARS IN THE DISTRICT
    // ==========================================
    const otherAvatars = new THREE.Group();
    scene.add(otherAvatars);
    otherAvatarsGroupRef.current = otherAvatars;

    const wanderers = [
      { name: 'Sari Dewi', handle: '@saridewi', x: -4, z: -2, color: 0xec4899 },
      { name: 'TechNova', handle: '@technova', x: 5, z: -4, color: 0x00f2fe },
      { name: 'Luna AI', handle: '@luna.ai', x: 2, z: 8, color: 0xa855f7 },
    ];

    wanderers.forEach((wnd) => {
      const g = new THREE.Group();
      g.position.set(wnd.x, 0, wnd.z);

      const tMesh = new THREE.Mesh(
        new THREE.CylinderGeometry(0.7, 0.5, 2.2, 16),
        new THREE.MeshStandardMaterial({ color: 0x1e293b, metalness: 0.9, roughness: 0.2 })
      );
      tMesh.position.y = 3.2;
      g.add(tMesh);

      const hMesh = new THREE.Mesh(
        new THREE.SphereGeometry(0.55, 16, 16),
        new THREE.MeshStandardMaterial({ color: 0xfcd34d })
      );
      hMesh.position.y = 4.8;
      g.add(hMesh);

      // Hovering label tag
      const nameTex = createNeonSign(wnd.name, wnd.handle, '#' + wnd.color.toString(16).padStart(6, '0'));
      const lbl = new THREE.Mesh(
        new THREE.PlaneGeometry(2.5, 1.1),
        new THREE.MeshBasicMaterial({ map: nameTex, side: THREE.DoubleSide })
      );
      lbl.position.set(0, 6.0, 0);
      g.add(lbl);

      otherAvatars.add(g);
    });

    // ==========================================
    // 5. ANIMATION LOOP & KINEMATICS
    // ==========================================
    let frameId = 0;
    const clock = new THREE.Clock();

    const tick = () => {
      const dt = Math.min(clock.getDelta(), 0.05);
      animRef.current.time += dt;
      const t = animRef.current.time;

      // Update player position and kinematics
      if (playerMeshRef.current) {
        playerMeshRef.current.position.x = animRef.current.avatarX;
        playerMeshRef.current.position.z = animRef.current.avatarZ;

        // Smooth rotation damping towards target movement angle
        let diff = animRef.current.targetRotY - animRef.current.currentRotY;
        while (diff < -Math.PI) diff += Math.PI * 2;
        while (diff > Math.PI) diff -= Math.PI * 2;
        animRef.current.currentRotY += diff * Math.min(dt * 12.0, 1.0);
        playerMeshRef.current.rotation.y = animRef.current.currentRotY;

        // Animate articulated limbs with organic kinematics
        if (animRef.current.isWalking) {
          // Subtle vertical gait bounce
          playerMeshRef.current.position.y = Math.abs(Math.sin(t * 8.0)) * 0.12;

          // Torso & head counter-rotation for realistic organic walking
          torsoGroup.rotation.y = Math.sin(t * 8.0) * 0.12;
          torsoGroup.rotation.z = Math.sin(t * 8.0) * 0.03;
          headGroup.rotation.y = -Math.sin(t * 8.0) * 0.08;
          headGroup.rotation.x = Math.abs(Math.sin(t * 8.0)) * 0.05;

          // Natural shoulder joint swing
          leftShoulderGroup.rotation.x = Math.sin(t * 8.0) * 0.65;
          rightShoulderGroup.rotation.x = -Math.sin(t * 8.0) * 0.65;

          // Natural hip joint swing
          leftHipGroup.rotation.x = -Math.sin(t * 8.0) * 0.7;
          rightHipGroup.rotation.x = Math.sin(t * 8.0) * 0.7;
        } else if (animRef.current.emote === 'wave') {
          playerMeshRef.current.position.y = 0;
          torsoGroup.rotation.set(0, 0, 0);
          leftShoulderGroup.rotation.set(0, 0, 0);
          rightShoulderGroup.rotation.x = 0;
          rightShoulderGroup.rotation.z = -2.3;
          rightShoulderGroup.rotation.y = Math.sin(t * 8.0) * 0.4;
          headGroup.rotation.y = 0.2;
          leftHipGroup.rotation.set(0, 0, 0);
          rightHipGroup.rotation.set(0, 0, 0);
        } else if (animRef.current.emote === 'dance') {
          playerMeshRef.current.position.y = Math.abs(Math.sin(t * 5.0)) * 0.22;
          torsoGroup.rotation.y = Math.sin(t * 3.0) * 0.4;
          headGroup.rotation.y = -Math.sin(t * 3.0) * 0.3;
          leftShoulderGroup.rotation.z = Math.sin(t * 5.0) * 0.8;
          rightShoulderGroup.rotation.z = -Math.sin(t * 5.0) * 0.8;
          leftHipGroup.rotation.x = Math.sin(t * 5.0) * 0.4;
          rightHipGroup.rotation.x = -Math.sin(t * 5.0) * 0.4;
        } else {
          // Fluid Idle breathing
          playerMeshRef.current.position.y = Math.sin(t * 2.2) * 0.04;
          torsoGroup.rotation.set(0, 0, 0);
          headGroup.rotation.y = Math.sin(t * 1.0) * 0.1;
          headGroup.rotation.x = Math.sin(t * 2.2) * 0.02;
          leftShoulderGroup.rotation.x = Math.sin(t * 2.2) * 0.03;
          rightShoulderGroup.rotation.x = -Math.sin(t * 2.2) * 0.03;
          rightShoulderGroup.rotation.z = 0;
          rightShoulderGroup.rotation.y = 0;
          leftHipGroup.rotation.set(0, 0, 0);
          rightHipGroup.rotation.set(0, 0, 0);
        }

        // Color reactor update
        coreMat.color.set(animRef.current.armorColor);
        visorMat.color.set(animRef.current.armorColor);
        visorMat.emissive.set(animRef.current.armorColor);
      }

      // Smooth OrbitControls camera follow (avatar third-person tracking)
      if (controlsRef.current) {
        controlsRef.current.target.x += (animRef.current.avatarX - controlsRef.current.target.x) * 0.08;
        controlsRef.current.target.y += (2.6 - controlsRef.current.target.y) * 0.08;
        controlsRef.current.target.z += (animRef.current.avatarZ - controlsRef.current.target.z) * 0.08;
        controlsRef.current.update();
      }

      // Check proximity to wanderers for social encounter
      const px = animRef.current.avatarX;
      const pz = animRef.current.avatarZ;
      const distToSari = Math.hypot(px - (-4), pz - (-2));
      const distToLuna = Math.hypot(px - 2, pz - 8);

      if (!isEncounterCardMuted) {
        if (distToSari < 5.0 && !permanentlyDismissedEncountersRef.current.has('Sari Dewi')) {
          setNearbyEncounter({
            name: 'Sari Dewi',
            handle: '@saridewi',
            type: 'Human',
            specialty: 'Content Creator & 3D Fashion',
            avatar: 'https://picsum.photos/seed/sari/150/150',
            distance: `${distToSari.toFixed(1)}m`,
          });
        } else if (distToLuna < 5.0 && !permanentlyDismissedEncountersRef.current.has('Luna AI')) {
          setNearbyEncounter({
            name: 'Luna AI',
            handle: '@luna.ai',
            type: 'AI Agent',
            owner: '@alextamara',
            specialty: '3D Spatial & Video Generator',
            avatar: 'https://picsum.photos/seed/luna-cyber/150/150',
            distance: `${distToLuna.toFixed(1)}m`,
          });
        } else {
          setNearbyEncounter(null);
        }
      } else {
        setNearbyEncounter(null);
      }

      // Dynamic 3D Menggu Art structures animation
      const podGroup = districtGroup.getObjectByName('MonorailPodGroup');
      if (podGroup) {
        podGroup.rotation.y = t * 0.35;
      }
      const droneGroup = districtGroup.getObjectByName('CitadelDroneGroup');
      if (droneGroup) {
        droneGroup.rotation.y = -t * 0.7;
      }
      const citadelGem = districtGroup.getObjectByName('CitadelGem');
      if (citadelGem) {
        citadelGem.rotation.y = t * 1.1;
        citadelGem.position.y = 66 + Math.sin(t * 2) * 0.7;
      }
      const fountainLotus = districtGroup.getObjectByName('FountainLotus');
      if (fountainLotus) {
        fountainLotus.rotation.y = t * 0.5;
        fountainLotus.position.y = 6.2 + Math.sin(t * 2.2) * 0.35;
      }
      const boothGem = districtGroup.getObjectByName('BoothShowcaseGem');
      if (boothGem) {
        boothGem.rotation.y = t * 1.3;
        boothGem.position.y = 3.0 + Math.sin(t * 2) * 0.3;
      }

      renderer.render(scene, camera);
      frameId = requestAnimationFrame(tick);
    };

    frameId = requestAnimationFrame(tick);

    // Keyboard navigation (WASD / Arrows)
    const handleKeyDown = (e: KeyboardEvent) => {
      const step = 0.6;
      let dx = 0;
      let dz = 0;
      if (e.key === 'w' || e.key === 'ArrowUp') dz -= step;
      if (e.key === 's' || e.key === 'ArrowDown') dz += step;
      if (e.key === 'a' || e.key === 'ArrowLeft') dx -= step;
      if (e.key === 'd' || e.key === 'ArrowRight') dx += step;

      if (dx !== 0 || dz !== 0) {
        animRef.current.avatarX += dx;
        animRef.current.avatarZ += dz;
        animRef.current.targetRotY = Math.atan2(dx, dz);
        animRef.current.isWalking = true;
        setAvatarPos({ x: animRef.current.avatarX, z: animRef.current.avatarZ });
        setIsWalking(true);
      }
    };

    const handleKeyUp = () => {
      animRef.current.isWalking = false;
      setIsWalking(false);
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);

    const handleResize = () => {
      if (!container) return;
      const nw = container.clientWidth;
      const nh = container.clientHeight;
      camera.aspect = nw / nh;
      camera.updateProjectionMatrix();
      renderer.setSize(nw, nh);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(frameId);
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
      window.removeEventListener('resize', handleResize);
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, []);

  // Send live stage chat
  const handleSendLiveChat = (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatMessage.trim()) return;
    setLiveChatFeed((prev) => [
      ...prev,
      { sender: 'Alex Tamara (Human Owner)', text: chatMessage.trim() },
    ]);
    setChatMessage('');
  };

  return (
    <div className="fixed inset-0 z-50 w-screen h-screen bg-slate-950 overflow-hidden select-none flex flex-col">
      {/* Top Header Bar for 3D Universe Navigation */}
      <header className="relative z-30 bg-slate-950/85 backdrop-blur-md border-b border-slate-800/80 px-3 py-2 flex flex-col gap-1 text-white">
        <div className="flex items-center justify-between gap-2">
          {/* Back & District Info */}
          <div className="flex items-center gap-2 min-w-0">
            <button
              onClick={onBackToFeed}
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold transition shrink-0"
              title="Kembali ke Feed"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Feed</span>
            </button>

            {onExitToHub && (
              <button
                onClick={onExitToHub}
                className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-cyan-950/80 hover:bg-cyan-900 border border-cyan-700/60 text-cyan-300 text-xs font-bold transition shrink-0 shadow-xs"
                title="Kembali ke Universe Hub"
              >
                <Compass className="w-3.5 h-3.5" />
                <span>Hub</span>
              </button>
            )}

            <div className="flex items-center gap-1.5 min-w-0">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse shrink-0" />
              <h1 className="font-extrabold text-xs sm:text-sm text-white truncate">
                {currentDistrict}
              </h1>
              <span className="hidden sm:inline-block text-[10px] px-1.5 py-0.2 rounded-full bg-emerald-500/20 text-emerald-300 font-mono">
                24.3K Online
              </span>
            </div>
          </div>

          {/* Credits */}
          <div className="flex items-center gap-1.5 shrink-0">
            <span className="text-[11px] font-mono text-cyan-300 font-bold bg-slate-800/80 px-2.5 py-1 rounded-xl border border-slate-700">
              {userCredits} Cr
            </span>
          </div>
        </div>

        {/* Sub-view navigation pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar py-0.5 text-xs">
          <button
            onClick={() => setSubView('IN_WORLD')}
            className={`px-3 py-1 rounded-full text-xs font-semibold whitespace-nowrap transition shrink-0 ${
              subView === 'IN_WORLD' ? 'bg-cyan-600 text-white shadow-xs' : 'bg-slate-800/80 text-slate-300 hover:bg-slate-700'
            }`}
          >
            🌐 Dunia 3D
          </button>
          <button
            onClick={() => setSubView('DISTRICT_MAP')}
            className={`px-3 py-1 rounded-full text-xs font-semibold whitespace-nowrap transition shrink-0 ${
              subView === 'DISTRICT_MAP' ? 'bg-indigo-600 text-white shadow-xs' : 'bg-slate-800/80 text-slate-300 hover:bg-slate-700'
            }`}
          >
            🗺️ Peta District
          </button>
          <button
            onClick={() => setSubView('LIVE_STAGE')}
            className={`px-3 py-1 rounded-full text-xs font-semibold whitespace-nowrap transition shrink-0 ${
              subView === 'LIVE_STAGE' ? 'bg-rose-600 text-white shadow-xs' : 'bg-slate-800/80 text-slate-300 hover:bg-slate-700'
            }`}
          >
            🎙️ Live Stage
          </button>
          <button
            onClick={() => setSubView('AVATAR_CUSTOMIZE')}
            className={`px-3 py-1 rounded-full text-xs font-semibold whitespace-nowrap transition shrink-0 ${
              subView === 'AVATAR_CUSTOMIZE' ? 'bg-purple-600 text-white shadow-xs' : 'bg-slate-800/80 text-slate-300 hover:bg-slate-700'
            }`}
          >
            🎨 Avatar
          </button>
          <button
            onClick={() => setSubView('MARKETPLACE_3D')}
            className={`px-3 py-1 rounded-full text-xs font-semibold whitespace-nowrap transition shrink-0 ${
              subView === 'MARKETPLACE_3D' ? 'bg-amber-600 text-white shadow-xs' : 'bg-slate-800/80 text-slate-300 hover:bg-slate-700'
            }`}
          >
            🛍️ Pasar 3D
          </button>
          <button
            onClick={() => setSubView('QUEST_REWARD')}
            className={`px-3 py-1 rounded-full text-xs font-semibold whitespace-nowrap transition shrink-0 ${
              subView === 'QUEST_REWARD' ? 'bg-emerald-600 text-white shadow-xs' : 'bg-slate-800/80 text-slate-300 hover:bg-slate-700'
            }`}
          >
            📜 Quest ({quests.filter(q => q.done).length}/{quests.length})
          </button>
          <button
            onClick={() => setSubView('NEARBY_PEOPLE')}
            className={`px-3 py-1 rounded-full text-xs font-semibold whitespace-nowrap transition shrink-0 ${
              subView === 'NEARBY_PEOPLE' ? 'bg-teal-600 text-white shadow-xs' : 'bg-slate-800/80 text-slate-300 hover:bg-slate-700'
            }`}
          >
            👥 Orang di Sekitar
          </button>
          <button
            onClick={() => {
              if (onExitToHub) {
                onExitToHub();
              } else {
                setSubView('UNIVERSE_HUB');
              }
            }}
            className={`px-3 py-1 rounded-full text-xs font-semibold whitespace-nowrap transition shrink-0 ${
              subView === 'UNIVERSE_HUB' ? 'bg-blue-600 text-white shadow-xs' : 'bg-slate-800/80 text-slate-300 hover:bg-slate-700'
            }`}
          >
            🏛️ Hub & Dunia
          </button>
        </div>
      </header>

      {/* 3D WebGL Canvas Layer */}
      <div ref={mountRef} className="absolute inset-0 z-10 w-full h-full cursor-grab active:cursor-grabbing" />

      {/* ======================================================== */}
      {/* 1. TAMPILAN DALAM DUNIA (HUD OVERLAY OVER 3D VIEWPORT)  */}
      {/* ======================================================== */}
      {subView === 'IN_WORLD' && (
        <div className="absolute inset-0 z-20 pointer-events-none flex flex-col justify-between p-3 sm:p-4 pt-24 sm:pt-24">
          {/* Top Status & Quick 3D Tour Bar */}
          <div className="pointer-events-auto flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 max-w-full z-30">
            <div className="flex items-center gap-2">
              <div className="px-3 py-1.5 rounded-full bg-slate-900/90 border border-cyan-500/30 text-white shadow-xl flex items-center gap-2 text-xs backdrop-blur-md">
                <Compass className="w-3.5 h-3.5 text-cyan-400 animate-pulse shrink-0" />
                <span className="font-bold text-white truncate">Crystal City Metropolis</span>
                <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-emerald-500/20 text-emerald-300 font-mono">
                  24,340 Online
                </span>
                <span className="text-[10px] text-slate-400 font-mono">
                  X:{avatarPos.x.toFixed(0)} Z:{avatarPos.z.toFixed(0)}
                </span>
              </div>

              <span className="px-2.5 py-1 rounded-full bg-[#FEF08A] text-slate-950 font-black text-[10px] border border-slate-900 shadow-xs hidden md:inline-flex items-center gap-1">
                <Sparkles className="w-3 h-3 text-amber-600" />
                3D Menggu Art Spatial
              </span>
            </div>

            {/* Quick Tour Presets & Download GLB */}
            <div className="flex items-center gap-1.5 flex-wrap">
              <div className="flex items-center gap-1 p-1 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-xl backdrop-blur-md overflow-x-auto no-scrollbar">
                <button
                  type="button"
                  onClick={() => handleTourCamera('OVERVIEW')}
                  className="px-2 py-1 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-[10px] font-bold transition shrink-0 cursor-pointer"
                >
                  🏙️ Overview
                </button>
                <button
                  type="button"
                  onClick={() => handleTourCamera('CITADEL')}
                  className="px-2 py-1 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-[10px] font-bold transition shrink-0 cursor-pointer"
                >
                  🗼 Citadel
                </button>
                <button
                  type="button"
                  onClick={() => handleTourCamera('PLAZA')}
                  className="px-2 py-1 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-[10px] font-bold transition shrink-0 cursor-pointer"
                >
                  ⛲ Plaza
                </button>
                <button
                  type="button"
                  onClick={() => handleTourCamera('BILLBOARD')}
                  className="px-2 py-1 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-[10px] font-bold transition shrink-0 cursor-pointer"
                >
                  📺 Billboard
                </button>
                <button
                  type="button"
                  onClick={() => handleTourCamera('BOOTH')}
                  className="px-2 py-1 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-[10px] font-bold transition shrink-0 cursor-pointer"
                >
                  🛍️ Booth
                </button>
                <button
                  type="button"
                  onClick={() => setInspectMengguItem({
                    id: 'landmark-citadel',
                    name: 'Crystal Citadel & AI Spire',
                    categoryTag: '3. District & Landmark',
                    description: 'Pusat komputasi AI & observatorium Crystal City.',
                    builderType: 'citadel',
                  })}
                  className="px-2.5 py-1 rounded-xl bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-500/40 text-[10px] font-black transition shrink-0 cursor-pointer flex items-center gap-1"
                >
                  <Box className="w-3 h-3 text-cyan-400" />
                  <span>Inspektor GLB</span>
                </button>
              </div>

              <button
                type="button"
                onClick={handleExportDistrictGLB}
                disabled={isExportingGLB}
                className="px-3 py-1.5 rounded-2xl bg-[#FEF08A] hover:bg-amber-300 text-slate-950 font-black text-xs border border-slate-900 shadow-xl transition flex items-center gap-1.5 cursor-pointer shrink-0 disabled:opacity-50"
                title="Unduh format 3D GLB spatial"
              >
                {isExportingGLB ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Mengekspor...</span>
                  </>
                ) : (
                  <>
                    <Download className="w-3.5 h-3.5 stroke-[2.5px]" />
                    <span>Unduh 3D (.GLB)</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Floating Proximity Encounter Notification - Docked top-right and 100% dismissible */}
          {nearbyEncounter && !isEncounterCardMuted && (
            <div className="pointer-events-auto absolute top-28 right-3 sm:right-6 max-w-[270px] sm:max-w-xs w-full p-3 rounded-2xl bg-slate-950/95 border border-purple-500/50 text-white shadow-2xl backdrop-blur-md animate-in fade-in slide-in-from-top-2 duration-200 z-30">
              <div className="flex items-center justify-between pb-1.5 border-b border-slate-800">
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                  <span className="text-[11px] font-bold text-purple-200 truncate">
                    Berdekatan ({nearbyEncounter.distance})
                  </span>
                </div>
                <button
                  onClick={() => {
                    if (nearbyEncounter) {
                      permanentlyDismissedEncountersRef.current.add(nearbyEncounter.name);
                    }
                    setIsEncounterCardMuted(true);
                    setNearbyEncounter(null);
                  }}
                  className="px-2 py-0.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-[11px] font-bold transition flex items-center gap-1"
                  title="Tutup & Jangan Tampilkan Lagi"
                >
                  <span>Tutup</span>
                  <span>✕</span>
                </button>
              </div>

              <div className="flex items-center gap-2.5 mt-2">
                <img
                  src={nearbyEncounter.avatar}
                  alt={nearbyEncounter.name}
                  className="w-9 h-9 rounded-full object-cover ring-2 ring-purple-400 shrink-0"
                />
                <div className="flex-1 min-w-0 text-xs">
                  <div className="flex items-center gap-1">
                    <h4 className="font-bold text-white truncate text-[11px]">{nearbyEncounter.name}</h4>
                    <span className="text-[9px] px-1 py-0.2 rounded bg-purple-500/20 text-purple-300 font-semibold shrink-0">
                      {nearbyEncounter.type}
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-400 truncate">{nearbyEncounter.handle}</p>
                </div>
              </div>

              {/* Interaction Buttons */}
              <div className="grid grid-cols-4 gap-1 mt-2.5 pt-2 border-t border-slate-800/80 text-[10px]">
                <button
                  onClick={() => showExpToast(`Anda melambaikan tangan menyapa ${nearbyEncounter.name}!`)}
                  className="py-1 rounded-lg bg-blue-600 hover:bg-blue-500 font-bold transition text-center"
                >
                  Sapa 👋
                </button>
                <button
                  onClick={() => showExpToast(`Membuka obrolan dengan ${nearbyEncounter.name}`)}
                  className="py-1 rounded-lg bg-slate-800 hover:bg-slate-700 font-medium transition text-center"
                >
                  Chat 💬
                </button>
                <button
                  onClick={() => showExpToast(`Profil: ${nearbyEncounter.name} (${nearbyEncounter.type})`)}
                  className="py-1 rounded-lg bg-slate-800 hover:bg-slate-700 font-medium transition text-center"
                >
                  Profil 👤
                </button>
                <button
                  onClick={() => {
                    permanentlyDismissedEncountersRef.current.add(nearbyEncounter.name);
                    setNearbyEncounter(null);
                  }}
                  className="py-1 rounded-lg bg-slate-800 hover:bg-rose-900/60 font-bold transition text-center text-rose-300"
                  title="Hapus notifikasi"
                >
                  ✕ Hapus
                </button>
              </div>
            </div>
          )}

          {/* Bottom Controls: Virtual D-Pad Movement & Actions */}
          <div className="pointer-events-auto flex items-end justify-between gap-2 pb-2">
            {/* Virtual Joystick / D-Pad */}
            <div className="p-2 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-2xl flex flex-col items-center gap-1 text-white text-xs shrink-0 backdrop-blur-sm">
              <button
                onClick={() => handleVirtualMove(0, -1.5)}
                className="w-9 h-9 rounded-xl bg-slate-800 hover:bg-slate-700 active:bg-cyan-600 font-bold flex items-center justify-center shadow"
              >
                ▲
              </button>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => handleVirtualMove(-1.5, 0)}
                  className="w-9 h-9 rounded-xl bg-slate-800 hover:bg-slate-700 active:bg-cyan-600 font-bold flex items-center justify-center shadow"
                >
                  ◀
                </button>
                <div className="w-5 h-5 rounded-full bg-cyan-500/20 flex items-center justify-center">
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                </div>
                <button
                  onClick={() => handleVirtualMove(1.5, 0)}
                  className="w-9 h-9 rounded-xl bg-slate-800 hover:bg-slate-700 active:bg-cyan-600 font-bold flex items-center justify-center shadow"
                >
                  ▶
                </button>
              </div>
              <button
                onClick={() => handleVirtualMove(0, 1.5)}
                className="w-9 h-9 rounded-xl bg-slate-800 hover:bg-slate-700 active:bg-cyan-600 font-bold flex items-center justify-center shadow"
              >
                ▼
              </button>
            </div>

            {/* In-World Chat Bar */}
            <div className="flex-1 max-w-sm">
              <div className="flex items-center gap-1.5 p-1 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-2xl backdrop-blur-sm">
                <input
                  type="text"
                  placeholder="Ketik chat di dunia 3D..."
                  className="flex-1 bg-transparent px-2.5 py-1.5 text-xs text-white outline-none placeholder:text-slate-500 min-w-0"
                />
                <button className="p-1.5 rounded-xl bg-slate-800 text-slate-300 hover:text-white transition shrink-0">
                  <Mic className="w-3.5 h-3.5" />
                </button>
                <button className="p-1.5 rounded-xl bg-cyan-600 text-white hover:bg-cyan-500 transition shrink-0">
                  <Send className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {/* Emote & Action Buttons */}
            <div className="flex flex-col gap-1.5 shrink-0">
              <button
                onClick={() => setAvatarEmote('wave')}
                className="w-9 h-9 rounded-xl bg-slate-900/90 hover:bg-slate-800 border border-slate-700 text-white flex items-center justify-center text-xs shadow transition backdrop-blur-sm"
                title="Lambaikan Tangan"
              >
                👋
              </button>
              <button
                onClick={() => setAvatarEmote('dance')}
                className="w-9 h-9 rounded-xl bg-slate-900/90 hover:bg-slate-800 border border-slate-700 text-white flex items-center justify-center text-xs shadow transition backdrop-blur-sm"
                title="Menari"
              >
                💃
              </button>
              <button
                onClick={() => setSubView('AVATAR_CUSTOMIZE')}
                className="w-9 h-9 rounded-xl bg-purple-600 hover:bg-purple-500 text-white flex items-center justify-center shadow-lg transition"
                title="Kustomisasi Avatar"
              >
                <User className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* 2 & 3. UNIVERSE HUB & PILIH DUNIA (SCREEN 2 & 3)        */}
      {/* ======================================================== */}
      {subView === 'UNIVERSE_HUB' && (
        <div className="absolute inset-0 top-[76px] z-40 bg-slate-950/95 overflow-y-auto p-4 sm:p-6 text-white space-y-6 pb-24">
          <div className="max-w-3xl mx-auto space-y-6">
            <div className="p-6 rounded-3xl bg-gradient-to-r from-blue-900 via-indigo-900 to-slate-900 border border-cyan-500/30 shadow-2xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div>
                <span className="px-2.5 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 font-bold text-[10px] uppercase">
                  Pusat Ekosistem Allpha
                </span>
                <h2 className="text-xl font-black mt-1 text-white">Crystal City 3D Universe</h2>
                <p className="text-xs text-slate-300 mt-1 max-w-md">
                  Dunia utama tempat manusia dan AI Agent bertemu, berkolaborasi, berkreasi, dan membuka peluang baru dalam visual spatial 3D.
                </p>
                <div className="flex items-center gap-4 mt-3 text-xs text-slate-400">
                  <span className="flex items-center gap-1 text-emerald-400 font-mono">
                    <span className="w-2 h-2 rounded-full bg-emerald-400" />
                    24,340 Online
                  </span>
                  <span>•</span>
                  <span>312 Live Event</span>
                </div>
              </div>
              <button
                onClick={() => handleTeleport('Central Hub', 0, 4)}
                className="px-6 py-3 rounded-2xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-black text-xs shadow-lg transition shrink-0"
              >
                Masuk ke Crystal City
              </button>
            </div>

            {/* Worlds Catalog */}
            <div className="space-y-3">
              <h3 className="font-bold text-sm text-slate-200">Pilih Dunia Virtual Populer</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                {[
                  { name: 'Crystal City', desc: 'Pusat ekosistem spatial utama Allpha', online: '24.3K', bg: 'from-blue-900 to-cyan-900' },
                  { name: 'Neo Tokyo', desc: 'Kota futuristik Asia & digital fashion', online: '12.5K', bg: 'from-pink-900 to-purple-900' },
                  { name: 'Mars Colony', desc: 'Eksplorasi luar angkasa & science lab', online: '8.7K', bg: 'from-amber-900 to-rose-900' },
                  { name: 'Oceanic World', desc: 'Dunia bawah laut & bioluminescent reef', online: '6.1K', bg: 'from-teal-900 to-emerald-900' },
                  { name: 'Fantasy Realm', desc: 'Dunia fantasi, naga & sihir neural', online: '4.9K', bg: 'from-violet-900 to-indigo-900' },
                  { name: 'Green Land', desc: 'Alam, keberlanjutan & biophilic cities', online: '3.2K', bg: 'from-emerald-900 to-lime-900' },
                ].map((w) => (
                  <div
                    key={w.name}
                    className="p-4 rounded-2xl bg-slate-900 border border-slate-800 hover:border-cyan-500/50 flex items-center justify-between transition"
                  >
                    <div>
                      <h4 className="font-bold text-sm text-white">{w.name}</h4>
                      <p className="text-[11px] text-slate-400 mt-0.5">{w.desc}</p>
                      <span className="text-[10px] text-cyan-300 font-mono mt-1 inline-block">
                        {w.online} Pengguna Aktif
                      </span>
                    </div>
                    <button
                      onClick={() => handleTeleport(w.name, 0, 0)}
                      className="px-3.5 py-1.5 rounded-xl bg-slate-800 hover:bg-cyan-600 text-white font-semibold text-xs transition"
                    >
                      Masuk
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* 5. PETA DISTRICT & TELEPORT (SCREEN 5)                   */}
      {/* ======================================================== */}
      {subView === 'DISTRICT_MAP' && (
        <div className="absolute inset-0 top-[76px] z-40 bg-slate-950/95 overflow-y-auto p-4 sm:p-6 text-white pb-24">
          <div className="max-w-2xl mx-auto space-y-5">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div>
                <h2 className="text-base font-black text-white">Peta District Crystal City</h2>
                <p className="text-xs text-slate-400">Pilih landmark atau plaza untuk langsung berteleportasi</p>
              </div>
              <button
                onClick={() => setSubView('IN_WORLD')}
                className="px-3 py-1.5 rounded-full bg-slate-800 hover:bg-slate-700 text-xs font-semibold"
              >
                Tutup Peta
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              {[
                { name: 'Central Hub', sub: 'Area utama berkumpul & pusat pertemuan', x: 0, z: 4, online: '1.2K', color: 'border-cyan-500' },
                { name: 'AI Plaza', sub: 'Pameran AI Agent & bot intelligence', x: -24, z: -10, online: '850', color: 'border-blue-500' },
                { name: 'Creator Hub', sub: 'Studio kreasi konten & podcast stage', x: 24, z: -10, online: '940', color: 'border-pink-500' },
                { name: 'Live Stage Arena', sub: 'Panggung live show, talkshow & pitching', x: 22, z: 18, online: '2.4K', color: 'border-purple-500' },
                { name: 'Business District', sub: 'Booth enterprise, kantor virtual & finance', x: -22, z: 16, online: '670', color: 'border-emerald-500' },
                { name: '3D Marketplace Avenue', sub: 'Kios digital fashion, gadget & avatar item', x: 0, z: -10, online: '1.5K', color: 'border-amber-500' },
              ].map((loc) => (
                <div
                  key={loc.name}
                  className={`p-4 rounded-2xl bg-slate-900 border ${loc.color}/40 hover:${loc.color} flex flex-col justify-between transition space-y-3`}
                >
                  <div>
                    <div className="flex items-center justify-between">
                      <h4 className="font-bold text-sm text-white">{loc.name}</h4>
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono">
                        {loc.online} Online
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-1">{loc.sub}</p>
                  </div>
                  <button
                    onClick={() => handleTeleport(loc.name, loc.x, loc.z)}
                    className="w-full py-2 rounded-xl bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white font-bold text-xs shadow transition"
                  >
                    Teleport Sekarang
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* 8. AVATAR SAYA & KUSTOMISASI (SCREEN 8)                  */}
      {/* ======================================================== */}
      {subView === 'AVATAR_CUSTOMIZE' && (
        <div className="absolute inset-0 top-[76px] z-40 bg-slate-950/95 overflow-y-auto p-4 sm:p-6 text-white pb-24">
          <div className="max-w-2xl mx-auto space-y-5">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div>
                <h2 className="text-base font-black text-white">Avatar Saya & Kustomisasi Rig 3D</h2>
                <p className="text-xs text-slate-400">Sesuaikan pakaian cybernetic, aksen reaktor neon, dan animasi pose</p>
              </div>
              <button
                onClick={() => setSubView('IN_WORLD')}
                className="px-3.5 py-1.5 rounded-full bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-bold text-xs shadow"
              >
                Terapkan & Masuk Dunia
              </button>
            </div>

            {/* Armor Color Swatches */}
            <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 space-y-2">
              <label className="text-xs font-bold text-slate-300">Warna Aksen Reaktor Neon:</label>
              <div className="flex items-center gap-3">
                {[
                  { color: '#06b6d4', name: 'Cyan Glow' },
                  { color: '#a855f7', name: 'Cyber Violet' },
                  { color: '#ec4899', name: 'Neon Rose' },
                  { color: '#eab308', name: 'Solar Amber' },
                  { color: '#10b981', name: 'Matrix Green' },
                ].map((c) => (
                  <button
                    key={c.color}
                    onClick={() => setAvatarArmorColor(c.color)}
                    className={`w-8 h-8 rounded-full border-2 transition ${
                      avatarArmorColor === c.color ? 'border-white scale-110 shadow-lg' : 'border-transparent opacity-60'
                    }`}
                    style={{ backgroundColor: c.color }}
                    title={c.name}
                  />
                ))}
              </div>
            </div>

            {/* Outfit Preset Skins */}
            <div className="space-y-2 text-xs">
              <label className="font-bold text-slate-300">Pilih Setelan Kostum Cybernetic:</label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                {[
                  { id: 'cyber-suit-blue', name: 'Cyber Suit V1', sub: 'Default Operative' },
                  { id: 'nexus-runner', name: 'Nexus Runner', sub: 'Lightweight Rig' },
                  { id: 'tactical-armor', name: 'Tactical Armor', sub: 'Heavy Titanium' },
                  { id: 'hologram-mesh', name: 'Hologram Mesh', sub: 'Neural Wireframe' },
                ].map((out) => (
                  <button
                    key={out.id}
                    onClick={() => setSelectedOutfit(out.id)}
                    className={`p-3 rounded-xl border text-left transition ${
                      selectedOutfit === out.id
                        ? 'bg-purple-950/80 border-purple-400 text-white shadow-md'
                        : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-white'
                    }`}
                  >
                    <p className="font-bold">{out.name}</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">{out.sub}</p>
                  </button>
                ))}
              </div>
            </div>

            {/* Emotes / Animation Poses */}
            <div className="space-y-2 text-xs">
              <label className="font-bold text-slate-300">Uji Animasi Pose & Emote:</label>
              <div className="grid grid-cols-4 gap-2">
                {(['idle', 'walk', 'wave', 'dance'] as const).map((em) => (
                  <button
                    key={em}
                    onClick={() => setAvatarEmote(em)}
                    className={`py-2 rounded-xl border font-bold capitalize transition ${
                      avatarEmote === em
                        ? 'bg-blue-600 border-blue-400 text-white'
                        : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-white'
                    }`}
                  >
                    {em}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* 10 & 11. LIVE STAGE & EVENT DETAIL (SCREEN 10 & 11)     */}
      {/* ======================================================== */}
      {subView === 'LIVE_STAGE' && (
        <div className="absolute inset-0 top-[76px] z-40 bg-slate-950/95 overflow-y-auto p-4 sm:p-6 text-white pb-24">
          <div className="max-w-3xl mx-auto space-y-6">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-pulse" />
                <h2 className="text-base font-black text-white">Live Stage Arena • Crystal City</h2>
                <span className="text-xs px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 font-mono font-bold">
                  LIVE NOW (2.4K Menonton)
                </span>
              </div>
              <button
                onClick={() => setSubView('IN_WORLD')}
                className="px-3 py-1.5 rounded-full bg-slate-800 hover:bg-slate-700 text-xs font-semibold"
              >
                Masuk ke Panggung 3D
              </button>
            </div>

            {/* Event Detail Card */}
            <div className="p-5 rounded-3xl bg-slate-900 border border-purple-500/30 space-y-3">
              <h3 className="text-lg font-black text-white">AI Innovation Summit 2026: Masa Depan AI & Dunia Spatial</h3>
              <p className="text-xs text-slate-300 leading-relaxed">
                Sesi kolaborasi langsung antara Human Owner (@alextamara) dan AI Agent miliknya (@luna.ai). Membahas integrasi bot cerdas di dunia 3D, ekonomi reward kredit, dan interaksi tanpa batas.
              </p>

              <div className="flex items-center gap-4 text-xs text-slate-400 pt-2 border-t border-slate-800">
                <span>📅 15 Maret 2026</span>
                <span>•</span>
                <span>⏰ 19:00 - 22:00 WIB</span>
                <span>•</span>
                <span>📍 Live Stage Arena, Crystal City</span>
              </div>
            </div>

            {/* Live Chat Stream in Stage */}
            <div className="p-4 rounded-3xl bg-slate-900 border border-slate-800 space-y-3">
              <h4 className="text-xs font-bold text-slate-300">Live Chat Pemirsa di Arena:</h4>
              <div className="h-44 overflow-y-auto space-y-2 pr-1 text-xs">
                {liveChatFeed.map((c, i) => (
                  <div key={i} className="p-2.5 rounded-xl bg-slate-950/70 border border-slate-800">
                    <span className={`font-bold mr-1.5 ${c.isAi ? 'text-cyan-300' : 'text-slate-200'}`}>
                      {c.sender}:
                    </span>
                    <span className="text-slate-300">{c.text}</span>
                  </div>
                ))}
              </div>

              <form onSubmit={handleSendLiveChat} className="flex items-center gap-2 pt-2">
                <input
                  type="text"
                  value={chatMessage}
                  onChange={(e) => setChatMessage(e.target.value)}
                  placeholder="Kirim tanggapan langsung ke panggung..."
                  className="flex-1 bg-slate-950 border border-slate-800 px-3.5 py-2 rounded-xl text-xs text-white outline-none focus:border-cyan-500"
                />
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs transition"
                >
                  Kirim
                </button>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* 12. MARKETPLACE 3D ASSET (SCREEN 12)                    */}
      {/* ======================================================== */}
      {subView === 'MARKETPLACE_3D' && (
        <div className="absolute inset-0 top-[76px] z-40 bg-slate-950/95 overflow-y-auto p-4 sm:p-6 text-white pb-24">
          <div className="max-w-3xl mx-auto space-y-5">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div>
                <h2 className="text-base font-black text-white">Marketplace 3D Asset & Avatar Skins</h2>
                <p className="text-xs text-slate-400">Beli dan pasang langsung aset 3D terverifikasi ke Booth atau Avatar Anda</p>
              </div>
              <button
                onClick={() => setSubView('IN_WORLD')}
                className="px-3 py-1.5 rounded-full bg-slate-800 hover:bg-slate-700 text-xs font-semibold"
              >
                Kembali ke 3D
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              {[
                { name: 'Futuristic Building Pack', type: '3D Building', price: 'Rp 150.000 / 30 Cr', likes: '1.2k' },
                { name: 'Space Vehicle Speeder', type: '3D Transport', price: 'Rp 200.000 / 40 Cr', likes: '856' },
                { name: 'City Props & Neon Signs', type: 'Environment', price: 'Rp 120.000 / 25 Cr', likes: '642' },
                { name: 'Hologram Stage Rig', type: 'Live Stage Item', price: 'Rp 250.000 / 50 Cr', likes: '1.1k' },
              ].map((item) => (
                <div
                  key={item.name}
                  className="p-4 rounded-2xl bg-slate-900 border border-slate-800 hover:border-amber-500/50 flex flex-col justify-between transition space-y-3"
                >
                  <div>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 font-semibold">
                      {item.type}
                    </span>
                    <h4 className="font-bold text-sm text-white mt-1.5">{item.name}</h4>
                    <p className="text-amber-400 font-bold font-mono mt-1">{item.price}</p>
                  </div>
                  <button
                    onClick={() => showExpToast(`Aset "${item.name}" berhasil dicoba pada preview avatar!`)}
                    className="w-full py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-bold text-xs transition shadow"
                  >
                    Beli & Pasang di 3D
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* 13. QUEST & REWARD (SCREEN 13)                          */}
      {/* ======================================================== */}
      {subView === 'QUEST_REWARD' && (
        <div className="absolute inset-0 top-[76px] z-40 bg-slate-950/95 overflow-y-auto p-4 sm:p-6 text-white pb-24">
          <div className="max-w-2xl mx-auto space-y-5">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div>
                <h2 className="text-base font-black text-white">Quest Harian & Bonus AI Credits</h2>
                <p className="text-xs text-slate-400">Selesaikan misi di dunia 3D untuk mengumpulkan XP dan AI Credits Reward</p>
              </div>
              <button
                onClick={() => setSubView('IN_WORLD')}
                className="px-3 py-1.5 rounded-full bg-slate-800 hover:bg-slate-700 text-xs font-semibold"
              >
                Tutup
              </button>
            </div>

            <div className="space-y-3">
              {quests.map((q) => (
                <div
                  key={q.id}
                  className={`p-4 rounded-2xl border transition flex items-center justify-between ${
                    q.done ? 'bg-slate-900/90 border-emerald-500/50' : 'bg-slate-900 border-slate-800'
                  }`}
                >
                  <div className="text-xs space-y-1">
                    <p className="font-bold text-white text-sm">{q.title}</p>
                    <p className="text-slate-400 text-[11px]">
                      Progress: {q.current}/{q.target} • Hadiah: +{q.xp} XP & +{q.credits} AI Credits
                    </p>
                  </div>
                  {q.done ? (
                    <span className="px-3 py-1.5 rounded-xl bg-emerald-500/20 text-emerald-300 font-bold text-xs border border-emerald-500/30 flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Selesai
                    </span>
                  ) : (
                    <button
                      onClick={() => {
                        setQuests((prev) =>
                          prev.map((item) =>
                            item.id === q.id ? { ...item, current: item.target, done: true } : item
                          )
                        );
                        if (onRewardBonus) onRewardBonus(q.credits, q.title);
                      }}
                      className="px-3 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs"
                    >
                      Klaim Reward
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* 14. ORANG DI SEKITAR (SCREEN 14)                         */}
      {/* ======================================================== */}
      {subView === 'NEARBY_PEOPLE' && (
        <div className="absolute inset-0 top-[76px] z-40 bg-slate-950/95 overflow-y-auto p-4 sm:p-6 text-white pb-24">
          <div className="max-w-2xl mx-auto space-y-5">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div>
                <h2 className="text-base font-black text-white">Orang & AI Agent di Sekitar Anda</h2>
                <p className="text-xs text-slate-400">Pengguna dan bot cerdas yang sedang berada di radius 50m Crystal City</p>
              </div>
              <button
                onClick={() => setSubView('IN_WORLD')}
                className="px-3 py-1.5 rounded-full bg-slate-800 hover:bg-slate-700 text-xs font-semibold"
              >
                Kembali ke 3D
              </button>
            </div>

            <div className="space-y-2.5">
              {[
                { name: 'Sari Dewi', handle: '@saridewi', type: 'Human', role: 'Content Creator', dist: '3.2m', avatar: 'https://picsum.photos/seed/sari/100/100' },
                { name: 'TechNova', handle: '@technova', type: 'AI Agent', role: 'IT & Teknologi (Milik @mikatanaka)', dist: '4.8m', avatar: 'https://picsum.photos/seed/technova/100/100' },
                { name: 'Dimas Ardi', handle: '@dimasardi', type: 'Human', role: '3D Architect & Modeler', dist: '12.4m', avatar: 'https://picsum.photos/seed/dimas/100/100' },
                { name: 'MediAI', handle: '@mediai', type: 'AI Agent', role: 'Kesehatan & Wellness (Milik @andipratama)', dist: '18.1m', avatar: 'https://picsum.photos/seed/mediai/100/100' },
              ].map((p) => (
                <div
                  key={p.handle}
                  className="p-3.5 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-between text-xs"
                >
                  <div className="flex items-center gap-3">
                    <img src={p.avatar} alt={p.name} className="w-10 h-10 rounded-full object-cover ring-2 ring-slate-700" />
                    <div>
                      <div className="flex items-center gap-1.5">
                        <span className="font-bold text-white text-sm">{p.name}</span>
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-800 text-cyan-300 font-semibold">
                          {p.type}
                        </span>
                      </div>
                      <p className="text-slate-400 text-[11px]">{p.role} • Jarak: {p.dist}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => showExpToast(`Menyapa ${p.name}!`)}
                      className="px-3 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 font-bold transition text-xs"
                    >
                      Sapa
                    </button>
                    <button
                      onClick={() => showExpToast(`Membuka obrolan dengan ${p.name}`)}
                      className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 font-semibold transition text-xs"
                    >
                      Chat
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Floating In-World Toast */}
      {expToast && (
        <div className="fixed top-16 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-2xl bg-slate-900/95 text-white text-xs font-bold border-2 border-slate-700 shadow-xl backdrop-blur-md">
          <span>✨ {expToast}</span>
        </div>
      )}

      {/* 3D Menggu Art Modal Inspector & GLB Exporter */}
      {inspectMengguItem && (
        <Menggu3DViewerModal
          item={inspectMengguItem}
          onClose={() => setInspectMengguItem(null)}
          onWarpToUniverse={() => {
            setInspectMengguItem(null);
            handleTourCamera('CITADEL');
          }}
        />
      )}
    </div>
  );
}

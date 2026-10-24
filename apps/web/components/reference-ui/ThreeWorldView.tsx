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
  Eye, 
  RotateCw, 
  Sparkles, 
  Volume2, 
  ChevronDown, 
  ChevronUp, 
  Maximize2, 
  Play, 
  Pause,
  CheckCircle2,
  ExternalLink,
  Info
} from 'lucide-react';

type WorldMode = 'DISTRICT' | 'MARKETPLACE' | 'AVATAR' | 'LIVESTAGE';

export default function ThreeWorldView() {
  const mountRef = useRef<HTMLDivElement>(null);
  const [activeMode, setActiveMode] = useState<WorldMode>('DISTRICT');
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [selectedBooth, setSelectedBooth] = useState<string | null>(null);
  
  // Avatar Customization State
  const [avatarColor, setAvatarColor] = useState<string>('#06b6d4'); // cyan default
  const [avatarPose, setAvatarPose] = useState<'idle' | 'walk' | 'present' | 'wave'>('idle');
  const [isHologramMode, setIsHologramMode] = useState<boolean>(false);

  // Live Stage State
  const [isPodcastLive, setIsPodcastLive] = useState<boolean>(true);
  const [podcastTopic, setPodcastTopic] = useState<string>('Ekosistem Sosial Masa Depan: Human × AI Agent');
  const [audioMeter, setAudioMeter] = useState<number>(65);

  // Keep references to Three.js elements
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const groupsRef = useRef<{
    district: THREE.Group;
    marketplace: THREE.Group;
    avatar: THREE.Group;
    liveStage: THREE.Group;
  } | null>(null);

  // Mutable animation state refs
  const animStateRef = useRef({
    time: 0,
    droneY: 0,
    avatarPose: 'idle',
    isPodcastLive: true,
    isHologramMode: false,
    avatarColor: '#06b6d4',
  });

  useEffect(() => {
    animStateRef.current.avatarPose = avatarPose;
    animStateRef.current.isHologramMode = isHologramMode;
    animStateRef.current.isPodcastLive = isPodcastLive;
    animStateRef.current.avatarColor = avatarColor;
  }, [avatarPose, isHologramMode, isPodcastLive, avatarColor]);

  // Audio meter oscillation effect for Live Stage
  useEffect(() => {
    if (!isPodcastLive) return;
    const interval = setInterval(() => {
      setAudioMeter(Math.floor(40 + Math.random() * 55));
    }, 200);
    return () => clearInterval(interval);
  }, [isPodcastLive]);

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

    // 1. Scene Setup
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x060913); // Deep cosmic navy
    scene.fog = new THREE.FogExp2(0x060913, 0.015);
    sceneRef.current = scene;

    // 2. Camera Setup
    const width = container.clientWidth || window.innerWidth;
    const height = container.clientHeight || (window.innerHeight - 130);
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 500);
    camera.position.set(0, 10, 28);
    cameraRef.current = camera;

    // 3. Renderer Setup
    const renderer = new THREE.WebGLRenderer({
      antialias: !isSoftwareGl,
      powerPreference: 'high-performance',
      alpha: false,
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(isSoftwareGl ? 1 : Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.15;
    renderer.shadowMap.enabled = !isSoftwareGl;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    rendererRef.current = renderer;

    container.appendChild(renderer.domElement);

    // 4. Orbit Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = !isSoftwareGl;
    controls.dampingFactor = 0.05;
    controls.maxPolarAngle = Math.PI / 2 - 0.02; // Keep camera above ground
    controls.minDistance = 3;
    controls.maxDistance = 90;
    controls.target.set(0, 3, 0);
    controlsRef.current = controls;

    // 5. Studio Environment Lighting via RoomEnvironment
    const pmremGenerator = new THREE.PMREMGenerator(renderer);
    scene.environment = pmremGenerator.fromScene(new RoomEnvironment(), 0.04).texture;
    pmremGenerator.dispose();

    // Studio 3-point light rig
    const ambientLight = new THREE.HemisphereLight(0x38bdf8, 0x0f172a, 0.9);
    scene.add(ambientLight);

    const dirKeyLight = new THREE.DirectionalLight(0xffffff, 2.0);
    dirKeyLight.position.set(15, 25, 20);
    dirKeyLight.castShadow = !isSoftwareGl;
    if (!isSoftwareGl) {
      dirKeyLight.shadow.mapSize.width = 1024;
      dirKeyLight.shadow.mapSize.height = 1024;
      dirKeyLight.shadow.camera.near = 0.5;
      dirKeyLight.shadow.camera.far = 80;
      const d = 25;
      dirKeyLight.shadow.camera.left = -d;
      dirKeyLight.shadow.camera.right = d;
      dirKeyLight.shadow.camera.top = d;
      dirKeyLight.shadow.camera.bottom = -d;
      dirKeyLight.shadow.bias = -0.0005;
      dirKeyLight.shadow.normalBias = 0.02;
    }
    scene.add(dirKeyLight);

    const rimCyanLight = new THREE.DirectionalLight(0x06b6d4, 1.8);
    rimCyanLight.position.set(-20, 15, -20);
    scene.add(rimCyanLight);

    const rimPurpleLight = new THREE.DirectionalLight(0xa855f7, 1.4);
    rimPurpleLight.position.set(20, 10, -15);
    scene.add(rimPurpleLight);

    // ==========================================
    // PROCEDURAL TEXTURE GENERATORS (Zero 404s)
    // ==========================================
    const createNeonSignTexture = (text: string, color: string, subtext?: string) => {
      const canvas = document.createElement('canvas');
      canvas.width = 512;
      canvas.height = 256;
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.fillStyle = '#050711';
        ctx.fillRect(0, 0, 512, 256);

        // Neon outer glow border
        ctx.strokeStyle = color;
        ctx.lineWidth = 10;
        ctx.strokeRect(16, 16, 480, 224);

        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 3;
        ctx.strokeRect(20, 20, 472, 216);

        // Text
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 44px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.shadowColor = color;
        ctx.shadowBlur = 25;
        ctx.fillText(text, 256, 110);

        if (subtext) {
          ctx.font = '22px sans-serif';
          ctx.fillStyle = color;
          ctx.shadowBlur = 10;
          ctx.fillText(subtext, 256, 170);
        }
      }
      const tex = new THREE.CanvasTexture(canvas);
      tex.colorSpace = THREE.SRGBColorSpace;
      tex.anisotropy = renderer.capabilities.getMaxAnisotropy();
      return tex;
    };

    const createRoadGridTexture = () => {
      const canvas = document.createElement('canvas');
      canvas.width = 512;
      canvas.height = 512;
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.fillStyle = '#0b0f19';
        ctx.fillRect(0, 0, 512, 512);

        // Glowing blue grid lines
        ctx.strokeStyle = '#1e293b';
        ctx.lineWidth = 2;
        for (let i = 0; i <= 512; i += 64) {
          ctx.beginPath();
          ctx.moveTo(i, 0);
          ctx.lineTo(i, 512);
          ctx.stroke();

          ctx.beginPath();
          ctx.moveTo(0, i);
          ctx.lineTo(512, i);
          ctx.stroke();
        }

        // Center highway neon lines
        ctx.strokeStyle = '#00f2fe';
        ctx.lineWidth = 8;
        ctx.shadowColor = '#00f2fe';
        ctx.shadowBlur = 15;
        ctx.beginPath();
        ctx.moveTo(256, 0);
        ctx.lineTo(256, 512);
        ctx.stroke();
      }
      const tex = new THREE.CanvasTexture(canvas);
      tex.wrapS = THREE.RepeatWrapping;
      tex.wrapT = THREE.RepeatWrapping;
      tex.repeat.set(12, 12);
      tex.colorSpace = THREE.SRGBColorSpace;
      return tex;
    };

    const createAudioWaveTexture = () => {
      const canvas = document.createElement('canvas');
      canvas.width = 512;
      canvas.height = 256;
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.fillStyle = '#020617';
        ctx.fillRect(0, 0, 512, 256);

        // Circular mic target
        ctx.strokeStyle = '#0284c7';
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.arc(256, 128, 70, 0, Math.PI * 2);
        ctx.stroke();

        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(256, 128, 50, 0, Math.PI * 2);
        ctx.stroke();

        // Audio waveform bars
        ctx.fillStyle = '#38bdf8';
        for (let x = 30; x < 480; x += 12) {
          const h = 20 + Math.sin(x * 0.05) * 45 + Math.random() * 20;
          ctx.fillRect(x, 128 - h / 2, 6, h);
        }

        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 20px monospace';
        ctx.textAlign = 'center';
        ctx.fillText('LIVE EXPERIENCE PODCAST • ALLPHA', 256, 40);
      }
      const tex = new THREE.CanvasTexture(canvas);
      tex.colorSpace = THREE.SRGBColorSpace;
      return tex;
    };

    // Shared Ground & Contact Shadow
    const groundGeo = new THREE.PlaneGeometry(160, 160);
    const groundMat = new THREE.MeshStandardMaterial({
      color: 0x080d1a,
      roughness: 0.25,
      metalness: 0.85,
      map: createRoadGridTexture(),
    });
    const groundMesh = new THREE.Mesh(groundGeo, groundMat);
    groundMesh.rotation.x = -Math.PI / 2;
    groundMesh.position.y = 0;
    groundMesh.receiveShadow = !isSoftwareGl;
    scene.add(groundMesh);

    // ==========================================
    // 1. DISTRICT SPATIAL GROUP (Crystal City)
    // ==========================================
    const districtGroup = new THREE.Group();
    scene.add(districtGroup);

    // Skyscrapers with composite architecture (3-12 parts each)
    const buildingColors = [0x111827, 0x0f172a, 0x1e1b4b, 0x030712];
    const neonBillboardTextures = [
      createNeonSignTexture('CYBERNETICA', '#00f2fe', 'DISTRICT 01'),
      createNeonSignTexture('NEO-KYOTO', '#ec4899', 'DIGITAL ATRIUM'),
      createNeonSignTexture('GLOWTECH', '#a855f7', 'SPATIAL SYSTEMS'),
      createNeonSignTexture('SYNTH-BITES', '#3b82f6', 'VIRTUAL LOUNGE'),
    ];

    // Left and Right side futuristic towers
    const towerCoords = [
      { x: -18, z: -10, w: 9, h: 36, d: 9 },
      { x: -20, z: 12, w: 10, h: 28, d: 10 },
      { x: -16, z: -32, w: 12, h: 48, d: 12 },
      { x: 18, z: -10, w: 9, h: 40, d: 9 },
      { x: 20, z: 14, w: 11, h: 30, d: 11 },
      { x: 16, z: -30, w: 13, h: 52, d: 13 },
      { x: 0, z: -46, w: 22, h: 64, d: 14 }, // Central monumental spire
    ];

    towerCoords.forEach((t, i) => {
      const bGroup = new THREE.Group();
      bGroup.position.set(t.x, 0, t.z);

      // Base hull
      const hullGeo = new THREE.BoxGeometry(t.w, t.h, t.d);
      const hullMat = new THREE.MeshStandardMaterial({
        color: buildingColors[i % buildingColors.length],
        metalness: 0.9,
        roughness: 0.15,
      });
      const hull = new THREE.Mesh(hullGeo, hullMat);
      hull.position.y = t.h / 2;
      hull.castShadow = !isSoftwareGl;
      hull.receiveShadow = !isSoftwareGl;
      bGroup.add(hull);

      // Beveled vertical glass stripes
      const stripeGeo = new THREE.BoxGeometry(t.w * 0.15, t.h * 0.85, t.d + 0.1);
      const stripeMat = new THREE.MeshPhysicalMaterial({
        color: 0x38bdf8,
        emissive: 0x0284c7,
        emissiveIntensity: 0.7,
        roughness: 0.1,
        metalness: 0.9,
      });
      const stripe = new THREE.Mesh(stripeGeo, stripeMat);
      stripe.position.y = t.h / 2;
      bGroup.add(stripe);

      // Roof spire / architectural crown
      const crownGeo = new THREE.ConeGeometry(t.w * 0.4, 8, 4);
      const crownMat = new THREE.MeshStandardMaterial({
        color: 0x38bdf8,
        metalness: 0.95,
        roughness: 0.1,
        wireframe: i % 2 === 0,
      });
      const crown = new THREE.Mesh(crownGeo, crownMat);
      crown.position.y = t.h + 4;
      bGroup.add(crown);

      // Neon Billboard display attached to facade
      const boardGeo = new THREE.PlaneGeometry(7, 3.5);
      const boardMat = new THREE.MeshBasicMaterial({
        map: neonBillboardTextures[i % neonBillboardTextures.length],
        side: THREE.DoubleSide,
      });
      const billboard = new THREE.Mesh(boardGeo, boardMat);
      billboard.position.set(0, t.h * 0.45, (t.x < 0 ? t.d / 2 + 0.1 : -t.d / 2 - 0.1));
      billboard.rotation.y = t.x < 0 ? 0 : Math.PI;
      bGroup.add(billboard);

      districtGroup.add(bGroup);
    });

    // Elevated pedestrian skybridge connecting left and right buildings
    const bridgeGeo = new THREE.BoxGeometry(36, 2.5, 5);
    const bridgeMat = new THREE.MeshPhysicalMaterial({
      color: 0x1e293b,
      metalness: 0.9,
      roughness: 0.2,
      transmission: isSoftwareGl ? 0 : 0.8,
      transparent: true,
      opacity: 0.9,
    });
    const skybridge = new THREE.Mesh(bridgeGeo, bridgeMat);
    skybridge.position.set(0, 15, -10);
    skybridge.castShadow = !isSoftwareGl;
    districtGroup.add(skybridge);

    // Glowing handrails on bridge
    const railGeo = new THREE.BoxGeometry(36, 0.4, 0.4);
    const railMat = new THREE.MeshBasicMaterial({ color: 0x00f2fe });
    const topRail1 = new THREE.Mesh(railGeo, railMat);
    topRail1.position.set(0, 16.5, -7.8);
    const topRail2 = new THREE.Mesh(railGeo, railMat);
    topRail2.position.set(0, 16.5, -12.2);
    districtGroup.add(topRail1, topRail2);

    // Hovering futuristic vehicle on avenue
    const vehicleGroup = new THREE.Group();
    const carBodyGeo = new THREE.BoxGeometry(3.6, 1.2, 6);
    const carMat = new THREE.MeshStandardMaterial({
      color: 0x0284c7,
      metalness: 0.95,
      roughness: 0.1,
    });
    const carBody = new THREE.Mesh(carBodyGeo, carMat);
    carBody.position.y = 1.0;
    vehicleGroup.add(carBody);

    const carCanopyGeo = new THREE.SphereGeometry(1.6, 16, 8);
    carCanopyGeo.scale(1, 0.6, 1.5);
    const carCanopyMat = new THREE.MeshPhysicalMaterial({
      color: 0x0f172a,
      roughness: 0.1,
      metalness: 0.9,
    });
    const carCanopy = new THREE.Mesh(carCanopyGeo, carCanopyMat);
    carCanopy.position.set(0, 1.7, -0.2);
    vehicleGroup.add(carCanopy);

    // Neon ground underglow on vehicle
    const underglowGeo = new THREE.PlaneGeometry(3.6, 6);
    const underglowMat = new THREE.MeshBasicMaterial({
      color: 0x00f2fe,
      transparent: true,
      opacity: 0.75,
    });
    const underglow = new THREE.Mesh(underglowGeo, underglowMat);
    underglow.rotation.x = -Math.PI / 2;
    underglow.position.y = 0.08;
    vehicleGroup.add(underglow);
    vehicleGroup.position.set(0, 0, 4);
    districtGroup.add(vehicleGroup);

    // Floating aerial patrol drone
    const droneGroup = new THREE.Group();
    const droneCenter = new THREE.Mesh(
      new THREE.SphereGeometry(0.8, 16, 16),
      new THREE.MeshStandardMaterial({ color: 0x0f172a, metalness: 0.9, roughness: 0.2 })
    );
    droneGroup.add(droneCenter);
    const droneRotorRing = new THREE.Mesh(
      new THREE.TorusGeometry(1.8, 0.12, 8, 24),
      new THREE.MeshBasicMaterial({ color: 0x38bdf8 })
    );
    droneRotorRing.rotation.x = Math.PI / 2;
    droneGroup.add(droneRotorRing);
    droneGroup.position.set(-5, 14, 0);
    districtGroup.add(droneGroup);

    // ==========================================
    // 2. 3D MARKETPLACE BOOTH GROUP
    // ==========================================
    const marketplaceGroup = new THREE.Group();
    scene.add(marketplaceGroup);

    const boothData = [
      { id: 'neon-threads', name: 'NEON THREADS', sub: 'Digital Fashion', x: -8, z: 2, color: 0xec4899 },
      { id: 'quantum-gear', name: 'QUANTUM GEAR', sub: 'Tech & Gadgets', x: 8, z: 2, color: 0x06b6d4 },
      { id: 'cyber-wear', name: 'CYBER WEAR', sub: '3D Armor & Skins', x: -8, z: -12, color: 0xa855f7 },
      { id: 'ai-avatars', name: 'AI AVATARS', sub: 'Neural Characters', x: 8, z: -12, color: 0x3b82f6 },
    ];

    boothData.forEach((b) => {
      const bBooth = new THREE.Group();
      bBooth.position.set(b.x, 0, b.z);

      // Kiosk Platform Base
      const platGeo = new THREE.CylinderGeometry(4.2, 4.4, 0.5, 32);
      const platMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, metalness: 0.9, roughness: 0.2 });
      const plat = new THREE.Mesh(platGeo, platMat);
      plat.position.y = 0.25;
      plat.receiveShadow = !isSoftwareGl;
      bBooth.add(plat);

      // Glowing circular perimeter rim
      const rimGeo = new THREE.TorusGeometry(4.3, 0.08, 8, 32);
      const rimMat = new THREE.MeshBasicMaterial({ color: b.color });
      const rim = new THREE.Mesh(rimGeo, rimMat);
      rim.rotation.x = Math.PI / 2;
      rim.position.y = 0.52;
      bBooth.add(rim);

      // Holographic arch / canopy
      const archGeo = new THREE.TorusGeometry(3.2, 0.2, 12, 24, Math.PI);
      const archMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, metalness: 0.9, roughness: 0.2 });
      const arch = new THREE.Mesh(archGeo, archMat);
      arch.position.y = 3.2;
      bBooth.add(arch);

      // Display sign board
      const signTex = createNeonSignTexture(b.name, '#' + b.color.toString(16).padStart(6, '0'), b.sub);
      const signMesh = new THREE.Mesh(
        new THREE.PlaneGeometry(3.8, 1.8),
        new THREE.MeshBasicMaterial({ map: signTex, side: THREE.DoubleSide })
      );
      signMesh.position.set(0, 4.2, 0);
      bBooth.add(signMesh);

      // Floating showcase centerpiece (different for each booth)
      let itemMesh: THREE.Object3D;
      if (b.id === 'neon-threads') {
        itemMesh = new THREE.Mesh(
          new THREE.ConeGeometry(0.9, 2.2, 16),
          new THREE.MeshPhysicalMaterial({
            color: b.color,
            emissive: b.color,
            emissiveIntensity: 0.4,
            metalness: 0.8,
            roughness: 0.2,
          })
        );
      } else if (b.id === 'quantum-gear') {
        itemMesh = new THREE.Mesh(
          new THREE.OctahedronGeometry(1.2),
          new THREE.MeshStandardMaterial({ color: b.color, metalness: 0.95, roughness: 0.1 })
        );
      } else if (b.id === 'cyber-wear') {
        itemMesh = new THREE.Mesh(
          new THREE.TorusKnotGeometry(0.7, 0.25, 64, 8),
          new THREE.MeshStandardMaterial({ color: b.color, metalness: 0.9, roughness: 0.15 })
        );
      } else {
        itemMesh = new THREE.Mesh(
          new THREE.IcosahedronGeometry(1.1, 1),
          new THREE.MeshPhysicalMaterial({ color: b.color, wireframe: true })
        );
      }
      itemMesh.position.set(0, 2.2, 0);
      bBooth.add(itemMesh);

      marketplaceGroup.add(bBooth);
    });

    // ==========================================
    // 3. 3D AVATAR & AI CHARACTER GROUP
    // ==========================================
    const avatarGroup = new THREE.Group();
    scene.add(avatarGroup);

    // Composite 3D Cyber Character
    const characterGroup = new THREE.Group();
    characterGroup.position.set(0, 0, 0);

    // Circular pedestal with contact shadow
    const pedGeo = new THREE.CylinderGeometry(3.5, 3.8, 0.4, 32);
    const pedMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, metalness: 0.9, roughness: 0.2 });
    const ped = new THREE.Mesh(pedGeo, pedMat);
    ped.position.y = 0.2;
    characterGroup.add(ped);

    const pedRing = new THREE.Mesh(
      new THREE.TorusGeometry(3.6, 0.08, 8, 32),
      new THREE.MeshBasicMaterial({ color: 0x06b6d4 })
    );
    pedRing.rotation.x = Math.PI / 2;
    pedRing.position.y = 0.42;
    characterGroup.add(pedRing);

    // Torso / Cyber Armor Jacket
    const torsoGeo = new THREE.CylinderGeometry(0.9, 0.7, 2.4, 16);
    const armorMat = new THREE.MeshStandardMaterial({
      color: 0x1e293b,
      metalness: 0.85,
      roughness: 0.25,
    });
    const torso = new THREE.Mesh(torsoGeo, armorMat);
    torso.position.y = 3.6;
    characterGroup.add(torso);

    // Glowing Chest Core (AI Reactor)
    const coreGeo = new THREE.BoxGeometry(0.45, 0.6, 0.3);
    const coreMat = new THREE.MeshBasicMaterial({ color: 0x06b6d4 });
    const chestCore = new THREE.Mesh(coreGeo, coreMat);
    chestCore.position.set(0, 3.8, 0.75);
    characterGroup.add(chestCore);

    // Head / Facial Features
    const headGeo = new THREE.SphereGeometry(0.65, 16, 16);
    headGeo.scale(1, 1.2, 1);
    const skinMat = new THREE.MeshStandardMaterial({
      color: 0xfbbf24,
      roughness: 0.6,
      metalness: 0.1,
    });
    const head = new THREE.Mesh(headGeo, skinMat);
    head.position.y = 5.3;
    characterGroup.add(head);

    // Cybernetic Headset & Illuminated Audio Rings (from reference)
    const headsetGeo = new THREE.TorusGeometry(0.72, 0.09, 8, 24, Math.PI);
    const headsetMat = new THREE.MeshStandardMaterial({ color: 0x0284c7, metalness: 0.9, roughness: 0.2 });
    const headset = new THREE.Mesh(headsetGeo, headsetMat);
    headset.rotation.z = Math.PI;
    headset.position.set(0, 5.4, 0);
    characterGroup.add(headset);

    const earEarringL = new THREE.Mesh(new THREE.CylinderGeometry(0.25, 0.25, 0.2, 16), coreMat);
    earEarringL.rotation.z = Math.PI / 2;
    earEarringL.position.set(-0.7, 5.3, 0);
    const earEarringR = earEarringL.clone();
    earEarringR.position.x = 0.7;
    characterGroup.add(earEarringL, earEarringR);

    // Limbs - Cybernetic Arms & Legs
    const armGeo = new THREE.CylinderGeometry(0.24, 0.2, 2.0, 12);
    const leftArm = new THREE.Mesh(armGeo, armorMat);
    leftArm.position.set(-1.25, 3.4, 0);
    leftArm.rotation.z = 0.15;
    const rightArm = new THREE.Mesh(armGeo, armorMat);
    rightArm.position.set(1.25, 3.4, 0);
    rightArm.rotation.z = -0.15;
    characterGroup.add(leftArm, rightArm);

    const legGeo = new THREE.CylinderGeometry(0.3, 0.25, 2.4, 12);
    const leftLeg = new THREE.Mesh(legGeo, armorMat);
    leftLeg.position.set(-0.45, 1.4, 0);
    const rightLeg = new THREE.Mesh(legGeo, armorMat);
    rightLeg.position.set(0.45, 1.4, 0);
    characterGroup.add(leftLeg, rightLeg);

    avatarGroup.add(characterGroup);

    // ==========================================
    // 4. LIVE STAGE & PODCAST STUDIO GROUP
    // ==========================================
    const liveStageGroup = new THREE.Group();
    scene.add(liveStageGroup);

    // Stage Platform
    const stagePlat = new THREE.Mesh(
      new THREE.CylinderGeometry(14, 14.5, 0.8, 36),
      new THREE.MeshStandardMaterial({ color: 0x090e17, metalness: 0.95, roughness: 0.15 })
    );
    stagePlat.position.y = 0.4;
    liveStageGroup.add(stagePlat);

    // Stage Backboard Wall with Ambient Audio Visualizer
    const backWallMesh = new THREE.Mesh(
      new THREE.CylinderGeometry(13.8, 13.8, 8, 36, 1, true, -Math.PI / 3, (2 * Math.PI) / 3),
      new THREE.MeshStandardMaterial({ color: 0x0b1120, metalness: 0.9, roughness: 0.3, side: THREE.BackSide })
    );
    backWallMesh.position.set(0, 4.4, -4);
    liveStageGroup.add(backWallMesh);

    // Visualizer Screen on Wall
    const screenGeo = new THREE.PlaneGeometry(12, 5.5);
    const screenMat = new THREE.MeshBasicMaterial({
      map: createAudioWaveTexture(),
      side: THREE.DoubleSide,
    });
    const screenMesh = new THREE.Mesh(screenGeo, screenMat);
    screenMesh.position.set(0, 4.8, -9.8);
    liveStageGroup.add(screenMesh);

    // Executive Broadcast Table (Dark polished wood + metal bevel)
    const metalDarkMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, metalness: 0.9, roughness: 0.2 });
    const tableGeo = new THREE.BoxGeometry(9, 0.4, 4);
    const tableMat = new THREE.MeshStandardMaterial({
      color: 0x1f2937,
      metalness: 0.8,
      roughness: 0.2,
    });
    const tableMesh = new THREE.Mesh(tableGeo, tableMat);
    tableMesh.position.set(0, 2.8, 0);
    liveStageGroup.add(tableMesh);

    // Table Metallic Legs
    const legT1 = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.18, 2.6, 16), metalDarkMat);
    legT1.position.set(-3.8, 1.4, -1.5);
    const legT2 = legT1.clone();
    legT2.position.set(3.8, 1.4, -1.5);
    const legT3 = legT1.clone();
    legT3.position.set(-3.8, 1.4, 1.5);
    const legT4 = legT1.clone();
    legT4.position.set(3.8, 1.4, 1.5);
    liveStageGroup.add(legT1, legT2, legT3, legT4);

    // Studio Condenser Microphones on Articulated Stands
    const createMic = (x: number, z: number, rotY: number) => {
      const micG = new THREE.Group();
      micG.position.set(x, 3.0, z);
      micG.rotation.y = rotY;

      // Base
      const mBase = new THREE.Mesh(new THREE.CylinderGeometry(0.35, 0.4, 0.08, 16), metalDarkMat);
      micG.add(mBase);

      // Angled neck
      const mNeck = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 0.9, 8), metalDarkMat);
      mNeck.position.set(0, 0.45, 0);
      mNeck.rotation.z = -0.2;
      micG.add(mNeck);

      // Condenser Capsule
      const mCap = new THREE.Mesh(
        new THREE.CylinderGeometry(0.14, 0.14, 0.45, 16),
        new THREE.MeshStandardMaterial({ color: 0x94a3b8, metalness: 0.95, roughness: 0.1 })
      );
      mCap.position.set(-0.15, 0.9, 0);
      micG.add(mCap);

      return micG;
    };

    const micLeft = createMic(-2.0, 0, Math.PI / 4);
    const micRight = createMic(2.0, 0, -Math.PI / 4);
    liveStageGroup.add(micLeft, micRight);

    // SEAT 1: Human Owner (Represented by Host Chair & Avatar Silhouette)
    const hostChair = new THREE.Mesh(
      new THREE.BoxGeometry(2.2, 3.0, 1.8),
      new THREE.MeshStandardMaterial({ color: 0x111827, metalness: 0.6, roughness: 0.4 })
    );
    hostChair.position.set(-3.6, 2.5, 0);
    liveStageGroup.add(hostChair);

    const hostLabelTex = createNeonSignTexture('ALEX TAMARA', '#38bdf8', 'HUMAN OWNER');
    const hostLabel = new THREE.Mesh(
      new THREE.PlaneGeometry(2.4, 1.0),
      new THREE.MeshBasicMaterial({ map: hostLabelTex, side: THREE.DoubleSide })
    );
    hostLabel.position.set(-3.6, 4.6, 0);
    hostLabel.rotation.y = Math.PI / 2;
    liveStageGroup.add(hostLabel);

    // SEAT 2: AI Agent (Holographic Wireframe & Glowing Blue Presence)
    const aiChair = hostChair.clone();
    aiChair.position.set(3.6, 2.5, 0);
    liveStageGroup.add(aiChair);

    const aiHoloAvatar = new THREE.Mesh(
      new THREE.CylinderGeometry(0.8, 0.6, 2.4, 16),
      new THREE.MeshPhysicalMaterial({
        color: 0x00f2fe,
        emissive: 0x00f2fe,
        emissiveIntensity: 0.8,
        wireframe: true,
        transparent: true,
        opacity: 0.85,
      })
    );
    aiHoloAvatar.position.set(3.6, 3.8, 0);
    liveStageGroup.add(aiHoloAvatar);

    const aiLabelTex = createNeonSignTexture('LUNA AI', '#a855f7', 'AI AGENT');
    const aiLabel = new THREE.Mesh(
      new THREE.PlaneGeometry(2.4, 1.0),
      new THREE.MeshBasicMaterial({ map: aiLabelTex, side: THREE.DoubleSide })
    );
    aiLabel.position.set(3.6, 4.6, 0);
    aiLabel.rotation.y = -Math.PI / 2;
    liveStageGroup.add(aiLabel);

    // Save groups to ref
    groupsRef.current = {
      district: districtGroup,
      marketplace: marketplaceGroup,
      avatar: avatarGroup,
      liveStage: liveStageGroup,
    };

    // Mode Visibility Initializer
    const updateVisibility = (mode: WorldMode) => {
      districtGroup.visible = mode === 'DISTRICT';
      marketplaceGroup.visible = mode === 'MARKETPLACE';
      avatarGroup.visible = mode === 'AVATAR';
      liveStageGroup.visible = mode === 'LIVESTAGE';

      if (mode === 'DISTRICT') {
        camera.position.set(0, 10, 28);
        controls.target.set(0, 3, 0);
      } else if (mode === 'MARKETPLACE') {
        camera.position.set(0, 9, 22);
        controls.target.set(0, 2, 0);
      } else if (mode === 'AVATAR') {
        camera.position.set(0, 4.5, 9);
        controls.target.set(0, 3.5, 0);
      } else if (mode === 'LIVESTAGE') {
        camera.position.set(0, 6, 14);
        controls.target.set(0, 3, 0);
      }
      controls.update();
    };

    updateVisibility(activeMode);

    // 6. Animation Loop with Clamped Delta Time
    let frameId = 0;
    const clock = new THREE.Clock();

    const tick = () => {
      const dt = Math.min(clock.getDelta(), 0.05);
      animStateRef.current.time += dt;
      const t = animStateRef.current.time;

      // Animate hovering vehicle & drone
      if (vehicleGroup && districtGroup.visible) {
        vehicleGroup.position.y = Math.sin(t * 1.5) * 0.12;
      }
      if (droneGroup && districtGroup.visible) {
        droneGroup.position.y = 14 + Math.sin(t * 2.0) * 0.4;
        droneGroup.rotation.y += dt * 0.5;
      }

      // Animate Avatar
      if (avatarGroup.visible) {
        if (animStateRef.current.avatarPose === 'idle') {
          characterGroup.position.y = Math.sin(t * 2.0) * 0.05;
          head.rotation.y = Math.sin(t * 0.8) * 0.15;
          chestCore.material.color.set(animStateRef.current.avatarColor);
        } else if (animStateRef.current.avatarPose === 'walk') {
          characterGroup.position.y = Math.abs(Math.sin(t * 6.0)) * 0.1;
          leftArm.rotation.x = Math.sin(t * 6.0) * 0.5;
          rightArm.rotation.x = -Math.sin(t * 6.0) * 0.5;
          leftLeg.rotation.x = -Math.sin(t * 6.0) * 0.5;
          rightLeg.rotation.x = Math.sin(t * 6.0) * 0.5;
        } else if (animStateRef.current.avatarPose === 'present') {
          rightArm.rotation.z = -1.2 + Math.sin(t * 2.0) * 0.2;
          head.rotation.y = -0.3;
        } else if (animStateRef.current.avatarPose === 'wave') {
          rightArm.rotation.z = -2.2;
          rightArm.rotation.x = Math.sin(t * 8.0) * 0.3;
        }

        // Hologram wireframe toggle
        torso.material.wireframe = animStateRef.current.isHologramMode;
      }

      // Animate Live Stage
      if (liveStageGroup.visible && animStateRef.current.isPodcastLive) {
        aiHoloAvatar.position.y = 3.8 + Math.sin(t * 3.0) * 0.08;
      }

      controls.update();
      renderer.render(scene, camera);

      frameId = requestAnimationFrame(tick);
    };

    frameId = requestAnimationFrame(tick);

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
      cancelAnimationFrame(frameId);
      window.removeEventListener('resize', handleResize);
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, []);

  // Mode change handler
  const handleSwitchMode = (mode: WorldMode) => {
    setActiveMode(mode);
    if (!groupsRef.current || !cameraRef.current || !controlsRef.current) return;
    const { district, marketplace, avatar, liveStage } = groupsRef.current;
    const camera = cameraRef.current;
    const controls = controlsRef.current;

    district.visible = mode === 'DISTRICT';
    marketplace.visible = mode === 'MARKETPLACE';
    avatar.visible = mode === 'AVATAR';
    liveStage.visible = mode === 'LIVESTAGE';

    if (mode === 'DISTRICT') {
      camera.position.set(0, 10, 28);
      controls.target.set(0, 3, 0);
    } else if (mode === 'MARKETPLACE') {
      camera.position.set(0, 9, 22);
      controls.target.set(0, 2, 0);
    } else if (mode === 'AVATAR') {
      camera.position.set(0, 4.5, 9);
      controls.target.set(0, 3.5, 0);
    } else if (mode === 'LIVESTAGE') {
      camera.position.set(0, 6, 14);
      controls.target.set(0, 3, 0);
    }
    controls.update();
  };

  return (
    <div className="relative w-full h-[calc(100vh-125px)] min-h-[550px] bg-slate-950 overflow-hidden select-none">
      {/* 3D WebGL Canvas Mount */}
      <div ref={mountRef} className="w-full h-full cursor-grab active:cursor-grabbing" />

      {/* Top Floating Badge & Scene Header (Non-occluding, top-left) */}
      <div className="absolute top-4 left-4 z-20 flex flex-col gap-1.5 pointer-events-none">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-900/80 border border-cyan-500/30 text-white text-xs font-medium shadow-lg backdrop-blur-none pointer-events-auto">
          <span className="w-2 h-2 rounded-full bg-cyan-400" />
          <span>ALLPHA 3D UNIVERSE</span>
          <span className="text-slate-400">|</span>
          <span className="text-cyan-300 font-semibold">
            {activeMode === 'DISTRICT' && 'Crystal City Central Avenue'}
            {activeMode === 'MARKETPLACE' && '3D Booth Marketplace'}
            {activeMode === 'AVATAR' && 'Avatar 3D Customizer'}
            {activeMode === 'LIVESTAGE' && 'Live Experience Podcast Stage'}
          </span>
        </div>
        <p className="text-[11px] text-slate-400 pl-1 drop-shadow">
          Drag untuk putar 360° • Scroll untuk zoom • Shift + Drag untuk geser
        </p>
      </div>

      {/* Top Right Quick Mode Pills */}
      <div className="absolute top-4 right-4 z-20 flex items-center gap-1.5 bg-slate-900/90 p-1.5 rounded-xl border border-slate-800 shadow-xl">
        <button
          onClick={() => handleSwitchMode('DISTRICT')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
            activeMode === 'DISTRICT' ? 'bg-cyan-600 text-white shadow' : 'text-slate-300 hover:bg-slate-800'
          }`}
        >
          <Building2 className="w-3.5 h-3.5" />
          <span>District</span>
        </button>
        <button
          onClick={() => handleSwitchMode('MARKETPLACE')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
            activeMode === 'MARKETPLACE' ? 'bg-purple-600 text-white shadow' : 'text-slate-300 hover:bg-slate-800'
          }`}
        >
          <ShoppingBag className="w-3.5 h-3.5" />
          <span>Booth 3D</span>
        </button>
        <button
          onClick={() => handleSwitchMode('AVATAR')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
            activeMode === 'AVATAR' ? 'bg-blue-600 text-white shadow' : 'text-slate-300 hover:bg-slate-800'
          }`}
        >
          <User className="w-3.5 h-3.5" />
          <span>Avatar 3D</span>
        </button>
        <button
          onClick={() => handleSwitchMode('LIVESTAGE')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
            activeMode === 'LIVESTAGE' ? 'bg-rose-600 text-white shadow' : 'text-slate-300 hover:bg-slate-800'
          }`}
        >
          <Radio className="w-3.5 h-3.5 text-rose-300" />
          <span>Live Stage</span>
        </button>
      </div>

      {/* Collapsible Unified Bottom Control Dock (Ergonomic, as mandated in Three.js guidelines) */}
      <div 
        className={`absolute bottom-3 left-1/2 -translate-x-1/2 z-20 w-[94%] max-w-3xl transition-transform duration-300 ${
          isCollapsed ? 'translate-y-[calc(100%-36px)]' : 'translate-y-0'
        }`}
      >
        {/* Collapse Toggle Handle */}
        <div className="flex justify-center mb-1">
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="flex items-center gap-1.5 px-4 py-1 rounded-t-lg bg-slate-900 border border-slate-700 text-slate-300 hover:text-white text-xs font-medium shadow-md transition"
          >
            {isCollapsed ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            <span>{isCollapsed ? '▴ Tampilkan Kontrol 3D' : '▾ Sembunyikan Kontrol (Cinema Mode)'}</span>
          </button>
        </div>

        {/* Dock Surface (Solid slate-900 surface, strictly no backdrop-filter over WebGL) */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-3.5 shadow-2xl text-white">
          {/* Mode 1: District Spatial Controls */}
          {activeMode === 'DISTRICT' && (
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 text-xs">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-cyan-400" />
                <span className="font-semibold text-slate-100">Crystal City Neo-Kyoto Atrium</span>
                <span className="text-slate-400">• 12 Kiosks & Skyscrapers</span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleSwitchMode('MARKETPLACE')}
                  className="px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 font-medium text-white transition flex items-center gap-1.5"
                >
                  <ShoppingBag className="w-3.5 h-3.5" />
                  <span>Kunjungi Booth Marketplace</span>
                </button>
                <button
                  onClick={() => handleSwitchMode('LIVESTAGE')}
                  className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 font-medium text-white transition flex items-center gap-1.5"
                >
                  <Radio className="w-3.5 h-3.5" />
                  <span>Masuk Podcast Live Stage</span>
                </button>
              </div>
            </div>
          )}

          {/* Mode 2: Marketplace Booth Controls */}
          {activeMode === 'MARKETPLACE' && (
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-slate-200">Pilih Booth Kiosk 3D untuk Inspeksi:</span>
                <span className="text-purple-400 text-[11px]">Mata uang: AI Credits & Rupiah (IDR)</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                <button
                  onClick={() => setSelectedBooth('neon-threads')}
                  className="p-2 rounded-xl bg-slate-800/80 hover:bg-slate-700/80 border border-pink-500/30 text-left transition"
                >
                  <p className="text-pink-400 font-bold text-xs">NEON THREADS</p>
                  <p className="text-[11px] text-slate-300">Digital Fashion • Rp 250k</p>
                </button>
                <button
                  onClick={() => setSelectedBooth('quantum-gear')}
                  className="p-2 rounded-xl bg-slate-800/80 hover:bg-slate-700/80 border border-cyan-500/30 text-left transition"
                >
                  <p className="text-cyan-400 font-bold text-xs">QUANTUM GEAR</p>
                  <p className="text-[11px] text-slate-300">Gadget & Drones • 45 Cr</p>
                </button>
                <button
                  onClick={() => setSelectedBooth('cyber-wear')}
                  className="p-2 rounded-xl bg-slate-800/80 hover:bg-slate-700/80 border border-purple-500/30 text-left transition"
                >
                  <p className="text-purple-400 font-bold text-xs">CYBER WEAR</p>
                  <p className="text-[11px] text-slate-300">Armor & Rig • Rp 150k</p>
                </button>
                <button
                  onClick={() => setSelectedBooth('ai-avatars')}
                  className="p-2 rounded-xl bg-slate-800/80 hover:bg-slate-700/80 border border-blue-500/30 text-left transition"
                >
                  <p className="text-blue-400 font-bold text-xs">AI AVATARS</p>
                  <p className="text-[11px] text-slate-300">Character Pack • 80 Cr</p>
                </button>
              </div>
            </div>
          )}

          {/* Mode 3: Avatar 3D Customizer Controls */}
          {activeMode === 'AVATAR' && (
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 text-xs">
              {/* Color Accents */}
              <div className="flex items-center gap-2">
                <span className="text-slate-300 font-medium">Aksen Armor:</span>
                <div className="flex items-center gap-1.5">
                  {[
                    { color: '#06b6d4', name: 'Cyan' },
                    { color: '#a855f7', name: 'Violet' },
                    { color: '#ec4899', name: 'Pink' },
                    { color: '#eab308', name: 'Gold' },
                  ].map((c) => (
                    <button
                      key={c.color}
                      onClick={() => setAvatarColor(c.color)}
                      className={`w-6 h-6 rounded-full border-2 transition ${
                        avatarColor === c.color ? 'border-white scale-110 shadow-lg' : 'border-transparent opacity-70'
                      }`}
                      style={{ backgroundColor: c.color }}
                      title={c.name}
                    />
                  ))}
                </div>
              </div>

              {/* Animation Poses */}
              <div className="flex items-center gap-1 bg-slate-800 p-1 rounded-lg">
                <button
                  onClick={() => setAvatarPose('idle')}
                  className={`px-2.5 py-1 rounded text-xs transition ${
                    avatarPose === 'idle' ? 'bg-blue-600 text-white' : 'text-slate-300 hover:text-white'
                  }`}
                >
                  Idle
                </button>
                <button
                  onClick={() => setAvatarPose('walk')}
                  className={`px-2.5 py-1 rounded text-xs transition ${
                    avatarPose === 'walk' ? 'bg-blue-600 text-white' : 'text-slate-300 hover:text-white'
                  }`}
                >
                  Walk
                </button>
                <button
                  onClick={() => setAvatarPose('present')}
                  className={`px-2.5 py-1 rounded text-xs transition ${
                    avatarPose === 'present' ? 'bg-blue-600 text-white' : 'text-slate-300 hover:text-white'
                  }`}
                >
                  Present
                </button>
                <button
                  onClick={() => setAvatarPose('wave')}
                  className={`px-2.5 py-1 rounded text-xs transition ${
                    avatarPose === 'wave' ? 'bg-blue-600 text-white' : 'text-slate-300 hover:text-white'
                  }`}
                >
                  Wave
                </button>
              </div>

              {/* Hologram wireframe toggle */}
              <button
                onClick={() => setIsHologramMode(!isHologramMode)}
                className={`px-3 py-1.5 rounded-lg border text-xs font-medium transition ${
                  isHologramMode
                    ? 'bg-cyan-600 border-cyan-400 text-white'
                    : 'bg-slate-800 border-slate-700 text-slate-300'
                }`}
              >
                Hologram Mesh
              </button>
            </div>
          )}

          {/* Mode 4: Live Stage Controls */}
          {activeMode === 'LIVESTAGE' && (
            <div className="flex flex-col gap-2.5">
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 text-xs">
                <div className="flex items-center gap-2">
                  <span className={`w-2.5 h-2.5 rounded-full ${isPodcastLive ? 'bg-rose-500' : 'bg-slate-500'}`} />
                  <span className="font-bold text-slate-100">Live Stage Podcast Studio</span>
                  <span className="text-slate-400">| Alex Tamara (Human) × Luna AI (AI Agent)</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-800 text-[11px] text-slate-300 font-mono">
                    <Volume2 className="w-3.5 h-3.5 text-cyan-400" />
                    <span>AUDIO FREQ: {audioMeter}%</span>
                  </div>
                  <button
                    onClick={() => setIsPodcastLive(!isPodcastLive)}
                    className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-bold transition ${
                      isPodcastLive
                        ? 'bg-rose-600 hover:bg-rose-700 text-white'
                        : 'bg-emerald-600 hover:bg-emerald-700 text-white'
                    }`}
                  >
                    {isPodcastLive ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
                    <span>{isPodcastLive ? 'Jeda Siaran' : 'Mulai Siaran'}</span>
                  </button>
                </div>
              </div>

              {/* Topic Selector */}
              <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                <span className="text-slate-400">Topik Diskusi:</span>
                {[
                  'Ekosistem Sosial Masa Depan: Human × AI Agent',
                  'Monetisasi 3D Virtual Worlds & Aset Digital',
                  'Kesehatan & Nutrisi Kerja Hybrid dengan MediAI',
                ].map((t) => (
                  <button
                    key={t}
                    onClick={() => setPodcastTopic(t)}
                    className={`px-2.5 py-1 rounded-lg transition truncate max-w-[280px] ${
                      podcastTopic === t
                        ? 'bg-cyan-950 border border-cyan-500 text-cyan-200'
                        : 'bg-slate-800 text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Selected 3D Booth Inspector Modal */}
      {selectedBooth && (
        <div className="absolute inset-0 z-30 flex items-center justify-center p-4 bg-black/60">
          <div className="w-full max-w-md rounded-2xl bg-slate-900 border border-purple-500/40 p-6 shadow-2xl text-white">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <ShoppingBag className="w-5 h-5 text-purple-400" />
                <h3 className="text-base font-bold text-slate-100">
                  {selectedBooth === 'neon-threads' && 'NEON THREADS • Booth Digital Fashion'}
                  {selectedBooth === 'quantum-gear' && 'QUANTUM GEAR • Booth Gadget & Drones'}
                  {selectedBooth === 'cyber-wear' && 'CYBER WEAR • Booth 3D Armor Rig'}
                  {selectedBooth === 'ai-avatars' && 'AI AVATARS • Neural Character Pack'}
                </h3>
              </div>
              <button
                onClick={() => setSelectedBooth(null)}
                className="text-slate-400 hover:text-white text-lg p-1"
              >
                ✕
              </button>
            </div>

            <div className="mt-4 space-y-3 text-xs">
              <p className="text-slate-300">
                Booth 3D ini terdaftar resmi di District Crystal City. Pengunjung dapat membeli lisensi aset 3D, mencoba langsung pada avatar, atau mengunduh paket glTF/FBX.
              </p>

              <div className="p-3 rounded-xl bg-slate-800/80 border border-slate-700 space-y-1.5">
                <div className="flex justify-between">
                  <span className="text-slate-400">Tenant / Creator:</span>
                  <span className="font-semibold text-slate-200">@dimasardi & @cybercraft</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Harga Lisensi:</span>
                  <span className="font-bold text-cyan-400">25 AI Credits / Rp 150.000</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Kompatibilitas:</span>
                  <span className="text-emerald-400">PWA, Three.js WebGL & Spatial Stage</span>
                </div>
              </div>
            </div>

            <div className="mt-6 flex items-center gap-2">
              <button
                onClick={() => {
                  alert('Item booth berhasil ditambahkan ke keranjang pembelian!');
                  setSelectedBooth(null);
                }}
                className="flex-1 py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-cyan-600 hover:from-purple-500 hover:to-cyan-500 text-white font-semibold text-xs shadow-lg transition"
              >
                Beli dengan AI Credits
              </button>
              <button
                onClick={() => setSelectedBooth(null)}
                className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition"
              >
                Tutup
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

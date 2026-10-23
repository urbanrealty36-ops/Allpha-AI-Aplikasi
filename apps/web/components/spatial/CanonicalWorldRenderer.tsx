"use client";

import { Component, Suspense, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Canvas, clear, useLoader } from "@react-three/fiber";
import { Group } from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { configureAllphaGLTFLoader } from "../../lib/spatial/configureAllphaGLTFLoader";
import { ALLPHA_ASSET_CATEGORIES, type AllphaAssetCategory } from "./CanonicalGlbPreview";

type SceneObject = {
  entity_id: string;
  asset_id: string;
  asset_version: number;
  category: AllphaAssetCategory;
  asset_url: string;
  sha256: string;
  byte_size: number;
  position: [number, number, number];
  rotation: [number, number, number];
  scale: [number, number, number];
  publication_status: "approved" | "published";
};
type SceneManifest = {
  schema_version: "1.0";
  scene_id: string;
  scene_version: number;
  world_id: string;
  coordinate_system: "right-handed-y-up";
  units: "meters";
  fallback_mode: "2d" | "low_detail";
  objects: SceneObject[];
};

class SceneErrorBoundary extends Component<{ children: ReactNode; onError: (error: Error) => void }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(error: Error) { this.props.onError(error); }
  render() { return this.state.failed ? null : this.props.children; }
}

function validateManifest(value: unknown): SceneManifest {
  if (!value || typeof value !== "object") throw new Error("Respons manifest bukan objek.");
  const m = value as Partial<SceneManifest>;
  if (m.schema_version !== "1.0" || typeof m.scene_id !== "string" || !m.scene_id.trim() || typeof m.world_id !== "string" || !m.world_id.trim() || !Number.isSafeInteger(m.scene_version) || (m.scene_version ?? 0) < 1 || m.coordinate_system !== "right-handed-y-up" || m.units !== "meters" || !["2d", "low_detail"].includes(m.fallback_mode as string) || !Array.isArray(m.objects) || m.objects.length > 500 || (m.objects.length === 0 && m.fallback_mode !== "2d")) {
    throw new Error("Versi atau struktur scene manifest tidak valid.");
  }
  const seen = new Set<string>();
  for (const object of m.objects) {
    if (!object || typeof object !== "object" || typeof object.entity_id !== "string" || !object.entity_id.trim() || seen.has(object.entity_id) || typeof object.asset_id !== "string" || !object.asset_id.trim() || !Number.isSafeInteger(object.asset_version) || object.asset_version < 1) throw new Error("ID entity/aset kosong, versi aset tidak valid, atau ID objek duplikat.");
    seen.add(object.entity_id);
    if (!ALLPHA_ASSET_CATEGORIES.includes(object.category) || !["approved", "published"].includes(object.publication_status)) throw new Error("Kategori atau status aset tidak diizinkan.");
    if (!/^https:\/\/[^\s]+$/i.test(object.asset_url) || !/^[a-f0-9]{64}$/i.test(object.sha256) || !Number.isSafeInteger(object.byte_size) || object.byte_size <= 0) throw new Error("Referensi atau integritas aset tidak valid.");
    for (const vector of [object.position, object.rotation, object.scale]) {
      if (!Array.isArray(vector) || vector.length !== 3 || vector.some((n) => !Number.isFinite(n))) throw new Error("Koordinat scene tidak valid.");
    }
    if (object.scale.some((n) => n <= 0)) throw new Error("Skala objek harus positif.");
  }
  return m as SceneManifest;
}

function SceneObjectModel({ object, onLoaded, onSelect, selected }: { object: SceneObject; onLoaded: (id: string) => void; onSelect: (id: string) => void; selected: boolean }) {
  const gltf = useLoader(GLTFLoader, object.asset_url, configureAllphaGLTFLoader);
  const model = useMemo(() => {
    const copy = new Group();
    copy.add(gltf.scene.clone(true));
    copy.position.set(...object.position);
    copy.rotation.set(...object.rotation);
    copy.scale.set(object.scale[0] * (selected ? 1.04 : 1), object.scale[1] * (selected ? 1.04 : 1), object.scale[2] * (selected ? 1.04 : 1));
    return copy;
  }, [gltf, object.position, object.rotation, object.scale, selected]);
  useEffect(() => { onLoaded(object.entity_id); }, [object.entity_id, onLoaded]);
  return <primitive object={model} onClick={(event: { stopPropagation: () => void }) => { event.stopPropagation(); onSelect(object.entity_id); }} />;
}

export function CanonicalWorldRenderer({ sceneKey, themeKey, apiBase }: { sceneKey?: string; themeKey?: string; apiBase?: string }) {
  const [manifest, setManifest] = useState<SceneManifest | null>(null);
  const [loadedIds, setLoadedIds] = useState<string[]>([]);
  const [selectedEntityId, setSelectedEntityId] = useState<string>("");
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const base = (apiBase || process.env.NEXT_PUBLIC_API_BASE_URL || "https://api.allpha.web.id").replace(/\/$/, "");
  const markLoaded = useCallback((id: string) => setLoadedIds((ids) => ids.includes(id) ? ids : [...ids, id]), []);

  useEffect(() => {
    const controller = new AbortController();
    setManifest(null); setLoadedIds([]); setSelectedEntityId(""); setError("");
    const key = themeKey || sceneKey || "";
    if (!/^[a-z0-9][a-z0-9._-]{2,119}$/.test(key) || Boolean(themeKey && sceneKey)) {
      setError("Kunci scene/Theme tidak valid.");
      return () => controller.abort();
    }
    const manifestPath = themeKey
      ? "/v1/spatial/themes/" + encodeURIComponent(themeKey) + "/manifest"
      : "/v1/spatial/scenes/" + encodeURIComponent(key) + "/manifest";
    void fetch(base + manifestPath, {
      signal: controller.signal, cache: "no-store", headers: { Accept: "application/json" },
    }).then(async (response) => {
      if (!response.ok) throw new Error(response.status === 404 ? (themeKey ? "Theme publik tidak ditemukan." : "Scene publik tidak ditemukan.") : "Manifest scene/Theme tidak tersedia (" + response.status + ").");
      return validateManifest(await response.json());
    }).then(setManifest).catch((cause: unknown) => {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Scene/Theme tidak dapat dimuat.");
    });
    return () => controller.abort();
  }, [sceneKey, themeKey, base, retry]);

  const retryScene = () => { manifest?.objects.forEach((object) => clear(GLTFLoader, object.asset_url)); setError(""); setManifest(null); setLoadedIds([]); setSelectedEntityId(""); setRetry((value) => value + 1); };
  const selectedObject = manifest?.objects.find((object) => object.entity_id === selectedEntityId) || null;
  return (
    <section aria-label="Allpha World Renderer" style={{ width: "100%" }}>
      {error && <div role="alert" style={{ padding: 16 }}>
        <p>Scene 3D tidak dapat ditampilkan.</p><p>{error}</p>
        <button type="button" onClick={retryScene}>Coba lagi</button>
        <p>Fallback: gunakan daftar objek scene setelah manifest tersedia.</p>
      </div>}
      {!error && !manifest && <p role="status" style={{ padding: 16 }}>Memuat manifest scene…</p>}
      {manifest && manifest.objects.length === 0 && manifest.fallback_mode === "2d" && <div role="status" style={{ padding: 16, border: "1px solid #d6dbe3", borderRadius: 12 }}><strong>Allpha Starter Universe</strong><p>Mode 2D aktif. Objek GLB akan tampil ketika tersedia pada manifest publik.</p></div>}
      {manifest && <p role="status" style={{ padding: 8 }}>
        {loadedIds.length < manifest.objects.length ? "Memuat objek " + loadedIds.length + "/" + manifest.objects.length : "Scene siap"} · {manifest.world_id} · v{manifest.scene_version}
      </p>}
      {manifest && !error && <div style={{ width: "100%", height: 420, minHeight: 280 }}>
        <SceneErrorBoundary key={manifest.scene_id + ":" + manifest.scene_version + ":" + retry} onError={(cause) => setError(cause.message || "Renderer gagal memuat scene.")}>
          <Canvas camera={{ position: [8, 6, 8], fov: 50 }} dpr={[1, 1.5]}>
            <color attach="background" args={["#eef1f5"]} />
            <ambientLight intensity={1.3} />
            <directionalLight position={[10, 14, 8]} intensity={2} />
            <gridHelper args={[40, 40, "#aab2bf", "#d6dbe3"]} />
            <Suspense fallback={null}>
              {manifest.objects.map((object) => <SceneObjectModel key={object.entity_id} object={object} onLoaded={markLoaded} onSelect={setSelectedEntityId} selected={object.entity_id === selectedEntityId} />)}
            </Suspense>
          </Canvas>
        </SceneErrorBoundary>
      </div>}
      {manifest && manifest.objects.length > 0 && <section aria-label="Spatial interactions" style={{ padding: 12, border: "1px solid #d6dbe3", borderRadius: 12, marginTop: 8 }}>
        <strong>Interaksi ruang</strong>
        {selectedObject ? <p role="status">{selectedObject.entity_id} · {selectedObject.category} · asset {selectedObject.asset_id} v{selectedObject.asset_version}</p> : <p>Pilih objek pada scene atau dari daftar untuk melihat detailnya.</p>}
        <ul aria-label="Daftar objek scene">
          {manifest.objects.map((object) => <li key={object.entity_id}><button type="button" aria-pressed={object.entity_id === selectedEntityId} onClick={() => setSelectedEntityId(object.entity_id)}>{object.entity_id} · {object.category} · v{object.asset_version}</button></li>)}
        </ul>
      </section>}
    </section>
  );
}

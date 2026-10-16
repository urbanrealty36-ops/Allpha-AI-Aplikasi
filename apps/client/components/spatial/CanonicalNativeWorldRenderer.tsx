import React, { Component, Suspense, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Pressable, Text, View } from "react-native";
import { Canvas, useLoader } from "@react-three/fiber/native";
import { Group } from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

const CATEGORY_KEYS = [
  "universe", "galaxy", "world", "orbit", "capsule", "district", "booth",
  "content-feed", "agent-character", "live-stage", "human-live",
  "sticker-social", "animation", "navigation-fx",
] as const;
type Category = (typeof CATEGORY_KEYS)[number];
type SceneObject = {
  entity_id: string; asset_id: string; asset_version: number; category: Category;
  asset_url: string; sha256: string; byte_size: number;
  position: [number, number, number]; rotation: [number, number, number]; scale: [number, number, number];
  publication_status: "approved" | "published";
};
type SceneManifest = {
  schema_version: "1.0"; scene_id: string; scene_version: number; world_id: string;
  coordinate_system: "right-handed-y-up"; units: "meters"; fallback_mode: "2d" | "low_detail";
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
  if (m.schema_version !== "1.0" || !m.scene_id || !m.world_id || !Array.isArray(m.objects) || m.objects.length < 1 || m.objects.length > 500) {
    throw new Error("Versi atau struktur scene manifest tidak valid.");
  }
  const seen = new Set<string>();
  for (const object of m.objects) {
    if (!object?.entity_id || seen.has(object.entity_id)) throw new Error("ID objek scene kosong atau duplikat.");
    seen.add(object.entity_id);
    if (!CATEGORY_KEYS.includes(object.category) || !["approved", "published"].includes(object.publication_status)) throw new Error("Kategori atau status aset tidak diizinkan.");
    if (!/^https:\/\//i.test(object.asset_url) || !/^[a-f0-9]{64}$/i.test(object.sha256) || !Number.isSafeInteger(object.byte_size) || object.byte_size <= 0) throw new Error("Referensi atau integritas aset tidak valid.");
    for (const vector of [object.position, object.rotation, object.scale]) {
      if (!Array.isArray(vector) || vector.length !== 3 || vector.some((n) => !Number.isFinite(n))) throw new Error("Koordinat scene tidak valid.");
    }
    if (object.scale.some((n) => n <= 0)) throw new Error("Skala objek harus positif.");
  }
  return m as SceneManifest;
}

function SceneObjectModel({ object, onLoaded }: { object: SceneObject; onLoaded: (id: string) => void }) {
  const gltf = useLoader(GLTFLoader, object.asset_url);
  const model = useMemo(() => {
    const copy = new Group();
    copy.add(gltf.scene.clone(true));
    copy.position.set(...object.position);
    copy.rotation.set(...object.rotation);
    copy.scale.set(...object.scale);
    return copy;
  }, [gltf, object.position, object.rotation, object.scale]);
  useEffect(() => { onLoaded(object.entity_id); }, [object.entity_id, onLoaded]);
  return <primitive object={model} />;
}

export function CanonicalNativeWorldRenderer({ sceneKey }: { sceneKey: string }) {
  const [manifest, setManifest] = useState<SceneManifest | null>(null);
  const [loadedIds, setLoadedIds] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const base = (process.env.EXPO_PUBLIC_API_BASE_URL || "https://api.allpha.web.id").replace(/\/$/, "");
  const markLoaded = useCallback((id: string) => setLoadedIds((ids) => ids.includes(id) ? ids : [...ids, id]), []);

  useEffect(() => {
    const controller = new AbortController();
    setManifest(null); setLoadedIds([]); setError("");
    if (!/^[a-z0-9][a-z0-9._-]{2,119}$/.test(sceneKey)) {
      setError("Kunci scene tidak valid.");
      return () => controller.abort();
    }
    void fetch(base + "/v1/spatial/scenes/" + encodeURIComponent(sceneKey) + "/manifest", {
      signal: controller.signal, headers: { Accept: "application/json" },
    }).then(async (response) => {
      if (!response.ok) throw new Error(response.status === 404 ? "Scene publik tidak ditemukan." : "Manifest scene tidak tersedia (" + response.status + ").");
      return validateManifest(await response.json());
    }).then(setManifest).catch((cause: unknown) => {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Scene tidak dapat dimuat.");
    });
    return () => controller.abort();
  }, [sceneKey, base, retry]);

  return (
    <View style={{ flex: 1 }}>
      {error ? (
        <View accessibilityRole="alert" style={{ padding: 16 }}>
          <Text>Scene 3D tidak dapat ditampilkan: {error}</Text>
          <Pressable onPress={() => { setError(""); setManifest(null); setLoadedIds([]); setRetry((value) => value + 1); }} accessibilityRole="button">
            <Text style={{ paddingVertical: 12 }}>Coba lagi</Text>
          </Pressable>
          <Text>Fallback: gunakan daftar objek scene jika manifest tersedia.</Text>
        </View>
      ) : !manifest ? (
        <Text accessibilityRole="progressbar" style={{ padding: 16 }}>Memuat manifest scene…</Text>
      ) : (
        <>
          <Text style={{ padding: 8 }}>{loadedIds.length < manifest.objects.length ? "Memuat objek " + loadedIds.length + "/" + manifest.objects.length : "Scene siap"} · {manifest.world_id} · v{manifest.scene_version}</Text>
          <View style={{ height: 360, width: "100%" }}>
            <SceneErrorBoundary key={manifest.scene_id + ":" + manifest.scene_version + ":" + retry} onError={(cause) => setError(cause.message || "Renderer gagal memuat scene.")}>
              <Canvas camera={{ position: [8, 6, 8], fov: 50 }}>
                <ambientLight intensity={1.3} />
                <directionalLight position={[10, 14, 8]} intensity={2} />
                <gridHelper args={[40, 40]} />
                <Suspense fallback={null}>
                  {manifest.objects.map((object) => <SceneObjectModel key={object.entity_id} object={object} onLoaded={markLoaded} />)}
                </Suspense>
              </Canvas>
            </SceneErrorBoundary>
          </View>
          {manifest.fallback_mode === "2d" && manifest.objects.map((object) => (
            <Text key={object.entity_id} style={{ paddingHorizontal: 12, paddingVertical: 4 }}>{object.category} · {object.asset_id} v{object.asset_version}</Text>
          ))}
        </>
      )}
    </View>
  );
}

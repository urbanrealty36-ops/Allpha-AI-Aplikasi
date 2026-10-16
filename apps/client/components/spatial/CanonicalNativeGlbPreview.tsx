import React, { Component, Suspense, useEffect, useMemo, useState, type ReactNode } from "react";
import { Pressable, Text, View, type StyleProp, type ViewStyle } from "react-native";
import { Canvas, useLoader } from "@react-three/fiber/native";
import { Box3, Group, Vector3 } from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader";

const CATEGORY_KEYS = [
  "universe", "galaxy", "world", "orbit", "capsule", "district", "booth",
  "content-feed", "agent-character", "live-stage", "human-live",
  "sticker-social", "animation", "navigation-fx",
] as const;
type Category = (typeof CATEGORY_KEYS)[number];

export type NativePublishedGlbManifestEntry = {
  asset_id: string;
  asset_version: number;
  category: Category;
  asset_url: string;
  sha256: string;
  byte_size: number;
  publication_status: "approved" | "published";
};

type Props = { asset: NativePublishedGlbManifestEntry; style?: StyleProp<ViewStyle> };

class RenderErrorBoundary extends Component<{ children: ReactNode; onError: (error: Error) => void }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(error: Error) { this.props.onError(error); }
  render() { return this.state.failed ? null : this.props.children; }
}

function Model({ url, onLoaded }: { url: string; onLoaded: () => void }) {
  const gltf = useLoader(GLTFLoader, url);
  const model = useMemo(() => {
    const root = new Group();
    const copy = gltf.scene.clone(true);
    const bounds = new Box3().setFromObject(copy);
    if (bounds.isEmpty()) throw new Error("GLB tidak memiliki geometri.");
    const size = bounds.getSize(new Vector3());
    const maxAxis = Math.max(size.x, size.y, size.z);
    if (!Number.isFinite(maxAxis) || maxAxis <= 0) throw new Error("Ukuran geometri tidak valid.");
    copy.position.sub(bounds.getCenter(new Vector3()));
    copy.scale.setScalar(2 / maxAxis);
    root.add(copy);
    return root;
  }, [gltf]);
  useEffect(() => { onLoaded(); }, [onLoaded]);
  return <primitive object={model} />;
}

export function CanonicalNativeGlbPreview({ asset, style }: Props) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const allowed = asset.publication_status === "approved" || asset.publication_status === "published";
  const valid = /^https:\/\//i.test(asset.asset_url)
    && /^[a-f0-9]{64}$/i.test(asset.sha256)
    && Number.isSafeInteger(asset.byte_size) && asset.byte_size > 0
    && CATEGORY_KEYS.includes(asset.category);

  if (!allowed || !valid) {
    return <View style={style} accessibilityRole="alert"><Text>Aset 3D tidak dapat dimuat: manifest tidak valid atau status publikasi tidak diizinkan.</Text></View>;
  }

  return (
    <View style={[{ minHeight: 300, overflow: "hidden" }, style]}>
      {!loaded && !error && <Text accessibilityRole="progressbar">Memuat aset 3D…</Text>}
      {error ? (
        <View accessibilityRole="alert">
          <Text>Aset 3D gagal dimuat: {error}</Text>
          <Pressable onPress={() => { setError(""); setLoaded(false); setRetry((n) => n + 1); }} accessibilityRole="button">
            <Text>Coba lagi</Text>
          </Pressable>
          <Text>Mode fallback: informasi aset 2D tersedia.</Text>
        </View>
      ) : (
        <View style={{ height: 280, width: "100%" }}>
          <RenderErrorBoundary key={asset.asset_url + ":" + retry} onError={(cause) => setError(cause.message || "Dekode GLB gagal.")}>
            <Canvas camera={{ position: [3, 2, 3], fov: 45 }}>
              <ambientLight intensity={1.6} />
              <directionalLight position={[4, 6, 5]} intensity={2} />
              <Suspense fallback={null}>
                <Model url={asset.asset_url} onLoaded={() => setLoaded(true)} />
              </Suspense>
            </Canvas>
          </RenderErrorBoundary>
        </View>
      )}
      <Text>{asset.asset_id} · v{asset.asset_version} · {asset.category} · {(asset.byte_size / 1024 / 1024).toFixed(2)} MB</Text>
    </View>
  );
}

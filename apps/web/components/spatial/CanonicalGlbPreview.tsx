"use client";

import { Component, Suspense, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Canvas, useLoader } from "@react-three/fiber";
import { Box3, Group, Vector3 } from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

export const ALLPHA_ASSET_CATEGORIES = [
  "universe", "galaxy", "world", "orbit", "capsule", "district", "booth",
  "content-feed", "agent-character", "live-stage", "human-live",
  "sticker-social", "animation", "navigation-fx",
] as const;

export type AllphaAssetCategory = (typeof ALLPHA_ASSET_CATEGORIES)[number];
export type PublishedGlbManifestEntry = {
  asset_id: string;
  asset_version: number;
  category: AllphaAssetCategory;
  asset_url: string;
  sha256: string;
  byte_size: number;
  publication_status: "approved" | "published";
};

type Props = { asset: PublishedGlbManifestEntry; className?: string; label?: string };

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
    if (bounds.isEmpty()) throw new Error("GLB tidak memiliki geometri yang dapat ditampilkan.");
    const size = bounds.getSize(new Vector3());
    const maxAxis = Math.max(size.x, size.y, size.z);
    if (!Number.isFinite(maxAxis) || maxAxis <= 0) throw new Error("Ukuran geometri GLB tidak valid.");
    copy.position.sub(bounds.getCenter(new Vector3()));
    copy.scale.setScalar(2 / maxAxis);
    root.add(copy);
    return root;
  }, [gltf]);
  useEffect(() => { onLoaded(); }, [onLoaded]);
  return <primitive object={model} />;
}

export function CanonicalGlbPreview({ asset, className, label = "Pratinjau aset 3D Allpha" }: Props) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const markLoaded = useCallback(() => setLoaded(true), []);
  const validUrl = /^https:\/\//i.test(asset.asset_url);
  const validDigest = /^[a-f0-9]{64}$/i.test(asset.sha256);
  const validSize = Number.isSafeInteger(asset.byte_size) && asset.byte_size > 0;
  const approved = asset.publication_status === "approved" || asset.publication_status === "published";
  const validCategory = ALLPHA_ASSET_CATEGORIES.includes(asset.category);

  if (!approved || !validUrl || !validDigest || !validSize || !validCategory) {
    return <div role="alert" className={className}>Aset 3D tidak dapat dimuat: manifest tidak valid atau status publikasi tidak diizinkan.</div>;
  }

  return (
    <section className={className} aria-label={label} style={{ position: "relative", minHeight: 280, overflow: "hidden" }}>
      {!loaded && !error && <div role="status" style={{ padding: 12 }}>Memuat aset 3D…</div>}
      {error && <div role="alert" style={{ padding: 12 }}>
        <p>Aset 3D gagal dimuat.</p>
        <p>{error}</p>
        <button type="button" onClick={() => { setError(""); setLoaded(false); setRetry((n) => n + 1); }}>Coba lagi</button>
      </div>}
      {!error && <div style={{ height: 320, width: "100%" }}>
        <RenderErrorBoundary key={asset.asset_url + ":" + retry} onError={(cause) => setError(cause.message || "Dekode GLB gagal.")}>
          <Canvas camera={{ position: [3, 2, 3], fov: 45 }} dpr={[1, 1.5]}>
            <color attach="background" args={["#f4f5f7"]} />
            <ambientLight intensity={1.6} />
            <directionalLight position={[4, 6, 5]} intensity={2} />
            <Suspense fallback={null}>
              <Model url={asset.asset_url} onLoaded={markLoaded} />
            </Suspense>
          </Canvas>
        </RenderErrorBoundary>
      </div>}
      <p style={{ fontSize: 12, padding: "4px 10px", color: "#4b5563" }}>
        {asset.asset_id} · v{asset.asset_version} · {asset.category} · {(asset.byte_size / 1024 / 1024).toFixed(2)} MB
      </p>
    </section>
  );
}

import { CanonicalWorldRenderer } from "../../../components/spatial/CanonicalWorldRenderer";

export default async function SpatialScenePage({ params }: { params: Promise<{ sceneKey: string }> }) {
  const { sceneKey } = await params;
  return (
    <main style={{ margin: "0 auto", maxWidth: 1200, padding: 24, color: "#111827" }}>
      <header style={{ marginBottom: 20 }}>
        <p style={{ fontSize: 12, letterSpacing: 1, textTransform: "uppercase", color: "#6b7280" }}>Allpha Universe</p>
        <h1 style={{ fontSize: 28, fontWeight: 650 }}>World Renderer</h1>
        <p style={{ color: "#4b5563" }}>Scene publik dimuat melalui manifest yang disediakan API kanonis.</p>
      </header>
      <CanonicalWorldRenderer sceneKey={sceneKey} />
    </main>
  );
}

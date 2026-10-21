import { CanonicalWorldRenderer } from "../../../components/spatial/CanonicalWorldRenderer";

export default async function PublishedThemePage({ params }: { params: Promise<{ themeKey: string }> }) {
  const { themeKey } = await params;
  return (
    <main style={{ margin: "0 auto", maxWidth: 1200, padding: 24, color: "#111827" }}>
      <header style={{ marginBottom: 20 }}>
        <p style={{ fontSize: 12, letterSpacing: 1, textTransform: "uppercase", color: "#6b7280" }}>Allpha Universe · Theme Catalog</p>
        <h1 style={{ fontSize: 28, fontWeight: 650 }}>Theme Renderer</h1>
        <p style={{ color: "#4b5563" }}>Theme dan aset versi published dimuat melalui manifest API kanonis. Draft dan aset yang belum disetujui tidak dapat dimuat di halaman publik.</p>
      </header>
      <CanonicalWorldRenderer themeKey={themeKey} />
    </main>
  );
}

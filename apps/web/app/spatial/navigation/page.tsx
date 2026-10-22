import Link from "next/link";
import { SpatialNavigationBrowser } from "../../../components/spatial/SpatialNavigationBrowser";

export default function SpatialNavigationPage() {
  return (
    <main style={{ maxWidth: 1240, margin: "0 auto", padding: "20px 16px", color: "#e8edf7" }}>
      <header style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: 12 }}>
        <div><p style={{ color: "#94a3b8", fontSize: 12, letterSpacing: 1.5, textTransform: "uppercase" }}>Allpha Universe · Spatial</p><h1 style={{ fontSize: 28, fontWeight: 750, margin: "6px 0" }}>Navigasi Universe</h1></div>
        <Link href="/spatial/themes" style={{ color: "#c7d2fe", border: "1px solid #39465f", borderRadius: 10, padding: "10px 14px", textDecoration: "none" }}>Buka Theme Universe →</Link>
      </header>
      <SpatialNavigationBrowser />
    </main>
  );
}

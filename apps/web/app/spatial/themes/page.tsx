"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CanonicalWorldRenderer } from "../../../components/spatial/CanonicalWorldRenderer";
import RequireSession from "../../../components/RequireSession";
import { getBrowserSupabase } from "../../../lib/supabase";

const API = (process.env.NEXT_PUBLIC_API_BASE_URL || "https://api.allpha.web.id").replace(/\/$/, "");
type Theme = {
  theme_key: string;
  display_name: string;
  description?: string;
  active_version: number;
  updated_at?: string;
};

export default function SpatialThemesPage() {
  const [items, setItems] = useState<Theme[]>([]);
  const [selected, setSelected] = useState<Theme | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    void (async () => {
      try {
        const supabase = getBrowserSupabase();
        const { data } = supabase ? await supabase.auth.getSession() : { data: { session: null } };
        if (!data.session) throw new Error("Masuk untuk membuka katalog Theme Universe.");
        const response = await fetch(API + "/v1/spatial/themes?limit=100&offset=0", {
          signal: controller.signal,
          cache: "no-store",
          headers: { Accept: "application/json", Authorization: "Bearer " + data.session.access_token },
        });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        const message = body?.detail?.message || "Katalog Theme tidak tersedia.";
        throw new Error(message + " (" + response.status + ")");
      }
        if (!controller.signal.aborted) setItems(Array.isArray(body.items) ? body.items : []);
      } catch (cause: unknown) {
        if (!controller.signal.aborted) {
          setItems([]);
          setError(cause instanceof Error ? cause.message : "Katalog Theme gagal dimuat.");
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    })();
    return () => controller.abort();
  }, [retry]);

  return (
    <RequireSession title="Universe 3D" description="Masuk untuk membuka Theme Universe dan menjalankan renderer 3D."><><main className="allpha-page allpha-spatial-page" style={{ maxWidth: 1180, margin: "0 auto", padding: "24px 16px 48px", color: "#e8edf7" }}>
      <header style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 16, marginBottom: 24 }}>
        <div>
          <p style={{ color: "#94a3b8", fontSize: 12, letterSpacing: 1.5, textTransform: "uppercase" }}>Allpha Universe · Spatial</p>
          <h1 style={{ fontSize: 32, lineHeight: 1.15, fontWeight: 750, margin: "8px 0" }}>Theme Universe</h1>
          <p style={{ color: "#aab5ca", maxWidth: 680 }}>Pilih dunia yang telah dipublikasikan. Katalog dan manifest berasal dari API kanonis; Theme draft dan aset yang belum lolos approval tidak ditampilkan.</p>
        </div>
        <Link href="/spatial/navigation" style={{ color: "#c7d2fe", border: "1px solid #39465f", borderRadius: 10, padding: "10px 14px", textDecoration: "none" }}>Jelajahi navigasi Universe</Link>
      </header>

      {loading ? <p role="status" style={{ padding: 18, border: "1px solid #293548", borderRadius: 12 }}>Memuat katalog Theme…</p> :
        error ? <section role="alert" style={{ padding: 18, border: "1px solid #7f1d1d", borderRadius: 12, background: "#1c1015" }}>
          <strong>Katalog belum dapat dimuat</strong>
          <p style={{ color: "#fecaca" }}>{error}</p>
          <button type="button" onClick={() => setRetry((value) => value + 1)} style={{ border: "1px solid #64748b", borderRadius: 8, padding: "9px 12px", color: "#f8fafc", background: "#172033", cursor: "pointer" }}>Coba lagi</button>
        </section> :
        items.length === 0 ? <section style={{ padding: 22, border: "1px solid #293548", borderRadius: 14, background: "#0b1220" }}>
          <h2 style={{ fontSize: 20, fontWeight: 650, margin: "0 0 8px" }}>Belum ada Theme publik</h2>
          <p style={{ color: "#aab5ca", margin: 0 }}>Katalog akan terisi setelah Theme memiliki manifest lengkap dengan aset yang sudah lolos validasi, moderasi, dan pemeriksaan hak penggunaan. Tidak ada data contoh yang ditampilkan.</p>
        </section> :
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 250px), 1fr))", gap: 12 }}>
          {items.map((theme) => <button key={theme.theme_key} type="button" onClick={() => setSelected(theme)} aria-pressed={selected?.theme_key === theme.theme_key} style={{ textAlign: "left", padding: 16, border: "1px solid " + (selected?.theme_key === theme.theme_key ? "#818cf8" : "#293548"), borderRadius: 14, background: selected?.theme_key === theme.theme_key ? "#151b35" : "#0b1220", color: "#e8edf7", cursor: "pointer" }}>
            <span style={{ display: "block", fontSize: 17, fontWeight: 700 }}>{theme.display_name}</span>
            <span style={{ display: "block", color: "#a5b4fc", fontSize: 12, marginTop: 5 }}>{theme.theme_key} · v{theme.active_version}</span>
            {theme.description && <span style={{ display: "block", color: "#aab5ca", fontSize: 13, marginTop: 8 }}>{theme.description}</span>}
          </button>)}
        </div>}

      {selected && <section style={{ marginTop: 24, border: "1px solid #293548", borderRadius: 16, padding: 16, background: "#0b1220" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: 8 }}>
          <div><h2 style={{ fontSize: 21, fontWeight: 700, margin: 0 }}>{selected.display_name}</h2><p style={{ color: "#aab5ca", margin: "4px 0 0" }}>Theme {selected.theme_key} · versi {selected.active_version}</p></div>
          <button type="button" onClick={() => setSelected(null)} style={{ border: "1px solid #39465f", borderRadius: 8, padding: "8px 12px", background: "#111a2d", color: "#e8edf7", cursor: "pointer" }}>Tutup</button>
        </div>
        <CanonicalWorldRenderer themeKey={selected.theme_key} />
      </section>}
    </main></></RequireSession>
  );
}

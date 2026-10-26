"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../../../lib/supabase";
import { SpatialNavigationBrowser } from "../../../../components/spatial/SpatialNavigationBrowser";

export default function SpatialNavigationCatalogPage() {
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [resolved, setResolved] = useState(false);

  useEffect(() => {
    if (!supabase) { setResolved(true); return; }
    let active = true;
    void supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      setSession(data.session);
      setResolved(true);
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, next) => {
      if (!active) return;
      setSession(next);
      setResolved(true);
    });
    return () => { active = false; listener.subscription.unsubscribe(); };
  }, [supabase]);

  if (!resolved) return <main className="min-h-[50dvh] p-6" role="status">Memeriksa sesi Allpha…</main>;
  if (!session) return (
    <main className="mx-auto flex min-h-[70dvh] max-w-xl items-center justify-center px-5">
      <section className="w-full rounded-2xl border-2 border-slate-900 bg-white p-5 text-slate-950 shadow-[3px_3px_0px_#0f172a]">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-indigo-700">Allpha Universe · Spatial</p>
        <h1 className="mt-2 text-xl font-black">Login diperlukan</h1>
        <p className="mt-2 text-sm text-slate-600">Katalog navigasi Universe hanya dapat dibuka setelah login.</p>
        <Link className="mt-4 inline-flex rounded-xl border-2 border-slate-900 bg-indigo-300 px-4 py-2 text-sm font-black text-slate-950" href={"/login?next=" + encodeURIComponent("/spatial/navigation/catalog")}>Daftar / Login</Link>
      </section>
    </main>
  );

  return (
    <main className="allpha-page allpha-spatial-page" style={{ maxWidth: 1240, margin: "0 auto", padding: "20px 16px", color: "#e8edf7" }}>
      <header style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: 12 }}>
        <div>
          <p style={{ color: "#94a3b8", fontSize: 12, letterSpacing: 1.5, textTransform: "uppercase" }}>Allpha Universe · Spatial</p>
          <h1 style={{ fontSize: 28, fontWeight: 750, margin: "6px 0" }}>Katalog Navigasi Universe</h1>
        </div>
        <Link href="/spatial/navigation" style={{ color: "#c7d2fe", border: "1px solid #39465f", borderRadius: 10, padding: "10px 14px", textDecoration: "none" }}>Kembali ke Dunia 3D →</Link>
      </header>
      <SpatialNavigationBrowser />
    </main>
  );
}

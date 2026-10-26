"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../../lib/supabase";
import Universe3DHubView from "../../../components/reference-ui/Universe3DHubView";

export default function Universe3DHubPage() {
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
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-indigo-700">Allpha Universe 3D</p>
        <h1 className="mt-2 text-xl font-black">Login diperlukan</h1>
        <p className="mt-2 text-sm text-slate-600">Universe Hub dan perpindahan dunia interaktif hanya tersedia untuk pengguna yang sudah masuk. Tidak ada sesi 3D yang dimulai untuk pengunjung publik.</p>
        <Link className="mt-4 inline-flex rounded-xl border-2 border-slate-900 bg-indigo-300 px-4 py-2 text-sm font-black text-slate-950" href={"/login?next=" + encodeURIComponent("/spatial/universe-hub")}>Daftar / Login</Link>
      </section>
    </main>
  );

  return (
    <Universe3DHubView
      onBackToFeed={() => window.location.assign("/feed")}
      userCredits={null}
      agentCredits={null}
      productionMode
    />
  );
}

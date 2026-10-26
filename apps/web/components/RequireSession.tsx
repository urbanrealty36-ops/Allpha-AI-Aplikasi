"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import Link from "next/link";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../lib/supabase";

export default function RequireSession({ children, title = "Fitur Allpha", description = "Masuk ke Allpha untuk melanjutkan." }: {
  children: ReactNode;
  title?: string;
  description?: string;
}) {
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    if (!supabase) { setSession(null); setChecking(false); return; }
    let active = true;
    void supabase.auth.getSession().then(({ data }) => {
      if (active) { setSession(data.session); setChecking(false); }
    }).catch(() => { if (active) { setSession(null); setChecking(false); } });
    const { data } = supabase.auth.onAuthStateChange((_event, next) => {
      if (active) { setSession(next); setChecking(false); }
    });
    return () => { active = false; data.subscription.unsubscribe(); };
  }, [supabase]);

  if (checking) return <main className="mx-auto flex min-h-[60dvh] max-w-xl items-center justify-center px-4 text-sm text-slate-600" role="status">Memeriksa sesi Allpha…</main>;
  if (!session) return <main className="mx-auto flex min-h-[60dvh] items-center justify-center bg-sky-50 px-4 py-8 text-slate-900"><section className="w-full max-w-md rounded-3xl border-2 border-slate-900 bg-white p-6 shadow-[3px_3px_0px_#0f172a]" aria-labelledby="allpha-auth-required-title"><p className="text-xs font-black uppercase tracking-wider text-sky-700">Allpha Universe</p><h1 id="allpha-auth-required-title" className="mt-2 text-lg font-black">{title}</h1><p className="my-3 text-sm leading-6 text-slate-600">{description}</p><p className="mb-4 text-xs text-slate-500">Fitur ini terkunci untuk pengunjung. Tidak ada sesi 3D, permintaan Agent, atau generasi AI yang dijalankan sebelum login.</p><Link className="inline-flex rounded-2xl border-2 border-slate-900 bg-sky-300 px-4 py-2.5 text-sm font-black text-slate-950 shadow-[2px_2px_0px_#0f172a]" href={"/login?next=" + encodeURIComponent(typeof window === "undefined" ? "/" : window.location.pathname + window.location.search)}>Masuk / Daftar</Link></section></main>;
  return <>{children}</>;
}

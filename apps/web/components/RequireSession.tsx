"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import Link from "next/link";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../lib/supabase";
import { verifyBackendSession } from "../lib/auth-validation.mjs";

const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

type SessionStatus = "checking" | "unavailable" | "unauthenticated" | "authenticated";

export default function RequireSession({ children, title = "Fitur Allpha", description = "Masuk ke Allpha untuk melanjutkan." }: {
  children: ReactNode;
  title?: string;
  description?: string;
}) {
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [status, setStatus] = useState<SessionStatus>("checking");
  const [retryNonce, setRetryNonce] = useState(0);

  useEffect(() => {
    if (!supabase) {
      setSession(null);
      setStatus("unavailable");
      return;
    }

    let active = true;
    let generation = 0;

    const validateSession = async (candidate: Session | null) => {
      const currentGeneration = ++generation;
      if (!candidate) {
        setSession(null);
        setStatus("unauthenticated");
        return;
      }

      setStatus("checking");
      try {
        const { data, error } = await supabase.auth.getUser(candidate.access_token);
        if (!active || currentGeneration !== generation) return;

        if (error) {
          const statusCode = (error as { status?: number }).status;
          if (statusCode === 401 || statusCode === 403) {
            await supabase.auth.signOut({ scope: "local" });
            if (active && currentGeneration === generation) {
              setSession(null);
              setStatus("unauthenticated");
            }
            return;
          }
          setSession(null);
          setStatus("unavailable");
          return;
        }

        if (!data.user || data.user.id !== candidate.user.id) {
          await supabase.auth.signOut({ scope: "local" });
          if (active && currentGeneration === generation) {
            setSession(null);
            setStatus("unauthenticated");
          }
          return;
        }

        // Supabase Auth validates token signature/expiry. FastAPI then applies
        // auth.sessions revocation fencing and returns the canonical account state.
        const backend = await verifyBackendSession(apiBase, candidate);
        if (!active || currentGeneration !== generation) return;

        if (backend.status === "rejected") {
          await supabase.auth.signOut({ scope: "local" });
          if (active && currentGeneration === generation) {
            setSession(null);
            setStatus("unauthenticated");
          }
          return;
        }
        if (backend.status !== "valid") {
          setSession(null);
          setStatus("unavailable");
          return;
        }

        setSession(candidate);
        setStatus("authenticated");
      } catch {
        if (active && currentGeneration === generation) {
          setSession(null);
          setStatus("unavailable");
        }
      }
    };

    const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      void Promise.resolve().then(() => validateSession(nextSession));
    });

    const initialGeneration = generation;
    void supabase.auth.getSession().then(({ data: current, error }) => {
      if (!active || generation !== initialGeneration) return;
      if (error) {
        setSession(null);
        setStatus("unavailable");
        return;
      }
      void validateSession(current.session);
    }).catch(() => {
      if (active && generation === initialGeneration) {
        setSession(null);
        setStatus("unavailable");
      }
    });

    return () => {
      active = false;
      generation += 1;
      data.subscription.unsubscribe();
    };
  }, [supabase, retryNonce]);

  if (status === "checking") {
    return <main className="mx-auto flex min-h-[60dvh] max-w-xl items-center justify-center px-4 text-sm text-slate-600" role="status">Memeriksa sesi Allpha…</main>;
  }

  if (status === "unavailable") {
    return (
      <main className="mx-auto flex min-h-[60dvh] items-center justify-center bg-sky-50 px-4 py-8 text-slate-900">
        <section className="w-full max-w-md rounded-3xl border-2 border-slate-900 bg-white p-6 shadow-[3px_3px_0px_#0f172a]" aria-labelledby="allpha-auth-unavailable-title">
          <p className="text-xs font-black uppercase tracking-wider text-sky-700">Allpha Universe</p>
          <h1 id="allpha-auth-unavailable-title" className="mt-2 text-lg font-black">Sesi belum dapat diverifikasi</h1>
          <p className="my-3 text-sm leading-6 text-slate-600">Layanan autentikasi sedang tidak dapat dijangkau. Sesi lokal tidak dihapus. Coba verifikasi kembali sebelum melanjutkan.</p>
          <button type="button" onClick={() => { setStatus("checking"); setRetryNonce((value) => value + 1); }} className="inline-flex rounded-2xl border-2 border-slate-900 bg-sky-300 px-4 py-2.5 text-sm font-black text-slate-950 shadow-[2px_2px_0px_#0f172a]">Coba lagi</button>
        </section>
      </main>
    );
  }

  if (status === "unauthenticated" || !session) {
    return (
      <main className="mx-auto flex min-h-[60dvh] items-center justify-center bg-sky-50 px-4 py-8 text-slate-900">
        <section className="w-full max-w-md rounded-3xl border-2 border-slate-900 bg-white p-6 shadow-[3px_3px_0px_#0f172a]" aria-labelledby="allpha-auth-required-title">
          <p className="text-xs font-black uppercase tracking-wider text-sky-700">Allpha Universe</p>
          <h1 id="allpha-auth-required-title" className="mt-2 text-lg font-black">{title}</h1>
          <p className="my-3 text-sm leading-6 text-slate-600">{description}</p>
          <p className="mb-4 text-xs text-slate-500">Fitur ini terkunci untuk pengunjung. Tidak ada permintaan Agent atau generasi AI yang dijalankan sebelum login.</p>
          <Link className="inline-flex rounded-2xl border-2 border-slate-900 bg-sky-300 px-4 py-2.5 text-sm font-black text-slate-950 shadow-[2px_2px_0px_#0f172a]" href={"/login?next=" + encodeURIComponent(typeof window === "undefined" ? "/" : window.location.pathname + window.location.search)}>Masuk / Daftar</Link>
        </section>
      </main>
    );
  }

  return <>{children}</>;
}

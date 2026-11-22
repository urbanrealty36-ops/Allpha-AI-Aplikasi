"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { getBrowserSupabase } from "@/lib/supabase";

function safeNext(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\") || /^\/(login|register|auth\/)/.test(value)) return "/start";
  return value;
}

export default function AuthCallbackPage() {
  const router = useRouter();
  const params = typeof window === "undefined" ? new URLSearchParams() : new URLSearchParams(window.location.search);
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [message, setMessage] = useState("Memverifikasi identitas dan memulihkan sesi…");
  const [error, setError] = useState("");
  const [retryNonce, setRetryNonce] = useState(0);
  const codeExchangeCompleted = useRef(false);
  const codeExchangeAttempted = useRef(false);
  const accessTokenBeforeExchange = useRef<string | null>(null);
  const codeExchangePromise = useRef<Promise<void> | null>(null);

  useEffect(() => {
    let active = true;
    const run = async () => {
      if (!supabase) { setError("Supabase Auth belum dikonfigurasi."); return; }
      try {
        const code = params.get("code");
        if (code && !codeExchangeCompleted.current) {
          // Never let an unrelated, already-persisted session bypass the OAuth
          // code exchange. This matters when a different account was signed in
          // before the callback URL was opened.
          if (!codeExchangePromise.current) {
            codeExchangePromise.current = (async () => {
              if (!codeExchangeAttempted.current) {
                const { data: beforeExchange, error: beforeError } = await supabase.auth.getSession();
                if (beforeError) throw beforeError;
                accessTokenBeforeExchange.current = beforeExchange.session?.access_token ?? null;
                codeExchangeAttempted.current = true;
              } else {
                // Supabase may persist the new session even when the browser
                // loses the exchange response. Accept it only if the token
                // changed from the session captured before the first exchange.
                const { data: recovered, error: recoveryError } = await supabase.auth.getSession();
                if (recoveryError) throw recoveryError;
                if (recovered.session && recovered.session.access_token !== accessTokenBeforeExchange.current) {
                  codeExchangeCompleted.current = true;
                  return;
                }
              }

              const { error: exchangeError } = await supabase.auth.exchangeCodeForSession(code);
              if (exchangeError) {
                const { data: recovered, error: recoveryError } = await supabase.auth.getSession();
                if (recoveryError) throw recoveryError;
                if (recovered.session && recovered.session.access_token !== accessTokenBeforeExchange.current) {
                  codeExchangeCompleted.current = true;
                  return;
                }
                throw exchangeError;
              }
              codeExchangeCompleted.current = true;
            })();
          }
          try {
            await codeExchangePromise.current;
          } catch (exchangeFailure) {
            codeExchangePromise.current = null;
            throw exchangeFailure;
          }
        }
        const { data, error: sessionError } = await supabase.auth.getSession();
        if (sessionError) throw sessionError;
        if (!data.session) throw new Error("Tautan autentikasi tidak menghasilkan sesi. Silakan masuk kembali.");
        const { data: userData, error: userError } = await supabase.auth.getUser(data.session.access_token);
        if (userError) {
          const statusCode = (userError as { status?: number }).status;
          if (statusCode === 401 || statusCode === 403) {
            await supabase.auth.signOut({ scope: "local" });
            throw new Error("Sesi autentikasi ditolak. Silakan mulai login kembali.");
          }
          throw new Error("Layanan autentikasi sementara tidak tersedia. Sesi lokal dipertahankan; coba lagi.");
        }
        if (!userData.user || userData.user.id !== data.session.user.id) {
          await supabase.auth.signOut({ scope: "local" });
          throw new Error("Identitas pengguna tidak cocok dengan sesi yang dipulihkan.");
        }
        if (!active) return;
        setMessage("Verifikasi berhasil. Menyiapkan akun Allpha…");
        router.replace(safeNext(params.get("next")));
      } catch (cause) {
        if (active) {
          setError(cause instanceof Error ? cause.message : "Verifikasi autentikasi gagal.");
          setMessage("Verifikasi belum selesai.");
        }
      }
    };
    void run();
    return () => { active = false; };
  }, [router, supabase, retryNonce]);

  return <main className="grid min-h-screen place-items-center bg-slate-50 p-6 text-slate-900"><section className="w-full max-w-md rounded-3xl border-2 border-slate-900 bg-white p-7 shadow-[4px_4px_0px_#0f172a]" aria-live="polite"><p className="text-xs font-black uppercase tracking-widest text-sky-700">ALLPHA UNIVERSE</p><h1 className="mt-3 text-xl font-black">Verifikasi akun</h1><p className="mt-3 text-sm text-slate-600">{error || message}</p>{error && <div className="mt-5 flex flex-wrap gap-3"><button type="button" className="inline-flex rounded-xl border-2 border-slate-900 bg-sky-300 px-4 py-2 text-sm font-black" onClick={() => { setError(""); setMessage("Mencoba memulihkan sesi…"); setRetryNonce((value) => value + 1); }}>Coba lagi</button><a className="inline-flex rounded-xl border-2 border-slate-900 bg-white px-4 py-2 text-sm font-black" href="/login">Kembali ke Login</a></div>}</section></main>;
}

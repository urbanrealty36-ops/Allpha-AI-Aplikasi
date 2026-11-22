"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getBrowserSupabase } from "@/lib/supabase";

function safeNext(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\") || /^\/(login|register|auth\/)/.test(value)) return "/start";
  return value;
}

export default function AuthCallbackPage() {
  const router = useRouter();
  const params = useSearchParams();
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [message, setMessage] = useState("Memverifikasi identitas dan memulihkan sesi…");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    const run = async () => {
      if (!supabase) { setError("Supabase Auth belum dikonfigurasi."); return; }
      try {
        const code = params.get("code");
        if (code) {
          const { error: exchangeError } = await supabase.auth.exchangeCodeForSession(code);
          if (exchangeError) throw exchangeError;
        }
        const { data, error: sessionError } = await supabase.auth.getSession();
        if (sessionError) throw sessionError;
        if (!data.session) throw new Error("Tautan autentikasi tidak menghasilkan sesi. Silakan masuk kembali.");
        const { data: userData, error: userError } = await supabase.auth.getUser(data.session.access_token);
        if (userError || !userData.user) throw userError ?? new Error("Identitas pengguna tidak dapat diverifikasi.");
        if (!active) return;
        setMessage("Verifikasi berhasil. Menyiapkan akun Allpha…");
        router.replace(safeNext(params.get("next")));
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : "Verifikasi autentikasi gagal.");
      }
    };
    void run();
    return () => { active = false; };
  }, [params, router, supabase]);

  return <main className="grid min-h-screen place-items-center bg-slate-50 p-6 text-slate-900"><section className="w-full max-w-md rounded-3xl border-2 border-slate-900 bg-white p-7 shadow-[4px_4px_0px_#0f172a]" aria-live="polite"><p className="text-xs font-black uppercase tracking-widest text-sky-700">ALLPHA UNIVERSE</p><h1 className="mt-3 text-xl font-black">Verifikasi akun</h1><p className="mt-3 text-sm text-slate-600">{error || message}</p>{error && <a className="mt-5 inline-flex rounded-xl border-2 border-slate-900 bg-sky-300 px-4 py-2 text-sm font-black" href="/login">Kembali ke Login</a>}</section></main>;
}

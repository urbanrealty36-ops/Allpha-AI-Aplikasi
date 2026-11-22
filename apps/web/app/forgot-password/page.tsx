"use client";

import { FormEvent, useMemo, useState } from "react";
import { getBrowserSupabase } from "@/lib/supabase";

export default function ForgotPasswordPage() {
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault(); setError(""); setMessage("");
    if (!supabase) { setError("Supabase Auth belum dikonfigurasi."); return; }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) { setError("Masukkan alamat email yang valid."); return; }
    setBusy(true);
    try {
      const redirectTo = window.location.origin + "/auth/callback?next=%2Freset-password";
      const { error: resetError } = await supabase.auth.resetPasswordForEmail(email.trim(), { redirectTo });
      if (resetError) throw resetError;
      setMessage("Jika akun tersedia, instruksi pemulihan akan dikirim ke email tersebut. Periksa inbox dan folder spam.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Permintaan pemulihan gagal."); }
    finally { setBusy(false); }
  }

  return <main className="grid min-h-screen place-items-center bg-slate-50 p-6 text-slate-900"><form onSubmit={submit} className="w-full max-w-md rounded-3xl border-2 border-slate-900 bg-white p-7 shadow-[4px_4px_0px_#0f172a]"><p className="text-xs font-black uppercase tracking-widest text-sky-700">ALLPHA UNIVERSE</p><h1 className="mt-3 text-xl font-black">Pulihkan password</h1><p className="mt-2 text-sm text-slate-600">Masukkan email akun untuk menerima tautan pemulihan yang aman.</p><label className="mt-6 block text-xs font-bold" htmlFor="recovery-email">Email</label><input id="recovery-email" type="email" autoComplete="email" required value={email} onChange={e=>setEmail(e.target.value)} className="mt-1 w-full rounded-xl border-2 border-slate-900 px-3 py-2 text-sm" /><button disabled={busy} className="mt-5 w-full rounded-xl border-2 border-slate-900 bg-sky-300 px-4 py-3 text-sm font-black disabled:opacity-50">{busy ? "Mengirim…" : "Kirim tautan pemulihan"}</button>{error && <p role="alert" className="mt-4 text-sm text-rose-700">{error}</p>}{message && <p role="status" className="mt-4 text-sm text-emerald-800">{message}</p>}<a href="/login" className="mt-5 block text-center text-sm font-bold underline">Kembali ke Login</a></form></main>;
}

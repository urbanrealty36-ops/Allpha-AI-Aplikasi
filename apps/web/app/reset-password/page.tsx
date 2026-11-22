"use client";

import { FormEvent, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { getBrowserSupabase } from "@/lib/supabase";

export default function ResetPasswordPage() {
  const router = useRouter();
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault(); setError("");
    if (!supabase) { setError("Supabase Auth belum dikonfigurasi."); return; }
    if (password.length < 8) { setError("Password minimal 8 karakter."); return; }
    if (password !== confirmation) { setError("Konfirmasi password tidak sama."); return; }
    setBusy(true);
    try {
      const { data, error: sessionError } = await supabase.auth.getSession();
      if (sessionError || !data.session) throw sessionError ?? new Error("Sesi pemulihan tidak ditemukan atau sudah kedaluwarsa. Minta tautan baru.");
      const { error: updateError } = await supabase.auth.updateUser({ password });
      if (updateError) throw updateError;
      await supabase.auth.signOut({ scope: "local" });
      router.replace("/login?mode=login");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Password tidak dapat diperbarui."); }
    finally { setBusy(false); }
  }

  return <main className="grid min-h-screen place-items-center bg-slate-50 p-6 text-slate-900"><form onSubmit={submit} className="w-full max-w-md rounded-3xl border-2 border-slate-900 bg-white p-7 shadow-[4px_4px_0px_#0f172a]"><p className="text-xs font-black uppercase tracking-widest text-sky-700">ALLPHA UNIVERSE</p><h1 className="mt-3 text-xl font-black">Buat password baru</h1><label className="mt-6 block text-xs font-bold" htmlFor="new-password">Password baru</label><input id="new-password" type="password" autoComplete="new-password" minLength={8} required value={password} onChange={e=>setPassword(e.target.value)} className="mt-1 w-full rounded-xl border-2 border-slate-900 px-3 py-2 text-sm" /><label className="mt-4 block text-xs font-bold" htmlFor="confirm-password">Konfirmasi password</label><input id="confirm-password" type="password" autoComplete="new-password" minLength={8} required value={confirmation} onChange={e=>setConfirmation(e.target.value)} className="mt-1 w-full rounded-xl border-2 border-slate-900 px-3 py-2 text-sm" /><button disabled={busy} className="mt-5 w-full rounded-xl border-2 border-slate-900 bg-sky-300 px-4 py-3 text-sm font-black disabled:opacity-50">{busy ? "Memperbarui…" : "Simpan password baru"}</button>{error && <p role="alert" className="mt-4 text-sm text-rose-700">{error}</p>}<a href="/login" className="mt-5 block text-center text-sm font-bold underline">Kembali ke Login</a></form></main>;
}

"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../../../lib/supabase";

type Passport = {
  id: string;
  handle: string;
  display_name: string;
  description: string;
  avatar_url: string | null;
  disclosure: string;
  visibility: "public";
  status: "active";
  created_at: string;
};
const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function AgentPassportPage() {
  const params = useParams<{ handle: string }>();
  const handle = params.handle;
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [passport, setPassport] = useState<Passport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!supabase) { setLoading(false); return; }
    let active = true;
    void supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      setSession(data.session);
      if (!data.session) { setLoading(false); return; }
      void fetch(apiBase + "/v1/agent-passports/" + encodeURIComponent(handle), {
        headers: { Authorization: "Bearer " + data.session.access_token },
        cache: "no-store",
      }).then(async (response) => {
        if (!response.ok) throw new Error("Passport tidak tersedia atau Agent tidak dipublikasikan.");
        const data = await response.json() as { passport: Passport };
        if (active) setPassport(data.passport);
      }).catch((cause) => {
        if (active) setError(cause instanceof Error ? cause.message : "Passport tidak dapat dimuat.");
      }).finally(() => { if (active) setLoading(false); });
    });
    return () => { active = false; };
  }, [supabase, handle]);

  return <main className="identity-shell">
    <header className="identity-topbar"><a className="brand" href="/"><span className="brand-mark">A</span> ALLPHA</a><a className="button-quiet" href="/agents">Kembali ke Agent Studio</a></header>
    <section className="passport-shell">
      <span className="section-kicker">ALLPHA AGENT PASSPORT</span>
      {loading ? <section className="panel loading-panel">Memverifikasi passport melalui API…</section> :
        !session ? <section className="panel passport-message"><h1>Masuk diperlukan</h1><p>Passport hanya ditampilkan kepada sesi Allpha yang terautentikasi.</p><a className="button-primary" href="/">Masuk ke Allpha</a></section> :
        error || !passport ? <section className="panel passport-message"><h1>Passport tidak tersedia</h1><p role="alert">{error || "Agent tidak ditemukan atau telah ditarik dari publik."}</p><a className="button-primary" href="/agents">Kembali ke Agent Studio</a></section> :
        <article className="panel passport-card">
          <div className="passport-avatar">{passport.avatar_url ? <img src={passport.avatar_url} alt="" /> : <span>{passport.display_name.slice(0, 1).toUpperCase()}</span>}</div>
          <span className="agent-status status-active">PUBLIC · ACTIVE</span>
          <h1>{passport.display_name}</h1><p className="passport-handle">@{passport.handle}</p>
          <p className="passport-description">{passport.description || "Belum ada deskripsi publik."}</p>
          <section className="passport-disclosure"><span className="section-kicker">AI DISCLOSURE</span><p>{passport.disclosure || "Ini adalah AI Agent. Respons dapat dihasilkan oleh model AI."}</p></section>
          <div className="detail-line"><span>Jenis identitas</span><strong>AI Agent, bukan Human</strong></div>
          <div className="detail-line"><span>Status passport</span><strong>Aktif dan publik</strong></div>
          <small className="agent-footnote">Dibuat {new Date(passport.created_at).toLocaleDateString("id-ID")} · Data dari backend Allpha</small>
        </article>}
    </section>
    <footer className="identity-footer"><span>ALLPHA · AGENT PASSPORT</span><span>Disclosure publik · Data API terautentikasi</span></footer>
  </main>;
}

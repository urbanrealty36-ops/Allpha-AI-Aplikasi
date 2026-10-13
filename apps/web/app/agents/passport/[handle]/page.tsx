"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

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
  const [passport, setPassport] = useState<Passport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    void fetch(apiBase + "/v1/agent-passports/" + encodeURIComponent(handle), { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error("Passport tidak tersedia atau Agent tidak dipublikasikan.");
        const data = await response.json() as { passport: Passport };
        if (active) setPassport(data.passport);
      })
      .catch((cause) => {
        if (active) setError(cause instanceof Error ? cause.message : "Passport tidak dapat dimuat.");
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [handle]);

  return <main className="identity-shell">
    <header className="identity-topbar"><a className="brand" href="/"><span className="brand-mark">A</span> ALLPHA</a><a className="button-quiet" href="/agents">Agent Studio ↗</a></header>
    <section className="passport-shell">
      <span className="section-kicker">ALLPHA AGENT PASSPORT</span>
      {loading ? <section className="panel loading-panel">Memuat Passport publik…</section> :
        error || !passport ? <section className="panel passport-message"><h1>Passport tidak tersedia</h1><p role="alert">{error || "Agent tidak ditemukan atau telah ditarik dari publik."}</p><a className="button-primary" href="/agents">Buka Agent Studio</a></section> :
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
    <footer className="identity-footer"><span>ALLPHA · AGENT PASSPORT</span><span>Disclosure publik · Data dari API Allpha</span></footer>
  </main>;
}

"use client";

import { useEffect, useState } from "react";

type ApiStatus = {
  status?: string;
  service?: string;
  version?: string;
  dependencies?: Record<string, string>;
};

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function HomePage() {
  const [apiStatus, setApiStatus] = useState<ApiStatus | null>(null);
  const [state, setState] = useState<"loading" | "connected" | "unavailable">("loading");

  async function checkApi(signal?: AbortSignal) {
    setState("loading");
    try {
      const response = await fetch(`${apiBase}/readyz`, { cache: "no-store", signal });
      if (!response.ok) throw new Error("API unavailable");
      setApiStatus(await response.json());
      setState("connected");
    } catch {
      if (!signal?.aborted) setState("unavailable");
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    void checkApi(controller.signal);
    return () => controller.abort();
  }, []);

  return (
    <main className="shell">
      <header className="topbar">
        <div className="wordmark"><span className="mark">A</span> ALLPHA</div>
        <span className="eyebrow">AI SOCIAL UNIVERSE</span>
      </header>
      <section className="hero">
        <p className="eyebrow">SATU UNIVERSE · MANUSIA & AI AGENT</p>
        <h1>Ruang digital untuk <span>terhubung,</span> berkarya, dan bertumbuh.</h1>
        <p className="intro">Allpha menghubungkan identitas manusia, AI Agent milik pengguna, komunitas, konten, dan pengalaman dalam satu universe.</p>
        <div className="actions">
          <a className="primary" href="#platform-status">Lihat status platform <span aria-hidden="true">↗</span></a>
          <a className="secondary" href="https://github.com/urbanrealty36-ops/Allpha-AI-Aplikasi">Engineering repository</a>
        </div>
      </section>
      <section id="platform-status" className="status-card" aria-live="polite">
        <div className="status-heading">
          <div><p className="eyebrow">FOUNDATION CHECK</p><h2>Status layanan</h2></div>
          <span className={`status-pill ${state}`}>{state === "loading" ? "Memeriksa" : state === "connected" ? "API terhubung" : "API tidak tersedia"}</span>
        </div>
        {state === "connected" && apiStatus ? (
          <>
            <p>Service <strong>{apiStatus.service}</strong> · versi {apiStatus.version}</p>
            <div className="dependency-list">
              {Object.entries(apiStatus.dependencies ?? {}).map(([name, status]) => (
                <div className="dependency" key={name}><span>{name.replaceAll("_", " ")}</span><code>{status}</code></div>
              ))}
            </div>
          </>
        ) : state === "unavailable" ? (
          <div className="empty-state"><p>Backend belum terjangkau dari browser ini.</p><p className="muted">Jalankan API lokal atau atur <code>NEXT_PUBLIC_API_BASE_URL</code>. Status ini bukan data simulasi.</p><button onClick={() => void checkApi()}>Coba lagi</button></div>
        ) : <p className="muted">Mengambil status langsung dari API…</p>}
      </section>
      <footer><span>ALLPHA · PLATFORM FOUNDATION</span><span>Bahasa Indonesia · English-ready</span></footer>
    </main>
  );
}

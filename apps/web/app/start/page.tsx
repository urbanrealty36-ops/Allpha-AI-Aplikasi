"use client";

import { useEffect, useMemo, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../lib/supabase";

const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

type AgentList = { items?: { id: string; status: string }[] };

export default function StartJourneyPage() {
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [status, setStatus] = useState("Memeriksa sesi autentikasi…");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!supabase) {
      setStatus("Autentikasi belum dikonfigurasi.");
      setError("Hubungi administrator aplikasi untuk menyelesaikan konfigurasi login.");
      return;
    }

    let active = true;
    let routed = false;
    const routeSession = async (session: Session | null) => {
      if (!active || routed) return;
      if (!session) {
        routed = true;
        window.location.replace("/");
        return;
      }
      setStatus("Memeriksa identitas AI Agent melalui Allpha API…");
      try {
        const response = await fetch(apiBase + "/v1/agents", {
          headers: { Authorization: "Bearer " + session.access_token, Accept: "application/json" },
          cache: "no-store",
        });
        if (!response.ok) {
          let message = "Status identitas AI Agent tidak dapat diverifikasi.";
          try {
            const body = await response.json();
            message = body?.detail?.message ?? body?.error?.message ?? message;
          } catch {}
          throw new Error(message);
        }
        const payload = await response.json() as AgentList;
        if (!active) return;
        routed = true;
        const hasAgentIdentity = Array.isArray(payload.items) && payload.items.length > 0;
        window.location.replace(hasAgentIdentity ? "/feed" : "/agents?onboarding=required");
      } catch (cause) {
        if (!active) return;
        setError(cause instanceof Error ? cause.message : "Perjalanan onboarding tidak dapat dilanjutkan.");
        setStatus("Onboarding belum dapat diverifikasi.");
      }
    };

    void supabase.auth.getSession().then(({ data, error: sessionError }) => {
      if (sessionError) {
        setError(sessionError.message);
        setStatus("Sesi tidak dapat diverifikasi.");
        return;
      }
      void routeSession(data.session);
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session) void routeSession(session);
    });
    return () => {
      active = false;
      listener.subscription.unsubscribe();
    };
  }, [supabase]);

  return (
    <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 24, background: "#0b1020", color: "#f7f8ff", fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif" }}>
      <section aria-live="polite" style={{ width: "min(100%, 480px)", border: "1px solid rgba(157,174,255,.22)", background: "rgba(22,30,58,.9)", borderRadius: 24, padding: 30, textAlign: "center", boxShadow: "0 24px 80px rgba(0,0,0,.24)" }}>
        <div aria-hidden="true" style={{ width: 58, height: 58, borderRadius: 18, display: "grid", placeItems: "center", margin: "0 auto 18px", background: "#4f46e5", fontWeight: 900, fontSize: 28 }}>A</div>
        <p style={{ letterSpacing: 3, fontSize: 11, color: "#a5b4fc", fontWeight: 800 }}>ALLPHA UNIVERSE</p>
        <h1 style={{ fontSize: 27, margin: "10px 0" }}>Menyiapkan perjalanan Anda</h1>
        <p style={{ color: "#c5cbe0", lineHeight: 1.6 }}>{status}</p>
        {!error && <div role="status" style={{ width: 28, height: 28, border: "3px solid #4b5578", borderTopColor: "#a5b4fc", borderRadius: "50%", margin: "22px auto 0", animation: "spin 1s linear infinite" }} />}
        {error && <div role="alert" style={{ marginTop: 20, color: "#fecaca", lineHeight: 1.6 }}>{error}<p><button type="button" onClick={() => window.location.reload()} style={{ padding: "10px 14px", borderRadius: 10, background: "#4f46e5", color: "white", border: 0, cursor: "pointer" }}>Coba lagi</button> <a href="/" style={{ color: "#c7d2fe" }}>Kembali ke login</a></p></div>}
      </section>
      <style jsx>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </main>
  );
}

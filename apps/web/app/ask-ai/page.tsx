"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../lib/supabase";
import AskAiView from "../../components/reference-ui/AskAiView";
import type { HumanProfile } from "../../lib/reference-store";

type MeResponse = { user?: { id: string; email?: string }; profile?: { username?: string | null; display_name?: string; avatar_url?: string | null; bio?: string } | null };
type Agent = { id: string; handle: string; display_name: string; description: string; status: string };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

export default function AskAiPage() {
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<HumanProfile | null>(null);
  const [agent, setAgent] = useState<Agent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!supabase) { setError("Konfigurasi autentikasi belum tersedia."); setLoading(false); return; }
    let active = true;
    const load = async () => {
      const { data } = await supabase.auth.getSession();
      if (!active) return;
      const current = data.session;
      setSession(current);
      if (!current) { setLoading(false); return; }
      const headers = { Authorization: "Bearer " + current.access_token, Accept: "application/json" };
      try {
        const [meResponse, agentResponse] = await Promise.all([
          fetch(apiBase + "/v1/me", { headers, cache: "no-store" }),
          fetch(apiBase + "/v1/agents", { headers, cache: "no-store" }),
        ]);
        if (!meResponse.ok) throw new Error("Identitas Human belum dapat dimuat dari Allpha API.");
        const me = await meResponse.json() as MeResponse;
        if (!me.user) throw new Error("Identitas Human kanonis tidak tersedia.");
        const name = me.profile?.display_name?.trim() || me.user.email || "Pengguna";
        setUser({ id: me.user.id, name, username: me.profile?.username || me.user.email || "", avatar: me.profile?.avatar_url || "/icon.svg", bio: me.profile?.bio || "", followers: 0, following: 0, postsCount: 0, badge: "Human" });
        if (agentResponse.ok) {
          const payload = await agentResponse.json() as { items?: Agent[] };
          setAgent((payload.items || []).find(item => item.status === "active") || null);
        } else {
          setError("Katalog AI Agent belum tersedia dari Allpha API.");
        }
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : "Identitas tidak dapat dimuat.");
      } finally { if (active) setLoading(false); }
    };
    void load();
    const { data: listener } = supabase.auth.onAuthStateChange((_event, next) => { if (active) setSession(next); });
    return () => { active = false; listener.subscription.unsubscribe(); };
  }, [supabase]);

  if (!session) return <main className="mx-auto max-w-xl p-6"><h1 className="text-xl font-bold">Tanya AI Agent</h1><p className="mt-3 text-sm text-slate-600">Masuk ke Allpha untuk memuat identitas dan AI Agent kanonis.</p><Link className="mt-4 inline-flex rounded-xl bg-blue-600 px-4 py-2 text-white" href="/login">Masuk</Link></main>;
  if (loading || !user) return <main className="mx-auto max-w-xl p-6 text-sm text-slate-600" role="status">{error || "Memuat identitas Allpha…"}</main>;
  return <>
    {error && <p role="status" className="mx-auto max-w-xl px-4 pt-3 text-xs text-amber-800">{error}</p>}
    <AskAiView onBack={() => { window.location.assign("/feed"); }} agentName={agent?.display_name || "Pilih AI Agent"} humanOwner={user.name} specialty={agent?.description || "AI Agent Allpha"} currentUser={user} availabilityMessage={agent ? "Agent Runtime chat belum memiliki adapter percakapan kanonis. Pertanyaan belum dikirim dan tidak ada kredit yang dipotong." : "Belum ada AI Agent aktif untuk akun ini. Tidak ada pertanyaan yang dikirim atau kredit yang dipotong."} />
  </>;
}

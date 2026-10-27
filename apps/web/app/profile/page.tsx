"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../lib/supabase";
import ProfileView from "../../components/reference-ui/ProfileView";
import type { AIAgentProfile, HumanProfile } from "../../lib/reference-store";
type Me = { user?: { id: string; email?: string }; profile?: { username?: string | null; display_name?: string; avatar_url?: string | null; bio?: string } | null };
type ApiAgent = { id: string; handle: string; display_name: string; description: string; avatar_url?: string | null; persona?: Record<string, unknown>; status: string; ownership?: { owner_user_id: string; status: string } };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");
export default function ProfilePage() {
 const supabase = useMemo(() => getBrowserSupabase(), []); const [session,setSession] = useState<Session|null>(null); const [human,setHuman] = useState<HumanProfile|null>(null); const [agents,setAgents] = useState<ApiAgent[]>([]); const [selectedAgent,setSelectedAgent] = useState<AIAgentProfile|null>(null); const [selectedAgentStatus,setSelectedAgentStatus] = useState(""); const [loading,setLoading] = useState(true); const [error,setError] = useState(""); const [openStoreAndBooth,setOpenStoreAndBooth] = useState(false);
 useEffect(()=>{ if (typeof window !== "undefined" && new URLSearchParams(window.location.search).get("open") === "store") setOpenStoreAndBooth(true); },[]);
 useEffect(() => {
  if (!supabase) {
    setError("Konfigurasi autentikasi belum tersedia.");
    setLoading(false);
    return;
  }
  let active = true;
  let requestSequence = 0;

  const loadProfile = async (current: Session | null) => {
    const sequence = ++requestSequence;
    setSession(current);
    setError("");
    if (!current) {
      setHuman(null);
      setAgents([]);
      setSelectedAgent(null);
      setSelectedAgentStatus("");
      setLoading(false);
      return;
    }

    setLoading(true);
    const headers = { Authorization: "Bearer " + current.access_token, Accept: "application/json" };
    try {
      const [meResponse, agentsResponse] = await Promise.all([
        fetch(apiBase + "/v1/me", { headers, cache: "no-store" }),
        fetch(apiBase + "/v1/agents", { headers, cache: "no-store" }),
      ]);
      if (!meResponse.ok) throw new Error("Identitas Human belum dapat dimuat dari Allpha API.");
      const me = await meResponse.json() as Me;
      if (!me.user || me.user.id !== current.user.id) throw new Error("Identitas Human kanonis tidak cocok dengan sesi aktif.");
      const displayName = me.profile?.display_name?.trim() || me.user.email || "Pengguna";
      const nextHuman: HumanProfile = {
        id: me.user.id,
        name: displayName,
        username: me.profile?.username || "",
        avatar: me.profile?.avatar_url || "/icon.svg",
        bio: me.profile?.bio || "",
        followers: 0,
        following: 0,
        postsCount: 0,
        badge: "Human",
      };

      if (!agentsResponse.ok) throw new Error("Daftar Agent belum tersedia dari Allpha API.");
      const payload = await agentsResponse.json() as { items?: ApiAgent[] };
      const owned = (payload.items || []).filter(item =>
        item.ownership?.owner_user_id === me.user!.id && item.ownership.status === "active"
      );
      const activeAgent = owned.find(item => item.status === "active") || null;
      const nextAgent: AIAgentProfile | null = activeAgent ? {
        id: activeAgent.id,
        name: activeAgent.display_name,
        handle: activeAgent.handle,
        avatar: activeAgent.avatar_url || "/icon.svg",
        ownerId: me.user.id,
        ownerName: displayName,
        ownerHandle: me.profile?.username || "",
        specialty: activeAgent.description || "Belum ditentukan",
        category: typeof activeAgent.persona?.category === "string" ? activeAgent.persona.category : "Belum ditentukan",
        bio: activeAgent.description || "",
        skills: [],
        creditsEarned: 0,
        autoReply: false,
        model: "Allpha AI Runtime",
        goals: [],
        tasks: [],
      } : null;

      if (!active || sequence !== requestSequence) return;
      setHuman(nextHuman);
      setAgents(owned);
      setSelectedAgentStatus(activeAgent?.status || "");
      setSelectedAgent(nextAgent);
    } catch (cause) {
      if (active && sequence === requestSequence) {
        setHuman(null);
        setAgents([]);
        setSelectedAgent(null);
        setSelectedAgentStatus("");
        setError(cause instanceof Error ? cause.message : "Profil tidak dapat dimuat.");
      }
    } finally {
      if (active && sequence === requestSequence) setLoading(false);
    }
  };

  void supabase.auth.getSession().then(({ data }) => {
    if (active) void loadProfile(data.session);
  });
  const { data: listener } = supabase.auth.onAuthStateChange((_event, next) => {
    if (active) void loadProfile(next);
  });
  return () => {
    active = false;
    requestSequence += 1;
    listener.subscription.unsubscribe();
  };
 }, [supabase]);
 if(!session)return <main className="mx-auto max-w-xl p-6"><h1 className="text-xl font-bold">Profil Allpha</h1><p className="mt-3 text-sm text-slate-600">Masuk untuk memuat profil kanonis Anda.</p><Link className="mt-4 inline-flex rounded-xl bg-blue-600 px-4 py-2 text-white" href="/login">Masuk</Link></main>;
 if(loading||!human)return <main className="mx-auto max-w-xl p-6 text-sm text-slate-600" role="status">{error||"Memuat profil Allpha…"}</main>;
 return <>{error&&<p role="alert" className="mx-auto max-w-xl px-4 pt-3 text-xs text-amber-800">{error}</p>}<ProfileView humanUser={human} agentProfile={selectedAgent} ownedAgents={agents.map(a=>({name:a.display_name,handle:a.handle,specialty:a.description||"Belum ditentukan",avatar:a.avatar_url||"/icon.svg",status:a.status}))} knowledgeDocs={[]} posts={[]} isTakeoverActive={false} showCredits={false} showSocialCounts={false} humanVerified={false} agentStatusLabel={selectedAgentStatus||"Belum ada Agent aktif"} onOpenTakeoverModal={()=>{window.location.assign("/agents")}} onOpenCreditsHub={()=>{window.location.assign("/skill-challenges")}} onOpenWorld3D={()=>{window.location.assign("/spatial/navigation")}} onOpenOnboarding={()=>{window.location.assign("/account")}} onOpenAccountSettings={()=>{window.location.assign("/account")}} initialOpenStoreAndBooth={openStoreAndBooth} /></>;
}

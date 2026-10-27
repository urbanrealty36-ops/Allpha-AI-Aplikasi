"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../lib/supabase";
import ProfileView from "../../components/reference-ui/ProfileView";
import type { AIAgentProfile, HumanProfile, PostItem } from "../../lib/reference-store";
type Me = { user?: { id: string; email?: string }; profile?: { username?: string | null; display_name?: string; avatar_url?: string | null; bio?: string } | null };
type ApiAgent = { id: string; handle: string; display_name: string; description: string; avatar_url?: string | null; persona?: Record<string, unknown>; status: string; ownership?: { owner_user_id: string; status: string } };
type ApiFeedItem = { id: string; owner_id: string; body: string; created_at: string; published_at?: string | null; creator?: { username?: string | null; display_name?: string | null; avatar_url?: string | null }; media?: { id: string; media_type: string; preview_url?: string | null }[]; engagement?: { likes: number; comments: number; shares?: number }; viewer_reaction?: string | null; saved?: boolean };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");
export default function ProfilePage() {
 const supabase = useMemo(() => getBrowserSupabase(), []); const [session,setSession] = useState<Session|null>(null); const [human,setHuman] = useState<HumanProfile|null>(null); const [agents,setAgents] = useState<ApiAgent[]>([]); const [posts,setPosts] = useState<PostItem[]>([]); const [selectedAgent,setSelectedAgent] = useState<AIAgentProfile|null>(null); const [selectedAgentStatus,setSelectedAgentStatus] = useState(""); const [loading,setLoading] = useState(true); const [error,setError] = useState(""); const [openStoreAndBooth,setOpenStoreAndBooth] = useState(false);
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
      setPosts([]);
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
      let profilePosts: PostItem[] = [];
      try {
        const feedResponse = await fetch(apiBase + "/v1/me/profile-feed?limit=50", { headers, cache: "no-store" });
        if (feedResponse.ok) {
          const feedPayload = await feedResponse.json() as { items?: ApiFeedItem[] };
          profilePosts = (feedPayload.items || []).filter(item => item.owner_id === me.user!.id).map(item => {
            const image = item.media?.find(media => media.media_type.startsWith("image/") && media.preview_url)?.preview_url;
            return {
              id: item.id,
              humanOwner: { name: me.profile?.display_name || me.profile?.username || "Pengguna", handle: me.profile?.username || "", avatar: me.profile?.avatar_url || "/icon.svg", verified: false },
              aiAgent: { name: "—", handle: "", avatar: "", specialty: "Belum tersedia" },
              takeoverMode: false,
              timestamp: new Date(item.published_at || item.created_at).toLocaleString("id-ID"),
              content: item.body,
              tags: [],
              ...(image ? { image } : {}),
              likes: item.engagement?.likes ?? 0,
              commentsCount: item.engagement?.comments ?? 0,
              reposts: item.engagement?.shares ?? 0,
              isLiked: Boolean(item.viewer_reaction),
              isBookmarked: Boolean(item.saved),
              comments: [],
            };
          });
        }
      } catch {
        // Profile identity remains usable if the optional feed read is temporarily unavailable.
      }
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
      setPosts(profilePosts);
      setSelectedAgentStatus(activeAgent?.status || "");
      setSelectedAgent(nextAgent);
    } catch (cause) {
      if (active && sequence === requestSequence) {
        setHuman(null);
        setAgents([]);
        setPosts([]);
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
 if(loading)return <main className="mx-auto max-w-xl p-6 text-sm text-slate-600" role="status">{error||"Memuat profil Allpha…"}</main>;
 if(!session)return <main className="mx-auto max-w-xl p-6"><h1 className="text-xl font-bold">Profil Allpha</h1><p className="mt-3 text-sm text-slate-600">{error||"Masuk untuk memuat profil kanonis Anda."}</p><Link className="mt-4 inline-flex rounded-xl bg-blue-600 px-4 py-2 text-white" href="/login">Masuk</Link></main>;
 if(!human)return <main className="mx-auto max-w-xl p-6 text-sm text-slate-600" role="alert">{error||"Profil kanonis belum tersedia."}</main>;
 async function toggleProfileLike(postId: string) {
  if (!session) { setError("Masuk kembali untuk menyukai postingan."); return; }
  const post = posts.find(item => item.id === postId);
  if (!post) return;
  try {
   const response = await fetch(apiBase + "/v1/feed/" + encodeURIComponent(postId) + "/reaction", {
    method: post.isLiked ? "DELETE" : "PUT",
    headers: { Authorization: "Bearer " + session.access_token, Accept: "application/json", ...(post.isLiked ? {} : { "Content-Type": "application/json" }) },
    ...(post.isLiked ? {} : { body: JSON.stringify({ reaction: "like" }) }),
   });
   if (!response.ok) throw new Error("Reaksi tidak dapat disimpan oleh Allpha API.");
   setPosts(current => current.map(item => item.id === postId ? { ...item, isLiked: !post.isLiked, likes: Math.max(0, item.likes + (post.isLiked ? -1 : 1)) } : item));
   setError("");
  } catch (cause) { setError(cause instanceof Error ? cause.message : "Reaksi gagal disimpan."); }
 }
 return <>{error&&<p role="alert" className="mx-auto max-w-xl px-4 pt-3 text-xs text-amber-800">{error}</p>}<ProfileView humanUser={human} agentProfile={selectedAgent} ownedAgents={agents.map(a=>({name:a.display_name,handle:a.handle,specialty:a.description||"Belum ditentukan",avatar:a.avatar_url||"/icon.svg",status:a.status}))} knowledgeDocs={[]} posts={posts} isTakeoverActive={false} onLikePost={toggleProfileLike} onSelectPost={(post)=>{window.location.assign("/feed?content="+encodeURIComponent(post.id))}} showCredits={false} showSocialCounts={false} humanVerified={false} agentStatusLabel={selectedAgentStatus||"Belum ada Agent aktif"} onOpenTakeoverModal={()=>{window.location.assign("/agents")}} onOpenCreditsHub={()=>{window.location.assign("/skill-challenges")}} onOpenWorld3D={()=>{window.location.assign("/spatial/navigation")}} onOpenOnboarding={()=>{window.location.assign("/account")}} onOpenAccountSettings={(tab = "settings")=>{window.location.assign("/account?tab="+encodeURIComponent(tab))}} initialOpenStoreAndBooth={openStoreAndBooth} onRevokeOtherSessions={async()=>{if(!supabase) throw new Error("Autentikasi belum tersedia."); const {error}=await supabase.auth.signOut({scope:"others"}); if(error) throw error;}} onLogout={async()=>{if(!supabase) throw new Error("Autentikasi belum tersedia."); const {error}=await supabase.auth.signOut(); if(error) throw error; window.location.assign("/login");}} /></>;
}

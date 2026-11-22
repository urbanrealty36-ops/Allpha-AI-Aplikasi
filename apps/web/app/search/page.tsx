"use client";

import { FormEvent, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../lib/supabase";
import ExploreView, { type SocialAccountItem } from "../../components/reference-ui/ExploreView";
import type { PostItem } from "../../lib/reference-store";
type SearchItem = { id: string; body: string; content_type: string; owner_id: string; ai_agent_id?: string | null; agent?: { id: string; handle: string; display_name: string; avatar_url?: string | null; description?: string | null } | null; published_at?: string | null; created_at: string; creator?: { username?: string | null; display_name?: string | null; avatar_url?: string | null }; engagement?: { likes: number; comments: number; saves: number; shares: number }; viewer_reaction?: string | null; saved?: boolean };
type Trend = { topic: string; content_count: number; example_content_id: string };
type Recommendation = SearchItem;
type Creator = { id: string; username?: string | null; display_name: string; avatar_url?: string | null; bio?: string; public_post_count: number; is_ai: boolean };
type DiscoveredUser = { id: string; username: string; display_name: string; avatar_url?: string | null; bio?: string; visibility: "public" | "private"; is_ai: false };
type Payload<T> = { items: T[]; query?: string; count?: number; has_more?: boolean; error?: { message?: string } };
type SocialGraphEdge = { id: string; target_user_id: string; actor_user_id: string; target_node_type: "human" | "agent"; target_agent_id?: string | null; actor_node_type: "human" | "agent"; actor_agent_id?: string | null; edge_type: "follow" | "block" | "mute"; status: "requested" | "active" };
type SocialGraphPayload = { outgoing?: SocialGraphEdge[]; incoming?: SocialGraphEdge[] };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

function SearchPageContent() {
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const searchParams = useSearchParams();
  const [session, setSession] = useState<Session | null>(null);
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<SearchItem[]>([]);
  const [trends, setTrends] = useState<Trend[]>([]);
  const [trendsBusy, setTrendsBusy] = useState(false);
  const [trendsError, setTrendsError] = useState("");
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [recommendationsBusy, setRecommendationsBusy] = useState(false);
  const [recommendationsError, setRecommendationsError] = useState("");
  const [creators, setCreators] = useState<Creator[]>([]);
  const [creatorsBusy, setCreatorsBusy] = useState(false);
  const [creatorsError, setCreatorsError] = useState("");
  const [discoveredUsers, setDiscoveredUsers] = useState<DiscoveredUser[]>([]);
  const [discoveryError, setDiscoveryError] = useState("");
  const [followedAccountIds, setFollowedAccountIds] = useState<string[]>([]);
  const [pendingFollowAccountIds, setPendingFollowAccountIds] = useState<string[]>([]);
  const [followEdgeIds, setFollowEdgeIds] = useState<Record<string, string>>({});
  const [blockedAccountIds, setBlockedAccountIds] = useState<string[]>([]);
  const [mutedAccountIds, setMutedAccountIds] = useState<string[]>([]);
  const [blockEdgeIds, setBlockEdgeIds] = useState<Record<string, string>>({});
  const [muteEdgeIds, setMuteEdgeIds] = useState<Record<string, string>>({});
  const [incomingFollowRequests, setIncomingFollowRequests] = useState<SocialGraphEdge[]>([]);
  const [ownedAgents, setOwnedAgents] = useState<Array<{ id: string; handle: string; display_name: string; status: string; ownership_role: "owner" | "operator" }>>([]);
  const [actorAgentId, setActorAgentId] = useState("");
  const [socialGraphError, setSocialGraphError] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [searched, setSearched] = useState(false);
  const [authPrompt, setAuthPrompt] = useState("");
  const lastUrlQuery = useRef<string | null>(null);
  const lastSessionUserId = useRef<string | null>(null);
  const sessionEpoch = useRef(0);
  const searchRequestSequence = useRef(0);
  const trendsRequestSequence = useRef(0);
  const recommendationsRequestSequence = useRef(0);
  const creatorsRequestSequence = useRef(0);
  const socialGraphRequestSequence = useRef(0);
  const discoveryRequestSequence = useRef(0);

  useEffect(() => {
    if (!supabase) return;
    let active = true;
    let authEventSeen = false;
    void supabase.auth.getSession().then(({ data }) => {
      if (active && !authEventSeen) setSession(data.session);
    });
    const { data } = supabase.auth.onAuthStateChange((_event, next) => {
      if (!active) return;
      authEventSeen = true;
      setSession(next);
    });
    return () => {
      active = false;
      sessionEpoch.current += 1;
      searchRequestSequence.current += 1;
      trendsRequestSequence.current += 1;
      recommendationsRequestSequence.current += 1;
      creatorsRequestSequence.current += 1;
      socialGraphRequestSequence.current += 1;
      discoveryRequestSequence.current += 1;
      data.subscription.unsubscribe();
    };
  }, [supabase]);

  useEffect(() => {
    const nextUserId = session?.user.id ?? null;
    if (lastSessionUserId.current === nextUserId) return;
    lastSessionUserId.current = nextUserId;
    sessionEpoch.current += 1;
    searchRequestSequence.current += 1;
    trendsRequestSequence.current += 1;
    recommendationsRequestSequence.current += 1;
    creatorsRequestSequence.current += 1;
    socialGraphRequestSequence.current += 1;
    discoveryRequestSequence.current += 1;
    lastUrlQuery.current = null;
    setQuery("");
    setItems([]);
    setTrends([]);
    setRecommendations([]);
    setCreators([]);
    setDiscoveredUsers([]);
    setDiscoveryError("");
    setFollowedAccountIds([]);
    setPendingFollowAccountIds([]);
    setSocialGraphError("");
    setBusy(false);
    setTrendsBusy(false);
    setRecommendationsBusy(false);
    setCreatorsBusy(false);
    setError("");
    setTrendsError("");
    setRecommendationsError("");
    setCreatorsError("");
    setSearched(false);
    setAuthPrompt("");
  }, [session?.user.id]);

  async function loadTrends() {
    const sequence = ++trendsRequestSequence.current;
    setTrendsBusy(true); setTrendsError("");
    try {
      const response = await fetch(apiBase + "/v1/trends?limit=10", { headers: session ? { Authorization: "Bearer " + session.access_token } : {}, cache: "no-store" });
      const payload = await response.json() as Payload<Trend>;
      if (sequence !== trendsRequestSequence.current) return;
      if (!response.ok) throw new Error(payload.error?.message || "Tren belum dapat dimuat.");
      setTrends(payload.items || []);
    } catch (cause) {
      if (sequence === trendsRequestSequence.current) setTrendsError(cause instanceof Error ? cause.message : "Tren belum dapat dimuat.");
    } finally { if (sequence === trendsRequestSequence.current) setTrendsBusy(false); }
  }

  async function loadRecommendations() {
    const sequence = ++recommendationsRequestSequence.current;
    setRecommendationsBusy(true); setRecommendationsError("");
    try {
      const response = await fetch(apiBase + "/v1/recommendations?limit=10", { headers: session ? { Authorization: "Bearer " + session.access_token } : {}, cache: "no-store" });
      const payload = await response.json() as Payload<Recommendation>;
      if (sequence !== recommendationsRequestSequence.current) return;
      if (!response.ok) throw new Error(payload.error?.message || "Rekomendasi belum dapat dimuat.");
      setRecommendations(payload.items || []);
    } catch (cause) {
      if (sequence === recommendationsRequestSequence.current) setRecommendationsError(cause instanceof Error ? cause.message : "Rekomendasi belum dapat dimuat.");
    } finally { if (sequence === recommendationsRequestSequence.current) setRecommendationsBusy(false); }
  }

  async function loadOwnedAgents() {
    if (!session) { setOwnedAgents([]); return; }
    try {
      const response = await fetch(apiBase + "/v1/social/actor-agents", { headers: { Authorization: "Bearer " + session.access_token }, cache: "no-store" });
      const payload = await response.json() as { items?: Array<{ id: string; handle: string; display_name: string; status: string }> };
      if (response.ok) setOwnedAgents(payload.items || []);
    } catch { setOwnedAgents([]); }
  }

  async function loadCreators() {
    const sequence = ++creatorsRequestSequence.current;
    setCreatorsBusy(true); setCreatorsError("");
    try {
      const response = await fetch(apiBase + "/v1/recommendations/creators?limit=20", {
        headers: session ? { Authorization: "Bearer " + session.access_token } : {}, cache: "no-store",
      });
      const payload = await response.json() as Payload<Creator>;
      if (sequence !== creatorsRequestSequence.current) return;
      if (!response.ok) throw new Error(payload.error?.message || "Rekomendasi akun belum dapat dimuat.");
      setCreators(payload.items || []);
    } catch (cause) {
      if (sequence === creatorsRequestSequence.current) {
        setCreatorsError(cause instanceof Error ? cause.message : "Rekomendasi akun belum dapat dimuat.");
        setCreators([]);
      }
    } finally { if (sequence === creatorsRequestSequence.current) setCreatorsBusy(false); }
  }

  async function loadSocialGraph() {
    if (!session) {
      socialGraphRequestSequence.current += 1;
      setFollowedAccountIds([]);
      setPendingFollowAccountIds([]);
      setFollowEdgeIds({});
      setBlockedAccountIds([]);
      setMutedAccountIds([]);
      setBlockEdgeIds({});
      setMuteEdgeIds({});
      setIncomingFollowRequests([]);
      setSocialGraphError("");
      return;
    }
    const sequence = ++socialGraphRequestSequence.current;
    setSocialGraphError("");
    try {
      const graphUrl = apiBase + "/v1/social/relationships" + (actorAgentId ? "?actor_agent_id=" + encodeURIComponent(actorAgentId) : "");
      const response = await fetch(graphUrl, {
        headers: { Authorization: "Bearer " + session.access_token },
        cache: "no-store",
      });
      const payload = await response.json() as SocialGraphPayload & { error?: { message?: string } };
      if (sequence !== socialGraphRequestSequence.current) return;
      if (!response.ok) throw new Error(payload.error?.message || "Status relasi sosial belum dapat dimuat.");
      const relationships = (payload.outgoing || []).filter(edge => edge.actor_node_type === (actorAgentId ? "agent" : "human"));
      const keyFor = (edge: SocialGraphEdge) => edge.target_node_type === "agent" ? String(edge.target_agent_id || "") : edge.target_user_id;
      const follows = relationships.filter(edge => edge.edge_type === "follow");
      const blocks = relationships.filter(edge => edge.edge_type === "block" && edge.status === "active");
      const mutes = relationships.filter(edge => edge.edge_type === "mute" && edge.status === "active");
      setFollowedAccountIds(follows.filter(edge => edge.status === "active").map(keyFor));
      setPendingFollowAccountIds(follows.filter(edge => edge.status === "requested").map(keyFor));
      setFollowEdgeIds(Object.fromEntries(follows.map(edge => [keyFor(edge), edge.id])));
      setBlockedAccountIds(blocks.map(keyFor));
      setMutedAccountIds(mutes.map(keyFor));
      setBlockEdgeIds(Object.fromEntries(blocks.map(edge => [keyFor(edge), edge.id])));
      setMuteEdgeIds(Object.fromEntries(mutes.map(edge => [keyFor(edge), edge.id])));
      setIncomingFollowRequests((payload.incoming || []).filter(edge => edge.edge_type === "follow" && edge.status === "requested"));
    } catch (cause) {
      if (sequence === socialGraphRequestSequence.current) {
        setFollowedAccountIds([]);
        setPendingFollowAccountIds([]);
        setFollowEdgeIds({});
        setBlockedAccountIds([]);
        setMutedAccountIds([]);
        setBlockEdgeIds({});
        setMuteEdgeIds({});
        setIncomingFollowRequests([]);
        setSocialGraphError(cause instanceof Error ? cause.message : "Status relasi sosial belum dapat dimuat.");
      }
    }
  }

  const loadDiscoveredUsers = useCallback(async (value: string) => {
    const normalized = value.trim().replace(/^@/, "");
    const sequence = ++discoveryRequestSequence.current;
    if (!session || !/^[a-zA-Z0-9_]{3,30}$/.test(normalized)) {
      setDiscoveredUsers([]);
      setDiscoveryError("");
      return;
    }
    setDiscoveryError("");
    try {
      const response = await fetch(apiBase + "/v1/social/discover-users?q=" + encodeURIComponent(normalized) + "&limit=20", {
        headers: { Authorization: "Bearer " + session.access_token },
        cache: "no-store",
      });
      const payload = await response.json() as Payload<DiscoveredUser>;
      if (sequence !== discoveryRequestSequence.current) return;
      if (!response.ok) throw new Error(payload.error?.message || "Pencarian username belum dapat dimuat.");
      setDiscoveredUsers(payload.items || []);
    } catch (cause) {
      if (sequence === discoveryRequestSequence.current) {
        setDiscoveredUsers([]);
        setDiscoveryError(cause instanceof Error ? cause.message : "Pencarian username belum dapat dimuat.");
      }
    }
  }, [session]);

  useEffect(() => {
    void loadTrends();
    void loadRecommendations();
    void loadCreators();
    void loadOwnedAgents();
    void loadSocialGraph();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.access_token]);

  const runSearch = useCallback(async (event?: FormEvent, value = query) => {
    event?.preventDefault();
    const sequence = ++searchRequestSequence.current;
    if (value.trim().length < 2) {
      setItems([]);
      setBusy(false);
      setSearched(false);
      setError("Masukkan minimal 2 karakter.");
      return;
    }
    setBusy(true); setError(""); setSearched(true);
    void loadDiscoveredUsers(value.trim());
    try {
      const response = await fetch(apiBase + "/v1/search?q=" + encodeURIComponent(value.trim()) + "&limit=30", {
        headers: session ? { Authorization: "Bearer " + session.access_token } : {}, cache: "no-store",
      });
      const payload = await response.json() as Payload<SearchItem>;
      if (sequence !== searchRequestSequence.current) return;
      if (!response.ok) throw new Error(payload.error?.message || "Pencarian gagal.");
      setItems(payload.items || []);
    } catch (cause) {
      if (sequence === searchRequestSequence.current) {
        setError(cause instanceof Error ? cause.message : "Pencarian gagal.");
        setItems([]);
      }
    } finally { if (sequence === searchRequestSequence.current) setBusy(false); }
  }, [query, session, loadDiscoveredUsers]);

  useEffect(() => { void loadSocialGraph(); }, [actorAgentId]);

  async function resolveIncomingFollow(edgeId: string, accept: boolean) {
    if (!session) return;
    try {
      const response = await fetch(apiBase + "/v1/social/relationships/" + encodeURIComponent(edgeId) + (accept ? "/accept" : "/reject"), {
        method: "POST",
        headers: { Authorization: "Bearer " + session.access_token, Accept: "application/json" },
        cache: "no-store",
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload?.error?.message || payload?.detail?.message || "Permintaan mengikuti tidak dapat diproses.");
      setSocialGraphError("");
      await loadSocialGraph();
      if (accept) void loadCreators();
    } catch (cause) {
      setSocialGraphError(cause instanceof Error ? cause.message : "Permintaan mengikuti tidak dapat diproses.");
    }
  }

  async function mutateSocialRelationship(accountId: string, edgeType: "block" | "mute", currentlyActive: boolean) {
    if (!session) { setAuthPrompt("Masuk untuk mengubah pengaturan relasi."); return; }
    const targetType = creators.some(item => item.id === accountId && item.is_ai) ? "agent" : "human";
    const edgeMap = edgeType === "block" ? blockEdgeIds : muteEdgeIds;
    const edgeId = edgeMap[accountId];
    try {
      const response = await fetch(
        currentlyActive && edgeId ? apiBase + "/v1/social/relationships/" + encodeURIComponent(edgeId) : apiBase + "/v1/social/relationships",
        {
          method: currentlyActive ? "DELETE" : "POST",
          headers: {
            Authorization: "Bearer " + session.access_token,
            Accept: "application/json",
            ...(currentlyActive ? {} : { "Content-Type": "application/json" }),
          },
          ...(currentlyActive ? {} : { body: JSON.stringify({ target_type: targetType, target_id: accountId, edge_type: edgeType, ...(actorAgentId ? { actor_agent_id: actorAgentId } : {}) }) }),
          cache: "no-store",
        },
      );
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload?.error?.message || payload?.detail?.message || "Pengaturan relasi tidak dapat diubah.");
      if (edgeType === "block") {
        setBlockedAccountIds(previous => currentlyActive ? previous.filter(id => id !== accountId) : [...new Set([...previous, accountId])]);
        setBlockEdgeIds(previous => { const next = { ...previous }; if (currentlyActive) delete next[accountId]; else if (payload?.edge?.id) next[accountId] = payload.edge.id; return next; });
      } else {
        setMutedAccountIds(previous => currentlyActive ? previous.filter(id => id !== accountId) : [...new Set([...previous, accountId])]);
        setMuteEdgeIds(previous => { const next = { ...previous }; if (currentlyActive) delete next[accountId]; else if (payload?.edge?.id) next[accountId] = payload.edge.id; return next; });
      }
      setSocialGraphError("");
      void loadCreators();
      void loadSocialGraph();
    } catch (cause) {
      setSocialGraphError(cause instanceof Error ? cause.message : "Pengaturan relasi tidak dapat diubah.");
    }
  }

  const urlQuery = searchParams.get("q")?.trim().slice(0, 100) ?? "";

  useEffect(() => {
    if (!urlQuery || urlQuery.length < 2) {
      lastUrlQuery.current = null;
      return;
    }
    if (lastUrlQuery.current === urlQuery) return;
    lastUrlQuery.current = urlQuery;
    setQuery(urlQuery);
    void runSearch(undefined, urlQuery);
  }, [session, urlQuery, runSearch]);

  const accountsForReference: SocialAccountItem[] = creators.map(item => ({
    id: item.id,
    name: item.display_name || item.username || "Kreator",
    handle: item.username || "",
    avatar: item.avatar_url || "/icon.svg",
    isAi: item.is_ai,
    specialty: "Kreator publik",
    bio: item.bio || "",
    publicPostCount: item.public_post_count,
    tags: [],
  }));

  const discoveredAccountsForReference: SocialAccountItem[] = discoveredUsers.map(item => ({
    id: item.id,
    name: item.display_name || item.username,
    handle: item.username,
    avatar: item.avatar_url || "/icon.svg",
    isAi: false,
    specialty: item.visibility === "private" ? "Akun privat" : "Akun yang dapat ditemukan",
    bio: item.bio || "",
    tags: [],
  }));
  const combinedAccountsForReference = [
    ...accountsForReference,
    ...discoveredAccountsForReference,
  ].filter((item, index, all) => all.findIndex(candidate => candidate.id === item.id) === index);

  const postsForReference: PostItem[] = items.map(item => ({
    id: item.id,
    humanOwner: { name: item.creator?.display_name || item.creator?.username || "Kreator", handle: item.creator?.username || "", avatar: item.creator?.avatar_url || "", verified: false },
    aiAgent: item.agent ? { name: item.agent.display_name || item.agent.handle, handle: item.agent.handle, avatar: item.agent.avatar_url || "", specialty: item.agent.description || "AI Agent" } : { name: "—", handle: "", avatar: "", specialty: "Belum tersedia" },
    takeoverMode: false,
    timestamp: new Date(item.published_at ?? item.created_at).toLocaleString("id-ID"),
    content: item.body,
    tags: [],
    likes: item.engagement?.likes ?? 0,
    commentsCount: item.engagement?.comments ?? 0,
    reposts: item.engagement?.shares ?? 0,
    isLiked: Boolean(item.viewer_reaction),
    isBookmarked: Boolean(item.saved),
    comments: [],
  }));

  const recommendationsForReference: PostItem[] = recommendations.map(item => ({
    id: item.id,
    humanOwner: { name: "Kreator", handle: "", avatar: "", verified: false },
    aiAgent: { name: "—", handle: "", avatar: "", specialty: "Belum tersedia" },
    takeoverMode: false,
    timestamp: new Date(item.published_at ?? item.created_at).toLocaleString("id-ID"),
    content: item.body,
    tags: [],
    likes: item.engagement?.likes ?? 0,
    commentsCount: item.engagement?.comments ?? 0,
    reposts: item.engagement?.shares ?? 0,
    isLiked: Boolean(item.viewer_reaction),
    isBookmarked: Boolean(item.saved),
    comments: [],
  }));

  return <>
    {session && <section className="mx-auto mt-3 max-w-xl rounded-2xl border-2 border-slate-900 bg-white p-3 shadow-[3px_3px_0px_#0f172a]">
      <label htmlFor="social-actor-agent" className="block text-xs font-black text-slate-950">Identitas yang melakukan follow</label>
      <select id="social-actor-agent" value={actorAgentId} onChange={event => setActorAgentId(event.target.value)} className="mt-2 w-full rounded-xl border-2 border-slate-900 bg-white p-2 text-sm font-bold">
        <option value="">Human · akun saya</option>
        {ownedAgents.filter(agent => agent.status === "active").map(agent => <option key={agent.id} value={agent.id}>AI Agent · @{agent.handle}</option>)}
      </select>
      <p className="mt-1 text-[11px] text-slate-600">{actorAgentId ? "Tindakan Agent tetap menggunakan otorisasi dan audit pemilik." : "Anda mengikuti Human atau Agent sebagai identitas Human."}</p>
    </section>}
    {!session && <section className="mx-auto mt-3 max-w-xl rounded-2xl border-2 border-slate-900 bg-white p-4 shadow-[3px_3px_0px_#0f172a]"><p className="text-xs font-black text-slate-950">{authPrompt || "Jelajahi konten publik. Masuk untuk personalisasi dan interaksi."}</p><div className="mt-2 flex gap-2"><a href={"/login?next=" + encodeURIComponent("/search")} className="rounded-xl border-2 border-slate-900 bg-sky-300 px-3 py-2 text-xs font-black text-slate-950">Masuk</a><a href={"/login?next=" + encodeURIComponent("/search")} className="rounded-xl border-2 border-slate-900 px-3 py-2 text-xs font-black text-slate-950">Daftar</a></div></section>}
      {session && incomingFollowRequests.length > 0 && <section className="mx-auto mb-3 max-w-xl rounded-2xl border-2 border-slate-900 bg-white p-3 shadow-[3px_3px_0px_#0f172a]">
        <div className="flex items-center justify-between"><h2 className="text-xs font-black text-slate-950">Permintaan mengikuti</h2><span className="rounded-full bg-amber-200 px-2 py-0.5 text-[10px] font-black">{incomingFollowRequests.length}</span></div>
        <div className="mt-2 space-y-2">
          {incomingFollowRequests.map(edge => <div key={edge.id} className="flex items-center justify-between gap-2 rounded-xl border border-slate-200 p-2">
            <div className="min-w-0"><p className="truncate text-xs font-bold text-slate-900">{edge.actor_node_type === "agent" ? "AI Agent · " + edge.actor_agent_id : "Human · " + edge.actor_user_id}</p><p className="text-[10px] text-slate-500">Meminta mengikuti profil Anda</p></div>
            <div className="flex shrink-0 gap-1"><button type="button" onClick={() => void resolveIncomingFollow(edge.id, true)} className="rounded-lg border-2 border-slate-900 bg-emerald-200 px-2 py-1 text-[10px] font-black">Terima</button><button type="button" onClick={() => void resolveIncomingFollow(edge.id, false)} className="rounded-lg border-2 border-slate-900 bg-rose-100 px-2 py-1 text-[10px] font-black">Tolak</button></div>
          </div>)}
        </div>
      </section>}
      <ExploreView
        posts={postsForReference}
        trendsData={trends}
        accountsData={combinedAccountsForReference}
        accountsLoading={creatorsBusy && combinedAccountsForReference.length === 0}
        accountsError={creatorsError && combinedAccountsForReference.length === 0 ? creatorsError : ""}
        discoveryError={discoveryError}
        relationshipError={socialGraphError}
        onRetryAccounts={() => { void loadCreators(); void loadSocialGraph(); void loadDiscoveredUsers(query); }}
        followedAccountIds={followedAccountIds}
        pendingFollowAccountIds={pendingFollowAccountIds}
        blockedAccountIds={blockedAccountIds}
        mutedAccountIds={mutedAccountIds}
        canBlockRelationships={!actorAgentId || ownedAgents.some(agent => agent.id === actorAgentId && agent.ownership_role === "owner")}
        onBlockAccount={(accountId, currentlyBlocked) => { void mutateSocialRelationship(accountId, "block", currentlyBlocked); }}
        onMuteAccount={(accountId, currentlyMuted) => { void mutateSocialRelationship(accountId, "mute", currentlyMuted); }}
        onFollowAccount={async (accountId, currentlyFollowed, currentlyPending = false) => {
          if (!session) { setAuthPrompt("Masuk untuk mengikuti kreator ini."); return; }
          const mutationEpoch = sessionEpoch.current;
          const targetId = accountId;
          const targetType = creators.some(item => item.id === targetId && item.is_ai) ? "agent" : "human";
          if (!targetId) {
            setSocialGraphError("Identitas target tidak valid.");
            return;
          }
          const removingRelationship = currentlyFollowed || currentlyPending;
          try {
            const edgeId = followEdgeIds[accountId];
            const response = await fetch(
              removingRelationship && edgeId
                ? apiBase + "/v1/social/relationships/" + encodeURIComponent(edgeId)
                : apiBase + "/v1/social/relationships",
              {
                method: removingRelationship ? "DELETE" : "POST",
                headers: {
                  Authorization: "Bearer " + session.access_token,
                  Accept: "application/json",
                  ...(removingRelationship ? {} : { "Content-Type": "application/json" }),
                },
                ...(removingRelationship ? {} : { body: JSON.stringify({ target_type: targetType, target_id: targetId, edge_type: "follow", ...(actorAgentId ? { actor_agent_id: actorAgentId } : {}) }) }),
                cache: "no-store",
              },
            );
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(payload?.error?.message || payload?.detail?.message || "Status mengikuti akun tidak dapat diubah.");
            if (sessionEpoch.current !== mutationEpoch) return;
            if (removingRelationship) {
              setFollowedAccountIds(previous => previous.filter(id => id !== accountId));
              setPendingFollowAccountIds(previous => previous.filter(id => id !== accountId));
              setFollowEdgeIds(previous => { const next = { ...previous }; delete next[accountId]; return next; });
            } else if (payload?.outcome === "follow_request_created" || payload?.edge?.status === "requested") {
              setFollowedAccountIds(previous => previous.filter(id => id !== accountId));
              setPendingFollowAccountIds(previous => [...new Set([...previous, accountId])]);
              if (payload?.edge?.id) setFollowEdgeIds(previous => ({ ...previous, [accountId]: payload.edge.id }));
            } else {
              setFollowedAccountIds(previous => [...new Set([...previous, accountId])]);
              setPendingFollowAccountIds(previous => previous.filter(id => id !== accountId));
              if (payload?.edge?.id) setFollowEdgeIds(previous => ({ ...previous, [accountId]: payload.edge.id }));
            }
            setSocialGraphError("");
            setAuthPrompt("");
          } catch (cause) {
            if (sessionEpoch.current === mutationEpoch) {
              setSocialGraphError(cause instanceof Error ? cause.message : "Status mengikuti akun tidak dapat diubah.");
            }
          }
        }}
        trendsLoading={trendsBusy}
        trendsError={trendsError}
        recommendationsData={recommendationsForReference}
        recommendationsLoading={recommendationsBusy}
        recommendationsError={recommendationsError}
        productionMode
        onOpenMarketplace={() => { window.location.assign("/marketplace"); }}
        onOpenStoreAndBoothModal={() => { window.location.assign("/profile?open=store"); }}
        initialSearchQuery={query}
        searchLoading={busy}
        searchError={error}
        searchEmpty={searched && !busy && !error && items.length === 0}
        searchPrompt={!searched && !busy && !error}
        onRetrySearch={() => { void runSearch(undefined, query); }}
        onRetryTrends={() => { void loadTrends(); }}
        onRetryRecommendations={() => { void loadRecommendations(); }}
        onSearch={value => { setQuery(value); void runSearch(undefined, value); }}
        onOpenAskAi={(agentName) => { if (!session) { setAuthPrompt("Masuk untuk menggunakan Tanya AI Agent."); return; } window.location.assign("/ask-ai?agent=" + encodeURIComponent(agentName)); }}
        onOpenWorld3D={() => { if (!session) { setAuthPrompt("Masuk untuk memasuki Universe 3D."); return; } window.location.assign("/spatial/navigation"); }}
        onOpenLiveStage={() => { if (!session) { setAuthPrompt("Masuk untuk bergabung dengan Live Stage."); return; } window.location.assign("/live"); }}
        onOpenFilmAi={() => { window.location.assign("/ai-cinema"); }}
      />
  </>;
}

export default function SearchPage() {
  return (
    <Suspense fallback={<main className="min-h-[70dvh] bg-sky-50 px-4 py-8 text-center text-sm font-semibold text-slate-600" role="status">Menyiapkan pencarian…</main>}>
      <SearchPageContent />
    </Suspense>
  );
}

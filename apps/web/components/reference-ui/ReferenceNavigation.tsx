"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../lib/supabase";
import Navbar from "./Navbar";
import BottomNav, { type TabType } from "./BottomNav";
import NotificationsModal from "./NotificationsModal";

const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

type NotificationSummary = { unread_count?: number };
type ConversationSummary = { unread_count?: number };
type ApiNotification = { id: string; event_key: string; title: string; body: string; read_at: string | null; created_at: string; payload?: Record<string, unknown> };
type NotificationItem = { id: string; category: "ALL" | "AI_AGENT" | "SOCIAL" | "CREDITS" | "SYSTEM"; title: string; message: string; timestamp: string; isRead: boolean; avatar?: string; badge?: string; badgeColor?: string };

function tabForPath(path: string): TabType {
  if (path.startsWith("/create")) return "CREATE";
  if (path.startsWith("/reels")) return "REELS";
  if (path.startsWith("/messages")) return "MESSAGES";
  if (path.startsWith("/live")) return "LIVESTAGE";
  if (path.startsWith("/spatial")) return "WORLD3D";
  if (path.startsWith("/skill-challenges")) return "SKILLS_CREDITS";
  if (path.startsWith("/search") || path.startsWith("/communities")) return "EXPLORE";
  if (path.startsWith("/ai-cinema")) return "FILM_AI";
  if (path.startsWith("/marketplace")) return "MARKETPLACE";
  if (path.startsWith("/stories") || path.startsWith("/feed")) return "FEED";
  if (path.startsWith("/profile") || path.startsWith("/agents")) return "PROFILE";
  return "FEED";
}

const routeForTab: Partial<Record<TabType, string>> = {
  FEED: "/feed",
  EXPLORE: "/search",
  CREATE: "/create",
  LIVESTAGE: "/live",
  WORLD3D: "/spatial/navigation",
  MESSAGES: "/messages",
  REELS: "/reels",
  SKILLS_CREDITS: "/skill-challenges",
  MARKETPLACE: "/marketplace",
  PROFILE: "/profile",
  POST_DETAIL: "/feed",
  TAKEOVER_CONTROL: "/agents",
  ASK_AI_VIEW: "/ask-ai",
  FILM_AI: "/ai-cinema",
};

export default function ReferenceNavigation() {
  const pathname = usePathname() || "/feed";
  const router = useRouter();
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const indicatorRequestSequence = useRef(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [session, setSession] = useState<Session | null>(null);
  const [unreadMessagesCount, setUnreadMessagesCount] = useState<number | undefined>(undefined);
  const [hasUnreadNotifications, setHasUnreadNotifications] = useState<boolean | null>(null);
  const [notificationsModalOpen, setNotificationsModalOpen] = useState(false);
  const [notificationsLoading, setNotificationsLoading] = useState(false);
  const [notificationsError, setNotificationsError] = useState("");
  const [notificationItems, setNotificationItems] = useState<NotificationItem[]>([]);
  const notificationRequestSequence = useRef(0);

  const refreshInboxIndicators = useCallback(async (current: Session | null) => {
    const sequence = ++indicatorRequestSequence.current;
    if (!current) {
      setUnreadMessagesCount(undefined);
      setHasUnreadNotifications(null);
      return;
    }

    // Reset on session changes and discard responses from prior accounts.
    setUnreadMessagesCount(undefined);
    setHasUnreadNotifications(null);
    const headers = { Authorization: "Bearer " + current.access_token, Accept: "application/json" };
    const [notifications, conversations] = await Promise.allSettled([
      fetch(apiBase + "/v1/notifications?limit=1", { headers, cache: "no-store" }),
      fetch(apiBase + "/v1/messages/conversations", { headers, cache: "no-store" }),
    ]);
    if (sequence !== indicatorRequestSequence.current) return;

    let notificationUnread: boolean | null = null;
    let messagesUnread: number | undefined;
    if (notifications.status === "fulfilled" && notifications.value.ok) {
      const summary = await notifications.value.json().catch(() => null) as NotificationSummary | null;
      if (sequence !== indicatorRequestSequence.current) return;
      if (typeof summary?.unread_count === "number" && Number.isFinite(summary.unread_count)) {
        notificationUnread = summary.unread_count > 0;
      }
    }
    if (conversations.status === "fulfilled" && conversations.value.ok) {
      const summary = await conversations.value.json().catch(() => null) as ConversationSummary | null;
      if (sequence !== indicatorRequestSequence.current) return;
      if (typeof summary?.unread_count === "number" && Number.isFinite(summary.unread_count)) {
        messagesUnread = Math.max(0, summary.unread_count);
      }
    }

    if (sequence !== indicatorRequestSequence.current) return;
    setHasUnreadNotifications(notificationUnread);
    setUnreadMessagesCount(messagesUnread);
  }, []);

  useEffect(() => {
    if (!supabase) {
      setSession(null);
      void refreshInboxIndicators(null);
      return;
    }
    let active = true;
    let authEventSeen = false;
    void supabase.auth.getSession().then(({ data }) => {
      if (!active || authEventSeen) return;
      setSession(data.session);
      void refreshInboxIndicators(data.session);
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, next) => {
      authEventSeen = true;
      if (!active) return;
      setSession(next);
      void refreshInboxIndicators(next);
    });
    return () => {
      active = false;
      indicatorRequestSequence.current += 1;
      listener.subscription.unsubscribe();
    };
  }, [supabase, refreshInboxIndicators]);

  const loadNotifications = useCallback(async () => {
    if (!session) {
      const returnTo = typeof window === "undefined" ? "/feed" : window.location.pathname + window.location.search;
      router.push("/login?next=" + encodeURIComponent(returnTo) + "&mode=login");
      setNotificationsModalOpen(false);
      return;
    }
    const sequence = ++notificationRequestSequence.current;
    setNotificationsLoading(true);
    setNotificationsError("");
    try {
      const response = await fetch(apiBase + "/v1/notifications?limit=50", {
        headers: { Authorization: "Bearer " + session.access_token, Accept: "application/json" },
        cache: "no-store",
      });
      if (!response.ok) throw new Error("Notifikasi gagal dimuat (HTTP " + response.status + ").");
      const data = await response.json() as { items?: ApiNotification[] };
      if (sequence !== notificationRequestSequence.current) return;
      setNotificationItems((data.items ?? []).map((item) => {
        const key = (item.event_key || "").toLowerCase();
        const category: NotificationItem["category"] = /credit|billing|settlement|royalt/.test(key)
          ? "CREDITS" : /agent|skill|runtime/.test(key) ? "AI_AGENT" : /social|follow|like|comment|message/.test(key)
          ? "SOCIAL" : /security|system|policy/.test(key) ? "SYSTEM" : "ALL";
        return {
          id: item.id,
          category,
          title: item.title,
          message: item.body,
          timestamp: new Date(item.created_at).toLocaleString("id-ID"),
          isRead: Boolean(item.read_at),
        };
      }));
    } catch (cause) {
      if (sequence === notificationRequestSequence.current) {
        setNotificationsError(cause instanceof Error ? cause.message : "Notifikasi gagal dimuat.");
      }
    } finally {
      if (sequence === notificationRequestSequence.current) setNotificationsLoading(false);
    }
  }, [router, session]);

  useEffect(() => {
    if (notificationsModalOpen) void loadNotifications();
    else notificationRequestSequence.current += 1;
  }, [notificationsModalOpen, loadNotifications]);

  const markNotificationRead = useCallback(async (id: string) => {
    if (!session) return;
    setNotificationsError("");
    try {
      const response = await fetch(apiBase + "/v1/notifications/" + encodeURIComponent(id) + "/read", {
        method: "PATCH",
        headers: { Authorization: "Bearer " + session.access_token, Accept: "application/json", "Content-Type": "application/json" },
        body: "{}",
        cache: "no-store",
      });
      if (!response.ok) throw new Error("Status baca notifikasi gagal disimpan (HTTP " + response.status + ").");
      setNotificationItems(current => current.map(item => item.id === id ? { ...item, isRead: true } : item));
      void refreshInboxIndicators(session);
    } catch (cause) {
      setNotificationsError(cause instanceof Error ? cause.message : "Status baca notifikasi gagal disimpan.");
    }
  }, [refreshInboxIndicators, session]);

  const markAllNotificationsRead = useCallback(async () => {
    if (!session) return;
    setNotificationsError("");
    try {
      const response = await fetch(apiBase + "/v1/notifications/read-all", {
        method: "POST",
        headers: { Authorization: "Bearer " + session.access_token, Accept: "application/json", "Content-Type": "application/json" },
        body: "{}",
        cache: "no-store",
      });
      if (!response.ok) throw new Error("Notifikasi gagal ditandai dibaca (HTTP " + response.status + ").");
      setNotificationItems(current => current.map(item => ({ ...item, isRead: true })));
      void refreshInboxIndicators(session);
    } catch (cause) {
      setNotificationsError(cause instanceof Error ? cause.message : "Notifikasi gagal ditandai dibaca.");
    }
  }, [refreshInboxIndicators, session]);

  const navigate = (path: string) => router.push(path);
  const setActiveTab = (tab: TabType) => navigate(routeForTab[tab] ?? "/feed");

  return (
    <>
      <Navbar
        userCredits={null}
        agentCredits={null}
        isTakeoverActive={null}
        unreadMessagesCount={unreadMessagesCount}
        hasUnreadNotifications={hasUnreadNotifications}
        onOpenTakeoverModal={() => navigate("/agents")}
        onOpenCreditsHub={() => navigate("/skill-challenges")}
        onOpenOnboarding={() => navigate("/agents?onboarding=required")}
        onOpenMessages={() => navigate("/messages")}
        onOpenNotifications={() => setNotificationsModalOpen(true)}
        isMessagesActive={pathname.startsWith("/messages")}
        searchQuery={searchQuery}
        setSearchQuery={setSearchQuery}
        onSearch={(query: string) => navigate("/search?q=" + encodeURIComponent(query))}
      />
      <BottomNav
        activeTab={tabForPath(pathname)}
        setActiveTab={setActiveTab}
        onOpenCreateModal={() => navigate("/feed?compose=1")}
      />
      <NotificationsModal
        isOpen={notificationsModalOpen}
        onClose={() => setNotificationsModalOpen(false)}
        notifications={notificationItems}
        loading={notificationsLoading}
        error={notificationsError}
        onMarkRead={(id) => { void markNotificationRead(id); }}
        onMarkAllRead={() => { void markAllNotificationsRead(); }}
        onOpenMessages={() => { setNotificationsModalOpen(false); navigate("/messages"); }}
        onOpenCreditsHub={() => { setNotificationsModalOpen(false); navigate("/skill-challenges"); }}
        onOpenLiveStage={() => { setNotificationsModalOpen(false); navigate("/live"); }}
        onNavigateToTab={(tab) => { setNotificationsModalOpen(false); navigate(routeForTab[tab as TabType] ?? "/feed"); }}
      />
    </>
  );
}

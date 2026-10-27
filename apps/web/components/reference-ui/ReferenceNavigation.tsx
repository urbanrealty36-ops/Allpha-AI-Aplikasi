"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../lib/supabase";
import Navbar from "./Navbar";
import BottomNav, { type TabType } from "./BottomNav";

const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

type NotificationSummary = { unread_count?: number };
type ConversationSummary = { unread_count?: number };

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
    void supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      setSession(data.session);
      void refreshInboxIndicators(data.session);
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, next) => {
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
        onOpenNotifications={() => navigate("/notifications")}
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
    </>
  );
}

"use client";

import { useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import Navbar from "./Navbar";
import BottomNav, { type TabType } from "./BottomNav";

function tabForPath(path: string): TabType {
  if (path.startsWith("/create")) return "CREATE";
  if (path.startsWith("/live")) return "LIVESTAGE";
  if (path.startsWith("/marketplace")) return "MARKETPLACE";
  if (path.startsWith("/cinema")) return "FILM_AI";
  if (path.startsWith("/reels")) return "REELS";
  if (path.startsWith("/messages")) return "MESSAGES";
  if (path.startsWith("/spatial")) return "WORLD3D";
  if (path.startsWith("/skill-challenges")) return "SKILLS_CREDITS";
  if (path.startsWith("/search") || path.startsWith("/communities")) return "EXPLORE";
  if (path.startsWith("/content-studio")) return "FILM_AI";
  if (path.startsWith("/agents")) return "PROFILE";
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
  PROFILE: "/agents",
  POST_DETAIL: "/feed",
  TAKEOVER_CONTROL: "/agents",
  ASK_AI_VIEW: "/content-studio",
  FILM_AI: "/cinema",
};

export default function ReferenceNavigation() {
  const pathname = usePathname() || "/feed";
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState("");

  const navigate = (path: string) => router.push(path);
  const setActiveTab = (tab: TabType) => navigate(routeForTab[tab] ?? "/feed");

  return (
    <>
      <Navbar
        userCredits={null}
        agentCredits={null}
        isTakeoverActive={null}
        onOpenTakeoverModal={() => navigate("/agents")}
        onOpenCreditsHub={() => navigate("/skill-challenges")}
        onOpenOnboarding={() => navigate("/agents?onboarding=required")}
        onOpenMessages={() => navigate("/messages")}
        onOpenNotifications={() => navigate("/notifications")}
        isMessagesActive={pathname.startsWith("/messages")}
        unreadMessagesCount={0}
        searchQuery={searchQuery}
        setSearchQuery={setSearchQuery}
        onSearchSubmit={() => { const query = searchQuery.trim(); navigate(query ? `/search?q=${encodeURIComponent(query)}` : "/search"); }}
      />
      <BottomNav
        activeTab={tabForPath(pathname)}
        setActiveTab={setActiveTab}
        onOpenCreateModal={() => navigate("/create")}
      />
    </>
  );
}

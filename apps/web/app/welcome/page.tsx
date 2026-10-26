"use client";

import { useMemo } from "react";
import { useRouter } from "next/navigation";
import AuthOnboardingPage from "@/components/reference-ui/AuthOnboardingPage";
import type { HumanProfile, AIAgentProfile } from "@/lib/reference-store";

const emptyHuman: HumanProfile = {
  id: "",
  name: "",
  username: "",
  avatar: "",
  bio: "",
  followers: 0,
  following: 0,
  postsCount: 0,
  badge: "Human",
};

const emptyAgent: AIAgentProfile = {
  id: "",
  name: "",
  handle: "",
  avatar: "",
  ownerId: "",
  ownerName: "",
  ownerHandle: "",
  specialty: "",
  category: "Kreativitas",
  bio: "",
  skills: [],
  creditsEarned: 0,
  autoReply: false,
  model: "Allpha AI Runtime",
  goals: [],
  tasks: [],
};

export default function WelcomePage() {
  const router = useRouter();
  const human = useMemo(() => emptyHuman, []);
  const agent = useMemo(() => emptyAgent, []);

  return (
    <AuthOnboardingPage
      currentUser={human}
      currentAgent={agent}
      onEnterApp={() => router.push("/feed")}
      onStartAuthentication={() => router.push("/login")}
      onCompleteAuth={() => {
        // Production authentication/profile provisioning is handled only by
        // AuthOnboardingRoute and the canonical Supabase + FastAPI flow.
        router.push("/login");
      }}
    />
  );
}

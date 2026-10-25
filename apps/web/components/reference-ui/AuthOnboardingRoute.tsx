"use client";

import { useMemo } from "react";
import { useRouter } from "next/navigation";
import type { Session } from "@supabase/supabase-js";
import AuthOnboardingFlow from "./AuthOnboardingFlow";
import type { AIAgentProfile, HumanProfile } from "@/lib/reference-store";
import { getBrowserSupabase } from "@/lib/supabase";

const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

async function responseError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return body?.detail?.message ?? body?.error?.message ?? `Permintaan gagal (${response.status}).`;
  } catch {
    return `Permintaan gagal (${response.status}).`;
  }
}

type SkillItem = { key: string; name: string; slug: string; category: string; catalog_version?: string; source?: { kind?: string }; character_profile?: Record<string, unknown> };
type AgentList = { items?: Array<{ id: string }> };

export default function AuthOnboardingRoute() {
  const router = useRouter();
  const supabase = useMemo(() => getBrowserSupabase(), []);

  async function complete(payload: {
    user: HumanProfile;
    agent: AIAgentProfile;
    email: string;
    password: string;
    authMode: "REGISTER" | "LOGIN";
    interests: string[];
    persona: string;
  }) {
    if (!supabase) throw new Error("Supabase Auth belum dikonfigurasi. Periksa environment Web.");
    let session: Session | null = null;

    if (payload.authMode === "REGISTER") {
      const { data, error } = await supabase.auth.signUp({
        email: payload.email,
        password: payload.password,
        options: { data: { display_name: payload.user.name.trim(), locale: "id-ID" } },
      });
      if (error) throw error;
      session = data.session;
      if (!session) throw new Error("Akun tercatat oleh Supabase, tetapi sesi belum tersedia. Konfirmasi email terlebih dahulu, lalu masuk kembali untuk melanjutkan pembuatan Agent.");
    } else {
      const { data, error } = await supabase.auth.signInWithPassword({ email: payload.email, password: payload.password });
      if (error) throw error;
      session = data.session;
    }
    if (!session) throw new Error("Sesi Supabase tidak tersedia. Silakan coba masuk kembali.");

    const headers = { Authorization: `Bearer ${session.access_token}`, "Content-Type": "application/json" };
    const existingResponse = await fetch(apiBase + "/v1/agents", { headers: { Authorization: headers.Authorization }, cache: "no-store" });
    if (!existingResponse.ok) throw new Error(await responseError(existingResponse));
    const existing = await existingResponse.json() as AgentList;
    if (existing.items?.length) {
      router.replace("/feed");
      return;
    }
    if (payload.authMode === "LOGIN") {
      router.replace("/agents?onboarding=required");
      return;
    }

    if (!payload.user.name.trim() || !payload.user.username.replace(/^@/, "").trim()) {
      throw new Error("Lengkapi nama dan username Human sebelum membuat Agent.");
    }
    const meResponse = await fetch(apiBase + "/v1/me", { headers: { Authorization: headers.Authorization }, cache: "no-store" });
    if (!meResponse.ok) throw new Error(await responseError(meResponse));

    const identityResponse = await fetch(apiBase + "/v1/me/profile", {
      method: "PATCH",
      headers,
      body: JSON.stringify({
        username: payload.user.username.replace(/^@/, "").trim().toLowerCase(),
        display_name: payload.user.name.trim(),
        avatar_url: payload.user.avatar || null,
        bio: payload.user.bio.trim(),
      }),
      cache: "no-store",
    });
    if (!identityResponse.ok) throw new Error(await responseError(identityResponse));

    for (const interest of payload.interests) {
      const interest_key = interest.toLowerCase().trim().replace(/[^a-z0-9._-]+/g, "-").replace(/^-+|-+$/g, "");
      if (!interest_key) continue;
      const response = await fetch(apiBase + "/v1/me/interests", {
        method: "PUT", headers, body: JSON.stringify({ interest_key, preference: "interested" }), cache: "no-store",
      });
      if (!response.ok) throw new Error(await responseError(response));
    }

    const catalogPages = await Promise.all([0, 100, 200, 300, 400].map(async (offset) => {
      const response = await fetch(apiBase + "/v1/skill-catalog?limit=100&offset=" + offset, { cache: "no-store" });
      if (!response.ok) throw new Error(await responseError(response));
      return await response.json() as { items?: SkillItem[] };
    }));
    const selectedSkillNames = new Set(payload.agent.skills.map((skill) => skill.trim().toLocaleLowerCase()));
    const selectedSkill = catalogPages.flatMap((page) => page.items ?? []).find((item) =>
      selectedSkillNames.has(item.name.trim().toLocaleLowerCase()) ||
      selectedSkillNames.has(item.slug.trim().toLocaleLowerCase()) ||
      selectedSkillNames.has(item.key.trim().toLocaleLowerCase())
    );
    if (!selectedSkill) {
      throw new Error("Skill yang dipilih belum memiliki padanan di katalog Skill kanonis FastAPI. Akun dan profil tersimpan; pilih Skill yang tersedia di katalog Agent untuk melanjutkan. Tidak ada Agent dummy yang dibuat.");
    }

    const agentResponse = await fetch(apiBase + "/v1/agents", {
      method: "POST",
      headers,
      body: JSON.stringify({
        handle: payload.agent.handle.replace(/^@/, "").trim().toLowerCase(),
        display_name: payload.agent.name.trim(),
        description: payload.agent.bio.trim(),
        avatar_url: payload.agent.avatar3DImage || null,
        persona: {
          tone: payload.persona,
          language: "id-ID",
          allpha_skill_key: selectedSkill.key,
          allpha_skill_catalog_version: selectedSkill.catalog_version ?? "allpha-skill-catalog-v1",
          allpha_skill_source: selectedSkill.source?.kind === "agency_agent_definition_metadata" ? "agency-agents" : "allpha-500",
          character_profile: selectedSkill.character_profile ?? {},
          selected_skills: payload.agent.skills,
          bidang: payload.agent.bidang ?? null,
        },
        disclosure: "Agent AI; respons dapat dihasilkan oleh model.",
        boundaries: { requires_owner_approval_for_external_actions: true, private_owner_data: "owner_only" },
        visibility: "private",
      }),
      cache: "no-store",
    });
    if (!agentResponse.ok) throw new Error(await responseError(agentResponse));
    router.replace("/feed");
  }

  return (
    <>
      <AuthOnboardingFlow
        isOpen
        onClose={() => router.replace("/feed")}
        onComplete={complete}
      />
    </>
  );
}

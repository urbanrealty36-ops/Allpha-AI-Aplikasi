"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../lib/supabase";
import AskAiView from "../../components/reference-ui/AskAiView";
import type { HumanProfile } from "../../lib/reference-store";

type MeResponse = { user?: { id: string; email?: string }; profile?: { username?: string | null; display_name?: string; avatar_url?: string | null; bio?: string } | null };
type Agent = { id: string; handle: string; display_name: string; description: string; status: string };
type Skill = { id: string; name?: string; display_name?: string; status: string; version: number };
type Capability = { capability_key: string; status: string };
type GenerationJob = { id: string; status: string; output_text?: string | null; error_code?: string | null; credits_to_reserve?: number };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return body?.error?.message || body?.detail?.message || "Permintaan AI belum dapat diproses.";
  } catch {
    return `Layanan AI merespons HTTP ${response.status}.`;
  }
}

const wait = (milliseconds: number) => new Promise(resolve => window.setTimeout(resolve, milliseconds));

export default function AskAiPage() {
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<HumanProfile | null>(null);
  const [agent, setAgent] = useState<Agent | null>(null);
  const [skill, setSkill] = useState<Skill | null>(null);
  const [capability, setCapability] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!supabase) { setError("Konfigurasi autentikasi belum tersedia."); setLoading(false); return; }
    let active = true;
    const load = async (current: Session | null) => {
      setSession(current);
      setUser(null); setAgent(null); setSkill(null); setCapability(""); setError("");
      if (!current) { setLoading(false); return; }
      setLoading(true);
      const headers = { Authorization: "Bearer " + current.access_token, Accept: "application/json" };
      try {
        const [meResponse, agentResponse] = await Promise.all([
          fetch(apiBase + "/v1/me", { headers, cache: "no-store" }),
          fetch(apiBase + "/v1/agents", { headers, cache: "no-store" }),
        ]);
        if (!meResponse.ok) throw new Error(await readError(meResponse));
        if (!agentResponse.ok) throw new Error(await readError(agentResponse));
        const me = await meResponse.json() as MeResponse;
        const agents = await agentResponse.json() as { items?: Agent[] };
        if (!me.user) throw new Error("Identitas Human kanonis tidak tersedia.");
        const name = me.profile?.display_name?.trim() || me.user.email || "Pengguna";
        if (!active) return;
        setUser({ id: me.user.id, name, username: me.profile?.username || me.user.email || "", avatar: me.profile?.avatar_url || "/icon.svg", bio: me.profile?.bio || "", followers: 0, following: 0, postsCount: 0, badge: "Human" });
        const selectedAgent = (agents.items || []).find(item => item.status === "active");
        if (!selectedAgent) throw new Error("Belum ada AI Agent aktif milik akun ini.");
        const [skillsResponse, capabilitiesResponse] = await Promise.all([
          fetch(apiBase + `/v1/agents/${selectedAgent.id}/skills`, { headers, cache: "no-store" }),
          fetch(apiBase + `/v1/agents/${selectedAgent.id}/capabilities`, { headers, cache: "no-store" }),
        ]);
        if (!skillsResponse.ok) throw new Error(await readError(skillsResponse));
        if (!capabilitiesResponse.ok) throw new Error(await readError(capabilitiesResponse));
        const skills = await skillsResponse.json() as { items?: Skill[] };
        const capabilities = await capabilitiesResponse.json() as { items?: Capability[] };
        const publishedSkill = (skills.items || []).find(item => item.status === "published");
        const approvedCapability = (capabilities.items || []).find(item => item.status === "approved");
        if (!publishedSkill) throw new Error("Agent belum memiliki Skill yang dipublikasikan dan dapat digunakan.");
        if (!approvedCapability) throw new Error("Agent belum memiliki capability yang disetujui untuk generation.");
        if (!active) return;
        setAgent(selectedAgent); setSkill(publishedSkill); setCapability(approvedCapability.capability_key);
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : "Konfigurasi Agent tidak dapat dimuat.");
      } finally {
        if (active) setLoading(false);
      }
    };
    void supabase.auth.getSession().then(({ data }) => load(data.session));
    const { data: listener } = supabase.auth.onAuthStateChange((_event, next) => { void load(next); });
    return () => { active = false; listener.subscription.unsubscribe(); };
  }, [supabase]);

  const submitQuery = useCallback(async (prompt: string) => {
    if (!session || !agent || !skill || !capability) throw new Error("Agent, Skill, atau capability belum siap.");
    const headers = { Authorization: "Bearer " + session.access_token, Accept: "application/json", "Content-Type": "application/json" };
    const createResponse = await fetch(apiBase + "/v1/generation/jobs", {
      method: "POST",
      headers: { ...headers, "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({ agent_id: agent.id, skill_id: skill.id, capability_id: capability, prompt, max_output_tokens: 1200 }),
      cache: "no-store",
    });
    if (!createResponse.ok) throw new Error(await readError(createResponse));
    const created = await createResponse.json() as { job_id: string; reserved_credits?: number };
    if (!created.job_id) throw new Error("Generation job belum dikonfirmasi oleh API.");

    for (let attempt = 0; attempt < 60; attempt += 1) {
      await wait(2000);
      const statusResponse = await fetch(apiBase + `/v1/generation/jobs/${created.job_id}`, { headers: { Authorization: headers.Authorization, Accept: "application/json" }, cache: "no-store" });
      if (!statusResponse.ok) throw new Error(await readError(statusResponse));
      const payload = await statusResponse.json() as { job?: GenerationJob };
      const job = payload.job;
      if (!job) throw new Error("Status Generation Job tidak ditemukan.");
      if (job.status === "succeeded" && job.output_text) {
        return { text: job.output_text, jobId: created.job_id, reservedCredits: created.reserved_credits };
      }
      if (job.status === "failed" || job.status === "cancelled") {
        throw new Error(job.error_code || "Generation gagal. Reservasi mengikuti kebijakan refund yang berlaku.");
      }
      if (job.status === "pending_reconciliation") {
        throw new Error("Status provider belum dapat dipastikan. Permintaan masuk rekonsiliasi; tidak ada pengulangan otomatis.");
      }
    }
    throw new Error("Generation masih berjalan. Periksa riwayat Generation untuk status terbaru; permintaan tidak dikirim ulang.");
  }, [session, agent, skill, capability]);

  if (!session) return <main className="mx-auto max-w-xl p-6"><h1 className="text-xl font-bold">Tanya AI Agent</h1><p className="mt-3 text-sm text-slate-600">Masuk ke Allpha untuk memuat identitas dan AI Agent kanonis.</p><Link className="mt-4 inline-flex rounded-xl bg-blue-600 px-4 py-2 text-white" href="/login">Masuk</Link></main>;
  if (loading || !user) return <main className="mx-auto max-w-xl p-6 text-sm text-slate-600" role="status">{error || "Memuat identitas dan capability Allpha…"}</main>;
  const unavailable = error || (!agent || !skill || !capability ? "Belum ada Agent, Skill published, atau capability approved yang memenuhi syarat. Tidak ada kredit yang dipotong." : "");
  return <>
    {unavailable && <p role="status" className="mx-auto max-w-xl px-4 pt-3 text-xs text-amber-800">{unavailable}</p>}
    <AskAiView onBack={() => { window.location.assign("/feed"); }} agentName={agent?.display_name || "AI Agent"} humanOwner={user.name} specialty={agent?.description || "AI Agent Allpha"} currentUser={user} onSubmitQuery={submitQuery} availabilityMessage={unavailable} />
  </>;
}

"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../../lib/supabase";
import GenerateModal, { type GenerateRequest } from "../../components/reference-ui/GenerateModal";

type Agent = { id: string; display_name: string; description?: string; status: string };
type Skill = { id: string; name?: string; display_name?: string; status: string; version: number };
type Capability = { capability_key: string; status: string };
type ExternalAgent = { agent: Agent; owner_user_id: string; skill: Skill; capabilities: Capability[]; consumer_grant_id: string; granted_scopes: string[] };
type Job = { status: string; artifact_available?: boolean; artifact_deletion_status?: "available" | "pending" | "deleted" | "unavailable"; error_code?: string | null; owner_reward_status?: string | null; dm_conversation_id?: string | null };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

async function errorMessage(response: Response) {
  try { const body = await response.json(); return body?.error?.message || body?.detail?.message || `Permintaan gagal (HTTP ${response.status}).`; }
  catch { return `Permintaan gagal (HTTP ${response.status}).`; }
}
const wait = (ms: number) => new Promise(resolve => window.setTimeout(resolve, ms));

export default function GeneratePage() {
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [externalAgents, setExternalAgents] = useState<ExternalAgent[]>([]);
  const [consumerGrantId, setConsumerGrantId] = useState("");
  const [agentId, setAgentId] = useState("");
  const [skills, setSkills] = useState<Skill[]>([]);
  const [skillId, setSkillId] = useState("");
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [capabilityId, setCapabilityId] = useState("");
  const [generatorOpen, setGeneratorOpen] = useState(false);
  const [knowledgeQuery, setKnowledgeQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [artifactDeleting, setArtifactDeleting] = useState(false);
  const [result, setResult] = useState("");
  const [jobId, setJobId] = useState("");
  const [dmConversationId, setDmConversationId] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (!supabase) { setError("Autentikasi Allpha belum dikonfigurasi."); setLoading(false); return; }
    let active = true;
    const load = async (current: Session | null) => {
      setSession(current); setAgents([]); setExternalAgents([]); setConsumerGrantId(""); setSkills([]); setCapabilities([]); setAgentId(""); setSkillId(""); setCapabilityId("");
      if (!current) { setLoading(false); return; }
      setLoading(true); setError("");
      try {
        const response = await fetch(apiBase + "/v1/agents", { headers: { Authorization: "Bearer " + current.access_token, Accept: "application/json" }, cache: "no-store" });
        if (!response.ok) throw new Error(await errorMessage(response));
        const data = await response.json() as { items?: Agent[] };
        const eligible = (data.items || []).filter(agent => agent.status === "active");
        let shared: ExternalAgent[] = [];
        try {
          const sharedResponse = await fetch(apiBase + "/v1/generation/agents", { headers: { Authorization: "Bearer " + current.access_token, Accept: "application/json" }, cache: "no-store" });
          if (sharedResponse.ok) {
            const sharedData = await sharedResponse.json() as { items?: ExternalAgent[] };
            shared = (sharedData.items || []).filter(item => item.agent?.status === "active" && item.skill?.status === "published" && item.consumer_grant_id);
          }
        } catch { /* Own-Agent generation remains available if the optional grant catalog is unavailable. */ }
        if (!active) return;
        setAgents(eligible); setExternalAgents(shared);
        if (!eligible.length && !shared.length) setError("Belum ada AI Agent aktif milik Anda atau Agent publik yang memberikan grant generation.");
      } catch (cause) { if (active) setError(cause instanceof Error ? cause.message : "Agent tidak dapat dimuat."); }
      finally { if (active) setLoading(false); }
    };
    void supabase.auth.getSession().then(({ data }) => load(data.session));
    const { data: listener } = supabase.auth.onAuthStateChange((_event, current) => { void load(current); });
    return () => { active = false; listener.subscription.unsubscribe(); };
  }, [supabase]);

  useEffect(() => {
    if (!session) return;
    const linkedJobId = new URLSearchParams(window.location.search).get("job_id");
    if (!linkedJobId || !/^[0-9a-f-]{36}$/i.test(linkedJobId)) return;
    let active = true;
    const loadPrivateArtifact = async () => {
      setJobId(linkedJobId); setBusy(true); setError(""); setNotice("");
      const headers = { Authorization: "Bearer " + session.access_token, Accept: "application/json" };
      try {
        const statusResponse = await fetch(apiBase + "/v1/generation/jobs/" + encodeURIComponent(linkedJobId), { headers, cache: "no-store" });
        if (!statusResponse.ok) throw new Error(await errorMessage(statusResponse));
        const statusPayload = await statusResponse.json() as { job?: Job };
        if (!statusPayload.job) throw new Error("Generation Job tidak ditemukan.");
        if (statusPayload.job.artifact_deletion_status === "pending") {
          setNotice("Penghapusan artefak sedang diproses. Akses file telah dinonaktifkan.");
          return;
        }
        if (statusPayload.job.artifact_deletion_status === "deleted") {
          setNotice("Artefak privat ini sudah dihapus oleh pemiliknya.");
          return;
        }
        if (statusPayload.job.status !== "succeeded" || !statusPayload.job.artifact_available) {
          throw new Error(statusPayload.job.error_code || "Artefak belum tersedia atau masih menunggu rekonsiliasi.");
        }
        const artifactResponse = await fetch(apiBase + "/v1/generation/jobs/" + encodeURIComponent(linkedJobId) + "/artifact", { headers, cache: "no-store" });
        if (!artifactResponse.ok) throw new Error(await errorMessage(artifactResponse));
        const artifact = await artifactResponse.json() as { url?: string };
        if (!artifact.url) throw new Error("Referensi artefak privat belum tersedia.");
        const outputResponse = await fetch(artifact.url, { cache: "no-store" });
        if (!outputResponse.ok) throw new Error("Unduhan artefak privat gagal.");
        const output = await outputResponse.text();
        if (!active) return;
        setResult(output);
        setNotice("Artefak privat dibuka dari DM. Akses menggunakan URL sementara dan tetap dibatasi pada pemilik job.");
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : "Artefak privat tidak dapat dibuka.");
      } finally { if (active) setBusy(false); }
    };
    void loadPrivateArtifact();
    return () => { active = false; };
  }, [session]);

  useEffect(() => {
    if (!session || !agentId) return;
    let active = true;
    const headers = { Authorization: "Bearer " + session.access_token, Accept: "application/json" };
    setSkills([]); setCapabilities([]); setSkillId(""); setCapabilityId(""); setError("");
    if (consumerGrantId) {
      const shared = externalAgents.find(item => item.consumer_grant_id === consumerGrantId && item.agent.id === agentId);
      if (!shared) { setError("Grant Agent eksternal tidak lagi tersedia."); return () => { active = false; }; }
      const approved = shared.capabilities.filter(item => item.status === "approved");
      setSkills([shared.skill]); setCapabilities(approved);
      setSkillId(shared.skill.id); setCapabilityId(approved[0]?.capability_key || "");
      if (!approved.length) setError("Agent eksternal belum memiliki capability approved.");
      return () => { active = false; };
    }
    void Promise.all([
      fetch(apiBase + `/v1/agents/${agentId}/skills`, { headers, cache: "no-store" }),
      fetch(apiBase + `/v1/agents/${agentId}/capabilities`, { headers, cache: "no-store" }),
    ]).then(async ([skillsResponse, capsResponse]) => {
      if (!skillsResponse.ok) throw new Error(await errorMessage(skillsResponse));
      if (!capsResponse.ok) throw new Error(await errorMessage(capsResponse));
      const skillData = await skillsResponse.json() as { items?: Skill[] };
      const capData = await capsResponse.json() as { items?: Capability[] };
      if (!active) return;
      const published = (skillData.items || []).filter(item => item.status === "published");
      const approved = (capData.items || []).filter(item => item.status === "approved");
      setSkills(published); setCapabilities(approved);
      if (!published.length || !approved.length) setError("Agent ini belum memiliki Skill published dan capability approved.");
      else { setSkillId(published[0].id); setCapabilityId(approved[0].capability_key); }
    }).catch(cause => { if (active) setError(cause instanceof Error ? cause.message : "Skill/capability tidak dapat dimuat."); });
    return () => { active = false; };
  }, [session, agentId, consumerGrantId, externalAgents]);

  async function generate(request: GenerateRequest): Promise<string | null> {
    if (!session || !agentId || !skillId || !capabilityId || busy) {
      throw new Error("Pilih Agent, Skill, dan capability yang valid sebelum generation.");
    }
    const promptText = [
      "Jenis konten: " + request.contentType,
      "Brand: " + request.brandName,
      "Produk/jasa: " + request.productDetails,
      "Brief: " + request.brief,
    ].join("\n");
    setBusy(true); setError(""); setNotice(""); setResult(""); setJobId(""); setDmConversationId("");
    const headers = { Authorization: "Bearer " + session.access_token, Accept: "application/json", "Content-Type": "application/json" };
    const body = { agent_id: agentId, skill_id: skillId, capability_id: capabilityId, prompt: promptText, max_output_tokens: 1800, ...(consumerGrantId ? { consumer_grant_id: consumerGrantId } : {}), ...((!consumerGrantId || externalAgents.find(item => item.consumer_grant_id === consumerGrantId)?.granted_scopes.includes("knowledge_public_read")) && knowledgeQuery.trim() ? { knowledge_query: knowledgeQuery.trim() } : {}) };
    try {
      const quoteResponse = await fetch(apiBase + "/v1/generation/quote", { method: "POST", headers, body: JSON.stringify(body), cache: "no-store" });
      if (!quoteResponse.ok) throw new Error(await errorMessage(quoteResponse));
      const quote = await quoteResponse.json() as { quote_id: string; expires_at: string; estimated_credits: number; model_id: string; policy_version: string; tariff_version: string; knowledge_context_sha256?: string | null; knowledge_source_count?: number; payer_role?: string; consumer_grant_id?: string; agent_snapshot_sha256: string; skill_snapshot_sha256: string };
      if (!quote.quote_id || Date.parse(quote.expires_at) <= Date.now() || !Number.isSafeInteger(quote.estimated_credits) || quote.estimated_credits <= 0) {
        throw new Error("Quote generation tidak valid atau sudah kedaluwarsa.");
      }
      if (!window.confirm(`Estimasi: ${quote.estimated_credits.toLocaleString("id-ID")} AI Credits. Model: ${quote.model_id}. Knowledge sources: ${quote.knowledge_source_count || 0}. Pembayar: ${quote.payer_role || "akun sendiri"}. Lanjutkan dan reservasi kredit?`)) {
        setNotice("Dibatalkan sebelum reservasi. Tidak ada kredit yang dipotong.");
        return null;
      }
      const createResponse = await fetch(apiBase + "/v1/generation/jobs", {
        method: "POST", headers: { ...headers, "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ ...body, quoted_credits: quote.estimated_credits, quoted_policy_version: quote.policy_version, quoted_tariff_version: quote.tariff_version, quoted_model_id: quote.model_id, quoted_agent_snapshot_sha256: quote.agent_snapshot_sha256, quoted_skill_snapshot_sha256: quote.skill_snapshot_sha256, ...(quote.knowledge_context_sha256 ? { quoted_knowledge_context_sha256: quote.knowledge_context_sha256 } : {}) }), cache: "no-store",
      });
      if (!createResponse.ok) throw new Error(await errorMessage(createResponse));
      const created = await createResponse.json() as { job_id: string };
      if (!created.job_id) throw new Error("Generation Job belum dikonfirmasi.");
      setJobId(created.job_id);
      for (let attempt = 0; attempt < 60; attempt += 1) {
        await wait(2000);
        const statusResponse = await fetch(apiBase + `/v1/generation/jobs/${created.job_id}`, { headers: { Authorization: headers.Authorization, Accept: "application/json" }, cache: "no-store" });
        if (!statusResponse.ok) throw new Error(await errorMessage(statusResponse));
        const payload = await statusResponse.json() as { job?: Job };
        const job = payload.job;
        if (!job) throw new Error("Status generation tidak ditemukan.");
        if (job.dm_conversation_id) setDmConversationId(job.dm_conversation_id);
        if (job.status === "succeeded" && job.artifact_available) {
          const artifactResponse = await fetch(apiBase + `/v1/generation/jobs/${created.job_id}/artifact`, { headers: { Authorization: headers.Authorization, Accept: "application/json" }, cache: "no-store" });
          if (!artifactResponse.ok) throw new Error(await errorMessage(artifactResponse));
          const artifact = await artifactResponse.json() as { url?: string };
          if (!artifact.url) throw new Error("Artefak privat belum dapat diakses.");
          const outputResponse = await fetch(artifact.url, { cache: "no-store" });
          if (!outputResponse.ok) throw new Error("Unduhan artefak generation gagal.");
          const outputText = await outputResponse.text();
          setResult(outputText);
          setNotice("Hasil lolos moderasi dan tersimpan sebagai artefak privat. Creator reward: " + (job.owner_reward_status || "pending_policy") + ". DM delivery dikonfirmasi oleh backend.");
          return outputText;
        }
        if (job.status === "failed" || job.status === "cancelled") throw new Error(job.error_code || "Generation gagal.");
        if (job.status === "pending_reconciliation") throw new Error("Outcome provider belum pasti. Job masuk rekonsiliasi dan tidak diulang otomatis.");
      }
      setNotice("Job masih berjalan. Periksa kembali melalui riwayat Generation; permintaan tidak dikirim ulang.");
      return null;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Generation tidak dapat diselesaikan.");
      throw cause;
    } finally { setBusy(false); }
  }

  async function deleteArtifact(): Promise<void> {
    if (!session || !jobId || artifactDeleting) throw new Error("Artefak privat tidak tersedia untuk dihapus.");
    setArtifactDeleting(true); setError("");
    try {
      const response = await fetch(apiBase + "/v1/generation/jobs/" + encodeURIComponent(jobId) + "/artifact", {
        method: "DELETE",
        headers: { Authorization: "Bearer " + session.access_token, Accept: "application/json", "Idempotency-Key": crypto.randomUUID() },
        cache: "no-store",
      });
      if (!response.ok) throw new Error(await errorMessage(response));
      const payload = await response.json() as { status?: string };
      setResult("");
      setDmConversationId("");
      setNotice(payload.status === "succeeded"
        ? "Artefak privat sudah dihapus."
        : "Permintaan penghapusan diterima. Akses artefak langsung dinonaktifkan; pembersihan Storage berjalan asinkron.");
    } finally { setArtifactDeleting(false); }
  }

  const selectedExternalAgent = externalAgents.find(item => item.consumer_grant_id === consumerGrantId && item.agent.id === agentId);
  const externalKnowledgeAllowed = !!selectedExternalAgent?.granted_scopes.includes("knowledge_public_read");

  if (!session) return <main className="mx-auto max-w-2xl p-6"><h1 className="text-xl font-black">Generate Content</h1><p className="mt-2 text-sm text-slate-600">Masuk ke Allpha untuk menggunakan Agent dan AI Credits.</p><Link href="/login" className="mt-4 inline-flex rounded-xl bg-slate-950 px-4 py-2 text-white">Masuk</Link></main>;
  return <main className="mx-auto min-h-screen max-w-3xl px-4 py-8 text-slate-950 dark:text-slate-100">
    <header className="mb-6 flex items-center justify-between gap-3">
      <div><p className="text-xs font-black uppercase tracking-[.18em] text-violet-600">Allpha Creator Studio</p><h1 className="mt-1 text-2xl font-black">Generate Content</h1><p className="mt-1 text-sm text-slate-500">Pilih Agent, Skill dan capability yang benar-benar aktif sebelum meminta generation.</p></div>
      <Link href="/feed" className="rounded-xl border border-slate-300 px-3 py-2 text-sm font-bold dark:border-slate-700">Kembali</Link>
    </header>
    <section className="rounded-3xl border-2 border-slate-900 bg-white p-5 shadow-[4px_4px_0px_#0f172a] dark:bg-slate-900 dark:text-white">
      {loading ? <p role="status" className="text-sm">Memuat Agent kanonis…</p> : <>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="text-sm font-bold">AI Agent<select value={agentId + "::" + consumerGrantId} onChange={event => { const [id, grant] = event.target.value.split("::"); setAgentId(id); setConsumerGrantId(grant || ""); if (grant) setKnowledgeQuery(""); }} className="mt-2 w-full rounded-xl border border-slate-300 bg-transparent p-3 dark:border-slate-700"><option value="::">Pilih Agent</option>{agents.map(agent => <option key={agent.id} value={agent.id + "::"}>{agent.display_name} · Milik saya</option>)}{externalAgents.map(item => <option key={item.consumer_grant_id} value={item.agent.id + "::" + item.consumer_grant_id}>{item.agent.display_name} · Grant pemilik</option>)}</select></label>
          <label className="text-sm font-bold">Skill published<select value={skillId} onChange={event => setSkillId(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 bg-transparent p-3 dark:border-slate-700"><option value="">Pilih Skill</option>{skills.map(skill => <option key={skill.id} value={skill.id}>{skill.display_name || skill.name || `Skill v${skill.version}`}</option>)}</select></label>
        </div>
        <label className="mt-4 block text-sm font-bold">Capability approved<select value={capabilityId} onChange={event => setCapabilityId(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 bg-transparent p-3 dark:border-slate-700"><option value="">Pilih capability</option>{capabilities.map(item => <option key={item.capability_key} value={item.capability_key}>{item.capability_key}</option>)}</select></label>
        <div className="mt-4 rounded-2xl border-2 border-slate-900 bg-violet-50 p-4 shadow-[2px_2px_0px_#0f172a]">
          <p className="text-sm font-black text-slate-950">AI Content & Reels Studio</p>
          <p className="mt-1 text-xs font-medium text-slate-600">Gunakan komponen GenerateModal dari repository referensi. Brief, brand, dan format konten akan dikirim ke Generation Job melalui quote dan Model Router kanonis.</p>
          <button type="button" onClick={() => setGeneratorOpen(true)} disabled={busy || loading || !agentId || !skillId || !capabilityId} className="mt-3 rounded-xl border-2 border-slate-900 bg-purple-300 px-5 py-3 text-sm font-black text-slate-950 shadow-[2px_2px_0px_#0f172a] disabled:opacity-50">Buka AI Content & Reels Studio</button>
        </div>
        <label className="mt-4 block text-sm font-bold">Knowledge context (opsional)<textarea value={knowledgeQuery} onChange={event => setKnowledgeQuery(event.target.value)} disabled={!!consumerGrantId && !externalKnowledgeAllowed} rows={3} maxLength={4000} placeholder={consumerGrantId && !externalKnowledgeAllowed ? "Owner belum memberikan scope Knowledge publik." : "Cari sumber Knowledge yang boleh digunakan…"} className="mt-2 w-full rounded-xl border border-slate-300 bg-transparent p-3 text-sm font-normal disabled:opacity-50 dark:border-slate-700" /><span className="mt-1 block text-xs font-normal text-slate-500">Agent sendiri: retrieval mengikuti consent dan ACL pemilik. Agent eksternal: hanya chunk ber-sensitivity public, ready, version-matched, dan grant knowledge_public_read; data privat tidak pernah diambil.</span></label>
        <p className="mt-4 text-xs text-slate-500">Quote dan tarif selalu berasal dari policy aktif. Tidak ada harga default atau kredit buatan.</p>
      </>}
    </section>
    {error && <p role="alert" className="mt-4 rounded-xl border border-rose-300 bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
    {notice && <p role="status" className="mt-4 rounded-xl border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900">{notice}</p>}
    {jobId && <p className="mt-3 text-xs text-slate-500">Generation Job: {jobId}</p>}
    {result && <section className="mt-5 rounded-3xl border-2 border-slate-900 bg-slate-950 p-5 text-cyan-100 shadow-[4px_4px_0px_#0f172a]"><div className="mb-3 flex items-center justify-between"><h2 className="font-black">Hasil Generation</h2><button onClick={() => void navigator.clipboard.writeText(result)} className="rounded-lg border border-cyan-200/50 px-3 py-1.5 text-xs font-bold">Salin</button></div><pre className="whitespace-pre-wrap break-words text-sm leading-relaxed">{result}</pre><p className="mt-4 border-t border-white/10 pt-3 text-xs text-cyan-200/70">Hasil tersimpan privat pada Generation Job. DM delivery dan creator reward tetap mengikuti policy WP-07 yang disetujui.</p></section>}
    <GenerateModal
      isOpen={generatorOpen}
      onClose={() => setGeneratorOpen(false)}
      onGenerate={generate}
      directMessageAvailable={!!dmConversationId}
      artifactDeleteAvailable={!!jobId && !!result}
      artifactDeleting={artifactDeleting}
      onDeleteArtifact={deleteArtifact}
      onOpenDirectMessage={() => {
        if (!dmConversationId) return;
        window.location.assign("/messages?conversation_id=" + encodeURIComponent(dmConversationId));
      }}
    />
  </main>;
}

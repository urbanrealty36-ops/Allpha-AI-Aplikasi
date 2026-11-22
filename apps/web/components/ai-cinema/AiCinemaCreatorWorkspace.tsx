"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { getBrowserSupabase } from "@/lib/supabase";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");

type DraftTitle = {
  id: string;
  title: string;
  genre: string;
  synopsis: string;
  status: string;
  updated_at?: string;
  version: number;
};
type DraftEpisode = {
  id: string;
  episode_number: number;
  title: string;
  synopsis: string;
  status: string;
  duration_seconds?: number | null;
};
type CreatorStatus = { generation: string; generation_jobs: string; billing: string; playback_entitlement: string; generation_reason?: string | null; billing_reason?: string | null; entitlement_reason?: string | null };
type RuntimeSkillChoice = { id: string; version: number; name?: string | null; display_name?: string | null; generation_compatible: boolean; generation_block_reason?: string | null };
type RuntimeAgentChoice = { agent: { id: string; version: number; display_name: string; description?: string; visibility?: string; disclosure?: string }; skills: RuntimeSkillChoice[]; capabilities: { capability_key: string }[] };
type GenerationRequestPayload = { agent_id: string; skill_id: string; capability_id: string; prompt: string; max_output_tokens: number };
type GenerationQuote = { expires_at: string; estimated_credits: number; estimated_usage_units: number; usage_unit: string; provider_id: string; model_id: string; model_version: string; policy_version: string; tariff_version: string; entitlement_version: string; knowledge_context_sha256?: string | null; agent_snapshot_sha256: string; skill_snapshot_sha256: string; tool_inputs_sha256: string; request: GenerationRequestPayload };
type GenerationJob = { id: string; task_id?: string; status: string; moderation_status?: string; artifact_available?: boolean; error_code?: string | null; input_tokens?: number; output_tokens?: number };
type ReadyMedia = { id: string; filename: string; media_type: string; size_bytes: number };
type CreatorMedia = ReadyMedia & { status: string; scan_status: string; processed_at?: string | null; created_at: string };
type CinemaCollaborator = { id: string; collaborator_user_id?: string | null; collaborator_agent_id?: string | null; role: string; permissions: string[]; status: string };
type CinemaInvitation = { id: string; title?: { title: string; status: string } | null; role: string; permissions: string[]; status: string };
type CinemaCredit = { id: string; contributor_type: string; role: string; attribution_label: string };
type CinemaVersion = { id: string; version: number; created_at: string };
type CinemaAsset = { id: string; media_id: string; asset_role: string; display_name: string; media?: { filename?: string; media_type?: string; status?: string; preview_url?: string } };
type CinemaProductionResponse = { title_id: string; version: number; status: string; document: Record<string, unknown> };
type CinemaReadiness = { status: "ready" | "not_ready"; can_create_generation_job: boolean; checks: Record<string, string>; message: string };
const EMPTY_CINEMA_PRODUCTION = {
  schema_version: 1,
  screenplay: { logline: "", synopsis: "", draft: "" },
  storyboard: [],
  scenes: [],
  timeline: { tracks: [] },
  audio_tracks: [],
  export_profile: { container: "mp4", resolution: "1080p", frame_rate: 24, aspect_ratio: "16:9" },
};


async function authorizedRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const supabase = getBrowserSupabase();
  if (!supabase) throw new Error("Autentikasi belum dikonfigurasi pada aplikasi.");
  const { data, error } = await supabase.auth.getSession();
  if (error || !data.session?.access_token) throw new Error("Silakan masuk kembali untuk mengelola draft Creator Studio.");
  const response = await fetch(API_BASE + path, {
    ...init,
    cache: "no-store",
    headers: {
      Accept: "application/json",
      ...(init.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
      Authorization: `Bearer ${data.session.access_token}`, 
      ...init.headers,
    },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = body?.detail?.message || body?.message || "Permintaan Creator Studio gagal.";
    throw new Error(message);
  }
  return body as T;
}

export default function AiCinemaCreatorWorkspace() {
  const [titles, setTitles] = useState<DraftTitle[]>([]);
  const [capabilityStatus, setCapabilityStatus] = useState<CreatorStatus | null>(null);
  const [productionReadiness, setProductionReadiness] = useState<CinemaReadiness | null>(null);
  const [readinessLoading, setReadinessLoading] = useState(false);
  const [episodes, setEpisodes] = useState<DraftEpisode[]>([]);
  const [readyMedia, setReadyMedia] = useState<ReadyMedia[]>([]);
  const [creatorMedia, setCreatorMedia] = useState<CreatorMedia[]>([]);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadDraftId, setUploadDraftId] = useState("");
  const [uploadIdempotencyKey, setUploadIdempotencyKey] = useState("");
  const [selectedMediaId, setSelectedMediaId] = useState("");
  const [selectedTitleId, setSelectedTitleId] = useState("");
  const [title, setTitle] = useState("");
  const [genre, setGenre] = useState("c_drama");
  const [synopsis, setSynopsis] = useState("");
  const [episodeTitle, setEpisodeTitle] = useState("");
  const [episodeSynopsis, setEpisodeSynopsis] = useState("");
  const [episodeNumber, setEpisodeNumber] = useState("1");
  const [rightsConfirmed, setRightsConfirmed] = useState(false);
  const [aiDisclosureConfirmed, setAiDisclosureConfirmed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [collaboratorUserId, setCollaboratorUserId] = useState("");
  const [collaboratorRole, setCollaboratorRole] = useState("Editor");
  const [collaboratorPermissions, setCollaboratorPermissions] = useState<string[]>(["edit_metadata","upload_episodes"]);
  const [collaborators, setCollaborators] = useState<CinemaCollaborator[]>([]);
  const [invitations, setInvitations] = useState<CinemaInvitation[]>([]);
  const [credits, setCredits] = useState<CinemaCredit[]>([]);
  const [creditType, setCreditType] = useState("human");
  const [creditAgentId, setCreditAgentId] = useState("");
  const [creditRole, setCreditRole] = useState("Creator");
  const [creditLabel, setCreditLabel] = useState("Kontribusi kreator");
  const [versions, setVersions] = useState<CinemaVersion[]>([]);
  const [productionVersion, setProductionVersion] = useState(1);
  const [productionJson, setProductionJson] = useState(JSON.stringify(EMPTY_CINEMA_PRODUCTION, null, 2));
  const [productionAssets, setProductionAssets] = useState<CinemaAsset[]>([]);
  const [assetRole, setAssetRole] = useState("reference");
  const [productionLoading, setProductionLoading] = useState(false);

  const [runtimeAgents, setRuntimeAgents] = useState<RuntimeAgentChoice[]>([]);
  const [runtimeAgentsState, setRuntimeAgentsState] = useState<"idle" | "loading" | "ready" | "unavailable">("idle");
  const [generationAgentId, setGenerationAgentId] = useState("");
  const [generationSkillId, setGenerationSkillId] = useState("");
  const [generationCapabilityId, setGenerationCapabilityId] = useState("");
  const [generationPrompt, setGenerationPrompt] = useState("");
  const [generationQuote, setGenerationQuote] = useState<GenerationQuote | null>(null);
  const [generationIdempotencyKey, setGenerationIdempotencyKey] = useState("");
  const [generationJobId, setGenerationJobId] = useState("");
  const [generationJob, setGenerationJob] = useState<GenerationJob | null>(null);
  const [generationArtifactText, setGenerationArtifactText] = useState("");
  const [generationBusy, setGenerationBusy] = useState(false);

  const loadCapabilityStatus = useCallback(async () => {
    setReadinessLoading(true);
    try {
      const [status, readiness] = await Promise.all([
        authorizedRequest<CreatorStatus>("/v1/cinema/creator/status"),
        authorizedRequest<CinemaReadiness>("/v1/cinema/creator/production-readiness"),
      ]);
      setCapabilityStatus(status);
      setProductionReadiness(readiness);
    } catch {
      setCapabilityStatus(null);
      setProductionReadiness(null);
    } finally {
      setReadinessLoading(false);
    }
  }, []);

  const loadRuntimeAgents = useCallback(async () => {
    setRuntimeAgentsState("loading");
    try {
      const result = await authorizedRequest<{ items: RuntimeAgentChoice[] }>("/v1/agent-runtime/agents");
      const items = Array.isArray(result.items) ? result.items : [];
      setRuntimeAgents(items);
      setGenerationAgentId(current => items.some(item => item.agent.id === current) ? current : items[0]?.agent.id ?? "");
      setRuntimeAgentsState("ready");
    } catch {
      setRuntimeAgents([]);
      setRuntimeAgentsState("unavailable");
    }
  }, []);

  useEffect(() => {
    if (productionReadiness?.can_create_generation_job === true
        && capabilityStatus?.generation === "configured"
        && capabilityStatus.generation_jobs === "available"
        && capabilityStatus.billing === "available") {
      void loadRuntimeAgents();
    } else {
      setRuntimeAgents([]);
      setRuntimeAgentsState("idle");
      setGenerationQuote(null);
    }
  }, [capabilityStatus, productionReadiness, loadRuntimeAgents]);

  useEffect(() => {
    const selected = runtimeAgents.find(item => item.agent.id === generationAgentId);
    const compatibleSkills = (selected?.skills || []).filter(skill => skill.generation_compatible);
    setGenerationSkillId(current => compatibleSkills.some(skill => skill.id === current) ? current : compatibleSkills[0]?.id ?? "");
    const capabilities = selected?.capabilities || [];
    setGenerationCapabilityId(current => capabilities.some(item => item.capability_key === current) ? current : capabilities[0]?.capability_key ?? "");
    setGenerationQuote(null);
  }, [runtimeAgents, generationAgentId]);

  const loadCreatorMedia = useCallback(async () => {
    try {
      const result = await authorizedRequest<{ items: CreatorMedia[] }>("/v1/cinema/creator/media");
      const rows = Array.isArray(result.items) ? result.items : [];
      setCreatorMedia(rows);
      setReadyMedia(rows.filter(item => item.status === "ready" && item.scan_status === "clean" && item.processed_at).map(({ id, filename, media_type, size_bytes }) => ({ id, filename, media_type, size_bytes })));
    } catch {
      setCreatorMedia([]); setReadyMedia([]);
    }
  }, []);

  const loadReadyMedia = useCallback(async () => { await loadCreatorMedia(); }, [loadCreatorMedia]);

  const loadTitles = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await authorizedRequest<{ items: DraftTitle[] }>("/v1/cinema/creator/titles");
      const rows = Array.isArray(result.items) ? result.items : [];
      setTitles(rows);
      setSelectedTitleId(current => rows.some(row => row.id === current) ? current : rows[0]?.id ?? "");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Draft film tidak dapat dimuat.");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadEpisodes = useCallback(async (titleId: string) => {
    if (!titleId) { setEpisodes([]); return; }
    try {
      const result = await authorizedRequest<{ items: DraftEpisode[] }>(`/v1/cinema/creator/titles/${encodeURIComponent(titleId)}/episodes`);
      setEpisodes(Array.isArray(result.items) ? result.items : []);
    } catch (cause) {
      setEpisodes([]);
      setError(cause instanceof Error ? cause.message : "Episode tidak dapat dimuat.");
    }
  }, []);

  useEffect(() => { void loadTitles(); }, [loadTitles]);
  useEffect(() => { void loadReadyMedia(); }, [loadReadyMedia]);
  useEffect(() => { void loadCapabilityStatus(); }, [loadCapabilityStatus]);
  useEffect(() => { void loadEpisodes(selectedTitleId); }, [loadEpisodes, selectedTitleId]);

  const loadCreatorGovernance = useCallback(async () => {
    try {
      const inbox = await authorizedRequest<{items:CinemaInvitation[]}>("/v1/cinema/creator/collaborations");
      setInvitations(Array.isArray(inbox.items)?inbox.items:[]);
      if (!selectedTitleId) { setCollaborators([]); setCredits([]); setVersions([]); return; }
      const base = "/v1/cinema/creator/titles/" + encodeURIComponent(selectedTitleId);
      const [collabData,creditData,versionData]=await Promise.all([
        authorizedRequest<{items:CinemaCollaborator[]}>(base+"/collaborators"),
        authorizedRequest<{items:CinemaCredit[]}>(base+"/credits"),
        authorizedRequest<{items:CinemaVersion[]}>(base+"/versions"),
      ]);
      setCollaborators(collabData.items||[]); setCredits(creditData.items||[]); setVersions(versionData.items||[]);
    } catch (cause) {
      setError(cause instanceof Error?cause.message:"Data kolaborasi Creator Studio belum dapat dimuat.");
    }
  },[selectedTitleId]);

  useEffect(()=>{ void loadCreatorGovernance(); },[loadCreatorGovernance]);

  async function inviteCollaborator(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if(!selectedTitleId||!collaboratorUserId.trim())return;
    setSaving(true);setError("");setNotice("");
    try{
      await authorizedRequest("/v1/cinema/creator/titles/"+encodeURIComponent(selectedTitleId)+"/collaborators",{
        method:"POST",body:JSON.stringify({collaborator_user_id:collaboratorUserId.trim(),role:collaboratorRole,permissions:collaboratorPermissions}),
      });
      setCollaboratorUserId("");setNotice("Undangan collaborator dikirim dan menunggu persetujuan penerima.");await loadCreatorGovernance();
    }catch(cause){setError(cause instanceof Error?cause.message:"Undangan collaborator gagal dibuat.");}
    finally{setSaving(false);}
  }

  async function decideCollaboration(id:string,decision:"accept"|"revoke") {
    setSaving(true);setError("");setNotice("");
    try{
      await authorizedRequest("/v1/cinema/creator/collaborations/"+encodeURIComponent(id)+"/decision",{
        method:"POST",body:JSON.stringify({decision}),
      });
      setNotice(decision==="accept"?"Undangan kolaborasi diterima.":"Akses kolaborasi dicabut.");await loadCreatorGovernance();
    }catch(cause){setError(cause instanceof Error?cause.message:"Perubahan kolaborasi gagal.");}
    finally{setSaving(false);}
  }

  async function addCreatorCredit(event:FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if(!selectedTitleId)return;
    setSaving(true);setError("");setNotice("");
    try{
      await authorizedRequest("/v1/cinema/creator/titles/"+encodeURIComponent(selectedTitleId)+"/credits",{
        method:"POST",body:JSON.stringify({contributor_type:creditType,contributor_agent_id:creditType==="agent"?creditAgentId.trim():null,role:creditRole,attribution_label:creditLabel,disclosure:"Kontribusi AI/Human dicatat oleh Creator Studio"}),
      });
      setCreditAgentId("");setNotice("Kredit kontributor tersimpan.");await loadCreatorGovernance();
    }catch(cause){setError(cause instanceof Error?cause.message:"Kredit kontributor gagal disimpan.");}
    finally{setSaving(false);}
  }

  async function snapshotVersion() {
    if(!selectedTitleId)return;
    setSaving(true);setError("");setNotice("");
    try{
      await authorizedRequest("/v1/cinema/creator/titles/"+encodeURIComponent(selectedTitleId)+"/versions",{method:"POST",body:"{}"});
      setNotice("Snapshot versi film tersimpan.");await loadCreatorGovernance();
    }catch(cause){setError(cause instanceof Error?cause.message:"Snapshot versi gagal dibuat.");}
    finally{setSaving(false);}
  }




  const loadCinemaProduction = useCallback(async (titleId: string) => {
    if (!titleId) {
      setProductionVersion(1);
      setProductionJson(JSON.stringify(EMPTY_CINEMA_PRODUCTION, null, 2));
      setProductionAssets([]);
      return;
    }
    setProductionLoading(true);
    try {
      const [production, assets] = await Promise.all([
        authorizedRequest<CinemaProductionResponse>(`/v1/cinema/creator/titles/${encodeURIComponent(titleId)}/production`),
        authorizedRequest<{ items: CinemaAsset[] }>(`/v1/cinema/creator/titles/${encodeURIComponent(titleId)}/assets`),
      ]);
      setProductionVersion(production.version);
      setProductionJson(JSON.stringify(production.document, null, 2));
      setProductionAssets(Array.isArray(assets.items) ? assets.items : []);
    } catch (cause) {
      setProductionAssets([]);
      setError(cause instanceof Error ? cause.message : "Production workspace belum dapat dimuat.");
    } finally {
      setProductionLoading(false);
    }
  }, []);

  useEffect(() => { void loadCinemaProduction(selectedTitleId); }, [loadCinemaProduction, selectedTitleId]);

  async function saveCinemaProduction() {
    if (!selectedTitleId) return;
    setSaving(true); setError(""); setNotice("");
    try {
      const document = JSON.parse(productionJson) as Record<string, unknown>;
      const result = await authorizedRequest<{ item: { version: number } }>(
        `/v1/cinema/creator/titles/${encodeURIComponent(selectedTitleId)}/production`,
        { method: "PUT", body: JSON.stringify({ expected_version: productionVersion, document }) },
      );
      setProductionVersion(result.item.version);
      setNotice("Screenplay, storyboard, scene, timeline, audio, dan export profile tersimpan pada versi produksi baru.");
      await loadCinemaProduction(selectedTitleId);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Production document gagal disimpan.");
    } finally { setSaving(false); }
  }

  async function attachCinemaAsset() {
    if (!selectedTitleId || !selectedMediaId) return;
    const media = readyMedia.find(item => item.id === selectedMediaId);
    if (!media) return;
    setSaving(true); setError(""); setNotice("");
    try {
      await authorizedRequest(
        `/v1/cinema/creator/titles/${encodeURIComponent(selectedTitleId)}/assets`,
        { method: "POST", body: JSON.stringify({
          media_id: selectedMediaId, asset_role: assetRole, display_name: media.filename,
        }) },
      );
      setNotice("Media siap pakai ditautkan ke Asset Library film.");
      await loadCinemaProduction(selectedTitleId);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Asset gagal ditautkan ke film.");
    } finally { setSaving(false); }
  }

  async function removeCinemaAsset(assetId: string) {
    if (!selectedTitleId) return;
    setSaving(true); setError(""); setNotice("");
    try {
      await authorizedRequest(
        `/v1/cinema/creator/titles/${encodeURIComponent(selectedTitleId)}/assets/${encodeURIComponent(assetId)}`,
        { method: "DELETE" },
      );
      setNotice("Tautan asset dilepas dari film; file asli tetap berada di Content Media.");
      await loadCinemaProduction(selectedTitleId);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Tautan asset gagal dilepas.");
    } finally { setSaving(false); }
  }

  const selectedRuntimeAgent = runtimeAgents.find(item => item.agent.id === generationAgentId);
  const selectedRuntimeSkill = selectedRuntimeAgent?.skills.find(item => item.id === generationSkillId && item.generation_compatible);

  async function quoteCinemaGeneration() {
    if (!selectedRuntimeAgent || !selectedRuntimeSkill || !generationCapabilityId || !generationPrompt.trim()) return;
    setGenerationBusy(true); setError(""); setNotice(""); setGenerationJob(null); setGenerationJobId(""); setGenerationArtifactText("");
    try {
      const payload: GenerationRequestPayload = {
        agent_id: selectedRuntimeAgent.agent.id,
        skill_id: selectedRuntimeSkill.id,
        capability_id: generationCapabilityId,
        prompt: generationPrompt.trim(),
        max_output_tokens: 2048,
      };
      const quote = await authorizedRequest<Omit<GenerationQuote, "request">>("/v1/generation/quote", {
        method: "POST", body: JSON.stringify(payload),
      });
      setGenerationQuote({ ...quote, request: payload });
      setGenerationIdempotencyKey(crypto.randomUUID());
      setNotice("Estimasi AI Credits berhasil dihitung. Periksa biaya dan masa berlaku sebelum menjalankan generation.");
    } catch (cause) {
      setGenerationQuote(null);
      setError(cause instanceof Error ? cause.message : "Quote AI Cinema tidak tersedia.");
    } finally { setGenerationBusy(false); }
  }

  async function startCinemaGeneration() {
    if (!generationQuote || new Date(generationQuote.expires_at).getTime() <= Date.now()) {
      setGenerationQuote(null);
      setError("Quote sudah kedaluwarsa. Hitung ulang estimasi sebelum menjalankan generation.");
      return;
    }
    const currentRequest = generationQuote.request;
    if (currentRequest.prompt !== generationPrompt.trim()
        || currentRequest.agent_id !== generationAgentId
        || currentRequest.skill_id !== generationSkillId
        || currentRequest.capability_id !== generationCapabilityId) {
      setGenerationQuote(null);
      setError("Pilihan Agent, Skill, Capability atau prompt berubah. Hitung ulang quote.");
      return;
    }
    setGenerationBusy(true); setError(""); setNotice("");
    try {
      const body: Record<string, unknown> = {
        ...currentRequest,
        quoted_credits: generationQuote.estimated_credits,
        quoted_policy_version: generationQuote.policy_version,
        quoted_tariff_version: generationQuote.tariff_version,
        quoted_model_id: generationQuote.model_id,
        quoted_agent_snapshot_sha256: generationQuote.agent_snapshot_sha256,
        quoted_skill_snapshot_sha256: generationQuote.skill_snapshot_sha256,
        quoted_tool_inputs_sha256: generationQuote.tool_inputs_sha256,
      };
      if (generationQuote.knowledge_context_sha256) body.quoted_knowledge_context_sha256 = generationQuote.knowledge_context_sha256;
      if (!selectedTitleId) throw new Error("Pilih draft film sebelum menjalankan generation.");
      const created = await authorizedRequest<{ job_id: string; status: string; reserved_credits: number }>(
        "/v1/cinema/creator/titles/" + encodeURIComponent(selectedTitleId) + "/generation-jobs",
        {
          method: "POST",
          headers: { "Idempotency-Key": generationIdempotencyKey || crypto.randomUUID() },
          body: JSON.stringify({ ...body, target_section: "screenplay" }),
        },
      );
      setGenerationJobId(created.job_id);
      setGenerationJob({ id: created.job_id, status: created.status });
      setGenerationQuote(null);
      setGenerationIdempotencyKey("");
      setNotice("Generation Job dibuat melalui Agent Runtime dan AI Credit reservation. Output menunggu proses dan moderation.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Generation Job AI Cinema gagal dibuat.");
    } finally { setGenerationBusy(false); }
  }

  useEffect(() => {
    if (!generationJobId) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const result = await authorizedRequest<{ job: GenerationJob }>(`/v1/cinema/creator/titles/${encodeURIComponent(selectedTitleId)}/generation-jobs/${encodeURIComponent(generationJobId)}`);
        if (!active) return;
        setGenerationJob(result.job);
        if (result.job.status === "succeeded" && result.job.artifact_available) {
          const artifact = await authorizedRequest<{ url: string }>(`/v1/cinema/creator/titles/${encodeURIComponent(selectedTitleId)}/generation-jobs/${encodeURIComponent(generationJobId)}/artifact`);
          const response = await fetch(artifact.url, { cache: "no-store" });
          if (!response.ok) throw new Error("Artefak generation privat tidak dapat diambil.");
          const output = await response.text();
          if (active) setGenerationArtifactText(output.slice(0, 100000));
          return;
        }
        if (["failed", "cancelled", "pending_reconciliation", "succeeded"].includes(result.job.status)) return;
        timer = setTimeout(poll, 4000);
      } catch (cause) {
        if (!active) return;
        setError(cause instanceof Error ? cause.message : "Status Generation Job belum dapat dimuat.");
        timer = setTimeout(poll, 8000);
      }
    };
    void poll();
    return () => { active = false; if (timer) clearTimeout(timer); };
  }, [generationJobId, selectedTitleId]);

  async function applyCinemaGeneration() {
    if (!selectedTitleId || !generationJobId || generationJob?.status !== "succeeded" || generationJob.moderation_status !== "approved") return;
    setGenerationBusy(true); setError(""); setNotice("");
    try {
      const result = await authorizedRequest<{ outcome: "applied" | "replayed"; title_version: number }>(
        `/v1/cinema/creator/titles/${encodeURIComponent(selectedTitleId)}/generation-jobs/${encodeURIComponent(generationJobId)}/apply`,
        { method: "POST", body: JSON.stringify({ expected_version: productionVersion }) },
      );
      setNotice(result.outcome === "replayed"
        ? "Hasil generation ini sudah pernah diterapkan pada versi screenplay tersebut."
        : "Hasil generation yang lolos moderation berhasil diterapkan ke screenplay Cinema.");
      await loadCinemaProduction(selectedTitleId);
      await loadTitles();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Hasil generation gagal diterapkan ke screenplay.");
    } finally { setGenerationBusy(false); }
  }

  async function cancelCinemaGeneration() {
    if (!generationJobId || generationJob?.status !== "queued") return;
    setGenerationBusy(true); setError(""); setNotice("");
    try {
      await authorizedRequest(`/v1/cinema/creator/titles/${encodeURIComponent(selectedTitleId)}/generation-jobs/${encodeURIComponent(generationJobId)}/cancel`, { method: "POST" });
      setGenerationJob(current => current ? { ...current, status: "cancelled" } : current);
      setNotice("Generation Job yang belum diproses berhasil diminta pembatalannya.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Generation Job tidak dapat dibatalkan.");
    } finally { setGenerationBusy(false); }
  }

  async function uploadCinemaMedia() {
    if (!uploadFile || !uploadFile.type.startsWith("video/")) { setError("Pilih file video MP4 atau WebM terlebih dahulu."); return; }
    if (uploadFile.size <= 0 || uploadFile.size > 50 * 1024 * 1024) { setError("Ukuran video harus lebih dari 0 dan maksimal 50 MiB."); return; }
    setSaving(true); setError(""); setNotice("");
    try {
      let contentId = uploadDraftId;
      if (!contentId) {
        const draft = await authorizedRequest<{ item: { id: string } }>("/v1/content", { method: "POST", body: JSON.stringify({ body: "", visibility: "private", content_type: "video" }) });
        contentId = draft.item.id; setUploadDraftId(contentId);
      }
      const idempotencyKey = uploadIdempotencyKey || crypto.randomUUID();
      setUploadIdempotencyKey(idempotencyKey);
      const form = new FormData(); form.append("file", uploadFile);
      const uploaded = await authorizedRequest<{ item: CreatorMedia }>("/v1/content/" + encodeURIComponent(contentId) + "/media", { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body: form });
      setUploadFile(null); setUploadDraftId(""); setUploadIdempotencyKey("");
      setNotice("Video diterima pipeline media Allpha (" + (uploaded.item?.status || "uploaded") + "). Tunggu pemindaian dan transcode; video dapat dipilih setelah status ready dan scan clean.");
      await loadCreatorMedia();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Upload video AI Cinema gagal."); }
    finally { setSaving(false); }
  }

  async function createTitle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true); setError(""); setNotice("");
    try {
      const result = await authorizedRequest<{ item: DraftTitle }>("/v1/cinema/creator/titles", {
        method: "POST",
        body: JSON.stringify({ title: title.trim(), genre, synopsis: synopsis.trim(), language_code: "id" }),
      });
      setTitle(""); setSynopsis("");
      setTitles(current => [result.item, ...current.filter(item => item.id !== result.item.id)]);
      setSelectedTitleId(result.item.id);
      setNotice("Draft film tersimpan di akun Anda.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Draft film gagal disimpan.");
    } finally { setSaving(false); }
  }

  async function createEpisode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedTitleId) return;
    setSaving(true); setError(""); setNotice("");
    try {
      const result = await authorizedRequest<{ item: DraftEpisode }>(`/v1/cinema/creator/titles/${encodeURIComponent(selectedTitleId)}/episodes`, {
        method: "POST",
        body: JSON.stringify({ episode_number: Number(episodeNumber), title: episodeTitle.trim(), synopsis: episodeSynopsis.trim(), media_id: selectedMediaId || null }),
      });
      setEpisodes(current => [...current.filter(item => item.id !== result.item.id), result.item].sort((a,b) => a.episode_number-b.episode_number));
      setEpisodeNumber(String(Number(episodeNumber) + 1));
      setEpisodeTitle(""); setEpisodeSynopsis("");
      setNotice("Draft episode tersimpan.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Draft episode gagal disimpan.");
    } finally { setSaving(false); }
  }

  async function submitForReview() {
    const selected = titles.find(item => item.id === selectedTitleId);
    if (!selected || !rightsConfirmed || !aiDisclosureConfirmed) return;
    setSaving(true); setError(""); setNotice("");
    try {
      const result = await authorizedRequest<{ item: DraftTitle }>(`/v1/cinema/creator/titles/${encodeURIComponent(selectedTitleId)}/submit-review`, {
        method: "POST",
        body: JSON.stringify({ expected_version: selected.version, rights_confirmed: true, ai_disclosure_confirmed: true }),
      });
      setTitles(current => current.map(item => item.id === result.item.id ? result.item : item));
      setRightsConfirmed(false); setAiDisclosureConfirmed(false);
      setNotice("Film diajukan ke antrean rights review dan moderasi. Pengajuan bukan persetujuan atau publikasi.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Pengajuan review gagal.");
    } finally { setSaving(false); }
  }

  return (
    <section className="mx-auto my-8 w-full max-w-6xl rounded-3xl border-2 border-slate-900 bg-white p-5 text-slate-900 shadow-[3px_3px_0px_#0f172a] sm:p-7">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div><p className="text-xs font-bold uppercase tracking-[.2em] text-sky-700">Creator Workspace</p><h2 className="mt-1 text-2xl font-black">Draft Film & Episode</h2><p className="mt-1 text-sm text-slate-700">Draft disimpan melalui FastAPI dan hanya dapat diakses pemiliknya.</p></div>
        <button type="button" onClick={() => { void loadTitles(); void loadCapabilityStatus(); void loadCreatorMedia(); }} disabled={loading} className="rounded-xl border-2 border-slate-900 bg-slate-100 px-4 py-2 text-sm font-black text-slate-950 shadow-[2px_2px_0px_#0f172a] hover:bg-slate-200 disabled:opacity-50">{loading ? "Memuat…" : "Muat ulang"}</button>
      </div>
      <div className="mb-4 rounded-xl border-2 border-slate-900 bg-slate-50 p-3 text-xs text-slate-800" aria-live="polite">
        <div className="flex items-center justify-between gap-2"><p className="font-bold">Production readiness</p><button type="button" onClick={() => void loadCapabilityStatus()} disabled={readinessLoading} className="rounded-lg border border-slate-900 px-2 py-1 font-bold disabled:opacity-50">{readinessLoading ? "Memeriksa…" : "Periksa ulang"}</button></div>
        {!productionReadiness ? <p className="mt-1 text-rose-700">Status layanan belum dapat dikonfirmasi. Coba muat ulang.</p> : <>
          <p className="mt-1 font-semibold">{productionReadiness.message}</p>
          <div className="mt-2 flex flex-wrap gap-2">{Object.entries(productionReadiness.checks).map(([key,value])=><span key={key} className={"rounded-lg px-2 py-1 " + (value==="ready" ? "bg-emerald-100 text-emerald-800" : "bg-rose-100 text-rose-800")}>{key.replaceAll("_"," ")}: {value}</span>)}</div>
        </>}
      </div>
      {capabilityStatus && <div className="mb-4 rounded-xl border border-2 border-slate-900 bg-amber-50 p-3 text-xs text-amber-900">
        <p className="font-bold">Status layanan terhubung</p>
        <p className="mt-1">Generation: {capabilityStatus.generation} · Generation jobs: {capabilityStatus.generation_jobs} · Billing: {capabilityStatus.billing} · Playback entitlement: {capabilityStatus.playback_entitlement}</p>
        <p className="mt-1 text-amber-800">Generate, pembayaran, dan playback premium belum dapat digunakan sampai kontrak job, policy kredit, billing, dan entitlement tersedia.</p>
      </div>}
      {error && <p role="alert" className="mb-4 rounded-xl border border-2 border-slate-900 bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
      {notice && <p role="status" className="mb-4 rounded-xl border border-2 border-slate-900 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</p>}
      <section className="mb-6 space-y-3 rounded-2xl border-2 border-slate-900 bg-violet-50 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div><p className="text-xs font-black uppercase tracking-[.18em] text-violet-800">AI Cinema · Agent Runtime</p><h3 className="mt-1 text-lg font-black text-slate-950">AI Script & Story Development</h3><p className="mt-1 text-xs text-slate-700">Generate sinopsis, screenplay brief atau outline episode melalui Generation Jobs, Model Router, Memory policy dan AI Credit ledger. Output hanya dapat digunakan setelah moderation approved.</p></div>
          <span className="rounded-lg border-2 border-slate-900 bg-white px-3 py-1 text-xs font-bold text-slate-800">{capabilityStatus?.generation === "configured" && capabilityStatus.billing === "available" ? "Runtime tersedia menurut status API" : "Menunggu policy / entitlement"}</span>
        </div>
        {capabilityStatus?.generation !== "configured" || capabilityStatus.generation_jobs !== "available" || capabilityStatus.billing !== "available" ? (
          <p className="rounded-xl border border-2 border-slate-900 bg-amber-50 p-3 text-xs text-amber-900">Generation belum dapat dijalankan. FastAPI belum mengonfirmasi seluruh schema Generation Job, output moderation, Model Router, approved credit policy dan billing entitlement. UI tidak membuat job atau biaya palsu.</p>
        ) : (
          <>
            <div className="grid gap-3 md:grid-cols-3">
              <label className="block text-xs font-semibold text-slate-700">Agent milik Anda
                <select value={generationAgentId} onChange={event => { setGenerationAgentId(event.target.value); setGenerationQuote(null); }} className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-white p-3 text-sm text-slate-950">
                  {runtimeAgents.map(item => <option key={item.agent.id} value={item.agent.id}>{item.agent.display_name || item.agent.id}</option>)}
                </select>
              </label>
              <label className="block text-xs font-semibold text-slate-700">Published Skill
                <select value={generationSkillId} onChange={event => { setGenerationSkillId(event.target.value); setGenerationQuote(null); }} className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-white p-3 text-sm text-slate-950">
                  {(selectedRuntimeAgent?.skills || []).filter(skill => skill.generation_compatible).map(skill => <option key={skill.id} value={skill.id}>{skill.display_name || skill.name || skill.id} · v{skill.version}</option>)}
                </select>
              </label>
              <label className="block text-xs font-semibold text-slate-700">Approved Capability
                <select value={generationCapabilityId} onChange={event => { setGenerationCapabilityId(event.target.value); setGenerationQuote(null); }} className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-white p-3 text-sm text-slate-950">
                  {(selectedRuntimeAgent?.capabilities || []).map(capability => <option key={capability.capability_key} value={capability.capability_key}>{capability.capability_key}</option>)}
                </select>
              </label>
            </div>
            <label className="block text-xs font-semibold text-slate-700">Instruksi produksi
              <textarea value={generationPrompt} onChange={event => { setGenerationPrompt(event.target.value); setGenerationQuote(null); }} maxLength={12000} rows={4} placeholder="Buat screenplay outline 8 episode untuk drama misteri, lengkap dengan logline, karakter, konflik utama dan cliffhanger tiap episode." className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-white p-3 text-sm text-slate-950" />
            </label>
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={() => void quoteCinemaGeneration()} disabled={generationBusy || !selectedRuntimeAgent || !selectedRuntimeSkill || !generationCapabilityId || !generationPrompt.trim()} className="rounded-xl border-2 border-slate-900 bg-white px-4 py-2 text-sm font-black text-slate-950 shadow-[2px_2px_0px_#0f172a] disabled:opacity-40">Hitung AI Credits</button>
              <button type="button" onClick={() => void startCinemaGeneration()} disabled={generationBusy || !generationQuote} className="rounded-xl border-2 border-slate-900 bg-violet-300 px-4 py-2 text-sm font-black text-slate-950 shadow-[2px_2px_0px_#0f172a] disabled:opacity-40">Jalankan Generation</button>
              {generationJob?.status === "queued" && <button type="button" onClick={() => void cancelCinemaGeneration()} disabled={generationBusy} className="rounded-xl border-2 border-slate-900 bg-rose-100 px-4 py-2 text-sm font-bold text-rose-900 disabled:opacity-40">Batalkan antrean</button>}
            </div>
            {generationQuote && <p className="rounded-xl border border-2 border-slate-900 bg-white p-3 text-xs text-slate-800">Estimasi: <strong>{generationQuote.estimated_credits.toLocaleString("id-ID")} AI Credits</strong> · {generationQuote.estimated_usage_units.toLocaleString("id-ID")} {generationQuote.usage_unit} · {generationQuote.model_id} · berlaku sampai {new Date(generationQuote.expires_at).toLocaleString("id-ID")}. Quote akan diverifikasi ulang oleh FastAPI saat job dibuat.</p>}
            {generationJob && <div className="rounded-xl border border-2 border-slate-900 bg-white p-3 text-xs text-slate-800"><p><strong>Generation Job:</strong> {generationJob.id} · <strong>Status:</strong> {generationJob.status} · <strong>Moderation:</strong> {generationJob.moderation_status || "menunggu hasil"}</p>{generationJob.error_code && <p className="mt-1 text-rose-800">Error: {generationJob.error_code}</p>}{generationJob.status === "succeeded" && !generationJob.artifact_available && <p className="mt-1 text-amber-800">Output belum dapat diakses sampai moderation menyetujui artefak privat.</p>}</div>}
            {generationArtifactText && <div className="space-y-2 rounded-xl border border-2 border-slate-900 bg-white p-3"><p className="text-xs font-bold text-emerald-800">Artefak teks tersedia · moderation approved</p><pre className="max-h-72 overflow-auto whitespace-pre-wrap text-xs text-slate-800">{generationArtifactText}</pre><div className="flex flex-wrap gap-2"><button type="button" onClick={() => setSynopsis(generationArtifactText.slice(0, 5000))} className="rounded-lg border-2 border-slate-900 bg-sky-100 px-3 py-2 text-xs font-bold">Gunakan sebagai sinopsis film</button><button type="button" onClick={() => setEpisodeSynopsis(generationArtifactText.slice(0, 3000))} className="rounded-lg border-2 border-slate-900 bg-rose-100 px-3 py-2 text-xs font-bold">Gunakan sebagai sinopsis episode</button><button type="button" onClick={() => void applyCinemaGeneration()} disabled={generationBusy || !selectedTitleId || generationJob?.status !== "succeeded" || generationJob.moderation_status !== "approved"} className="rounded-lg border-2 border-slate-900 bg-emerald-100 px-3 py-2 text-xs font-bold disabled:opacity-40">Terapkan ke screenplay</button></div></div>}
            {runtimeAgentsState === "loading" && <p className="text-xs text-slate-600">Memuat Agent dan Skill milik Anda…</p>}
            {runtimeAgentsState === "ready" && runtimeAgents.length === 0 && <p className="text-xs text-slate-600">Belum ada Agent aktif dengan ownership Anda.</p>}
            {runtimeAgentsState === "ready" && selectedRuntimeAgent && !selectedRuntimeSkill && <p className="text-xs text-amber-800">Agent ini belum memiliki Published Skill dengan tool adapter Generation yang tersedia.</p>}
            {runtimeAgentsState === "unavailable" && <p className="text-xs text-rose-800">Katalog Agent Runtime tidak dapat dimuat. Periksa koneksi FastAPI dan ownership policy.</p>}
          </>
        )}
      </section>

      <section className="mb-6 space-y-4 rounded-2xl border-2 border-slate-900 bg-slate-50 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-black uppercase tracking-[.18em] text-sky-800">Production Workspace · v{productionVersion}</p>
            <h3 className="mt-1 text-lg font-black text-slate-950">Screenplay, Storyboard & Editing Timeline</h3>
            <p className="mt-1 text-xs text-slate-700">Dokumen produksi disimpan melalui FastAPI dengan optimistic versioning. Media timeline dan audio wajib berasal dari Asset Library film yang sudah diproses dan lolos scan.</p>
          </div>
          <button type="button" onClick={() => void loadCinemaProduction(selectedTitleId)} disabled={!selectedTitleId || productionLoading} className="rounded-xl border-2 border-slate-900 bg-white px-3 py-2 text-xs font-bold text-slate-950 disabled:opacity-40">{productionLoading ? "Memuat…" : "Muat production"}</button>
        </div>
        {!selectedTitleId ? (
          <p className="rounded-xl border border-slate-900 bg-amber-50 p-3 text-xs text-amber-900">Pilih atau buat draft film untuk membuka Production Workspace.</p>
        ) : (
          <>
            <label className="block text-xs font-semibold text-slate-700">Production document · JSON terstruktur
              <textarea value={productionJson} onChange={event => setProductionJson(event.target.value)} rows={15} spellCheck={false} className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-white p-3 font-mono text-xs leading-relaxed text-slate-950" />
            </label>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="max-w-2xl text-xs text-slate-600">Kontrak mencakup screenplay, scene & dialogue, storyboard shots, video/audio/subtitle timeline tracks, audio beds, dan export profile. Provider rendering belum dipanggil dari editor ini.</p>
              <button type="button" onClick={() => void saveCinemaProduction()} disabled={saving || productionLoading} className="rounded-xl border-2 border-slate-900 bg-sky-200 px-4 py-2 text-sm font-black text-slate-950 shadow-[2px_2px_0px_#0f172a] disabled:opacity-40">{saving ? "Menyimpan…" : "Simpan versi produksi"}</button>
            </div>
            <div className="rounded-xl border-2 border-slate-900 bg-white p-3">
              <div className="mb-3 flex flex-wrap items-end gap-2">
                <label className="min-w-[180px] flex-1 text-xs font-semibold text-slate-700">Media siap pakai
                  <select value={selectedMediaId} onChange={event => setSelectedMediaId(event.target.value)} className="mt-1 w-full rounded-lg border-2 border-slate-900 bg-white p-2 text-sm text-slate-950">
                    <option value="">Pilih media</option>
                    {readyMedia.map(item => <option key={item.id} value={item.id}>{item.filename} · {item.media_type}</option>)}
                  </select>
                </label>
                <label className="text-xs font-semibold text-slate-700">Peran asset
                  <select value={assetRole} onChange={event => setAssetRole(event.target.value)} className="mt-1 rounded-lg border-2 border-slate-900 bg-white p-2 text-sm text-slate-950">
                    {["reference","storyboard","source_video","source_audio","music","subtitle","generated_image","generated_video","cover","trailer"].map(role => <option key={role} value={role}>{role}</option>)}
                  </select>
                </label>
                <button type="button" onClick={() => void attachCinemaAsset()} disabled={saving || !selectedMediaId} className="rounded-lg border-2 border-slate-900 bg-violet-100 px-3 py-2 text-xs font-black text-slate-950 disabled:opacity-40">Tautkan asset</button>
              </div>
              <div className="space-y-2">
                {productionAssets.map(asset => (
                  <div key={asset.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-300 p-2 text-xs">
                    <div><strong>{asset.display_name}</strong><span className="ml-2 text-slate-600">{asset.asset_role} · {asset.media?.media_type || "media"}</span></div>
                    <button type="button" onClick={() => void removeCinemaAsset(asset.id)} disabled={saving} className="rounded-md border border-slate-900 px-2 py-1 font-bold text-rose-800 disabled:opacity-40">Lepas</button>
                  </div>
                ))}
                {productionAssets.length === 0 && <p className="text-xs text-slate-500">Belum ada asset yang ditautkan ke film ini.</p>}
              </div>
            </div>
          </>
        )}
      </section>
      <div className="grid gap-6 lg:grid-cols-2">
        <form onSubmit={createTitle} className="space-y-3 rounded-2xl border-2 border-slate-900 bg-white p-4">
          <h3 className="font-bold">Buat draft film</h3>
          <label className="block text-xs text-slate-700">Judul film<input required maxLength={160} value={title} onChange={event => setTitle(event.target.value)} className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-slate-50 p-3 text-sm text-slate-900" /></label>
          <label className="block text-xs text-slate-700">Genre<select value={genre} onChange={event => setGenre(event.target.value)} className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-slate-50 p-3 text-sm text-slate-900"><option value="c_drama">C-Drama</option><option value="k_drama">K-Drama</option><option value="scifi">Sci-Fi</option><option value="romance">Romance</option><option value="thriller">Thriller</option><option value="animation_3d">Animasi 3D</option><option value="documentary">Dokumenter</option><option value="other">Lainnya</option></select></label>
          <label className="block text-xs text-slate-700">Sinopsis<textarea maxLength={5000} rows={4} value={synopsis} onChange={event => setSynopsis(event.target.value)} className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-slate-50 p-3 text-sm text-slate-900" /></label>
          <button disabled={saving || !title.trim()} className="w-full rounded-xl bg-sky-300 px-4 py-3 text-sm font-black text-slate-950 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] disabled:opacity-50">{saving ? "Menyimpan…" : "Simpan draft film"}</button>
        </form>
        <div className="space-y-4">
          <div className="rounded-2xl border-2 border-slate-900 bg-white p-4">
            <h3 className="mb-3 font-bold">Film milik saya</h3>
            {titles.length === 0 ? <p className="text-sm text-slate-600">{loading ? "Memuat draft…" : "Belum ada draft film pada akun ini."}</p> : <select aria-label="Pilih draft film" value={selectedTitleId} onChange={event => setSelectedTitleId(event.target.value)} className="w-full rounded-xl border-2 border-slate-900 bg-slate-50 p-3 text-sm text-slate-900">{titles.map(item => <option key={item.id} value={item.id}>{item.title} · {item.status}</option>)}</select>}
          </div>
          <div className="space-y-3 rounded-2xl border-2 border-slate-900 bg-white p-4">
            <h3 className="font-bold">Ajukan ke review</h3>
            <label className="flex items-start gap-2 text-xs text-slate-700"><input type="checkbox" checked={rightsConfirmed} onChange={event => setRightsConfirmed(event.target.checked)} />Saya menyatakan memiliki hak/izin atas materi yang digunakan.</label>
            <label className="flex items-start gap-2 text-xs text-slate-700"><input type="checkbox" checked={aiDisclosureConfirmed} onChange={event => setAiDisclosureConfirmed(event.target.checked)} />Saya mengonfirmasi pengungkapan penggunaan AI pada metadata film.</label>
            <button type="button" onClick={() => void submitForReview()} disabled={saving || !selectedTitleId || !rightsConfirmed || !aiDisclosureConfirmed} className="w-full rounded-xl border-2 border-slate-900 bg-rose-100 px-4 py-3 text-sm font-black text-rose-900 shadow-[2px_2px_0px_#0f172a] disabled:opacity-40">{saving ? "Mengajukan…" : "Ajukan rights review & moderasi"}</button>
            <p className="text-xs text-slate-600">API akan menolak pengajuan jika episode belum memiliki media ready dan scan clean. Keputusan hak cipta dan moderasi tetap dilakukan operator.</p>
          </div>
          <section className="space-y-3 rounded-2xl border-2 border-slate-900 bg-white p-4">
            <h3 className="font-bold">Upload video film · Media Pipeline</h3>
            <p className="text-xs text-slate-600">MP4/WebM maksimal 50 MiB. File disimpan melalui FastAPI ke Supabase Storage; worker dan pemeriksaan keamanan menentukan kapan media siap digunakan.</p>
            <input type="file" accept="video/mp4,video/webm" onChange={event => { const next = event.target.files?.[0] ?? null; const sameFile = Boolean(next && uploadFile && next.name === uploadFile.name && next.size === uploadFile.size && next.lastModified === uploadFile.lastModified); setUploadFile(next); if (!sameFile) setUploadIdempotencyKey(""); }} className="block w-full text-xs text-slate-700 file:mr-3 file:rounded-lg file:border-0 file:bg-sky-300 file:border-2 file:border-slate-900 file:px-3 file:py-2 file:text-xs file:font-black file:text-slate-950" />
            {uploadFile && <p className="text-xs text-slate-700">{uploadFile.name} · {(uploadFile.size / 1024 / 1024).toFixed(1)} MiB</p>}
            <button type="button" onClick={() => void uploadCinemaMedia()} disabled={saving || !uploadFile} className="w-full rounded-xl bg-sky-300 px-4 py-3 text-sm font-black text-slate-950 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] disabled:opacity-50">{saving ? "Mengunggah…" : "Unggah video ke Media Pipeline"}</button>
            <div className="space-y-1 border-t border-slate-900 pt-3"><p className="text-xs font-bold text-slate-700">Status media saya</p>{creatorMedia.length ? creatorMedia.map(media => <p key={media.id} className="text-xs text-slate-600">{media.filename} · {media.status} · scan {media.scan_status}{media.processed_at ? " · diproses " + new Date(media.processed_at).toLocaleString("id-ID") : ""}</p>) : <p className="text-xs text-slate-600">Belum ada media milik akun ini.</p>}</div>
          </section>
          <form onSubmit={createEpisode} className="space-y-3 rounded-2xl border-2 border-slate-900 bg-white p-4">
            <h3 className="font-bold">Tambah draft episode</h3>
            <label className="block text-xs text-slate-700">Nomor episode<input required type="number" min="1" max="10000" value={episodeNumber} onChange={event => setEpisodeNumber(event.target.value)} className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-slate-50 p-3 text-sm text-slate-900" /></label>
            <label className="block text-xs text-slate-700">Judul episode<input required maxLength={160} value={episodeTitle} onChange={event => setEpisodeTitle(event.target.value)} className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-slate-50 p-3 text-sm text-slate-900" /></label>
            <label className="block text-xs text-slate-700">Sinopsis<textarea maxLength={3000} rows={2} value={episodeSynopsis} onChange={event => setEpisodeSynopsis(event.target.value)} className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-slate-50 p-3 text-sm text-slate-900" /></label>
            <label className="block text-xs text-slate-700">Media episode · hanya media siap dan scan clean<select value={selectedMediaId} onChange={event => setSelectedMediaId(event.target.value)} className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-slate-50 p-3 text-sm text-slate-900"><option value="">Simpan tanpa media (draft)</option>{readyMedia.map(media => <option key={media.id} value={media.id}>{media.filename} · {media.media_type} · {(media.size_bytes / 1024 / 1024).toFixed(1)} MiB</option>)}</select><span className="mt-1 block text-slate-600">Media dari Creator Studio hanya tersedia setelah processing selesai dan scan berstatus clean.</span></label>
            <button disabled={saving || !selectedTitleId || !episodeTitle.trim()} className="w-full rounded-xl bg-rose-300 px-4 py-3 text-sm font-black text-slate-950 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] disabled:opacity-50">{saving ? "Menyimpan…" : "Simpan draft episode"}</button>
          </form>
        </div>
      </div>
      <div className="mt-6 rounded-2xl border-2 border-slate-900 bg-slate-50 p-4">
        <h3 className="mb-3 font-bold">Daftar episode</h3>
        {episodes.length === 0 ? <p className="text-sm text-slate-600">Belum ada episode untuk film yang dipilih.</p> : <ol className="space-y-2">{episodes.map(item => <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-slate-50 p-3 text-sm"><span><strong>Episode {item.episode_number} — {item.title}</strong><span className="ml-2 text-xs text-slate-600">{item.status}</span></span><span className="text-xs text-slate-600">{item.duration_seconds ? `${item.duration_seconds} dtk` : "Durasi belum ditetapkan"}</span></li>)}</ol>}
      </div>
      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <section className="rounded-2xl border-2 border-slate-900 bg-white p-4">
          <h3 className="font-bold">Kolaborator & Human-Agent credits</h3>
          <p className="mt-1 text-xs text-slate-600">Akses diberikan per film dan per scope. Undangan Human aktif setelah penerima menyetujui.</p>
          <form onSubmit={inviteCollaborator} className="mt-3 space-y-2">
            <label className="block text-xs text-slate-700">ID akun Human yang diundang (UUID)<input value={collaboratorUserId} onChange={e=>setCollaboratorUserId(e.target.value)} placeholder="UUID akun collaborator" className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-slate-50 p-3 text-sm text-slate-900"/></label>
            <label className="block text-xs text-slate-700">Peran<input value={collaboratorRole} onChange={e=>setCollaboratorRole(e.target.value)} maxLength={80} className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-slate-50 p-3 text-sm text-slate-900"/></label>
            <div className="flex flex-wrap gap-3 text-xs text-slate-700">
              {["edit_metadata","upload_episodes","manage_credits","submit_review"].map(scope=><label key={scope} className="flex items-center gap-1"><input type="checkbox" checked={collaboratorPermissions.includes(scope)} onChange={e=>setCollaboratorPermissions(v=>e.target.checked?[...v,scope]:v.filter(x=>x!==scope))}/>{scope}</label>)}
            </div>
            <button disabled={saving||!selectedTitleId||!collaboratorUserId.trim()} className="rounded-xl bg-sky-300 px-4 py-2 text-sm font-black text-slate-950 border-2 border-slate-900 shadow-[2px_2px_0px_#0f172a] disabled:opacity-50">Undang collaborator</button>
          </form>
          <div className="mt-4 space-y-2">
            {collaborators.map(item=><div key={item.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-slate-50 p-3 text-xs"><span><strong>{item.role}</strong><span className="ml-2 text-slate-600">{item.collaborator_user_id||item.collaborator_agent_id} · {item.status}</span><span className="block text-slate-600">{item.permissions.join(", ")}</span></span>{item.status!=="revoked"&&<button onClick={()=>void decideCollaboration(item.id,"revoke")} className="rounded-lg border border-2 border-slate-900 px-3 py-1 text-rose-800">Cabut akses</button>}</div>)}
            {collaborators.length===0&&<p className="text-xs text-slate-600">Belum ada collaborator pada film ini.</p>}
          </div>
          <div className="mt-4 border-t border-slate-900 pt-3">
            <h4 className="text-sm font-bold">Undangan saya</h4>
            {invitations.map(item=><div key={item.id} className="mt-2 flex flex-wrap items-center justify-between gap-2 rounded-xl bg-slate-50 p-3 text-xs"><span>{item.title?.title||"Film"} · {item.role} · {item.status}</span>{item.status==="invited"&&<button onClick={()=>void decideCollaboration(item.id,"accept")} className="rounded-lg bg-violet-400 px-3 py-1 font-bold text-slate-950">Terima</button>}</div>)}
          </div>
        </section>
        <section className="rounded-2xl border-2 border-slate-900 bg-white p-4">
          <h3 className="font-bold">Creator Credits & Version History</h3>
          <form onSubmit={addCreatorCredit} className="mt-3 space-y-2">
            <label className="block text-xs text-slate-700">Jenis kontributor<select value={creditType} onChange={e=>setCreditType(e.target.value)} className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-slate-50 p-3 text-sm text-slate-900"><option value="human">Human (akun saya)</option><option value="agent">AI Agent</option></select></label>
            {creditType==="agent"&&<label className="block text-xs text-slate-700">ID AI Agent (UUID)<input value={creditAgentId} onChange={e=>setCreditAgentId(e.target.value)} className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-slate-50 p-3 text-sm text-slate-900" placeholder="UUID AI Agent milik pemilik film"/></label>}
            <label className="block text-xs text-slate-700">Peran kontribusi<input value={creditRole} onChange={e=>setCreditRole(e.target.value)} maxLength={80} className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-slate-50 p-3 text-sm text-slate-900"/></label>
            <label className="block text-xs text-slate-700">Label atribusi<input value={creditLabel} onChange={e=>setCreditLabel(e.target.value)} maxLength={160} className="mt-1 w-full rounded-xl border-2 border-slate-900 bg-slate-50 p-3 text-sm text-slate-900"/></label>
            <button disabled={saving||!selectedTitleId||(creditType==="agent"&&!creditAgentId.trim())} className="rounded-xl bg-violet-400 px-4 py-2 text-sm font-black text-slate-950 disabled:opacity-50">Simpan creator credit</button>
          </form>
          <div className="mt-3 space-y-1">{credits.map(item=><p key={item.id} className="rounded-lg bg-slate-50 p-2 text-xs">{item.attribution_label} · {item.role} · {item.contributor_type}</p>)}{credits.length===0&&<p className="text-xs text-slate-600">Belum ada kredit kreator.</p>}</div>
          <div className="mt-4 border-t border-slate-900 pt-3">
            <button type="button" disabled={saving||!selectedTitleId} onClick={()=>void snapshotVersion()} className="rounded-xl border border-cyan-300/40 px-4 py-2 text-sm font-bold text-sky-800 disabled:opacity-50">Simpan snapshot versi film</button>
            <div className="mt-2 space-y-1">{versions.map(item=><p key={item.id} className="text-xs text-slate-600">Versi {item.version} · {new Date(item.created_at).toLocaleString("id-ID")}</p>)}{versions.length===0&&<p className="text-xs text-slate-600">Belum ada snapshot versi.</p>}</div>
          </div>
        </section>
      </div>
      <p className="mt-4 text-xs leading-relaxed text-amber-800">Generate AI, tarif/kredit, publikasi, moderasi, dan entitlement belum diaktifkan di panel ini karena kontrak job, policy billing, dan bukti runtime terkait belum lengkap.</p>
    </section>
  );
}

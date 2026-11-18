import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, Text, TextInput, View } from "react-native";
import type { Session } from "@supabase/supabase-js";

type Props = { session: Session; apiBase: string };
type Agent = { id: string; display_name: string; handle: string; status: string };
type Policy = { allowed_actions: string[]; approval_mode: "every_post" | "high_risk_only" | "disabled"; disclosure_text: string; is_enabled: boolean; version: number };
type Approval = { id: string; agent_id: string; content_id: string; action_type: string; status: string; disclosure_snapshot: string; requested_at: string; decided_at?: string | null };
type Automation = { version: number; auto_reply_channels: string[]; blocked_topics: string[]; reply_tone: string; allowed_tool_scopes: string[]; max_replies_per_minute: number; daily_credit_budget: number; quiet_hours: Record<string, unknown>; escalation_rules: Record<string, unknown>; takeover_active: boolean };
type DecisionResult = { outcome: string; execution?: { kind?: string; message_id?: string; conversation_id?: string; story_id?: string; comment_id?: string }; approval?: { status?: string } };
const choices = ["draft_post", "draft_comment", "draft_reply", "suggest_repost", "draft_story"];
const styles = {
  page: { flexGrow: 1, backgroundColor: "#0B1020", padding: 18, gap: 14 } as const,
  card: { backgroundColor: "#141B31", borderColor: "#29314B", borderWidth: 1, borderRadius: 22, padding: 18, gap: 12 } as const,
  title: { color: "#F7F8FF", fontSize: 20, fontWeight: "800" as const },
  body: { color: "#C0C7DA", fontSize: 13, lineHeight: 19 } as const,
  kicker: { color: "#A5B4FC", fontSize: 10, letterSpacing: 2, fontWeight: "800" as const },
  field: { color: "#F7F8FF", backgroundColor: "#0D1326", borderColor: "#303A58", borderWidth: 1, borderRadius: 12, padding: 12 } as const,
  action: { color: "#E1E6F8", borderColor: "#3A4566", borderWidth: 1, borderRadius: 12, padding: 12, overflow: "hidden" as const },
  error: { color: "#FCA5A5", backgroundColor: "#321D2B", padding: 10, borderRadius: 10 } as const,
  ok: { color: "#86EFAC", backgroundColor: "#12302C", padding: 10, borderRadius: 10 } as const,
};
export function AgentSocialControls({ session, apiBase }: Props) {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentId, setAgentId] = useState("");
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [actions, setActions] = useState<string[]>(["draft_post"]);
  const [mode, setMode] = useState<Policy["approval_mode"]>("every_post");
  const [disclosure, setDisclosure] = useState("Dibuat bersama AI Agent");
  const [enabled, setEnabled] = useState(false);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [automation, setAutomation] = useState<Automation | null>(null);
  const [channels, setChannels] = useState<string[]>([]);
  const [blockedTopicsText, setBlockedTopicsText] = useState("");
  const [replyTone, setReplyTone] = useState("friendly_concise");
  const [dailyBudget, setDailyBudget] = useState("0");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const api = useCallback(async (path: string, init: RequestInit = {}) => {
    const response = await fetch(apiBase.replace(/\/$/, "") + path, { ...init, headers: { Authorization: "Bearer " + session.access_token, Accept: "application/json", "Content-Type": "application/json", ...(init.headers || {}) }, cache: "no-store" });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data?.detail?.message || data?.error?.message || "Permintaan gagal.");
    return data;
  }, [apiBase, session.access_token]);
  const load = useCallback(async () => {
    setLoading(true); setError(""); setPolicy(null); setAutomation(null); setEnabled(false);
    try {
      const [a, p] = await Promise.all([api("/v1/agents"), api("/v1/agent-social/approvals")]);
      const active = (a.items || []).filter((x: Agent) => x.status === "active");
      setAgents(active); setApprovals(p.items || []);
      const selected = active.some((x: Agent) => x.id === agentId) ? agentId : active[0]?.id || "";
      setAgentId(selected);
      if (selected) {
        const [result, automationResult] = await Promise.all([
          api("/v1/agent-social/policy?agent_id=" + encodeURIComponent(selected)),
          api("/v1/agent-social/automation?agent_id=" + encodeURIComponent(selected)),
        ]);
        const current = result.policy as Policy | null;
        const currentAutomation = automationResult.policy as Automation | null;
        setAutomation(currentAutomation);
        setChannels(currentAutomation?.auto_reply_channels || []);
        setBlockedTopicsText((currentAutomation?.blocked_topics || []).join(", "));
        setReplyTone(currentAutomation?.reply_tone || "friendly_concise");
        setDailyBudget(String(currentAutomation?.daily_credit_budget ?? 0));
        setPolicy(current);
        setActions(current?.allowed_actions || ["draft_post"]); setMode(current?.approval_mode === "disabled" ? "disabled" : "every_post");
        setDisclosure(current?.disclosure_text || "Dibuat bersama AI Agent"); setEnabled(current?.is_enabled ?? false);
      } else { setPolicy(null); setAutomation(null); setChannels([]); setBlockedTopicsText(""); setReplyTone("friendly_concise"); setDailyBudget("0"); setEnabled(false); setActions(["draft_post"]); setMode("every_post"); }
    } catch (cause) { setPolicy(null); setAutomation(null); setEnabled(false); setActions(["draft_post"]); setMode("every_post"); setError(cause instanceof Error ? cause.message : "Data tidak dapat dimuat."); }
    finally { setLoading(false); }
  }, [api, agentId]);
  useEffect(() => { void load(); }, [load]);
  async function save() {
    if (!agentId) return; setBusy(true); setError(""); setNotice("");
    try {
      const result = await api("/v1/agent-social/policy/" + agentId, { method: "PUT", body: JSON.stringify({ allowed_actions: actions, approval_mode: mode, disclosure_text: disclosure, is_enabled: enabled, expected_version: policy?.version ?? null }) });
      setPolicy(result.policy); setNotice("Kebijakan tersimpan."); await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Kebijakan gagal disimpan."); }
    finally { setBusy(false); }
  }
  async function saveAutomation() {
    if (!agentId || !automation || busy) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await api("/v1/agent-social/automation/" + agentId, {
        method: "PUT",
        body: JSON.stringify({
          auto_reply_channels: channels,
          blocked_topics: blockedTopicsText.split(",").map(item => item.trim()).filter(Boolean),
          reply_tone: replyTone,
          allowed_tool_scopes: automation.allowed_tool_scopes || [],
          max_replies_per_minute: automation.max_replies_per_minute || 1,
          daily_credit_budget: Math.max(0, Math.floor(Number(dailyBudget) || 0)),
          quiet_hours: automation.quiet_hours || {},
          escalation_rules: automation.escalation_rules || {},
          expected_version: automation.version,
        }),
      });
      setAutomation(result.policy as Automation);
      setNotice("Konfigurasi Auto Reply tersimpan; eksekusi tetap nonaktif sampai runtime tersedia.");
      await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Konfigurasi gagal disimpan."); }
    finally { setBusy(false); }
  }
  async function decide(id: string, decision: "approve" | "reject") {
    setBusy(true); setError(""); setNotice("");
    try { const result = await api("/v1/agent-social/approvals/" + id + "/decision", { method: "POST", body: JSON.stringify({ decision, reason: decision === "approve" ? "Disetujui pemilik melalui Native" : "Ditolak pemilik melalui Native" }) }) as DecisionResult; const execution = result.execution; const detail = execution?.kind === "story_dm" ? "DM Story berhasil dibuat dan tertaut ke Story." : execution?.kind === "comment" ? "Komentar/reply Agent tercatat dengan atribusi." : execution?.kind === "post_moderation" ? "Draft dikirim ke antrean moderasi; belum dipublikasikan." : execution?.kind === "agent_repost" ? "Repost Agent tercatat dengan atribusi dan disclosure." : result.approval?.status === "approved" ? "Approval tercatat; moderasi konten tetap berlaku." : "Permintaan ditolak."; setNotice((result.outcome === "replayed" ? "Hasil transaksi sebelumnya dipulihkan. " : "") + detail); await load(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Keputusan gagal."); }
    finally { setBusy(false); }
  }
  async function revoke(id: string) {
    setBusy(true); setError("");
    try { const result = await api("/v1/agent-social/approvals/" + id + "/revoke", { method: "POST" }); setNotice(result.outcome === "replayed" ? "Pencabutan sebelumnya sudah tercatat." : "Persetujuan dicabut; audit dan notifikasi tercatat."); await load(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Pencabutan gagal."); }
    finally { setBusy(false); }
  }
  return <ScrollView contentContainerStyle={styles.page}>
    <View style={styles.card}><Text style={styles.kicker}>HUMAN CONTROL · WP-06</Text><Text style={styles.title}>Kebijakan Sosial AI Agent</Text><Text style={styles.body}>Pemilik menentukan tindakan yang dapat disiapkan Agent. Seluruh approval tetap memerlukan keputusan Human.</Text>
      {loading ? <ActivityIndicator color="#A5B4FC"/> : agents.length === 0 ? <Text style={styles.body}>Belum ada Agent aktif yang dimiliki akun ini.</Text> : <>
        {agents.map(agent => <Text key={agent.id} onPress={() => setAgentId(agent.id)} style={[styles.action, { borderColor: agent.id === agentId ? "#A5B4FC" : "#3A4566" }]}>{agent.id === agentId ? "✓ " : ""}{agent.display_name} · @{agent.handle}</Text>)}
        <Text style={styles.kicker}>IZIN TINDAKAN</Text>
        {choices.map(key => <Text key={key} onPress={() => setActions(old => old.includes(key) ? old.filter(x => x !== key) : [...old, key])} style={styles.action}>{actions.includes(key) ? "☑ " : "□ "}{key.replaceAll("_", " ")}</Text>)}
        <Text style={styles.kicker}>MODE APPROVAL</Text>
        {(["every_post", "high_risk_only", "disabled"] as const).map(value => <Text key={value} onPress={value === "high_risk_only" ? undefined : () => setMode(value)} style={[styles.action, { opacity: value === "high_risk_only" ? 0.45 : 1 }]}>{mode === value ? "✓ " : ""}{value}{value === "high_risk_only" ? " · belum didukung runtime" : ""}</Text>)}
        {mode === "high_risk_only" && <Text style={styles.error}>Mode lama ini belum didukung oleh runtime. Pilih every_post atau disabled sebelum menyimpan.</Text>}
        <Text style={styles.kicker}>DISCLOSURE PUBLIK</Text><TextInput value={disclosure} onChangeText={setDisclosure} maxLength={180} style={styles.field}/>
        <Text onPress={() => setEnabled(value => !value)} style={styles.action}>{enabled ? "☑" : "□"} Kebijakan aktif</Text>
        <Text onPress={busy || !disclosure.trim() || (enabled && mode !== "disabled" && actions.length === 0) || mode === "high_risk_only" ? undefined : () => void save()} style={[styles.action, { backgroundColor: busy ? "#303A58" : "#A5B4FC", color: "#10152A", fontWeight: "800", opacity: busy || !disclosure.trim() || (enabled && mode !== "disabled" && actions.length === 0) || mode === "high_risk_only" ? 0.45 : 1 }]}>{busy ? "Menyimpan…" : "Simpan Kebijakan"}</Text>
      </>}
    </View>

    <View style={styles.card}>
      <Text style={styles.kicker}>AUTO REPLY · TAKEOVER</Text>
      <Text style={styles.title}>Kontrol Otomatisasi</Text>
      <Text style={styles.body}>Eksekusi tetap membutuhkan policy runtime yang disetujui. Takeover menghentikan Auto Reply dan mencabut approval yang masih pending. Auto Reply tetap nonaktif sampai runtime event consumer tersambung.</Text>
      <Text style={styles.body}>Status: {automation?.takeover_active ? "Takeover Human aktif" : automation ? "Takeover dilepas · Auto Reply masih nonaktif" : "Policy automation belum tersedia"}</Text>
      {automation ? <>
        <Text style={styles.kicker}>CHANNEL AUTO REPLY</Text>
        {["comments", "mentions", "dm", "live_chat"].map(channel => <Text key={channel} onPress={() => setChannels(old => old.includes(channel) ? old.filter(item => item !== channel) : [...old, channel])} style={styles.action}>{channels.includes(channel) ? "☑ " : "□ "}{channel.replace("_", " ")}</Text>)}
        <Text style={styles.kicker}>TOPIK YANG DIBLOKIR</Text>
        <TextInput value={blockedTopicsText} onChangeText={setBlockedTopicsText} placeholder="Pisahkan dengan koma" placeholderTextColor="#94A3B8" style={styles.field}/>
        <Text style={styles.kicker}>GAYA KOMUNIKASI</Text>
        {["friendly_concise", "professional", "warm", "formal"].map(value => <Text key={value} onPress={() => setReplyTone(value)} style={styles.action}>{replyTone === value ? "✓ " : ""}{value.replaceAll("_", " ")}</Text>)}
        <Text style={styles.kicker}>BATAS BUDGET HARIAN (AI CREDITS)</Text>
        <TextInput value={dailyBudget} onChangeText={setDailyBudget} keyboardType="number-pad" style={styles.field}/>
        <Text onPress={() => void saveAutomation()} style={[styles.action, { backgroundColor: busy ? "#303A58" : "#A5B4FC", color: "#10152A", fontWeight: "800" }]}>{busy ? "Menyimpan…" : "Simpan Pengaturan Auto Reply"}</Text>
      </> : <Text style={styles.body}>Policy automation belum dibuat untuk Agent ini. Kontrol dinonaktifkan sampai backend menyediakan record kanonis.</Text>}
      <Text onPress={async () => { if (!agentId || !automation || busy) return; setBusy(true); setError(""); try { const active = !automation.takeover_active; const result = await api("/v1/agent-social/takeover/" + agentId,{method:"POST",body:JSON.stringify({takeover_active:active,reason:active?"owner_manual_takeover_native":"owner_released_takeover_native"})}); setAutomation(result.policy as Automation); setNotice(active?"Takeover aktif; approval pending dicabut.":"Takeover dilepas; Auto Reply belum diaktifkan."); await load(); } catch(cause) { setError(cause instanceof Error?cause.message:"Takeover gagal."); } finally { setBusy(false); } }} style={[styles.action, { opacity: !automation || busy ? 0.5 : 1 }]}>{automation?.takeover_active ? "Lepas Takeover" : "Ambil Alih Sekarang"}</Text>
    </View>
    <View style={styles.card}><Text style={styles.title}>Approval Inbox</Text><Text style={styles.body}>{approvals.filter(x => x.status === "pending").length} permintaan menunggu keputusan</Text>
      {approvals.length === 0 ? <Text style={styles.body}>Belum ada approval.</Text> : approvals.map(item => <View key={item.id} style={{ borderTopWidth: 1, borderTopColor: "#29314B", paddingTop: 12, gap: 8 }}>
        <Text style={styles.body}>{item.action_type} · {item.status}</Text><Text style={styles.body}>{new Date(item.requested_at).toLocaleString("id-ID")}</Text><Text style={styles.body}>{item.disclosure_snapshot}</Text>
        {item.status === "pending" && <><Text onPress={() => void decide(item.id, "approve")} style={styles.action}>Setujui</Text><Text onPress={() => void decide(item.id, "reject")} style={styles.action}>Tolak</Text></>}
        {item.status === "approved" && <Text onPress={() => void revoke(item.id)} style={styles.action}>Cabut persetujuan</Text>}
      </View>)}
    </View>
    {!!error && <Text style={styles.error}>{error}</Text>}{!!notice && <Text style={styles.ok}>{notice}</Text>}
  </ScrollView>;
}

import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, Text, TextInput, View } from "react-native";
import type { Session } from "@supabase/supabase-js";

type Props = { session: Session; apiBase: string };
type Agent = { id: string; display_name: string; handle: string; status: string };
type Policy = { allowed_actions: string[]; approval_mode: "every_post" | "high_risk_only" | "disabled"; disclosure_text: string; is_enabled: boolean; version: number };
type Approval = { id: string; agent_id: string; content_id: string; action_type: string; status: string; disclosure_snapshot: string; requested_at: string; decided_at?: string | null };\ntype DecisionResult = { outcome: string; execution?: { kind?: string; message_id?: string; conversation_id?: string; story_id?: string; comment_id?: string }; approval?: { status?: string } };
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
  const [enabled, setEnabled] = useState(true);
  const [approvals, setApprovals] = useState<Approval[]>([]);
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
    setLoading(true); setError("");
    try {
      const [a, p] = await Promise.all([api("/v1/agents"), api("/v1/agent-social/approvals")]);
      const active = (a.items || []).filter((x: Agent) => x.status === "active");
      setAgents(active); setApprovals(p.items || []);
      const selected = active.some((x: Agent) => x.id === agentId) ? agentId : active[0]?.id || "";
      setAgentId(selected);
      if (selected) {
        const result = await api("/v1/agent-social/policy?agent_id=" + encodeURIComponent(selected));
        const current = result.policy as Policy | null; setPolicy(current);
        setActions(current?.allowed_actions || ["draft_post"]); setMode(current?.approval_mode || "every_post");
        setDisclosure(current?.disclosure_text || "Dibuat bersama AI Agent"); setEnabled(current?.is_enabled ?? true);
      } else setPolicy(null);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Data tidak dapat dimuat."); }
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
  async function decide(id: string, decision: "approve" | "reject") {
    setBusy(true); setError(""); setNotice("");
    try { const result = await api("/v1/agent-social/approvals/" + id + "/decision", { method: "POST", body: JSON.stringify({ decision, reason: decision === "approve" ? "Disetujui pemilik melalui Native" : "Ditolak pemilik melalui Native" }) }) as DecisionResult; const execution = result.execution; const detail = execution?.kind === "story_dm" ? "DM Story berhasil dibuat dan tertaut ke Story." : execution?.kind === "comment" ? "Balasan komentar berhasil dicatat." : result.approval?.status === "approved" ? "Draft disetujui; moderasi konten tetap berlaku." : "Permintaan ditolak."; setNotice((result.outcome === "replayed" ? "Hasil transaksi sebelumnya dipulihkan. " : "") + detail); await load(); }
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
        {(["every_post", "high_risk_only", "disabled"] as const).map(value => <Text key={value} onPress={() => setMode(value)} style={styles.action}>{mode === value ? "✓ " : ""}{value}</Text>)}
        <Text style={styles.kicker}>DISCLOSURE PUBLIK</Text><TextInput value={disclosure} onChangeText={setDisclosure} maxLength={180} style={styles.field}/>
        <Text onPress={() => setEnabled(value => !value)} style={styles.action}>{enabled ? "☑" : "□"} Kebijakan aktif</Text>
        <Text onPress={() => void save()} style={[styles.action, { backgroundColor: busy ? "#303A58" : "#A5B4FC", color: "#10152A", fontWeight: "800" }]}>{busy ? "Menyimpan…" : "Simpan Kebijakan"}</Text>
      </>}
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

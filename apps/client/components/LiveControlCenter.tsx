import React, { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, ScrollView, Text, TextInput, View } from "react-native";
import type { Session } from "@supabase/supabase-js";

type LiveSession = {
  id: string; host_user_id: string; conversation_id: string; title: string;
  description: string; visibility: "public" | "followers" | "private";
  status: string; version: number; scheduled_at?: string | null;
  media_plane?: { status: string; publish_subscribe_tokens_available: boolean };
};
type Participant = { id: string; user_id: string; participant_role: string; status: string };
type StageEvent = { id: string; event_seq: number; actor_user_id: string | null; event_type: string; payload: Record<string, unknown> };

function uuid() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, token => {
    const random = Math.floor(Math.random() * 16);
    return (token === "x" ? random : (random & 0x3) | 0x8).toString(16);
  });
}

export function LiveControlCenter({ session, apiBase }: { session: Session; apiBase: string }) {
  const [items, setItems] = useState<LiveSession[]>([]);
  const [selected, setSelected] = useState<LiveSession | null>(null);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [events, setEvents] = useState<StageEvent[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [visibility, setVisibility] = useState<"public" | "followers" | "private">("public");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [handRaised, setHandRaised] = useState(false);
  const pending = useRef(new Map<string, string>());

  const keyFor = (scope: string) => {
    const current = pending.current.get(scope);
    if (current) return current;
    const created = uuid();
    pending.current.set(scope, created);
    return created;
  };
  const confirmed = (scope: string) => pending.current.delete(scope);

  const request = useCallback(async <T,>(path: string, method = "GET", body?: unknown): Promise<T> => {
    const response = await fetch(apiBase.replace(/\/$/, "") + path, {
      method, headers: { Accept: "application/json", Authorization: "Bearer " + session.access_token,
        ...(body ? { "Content-Type": "application/json" } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload?.error?.message || payload?.detail?.message || "Operasi Live belum dapat dikonfirmasi.");
    return payload as T;
  }, [apiBase, session.access_token]);

  const refresh = useCallback(async (selectedId?: string) => {
    setLoading(true); setError("");
    try {
      const result = await request<{ items: LiveSession[] }>("/v1/live/sessions");
      const rows = Array.isArray(result.items) ? result.items : [];
      setItems(rows);
      const target = rows.find(row => row.id === selectedId) || rows.find(row => row.id === selected?.id) || rows[0] || null;
      setSelected(target);
      if (target) {
        const detail = await request<{ session: LiveSession; participants: Participant[] }>(`/v1/live/sessions/${target.id}`);
        setSelected(detail.session); setParticipants(detail.participants || []);
        const feed = await request<{ items: StageEvent[] }>(`/v1/live/sessions/${target.id}/stage-events?limit=50`);
        const stage = Array.isArray(feed.items) ? feed.items : [];
        setEvents(stage);
        const latest = [...stage].reverse().find(event => event.event_type === "stage_hand_raised" && event.actor_user_id === session.user.id);
        setHandRaised(latest?.payload?.raised === true);
      } else { setParticipants([]); setEvents([]); setHandRaised(false); }
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Data Live tidak dapat dimuat."); }
    finally { setLoading(false); }
  }, [request, selected?.id, session.user.id]);

  useEffect(() => { void refresh(); }, [refresh]);

  async function run(action: () => Promise<void>, success: string) {
    setBusy(true); setError(""); setNotice("");
    try { await action(); setNotice(success); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Operasi Live gagal."); }
    finally { setBusy(false); }
  }

  async function createSession() {
    if (!title.trim()) return;
    await run(async () => {
      const result = await request<{ session: LiveSession }>("/v1/live/sessions", "POST", {
        title: title.trim(), description, visibility, idempotency_key: keyFor("create"),
      });
      confirmed("create"); setTitle(""); setDescription("");
      await refresh(result.session.id);
    }, "Sesi tersimpan pada Live Control Plane.");
  }

  async function transition(next: "preparing" | "ended") {
    if (!selected) return;
    await run(async () => {
      await request(`/v1/live/sessions/${selected.id}/transition`, "POST", {
        expected_version: selected.version, next_status: next, reason: "native_host_action",
      });
      await refresh(selected.id);
    }, next === "preparing" ? "Stage disiapkan. Media plane tetap nonaktif." : "Sesi diakhiri.");
  }

  async function joinOrLeave(join: boolean) {
    if (!selected) return;
    const scope = (join ? "join:" : "leave:") + selected.id;
    await run(async () => {
      await request(`/v1/live/sessions/${selected.id}/${join ? "join" : "leave"}`, "POST", { idempotency_key: keyFor(scope) });
      confirmed(scope); await refresh(selected.id);
    }, join ? "Berhasil bergabung ke sesi." : "Keluar dari sesi.");
  }

  async function stageEvent(type: "stage_hand_raised" | "stage_reaction_added", payload: Record<string, unknown>, scope: string) {
    if (!selected) return;
    await run(async () => {
      await request(`/v1/live/sessions/${selected.id}/stage-events`, "POST", {
        event_type: type, payload, idempotency_key: keyFor(scope),
      });
      confirmed(scope);
      if (type === "stage_hand_raised") setHandRaised(payload.raised === true);
      const feed = await request<{ items: StageEvent[] }>(`/v1/live/sessions/${selected.id}/stage-events?limit=50`);
      setEvents(feed.items || []);
    }, type === "stage_hand_raised" ? (payload.raised ? "Tangan diangkat." : "Tangan diturunkan.") : "Reaksi dikirim.");
  }

  const joined = participants.some(item => item.user_id === session.user.id && item.status === "joined");
  const host = selected?.host_user_id === session.user.id;
  const active = Boolean(selected && ["preparing", "live", "paused", "reconnecting"].includes(selected.status));

  return <ScrollView contentContainerStyle={{ padding: 18, gap: 14 }}>
    <View style={{ gap: 5 }}>
      <Text style={{ color: "#A5B4FC", fontSize: 11, fontWeight: "900", letterSpacing: 2 }}>ENG-P25 · LIVE CONTROL PLANE</Text>
      <Text style={{ color: "#F7F8FF", fontSize: 24, fontWeight: "900" }}>Live & Stage</Text>
      <Text style={{ color: "#A5ADC3", lineHeight: 19 }}>Sesi, peserta, hand raise, dan reaksi menggunakan kontrak FastAPI yang sama dengan Web.</Text>
    </View>
    <View style={{ borderWidth: 1, borderColor: "#8A5A12", borderRadius: 14, padding: 12, backgroundColor: "#33270F" }}>
      <Text style={{ color: "#FCD34D", fontWeight: "800" }}>Media streaming belum diaktifkan.</Text>
      <Text style={{ color: "#FDE68A", fontSize: 12, lineHeight: 18 }}>WebRTC/SFU/TURN, token publish/subscribe, dan recording tetap terkunci sampai ADR-WP10-001 disetujui.</Text>
    </View>
    {!!error && <Text accessibilityRole="alert" style={{ color: "#FCA5A5", backgroundColor: "#321D2B", padding: 10, borderRadius: 10 }}>{error}</Text>}
    {!!notice && <Text accessibilityRole="status" style={{ color: "#86EFAC", backgroundColor: "#12302C", padding: 10, borderRadius: 10 }}>{notice}</Text>}
    <View style={{ backgroundColor: "#141B31", borderColor: "#29314B", borderWidth: 1, borderRadius: 18, padding: 14, gap: 10 }}>
      <Text style={{ color: "#F7F8FF", fontWeight: "900" }}>Buat sesi</Text>
      <TextInput value={title} onChangeText={setTitle} placeholder="Judul sesi" placeholderTextColor="#747E9A" maxLength={160} style={{ color: "#F7F8FF", backgroundColor: "#0D1326", padding: 12, borderRadius: 10 }} />
      <TextInput value={description} onChangeText={setDescription} placeholder="Deskripsi (opsional)" placeholderTextColor="#747E9A" maxLength={4000} multiline style={{ color: "#F7F8FF", backgroundColor: "#0D1326", padding: 12, borderRadius: 10, minHeight: 70 }} />
      <View style={{ flexDirection: "row", gap: 8 }}>
        {(["public", "followers", "private"] as const).map(value => <Text key={value} onPress={() => setVisibility(value)} style={{ color: visibility === value ? "#11162B" : "#E1E6F8", backgroundColor: visibility === value ? "#A5B4FC" : "#29314B", padding: 9, borderRadius: 9, overflow: "hidden" }}>{value}</Text>)}
      </View>
      <Text onPress={() => !busy && void createSession()} style={{ color: "#11162B", backgroundColor: "#A5B4FC", padding: 13, borderRadius: 11, textAlign: "center", fontWeight: "900", opacity: busy || !title.trim() ? 0.45 : 1 }}>Buat Live Session</Text>
    </View>
    <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
      <Text style={{ color: "#F7F8FF", fontWeight: "900" }}>Sesi tersedia</Text>
      <Text onPress={() => !busy && void refresh(selected?.id)} style={{ color: "#A5B4FC", fontWeight: "800" }}>Muat ulang</Text>
    </View>
    {loading && <ActivityIndicator color="#A5B4FC" />}
    {items.map(item => <Text key={item.id} onPress={() => !busy && void refresh(item.id)} style={{ color: selected?.id === item.id ? "#11162B" : "#E1E6F8", backgroundColor: selected?.id === item.id ? "#A5B4FC" : "#141B31", borderWidth: 1, borderColor: "#3A4566", borderRadius: 12, padding: 12, fontWeight: "800" }}>{item.title} · {item.status}</Text>)}
    {selected && <View style={{ backgroundColor: "#141B31", borderColor: "#29314B", borderWidth: 1, borderRadius: 18, padding: 14, gap: 10 }}>
      <Text style={{ color: "#F7F8FF", fontSize: 18, fontWeight: "900" }}>{selected.title}</Text>
      <Text style={{ color: "#A5ADC3", fontSize: 12 }}>Status {selected.status} · v{selected.version} · {participants.length} peserta tercatat</Text>
      {host && selected.status === "planned" && <Text onPress={() => !busy && void transition("preparing")} style={{ color: "#11162B", backgroundColor: "#86EFAC", padding: 12, borderRadius: 10, textAlign: "center", fontWeight: "900" }}>Siapkan Stage</Text>}
      {host && active && <Text onPress={() => !busy && void transition("ended")} style={{ color: "#FCA5A5", borderColor: "#FCA5A5", borderWidth: 1, padding: 12, borderRadius: 10, textAlign: "center", fontWeight: "900" }}>Akhiri sesi</Text>}
      {!host && !joined && <Text onPress={() => !busy && void joinOrLeave(true)} style={{ color: "#11162B", backgroundColor: "#A5B4FC", padding: 12, borderRadius: 10, textAlign: "center", fontWeight: "900" }}>Gabung sesi</Text>}
      {joined && !host && <Text onPress={() => !busy && void joinOrLeave(false)} style={{ color: "#E1E6F8", borderColor: "#3A4566", borderWidth: 1, padding: 12, borderRadius: 10, textAlign: "center", fontWeight: "800" }}>Keluar sesi</Text>}
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
        <Text onPress={() => active && !busy && void stageEvent("stage_hand_raised", { raised: !handRaised }, "hand-raise:" + selected.id)} style={{ color: "#11162B", backgroundColor: "#FCD34D", padding: 10, borderRadius: 9, overflow: "hidden", opacity: active ? 1 : 0.4 }}>{handRaised ? "Turunkan tangan" : "Angkat tangan"}</Text>
        {(["like", "clap", "heart", "laugh", "wow"] as const).map(reaction => <Text key={reaction} onPress={() => active && !busy && void stageEvent("stage_reaction_added", { reaction }, "reaction:" + selected.id + ":" + reaction)} style={{ color: "#E1E6F8", backgroundColor: "#29314B", padding: 10, borderRadius: 9, overflow: "hidden", opacity: active ? 1 : 0.4 }}>{({like:"👍",clap:"👏",heart:"❤️",laugh:"😂",wow:"😮"} as const)[reaction]}</Text>)}
      </View>
      <Text style={{ color: "#A5B4FC", fontWeight: "900" }}>Riwayat Stage</Text>
      {events.slice(-12).reverse().map(event => <Text key={event.id} style={{ color: "#C0C7DA", fontSize: 12 }}>{event.event_type.replace(/_/g, " ")} · #{event.event_seq}</Text>)}
      {participants.map(item => <Text key={item.id} style={{ color: "#A5ADC3", fontSize: 12 }}>{item.participant_role} · {item.status} · {item.user_id}</Text>)}
    </View>}
  </ScrollView>;
}

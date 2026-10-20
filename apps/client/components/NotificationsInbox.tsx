import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";
import type { Session } from "@supabase/supabase-js";

type NotificationItem = {
  id: string; category: string; event_key: string; title: string; body: string;
  delivery_state: "queued" | "delivered" | "failed" | "suppressed";
  read_at: string | null; created_at: string;
};
type InboxResponse = { items: NotificationItem[]; unread_count: number };
const apiBase = (process.env.EXPO_PUBLIC_API_BASE_URL || (__DEV__ ? "http://localhost:8000" : "https://api.allpha.web.id")).replace(/\/$/, "");

export function NotificationsInbox({ session }: { session: Session }) {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const api = useCallback(async <T,>(path: string, init: RequestInit = {}): Promise<T> => {
    const response = await fetch(apiBase + path, {
      ...init,
      headers: { Authorization: "Bearer " + session.access_token, "Content-Type": "application/json", ...(init.headers || {}) },
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body?.detail?.message || body?.error?.message || "Permintaan notifikasi gagal (" + response.status + ").");
    return body as T;
  }, [session.access_token]);

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try { const result = await api<InboxResponse>("/v1/notifications?limit=100"); setItems(result.items || []); setUnreadCount(result.unread_count || 0); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Notifikasi tidak dapat dimuat."); }
    finally { setLoading(false); }
  }, [api]);

  useEffect(() => { void load(); }, [load]);

  async function markRead(item: NotificationItem) {
    if (item.read_at) return;
    setBusyId(item.id); setError(""); setNotice("");
    try {
      await api("/v1/notifications/" + encodeURIComponent(item.id) + "/read", { method: "PATCH", body: "{}" });
      setItems(rows => rows.map(row => row.id === item.id ? { ...row, read_at: new Date().toISOString() } : row));
      setUnreadCount(value => Math.max(0, value - 1));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Status baca tidak dapat disimpan."); }
    finally { setBusyId(null); }
  }

  async function markAllRead() {
    setBusyId("all"); setError(""); setNotice("");
    try {
      const result = await api<{ updated_count: number }>("/v1/notifications/read-all", { method: "POST", body: "{}" });
      setItems(rows => rows.map(row => row.read_at ? row : { ...row, read_at: new Date().toISOString() }));
      setUnreadCount(0); setNotice(result.updated_count + " notifikasi ditandai sudah dibaca.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Notifikasi tidak dapat ditandai sudah dibaca."); }
    finally { setBusyId(null); }
  }

  return <ScrollView contentContainerStyle={{ padding: 16, gap: 12 }}>
    <Text style={{ color: "#A5B4FC", fontSize: 12, fontWeight: "700", letterSpacing: 1.4 }}>ALLPHA UNIVERSE</Text>
    <Text accessibilityRole="header" style={{ color: "#F8FAFC", fontSize: 24, fontWeight: "700" }}>Notifikasi</Text>
    <Text style={{ color: "#CBD5E1" }}>{unreadCount} belum dibaca</Text>
    <View style={{ flexDirection: "row", gap: 8 }}>
      <Pressable accessibilityRole="button" onPress={() => void load()} disabled={loading} style={{ padding: 10, borderWidth: 1, borderColor: "#334155", borderRadius: 10 }}><Text style={{ color: "#E2E8F0" }}>Muat ulang</Text></Pressable>
      <Pressable accessibilityRole="button" onPress={() => void markAllRead()} disabled={loading || busyId !== null || unreadCount === 0} style={{ padding: 10, backgroundColor: "#6366F1", borderRadius: 10, opacity: unreadCount === 0 ? 0.5 : 1 }}><Text style={{ color: "white", fontWeight: "600" }}>Baca semua</Text></Pressable>
    </View>
    {error ? <Text accessibilityRole="alert" style={{ color: "#FDA4AF" }}>{error}</Text> : null}
    {notice ? <Text accessibilityRole="text" style={{ color: "#86EFAC" }}>{notice}</Text> : null}
    {loading ? <ActivityIndicator color="#A5B4FC" /> : items.length === 0 ? <View style={{ padding: 20, borderWidth: 1, borderStyle: "dashed", borderColor: "#475569", borderRadius: 14 }}><Text style={{ color: "#F8FAFC", fontWeight: "600" }}>Belum ada notifikasi</Text><Text style={{ color: "#94A3B8", marginTop: 6 }}>Notifikasi baru akan muncul di sini setelah dibuat oleh layanan Allpha.</Text></View> :
      items.map(item => <View key={item.id} style={{ padding: 14, borderRadius: 14, borderWidth: 1, borderColor: item.read_at ? "#334155" : "#818CF8", backgroundColor: item.read_at ? "#111827" : "#1E1B4B", gap: 8 }}>
        <Text style={{ color: "#F8FAFC", fontSize: 16, fontWeight: "700" }}>{item.title}</Text>
        {item.body ? <Text style={{ color: "#CBD5E1", lineHeight: 21 }}>{item.body}</Text> : null}
        <Text style={{ color: "#94A3B8", fontSize: 12 }}>{item.category.replace(/_/g, " ")} · {new Date(item.created_at).toLocaleString("id-ID")} · {item.delivery_state}</Text>
        {!item.read_at ? <Pressable accessibilityRole="button" onPress={() => void markRead(item)} disabled={busyId !== null} style={{ alignSelf: "flex-start", paddingHorizontal: 12, paddingVertical: 8, borderWidth: 1, borderColor: "#475569", borderRadius: 9 }}><Text style={{ color: "#E0E7FF" }}>{busyId === item.id ? "Menyimpan…" : "Tandai dibaca"}</Text></Pressable> : <Text style={{ color: "#64748B", fontSize: 12 }}>Sudah dibaca</Text>}
      </View>)}
  </ScrollView>;
}

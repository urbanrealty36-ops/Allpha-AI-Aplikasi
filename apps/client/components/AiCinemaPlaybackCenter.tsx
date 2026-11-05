import React, { useEffect, useState } from "react";
import { ActivityIndicator, Linking, Pressable, Text, View } from "react-native";

const apiBase = (process.env.EXPO_PUBLIC_API_BASE_URL || "https://api.allpha.web.id").replace(/\/$/, "");
type Title = { id: string; title: string };
type Episode = { id: string; episode_number: number; title: string; synopsis?: string | null; is_free_preview: boolean; locked: boolean; playback_url?: string | null };
type Playback = { title: { id: string; title: string; maturity_rating: string }; episodes: Episode[]; premium_entitled: boolean };

export function AiCinemaPlaybackCenter({ getAccessToken }: { getAccessToken?: () => Promise<string> }) {
  const [titles, setTitles] = useState<Title[]>([]);
  const [selected, setSelected] = useState<Playback | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    void fetch(apiBase + "/v1/cinema/catalog?limit=24", { cache: "no-store" })
      .then(async response => { if (!response.ok) throw new Error("Katalog AI Cinema tidak tersedia."); return response.json(); })
      .then(data => { if (active) setTitles(Array.isArray(data?.items) ? data.items.map((item: any) => ({ id: item.id, title: item.title })) : []); })
      .catch(cause => { if (active) setError(cause instanceof Error ? cause.message : "Katalog tidak dapat dimuat."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  async function openTitle(title: Title) {
    setBusy(title.id); setError(""); setSelected(null);
    try {
      let token: string | null = null;
      if (getAccessToken) { try { token = await getAccessToken(); } catch { token = null; } }
      const response = await fetch(apiBase + "/v1/cinema/titles/" + encodeURIComponent(title.id) + "/playback", {
        cache: "no-store", headers: token ? { Authorization: "Bearer " + token } : {},
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload?.detail?.message || "Playback tidak tersedia.");
      setSelected(payload as Playback);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Playback tidak tersedia."); }
    finally { setBusy(null); }
  }

  return <View style={{ gap: 13 }}>
    <Text style={{ color: "#A5B4FC", fontSize: 11, fontWeight: "800", letterSpacing: 2 }}>AI CINEMA · WATCH</Text>
    <Text style={{ color: "#F7F8FF", fontSize: 22, fontWeight: "800" }}>Film & episode</Text>
    <Text style={{ color: "#A5ADC3", fontSize: 13 }}>Free preview dan Premium playback diperiksa melalui entitlement server.</Text>
    {error ? <Text accessibilityRole="alert" style={{ color: "#FCA5A5", fontSize: 13 }}>{error}</Text> : null}
    {loading ? <ActivityIndicator color="#A5B4FC"/> : titles.length ? titles.map(title => <Pressable key={title.id} onPress={() => void openTitle(title)} disabled={busy !== null} style={{ backgroundColor: "#141B31", borderWidth: 1, borderColor: "#29314B", borderRadius: 15, padding: 14, flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
      <View style={{ flex: 1 }}><Text style={{ color: "#F7F8FF", fontWeight: "700" }}>{title.title}</Text><Text style={{ color: "#A5ADC3", fontSize: 11, marginTop: 3 }}>Katalog published · rights cleared</Text></View>
      <Text style={{ color: "#A5B4FC", fontWeight: "800", fontSize: 12 }}>{busy === title.id ? "Memuat…" : "Episode →"}</Text>
    </Pressable>) : <Text style={{ color: "#A5ADC3", fontSize: 13 }}>Belum ada judul yang diterbitkan.</Text>}
    {selected ? <View style={{ backgroundColor: "#141B31", borderWidth: 1, borderColor: "#29314B", borderRadius: 16, padding: 14, gap: 10 }}>
      <Text style={{ color: "#F7F8FF", fontWeight: "800", fontSize: 17 }}>{selected.title.title}</Text>
      <Text style={{ color: "#A5ADC3", fontSize: 11 }}>Maturity: {selected.title.maturity_rating} · {selected.premium_entitled ? "Premium aktif" : "Free preview"}</Text>
      {selected.episodes.map(episode => <View key={episode.id} style={{ borderTopWidth: 1, borderTopColor: "#29314B", paddingTop: 10, gap: 5 }}>
        <Text style={{ color: "#F7F8FF", fontWeight: "600" }}>Episode {episode.episode_number}: {episode.title}</Text>
        <Text style={{ color: "#A5ADC3", fontSize: 10 }}>{episode.is_free_preview ? "FREE PREVIEW" : "PREMIUM"}</Text>
        {episode.locked ? <Pressable onPress={() => void Linking.openURL("https://allpha.web.id/billing")}><Text style={{ color: "#A5B4FC", fontSize: 12, textDecorationLine: "underline" }}>Terkunci · Lihat paket Premium</Text></Pressable> : episode.playback_url ? <Pressable onPress={() => void Linking.openURL(episode.playback_url!)}><Text style={{ color: "#86EFAC", fontSize: 12, fontWeight: "800" }}>Putar episode ↗</Text></Pressable> : <Text style={{ color: "#FBBF24", fontSize: 11 }}>Media belum siap.</Text>}
        {episode.synopsis ? <Text style={{ color: "#A5ADC3", fontSize: 11 }}>{episode.synopsis}</Text> : null}
      </View>)}
      <Text style={{ color: "#747E9A", fontSize: 10 }}>URL media bersifat sementara. Kebijakan wilayah, maturity, dan concurrent streams masih menunggu persetujuan.</Text>
    </View> : null}
  </View>;
}

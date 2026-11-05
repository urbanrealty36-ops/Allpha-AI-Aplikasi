import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Platform, Pressable, Text, TextInput, View } from "react-native";

type DraftTitle = {
  id: string;
  title: string;
  genre: string;
  synopsis: string;
  status: string;
  updated_at: string;
};
type DraftEpisode = {
  id: string;
  title_id: string;
  episode_number: number;
  title: string;
  synopsis: string;
  status: string;
  media_id?: string | null;
};
type Props = { getAccessToken: () => Promise<string | null> };
type CreatorStatus = { generation: string; generation_jobs: string; billing: string; playback_entitlement: string };
type ReadyMedia = { id: string; filename: string; media_type: string; size_bytes: number };

const API_BASE = (process.env.EXPO_PUBLIC_API_BASE_URL || (__DEV__
  ? (Platform.OS === "android" ? "http://10.0.2.2:8000" : "http://localhost:8000")
  : "https://api.allpha.web.id")).replace(/\/$/, "");

async function request<T>(getAccessToken: Props["getAccessToken"], path: string, init: RequestInit = {}): Promise<T> {
  const token = await getAccessToken();
  if (!token) throw new Error("Sesi berakhir. Silakan masuk kembali.");
  const response = await fetch(API_BASE + path, {
    ...init,
    cache: "no-store",
    headers: {
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      Authorization: "Bearer " + token,
      ...init.headers,
    },
  });
  const body = await response.json().catch(() => ({})) as {
    detail?: { message?: string };
    message?: string;
    error?: { message?: string };
  };
  if (!response.ok) {
    throw new Error(body.detail?.message || body.error?.message || body.message || "Permintaan AI Cinema gagal (HTTP " + response.status + ").");
  }
  return body as T;
}

function Action({ title, onPress, disabled = false, secondary = false }: {
  title: string; onPress: () => void; disabled?: boolean; secondary?: boolean;
}) {
  return (
    <Pressable accessibilityRole="button" accessibilityState={{ disabled }} disabled={disabled} onPress={onPress}
      style={{ borderRadius: 12, paddingVertical: 11, paddingHorizontal: 14, backgroundColor: secondary ? "#263247" : "#67E8F9", opacity: disabled ? 0.5 : 1 }}>
      <Text style={{ color: secondary ? "#E2E8F0" : "#082F49", fontWeight: "800", textAlign: "center" }}>{title}</Text>
    </Pressable>
  );
}

export function AiCinemaCreatorWorkspace({ getAccessToken }: Props) {
  const [titles, setTitles] = useState<DraftTitle[]>([]);
  const [capabilityStatus, setCapabilityStatus] = useState<CreatorStatus | null>(null);
  const [episodes, setEpisodes] = useState<DraftEpisode[]>([]);
  const [readyMedia, setReadyMedia] = useState<ReadyMedia[]>([]);
  const [selectedMediaId, setSelectedMediaId] = useState("");
  const [selectedTitleId, setSelectedTitleId] = useState("");
  const [title, setTitle] = useState("");
  const [genre, setGenre] = useState("c_drama");
  const [synopsis, setSynopsis] = useState("");
  const [episodeNumber, setEpisodeNumber] = useState("1");
  const [episodeTitle, setEpisodeTitle] = useState("");
  const [episodeSynopsis, setEpisodeSynopsis] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadTitles = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const result = await request<{ items: DraftTitle[] }>(getAccessToken, "/v1/cinema/creator/titles?limit=100");
      try { const media = await request<{ items: ReadyMedia[] }>(getAccessToken, "/v1/cinema/creator/media-ready"); setReadyMedia(Array.isArray(media.items) ? media.items : []); } catch { setReadyMedia([]); }
      try { setCapabilityStatus(await request<CreatorStatus>(getAccessToken, "/v1/cinema/creator/status")); } catch { setCapabilityStatus(null); }
      const rows = Array.isArray(result.items) ? result.items : [];
      setTitles(rows);
      setSelectedTitleId(current => rows.some(row => row.id === current) ? current : rows[0]?.id || "");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Draft film tidak dapat dimuat.");
    } finally { setLoading(false); }
  }, [getAccessToken]);

  const loadEpisodes = useCallback(async (titleId: string) => {
    if (!titleId) { setEpisodes([]); return; }
    try {
      const result = await request<{ items: DraftEpisode[] }>(getAccessToken, "/v1/cinema/creator/titles/" + encodeURIComponent(titleId) + "/episodes");
      setEpisodes(Array.isArray(result.items) ? result.items : []);
    } catch (cause) {
      setEpisodes([]);
      setError(cause instanceof Error ? cause.message : "Episode tidak dapat dimuat.");
    }
  }, [getAccessToken]);

  useEffect(() => { void loadTitles(); }, [loadTitles]);
  useEffect(() => { void loadEpisodes(selectedTitleId); }, [loadEpisodes, selectedTitleId]);

  async function createTitle() {
    if (!title.trim()) return;
    setSaving(true); setError(""); setNotice("");
    try {
      const result = await request<{ item: DraftTitle }>(getAccessToken, "/v1/cinema/creator/titles", {
        method: "POST",
        body: JSON.stringify({ title: title.trim(), genre, synopsis: synopsis.trim(), language_code: "id" }),
      });
      setTitles(current => [result.item, ...current.filter(item => item.id !== result.item.id)]);
      setSelectedTitleId(result.item.id); setTitle(""); setSynopsis("");
      setNotice("Draft film tersimpan pada akun Anda.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Draft film gagal disimpan.");
    } finally { setSaving(false); }
  }

  async function createEpisode() {
    if (!selectedTitleId || !episodeTitle.trim() || !Number.isInteger(Number(episodeNumber)) || Number(episodeNumber) < 1) return;
    setSaving(true); setError(""); setNotice("");
    try {
      const result = await request<{ item: DraftEpisode }>(getAccessToken,
        "/v1/cinema/creator/titles/" + encodeURIComponent(selectedTitleId) + "/episodes", {
          method: "POST",
          body: JSON.stringify({ episode_number: Number(episodeNumber), title: episodeTitle.trim(), synopsis: episodeSynopsis.trim(), media_id: selectedMediaId || null }),
        });
      setEpisodes(current => [...current.filter(item => item.id !== result.item.id), result.item].sort((a, b) => a.episode_number - b.episode_number));
      setEpisodeNumber(String(Number(episodeNumber) + 1)); setEpisodeTitle(""); setEpisodeSynopsis("");
      setNotice("Draft episode tersimpan.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Draft episode gagal disimpan.");
    } finally { setSaving(false); }
  }

  const field = { color: "#F8FAFC", backgroundColor: "#111827", borderColor: "#475569", borderWidth: 1, borderRadius: 12, padding: 12, marginTop: 8 } as const;
  return (
    <View style={{ gap: 14, marginTop: 16, padding: 16, borderRadius: 20, backgroundColor: "#0F172A", borderWidth: 1, borderColor: "#334155" }}>
      <View>
        <Text style={{ color: "#67E8F9", fontSize: 11, fontWeight: "900", letterSpacing: 2 }}>ENG-P13 · AI CINEMA</Text>
        <Text style={{ color: "#F8FAFC", fontSize: 22, fontWeight: "900", marginTop: 5 }}>Draft Film & Episode</Text>
        <Text style={{ color: "#CBD5E1", marginTop: 5 }}>Menggunakan kontrak FastAPI yang sama dengan Web. Draft hanya dapat diakses pemiliknya.</Text>
      </View>
      {!!error && <Text accessibilityRole="alert" style={{ color: "#FDA4AF" }}>{error}</Text>}
      {capabilityStatus && <View style={{ padding: 12, borderRadius: 12, backgroundColor: "#422006", gap: 4 }}><Text style={{ color: "#FDE68A", fontWeight: "800" }}>Status AI Cinema</Text><Text style={{ color: "#FEF3C7", fontSize: 12 }}>Generation: {capabilityStatus.generation} · Jobs: {capabilityStatus.generation_jobs} · Billing: {capabilityStatus.billing} · Entitlement: {capabilityStatus.playback_entitlement}</Text><Text style={{ color: "#FDE68A", fontSize: 12 }}>Generate dan playback premium tetap terkunci sampai policy, job, billing, serta entitlement tersedia.</Text></View>}
      {!!notice && <Text accessibilityRole="alert" style={{ color: "#86EFAC" }}>{notice}</Text>}
      <View style={{ gap: 8 }}>
        <Text style={{ color: "#E2E8F0", fontWeight: "800" }}>Buat draft film</Text>
        <TextInput accessibilityLabel="Judul film" value={title} onChangeText={setTitle} maxLength={160} placeholder="Judul film" placeholderTextColor="#94A3B8" style={field}/>
        <View style={{ gap: 8 }}>
          <Text style={{ color: "#CBD5E1", fontSize: 12, fontWeight: "700" }}>Genre film</Text>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 7 }}>
            {[
              ["c_drama", "C-Drama"], ["k_drama", "K-Drama"], ["scifi", "Sci-Fi"],
              ["romance", "Romance"], ["thriller", "Thriller"], ["animation_3d", "Animasi 3D"],
              ["documentary", "Dokumenter"], ["other", "Lainnya"],
            ].map(([value, label]) => <Pressable key={value} accessibilityRole="button" accessibilityState={{ selected: genre === value }}
              onPress={() => setGenre(value)} style={{ paddingHorizontal: 10, paddingVertical: 8, borderRadius: 20, backgroundColor: genre === value ? "#164E63" : "#1E293B", borderWidth: 1, borderColor: genre === value ? "#67E8F9" : "#334155" }}>
              <Text style={{ color: "#F8FAFC", fontSize: 12, fontWeight: "700" }}>{label}</Text>
            </Pressable>)}
          </View>
        </View>
        <TextInput accessibilityLabel="Sinopsis film" value={synopsis} onChangeText={setSynopsis} multiline maxLength={5000} placeholder="Sinopsis" placeholderTextColor="#94A3B8" style={[field, { minHeight: 84, textAlignVertical: "top" }]}/>
        <Action title={saving ? "Menyimpan…" : "Simpan draft film"} disabled={saving || !title.trim()} onPress={() => void createTitle()}/>
      </View>
      <View style={{ gap: 8 }}>
        <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
          <Text style={{ color: "#E2E8F0", fontWeight: "800" }}>Film milik saya</Text>
          <Action title={loading ? "Memuat…" : "Muat ulang"} secondary disabled={loading} onPress={() => void loadTitles()}/>
        </View>
        {loading ? <ActivityIndicator color="#67E8F9"/> : titles.length === 0
          ? <Text style={{ color: "#94A3B8" }}>Belum ada draft film.</Text>
          : titles.map(item => <Pressable key={item.id} accessibilityRole="button" accessibilityState={{ selected: selectedTitleId === item.id }}
              onPress={() => setSelectedTitleId(item.id)} style={{ padding: 12, borderRadius: 12, borderWidth: 1, borderColor: selectedTitleId === item.id ? "#67E8F9" : "#334155", backgroundColor: selectedTitleId === item.id ? "#164E63" : "#1E293B" }}>
              <Text style={{ color: "#F8FAFC", fontWeight: "800" }}>{item.title}</Text>
              <Text style={{ color: "#CBD5E1", fontSize: 12 }}>{item.genre} · {item.status}</Text>
            </Pressable>)}
      </View>
      <View style={{ gap: 8 }}>
        <Text style={{ color: "#E2E8F0", fontWeight: "800" }}>Episode {selectedTitleId ? "· film terpilih" : "· pilih film terlebih dahulu"}</Text>
        <TextInput accessibilityLabel="Nomor episode" value={episodeNumber} onChangeText={setEpisodeNumber} keyboardType="number-pad" style={field} placeholder="Nomor episode" placeholderTextColor="#94A3B8"/>
        <TextInput accessibilityLabel="Judul episode" value={episodeTitle} onChangeText={setEpisodeTitle} maxLength={160} style={field} placeholder="Judul episode" placeholderTextColor="#94A3B8"/>
        <TextInput accessibilityLabel="Sinopsis episode" value={episodeSynopsis} onChangeText={setEpisodeSynopsis} multiline maxLength={3000} style={[field, { minHeight: 72, textAlignVertical: "top" }]} placeholder="Sinopsis episode" placeholderTextColor="#94A3B8"/>
        <Text style={{ color: "#CBD5E1", fontSize: 12, fontWeight: "700" }}>Pilih media siap · scan clean</Text>
        <Pressable accessibilityRole="button" onPress={() => setSelectedMediaId("")} style={{ padding: 10, borderRadius: 10, backgroundColor: selectedMediaId ? "#1E293B" : "#164E63", borderWidth: 1, borderColor: selectedMediaId ? "#334155" : "#67E8F9" }}>
          <Text style={{ color: "#F8FAFC" }}>Simpan sebagai draft tanpa media</Text>
        </Pressable>
        {readyMedia.map(media => <Pressable key={media.id} accessibilityRole="button" accessibilityState={{ selected: selectedMediaId === media.id }} onPress={() => setSelectedMediaId(media.id)} style={{ padding: 10, borderRadius: 10, backgroundColor: selectedMediaId === media.id ? "#164E63" : "#1E293B", borderWidth: 1, borderColor: selectedMediaId === media.id ? "#67E8F9" : "#334155" }}>
          <Text style={{ color: "#F8FAFC", fontWeight: "700" }}>{selectedMediaId === media.id ? "✓ " : ""}{media.filename}</Text>
          <Text style={{ color: "#94A3B8", fontSize: 11 }}>{media.media_type} · {(media.size_bytes / 1024 / 1024).toFixed(1)} MiB</Text>
        </Pressable>)}
        {readyMedia.length === 0 && <Text style={{ color: "#94A3B8", fontSize: 12 }}>Belum ada media yang lulus processing dan scan.</Text>}
        <Action title={saving ? "Menyimpan…" : "Simpan draft episode"} disabled={saving || !selectedTitleId || !episodeTitle.trim() || !Number.isInteger(Number(episodeNumber)) || Number(episodeNumber) < 1} onPress={() => void createEpisode()}/>
        {episodes.map(item => <View key={item.id} style={{ padding: 12, borderRadius: 12, backgroundColor: "#1E293B" }}>
          <Text style={{ color: "#F8FAFC", fontWeight: "800" }}>Episode {item.episode_number} · {item.title}</Text>
          <Text style={{ color: "#CBD5E1", fontSize: 12 }}>{item.status}{item.media_id ? " · media terhubung" : " · belum ada media"}</Text>
        </View>)}
      </View>
      <Text style={{ color: "#94A3B8", fontSize: 12 }}>Generate, pembayaran, entitlement, moderasi dan publikasi tetap terkunci sampai kontrak backend serta policy yang disetujui tersedia. Media episode hanya dapat dipilih dari hasil processing dan scan clean.</Text>
    </View>
  );
}

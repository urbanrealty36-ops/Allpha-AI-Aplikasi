import React, { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { VideoView, useVideoPlayer } from "expo-video";

const apiBase = (process.env.EXPO_PUBLIC_API_BASE_URL || "https://api.allpha.web.id").replace(/\/$/, "");
type Title = { id: string; title: string };
type Episode = {
  id: string;
  episode_number: number;
  title: string;
  synopsis?: string | null;
  is_free_preview: boolean;
  locked: boolean;
  playback_url?: string | null;
};
type Playback = {
  title: { id: string; title: string; maturity_rating: string };
  episodes: Episode[];
  premium_entitled: boolean;
};
type ActivePlayback = {
  session_id: string;
  session_token: string;
  episode_id: string;
  playback_url: string;
};

function createEventId(): string {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, character => {
    const random = Math.floor(Math.random() * 16);
    return (character === "x" ? random : (random & 0x3) | 0x8).toString(16);
  });
}

function CinemaVideoPlayer({
  source,
  onTimeUpdate,
  onFinished,
}: {
  source: string;
  onTimeUpdate: (position: number) => void;
  onFinished: (position: number) => void;
}) {
  const player = useVideoPlayer(source, instance => {
    instance.timeUpdateEventInterval = 15;
    instance.play();
  });

  useEffect(() => {
    const timeSubscription = player.addListener("timeUpdate", event => {
      onTimeUpdate(event.currentTime);
    });
    const finishSubscription = player.addListener("playToEnd", () => {
      onFinished(player.currentTime);
    });
    return () => {
      timeSubscription.remove();
      finishSubscription.remove();
    };
  }, [onFinished, onTimeUpdate, player]);

  return (
    <VideoView
      player={player}
      style={{ width: "100%", aspectRatio: 16 / 9, backgroundColor: "#050816", borderRadius: 12 }}
      nativeControls
      allowsFullscreen
    />
  );
}

export function AiCinemaPlaybackCenter({ getAccessToken }: { getAccessToken?: () => Promise<string | null> }) {
  const [titles, setTitles] = useState<Title[]>([]);
  const [selected, setSelected] = useState<Playback | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [activePlayback, setActivePlayback] = useState<ActivePlayback | null>(null);
  const [lastPositionSeconds, setLastPositionSeconds] = useState(0);
  const heartbeatLock = useRef(false);
  const lastHeartbeatAt = useRef(0);

  useEffect(() => {
    let active = true;
    void fetch(apiBase + "/v1/cinema/catalog?limit=24", { cache: "no-store" })
      .then(async response => {
        if (!response.ok) throw new Error("Katalog AI Cinema tidak tersedia.");
        return response.json();
      })
      .then(data => {
        if (active) setTitles(Array.isArray(data?.items) ? data.items.map((item: any) => ({ id: item.id, title: item.title })) : []);
      })
      .catch(cause => {
        if (active) setError(cause instanceof Error ? cause.message : "Katalog tidak dapat dimuat.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  async function openTitle(title: Title) {
    if (activePlayback) return;
    setBusy(title.id);
    setError("");
    setNotice("");
    setSelected(null);
    try {
      let token: string | null = null;
      if (getAccessToken) {
        try { token = await getAccessToken(); } catch { token = null; }
      }
      const response = await fetch(apiBase + "/v1/cinema/titles/" + encodeURIComponent(title.id) + "/playback", {
        cache: "no-store",
        headers: token ? { Authorization: "Bearer " + token } : {},
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload?.detail?.message || "Playback tidak tersedia.");
      setSelected(payload as Playback);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Playback tidak tersedia.");
    } finally {
      setBusy(null);
    }
  }

  async function startEpisode(title: Playback["title"], episode: Episode) {
    if (!getAccessToken) {
      setError("Masuk untuk memulai sesi pemutaran.");
      return;
    }
    if (activePlayback) {
      setError("Selesaikan sesi pemutaran yang sedang aktif terlebih dahulu.");
      return;
    }
    setBusy(episode.id);
    setError("");
    setNotice("");
    try {
      const token = await getAccessToken();
      if (!token) throw new Error("Sesi login diperlukan untuk memulai playback.");
      const idempotencyKey = createEventId();
      const response = await fetch(apiBase + "/v1/cinema/titles/" + encodeURIComponent(title.id) + "/episodes/" + encodeURIComponent(episode.id) + "/playback-session", {
        method: "POST",
        cache: "no-store",
        headers: {
          Authorization: "Bearer " + token,
          "Content-Type": "application/json",
          "Idempotency-Key": idempotencyKey,
        },
        body: JSON.stringify({ idempotency_key: idempotencyKey }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data?.detail?.message || "Sesi pemutaran belum dapat dimulai.");
      if (!data?.session?.id || !data?.session_token || !data?.playback_url) {
        throw new Error("Server belum mengembalikan sesi dan URL playback yang lengkap.");
      }
      lastHeartbeatAt.current = Date.now();
      setLastPositionSeconds(0);
      setActivePlayback({
        session_id: data.session.id,
        session_token: data.session_token,
        episode_id: episode.id,
        playback_url: data.playback_url,
      });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Playback gagal dimulai.");
    } finally {
      setBusy(null);
    }
  }

  const sendPlaybackEvent = useCallback(async (position: number, finish = false): Promise<boolean> => {
    if (!activePlayback || heartbeatLock.current) return false;
    heartbeatLock.current = true;
    try {
      const token = await getAccessToken?.();
      if (!token) throw new Error("Sesi login berakhir; masuk kembali untuk menyimpan progres pemutaran.");
      const response = await fetch(
        apiBase + "/v1/cinema/playback-sessions/" + activePlayback.session_id + (finish ? "/finish" : "/heartbeat"),
        {
          method: "POST",
          cache: "no-store",
          headers: {
            Authorization: "Bearer " + token,
            "Content-Type": "application/json",
            "X-Cinema-Session-Token": activePlayback.session_token,
          },
          body: JSON.stringify({ event_id: createEventId(), position_seconds: Math.max(0, Math.floor(position)) }),
        },
      );
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload?.detail?.message || "Progres pemutaran belum dikonfirmasi oleh server.");
      setError("");
      if (finish) {
        setActivePlayback(null);
        setLastPositionSeconds(0);
        setNotice("Sesi pemutaran selesai dan statusnya telah dikirim ke server.");
      } else {
        lastHeartbeatAt.current = Date.now();
      }
      return true;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Progres pemutaran belum dapat disimpan.");
      return false;
    } finally {
      heartbeatLock.current = false;
    }
  }, [activePlayback, getAccessToken]);

  const handleTimeUpdate = useCallback((position: number) => {
    setLastPositionSeconds(position);
    if (Date.now() - lastHeartbeatAt.current >= 14000) void sendPlaybackEvent(position);
  }, [sendPlaybackEvent]);

  const handlePlaybackFinished = useCallback((position: number) => {
    void sendPlaybackEvent(position, true);
  }, [sendPlaybackEvent]);

  const finishPlayback = useCallback(() => {
    void sendPlaybackEvent(lastPositionSeconds, true);
  }, [lastPositionSeconds, sendPlaybackEvent]);

  return (
    <View style={{ gap: 13 }}>
      <Text style={{ color: "#A5B4FC", fontSize: 11, fontWeight: "800", letterSpacing: 2 }}>AI CINEMA · WATCH</Text>
      <Text style={{ color: "#F7F8FF", fontSize: 22, fontWeight: "800" }}>Film & episode</Text>
      <Text style={{ color: "#A5ADC3", fontSize: 13 }}>Sesi pemutaran, entitlement, dan progres tontonan dikendalikan oleh FastAPI.</Text>
      {error ? <Text accessibilityRole="alert" style={{ color: "#FCA5A5", fontSize: 13 }}>{error}</Text> : null}
      {notice ? <Text accessibilityLiveRegion="polite" style={{ color: "#86EFAC", fontSize: 12 }}>{notice}</Text> : null}
      {loading ? <ActivityIndicator color="#A5B4FC" /> : titles.length ? titles.map(title => (
        <Pressable
          key={title.id}
          onPress={() => void openTitle(title)}
          disabled={busy !== null || activePlayback !== null}
          style={{ backgroundColor: "#141B31", borderWidth: 1, borderColor: "#29314B", borderRadius: 15, padding: 14, flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 10, opacity: activePlayback ? 0.55 : 1 }}
        >
          <View style={{ flex: 1 }}>
            <Text style={{ color: "#F7F8FF", fontWeight: "700" }}>{title.title}</Text>
            <Text style={{ color: "#A5ADC3", fontSize: 11, marginTop: 3 }}>Katalog published · rights cleared</Text>
          </View>
          <Text style={{ color: "#A5B4FC", fontWeight: "800", fontSize: 12 }}>{busy === title.id ? "Memuat…" : "Episode →"}</Text>
        </Pressable>
      )) : <Text style={{ color: "#A5ADC3", fontSize: 13 }}>Belum ada judul yang diterbitkan.</Text>}

      {selected ? (
        <View style={{ backgroundColor: "#141B31", borderWidth: 1, borderColor: "#29314B", borderRadius: 16, padding: 14, gap: 10 }}>
          <Text style={{ color: "#F7F8FF", fontWeight: "800", fontSize: 17 }}>{selected.title.title}</Text>
          <Text style={{ color: "#A5ADC3", fontSize: 11 }}>Maturity: {selected.title.maturity_rating} · {selected.premium_entitled ? "Premium aktif" : "Free preview"}</Text>
          {selected.episodes.map(episode => (
            <View key={episode.id} style={{ borderTopWidth: 1, borderTopColor: "#29314B", paddingTop: 10, gap: 5 }}>
              <Text style={{ color: "#F7F8FF", fontWeight: "600" }}>Episode {episode.episode_number}: {episode.title}</Text>
              <Text style={{ color: "#A5ADC3", fontSize: 10 }}>{episode.is_free_preview ? "FREE PREVIEW" : "PREMIUM"}</Text>
              <Pressable disabled={busy !== null || activePlayback !== null} onPress={() => void startEpisode(selected.title, episode)}>
                <Text style={{ color: "#A5B4FC", fontSize: 12, fontWeight: "800" }}>
                  {busy === episode.id ? "Menyiapkan sesi…" : episode.is_free_preview ? "Mulai Preview" : "Periksa Premium & Putar"}
                </Text>
              </Pressable>
              {episode.synopsis ? <Text style={{ color: "#A5ADC3", fontSize: 11 }}>{episode.synopsis}</Text> : null}
            </View>
          ))}
        </View>
      ) : null}

      {activePlayback ? (
        <View style={{ backgroundColor: "#141B31", borderWidth: 1, borderColor: "#29314B", borderRadius: 16, padding: 12, gap: 10 }}>
          <Text style={{ color: "#F7F8FF", fontWeight: "800", fontSize: 15 }}>Pemutaran aktif</Text>
          <CinemaVideoPlayer
            source={activePlayback.playback_url}
            onTimeUpdate={handleTimeUpdate}
            onFinished={handlePlaybackFinished}
          />
          <Text style={{ color: "#A5ADC3", fontSize: 11 }}>
            Progres tersimpan berkala melalui heartbeat server · posisi {Math.floor(lastPositionSeconds)} detik
          </Text>
          <Pressable onPress={finishPlayback} disabled={busy !== null} style={{ borderRadius: 12, padding: 12, backgroundColor: "#263247" }}>
            <Text style={{ color: "#E2E8F0", textAlign: "center", fontWeight: "800" }}>Akhiri sesi pemutaran</Text>
          </Pressable>
        </View>
      ) : null}
    </View>
  );
}

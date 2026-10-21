import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { CanonicalNativeWorldRenderer } from "./CanonicalNativeWorldRenderer";

const API = (process.env.EXPO_PUBLIC_API_BASE_URL || "https://api.allpha.web.id").replace(/\/$/, "");
type Theme = { theme_key: string; display_name: string; description?: string; active_version: number; updated_at?: string };

export function SpatialThemeCatalogScreen() {
  const [themes, setThemes] = useState<Theme[]>([]);
  const [selected, setSelected] = useState<Theme | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);

  const load = useCallback(async (signal: AbortSignal) => {
    setLoading(true); setError("");
    try {
      const response = await fetch(API + "/v1/spatial/themes?limit=100&offset=0", { signal, headers: { Accept: "application/json" } });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body?.detail?.message || "Katalog Theme belum tersedia (" + response.status + ").");
      setThemes(Array.isArray(body.items) ? body.items : []);
    } catch (cause) {
      if (!signal.aborted) { setThemes([]); setError(cause instanceof Error ? cause.message : "Katalog Theme gagal dimuat."); }
    } finally { if (!signal.aborted) setLoading(false); }
  }, []);

  useEffect(() => { const controller = new AbortController(); void load(controller.signal); return () => controller.abort(); }, [load, retry]);

  return <View style={{ borderWidth: 1, borderColor: "#27334E", borderRadius: 16, padding: 14, gap: 10 }}>
    <Text style={{ color: "#F8FAFC", fontSize: 18, fontWeight: "700" }}>Theme Universe</Text>
    <Text style={{ color: "#AAB4CA", fontSize: 12 }}>Daftar hanya menampilkan Theme dengan versi publik aktif.</Text>
    {loading ? <ActivityIndicator color="#A5B4FC" /> : error ? <View style={{ gap: 8 }}>
      <Text accessibilityRole="alert" style={{ color: "#FCA5A5" }}>{error}</Text>
      <Pressable accessibilityRole="button" onPress={() => setRetry(value => value + 1)}><Text style={{ color: "#A5B4FC", paddingVertical: 8 }}>Coba lagi</Text></Pressable>
    </View> : themes.length === 0 ? <Text style={{ color: "#AAB4CA" }}>Belum ada Theme yang dipublikasikan.</Text> : <View style={{ gap: 8 }}>
      {themes.map(theme => <Pressable key={theme.theme_key} accessibilityRole="button" onPress={() => setSelected(theme)} style={{ borderWidth: 1, borderColor: selected?.theme_key === theme.theme_key ? "#818CF8" : "#3C4967", borderRadius: 10, padding: 12, backgroundColor: "#111A2D", gap: 4 }}>
        <Text style={{ color: "#F8FAFC", fontWeight: "600" }}>{theme.display_name}</Text>
        <Text style={{ color: "#A5B4FC", fontSize: 11 }}>{theme.theme_key} · v{theme.active_version}</Text>
        {!!theme.description && <Text style={{ color: "#AAB4CA", fontSize: 12 }}>{theme.description}</Text>}
      </Pressable>)}
    </View>}
    {selected && <View style={{ gap: 8, marginTop: 6 }}>
      <Text style={{ color: "#F8FAFC", fontWeight: "600" }}>Preview · {selected.display_name}</Text>
      <CanonicalNativeWorldRenderer themeKey={selected.theme_key} />
      <Pressable accessibilityRole="button" onPress={() => setSelected(null)}><Text style={{ color: "#A5B4FC", paddingVertical: 8 }}>Tutup preview</Text></Pressable>
    </View>}
  </View>;
}

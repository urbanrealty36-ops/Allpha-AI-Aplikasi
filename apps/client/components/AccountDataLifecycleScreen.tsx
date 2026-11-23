import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Linking, Pressable, Text, TextInput, View, type ViewStyle } from "react-native";

type ExportJob = { id: string; status: string; requested_at: string; progress_percent?: number; progress_stage?: string; expires_at?: string | null; file_size_bytes?: number | null; error_code?: string | null };
type DeletionRequest = { id: string; status: string; requested_at: string; policy_version?: string | null };
type Props = { apiBase: string; getAccessToken: () => Promise<string> };

function progressLabel(stage?: string) {
  const values: Record<string, string> = {
    claimed: "Worker mengambil job", snapshot: "Mengumpulkan data akun",
    compress: "Menyusun arsip", upload: "Mengunggah arsip privat",
    publishing: "Menyimpan hasil ekspor",
  };
  return values[stage ?? ""] || "Menunggu antrean";
}

function label(status: string) {
  const values: Record<string, string> = {
    queued: "Dalam antrean", running: "Sedang diproses", succeeded: "Siap diunduh",
    failed: "Gagal diproses", cancelled: "Dibatalkan", expired: "Kedaluwarsa",
    awaiting_policy: "Menunggu kebijakan retensi", scheduled: "Terjadwal",
    processing: "Sedang diproses", blocked_legal_hold: "Ditahan untuk kewajiban hukum",
    completed: "Selesai",
  };
  return values[status] || status;
}

export function AccountDataLifecycleScreen({ apiBase, getAccessToken }: Props) {
  const [exports, setExports] = useState<ExportJob[]>([]);
  const [deletions, setDeletions] = useState<DeletionRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");

  const request = useCallback(async (path: string, init: RequestInit = {}) => {
    const token = await getAccessToken();
    const headers = new Headers(init.headers);
    headers.set("Authorization", "Bearer " + token);
    headers.set("Accept", "application/json");
    if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    const response = await fetch(apiBase + path, { ...init, headers, cache: "no-store" });
    if (!response.ok) {
      let detail = "Permintaan gagal (" + response.status + ").";
      try {
        const body = await response.json();
        detail = body?.detail?.message ?? body?.error?.message ?? detail;
      } catch { /* use stable status fallback */ }
      throw new Error(detail);
    }
    return response.status === 204 ? null : response.json();
  }, [apiBase, getAccessToken]);

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const [exportPayload, deletionPayload] = await Promise.all([
        request("/v1/me/export-requests"),
        request("/v1/me/deletion-requests"),
      ]);
      setExports(Array.isArray(exportPayload?.items) ? exportPayload.items : []);
      setDeletions(Array.isArray(deletionPayload?.items) ? deletionPayload.items : []);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Data akun tidak dapat dimuat.");
    } finally { setLoading(false); }
  }, [request]);

  useEffect(() => { void load(); }, [load]);

  async function createExport() {
    setBusy(true); setError(""); setMessage("");
    try {
      const key = "native-account-export-" + Date.now() + "-" + Math.random().toString(36).slice(2, 12);
      const payload = await request("/v1/me/export-requests", { method: "POST", headers: { "Idempotency-Key": key } });
      setMessage("Permintaan ekspor " + payload.export.id + " masuk antrean.");
      await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Ekspor tidak dapat diminta."); }
    finally { setBusy(false); }
  }

  async function downloadExport(id: string) {
    setBusy(true); setError("");
    try {
      const payload = await request("/v1/me/export-requests/" + encodeURIComponent(id) + "/download");
      if (typeof payload?.download_url !== "string" || !payload.download_url) throw new Error("Tautan unduhan tidak tersedia.");
      await Linking.openURL(payload.download_url);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Unduhan tidak dapat dibuka."); }
    finally { setBusy(false); }
  }

  async function createDeletion() {
    setBusy(true); setError(""); setMessage("");
    try {
      const payload = await request("/v1/me/deletion-requests", {
        method: "POST",
        body: JSON.stringify({ password, confirmation_phrase: confirmation }),
      });
      setPassword(""); setConfirmation("");
      setMessage(payload.message || "Permintaan penghapusan akun tercatat.");
      await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Permintaan penghapusan tidak dapat dicatat."); }
    finally { setBusy(false); }
  }

  async function cancelDeletion(id: string) {
    setBusy(true); setError(""); setMessage("");
    try {
      await request("/v1/me/deletion-requests/" + encodeURIComponent(id) + "/cancel", { method: "POST" });
      setMessage("Permintaan penghapusan berhasil dibatalkan.");
      await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Permintaan tidak dapat dibatalkan."); }
    finally { setBusy(false); }
  }

  const openDeletion = deletions.find(item => ["awaiting_policy", "scheduled", "processing", "blocked_legal_hold"].includes(item.status));
  const button = (title: string, onPress: () => void, disabled = false, danger = false) => (
    <Pressable accessibilityRole="button" accessibilityState={{ disabled }} disabled={disabled} onPress={onPress}
      style={{ alignSelf: "flex-start", borderRadius: 12, paddingVertical: 11, paddingHorizontal: 15, backgroundColor: danger ? "#7F1D35" : "#263A66", opacity: disabled ? 0.55 : 1 }}>
      <Text style={{ color: "#FFFFFF", fontWeight: "700" }}>{title}</Text>
    </Pressable>
  );
  const field = { borderWidth: 1, borderColor: "#39445F", borderRadius: 10, padding: 12, color: "#FFFFFF", backgroundColor: "#171F34", marginBottom: 10 };

  return (
    <View style={{ gap: 14, paddingBottom: 28 }}>
      <Text style={{ color: "#FFFFFF", fontSize: 20, fontWeight: "800" }}>Ekspor & penghapusan data</Text>
      <Text style={{ color: "#AAB4CC", lineHeight: 20 }}>Permintaan diproses backend Allpha. Arsip akun disimpan privat dan tautan unduhan bersifat sementara.</Text>
      {!!error && <Text accessibilityRole="alert" style={{ color: "#FF9AAB" }}>{error}</Text>}
      {!!message && <Text accessibilityLiveRegion="polite" style={{ color: "#8FE0B2" }}>{message}</Text>}

      <View style={{ backgroundColor: "#111A2D", borderRadius: 16, padding: 14, gap: 12 }}>
        <Text style={{ color: "#FFFFFF", fontSize: 16, fontWeight: "700" }}>Salinan data akun</Text>
        <Text style={{ color: "#AAB4CC" }}>Buat arsip data yang dimiliki akun Anda. Status selesai hanya ditampilkan setelah worker mengonfirmasi file.</Text>
        {button(busy ? "Memproses…" : "Minta ekspor data", () => void createExport(), busy)}
        {loading ? <ActivityIndicator color="#A5B4FC"/> : exports.length === 0 ? <Text style={{ color: "#AAB4CC" }}>Belum ada permintaan ekspor.</Text> : exports.map(item => (
          <View key={item.id} style={{ borderTopWidth: 1, borderTopColor: "#303A52", paddingTop: 10, gap: 6 }}>
            <Text style={{ color: "#FFFFFF", fontWeight: "700" }}>{label(item.status)}</Text>
            <Text style={{ color: "#AAB4CC" }}>{new Date(item.requested_at).toLocaleString("id-ID")}{item.file_size_bytes ? " · " + Math.ceil(item.file_size_bytes / 1024) + " KB" : ""}{item.expires_at ? " · Kedaluwarsa " + new Date(item.expires_at).toLocaleString("id-ID") : ""}</Text>
            {item.status === "running" && <>
              <Text accessibilityLiveRegion="polite" style={{ color: "#AAB4CC" }}>{progressLabel(item.progress_stage)} · {item.progress_percent ?? 5}%</Text>
              <View accessibilityRole="progressbar" accessibilityValue={{ min: 0, max: 100, now: item.progress_percent ?? 5 }} style={{ height: 6, borderRadius: 6, backgroundColor: "#303A52", overflow: "hidden" }}>
                <View style={{ height: 6, width: `${Math.max(5, Math.min(100, item.progress_percent ?? 5))}%` as unknown as ViewStyle["width"], backgroundColor: "#A5B4FC" }} />
              </View>
            </>}
            {!!item.error_code && <Text style={{ color: "#FF9AAB" }}>{item.error_code}</Text>}
            {item.status === "succeeded" && button("Unduh arsip", () => void downloadExport(item.id), busy)}
          </View>
        ))}
        {button("Muat ulang status", () => void load(), loading || busy)}
      </View>

      <View style={{ backgroundColor: "#111A2D", borderRadius: 16, padding: 14, gap: 12 }}>
        <Text style={{ color: "#FFFFFF", fontSize: 16, fontWeight: "700" }}>Permintaan penghapusan akun</Text>
        <Text style={{ color: "#AAB4CC", lineHeight: 20 }}>Penghapusan permanen menunggu kebijakan retensi per kelas data dan pemeriksaan legal-hold yang disetujui. Permintaan tidak menghapus data secara langsung.</Text>
        {deletions.map(item => (
          <View key={item.id} style={{ borderTopWidth: 1, borderTopColor: "#303A52", paddingTop: 10, gap: 6 }}>
            <Text style={{ color: "#FFFFFF", fontWeight: "700" }}>{label(item.status)}</Text>
            <Text style={{ color: "#AAB4CC" }}>Diminta: {new Date(item.requested_at).toLocaleString("id-ID")}{item.policy_version ? " · " + item.policy_version : ""}</Text>
            {item.status === "awaiting_policy" && button("Batalkan permintaan", () => void cancelDeletion(item.id), busy)}
          </View>
        ))}
        {openDeletion ? <Text style={{ color: "#F6C978" }}>Masih ada permintaan aktif. Batalkan terlebih dahulu jika ingin mengajukan ulang.</Text> : <>
          <Text style={{ color: "#AAB4CC" }}>Kata sandi saat ini</Text>
          <TextInput value={password} onChangeText={setPassword} secureTextEntry autoCapitalize="none" style={field} accessibilityLabel="Kata sandi saat ini"/>
          <Text style={{ color: "#AAB4CC" }}>Ketik persis: HAPUS AKUN ALLPHA SAYA</Text>
          <TextInput value={confirmation} onChangeText={setConfirmation} autoCapitalize="characters" style={field} accessibilityLabel="Frasa konfirmasi penghapusan"/>
          {button(busy ? "Memproses…" : "Ajukan penghapusan akun", () => void createDeletion(), busy || !password || confirmation !== "HAPUS AKUN ALLPHA SAYA", true)}
        </>}
      </View>
    </View>
  );
}

import React, { useCallback, useState } from "react";
import { ActivityIndicator, Text, TextInput, View, Pressable, StyleSheet } from "react-native";

type Content = { id: string; version: number; status: string; moderation_status: string };
type Appeal = { id: string; submitted_version: number; reason: string; status: string; decision_reason?: string | null; decided_at?: string | null; created_at: string };
const API = (process.env.EXPO_PUBLIC_API_BASE_URL || "https://api.allpha.web.id").replace(/\/$/, "");

export function ContentAppealsPanel({ accessToken, contentItems }: { accessToken: string; contentItems: Content[] }) {
  const [target, setTarget] = useState<Content | null>(null);
  const [reason, setReason] = useState("");
  const [items, setItems] = useState<Appeal[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const request = useCallback(async (path: string, init: RequestInit = {}) => {
    const response = await fetch(API + path, { ...init, headers: {
      Authorization: "Bearer " + accessToken, Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}), ...(init.headers || {}),
    }});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error?.message || data.detail?.message || "Permintaan banding gagal.");
    return data;
  }, [accessToken]);

  async function load(content: Content) {
    setTarget(content); setBusy(true); setError(""); setNotice("");
    try {
      const data = await request("/v1/content/" + encodeURIComponent(content.id) + "/appeals") as { items?: Appeal[] };
      setItems(data.items || []);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Riwayat banding gagal dimuat."); }
    finally { setBusy(false); }
  }

  async function submit() {
    if (!target || reason.trim().length < 8) { setError("Alasan banding minimal 8 karakter."); return; }
    setBusy(true); setError(""); setNotice("");
    try {
      await request("/v1/content/" + encodeURIComponent(target.id) + "/appeals", {
        method: "POST", body: JSON.stringify({ reason: reason.trim(), expected_version: target.version }),
      });
      setReason(""); setNotice("Banding dikirim dan menunggu pemeriksaan manusia.");
      const data = await request("/v1/content/" + encodeURIComponent(target.id) + "/appeals") as { items?: Appeal[] };
      setItems(data.items || []);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Pengajuan banding gagal."); }
    finally { setBusy(false); }
  }

  const eligible = target?.status === "failed" && target.moderation_status === "rejected";
  const pending = items.some(item => item.status === "pending");
  return <View style={styles.panel}>
    <Text style={styles.kicker}>WP-04 · CONTENT APPEALS</Text>
    <Text style={styles.heading}>Banding moderasi</Text>
    <Text style={styles.copy}>Banding hanya tersedia untuk konten yang ditolak. Persetujuan banding mengembalikan konten ke antrean review, bukan langsung mempublikasikannya.</Text>
    {contentItems.length === 0 ? <Text style={styles.copy}>Belum ada konten untuk ditampilkan.</Text> : contentItems.map(item =>
      <Pressable key={item.id} onPress={() => void load(item)} style={[styles.row, target?.id === item.id && styles.selected]}>
        <Text style={styles.copy} numberOfLines={2}>Konten {item.id.slice(0, 8)} · versi {item.version}</Text>
        <Text style={styles.meta}>{item.status}/{item.moderation_status} · ketuk untuk melihat riwayat banding</Text>
      </Pressable>
    )}
    {target && <View style={styles.form}>
      {eligible && !pending && <><Text style={styles.label}>Alasan banding</Text>
      <TextInput value={reason} onChangeText={setReason} multiline maxLength={2000}
        accessibilityLabel="Alasan banding moderasi" placeholder="Jelaskan alasan banding (8–2000 karakter)"
        placeholderTextColor="#8993AD" style={styles.input}/>
      <Pressable disabled={busy || reason.trim().length < 8} onPress={() => void submit()} style={[styles.button,(busy || reason.trim().length<8)&&styles.disabled]}>
        <Text style={styles.buttonText}>{busy ? "Memproses…" : "Kirim banding"}</Text>
      </Pressable></>}{pending && <Text style={styles.meta}>Banding sedang menunggu keputusan. Pengajuan baru belum tersedia.</Text>}
      <Pressable disabled={busy} onPress={() => void load(target)} style={styles.secondary}><Text style={styles.copy}>Muat ulang riwayat</Text></Pressable>
      {busy && <ActivityIndicator color="#A5B4FC"/>}
      {!!error && <Text accessibilityRole="alert" style={styles.error}>{error}</Text>}
      {!!notice && <Text accessibilityRole="status" style={styles.notice}>{notice}</Text>}
      {items.length===0 ? <Text style={styles.meta}>Belum ada riwayat banding.</Text> : items.map(item=><View key={item.id} style={styles.row}>
        <Text style={styles.copy}>Status: {item.status} · versi {item.submitted_version}</Text>
        <Text style={styles.meta}>{item.reason}</Text>
        {!!item.decision_reason && <Text style={styles.meta}>Keputusan: {item.decision_reason}</Text>}
        {!!item.decided_at && <Text style={styles.meta}>{new Date(item.decided_at).toLocaleString("id-ID")}</Text>}
      </View>)}
    </View>}
  </View>;
}
const styles=StyleSheet.create({
 panel:{backgroundColor:"#10182D",borderColor:"#303A58",borderWidth:1,borderRadius:18,padding:14,gap:10,marginTop:14},
 kicker:{color:"#A5B4FC",fontSize:10,fontWeight:"800",letterSpacing:2},heading:{color:"#F7F8FF",fontSize:18,fontWeight:"800"},
 copy:{color:"#D5DAE8",fontSize:13,lineHeight:19},meta:{color:"#9DA8C2",fontSize:11,lineHeight:17},
 row:{padding:10,borderWidth:1,borderColor:"#303A58",borderRadius:12,gap:5},selected:{borderColor:"#A5B4FC"},
 form:{gap:9,marginTop:8},label:{color:"#E5EAF7",fontWeight:"700",fontSize:13},
 input:{minHeight:90,textAlignVertical:"top",padding:12,color:"#F7F8FF",backgroundColor:"#0B1020",borderWidth:1,borderColor:"#303A58",borderRadius:12},
 button:{backgroundColor:"#A5B4FC",padding:12,borderRadius:12,alignItems:"center"},buttonText:{color:"#11162B",fontWeight:"800"},
 disabled:{opacity:.45},secondary:{padding:10,alignItems:"center"},error:{color:"#FCA5A5",fontSize:12},notice:{color:"#86EFAC",fontSize:12}
});

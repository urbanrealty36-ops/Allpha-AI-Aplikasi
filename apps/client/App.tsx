import React, { useEffect, useState } from "react";
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { NavigationContainer, useNavigation, type NavigationProp } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { SafeAreaProvider } from "react-native-safe-area-context";
import * as SecureStore from "expo-secure-store";
import { StatusBar } from "expo-status-bar";
import { createClient, type Session, type SupabaseClient } from "@supabase/supabase-js";

type Routes = { Welcome: undefined; Auth: { mode?: "signin" | "signup" } | undefined; Profile: undefined };
type Profile = { id: string; username: string | null; display_name: string; avatar_url: string | null; bio: string; locale: "id-ID" | "en-US"; visibility: "public" | "private"; account_status?: "active" | "deactivation_requested"; created_at?: string };
type Settings = { theme: "light" | "dark" | "system"; notification_preferences: { product_updates: boolean; security_alerts: boolean; social_activity: boolean }; privacy_settings: { discoverable_by_username: boolean }; updated_at?: string };
const apiBase = (process.env.EXPO_PUBLIC_API_BASE_URL || (Platform.OS === "android" ? "http://10.0.2.2:8000" : "http://localhost:8000")).replace(/\/$/, "");
const supabaseUrl = process.env.EXPO_PUBLIC_SUPABASE_URL || "";
const supabaseKey = process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY || "";
const configured = Boolean(supabaseUrl && supabaseKey);

// Chunking keeps larger auth sessions within platform secure-storage item limits.
const secureStorage = {
  async getItem(key: string) {
    const n = Number(await SecureStore.getItemAsync(key + ":count") || 0);
    if (n > 0 && n <= 30) {
      const parts = await Promise.all(Array.from({ length: n }, (_, i) => SecureStore.getItemAsync(key + ":" + i)));
      return parts.every((part) => part !== null) ? parts.join("") : null;
    }
    return SecureStore.getItemAsync(key);
  },
  async setItem(key: string, value: string) {
    const chunks = value.match(/[\s\S]{1,1800}/g) || [""];
    if (chunks.length > 30) throw new Error("Sesi terlalu besar untuk penyimpanan aman perangkat.");
    const oldCount = Number(await SecureStore.getItemAsync(key + ":count") || 0);
    await SecureStore.deleteItemAsync(key).catch(() => undefined);
    for (let i = 0; i < Math.max(oldCount, chunks.length); i++) {
      if (i < chunks.length) await SecureStore.setItemAsync(key + ":" + i, chunks[i]);
      else await SecureStore.deleteItemAsync(key + ":" + i).catch(() => undefined);
    }
    await SecureStore.setItemAsync(key + ":count", String(chunks.length));
  },
  async removeItem(key: string) {
    const n = Number(await SecureStore.getItemAsync(key + ":count") || 0);
    await Promise.all(Array.from({ length: Math.min(n, 30) }, (_, i) => SecureStore.deleteItemAsync(key + ":" + i).catch(() => undefined)));
    await SecureStore.deleteItemAsync(key + ":count").catch(() => undefined);
    await SecureStore.deleteItemAsync(key).catch(() => undefined);
  }
};
const supabase: SupabaseClient | null = configured ? createClient(supabaseUrl, supabaseKey, {
  auth: { storage: secureStorage, persistSession: true, autoRefreshToken: true, detectSessionInUrl: false, flowType: "pkce" }
}) : null;
const Stack = createNativeStackNavigator<Routes>();

function Button({ title, onPress, secondary = false, disabled = false }: { title: string; onPress: () => void; secondary?: boolean; disabled?: boolean }) {
  return <Pressable accessibilityRole="button" disabled={disabled} onPress={onPress} style={({ pressed }) => [s.button, secondary && s.secondary, disabled && s.disabled, pressed && s.pressed]}><Text style={[s.buttonText, secondary && s.secondaryText]}>{title}</Text></Pressable>;
}
function Brand() { return <View style={s.brand}><View style={s.mark}><Text style={s.markText}>A</Text></View><Text style={s.eyebrow}>AI SOCIAL UNIVERSE</Text><Text style={s.brandTitle}>Allpha</Text><Text style={s.muted}>Satu universe untuk manusia dan AI Agent.</Text></View>; }

function Welcome() {
  const nav = useNavigation<NavigationProp<Routes>>();
  const [health, setHealth] = useState("Memeriksa API…");
  useEffect(() => { let active = true; fetch(apiBase + "/healthz").then(r => { if (!r.ok) throw new Error(); return r.json(); }).then(b => { if (active) setHealth(b.status === "ok" ? "API terhubung" : "API memberi status tidak dikenal"); }).catch(() => { if (active) setHealth("API tidak terjangkau"); }); return () => { active = false; }; }, []);
  return <ScrollView contentContainerStyle={s.page}><Brand/><View style={s.card}><Text style={s.kicker}>YOUR WORLD. YOUR AGENT.</Text><Text style={s.hero}>Temukan dunia yang terhubung.</Text><Text style={s.body}>Mulai dengan identitas manusia, lalu hubungkan perjalanan Anda ke AI Agent dan universe sosial Allpha.</Text><Text style={s.status}>●  {health}</Text>{!configured && <Text style={s.warning}>Autentikasi belum dikonfigurasi. Atur EXPO_PUBLIC_SUPABASE_URL dan EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY.</Text>}<Button title="Masuk" onPress={() => nav.navigate("Auth", { mode: "signin" })} disabled={!configured}/><Button title="Buat akun" secondary onPress={() => nav.navigate("Auth", { mode: "signup" })} disabled={!configured}/></View><Text style={s.footnote}>Native Android & iOS · sesi tersimpan di secure storage</Text></ScrollView>;
}

function Auth({ route }: { route: { params?: { mode?: "signin" | "signup" } } }) {
  const nav = useNavigation<NavigationProp<Routes>>();
  const [mode, setMode] = useState<"signin" | "signup">(route.params?.mode || "signin");
  const [name, setName] = useState(""); const [email, setEmail] = useState(""); const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false); const [message, setMessage] = useState(""); const [error, setError] = useState("");
  async function submit() {
    if (!supabase) return; setBusy(true); setError(""); setMessage("");
    try {
      if (mode === "signup") {
        if (!name.trim()) throw new Error("Nama tampilan wajib diisi.");
        const { data, error: e } = await supabase.auth.signUp({ email: email.trim(), password, options: { data: { display_name: name.trim(), locale: "id-ID" } } });
        if (e) throw e; setMessage(data.session ? "Akun berhasil dibuat." : "Akun dibuat. Periksa email untuk konfirmasi sebelum masuk.");
      } else { const { error: e } = await supabase.auth.signInWithPassword({ email: email.trim(), password }); if (e) throw e; }
    } catch (e) { setError(e instanceof Error ? e.message : "Autentikasi gagal. Coba lagi."); }
    finally { setBusy(false); }
  }
  return <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}><ScrollView contentContainerStyle={s.page}><Brand/><View style={s.card}><Text style={s.title}>{mode === "signin" ? "Selamat datang kembali" : "Buat identitas Anda"}</Text>{mode === "signup" && <TextInput accessibilityLabel="Nama tampilan" placeholder="Nama tampilan" placeholderTextColor="#8B94AC" value={name} onChangeText={setName} style={s.input}/>}<TextInput accessibilityLabel="Email" autoCapitalize="none" keyboardType="email-address" autoComplete="email" placeholder="Email" placeholderTextColor="#8B94AC" value={email} onChangeText={setEmail} style={s.input}/><TextInput accessibilityLabel="Kata sandi" secureTextEntry autoCapitalize="none" placeholder="Kata sandi (min. 8 karakter)" placeholderTextColor="#8B94AC" value={password} onChangeText={setPassword} style={s.input}/>{!!error && <Text accessibilityRole="alert" style={s.error}>{error}</Text>}{!!message && <Text accessibilityRole="alert" style={s.success}>{message}</Text>}{busy && <ActivityIndicator color="#A5B4FC"/>}<Button title={busy ? "Memproses…" : mode === "signin" ? "Masuk dengan aman" : "Daftar"} disabled={busy || !email.trim() || password.length < 8 || (mode === "signup" && !name.trim())} onPress={() => void submit()}/><Button title={mode === "signin" ? "Belum punya akun? Daftar" : "Sudah punya akun? Masuk"} secondary onPress={() => { setMode(mode === "signin" ? "signup" : "signin"); setError(""); setMessage(""); }}/><Button title="Kembali" secondary onPress={() => nav.goBack()}/></View></ScrollView></KeyboardAvoidingView>;
}

function Profile({ session }: { session: Session }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [tab, setTab] = useState<"profile" | "settings">("profile");
  const [loading, setLoading] = useState(true); const [busy, setBusy] = useState(false);
  const [error, setError] = useState(""); const [message, setMessage] = useState(""); const [retry, setRetry] = useState(0);
  async function apiRequest(path: string, init: RequestInit = {}) {
    const response = await fetch(apiBase + path, {
      ...init,
      headers: { Authorization: "Bearer " + session.access_token, Accept: "application/json", "Content-Type": "application/json", ...(init.headers || {}) },
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body?.error?.message || body?.detail?.message || "Permintaan gagal (" + response.status + ").");
    return body;
  }
  useEffect(() => {
    let active = true; setLoading(true); setError("");
    Promise.all([apiRequest("/v1/me"), apiRequest("/v1/me/settings")])
      .then(([identity, preferences]) => {
        if (active) { setProfile(identity.profile || null); setSettings(preferences.settings || null); }
      }).catch(e => { if (active) setError(e instanceof Error ? e.message : "Koneksi gagal."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [session.access_token, retry]);
  async function saveProfile() {
    if (!profile) return; setBusy(true); setError(""); setMessage("");
    try {
      const data = await apiRequest("/v1/me/profile", { method: "PATCH", body: JSON.stringify({
        username: profile.username || null, display_name: profile.display_name, avatar_url: profile.avatar_url || null,
        bio: profile.bio, visibility: profile.visibility, locale: profile.locale,
      }) });
      setProfile((current) => current ? { ...current, ...data.profile } : current); setMessage("Profil berhasil disimpan.");
    } catch (e) { setError(e instanceof Error ? e.message : "Profil tidak dapat disimpan."); }
    finally { setBusy(false); }
  }
  async function saveSettings() {
    if (!profile || !settings) return; setBusy(true); setError(""); setMessage("");
    try {
      const [identity, prefs] = await Promise.all([
        apiRequest("/v1/me/profile", { method: "PATCH", body: JSON.stringify({ locale: profile.locale }) }),
        apiRequest("/v1/me/settings", { method: "PATCH", body: JSON.stringify(settings) }),
      ]);
      setProfile((current) => current ? { ...current, ...identity.profile } : current);
      setSettings(prefs.settings); setMessage("Pengaturan privasi dan preferensi berhasil disimpan.");
    } catch (e) { setError(e instanceof Error ? e.message : "Pengaturan tidak dapat disimpan."); }
    finally { setBusy(false); }
  }
  async function requestDeactivation() {
    setBusy(true); setError(""); setMessage("");
    try {
      const data = await apiRequest("/v1/me/deactivation-request", { method: "POST", body: "{}" });
      setProfile((current) => current ? { ...current, account_status: data.profile.account_status } : current);
      setMessage(data.message || "Permintaan penonaktifan akun tercatat.");
    } catch (e) { setError(e instanceof Error ? e.message : "Permintaan penonaktifan gagal."); }
    finally { setBusy(false); }
  }
  const field = { ...s.input, flex: 1 } as const;
  return <ScrollView contentContainerStyle={s.page}><Brand/>
    <View style={s.card}>
      <Text style={s.kicker}>HUMAN IDENTITY</Text><Text style={s.title}>Identitas Anda</Text>
      <Text style={s.muted}>{session.user.email || session.user.id}</Text>
      <View style={{ flexDirection: "row", gap: 10 }}>
        <Button title="Profil" secondary={tab !== "profile"} onPress={() => { setTab("profile"); setError(""); setMessage(""); }}/>
        <Button title="Pengaturan & privasi" secondary={tab !== "settings"} onPress={() => { setTab("settings"); setError(""); setMessage(""); }}/>
      </View>
      {loading ? <ActivityIndicator color="#A5B4FC"/> : error ? <><Text accessibilityRole="alert" style={s.error}>{error}</Text><Button title="Coba lagi" onPress={() => setRetry(n => n + 1)}/></> :
      tab === "profile" ? profile ? <>
        <Text style={s.muted}>Perubahan disimpan melalui API Allpha dan sesi akun Anda.</Text>
        <Text style={s.muted}>Nama tampilan</Text><TextInput accessibilityLabel="Nama tampilan" value={profile.display_name} onChangeText={display_name => setProfile({ ...profile, display_name })} maxLength={80} style={field} placeholder="Nama tampilan" placeholderTextColor="#8B94AC"/>
        <Text style={s.muted}>Username (huruf kecil, angka, _)</Text><TextInput accessibilityLabel="Username" autoCapitalize="none" value={profile.username || ""} onChangeText={value => setProfile({ ...profile, username: value.toLowerCase() || null })} maxLength={30} style={field} placeholder="nama_pengguna" placeholderTextColor="#8B94AC"/>
        <Text style={s.muted}>URL avatar</Text><TextInput accessibilityLabel="URL avatar" autoCapitalize="none" keyboardType="url" value={profile.avatar_url || ""} onChangeText={value => setProfile({ ...profile, avatar_url: value || null })} style={field} placeholder="https://…" placeholderTextColor="#8B94AC"/>
        <Text style={s.muted}>Bio</Text><TextInput accessibilityLabel="Bio" multiline value={profile.bio} onChangeText={bio => setProfile({ ...profile, bio })} maxLength={500} style={[field, { minHeight: 90, textAlignVertical: "top" }]} placeholder="Ceritakan tentang diri Anda" placeholderTextColor="#8B94AC"/>
        <Text style={s.muted}>Bahasa</Text><View style={{ flexDirection: "row", gap: 8 }}><Button title="Bahasa Indonesia" secondary={profile.locale !== "id-ID"} onPress={() => setProfile({ ...profile, locale: "id-ID" })}/><Button title="English" secondary={profile.locale !== "en-US"} onPress={() => setProfile({ ...profile, locale: "en-US" })}/></View>
        <Text style={s.muted}>Visibilitas profil</Text><View style={{ flexDirection: "row", gap: 8 }}><Button title="Publik" secondary={profile.visibility !== "public"} onPress={() => setProfile({ ...profile, visibility: "public" })}/><Button title="Privat" secondary={profile.visibility !== "private"} onPress={() => setProfile({ ...profile, visibility: "private" })}/></View>
        <Button title={busy ? "Menyimpan…" : "Simpan profil"} disabled={busy || profile.account_status === "deactivation_requested"} onPress={() => void saveProfile()}/>
        <Text style={s.muted}>Status akun: {profile.account_status === "deactivation_requested" ? "Permintaan penonaktifan tercatat" : "Aktif"}</Text>
        <Button title={profile.account_status === "deactivation_requested" ? "Penonaktifan diminta" : "Minta penonaktifan akun"} secondary disabled={busy || profile.account_status === "deactivation_requested"} onPress={() => void requestDeactivation()}/>
      </> : <Text style={s.muted}>Profil belum tersedia.</Text> :
      settings ? <>
        <Text style={s.kicker}>PREFERENSI</Text><Text style={s.body}>Tema aplikasi</Text>
        <View style={{ flexDirection: "row", gap: 8 }}><Button title="Sistem" secondary={settings.theme !== "system"} onPress={() => setSettings({ ...settings, theme: "system" })}/><Button title="Terang" secondary={settings.theme !== "light"} onPress={() => setSettings({ ...settings, theme: "light" })}/><Button title="Gelap" secondary={settings.theme !== "dark"} onPress={() => setSettings({ ...settings, theme: "dark" })}/></View>
        <Text style={s.kicker}>NOTIFIKASI</Text>
        {(["product_updates", "security_alerts", "social_activity"] as const).map((key) => <Button key={key} title={(settings.notification_preferences[key] ? "✓ " : "○ ") + ({ product_updates: "Pembaruan produk", security_alerts: "Peringatan keamanan", social_activity: "Aktivitas sosial" }[key])} secondary={!settings.notification_preferences[key]} onPress={() => setSettings({ ...settings, notification_preferences: { ...settings.notification_preferences, [key]: !settings.notification_preferences[key] } })}/>)}
        <Text style={s.kicker}>PRIVASI</Text><Text style={s.body}>Temukan profil melalui username</Text>
        <View style={{ flexDirection: "row", gap: 8 }}><Button title="Dapat ditemukan" secondary={!settings.privacy_settings.discoverable_by_username} onPress={() => setSettings({ ...settings, privacy_settings: { ...settings.privacy_settings, discoverable_by_username: true } })}/><Button title="Tidak ditemukan" secondary={settings.privacy_settings.discoverable_by_username} onPress={() => setSettings({ ...settings, privacy_settings: { ...settings.privacy_settings, discoverable_by_username: false } })}/></View>
        <Button title={busy ? "Menyimpan…" : "Simpan pengaturan"} disabled={busy} onPress={() => void saveSettings()}/>
      </> : <Text style={s.muted}>Pengaturan belum tersedia.</Text>}
      {!!error && !loading && <Text accessibilityRole="alert" style={s.error}>{error}</Text>}
      {!!message && <Text accessibilityRole="alert" style={s.success}>{message}</Text>}
      <Button title="Keluar" secondary onPress={() => void supabase?.auth.signOut()}/>
    </View>
    <Text style={s.footnote}>Data identitas, pengaturan dan privasi dibaca/ditulis melalui API resmi. Tidak ada akses database langsung dari aplikasi.</Text>
  </ScrollView>;
}

function Navigator() {
  const [session, setSession] = useState<Session | null>(null); const [ready, setReady] = useState(false);
  useEffect(() => { let active = true; if (!supabase) { setReady(true); return; } void supabase.auth.getSession().then(({ data }) => { if (active) { setSession(data.session); setReady(true); } }); const { data } = supabase.auth.onAuthStateChange((_event, next) => { if (active) setSession(next); }); return () => { active = false; data.subscription.unsubscribe(); }; }, []);
  if (!ready) return <View style={s.loading}><ActivityIndicator size="large" color="#A5B4FC"/><Text style={s.muted}>Menyiapkan sesi aman…</Text></View>;
  return <NavigationContainer><Stack.Navigator key={session?.user.id || "anonymous"} initialRouteName={session ? "Profile" : "Welcome"} screenOptions={{ headerShown: false, contentStyle: { backgroundColor: "#0B1020" } }}>{session ? <Stack.Screen name="Profile">{() => <Profile session={session}/>}</Stack.Screen> : <><Stack.Screen name="Welcome" component={Welcome}/><Stack.Screen name="Auth" component={Auth}/></>}</Stack.Navigator></NavigationContainer>;
}
export default function App() { return <SafeAreaProvider><StatusBar style="light"/><Navigator/></SafeAreaProvider>; }

const s = StyleSheet.create({
 page:{flexGrow:1,justifyContent:"center",backgroundColor:"#0B1020",padding:22,gap:20},brand:{alignItems:"center",gap:6,marginBottom:8},mark:{width:54,height:54,borderRadius:18,backgroundColor:"#A5B4FC",alignItems:"center",justifyContent:"center",marginBottom:8},markText:{fontSize:28,fontWeight:"900",color:"#10152A"},eyebrow:{color:"#A5B4FC",letterSpacing:3,fontSize:10,fontWeight:"800"},brandTitle:{color:"#F5F7FF",fontSize:34,fontWeight:"800"},muted:{color:"#A5ADC3",fontSize:13,lineHeight:20,textAlign:"center"},card:{backgroundColor:"#141B31",borderColor:"#29314B",borderWidth:1,borderRadius:26,padding:22,gap:15},kicker:{color:"#A5B4FC",letterSpacing:2,fontSize:10,fontWeight:"800"},hero:{color:"#F7F8FF",fontSize:25,fontWeight:"800",lineHeight:32},title:{color:"#F7F8FF",fontSize:22,fontWeight:"800"},body:{color:"#C0C7DA",fontSize:14,lineHeight:22},button:{minHeight:49,borderRadius:14,backgroundColor:"#A5B4FC",padding:14,alignItems:"center",justifyContent:"center",marginTop:2},secondary:{backgroundColor:"transparent",borderWidth:1,borderColor:"#3A4566"},buttonText:{color:"#11162B",fontWeight:"800",fontSize:14},secondaryText:{color:"#E1E6F8"},disabled:{opacity:.45},pressed:{opacity:.8},input:{minHeight:50,backgroundColor:"#0D1326",color:"#F7F8FF",borderColor:"#303A58",borderWidth:1,borderRadius:13,paddingHorizontal:14,fontSize:15},status:{color:"#A5ADC3",fontSize:12},warning:{color:"#FBBF24",fontSize:12,lineHeight:18},error:{color:"#FCA5A5",backgroundColor:"#321D2B",padding:12,borderRadius:10,fontSize:13,lineHeight:19},success:{color:"#86EFAC",backgroundColor:"#12302C",padding:12,borderRadius:10,fontSize:13,lineHeight:19},footnote:{color:"#747E9A",textAlign:"center",fontSize:11,lineHeight:18},loading:{flex:1,backgroundColor:"#0B1020",alignItems:"center",justifyContent:"center",gap:12}
});

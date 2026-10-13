"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "../lib/supabase";

type Profile = {
  id: string; username: string | null; display_name: string; avatar_url: string | null; bio: string;
  visibility: "public" | "private"; locale: "id-ID" | "en-US"; account_status: "active" | "deactivation_requested";
  created_at: string; updated_at: string;
};
type Settings = {
  user_id: string; theme: "light" | "dark" | "system";
  notification_preferences: { product_updates: boolean; security_alerts: boolean; social_activity: boolean };
  privacy_settings: { discoverable_by_username: boolean }; updated_at: string;
};
type IdentityResponse = { user: { id: string; email?: string; email_confirmed_at?: string }; profile: Profile | null };
type SettingsResponse = { settings: Settings | null };
const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function apiError(response: Response): Promise<string> {
  try { const body = await response.json(); return body?.detail?.message ?? body?.error?.message ?? "Permintaan gagal (" + response.status + ")."; }
  catch { return "Permintaan gagal (" + response.status + ")."; }
}

export default function HomePage() {
  const supabase = useMemo(() => getBrowserSupabase(), []);
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [displayName, setDisplayName] = useState("");
  const [loading, setLoading] = useState(true); const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(""); const [error, setError] = useState("");
  const [tab, setTab] = useState<"profile" | "settings">("profile");

  const loadIdentity = useCallback(async (active: Session) => {
    setLoading(true); setError("");
    try {
      const headers = { Authorization: "Bearer " + active.access_token };
      const responses = await Promise.all([
        fetch(apiBase + "/v1/me", { headers, cache: "no-store" }),
        fetch(apiBase + "/v1/me/settings", { headers, cache: "no-store" }),
      ]);
      if (!responses[0].ok) throw new Error(await apiError(responses[0]));
      if (!responses[1].ok) throw new Error(await apiError(responses[1]));
      const identity = await responses[0].json() as IdentityResponse;
      const prefs = await responses[1].json() as SettingsResponse;
      setProfile(identity.profile); setSettings(prefs.settings);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Data identitas tidak dapat dimuat."); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    if (!supabase) { setLoading(false); return; }
    let active = true;
    void supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      setSession(data.session);
      if (data.session) void loadIdentity(data.session); else setLoading(false);
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, next) => {
      if (!active) return;
      setSession(next);
      if (next) void loadIdentity(next);
      else { setProfile(null); setSettings(null); setLoading(false); }
    });
    return () => { active = false; listener.subscription.unsubscribe(); };
  }, [supabase, loadIdentity]);

  async function handleAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!supabase) return;
    setSaving(true); setError(""); setMessage("");
    try {
      if (mode === "signup") {
        const { data, error: authError } = await supabase.auth.signUp({ email: email.trim(), password, options: { data: { display_name: displayName.trim(), locale: "id-ID" } } });
        if (authError) throw authError;
        if (!data.session) setMessage("Akun dibuat. Periksa email untuk menyelesaikan konfirmasi sebelum masuk.");
        else setMessage("Akun berhasil dibuat.");
      } else {
        const { error: authError } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
        if (authError) throw authError;
      }
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Autentikasi gagal."); }
    finally { setSaving(false); }
  }

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!session || !profile) return;
    setSaving(true); setError(""); setMessage("");
    try {
      const response = await fetch(apiBase + "/v1/me/profile", {
        method: "PATCH", headers: { Authorization: "Bearer " + session.access_token, "Content-Type": "application/json" },
        body: JSON.stringify({ username: profile.username || null, display_name: profile.display_name, avatar_url: profile.avatar_url || null, bio: profile.bio, visibility: profile.visibility, locale: profile.locale }),
      });
      if (!response.ok) throw new Error(await apiError(response));
      const data = await response.json(); setProfile(data.profile); setMessage("Profil berhasil disimpan ke Allpha.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Profil tidak dapat disimpan."); }
    finally { setSaving(false); }
  }

  async function saveSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!session || !settings || !profile) return;
    setSaving(true); setError(""); setMessage("");
    try {
      const headers = { Authorization: "Bearer " + session.access_token, "Content-Type": "application/json" };
      const profileResponse = await fetch(apiBase + "/v1/me/profile", { method: "PATCH", headers, body: JSON.stringify({ locale: profile.locale }) });
      if (!profileResponse.ok) throw new Error(await apiError(profileResponse));
      const settingsResponse = await fetch(apiBase + "/v1/me/settings", { method: "PATCH", headers, body: JSON.stringify(settingsPayload(settings)) });
      if (!settingsResponse.ok) throw new Error(await apiError(settingsResponse));
      const updatedProfile = await profileResponse.json() as { profile: Profile };
      const updatedSettings = await settingsResponse.json() as SettingsResponse;
      setProfile(updatedProfile.profile); setSettings(updatedSettings.settings); setMessage("Pengaturan berhasil disimpan.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Pengaturan tidak dapat disimpan."); }
    finally { setSaving(false); }
  }

  async function requestDeactivation() {
    if (!session || !window.confirm("Ajukan permintaan penonaktifan akun? Akun tidak langsung dihapus.")) return;
    setSaving(true); setError(""); setMessage("");
    try {
      const response = await fetch(apiBase + "/v1/me/deactivation-request", { method: "POST", headers: { Authorization: "Bearer " + session.access_token } });
      if (!response.ok) throw new Error(await apiError(response));
      const data = await response.json();
      setProfile((current) => current ? { ...current, account_status: data.profile.account_status } : current); setMessage(data.message);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Permintaan tidak dapat dikirim."); }
    finally { setSaving(false); }
  }

  if (!supabase) return <main className="identity-shell"><header className="identity-topbar"><a className="brand" href="/"><span className="brand-mark">A</span> ALLPHA</a><span className="top-note">HUMAN IDENTITY</span></header><section className="config-card"><span className="section-kicker">KONFIGURASI DIBUTUHKAN</span><h1>Hubungkan identitas Allpha</h1><p>Atur <code>NEXT_PUBLIC_SUPABASE_URL</code> dan <code>NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY</code> untuk mengaktifkan login nyata. Tidak ada akun contoh yang ditampilkan.</p></section></main>;

  if (!session) return <main className="identity-shell">
    <header className="identity-topbar"><a className="brand" href="/"><span className="brand-mark">A</span> ALLPHA</a><span className="top-note">HUMAN IDENTITY</span></header>
    <section className="auth-layout"><div className="auth-intro"><span className="section-kicker">AI SOCIAL UNIVERSE</span><h1>Identitas Anda, pusat dari universe Anda.</h1><p>Kelola profil manusia, privasi, dan preferensi akun dari satu tempat.</p><div className="identity-orbit" aria-hidden="true"><span /><i /><b>A</b></div></div>
      <form className="panel auth-panel" onSubmit={handleAuth}><div className="panel-heading"><span className="section-kicker">{mode === "signin" ? "SELAMAT DATANG KEMBALI" : "MULAI DI ALLPHA"}</span><h2>{mode === "signin" ? "Masuk ke Allpha" : "Buat akun manusia"}</h2><p>Autentikasi melalui Supabase.</p></div>
        {mode === "signup" && <label>Nama tampilan<input autoComplete="name" value={displayName} onChange={(e) => setDisplayName(e.target.value)} minLength={2} maxLength={80} required /></label>}
        <label>Email<input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
        <label>Kata sandi<input type="password" autoComplete={mode === "signin" ? "current-password" : "new-password"} value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} required /></label>
        {error && <p className="notice error" role="alert">{error}</p>}{message && <p className="notice success" role="status">{message}</p>}
        <button className="button-primary full-width" type="submit" disabled={saving}>{saving ? "Memproses…" : mode === "signin" ? "Masuk" : "Buat akun"}</button>
        <p className="switch-mode">{mode === "signin" ? "Belum memiliki akun?" : "Sudah memiliki akun?"} <button type="button" className="text-button" onClick={() => { setMode(mode === "signin" ? "signup" : "signin"); setError(""); setMessage(""); }}>{mode === "signin" ? "Daftar" : "Masuk"}</button></p>
      </form></section><footer className="identity-footer"><span>ALLPHA · HUMAN IDENTITY</span><span>Data nyata · Akses berbasis sesi</span></footer></main>;

  return <main className="identity-shell">
    <header className="identity-topbar"><a className="brand" href="/"><span className="brand-mark">A</span> ALLPHA</a><div className="account-menu"><span className="signed-in">{session.user.email}</span><button className="button-quiet" onClick={() => void supabase.auth.signOut()}>Keluar ↗</button></div></header>
    <section className="workspace-heading"><div><span className="section-kicker">RUANG PERSONAL</span><h1>Identitas manusia</h1><p>Profil dan pengaturan yang tersimpan pada akun Allpha Anda.</p></div>
      {profile && <div className="profile-chip">{profile.avatar_url ? <img src={profile.avatar_url} alt="" /> : <span>{(profile.display_name || session.user.email || "A").slice(0, 1).toUpperCase()}</span>}<div><strong>{profile.display_name || "Pengguna Allpha"}</strong><small>{profile.username ? "@" + profile.username : "Username belum diatur"}</small></div></div>}
    </section>
    <nav className="identity-tabs" aria-label="Bagian identitas"><button className={tab === "profile" ? "active" : ""} onClick={() => setTab("profile")}>Profil</button><button className={tab === "settings" ? "active" : ""} onClick={() => setTab("settings")}>Pengaturan</button></nav>
    {error && <p className="notice error" role="alert">{error}</p>}{message && <p className="notice success" role="status">{message}</p>}
    {loading || !profile || !settings ? <section className="panel loading-panel">Mengambil profil dan pengaturan dari backend…</section> : tab === "profile" ?
      <div className="content-grid"><form className="panel profile-form" onSubmit={saveProfile}>
        <div className="panel-heading"><span className="section-kicker">PROFIL PUBLIK</span><h2>Informasi manusia</h2><p>Perubahan dikirim ke API dan disimpan di database akun Anda.</p></div>
        <div className="avatar-row">{profile.avatar_url ? <img className="avatar-large" src={profile.avatar_url} alt="Avatar profil" /> : <div className="avatar-large avatar-placeholder">{(profile.display_name || "A").slice(0, 1).toUpperCase()}</div>}<div><strong>{profile.display_name || "Nama belum diatur"}</strong><p className="muted">Avatar menggunakan URL gambar yang Anda kelola.</p></div></div>
        <label>Nama tampilan<input value={profile.display_name} maxLength={80} onChange={(e) => setProfile({ ...profile, display_name: e.target.value })} required /></label>
        <label>Username<input value={profile.username ?? ""} minLength={3} maxLength={30} pattern="[a-z0-9_]{3,30}" onChange={(e) => setProfile({ ...profile, username: e.target.value.toLowerCase() || null })} placeholder="nama_pengguna" /><small>3–30 karakter; huruf kecil, angka, dan garis bawah.</small></label>
        <label>URL avatar<input type="url" value={profile.avatar_url ?? ""} maxLength={2048} onChange={(e) => setProfile({ ...profile, avatar_url: e.target.value || null })} placeholder="https://…" /></label>
        <label>Bio<textarea value={profile.bio} maxLength={500} rows={4} onChange={(e) => setProfile({ ...profile, bio: e.target.value })} placeholder="Ceritakan sedikit tentang diri Anda." /></label>
        <div className="field-row"><label>Bahasa<select value={profile.locale} onChange={(e) => setProfile({ ...profile, locale: e.target.value as Profile["locale"] })}><option value="id-ID">Bahasa Indonesia</option><option value="en-US">English (US)</option></select></label><label>Visibilitas profil<select value={profile.visibility} onChange={(e) => setProfile({ ...profile, visibility: e.target.value as Profile["visibility"] })}><option value="public">Publik</option><option value="private">Privat</option></select></label></div>
        <div className="form-actions"><span className="muted">Status akun: {profile.account_status === "active" ? "Aktif" : "Permintaan penonaktifan tercatat"}</span><button className="button-primary" disabled={saving || profile.account_status !== "active"}>{saving ? "Menyimpan…" : "Simpan profil"}</button></div>
      </form><aside className="side-column">
        <section className="panel side-panel"><span className="section-kicker">IDENTITAS AKUN</span><h3>{session.user.email}</h3><p className="muted">{session.user.email_confirmed_at ? "Email telah dikonfirmasi." : "Email belum dikonfirmasi."}</p><div className="detail-line"><span>ID identitas</span><code>{profile.id.slice(0, 8)}…</code></div><div className="detail-line"><span>Bergabung</span><span>{new Date(profile.created_at).toLocaleDateString(profile.locale)}</span></div></section>
        <section className="panel side-panel"><span className="section-kicker">KONTROL AKUN</span><h3>Penonaktifan</h3><p className="muted">Permintaan ini tidak langsung menghapus data atau sesi Anda.</p><button className="button-danger" onClick={() => void requestDeactivation()} disabled={saving || profile.account_status !== "active"}>{profile.account_status === "active" ? "Minta penonaktifan" : "Permintaan tercatat"}</button></section>
      </aside></div> :
      <form className="settings-layout" onSubmit={saveSettings}>
        <section className="panel settings-panel"><div className="panel-heading"><span className="section-kicker">PREFERENSI</span><h2>Pengalaman Anda</h2><p>Preferensi disimpan per akun dan dimuat kembali dari database.</p></div>
          <label>Tema antarmuka<select value={settings.theme} onChange={(e) => setSettings({ ...settings, theme: e.target.value as Settings["theme"] })}><option value="system">Ikuti sistem</option><option value="light">Terang</option><option value="dark">Gelap</option></select></label>
          <label>Bahasa profil<select value={profile.locale} onChange={(e) => setProfile({ ...profile, locale: e.target.value as Profile["locale"] })}><option value="id-ID">Bahasa Indonesia</option><option value="en-US">English (US)</option></select></label>
        </section>
        <section className="panel settings-panel"><div className="panel-heading"><span className="section-kicker">NOTIFIKASI</span><h2>Atur pemberitahuan</h2><p>Preferensi tersimpan; pengiriman notifikasi akan diaktifkan oleh layanan notifikasi.</p></div>
          <PreferenceToggle title="Pembaruan produk" description="Informasi fitur dan pembaruan Allpha." checked={settings.notification_preferences.product_updates} onChange={(checked) => setSettings({ ...settings, notification_preferences: { ...settings.notification_preferences, product_updates: checked } })} />
          <PreferenceToggle title="Peringatan keamanan" description="Pemberitahuan terkait keamanan akun." checked={settings.notification_preferences.security_alerts} onChange={(checked) => setSettings({ ...settings, notification_preferences: { ...settings.notification_preferences, security_alerts: checked } })} />
          <PreferenceToggle title="Aktivitas sosial" description="Pemberitahuan interaksi sosial saat fitur tersedia." checked={settings.notification_preferences.social_activity} onChange={(checked) => setSettings({ ...settings, notification_preferences: { ...settings.notification_preferences, social_activity: checked } })} />
        </section>
        <section className="panel settings-panel"><div className="panel-heading"><span className="section-kicker">PRIVASI</span><h2>Kontrol penemuan profil</h2><p>Visibilitas profil publik dikendalikan pada data profil Anda.</p></div>
          <PreferenceToggle title="Dapat ditemukan melalui username" description="Izinkan fitur pencarian menggunakan username saat discovery diaktifkan." checked={settings.privacy_settings.discoverable_by_username} onChange={(checked) => setSettings({ ...settings, privacy_settings: { discoverable_by_username: checked } })} />
          <div className="detail-line"><span>Visibilitas profil</span><strong>{profile.visibility === "public" ? "Publik" : "Privat"}</strong></div><button className="button-primary" disabled={saving}>{saving ? "Menyimpan…" : "Simpan pengaturan"}</button>
        </section><div className="settings-footer"><span className="muted">Preferensi disimpan melalui API terautentikasi.</span><button type="button" className="button-quiet" onClick={() => setTab("profile")}>Kembali ke profil</button></div>
      </form>}
    <footer className="identity-footer"><span>ALLPHA · HUMAN IDENTITY</span><span>Data akun nyata · Supabase Auth + PostgreSQL</span></footer>
  </main>;
}

function settingsPayload(settings: Settings) {
  return { theme: settings.theme, notification_preferences: settings.notification_preferences, privacy_settings: settings.privacy_settings };
}

function PreferenceToggle({ title, description, checked, onChange }: { title: string; description: string; checked: boolean; onChange: (value: boolean) => void }) {
  return <label className="preference-toggle"><span><strong>{title}</strong><small>{description}</small></span><input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} /></label>;
}

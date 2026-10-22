"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

const API = (process.env.NEXT_PUBLIC_API_BASE_URL || "https://api.allpha.web.id").replace(/\/$/, "");
const SUPABASE = (process.env.NEXT_PUBLIC_SUPABASE_URL || "").replace(/\/$/, "");
const PUBLIC_KEY = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || "";
const CATEGORIES = [
  "universe", "galaxy", "world", "orbit", "capsule", "district", "booth",
  "content-feed", "agent-character", "live-stage", "human-live", "sticker-social",
  "animation", "navigation-fx",
] as const;

type Category = (typeof CATEGORIES)[number];
type Session = { access_token: string; refresh_token: string; user: { id: string; email?: string } };
type Asset = { asset_key: string; version: number; display_name: string; category: Category; status: string; moderation_status?: string; sha256: string; byte_size: number; license_evidence_status?: string };
type Theme = { theme_key: string; display_name: string; description: string; status: string; active_version: number | null };
type ThemeVersion = { theme_key: string; version: number; status: string; manifest_sha256: string };
type Coverage = { category: Category; asset_versions: number; ingest_receipts: number; published: number; approved: number; rights_verified: number; publication_ready: number };
type UnregisteredReceipt = { asset_key: string; display_name: string; category_candidate: Category | null; category_mapping_status: string; lifecycle_status: string; sha256: string; byte_size: number; source_repo?: string; source_path?: string; source_url?: string; source_license_claim?: string; review_state?: string };
type CoverageReport = { categories: Coverage[]; total_asset_versions: number; total_ingest_receipts: number; receipt_mapping_status_counts: Record<string, number>; unregistered_receipts: UnregisteredReceipt[]; integrity_mismatches: unknown[]; category_mismatches: unknown[]; truncated: boolean };
type ApiResult<T> = T & { detail?: { code?: string; message?: string }; message?: string };

const inputStyle: React.CSSProperties = { width: "100%", boxSizing: "border-box", padding: "10px 12px", border: "1px solid #334155", borderRadius: 8, background: "#0f172a", color: "#f8fafc", marginTop: 5 };
const buttonStyle: React.CSSProperties = { padding: "10px 14px", border: "1px solid #475569", borderRadius: 8, background: "#172554", color: "#f8fafc", cursor: "pointer" };
const panelStyle: React.CSSProperties = { border: "1px solid #293548", borderRadius: 14, padding: 18, background: "#0b1220" };
const muted: React.CSSProperties = { color: "#94a3b8", fontSize: 13 };

export default function SpatialThemeBuilderPage() {
  const [session, setSession] = useState<Session | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [themes, setThemes] = useState<Theme[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [selectedTheme, setSelectedTheme] = useState("");
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const [selectedVersionStatus, setSelectedVersionStatus] = useState<string | null>(null);
  const [coverage, setCoverage] = useState<Coverage[]>([]);
  const [coverageReport, setCoverageReport] = useState<CoverageReport | null>(null);
  const [selectedAsset, setSelectedAsset] = useState<Partial<Record<Category, string>>>({});
  const [themeKey, setThemeKey] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [fallbackMode, setFallbackMode] = useState<"low_detail" | "2d">("low_detail");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [validation, setValidation] = useState<Record<string, unknown> | null>(null);

  const call = useCallback(async <T,>(path: string, init: RequestInit = {}): Promise<T> => {
    if (!session) throw new Error("Login operator diperlukan.");
    const response = await fetch(API + path, {
      ...init, cache: "no-store",
      headers: { Accept: "application/json", "Content-Type": "application/json", ...(init.headers || {}), Authorization: "Bearer " + session.access_token },
    });
    const body = await response.json().catch(() => ({})) as ApiResult<T>;
    if (!response.ok) throw new Error(body.detail?.message || body.message || "API gagal (" + response.status + ").");
    return body;
  }, [session]);

  const load = useCallback(async () => {
    if (!session) return;
    setBusy(true); setError("");
    try {
      const [themeData, coverageData] = await Promise.all([
        call<{ items: Theme[] }>("/v1/admin/spatial/themes?limit=100&offset=0"),
        call<CoverageReport>("/v1/admin/spatial/assets/category-coverage"),
      ]);
      const assetPages = await Promise.all(CATEGORIES.map(category =>
        call<{ items: Asset[] }>("/v1/admin/spatial/assets?limit=100&offset=0&category=" + encodeURIComponent(category))
          .then(result => result.items || [])
      ));
      setThemes(themeData.items || []);
      setCoverage(coverageData.categories || []);
      setCoverageReport(coverageData);
      setAssets(assetPages.flat());
      setMessage("Theme dan aset dimuat dari API kanonis. Aset hanya kandidat; status lifecycle tetap menentukan apakah boleh dipublikasikan.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Gagal memuat Theme dan aset.");
    } finally { setBusy(false); }
  }, [call, session]);

  useEffect(() => { if (session) void load(); }, [session, load]);

  async function login(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    try {
      if (!SUPABASE || !PUBLIC_KEY) throw new Error("NEXT_PUBLIC_SUPABASE_URL atau NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY belum dikonfigurasi pada Vercel.");
      const response = await fetch(SUPABASE + "/auth/v1/token?grant_type=password", {
        method: "POST", cache: "no-store",
        headers: { apikey: PUBLIC_KEY, "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok || !body.access_token || !body.user?.id) throw new Error(body.msg || body.error_description || "Login Supabase gagal.");
      setSession({ access_token: body.access_token, refresh_token: body.refresh_token, user: body.user });
      setMessage("Autentikasi berhasil. Semua izin operator tetap diperiksa oleh FastAPI.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Login gagal."); }
    finally { setBusy(false); }
  }

  async function createTheme(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setMessage(""); setValidation(null);
    try {
      const result = await call<{ item: Theme }>("/v1/admin/spatial/themes", {
        method: "POST", body: JSON.stringify({ theme_key: themeKey.trim(), display_name: displayName.trim(), description: description.trim() }),
      });
      setSelectedTheme(result.item.theme_key);
      setThemeKey(""); setDisplayName(""); setDescription("");
      setMessage("Theme draft dibuat: " + result.item.theme_key + ". Pilih aset yang benar-benar tersedia untuk menyusun versi manifest.");
      await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Theme gagal dibuat."); }
    finally { setBusy(false); }
  }

  function buildManifest() {
    const slots = CATEGORIES.flatMap(category => {
      const value = selectedAsset[category];
      if (!value) return [];
      const [asset_key, version] = value.split("@");
      return [{
        slot_key: "slot-" + category,
        category,
        asset_key,
        asset_version: Number(version),
        transform: { position: [0, 0, 0], rotation: [0, 0, 0], scale: [1, 1, 1] },
        required: true,
      }];
    });
    return { schema_version: "1.0", theme_key: selectedTheme, display_name: themes.find(theme => theme.theme_key === selectedTheme)?.display_name || selectedTheme, description: themes.find(theme => theme.theme_key === selectedTheme)?.description || "", fallback_mode: fallbackMode, slots };
  }

  async function createVersion() {
    if (!selectedTheme) { setError("Pilih Theme terlebih dahulu."); return; }
    const manifest = buildManifest();
    if (!manifest.slots.length) { setError("Pilih minimal satu aset nyata sebelum membuat versi manifest."); return; }
    setBusy(true); setError(""); setMessage(""); setValidation(null);
    try {
      const result = await call<{ item: ThemeVersion; validation: Record<string, unknown> }>("/v1/admin/spatial/themes/" + encodeURIComponent(selectedTheme) + "/versions", {
        method: "POST", body: JSON.stringify({ manifest }),
      });
      setSelectedVersion(result.item.version);
      setSelectedVersionStatus(result.item.status || "draft");
      setValidation(result.validation);
      setMessage("Versi draft v" + result.item.version + " tersimpan. Kelengkapan kategori dan status aset ditampilkan pada hasil validasi.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Versi Theme gagal dibuat."); }
    finally { setBusy(false); }
  }

  async function versionAction(action: "validate" | "approve" | "publish") {
    if (!selectedTheme || !selectedVersion) { setError("Buat atau pilih versi Theme terlebih dahulu."); return; }
    setBusy(true); setError(""); setMessage(""); setValidation(null);
    try {
      const result = await call<Record<string, unknown>>("/v1/admin/spatial/themes/" + encodeURIComponent(selectedTheme) + "/versions/" + selectedVersion + "/" + action, { method: "POST" });
      setValidation(result);
      if (typeof result.status === "string" && result.status !== "blocked") setSelectedVersionStatus(result.status);
      if (result.status === "blocked" || result.valid === false) {
        setMessage("Aksi " + action + " diblokir oleh validasi lifecycle. Periksa error dan warning; tidak ada publikasi yang dipaksakan.");
      } else {
        setMessage("Respons API untuk " + action + " diterima. Periksa status dan validasi sebelum melanjutkan.");
      }
      await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Aksi Theme gagal."); }
    finally { setBusy(false); }
  }

  const selectedAssets = CATEGORIES.flatMap(category => {
    const value = selectedAsset[category];
    return value ? [{ category, value }] : [];
  });
  const missingCategories = CATEGORIES.filter(category => !selectedAsset[category]);
  const readyAssets = (category: Category) => assets.filter(asset => asset.category === category);

  return <main style={{ maxWidth: 1240, margin: "0 auto", padding: "28px 20px", color: "#e2e8f0", fontFamily: "Inter,system-ui,sans-serif", display: "grid", gap: 18 }}>
    <header>
      <p style={{ fontSize: 12, letterSpacing: 2, color: "#a5b4fc", fontWeight: 700 }}>ALLPHA UNIVERSE · ENG-P22</p>
      <h1 style={{ fontSize: 32, margin: "6px 0" }}>Spatial Theme Builder</h1>
      <p style={muted}>Manifest deklaratif, 14 kategori kanonis, versi immutable, dan publication gates dari FastAPI.</p>
      <p style={muted}>Target desain: 25 Theme × 14 kategori = 350 slot. Slot yang belum memiliki aset nyata tetap missing; sistem tidak membuat GLB atau data katalog fiktif.</p>
    </header>

    {!session ? <form onSubmit={login} style={{ ...panelStyle, maxWidth: 460, display: "grid", gap: 12 }}>
      <h2 style={{ margin: 0, fontSize: 20 }}>Login operator</h2>
      <label>Email<input required type="email" autoComplete="username" value={email} onChange={event => setEmail(event.target.value)} style={inputStyle} /></label>
      <label>Password<input required type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} style={inputStyle} /></label>
      <button disabled={busy} style={buttonStyle}>{busy ? "Memproses…" : "Login melalui Supabase Auth"}</button>
      <p style={muted}>Login tidak memberi hak istimewa otomatis. API memvalidasi scope platform:content.moderate pada setiap operasi.</p>
    </form> : <>
      <section style={{ ...panelStyle, display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center", justifyContent: "space-between" }}>
        <span>Operator: {session.user.email || session.user.id}</span>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button style={buttonStyle} disabled={busy} onClick={() => void load()}>Muat ulang data</button>
          <button style={buttonStyle} onClick={() => { setSession(null); setThemes([]); setAssets([]); setSelectedVersion(null); }}>Keluar</button>
        </div>
      </section>

      <section style={panelStyle}>
        <h2 style={{ marginTop: 0 }}>1. Buat Theme draft</h2>
        <form onSubmit={createTheme} style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 12, alignItems: "end" }}>
          <label>Theme key<input required minLength={3} maxLength={120} pattern="[a-z0-9][a-z0-9._-]{2,119}" value={themeKey} onChange={event => setThemeKey(event.target.value)} style={inputStyle} /></label>
          <label>Nama tampilan<input required minLength={2} maxLength={160} value={displayName} onChange={event => setDisplayName(event.target.value)} style={inputStyle} /></label>
          <label>Deskripsi<input maxLength={2000} value={description} onChange={event => setDescription(event.target.value)} style={inputStyle} /></label>
          <button disabled={busy} style={buttonStyle}>Buat Theme</button>
        </form>
      </section>

      <section style={panelStyle}>
        <h2 style={{ marginTop: 0 }}>2. Rekonsiliasi 927 ingest receipts</h2>
        {!coverageReport ? <p style={muted}>Laporan coverage belum tersedia.</p> : <>
          <p style={muted}>Registry aset: {coverageReport.total_asset_versions} versi · ingest receipts: {coverageReport.total_ingest_receipts} · status mapping: {Object.entries(coverageReport.receipt_mapping_status_counts).map(([key, value]) => key + " " + value).join(" · ") || "belum tersedia"}.</p>
          <p style={muted}>Ketidakcocokan checksum/ukuran: {coverageReport.integrity_mismatches.length} · ketidakcocokan kategori: {coverageReport.category_mismatches.length} · laporan terpotong: {coverageReport.truncated ? "ya" : "tidak"}.</p>
          {coverageReport.unregistered_receipts.length === 0 ? <p style={muted}>Semua receipt yang dibaca memiliki asset record kanonis.</p> : <div style={{ display: "grid", gap: 10 }}>
            <strong>{coverageReport.unregistered_receipts.length} receipt belum mempunyai asset record kanonis</strong>
            {coverageReport.unregistered_receipts.map(receipt => <article key={receipt.asset_key} style={{ border: "1px solid #7c2d12", borderRadius: 10, padding: 12 }}>
              <strong>{receipt.display_name}</strong>
              <p style={muted}>{receipt.asset_key} · {receipt.lifecycle_status} · {receipt.category_mapping_status} · kandidat: {receipt.category_candidate || "unmapped"}</p>
              <p style={muted}>Sumber: {receipt.source_repo || "unknown"} / {receipt.source_path || "unknown"}</p>
              <p style={muted}>Klaim lisensi: {receipt.source_license_claim || "unknown"} · review: {receipt.review_state || "pending"}</p>
              <code style={{ fontSize: 11, overflowWrap: "anywhere" }}>SHA-256: {receipt.sha256} · {receipt.byte_size} bytes</code>
              <p style={muted}>Belum otomatis didaftarkan: perlu rekonsiliasi file/hash, kategori berbukti, dan lifecycle ingest sebelum registrasi kanonis.</p>
            </article>)}
          </div>}
          {coverageReport.integrity_mismatches.length > 0 && <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere", fontSize: 12 }}>{JSON.stringify(coverageReport.integrity_mismatches, null, 2)}</pre>}
          {coverageReport.category_mismatches.length > 0 && <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere", fontSize: 12 }}>{JSON.stringify(coverageReport.category_mismatches, null, 2)}</pre>}
        </>}
      </section>

      <section style={panelStyle}>
        <h2 style={{ marginTop: 0 }}>3. Pilih Theme dan susun 14 kategori</h2>
        <label>Theme kanonis<select value={selectedTheme} onChange={event => { setSelectedTheme(event.target.value); setSelectedVersion(null); setSelectedVersionStatus(null); setValidation(null); }} style={inputStyle}>
          <option value="">Pilih Theme</option>{themes.map(theme => <option key={theme.theme_key} value={theme.theme_key}>{theme.display_name} · {theme.theme_key} · {theme.status}{theme.active_version ? " v" + theme.active_version : ""}</option>)}
        </select></label>
        <label style={{ display: "block", marginTop: 12 }}>Fallback renderer<select value={fallbackMode} onChange={event => setFallbackMode(event.target.value as "low_detail" | "2d")} style={inputStyle}><option value="low_detail">low_detail</option><option value="2d">2d</option></select></label>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(250px,1fr))", gap: 12, marginTop: 14 }}>
          {CATEGORIES.map(category => {
            const candidates = readyAssets(category);
            return <label key={category} style={{ border: "1px solid #293548", borderRadius: 10, padding: 12 }}>
              <strong>{category}</strong>
              <p style={muted}>{coverage.find(item => item.category === category)?.asset_versions ?? 0} asset record · {coverage.find(item => item.category === category)?.publication_ready ?? 0} siap publikasi · {candidates.length} kandidat di halaman pertama</p>
              <select value={selectedAsset[category] || ""} onChange={event => setSelectedAsset(current => ({ ...current, [category]: event.target.value }))} style={inputStyle}>
                <option value="">Slot belum dipetakan</option>
                {candidates.map(asset => <option key={asset.asset_key + "@" + asset.version} value={asset.asset_key + "@" + asset.version}>{asset.display_name} · v{asset.version} · {asset.status}/{asset.moderation_status || "pending"}</option>)}
              </select>
            </label>;
          })}
        </div>
        <div style={{ ...muted, marginTop: 12 }}>Terpilih {selectedAssets.length}/14 kategori. Belum terpetakan: {missingCategories.join(", ") || "tidak ada"}.</div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
          <button disabled={busy || !selectedTheme || selectedAssets.length === 0} style={buttonStyle} onClick={() => void createVersion()}>Buat versi manifest draft</button>
          <button disabled={busy || !selectedTheme || !selectedVersion} style={buttonStyle} onClick={() => void versionAction("validate")}>Validasi versi</button>
          <button disabled={busy || !selectedTheme || !selectedVersion || !["draft", "review"].includes(selectedVersionStatus || "")} style={buttonStyle} onClick={() => void versionAction("approve")}>Setujui versi</button>
          <button disabled={busy || !selectedTheme || !selectedVersion || selectedVersionStatus !== "approved"} style={buttonStyle} onClick={() => void versionAction("publish")}>Publikasikan versi</button>
        </div>
        <p style={muted}>Publish tetap diblokir oleh API jika kategori belum lengkap, hash tidak cocok, atau aset belum published + approved + rights verified. Tombol UI tidak dapat melewati pemeriksaan tersebut.</p>
      </section>

      <section style={panelStyle}>
        <h2 style={{ marginTop: 0 }}>4. Theme registry kanonis</h2>
        {themes.length === 0 ? <p style={muted}>Belum ada Theme pada registry. Tidak ada Theme contoh yang dibuat otomatis.</p> : themes.map(theme => <article key={theme.theme_key} style={{ display: "flex", gap: 12, justifyContent: "space-between", flexWrap: "wrap", borderTop: "1px solid #293548", padding: "12px 0" }}>
          <div><strong>{theme.display_name}</strong><p style={muted}>{theme.theme_key} · {theme.status} · active version: {theme.active_version ?? "none"}</p></div>
          <button style={buttonStyle} onClick={() => { setSelectedTheme(theme.theme_key); setSelectedVersion(theme.active_version); setSelectedVersionStatus(theme.active_version ? "published" : null); setValidation(null); }}>Pilih Theme</button>
        </article>)}
      </section>
    </>}

    {error && <p role="alert" style={{ padding: 12, borderRadius: 8, background: "#451a1a", color: "#fecaca" }}>{error}</p>}
    {message && <p role="status" style={{ padding: 12, borderRadius: 8, background: "#172554", color: "#dbeafe" }}>{message}</p>}
    {validation && <section style={panelStyle}><h2 style={{ marginTop: 0 }}>Hasil validasi API</h2><pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere", fontSize: 12, color: "#cbd5e1" }}>{JSON.stringify(validation, null, 2)}</pre></section>}
  </main>;
}

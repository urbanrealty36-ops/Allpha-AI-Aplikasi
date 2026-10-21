"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

const api = (process.env.NEXT_PUBLIC_API_BASE_URL || "https://api.allpha.web.id").replace(/\/$/, "");
const supabase = (process.env.NEXT_PUBLIC_SUPABASE_URL || "").replace(/\/$/, "");
const publicKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || "";
const categories = [
  "universe", "galaxy", "world", "orbit", "capsule", "district", "booth",
  "content-feed", "agent-character", "live-stage", "human-live",
  "sticker-social", "animation", "navigation-fx",
] as const;

type Session = { access_token: string; refresh_token: string; user: { id: string; email?: string } };
type Theme = { theme_key: string; display_name: string; description: string; status: string; active_version: number | null; updated_at: string };
type Asset = { asset_key: string; version: number; display_name: string; category: string; status: string; moderation_status: string; sha256: string; byte_size: number; license_evidence?: { status?: string; note?: string } };
type ApiResult = { item?: Theme; items?: unknown[]; validation?: Record<string, unknown>; [key: string]: unknown };

const defaultManifest = (themeKey: string, displayName: string) => JSON.stringify({
  schema_version: "1.0",
  theme_key: themeKey,
  display_name: displayName,
  description: "",
  fallback_mode: "low_detail",
  slots: [],
}, null, 2);

export default function ThemeBuilderPage() {
  const [session, setSession] = useState<Session | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [themes, setThemes] = useState<Theme[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [assetCategory, setAssetCategory] = useState("");
  const [assetOffset, setAssetOffset] = useState(0);
  const [themeKey, setThemeKey] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [manifestText, setManifestText] = useState(defaultManifest("", ""));
  const [selected, setSelected] = useState<Theme | null>(null);
  const [version, setVersion] = useState<number | null>(null);
  const [validation, setValidation] = useState<Record<string, unknown> | null>(null);
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const request = useCallback(async <T,>(path: string, method = "GET", body?: unknown): Promise<T> => {
    if (!session) throw new Error("Login operator diperlukan.");
    const response = await fetch(api + path, {
      method,
      cache: "no-store",
      headers: { Authorization: "Bearer " + session.access_token, Accept: "application/json", ...(body ? { "Content-Type": "application/json" } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = result?.detail;
      throw new Error(typeof detail?.message === "string" ? detail.message : typeof detail === "string" ? detail : "Permintaan gagal (" + response.status + ").");
    }
    return result as T;
  }, [session]);

  const loadThemes = useCallback(async () => {
    if (!session) return;
    const result = await request<ApiResult>("/v1/admin/spatial/themes?limit=100&offset=0");
    setThemes(Array.isArray(result.items) ? result.items as Theme[] : []);
  }, [request, session]);

  const loadAssets = useCallback(async () => {
    if (!session) return;
    const params = new URLSearchParams({ limit: "100", offset: String(assetOffset) });
    if (assetCategory) params.set("category", assetCategory);
    const result = await request<ApiResult>("/v1/admin/spatial/assets?" + params.toString());
    setAssets(Array.isArray(result.items) ? result.items as Asset[] : []);
  }, [request, session, assetCategory, assetOffset]);

  useEffect(() => {
    void loadThemes().catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "Katalog Theme tidak tersedia."));
  }, [loadThemes]);
  useEffect(() => {
    void loadAssets().catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "Asset Library tidak tersedia."));
  }, [loadAssets]);

  async function login(event: FormEvent) {
    event.preventDefault(); setError(""); setMessage(""); setBusy(true);
    try {
      if (!supabase || !publicKey) throw new Error("Konfigurasi Supabase URL/publishable key belum tersedia.");
      const response = await fetch(supabase + "/auth/v1/token?grant_type=password", {
        method: "POST", headers: { apikey: publicKey, "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }), cache: "no-store",
      });
      const result = await response.json();
      if (!response.ok || !result.access_token || !result.user?.id) throw new Error(result.msg || result.error_description || "Login Supabase gagal.");
      setSession({ access_token: result.access_token, refresh_token: result.refresh_token, user: result.user });
      setPassword("");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Login gagal."); }
    finally { setBusy(false); }
  }

  async function createTheme(event: FormEvent) {
    event.preventDefault(); setError(""); setMessage(""); setBusy(true);
    try {
      const result = await request<ApiResult>("/v1/admin/spatial/themes", "POST", { theme_key: themeKey.trim(), display_name: displayName.trim(), description });
      const item = result.item as Theme;
      setSelected(item); setVersion(null); setValidation(null); setPreview(null);
      setManifestText(defaultManifest(item.theme_key, item.display_name));
      setMessage("Theme draft dibuat. Buat versi manifest untuk menyimpan konfigurasi layout.");
      await loadThemes();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Theme tidak dapat dibuat."); }
    finally { setBusy(false); }
  }

  function selectTheme(item: Theme) {
    setSelected(item); setThemeKey(item.theme_key); setDisplayName(item.display_name); setDescription(item.description || "");
    setManifestText(defaultManifest(item.theme_key, item.display_name)); setVersion(null); setValidation(null); setPreview(null);
    setError(""); setMessage("Theme dipilih. Untuk membuat versi baru, edit manifest deklaratif lalu simpan versi.");
  }

  function addAssetSlot(asset: Asset) {
    setError(""); setMessage("");
    if (!selected) { setError("Pilih Theme sebelum menambahkan slot."); return; }
    try {
      const manifest = JSON.parse(manifestText);
      if (manifest.theme_key !== selected.theme_key) throw new Error("theme_key pada manifest harus sama dengan Theme yang dipilih.");
      const stem = asset.asset_key.toLowerCase().replace(/[^a-z0-9._-]+/g, "-").replace(/^[^a-z0-9]+/, "").slice(0, 100);
      let slotKey = (asset.category + "." + stem).slice(0, 120);
      const used = new Set<string>((manifest.slots || []).map((slot: { slot_key?: string }) => slot.slot_key || ""));
      let suffix = 2;
      while (used.has(slotKey)) { slotKey = (asset.category + "." + stem).slice(0, 115) + "-" + suffix++; }
      manifest.slots = [...(manifest.slots || []), {
        slot_key: slotKey, category: asset.category, asset_key: asset.asset_key, asset_version: asset.version,
        transform: { position: [0, 0, 0], rotation: [0, 0, 0], scale: [1, 1, 1] }, required: true,
      }];
      setManifestText(JSON.stringify(manifest, null, 2));
      setMessage("Slot " + slotKey + " ditambahkan ke editor. Simpan sebagai versi baru setelah layout diperiksa.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Slot tidak dapat ditambahkan."); }
  }

  async function createVersion() {
    setError(""); setMessage(""); setBusy(true); setValidation(null); setPreview(null);
    try {
      if (!selected) throw new Error("Pilih atau buat Theme terlebih dahulu.");
      const manifest = JSON.parse(manifestText);
      const result = await request<ApiResult>("/v1/admin/spatial/themes/" + encodeURIComponent(selected.theme_key) + "/versions", "POST", { manifest });
      const item = result.item as unknown as { version: number };
      setVersion(item.version);
      setValidation((result.validation || null) as Record<string, unknown> | null);
      setMessage("Versi draft v" + item.version + " tersimpan sebagai snapshot immutable. Perubahan selanjutnya harus menjadi versi baru.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Manifest JSON tidak valid."); }
    finally { setBusy(false); }
  }

  async function runAction(action: "validate" | "preview" | "approve" | "publish") {
    setError(""); setMessage(""); setBusy(true);
    try {
      if (!selected || version === null) throw new Error("Simpan versi draft sebelum menjalankan aksi.");
      const result = await request<ApiResult>("/v1/admin/spatial/themes/" + encodeURIComponent(selected.theme_key) + "/versions/" + version + "/" + action, "POST");
      if (action === "validate") setValidation(result as Record<string, unknown>);
      if (action === "preview") setPreview(result as Record<string, unknown>);
      if (action === "publish") { setMessage("Versi Theme dipublikasikan. Renderer publik dapat mengambil manifest melalui API kanonis."); await loadThemes(); }
      else if (action === "approve") {
        setValidation(result as Record<string, unknown>);
        setMessage(result.status === "approved" ? "Versi Theme disetujui; publikasi sekarang dapat diajukan." : "Persetujuan diblokir. Periksa hasil validasi sebelum mencoba lagi.");
      } else setMessage(action === "validate" ? "Validasi selesai. Periksa error, warning, coverage kategori, dan hash." : "Manifest preview berhasil dibuat menggunakan URL aset berumur pendek.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Aksi Theme gagal."); }
    finally { setBusy(false); }
  }

  return <main style={{ maxWidth: 1180, margin: "0 auto", padding: "28px 20px 56px", color: "#17202a" }}>
    <header style={{ marginBottom: 24 }}>
      <p style={{ margin: 0, fontSize: 12, letterSpacing: 1.6, textTransform: "uppercase", color: "#64748b" }}>Allpha Universe · ENG-P22</p>
      <h1 style={{ fontSize: 30, margin: "8px 0" }}>Theme Builder & GLB Manifest</h1>
      <p style={{ maxWidth: 760, lineHeight: 1.6, color: "#475569" }}>Kelola Theme berversi dengan manifest deklaratif. Semua referensi aset harus menunjuk versi pada registry spasial kanonis; publikasi hanya menerima aset published, approved, dan bukti hak berstatus verified.</p>
    </header>

    {!session ? <form onSubmit={login} style={panel}>
      <h2 style={h2}>Login operator</h2>
      <label style={label}>Email<input autoComplete="username" type="email" required value={email} onChange={e=>setEmail(e.target.value)} style={input} /></label>
      <label style={label}>Password<input autoComplete="current-password" type="password" required value={password} onChange={e=>setPassword(e.target.value)} style={input} /></label>
      <button disabled={busy} style={button}>{busy ? "Memproses…" : "Masuk"}</button>
      <p style={muted}>Memerlukan grant operator aktif dengan scope platform:content.moderate. Login tidak memberikan hak operator secara otomatis.</p>
    </form> : <>
      <section style={{ ...panel, marginBottom: 20 }}>
        <div style={row}><h2 style={h2}>Theme registry</h2><button style={secondary} disabled={busy} onClick={()=>void loadThemes()}>Muat ulang</button><button style={secondary} onClick={()=>{setSession(null);setThemes([]);setSelected(null);}}>Keluar</button></div>
        {themes.length === 0 ? <p style={muted}>Belum ada Theme yang dapat ditampilkan, atau katalog belum tersedia pada skema Production.</p> : <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fit,minmax(240px,1fr))", gap:10 }}>
          {themes.map(item=><button key={item.theme_key} type="button" onClick={()=>selectTheme(item)} style={{...themeCard,borderColor:selected?.theme_key===item.theme_key?"#334155":"#d8dee8"}}>
            <strong>{item.display_name}</strong><span style={muted}>{item.theme_key}</span><span style={badge}>{item.status}{item.active_version ? " · v"+item.active_version : ""}</span>
          </button>)}
        </div>}
      </section>

      <section style={{ ...panel, marginBottom: 20 }}>
        <div style={row}><h2 style={h2}>Asset Library · registry kanonis</h2><button style={secondary} disabled={busy} onClick={()=>void loadAssets()}>Muat ulang</button></div>
        <div style={{display:"flex",gap:10,alignItems:"end",flexWrap:"wrap",marginBottom:12}}>
          <label style={{...label,minWidth:240}}>Filter kategori
            <select value={assetCategory} onChange={e=>{setAssetCategory(e.target.value);setAssetOffset(0);}} style={input}>
              <option value="">Semua kategori</option>{categories.map(category=><option key={category} value={category}>{category}</option>)}
            </select>
          </label>
          <span style={muted}>Menampilkan {assets.length} aset · offset {assetOffset}. Pilih aset untuk menambahkan slot ke manifest.</span>
        </div>
        {assets.length===0 ? <p style={muted}>Tidak ada aset pada filter ini, atau registry belum tersedia.</p> : <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(260px,1fr))",gap:10}}>
          {assets.map(asset=><article key={asset.asset_key+":"+asset.version} style={{border:"1px solid #dbe2ea",borderRadius:10,padding:12,display:"grid",gap:6}}>
            <strong>{asset.display_name}</strong><span style={muted}>{asset.asset_key} · v{asset.version}</span>
            <div style={{display:"flex",gap:6,flexWrap:"wrap"}}><span style={categoryChip}>{asset.category}</span><span style={badge}>{asset.status}</span><span style={badge}>moderation: {asset.moderation_status}</span></div>
            <span style={muted}>SHA-256: {asset.sha256.slice(0,16)}… · {(asset.byte_size/1024/1024).toFixed(2)} MiB</span>
            <span style={muted}>Rights evidence: {asset.license_evidence?.status || "missing"}</span>
            <button type="button" style={secondary} disabled={!selected||busy} onClick={()=>addAssetSlot(asset)}>Tambahkan ke manifest</button>
          </article>)}
        </div>}
        <div style={{display:"flex",gap:8,alignItems:"center",marginTop:12}}>
          <button style={secondary} disabled={busy||assetOffset===0} onClick={()=>setAssetOffset(Math.max(0,assetOffset-100))}>Sebelumnya</button>
          <span style={muted}>Offset {assetOffset}</span>
          <button style={secondary} disabled={busy||assets.length<100} onClick={()=>setAssetOffset(assetOffset+100)}>Berikutnya</button>
        </div>
      </section>

      <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fit,minmax(min(100%,420px),1fr))", gap:20, alignItems:"start" }}>
        <section style={panel}>
          <h2 style={h2}>1. Buat Theme draft</h2>
          <form onSubmit={createTheme} style={{display:"grid",gap:12}}>
            <label style={label}>Theme key<input required minLength={3} maxLength={120} pattern="[a-z0-9][a-z0-9._-]{2,119}" value={themeKey} onChange={e=>setThemeKey(e.target.value)} style={input} placeholder="crystal-city" /></label>
            <label style={label}>Nama Theme<input required minLength={2} maxLength={160} value={displayName} onChange={e=>setDisplayName(e.target.value)} style={input} placeholder="Crystal AI City" /></label>
            <label style={label}>Deskripsi<textarea maxLength={2000} value={description} onChange={e=>setDescription(e.target.value)} style={textarea} /></label>
            <button disabled={busy||!session} style={button}>Buat Theme</button>
          </form>
          {selected && <p style={muted}>Terpilih: <strong>{selected.theme_key}</strong>. Snapshot versi tidak dapat ditimpa.</p>}
        </section>

        <section style={panel}>
          <h2 style={h2}>2. Manifest deklaratif</h2>
          <p style={muted}>Gunakan JSON schema v1.0. Setiap slot menunjuk asset_key + asset_version yang sudah ada; transform memakai meter dan koordinat right-handed-y-up. Tidak menerima executable code.</p>
          <div style={{display:"flex",flexWrap:"wrap",gap:6,marginBottom:10}}>{categories.map(category=><span key={category} style={categoryChip}>{category}</span>)}</div>
          <textarea aria-label="Theme manifest JSON" spellCheck={false} value={manifestText} onChange={e=>setManifestText(e.target.value)} style={{...textarea,minHeight:330,fontFamily:"ui-monospace,SFMono-Regular,Menlo,monospace",fontSize:12}} />
          <div style={{display:"flex",flexWrap:"wrap",gap:8,marginTop:12}}>
            <button disabled={busy||!selected} style={button} onClick={()=>void createVersion()}>Simpan versi immutable</button>
            <button disabled={busy||version===null} style={secondary} onClick={()=>void runAction("validate")}>Validasi</button>
            <button disabled={busy||version===null} style={secondary} onClick={()=>void runAction("preview")}>Buat preview</button>
            <button disabled={busy||version===null} style={secondary} onClick={()=>void runAction("approve")}>Setujui versi</button>
            <button disabled={busy||version===null} style={secondary} onClick={()=>void runAction("publish")}>Publikasikan</button>
          </div>
          {version!==null && <p style={muted}>Versi terpilih: v{version}. Untuk mengubah manifest, buat versi baru; versi ini tetap immutable.</p>}
        </section>
      </div>

      <section style={{...panel,marginTop:20}}>
        <h2 style={h2}>3. Hasil validasi / preview</h2>
        {!validation&&!preview ? <p style={muted}>Hasil validasi dan preview akan muncul di sini.</p> : <pre style={pre}>{JSON.stringify({validation,preview},null,2)}</pre>}
        <p style={muted}>Preview menggunakan signed URL berumur pendek untuk operator. Link preview bukan publikasi. Endpoint publik hanya mengeluarkan manifest Theme aktif dan aset versi published yang approved dengan bukti hak terverifikasi.</p>
      </section>
    </>}

    {error && <p role="alert" style={{marginTop:16,padding:12,borderRadius:8,background:"#fff1f2",color:"#9f1239"}}>{error}</p>}
    {message && <p role="status" style={{marginTop:16,padding:12,borderRadius:8,background:"#f0fdf4",color:"#166534"}}>{message}</p>}
  </main>;
}

const panel: React.CSSProperties = { border:"1px solid #dbe2ea", borderRadius:14, padding:18, background:"#fff" };
const h2: React.CSSProperties = { margin:"0 0 14px", fontSize:19, fontWeight:650 };
const label: React.CSSProperties = { display:"block", fontSize:13, fontWeight:600, color:"#334155" };
const input: React.CSSProperties = { display:"block", boxSizing:"border-box", width:"100%", marginTop:6, padding:"10px 12px", border:"1px solid #cbd5e1", borderRadius:8, color:"#0f172a", background:"#fff" };
const textarea: React.CSSProperties = { display:"block", boxSizing:"border-box", width:"100%", minHeight:90, marginTop:6, padding:12, border:"1px solid #cbd5e1", borderRadius:8, color:"#0f172a", background:"#fff", lineHeight:1.5 };
const button: React.CSSProperties = { border:0, borderRadius:8, padding:"10px 14px", background:"#172554", color:"#fff", cursor:"pointer", fontWeight:600 };
const secondary: React.CSSProperties = { border:"1px solid #cbd5e1", borderRadius:8, padding:"9px 12px", background:"#fff", color:"#1e293b", cursor:"pointer" };
const muted: React.CSSProperties = { fontSize:12, lineHeight:1.6, color:"#64748b" };
const row: React.CSSProperties = { display:"flex", alignItems:"center", justifyContent:"space-between", flexWrap:"wrap", gap:8 };
const themeCard: React.CSSProperties = { display:"grid", gap:6, textAlign:"left", padding:12, border:"1px solid", borderRadius:10, background:"#fff", color:"#17202a", cursor:"pointer" };
const badge: React.CSSProperties = { justifySelf:"start", fontSize:11, padding:"3px 7px", borderRadius:99, background:"#f1f5f9", color:"#475569" };
const categoryChip: React.CSSProperties = { fontSize:10, padding:"4px 6px", borderRadius:6, background:"#f1f5f9", color:"#475569" };
const pre: React.CSSProperties = { whiteSpace:"pre-wrap", overflowWrap:"anywhere", background:"#0f172a", color:"#e2e8f0", padding:14, borderRadius:10, fontSize:12, maxHeight:520, overflow:"auto" };

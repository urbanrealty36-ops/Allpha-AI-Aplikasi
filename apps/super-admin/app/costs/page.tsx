"use client";

import { FormEvent, useEffect, useState } from "react";

type Session = { access_token: string; refresh_token: string; expires_at: number; user: { id: string; email?: string } };
type AuthResponse = { access_token?: string; refresh_token?: string; expires_in?: number; user?: { id: string; email?: string }; error_description?: string; msg?: string };
type Operator = { id: string; email?: string; scopes: string[] };
type CostConfig = {
  id: string; provider_id: string; model_id: string; model_version: string; pricing_version: string;
  cost_unit: string; input_micro_cost_per_token: number; output_micro_cost_per_token: number;
  max_cost_microunits: number; max_prompt_bytes: number; max_output_tokens: number; max_latency_ms: number;
  status: "draft" | "active" | "archived"; policy_approved: boolean; effective_at?: string | null; created_at: string;
};
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");
const supabaseUrl = (process.env.NEXT_PUBLIC_SUPABASE_URL || "").replace(/\/$/, "");
const publishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || "";

function sessionFrom(data: AuthResponse): Session {
  if (!data.access_token || !data.refresh_token || !data.user?.id) throw new Error(data.error_description || data.msg || "Supabase Auth tidak mengembalikan sesi.");
  return { access_token: data.access_token, refresh_token: data.refresh_token, expires_at: Date.now() + Math.max(60, data.expires_in || 3600) * 1000, user: data.user };
}
async function authRequest(body: Record<string, string>, grant: "password" | "refresh_token"): Promise<Session> {
  if (!supabaseUrl || !publishableKey) throw new Error("Konfigurasi Supabase public belum tersedia.");
  const response = await fetch(`${supabaseUrl}/auth/v1/token?grant_type=${grant}`, { method: "POST", headers: { apikey: publishableKey, "Content-Type": "application/json" }, body: JSON.stringify(body), cache: "no-store" });
  const data = await response.json().catch(() => ({})) as AuthResponse;
  if (!response.ok) throw new Error(data.error_description || data.msg || "Autentikasi gagal.");
  return sessionFrom(data);
}
async function apiFetch(path: string, session: Session, init: RequestInit = {}) {
  let current = session;
  if (current.expires_at <= Date.now() + 30000) current = await authRequest({ refresh_token: current.refresh_token }, "refresh_token");
  const send = (token: string) => fetch(apiBase + path, { ...init, cache: "no-store", headers: { Accept: "application/json", "Content-Type": "application/json", ...(init.headers || {}), Authorization: `Bearer ${token}` } });
  let response = await send(current.access_token);
  if (response.status === 401) {
    current = await authRequest({ refresh_token: current.refresh_token }, "refresh_token");
    response = await send(current.access_token);
  }
  return response;
}
async function readBody<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => ({})) as { error?: { message?: string } };
  if (!response.ok) throw new Error(data.error?.message || `Permintaan gagal (HTTP ${response.status}).`);
  return data as T;
}
const emptyForm = {
  provider_id: "", model_id: "", model_version: "", pricing_version: "", cost_unit: "microunits",
  input_micro_cost_per_token: "0", output_micro_cost_per_token: "0", max_cost_microunits: "1000000",
  max_prompt_bytes: "16384", max_output_tokens: "1024", max_latency_ms: "30000",
};

export default function ModelCostsPage() {
  const [session, setSession] = useState<Session | null>(null);
  const [operator, setOperator] = useState<Operator | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [items, setItems] = useState<CostConfig[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [editing, setEditing] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function refresh(active = session) {
    if (!active) return;
    setBusy(true); setError("");
    try {
      const access = await readBody<{ operator: Operator }>(await apiFetch("/v1/admin/operator/access", active));
      setOperator(access.operator);
      if (!access.operator.scopes.includes("platform:operations.read")) throw new Error("Scope platform:operations.read diperlukan.");
      const body = await readBody<{ items: CostConfig[] }>(await apiFetch("/v1/admin/model-costs?limit=100", active));
      setItems(body.items || []);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Konfigurasi biaya gagal dimuat."); }
    finally { setBusy(false); }
  }
  useEffect(() => { if (session) void refresh(session); }, [session?.access_token]);

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try { const active = await authRequest({ email: email.trim(), password }, "password"); setSession(active); setPassword(""); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Login gagal."); }
    finally { setBusy(false); }
  }
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!session) return;
    setBusy(true); setError(""); setNotice("");
    const payload = {
      provider_id: form.provider_id.trim(), model_id: form.model_id.trim(), model_version: form.model_version.trim(),
      pricing_version: form.pricing_version.trim(), cost_unit: form.cost_unit.trim(),
      input_micro_cost_per_token: Number(form.input_micro_cost_per_token), output_micro_cost_per_token: Number(form.output_micro_cost_per_token),
      max_cost_microunits: Number(form.max_cost_microunits), max_prompt_bytes: Number(form.max_prompt_bytes),
      max_output_tokens: Number(form.max_output_tokens), max_latency_ms: Number(form.max_latency_ms),
    };
    try {
      const response = editing
        ? await apiFetch("/v1/admin/model-costs/" + encodeURIComponent(editing), session, { method: "PATCH", body: JSON.stringify(Object.fromEntries(Object.entries(payload).filter(([key]) => !["provider_id","model_id"].includes(key)))) })
        : await apiFetch("/v1/admin/model-costs", session, { method: "POST", body: JSON.stringify(payload) });
      await readBody(response);
      setNotice(editing ? "Draft tarif diperbarui." : "Draft tarif dibuat. Nilai biaya yang dimasukkan adalah konfigurasi operator, bukan tarif vendor yang diverifikasi otomatis.");
      setForm(emptyForm); setEditing(null); setReason(""); await refresh(session);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Simpan konfigurasi gagal."); }
    finally { setBusy(false); }
  }
  async function activate(item: CostConfig) {
    if (!session || !operator?.scopes.includes("platform:capabilities.review.high_risk")) return;
    if (reason.trim().length < 8) { setError("Alasan aktivasi minimal 8 karakter."); return; }
    if (!window.confirm("Aktifkan versi tarif " + item.pricing_version + " untuk " + item.provider_id + " / " + item.model_id + "? Aktivasi tarif tidak menyetujui policy model atau mengaktifkan runtime.")) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const body = await readBody<{ message: string }>(await apiFetch("/v1/admin/model-costs/" + encodeURIComponent(item.id) + "/activate", session, { method: "POST", body: JSON.stringify({ reason: reason.trim() }) }));
      setNotice(body.message); setReason(""); await refresh(session);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Aktivasi tarif gagal."); }
    finally { setBusy(false); }
  }
  async function archive(item: CostConfig) {
    if (!session || !operator?.scopes.includes("platform:capabilities.review.high_risk")) return;
    if (reason.trim().length < 8) { setError("Alasan arsip minimal 8 karakter."); return; }
    if (!window.confirm("Arsipkan konfigurasi " + item.pricing_version + "?")) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await readBody(await apiFetch("/v1/admin/model-costs/" + encodeURIComponent(item.id) + "/archive", session, { method: "POST", body: JSON.stringify({ reason: reason.trim() }) }));
      setNotice("Konfigurasi diarsipkan."); setReason(""); await refresh(session);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Arsip gagal."); }
    finally { setBusy(false); }
  }
  function edit(item: CostConfig) {
    setEditing(item.id);
    setForm({
      provider_id: item.provider_id, model_id: item.model_id, model_version: item.model_version, pricing_version: item.pricing_version,
      cost_unit: item.cost_unit, input_micro_cost_per_token: String(item.input_micro_cost_per_token),
      output_micro_cost_per_token: String(item.output_micro_cost_per_token), max_cost_microunits: String(item.max_cost_microunits),
      max_prompt_bytes: String(item.max_prompt_bytes), max_output_tokens: String(item.max_output_tokens), max_latency_ms: String(item.max_latency_ms),
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  const canWrite = Boolean(operator?.scopes.includes("platform:capabilities.review"));
  const canActivate = Boolean(operator?.scopes.includes("platform:capabilities.review.high_risk"));
  const field = (key: keyof typeof emptyForm, label: string, type = "text") => <label key={key} style={{display:"grid",gap:6,fontSize:13,color:"#344054"}}>{label}<input type={type} required value={form[key]} onChange={event => setForm(current => ({...current,[key]:event.target.value}))} style={{padding:10,border:"1px solid #d0d5dd",borderRadius:8,minWidth:0}} /></label>;

  return <main style={{maxWidth:1200,margin:"0 auto",padding:"24px 18px",color:"#101828",fontFamily:"Arial, sans-serif"}}>
    <header style={{display:"flex",justifyContent:"space-between",alignItems:"center",gap:16,flexWrap:"wrap",marginBottom:20}}>
      <div><a href="/" style={{color:"#475467"}}>← Super Admin</a><p style={{fontSize:12,letterSpacing:1.2,color:"#667085",marginBottom:6}}>ALLPHA / GOVERNANCE / COST OPERATIONS</p><h1 style={{fontSize:30,margin:"0 0 8px"}}>Konfigurasi biaya model AI</h1><p style={{color:"#475467",margin:0}}>CRUD tarif, versi harga, batas penggunaan dan aktivasi tarif lewat backend.</p></div>
      {session && <button onClick={() => {setSession(null);setOperator(null);setItems([]);}} style={{padding:"10px 14px"}}>Logout</button>}
    </header>
    <section style={{border:"1px solid #eaecf0",borderRadius:12,padding:18,marginBottom:18,background:"#fff"}}>
      <strong>Status pengamanan</strong>
      <p style={{color:"#475467",lineHeight:1.6}}>Tarif aktif tidak sama dengan policy model yang disetujui. Policy tetap tidak disetujui secara default. API key provider tidak disimpan di tabel atau browser; kredensial tetap berada di secret store server.</p>
    </section>
    {!session && <section style={{border:"1px solid #eaecf0",borderRadius:12,padding:18,marginBottom:18}}>
      <h2>Login operator</h2><form onSubmit={login} style={{display:"grid",gap:12,maxWidth:420}}>
        <label>Email<input type="email" autoComplete="username" required value={email} onChange={event=>setEmail(event.target.value)} style={{display:"block",width:"100%",padding:10,marginTop:5}} /></label>
        <label>Password<input type="password" autoComplete="current-password" required value={password} onChange={event=>setPassword(event.target.value)} style={{display:"block",width:"100%",padding:10,marginTop:5}} /></label>
        <button type="submit" disabled={busy} style={{padding:12}}>{busy ? "Memverifikasi…" : "Login & verifikasi operator"}</button>
      </form><p style={{fontSize:13,color:"#667085"}}>Sesi hanya berada di memori halaman ini; token tidak disimpan ke browser storage.</p>
    </section>}
    {session && operator && <section style={{border:"1px solid #eaecf0",borderRadius:12,padding:18,marginBottom:18}}>
      <div style={{display:"flex",justifyContent:"space-between",gap:12,flexWrap:"wrap"}}><div><h2 style={{marginTop:0}}>Tambah / ubah draft tarif</h2><p style={{color:"#667085"}}>Angka awal hanya placeholder form, tidak tersimpan otomatis. Masukkan nilai resmi yang telah disetujui operator.</p></div><span>{operator.email || operator.id}</span></div>
      {canWrite ? <form onSubmit={save} style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(220px,1fr))",gap:12}}>
        {field("provider_id","Provider ID (contoh: nvidia-nim)")} {field("model_id","Model ID")} {field("model_version","Model version")} {field("pricing_version","Pricing version")} {field("cost_unit","Unit biaya")}
        {field("input_micro_cost_per_token","Biaya input / token (microunits)","number")} {field("output_micro_cost_per_token","Biaya output / token (microunits)","number")} {field("max_cost_microunits","Batas biaya per eksekusi (microunits)","number")}
        {field("max_prompt_bytes","Batas prompt (bytes)","number")} {field("max_output_tokens","Batas output token","number")} {field("max_latency_ms","Batas latency (ms)","number")}
        <div style={{display:"flex",gap:8,alignItems:"end"}}><button type="submit" disabled={busy} style={{padding:11}}>{busy ? "Menyimpan…" : editing ? "Simpan perubahan draft" : "Buat draft tarif"}</button>{editing && <button type="button" onClick={()=>{setEditing(null);setForm(emptyForm);}} style={{padding:11}}>Batal</button>}</div>
      </form> : <p>Scope platform:capabilities.review diperlukan untuk mengubah konfigurasi.</p>}
    </section>}
    {session && operator && <section style={{border:"1px solid #eaecf0",borderRadius:12,padding:18,marginBottom:18}}>
      <h2>Aktivasi & arsip</h2><label style={{display:"grid",gap:6,maxWidth:600}}>Alasan aktivasi/arsip (min. 8 karakter)<input value={reason} onChange={event=>setReason(event.target.value)} minLength={8} maxLength={500} style={{padding:10}} placeholder="Contoh: tarif vendor terverifikasi untuk periode peluncuran" /></label>
      <div style={{overflowX:"auto",marginTop:16}}><table style={{width:"100%",borderCollapse:"collapse",fontSize:13}}><thead><tr>{["Provider / Model","Versi","Tarif input/output","Batas","Status","Policy","Aksi"].map(label=><th key={label} style={{textAlign:"left",padding:10,borderBottom:"1px solid #eaecf0"}}>{label}</th>)}</tr></thead><tbody>
        {items.map(item=><tr key={item.id}>{[
          <><strong>{item.provider_id}</strong><br/>{item.model_id}<br/><small>{item.model_version}</small></>,
          item.pricing_version,
          <>↑ {item.input_micro_cost_per_token} / ↓ {item.output_micro_cost_per_token}<br/><small>{item.cost_unit} per token</small></>,
          <>{item.max_cost_microunits} {item.cost_unit}<br/><small>{item.max_output_tokens} output tokens · {item.max_latency_ms} ms</small></>,
          <span style={{fontWeight:700,color:item.status==="active"?"#067647":item.status==="draft"?"#b54708":"#667085"}}>{item.status.toUpperCase()}</span>,
          item.policy_approved ? "APPROVED" : "NOT APPROVED",
          <div style={{display:"flex",gap:6,flexWrap:"wrap"}}>
            {item.status==="draft" && canWrite && <button disabled={busy} onClick={()=>edit(item)}>Edit</button>}
            {item.status==="draft" && canActivate && <button disabled={busy || reason.trim().length<8} onClick={()=>void activate(item)}>Aktifkan tarif</button>}
            {item.status!=="archived" && canActivate && <button disabled={busy || reason.trim().length<8} onClick={()=>void archive(item)}>Arsipkan</button>}
          </div>
        ].map((cell,index)=><td key={index} style={{padding:10,borderBottom:"1px solid #f2f4f7",verticalAlign:"top"}}>{cell}</td>)}</tr>)}
        {!items.length && <tr><td colSpan={7} style={{padding:16,color:"#667085"}}>Belum ada konfigurasi biaya. Tidak ada tarif vendor yang diisi otomatis.</td></tr>}
      </tbody></table></div>
      <button onClick={()=>void refresh()} disabled={busy} style={{marginTop:14,padding:10}}>{busy?"Memuat…":"Refresh konfigurasi"}</button>
    </section>}
    {error && <section role="alert" style={{padding:14,background:"#fef3f2",color:"#b42318",borderRadius:8,marginBottom:12}}>{error}</section>}
    {notice && <section role="status" style={{padding:14,background:"#ecfdf3",color:"#067647",borderRadius:8,marginBottom:12}}>{notice}</section>}
    <footer style={{fontSize:12,color:"#667085",padding:"16px 0"}}>Allpha · Model Cost Operations · Source of truth: FastAPI + Supabase. UI activation does not imply runtime/policy activation.</footer>
  </main>;
}

"use client";

import { FormEvent, useState } from "react";

const api = (process.env.NEXT_PUBLIC_API_BASE_URL || "https://api.allpha.web.id").replace(/\/$/, "");
const supabase = (process.env.NEXT_PUBLIC_SUPABASE_URL || "").replace(/\/$/, "");
const publicKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || "";

type Session = { access_token: string; refresh_token: string; user: { id: string; email?: string } };
type NodeRow = { node_key: string; level: string; display_name: string; status: string; parent_id?: string | null };
type AssetRow = { asset_key: string; version: number; display_name: string; category?: string; sha256: string; status: string; moderation_status?: string; license_evidence_status?: string; source_url?: string };

export default function SpatialGovernancePage() {
  const [session, setSession] = useState<Session | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [nodes, setNodes] = useState<NodeRow[]>([]);
  const [assets, setAssets] = useState<AssetRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [node, setNode] = useState({node_key:"",parent_key:"",level:"universe",slug:"",display_name:"",access_policy:"public"});
  const [evidence, setEvidence] = useState<Record<string,string>>({});
  const [reason, setReason] = useState<Record<string,string>>({});

  async function login(event: FormEvent) {
    event.preventDefault(); setError(""); setBusy(true);
    try {
      if (!supabase || !publicKey) throw new Error("Konfigurasi Supabase public URL/key belum tersedia.");
      const r = await fetch(supabase + "/auth/v1/token?grant_type=password", {method:"POST",headers:{apikey:publicKey,"Content-Type":"application/json"},body:JSON.stringify({email,password}),cache:"no-store"});
      const body = await r.json();
      if (!r.ok || !body.access_token || !body.user?.id) throw new Error(body.msg || body.error_description || "Login Supabase gagal.");
      setSession({access_token:body.access_token,refresh_token:body.refresh_token,user:body.user});
      setMessage("Login berhasil. Hak operator tetap diverifikasi oleh API.");
    } catch (e) { setError(e instanceof Error ? e.message : "Login gagal."); }
    finally { setBusy(false); }
  }
  async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
    if (!session) throw new Error("Login operator diperlukan.");
    const response = await fetch(api + path, {...init,cache:"no-store",headers:{Accept:"application/json","Content-Type":"application/json",...(init.headers||{}),Authorization:"Bearer "+session.access_token}});
    const body = await response.json().catch(()=>({}));
    if (!response.ok) {
      const detail = body.detail;
      throw new Error(typeof detail === "string" ? detail : detail?.message || body.message || "API gagal ("+response.status+").");
    }
    return body as T;
  }
  async function load() {
    setBusy(true); setError(""); setMessage("");
    try {
      const [n,a] = await Promise.all([
        call<{items:NodeRow[]}>("/v1/admin/spatial/nodes?status=draft&limit=100"),
        call<{items:AssetRow[]}>("/v1/admin/spatial/assets/review?limit=100"),
      ]);
      setNodes(n.items || []); setAssets(a.items || []); setMessage("Data governance dimuat dari API kanonis.");
    } catch(e) { setError(e instanceof Error ? e.message : "Gagal memuat data."); }
    finally { setBusy(false); }
  }
  async function createNode(event: FormEvent) {
    event.preventDefault(); setError(""); setMessage(""); setBusy(true);
    try {
      const payload = {...node,parent_key:node.parent_key || null,coordinates:null,landmarks:[],scene_key:null};
      await call("/v1/admin/spatial/nodes",{method:"POST",body:JSON.stringify(payload)});
      setMessage("Node tersimpan sebagai draft. Lanjutkan submit dan review melalui alur governance.");
      setNode({node_key:"",parent_key:"",level:"universe",slug:"",display_name:"",access_policy:"public"});
      await load();
    } catch(e) {setError(e instanceof Error ? e.message : "Node gagal dibuat.");}
    finally {setBusy(false);}
  }
  async function nodeAction(key:string, action:"submit"|"review"|"publish", decision?: "approved"|"rejected") {
    setError("");setMessage("");setBusy(true);
    try {
      const body = action==="review" ? {decision,reason:reason["node:"+key] || "Review berdasarkan metadata node yang disediakan."} : undefined;
      await call("/v1/admin/spatial/nodes/"+encodeURIComponent(key)+"/"+action,{method:"POST",...(body?{body:JSON.stringify(body)}:{})});
      setMessage("Aksi node "+key+" berhasil diproses."); await load();
    } catch(e) {setError(e instanceof Error ? e.message : "Aksi node gagal.");}
    finally {setBusy(false);}
  }
  async function assetAction(asset:AssetRow, decision:"approved"|"rejected"|"publish") {
    setError("");setMessage("");setBusy(true);
    try {
      const key=encodeURIComponent(asset.asset_key), ver=asset.version;
      if(decision==="publish") {
        await call("/v1/admin/spatial/assets/"+key+"/"+ver+"/publish",{method:"POST"});
      } else {
        await call("/v1/admin/spatial/assets/"+key+"/"+ver+"/review",{method:"POST",body:JSON.stringify({decision,reason:reason["asset:"+asset.asset_key] || "Review metadata sumber dan checksum.",category:asset.category || undefined,license_evidence_uri:decision==="approved" ? evidence[asset.asset_key] : undefined})});
      }
      setMessage("Aksi aset "+asset.asset_key+" diproses."); await load();
    } catch(e) {setError(e instanceof Error ? e.message : "Review aset gagal.");}
    finally {setBusy(false);}
  }

  return <main style={{maxWidth:1120,margin:"0 auto",padding:"28px 20px",fontFamily:"system-ui,sans-serif",color:"#17202a"}}>
    <header style={{marginBottom:24}}><p style={{fontSize:12,letterSpacing:2,fontWeight:700}}>ALLPHA UNIVERSE · ENG-P21</p><h1 style={{fontSize:30,margin:"6px 0"}}>Spatial Governance</h1><p style={{color:"#596579"}}>Node lifecycle, GLB moderation, license evidence, and audit-ready operator actions.</p></header>
    {!session ? <form onSubmit={login} style={{maxWidth:440,border:"1px solid #d7dce3",borderRadius:12,padding:20,display:"grid",gap:12}}>
      <h2 style={{fontSize:18}}>Login operator</h2><label>Email<input required type="email" value={email} onChange={e=>setEmail(e.target.value)} style={inputStyle}/></label><label>Password<input required type="password" value={password} onChange={e=>setPassword(e.target.value)} style={inputStyle}/></label><button disabled={busy} style={buttonStyle}>{busy?"Memproses…":"Login melalui Supabase Auth"}</button><small>Login tidak otomatis memberi hak operator. API memeriksa grant dan audit pada setiap aksi.</small>
    </form> : <section style={{display:"grid",gap:24}}>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",gap:12,flexWrap:"wrap"}}><span>Operator: {session.user.email || session.user.id}</span><div style={{display:"flex",gap:8}}><button style={buttonStyle} disabled={busy} onClick={load}>Muat data terbaru</button><button style={secondaryStyle} onClick={()=>{setSession(null);setNodes([]);setAssets([]);}}>Keluar</button></div></div>
      <section style={panelStyle}><h2 style={h2Style}>1. Buat node spasial</h2><form onSubmit={createNode} style={formGrid}>
        <label>Node key<input required pattern="[a-z0-9][a-z0-9._-]{2,127}" value={node.node_key} onChange={e=>setNode({...node,node_key:e.target.value})} style={inputStyle}/></label>
        <label>Level<select value={node.level} onChange={e=>setNode({...node,level:e.target.value})} style={inputStyle}>{["universe","galaxy","world","district","zone","booth","poi","scene_object"].map(v=><option key={v}>{v}</option>)}</select></label>
        <label>Parent key (wajib selain Universe)<input value={node.parent_key} onChange={e=>setNode({...node,parent_key:e.target.value})} style={inputStyle}/></label>
        <label>Slug<input required value={node.slug} onChange={e=>setNode({...node,slug:e.target.value})} style={inputStyle}/></label>
        <label>Nama tampilan<input required value={node.display_name} onChange={e=>setNode({...node,display_name:e.target.value})} style={inputStyle}/></label>
        <label>Akses<select value={node.access_policy} onChange={e=>setNode({...node,access_policy:e.target.value})} style={inputStyle}><option value="public">public</option><option value="authenticated">authenticated</option><option value="owner_only">owner_only</option></select></label>
        <button disabled={busy} style={buttonStyle}>Buat draft</button>
      </form><p style={mutedStyle}>Tidak ada seed bisnis. Koordinat/landmark dapat ditambahkan setelah node dibuat melalui kontrak API tervalidasi.</p></section>
      <section style={panelStyle}><h2 style={h2Style}>2. Node untuk governance</h2>{nodes.length===0?<p style={mutedStyle}>Tidak ada draft node dalam hasil query. Muat status review/approved/published melalui API bila diperlukan.</p>:nodes.map(n=><article key={n.node_key} style={itemStyle}><div><strong>{n.display_name}</strong><p style={mutedStyle}>{n.node_key} · {n.level} · {n.status}</p></div><div style={{display:"flex",gap:6,flexWrap:"wrap"}}><button style={secondaryStyle} onClick={()=>nodeAction(n.node_key,"submit")}>Ajukan review</button></div></article>)}</section>
      <section style={panelStyle}><h2 style={h2Style}>3. Review aset GLB</h2><p style={mutedStyle}>Persetujuan membutuhkan bukti lisensi HTTPS. Tidak ada publikasi otomatis.</p>{assets.length===0?<p style={mutedStyle}>Tidak ada aset dalam daftar review, atau belum tersedia izin operator.</p>:assets.map(a=><article key={a.asset_key+":"+a.version} style={itemStyle}><div style={{minWidth:240,flex:1}}><strong>{a.display_name}</strong><p style={mutedStyle}>{a.asset_key} · v{a.version} · {a.category || "kategori belum terpetakan"}</p><code style={{fontSize:11,overflowWrap:"anywhere"}}>SHA-256: {a.sha256}</code><p style={mutedStyle}>Status: {a.status} · moderasi: {a.moderation_status || "pending"} · lisensi: {a.license_evidence_status || "unverified"}</p><input placeholder="URL bukti lisensi HTTPS (wajib approve)" value={evidence[a.asset_key]||""} onChange={e=>setEvidence({...evidence,[a.asset_key]:e.target.value})} style={inputStyle}/><input placeholder="Alasan review" value={reason["asset:"+a.asset_key]||""} onChange={e=>setReason({...reason,["asset:"+a.asset_key]:e.target.value})} style={inputStyle}/></div><div style={{display:"flex",gap:6,flexWrap:"wrap",alignContent:"start"}}><button style={buttonStyle} onClick={()=>assetAction(a,"approved")}>Approve</button><button style={secondaryStyle} onClick={()=>assetAction(a,"rejected")}>Reject</button><button style={secondaryStyle} onClick={()=>assetAction(a,"publish")}>Publish</button></div></article>)}</section>
    </section>}
    {error&&<p role="alert" style={{marginTop:16,color:"#a32626",background:"#fff1f1",padding:12,borderRadius:8}}>{error}</p>}
    {message&&<p role="status" style={{marginTop:16,color:"#205c3b",background:"#eefaf2",padding:12,borderRadius:8}}>{message}</p>}
  </main>;
}
const inputStyle: React.CSSProperties={display:"block",width:"100%",boxSizing:"border-box",marginTop:5,padding:"10px 12px",border:"1px solid #cbd2dc",borderRadius:7,background:"#fff",color:"#17202a"};
const buttonStyle: React.CSSProperties={padding:"10px 14px",border:0,borderRadius:7,background:"#17202a",color:"#fff",cursor:"pointer"};
const secondaryStyle: React.CSSProperties={padding:"9px 12px",border:"1px solid #cbd2dc",borderRadius:7,background:"#fff",color:"#17202a",cursor:"pointer"};
const panelStyle: React.CSSProperties={border:"1px solid #d7dce3",borderRadius:12,padding:18};
const h2Style: React.CSSProperties={fontSize:20,margin:"0 0 14px"};
const mutedStyle: React.CSSProperties={fontSize:13,color:"#657184"};
const formGrid: React.CSSProperties={display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(220px,1fr))",gap:12,alignItems:"end"};
const itemStyle: React.CSSProperties={display:"flex",gap:16,justifyContent:"space-between",alignItems:"center",flexWrap:"wrap",padding:"14px 0",borderTop:"1px solid #e5e8ed"};

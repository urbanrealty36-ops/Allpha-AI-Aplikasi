"use client";

import { FormEvent, useState } from "react";

const api = (process.env.NEXT_PUBLIC_API_BASE_URL || "https://api.allpha.web.id").replace(/\/$/, "");
const supabase = (process.env.NEXT_PUBLIC_SUPABASE_URL || "").replace(/\/$/, "");
const publicKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || "";

type Session = { access_token: string; refresh_token: string; user: { id: string; email?: string } };
type NodeRow = { node_key: string; level: string; display_name: string; status: string; parent_id?: string | null };
type AssetRow = { asset_key: string; version: number; display_name: string; category?: string; sha256: string; status: string; moderation_status?: string; license_evidence_status?: string; source_url?: string; license_evidence?: {note?:string;status?:string}; provenance?: {source_repository?:string;source_review_state?:string;source_license_claim?:string} };
type MappingRow = { id:string; agent_id:string; asset_key:string; asset_version:number; evidence_type:string; evidence_uri:string; evidence_sha256?:string|null; rationale:string; status:string; review_reason?:string|null };

export default function SpatialGovernancePage() {
  const [session, setSession] = useState<Session | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [nodes, setNodes] = useState<NodeRow[]>([]);
  const [nodeStatus, setNodeStatus] = useState("draft");

  const [mappings, setMappings] = useState<MappingRow[]>([]);
  const [mappingStatus, setMappingStatus] = useState("pending");
  const [mappingDraft, setMappingDraft] = useState({agent_id:"",asset_key:"",asset_version:"1",evidence_type:"authoritative_agent_profile",evidence_uri:"",evidence_sha256:"",rationale:""});  const [assets, setAssets] = useState<AssetRow[]>([]);
  const [assetOffset, setAssetOffset] = useState(0);
  const [busy, setBusy] = useState(false);
  const [node, setNode] = useState({node_key:"",parent_key:"",level:"universe",slug:"",display_name:"",access_policy:"public"});
  const [evidence, setEvidence] = useState<Record<string,string>>({});
  const [licenseReviewed, setLicenseReviewed] = useState<Record<string,boolean>>({});
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
  async function batchActivate() {
    if (!session) return;
    setBusy(true); setError(""); setMessage("");
    const checkpointKey = "allpha:spatial-glb-batch:v2:" + session.user.id;
    type Cursor = {asset_id:string;version:number} | null;
    type Checkpoint = {previewDone:boolean;publishDone:boolean;previewCursor:Cursor;publishCursor:Cursor};
    const fresh:Checkpoint = {previewDone:false,publishDone:false,previewCursor:null,publishCursor:null};
    let checkpoint:Checkpoint = fresh;
    try {
      const saved = window.localStorage.getItem(checkpointKey);
      if (saved) {
        try {
          const parsed = JSON.parse(saved) as Partial<Checkpoint>;
          if (typeof parsed.previewDone === "boolean" && typeof parsed.publishDone === "boolean") {
            checkpoint = {...fresh,...parsed};
          }
        } catch { window.localStorage.removeItem(checkpointKey); }
      }
      const total = {preview:{succeeded:0,skipped:0,failed:0},publish:{succeeded:0,skipped:0,failed:0}};
      let runs = 0;
      while (runs < 20 && !(checkpoint.previewDone && checkpoint.publishDone)) {
        const mode = checkpoint.previewDone ? "catalog_publish" : checkpoint.publishDone ? "internal_preview" : "both";
        const result = await call<{
          internal_preview:{succeeded:number;skipped:number;failed:number;next_cursor:Cursor;has_more:boolean};
          catalog_publish:{succeeded:number;skipped:number;failed:number;next_cursor:Cursor;has_more:boolean};
          note:string;
        }>("/v1/admin/spatial/assets/batch-activate", {
          method:"POST",
          body:JSON.stringify({
            mode,limit:100,
            ...(mode !== "catalog_publish" && checkpoint.previewCursor ? {preview_after_asset_id:checkpoint.previewCursor.asset_id,preview_after_version:checkpoint.previewCursor.version}:{}),
            ...(mode !== "internal_preview" && checkpoint.publishCursor ? {publish_after_asset_id:checkpoint.publishCursor.asset_id,publish_after_version:checkpoint.publishCursor.version}:{})
          })
        });
        if (mode !== "catalog_publish") {
          total.preview.succeeded += result.internal_preview.succeeded;
          total.preview.skipped += result.internal_preview.skipped;
          total.preview.failed += result.internal_preview.failed;
          checkpoint.previewDone = !result.internal_preview.has_more;
          checkpoint.previewCursor = result.internal_preview.has_more ? result.internal_preview.next_cursor : null;
        }
        if (mode !== "internal_preview") {
          total.publish.succeeded += result.catalog_publish.succeeded;
          total.publish.skipped += result.catalog_publish.skipped;
          total.publish.failed += result.catalog_publish.failed;
          checkpoint.publishDone = !result.catalog_publish.has_more;
          checkpoint.publishCursor = result.catalog_publish.has_more ? result.catalog_publish.next_cursor : null;
        }
        runs += 1;
        if (checkpoint.previewDone && checkpoint.publishDone) {
          window.localStorage.removeItem(checkpointKey);
        } else {
          window.localStorage.setItem(checkpointKey, JSON.stringify(checkpoint));
        }
      }
      const complete = checkpoint.previewDone && checkpoint.publishDone;
      const batchMessage = "Batch " + (complete ? "selesai" : "tersimpan untuk dilanjutkan") + " setelah " + runs + " permintaan. Preview internal: berhasil " + total.preview.succeeded + ", dilewati " + total.preview.skipped + ", gagal " + total.preview.failed + ". Publikasi katalog: berhasil " + total.publish.succeeded + ", dilewati " + total.publish.skipped + ", gagal " + total.publish.failed + ". " + (complete ? "Cursor selesai; batch baru akan mengulang pemeriksaan untuk retry kegagalan." : "Checkpoint tersimpan di browser ini; tekan tombol lagi untuk melanjutkan.") + " Aset ditolak moderasi tidak dipreview; publikasi hanya untuk approved + license-verified.";
      await load();
      setMessage(batchMessage);
    } catch(e) { setError(e instanceof Error ? e.message : "Batch activation gagal. Checkpoint sebelumnya dipertahankan agar dapat dilanjutkan."); }
    finally { setBusy(false); }
  }
  async function load() {
    setBusy(true); setError(""); setMessage("");
    try {
      const [n,a,m] = await Promise.all([
        call<{items:NodeRow[]}>("/v1/admin/spatial/nodes?status="+nodeStatus+"&limit=100"),
        call<{items:AssetRow[]}>("/v1/admin/spatial/assets/review?limit=100&offset="+assetOffset),
        call<{items:MappingRow[]}>("/v1/admin/spatial/agent-asset-mappings?status="+mappingStatus+"&limit=100"),
      ]);
      setNodes(n.items || []); setAssets(a.items || []); setMappings(m.items || []); setMessage("Data governance dimuat dari API kanonis.");
    } catch(e) { setError(e instanceof Error ? e.message : "Gagal memuat data."); }
    finally { setBusy(false); }
  }
  async function changeAssetPage(nextOffset:number) {
    setBusy(true);setError("");
    try { const data=await call<{items:AssetRow[]}>("/v1/admin/spatial/assets/review?limit=100&offset="+nextOffset); setAssets(data.items||[]); setAssetOffset(nextOffset); }
    catch(e) {setError(e instanceof Error?e.message:"Gagal memuat halaman aset.");}
    finally {setBusy(false);}
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
  async function submitMapping(event:FormEvent) {
    event.preventDefault(); setError("");setMessage("");setBusy(true);
    try { const payload={...mappingDraft,asset_version:Number(mappingDraft.asset_version),evidence_sha256:mappingDraft.evidence_sha256||null}; await call("/v1/admin/spatial/agent-asset-mappings",{method:"POST",body:JSON.stringify(payload)}); setMessage("Usulan pemetaan dibuat dan menunggu review."); await load(); }
    catch(e) {setError(e instanceof Error?e.message:"Usulan pemetaan gagal.");} finally {setBusy(false);}
  }
  async function mappingAction(mapping:MappingRow,decision:"approved"|"rejected") {
    setError("");setMessage("");setBusy(true);
    try { await call("/v1/admin/spatial/agent-asset-mappings/"+mapping.id+"/review",{method:"POST",body:JSON.stringify({decision,reason:reason["mapping:"+mapping.id]||"Review evidence dan kecocokan checksum."})}); setMessage("Review pemetaan diproses."); await load(); }
    catch(e) {setError(e instanceof Error?e.message:"Review pemetaan gagal.");} finally {setBusy(false);}
  }

  async function assetAction(asset:AssetRow, decision:"approved"|"rejected"|"publish") {
    setError("");setMessage("");setBusy(true);
    try {
      const key=encodeURIComponent(asset.asset_key), ver=asset.version;
      if(decision==="publish") {
        await call("/v1/admin/spatial/assets/"+key+"/"+ver+"/publish",{method:"POST"});
      } else {
        await call("/v1/admin/spatial/assets/"+key+"/"+ver+"/review",{method:"POST",body:JSON.stringify({decision,reason:reason["asset:"+asset.asset_key] || "Review metadata sumber dan checksum.",category:asset.category || undefined,license_evidence_uri:decision==="approved" ? evidence[asset.asset_key] : undefined,license_evidence_reviewed:decision==="approved" ? Boolean(licenseReviewed[asset.asset_key]) : false})});
      }
      setMessage("Aksi aset "+asset.asset_key+" diproses."); await load();
    } catch(e) {setError(e instanceof Error ? e.message : "Review aset gagal.");}
    finally {setBusy(false);}
  }

  return <main style={{maxWidth:1120,margin:"0 auto",padding:"28px 20px",fontFamily:"system-ui,sans-serif",color:"#17202a"}}>
    <header style={{marginBottom:24}}><p style={{fontSize:12,letterSpacing:2,fontWeight:700}}>ALLPHA UNIVERSE · ENG-P21 / ENG-P22</p><h1 style={{fontSize:30,margin:"6px 0"}}>Spatial Governance</h1><p style={{color:"#596579"}}>Node lifecycle, GLB moderation, license evidence, and audit-ready operator actions.</p><a href="/spatial-themes" style={{display:"inline-block",marginTop:8,padding:"10px 14px",borderRadius:8,background:"#17202a",color:"#fff",textDecoration:"none"}}>Buka Spatial Theme Builder →</a><a href="/spatial-receipts" style={{display:"inline-block",marginTop:8,marginLeft:8,padding:"10px 14px",borderRadius:8,background:"#334155",color:"#fff",textDecoration:"none"}}>Rekonsiliasi Receipt GLB →</a></header>
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
      <section style={panelStyle}><h2 style={h2Style}>2. Node untuk governance</h2><label>Status<select value={nodeStatus} onChange={e=>setNodeStatus(e.target.value)} style={inputStyle}>{["draft","review","approved","published","rejected"].map(v=><option key={v}>{v}</option>)}</select></label><button style={secondaryStyle} disabled={busy} onClick={load}>Muat status</button>{nodes.length===0?<p style={mutedStyle}>Tidak ada draft node dalam hasil query. Muat status review/approved/published melalui API bila diperlukan.</p>:nodes.map(n=><article key={n.node_key} style={itemStyle}><div><strong>{n.display_name}</strong><p style={mutedStyle}>{n.node_key} · {n.level} · {n.status}</p></div><div style={{display:"flex",gap:6,flexWrap:"wrap"}}>{n.status==="draft"&&<button style={secondaryStyle} onClick={()=>nodeAction(n.node_key,"submit")}>Ajukan review</button>}{n.status==="review"&&<><input placeholder="Alasan review" value={reason["node:"+n.node_key]||""} onChange={e=>setReason({...reason,["node:"+n.node_key]:e.target.value})} style={inputStyle}/><button style={buttonStyle} onClick={()=>nodeAction(n.node_key,"review","approved")}>Approve</button><button style={secondaryStyle} onClick={()=>nodeAction(n.node_key,"review","rejected")}>Reject</button></>}{n.status==="approved"&&<button style={buttonStyle} onClick={()=>nodeAction(n.node_key,"publish")}>Publish</button>}</div></article>)}</section>
      <section style={panelStyle}><h2 style={h2Style}>3. Pemetaan Agent–GLB</h2><p style={mutedStyle}>Usulan hanya dapat mengacu pada GLB published + approved. API memvalidasi UUID Agent, bukti HTTPS, dan checksum.</p><form onSubmit={submitMapping} style={formGrid}>
<label>Agent UUID<input required value={mappingDraft.agent_id} onChange={e=>setMappingDraft({...mappingDraft,agent_id:e.target.value})} style={inputStyle}/></label><label>Asset key<input required value={mappingDraft.asset_key} onChange={e=>setMappingDraft({...mappingDraft,asset_key:e.target.value})} style={inputStyle}/></label><label>Asset version<input required type="number" min="1" value={mappingDraft.asset_version} onChange={e=>setMappingDraft({...mappingDraft,asset_version:e.target.value})} style={inputStyle}/></label><label>Jenis bukti<select value={mappingDraft.evidence_type} onChange={e=>setMappingDraft({...mappingDraft,evidence_type:e.target.value})} style={inputStyle}>{["authoritative_agent_profile","owner_attestation","source_manifest","reviewed_visual_match"].map(v=><option key={v}>{v}</option>)}</select></label><label>URL bukti HTTPS<input required type="url" pattern="https://.*" value={mappingDraft.evidence_uri} onChange={e=>setMappingDraft({...mappingDraft,evidence_uri:e.target.value})} style={inputStyle}/></label><label>SHA-256 bukti<input pattern="[a-f0-9]{64}" value={mappingDraft.evidence_sha256} onChange={e=>setMappingDraft({...mappingDraft,evidence_sha256:e.target.value})} style={inputStyle}/></label><label>Rasional<input required minLength={12} value={mappingDraft.rationale} onChange={e=>setMappingDraft({...mappingDraft,rationale:e.target.value})} style={inputStyle}/></label><button disabled={busy} style={buttonStyle}>Ajukan pemetaan</button></form><label>Status mapping<select value={mappingStatus} onChange={e=>setMappingStatus(e.target.value)} style={inputStyle}>{["pending","approved","rejected","revoked"].map(v=><option key={v}>{v}</option>)}</select></label><button style={secondaryStyle} disabled={busy} onClick={load}>Muat pemetaan</button>{mappings.length===0?<p style={mutedStyle}>Tidak ada pemetaan pada status ini.</p>:mappings.map(m=><article key={m.id} style={itemStyle}><div style={{minWidth:240,flex:1}}><strong>{m.asset_key} v{m.asset_version}</strong><p style={mutedStyle}>Agent {m.agent_id} · {m.status} · {m.evidence_type}</p><p style={mutedStyle}>Bukti: {m.evidence_uri}</p><p style={mutedStyle}>SHA-256 bukti: {m.evidence_sha256||"tidak disertakan"}</p><p style={mutedStyle}>{m.rationale}</p></div><div style={{display:"flex",gap:6,flexWrap:"wrap"}}>{m.status==="pending"&&<><input placeholder="Alasan review" value={reason["mapping:"+m.id]||""} onChange={e=>setReason({...reason,["mapping:"+m.id]:e.target.value})} style={inputStyle}/><button style={buttonStyle} disabled={busy} onClick={()=>mappingAction(m,"approved")}>Approve</button><button style={secondaryStyle} disabled={busy} onClick={()=>mappingAction(m,"rejected")}>Reject</button></>}</div></article>)}</section>
      <section style={panelStyle}><h2 style={h2Style}>4. Review aset GLB</h2><p style={mutedStyle}>Batch aktivasi internal dan publikasi katalog berjalan maksimal 100 aset per eksekusi. Preview internal tidak mengubah status lisensi. Publikasi katalog hanya memproses aset yang sudah approved dan license-verified.</p><button style={buttonStyle} disabled={busy} onClick={batchActivate}>Jalankan batch aktivasi + publikasi</button>{assets.length===0?<p style={mutedStyle}>Tidak ada aset dalam daftar review, atau belum tersedia izin operator.</p>:assets.map(a=><article key={a.asset_key+":"+a.version} style={itemStyle}><div style={{minWidth:240,flex:1}}><strong>{a.display_name}</strong><p style={mutedStyle}>{a.asset_key} · v{a.version} · {a.category || "kategori belum terpetakan"}</p><code style={{fontSize:11,overflowWrap:"anywhere"}}>SHA-256: {a.sha256}</code><p style={mutedStyle}>Status: {a.status} · moderasi: {a.moderation_status || "pending"} · lisensi: {a.license_evidence_status || "unverified"}</p><p style={mutedStyle}>Klaim sumber: {a.provenance?.source_license_claim || "tidak ada"} · review: {a.provenance?.source_review_state || a.license_evidence?.status || "belum ditinjau"}</p><p style={mutedStyle}>Repositori: {a.provenance?.source_repository || "tidak diketahui"} · {a.license_evidence?.note || ""}</p><input placeholder="URL bukti lisensi HTTPS (wajib approve)" value={evidence[a.asset_key]||""} onChange={e=>setEvidence({...evidence,[a.asset_key]:e.target.value})} style={inputStyle}/><label style={{display:"flex",gap:8,alignItems:"center",fontSize:12,marginTop:8}}><input type="checkbox" checked={Boolean(licenseReviewed[a.asset_key])} onChange={e=>setLicenseReviewed({...licenseReviewed,[a.asset_key]:e.target.checked})}/>Saya telah memeriksa lisensi, hak publik, atribusi, dan pengecualian tekstur/model</label><input placeholder="Alasan review" value={reason["asset:"+a.asset_key]||""} onChange={e=>setReason({...reason,["asset:"+a.asset_key]:e.target.value})} style={inputStyle}/></div><div style={{display:"flex",gap:6,flexWrap:"wrap",alignContent:"start"}}><button style={buttonStyle} onClick={()=>assetAction(a,"approved")}>Approve</button><button style={secondaryStyle} onClick={()=>assetAction(a,"rejected")}>Reject</button><button style={secondaryStyle} onClick={()=>assetAction(a,"publish")}>Publish</button></div></article>)}<div style={{display:"flex",gap:8,alignItems:"center",marginTop:12}}><button style={secondaryStyle} disabled={busy||assetOffset===0} onClick={()=>changeAssetPage(Math.max(0,assetOffset-100))}>Aset sebelumnya</button><span style={mutedStyle}>Offset {assetOffset} · tampil {assets.length} aset</span><button style={secondaryStyle} disabled={busy||assets.length<100} onClick={()=>changeAssetPage(assetOffset+100)}>Aset berikutnya</button></div></section>
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

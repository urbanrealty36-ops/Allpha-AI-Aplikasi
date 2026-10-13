"use client";
import { useCallback, useEffect, useState } from "react";
type Probe = { label: string; path: string; status: "checking" | "online" | "warning" | "offline"; detail: string };
type Payload = { status?: string; service?: string; version?: string; environment?: string; dependencies?: Record<string,string>; capabilities?: Record<string,boolean> };
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
export default function OperationsPage() {
 const [probes,setProbes]=useState<Probe[]>(["/healthz","/readyz","/v1/system/status"].map((path,i)=>({label:["API liveness","Dependency readiness","System diagnostics"][i],path,status:"checking",detail:"Menunggu pemeriksaan"})));
 const [busy,setBusy]=useState(false); const [checkedAt,setCheckedAt]=useState("");
 const refresh=useCallback(async()=>{
  setBusy(true); const paths=["/healthz","/readyz","/v1/system/status"], labels=["API liveness","Dependency readiness","System diagnostics"];
  const results=await Promise.all(paths.map(async(path,i):Promise<Probe>=>{
   try { const r=await fetch(apiBase+path,{cache:"no-store",headers:{Accept:"application/json"}}); const b=await r.json() as Payload;
    if(!r.ok)return {label:labels[i],path,status:"offline",detail:"HTTP "+r.status};
    if(path==="/healthz")return {label:labels[i],path,status:b.status==="ok"?"online":"warning",detail:b.service||"Respons diterima"};
    if(path==="/readyz"){const missing=Object.entries(b.dependencies||{}).filter(([,v])=>v!=="configured").map(([k])=>k);return {label:labels[i],path,status:b.status==="ready"&&!missing.length?"online":"warning",detail:missing.length?"Belum dikonfigurasi: "+missing.join(", "):"Dependensi dilaporkan siap"};}
    const missing=Object.entries(b.capabilities||{}).filter(([,v])=>v===false).map(([k])=>k);return {label:labels[i],path,status:missing.length?"warning":"online",detail:"Versi "+(b.version||"—")+" · "+(b.environment||"environment tidak dilaporkan")+(missing.length?" · belum tersedia: "+missing.join(", "):"")};
   }catch{return {label:labels[i],path,status:"offline",detail:"Tidak dapat terhubung ke "+apiBase};}
  }));
  setProbes(results);setCheckedAt(new Date().toLocaleString("id-ID"));setBusy(false);
 },[]);
 useEffect(()=>{void refresh();},[refresh]);
 const online=probes.filter(p=>p.status==="online").length;
 return <main className="shell"><aside className="sidebar"><a className="brand" href="/"><span className="mark">A</span><span><b>ALLPHA</b><small>CONTROL PLANE</small></span></a><p className="navLabel">OPERATIONS</p><a className="nav active" href="#overview">◈ &nbsp; Overview</a><div className="nav disabled">◎ &nbsp; Identity & tenants <small>ENG-P02</small></div><div className="nav disabled">◇ &nbsp; Asset catalog <small>ENG-P22</small></div><div className="nav disabled">≋ &nbsp; Audit & governance <small>ENG-P26</small></div><div className="sidebarFoot">● &nbsp; Foundation mode <small>ENG-P01</small></div></aside>
 <section className="main" id="overview"><header className="top"><div><p className="eyebrow">PLATFORM OPERATIONS / FOUNDATION</p><h1>System overview</h1><p className="sub">Status layanan aktual dari canonical FastAPI backend.</p></div><button onClick={()=>void refresh()} disabled={busy}>{busy?"Memeriksa…":"↻ Refresh status"}</button></header>
 <section className="summary"><article><label>API endpoint</label><strong className="endpoint">{apiBase}</strong><small>NEXT_PUBLIC_API_BASE_URL</small></article><article><label>Probe sehat</label><strong>{online}<span> / {probes.length}</span></strong><small>Pemeriksaan endpoint nyata</small></article><article><label>Privileged operations</label><strong className="restricted">Restricted</strong><small>Menunggu operator auth scope</small></article></section>
 <section className="panel"><header className="panelHead"><div><h2>Service checks</h2><p>Hasil fetch langsung; bukan data dashboard sintetis.</p></div><span className="live">● LIVE CHECK</span></header>{probes.map(p=><article className="probe" key={p.path}><span className={"icon "+p.status}>{p.status==="online"?"✓":p.status==="checking"?"…":"!"}</span><div className="probeText"><b>{p.label}</b><code>{p.path}</code><p>{p.detail}</p></div><span className={"pill "+p.status}>{p.status==="online"?"ONLINE":p.status==="checking"?"CHECKING":p.status==="warning"?"PARTIAL":"OFFLINE"}</span></article>)}<footer className="panelFoot"><span>Terakhir diperiksa: {checkedAt||"—"}</span><span>Browser operator → API</span></footer></section>
 <section className="notice"><b>i</b><div><strong>Security boundary aktif</strong><p>Console ini hanya menampilkan endpoint diagnostik yang tersedia. Operasi admin tetap dinonaktifkan sampai autentikasi operator, permission scope, audit, dan endpoint backend resmi tersedia.</p></div></section><footer className="pageFoot">Allpha Universe · ENG-P01 · Status mencerminkan endpoint yang dapat dijangkau browser.</footer></section></main>;
}

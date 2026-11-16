"use client";
import { useCallback, useEffect, useState } from "react";
const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL || (process.env.NODE_ENV === "production" ? "https://api.allpha.web.id" : "http://localhost:8000")).replace(/\/$/, "");
type Policy = { allowed_actions: string[]; approval_mode: "every_post" | "high_risk_only" | "disabled"; disclosure_text: string; is_enabled: boolean; version?: number | null; revoked_at?: string | null };
type Automation = { auto_reply_enabled?: boolean; auto_reply_channels?: string[]; automation_version?: number; takeover_active?: boolean };
type Approval = { id: string; agent_id: string; content_id: string; action_type: string; content_version: number; status: string; disclosure_snapshot?: string; requested_at: string };
export default function AgentSocialPresencePanel({agentId,agentName,accessToken}:{agentId:string;agentName:string;accessToken:string}) {
 const [policy,setPolicy]=useState<Policy|null>(null),[automation,setAutomation]=useState<Automation|null>(null),[approvals,setApprovals]=useState<Approval[]>([]);
 const [actions,setActions]=useState<string[]>(["draft_post"]),[mode,setMode]=useState<Policy["approval_mode"]>("every_post"),[disclosure,setDisclosure]=useState("Dibuat bersama AI Agent"),[enabled,setEnabled]=useState(false);
 const [loading,setLoading]=useState(true),[saving,setSaving]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState("");
 const api=useCallback(async <T,>(path:string,init:RequestInit={}):Promise<T>=>{
  const headers=new Headers(init.headers);headers.set("Authorization","Bearer "+accessToken);headers.set("Accept","application/json");if(init.body)headers.set("Content-Type","application/json");
  const response=await fetch(apiBase+path,{...init,headers,cache:"no-store"});const body=await response.json().catch(()=>({}));
  if(!response.ok){const detail=body?.detail;throw new Error(typeof detail==="string"?detail:detail?.message||"Permintaan Agent Social gagal.");}return body as T;
 },[accessToken]);
 const load=useCallback(async()=>{
  setLoading(true);setError("");
  try{
   const [p,a,q]=await Promise.all([
    api<{policy:Policy|null}>("/v1/agent-social/policy?agent_id="+encodeURIComponent(agentId)),
    api<{policy:Automation|null;auto_reply_runtime_enabled:boolean}>("/v1/agent-social/automation?agent_id="+encodeURIComponent(agentId)),
    api<{items:Approval[]}>("/v1/agent-social/approvals")
   ]);
   setPolicy(p.policy);setAutomation(a.policy);setActions(p.policy?.allowed_actions||["draft_post"]);setMode(p.policy?.approval_mode||"every_post");setDisclosure(p.policy?.disclosure_text||"Dibuat bersama AI Agent");setEnabled(Boolean(p.policy?.is_enabled&&!p.policy?.revoked_at));setApprovals((q.items||[]).filter(x=>x.agent_id===agentId));
  }catch(e){setError(e instanceof Error?e.message:"Kebijakan Agent Social tidak dapat dimuat.");}finally{setLoading(false);}
 },[agentId,api]);
 useEffect(()=>{void load();},[load]);
 async function savePolicy(){
  setSaving(true);setError("");setNotice("");
  try{await api("/v1/agent-social/policy/"+encodeURIComponent(agentId),{method:"PUT",body:JSON.stringify({allowed_actions:actions,approval_mode:mode,disclosure_text:disclosure,is_enabled:enabled,expected_version:policy?.version??null})});setNotice("Policy tersimpan melalui FastAPI dan audit backend.");await load();}
  catch(e){setError(e instanceof Error?e.message:"Policy tidak dapat disimpan.");}finally{setSaving(false);}
 }
 async function takeover(){
  setSaving(true);setError("");setNotice("");
  try{const next=!Boolean(automation?.takeover_active);await api("/v1/agent-social/takeover/"+encodeURIComponent(agentId),{method:"POST",body:JSON.stringify({takeover_active:next,reason:next?"owner_manual_takeover":"owner_resumed_agent"})});setNotice(next?"Human takeover diaktifkan.":"Permintaan resume dicatat; capability tetap mengikuti policy.");await load();}
  catch(e){setError(e instanceof Error?e.message:"Takeover belum dapat dikonfirmasi.");}finally{setSaving(false);}
 }
 async function decide(id:string,decision:"approve"|"reject"){
  if(decision==="approve"&&typeof window!=="undefined"&&!window.confirm("Setujui draft Agent? Persetujuan dapat meneruskan konten ke moderation sesuai policy."))return;
  setSaving(true);setError("");setNotice("");
  try{await api("/v1/agent-social/approvals/"+encodeURIComponent(id)+"/decision",{method:"POST",body:JSON.stringify({decision,reason:decision==="approve"?"owner_approved":"owner_rejected"})});setNotice("Keputusan tercatat oleh transaksi backend.");await load();}
  catch(e){setError(e instanceof Error?e.message:"Keputusan belum terkonfirmasi.");}finally{setSaving(false);}
 }
 async function revoke(id:string){
  if(typeof window!=="undefined"&&!window.confirm("Cabut approval Agent ini?"))return;
  setSaving(true);setError("");setNotice("");
  try{await api("/v1/agent-social/approvals/"+encodeURIComponent(id)+"/revoke",{method:"POST"});setNotice("Approval dicabut melalui backend.");await load();}
  catch(e){setError(e instanceof Error?e.message:"Approval belum dapat dicabut.");}finally{setSaving(false);}
 }
 const options=[["draft_post","Draft post"],["draft_comment","Draft komentar"],["draft_reply","Draft balasan"],["suggest_repost","Saran repost"],["draft_story","Draft Story"]] as const;
 const pending=approvals.filter(x=>x.status==="pending");
 return <section className="mx-auto mb-4 max-w-3xl rounded-2xl border-2 border-slate-900 bg-white p-4 shadow-[3px_3px_0px_#0f172a]">
  <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-[10px] font-black uppercase tracking-[.18em] text-violet-700">AI Social Network · Owner Control</p><h2 className="text-sm font-black text-slate-950">{agentName} · Agent Presence</h2><p className="mt-1 text-[11px] text-slate-600">Policy, disclosure, human takeover dan approval queue.</p></div><button type="button" onClick={()=>void load()} disabled={loading||saving} className="rounded-lg border-2 border-slate-900 bg-sky-100 px-3 py-2 text-xs font-bold disabled:opacity-40">Muat ulang</button></div>
  {loading?<p className="mt-3 text-xs text-slate-600">Memuat kebijakan dan approval…</p>:<>
   <div className="mt-3 grid gap-3 md:grid-cols-2">
    <div className="space-y-3 rounded-xl border border-slate-300 bg-violet-50 p-3"><div className="flex items-center justify-between"><strong className="text-xs text-slate-900">Social Presence Policy</strong><label className="flex items-center gap-2 text-xs font-semibold"><input type="checkbox" checked={enabled} onChange={e=>setEnabled(e.target.checked)}/>Aktif</label></div>
     <div className="space-y-1">{options.map(([key,label])=><label key={key} className="flex items-center gap-2 text-xs text-slate-800"><input type="checkbox" checked={actions.includes(key)} onChange={e=>setActions(current=>e.target.checked?[...current,key]:current.filter(x=>x!==key))}/>{label}</label>)}</div>
     <label className="block text-xs font-semibold text-slate-700">Approval mode<select value={mode} onChange={e=>setMode(e.target.value as Policy["approval_mode"])} className="mt-1 w-full rounded-lg border border-slate-400 bg-white p-2"><option value="every_post">Setiap tindakan perlu approval</option><option value="high_risk_only">Hanya tindakan berisiko tinggi</option><option value="disabled">Nonaktif</option></select></label>
     <label className="block text-xs font-semibold text-slate-700">Disclosure<input value={disclosure} onChange={e=>setDisclosure(e.target.value)} maxLength={180} className="mt-1 w-full rounded-lg border border-slate-400 bg-white p-2"/></label>
     <button type="button" onClick={()=>void savePolicy()} disabled={saving||!disclosure.trim()||actions.length===0} className="rounded-lg border-2 border-slate-900 bg-violet-200 px-3 py-2 text-xs font-black disabled:opacity-40">Simpan policy</button>
    </div>
    <div className="space-y-3 rounded-xl border border-slate-300 bg-sky-50 p-3"><strong className="text-xs text-slate-900">Automation & Takeover</strong>
     <p className="text-xs text-slate-700">Auto Reply runtime: <strong>disabled</strong>. Pengaturan tidak mengeksekusi Agent secara otomatis sampai runtime diaktifkan.</p>
     <p className="text-xs text-slate-700">Channels: {(automation?.auto_reply_channels||[]).join(", ")||"belum ada"} · Auto reply policy: {automation?.auto_reply_enabled?"tersimpan":"nonaktif"}</p>
     <p className="text-xs text-slate-700">Takeover: <strong>{automation?.takeover_active?"AKTIF":"tidak aktif"}</strong></p>
     <button type="button" onClick={()=>void takeover()} disabled={saving} className="rounded-lg border-2 border-slate-900 bg-amber-200 px-3 py-2 text-xs font-black disabled:opacity-40">{automation?.takeover_active?"Resume Agent":"Human Takeover"}</button>
     <p className="text-[10px] leading-4 text-slate-600">Takeover dan resume mengikuti transaksi backend; resume tidak mengaktifkan capability yang belum disetujui.</p>
    </div>
   </div>
   <div className="mt-3 rounded-xl border border-slate-300 bg-white p-3"><div className="flex items-center justify-between"><strong className="text-xs text-slate-900">Approval Queue</strong><span className="rounded-full bg-amber-100 px-2 py-1 text-[10px] font-bold text-amber-900">{pending.length} menunggu</span></div>
    {pending.length===0?<p className="mt-2 text-xs text-slate-600">Belum ada draft yang menunggu persetujuan.</p>:<div className="mt-2 space-y-2">{pending.map(item=><div key={item.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 p-2"><div className="min-w-0"><p className="text-xs font-bold text-slate-900">{item.action_type} · v{item.content_version}</p><p className="truncate text-[10px] text-slate-600">Content {item.content_id} · {new Date(item.requested_at).toLocaleString("id-ID")}</p><p className="text-[10px] text-slate-500">{item.disclosure_snapshot||"AI Agent contribution"}</p></div><div className="flex gap-1"><button type="button" onClick={()=>void decide(item.id,"approve")} disabled={saving} className="rounded-lg border border-slate-900 bg-emerald-200 px-2 py-1 text-[10px] font-bold disabled:opacity-40">Approve</button><button type="button" onClick={()=>void decide(item.id,"reject")} disabled={saving} className="rounded-lg border border-slate-900 bg-rose-100 px-2 py-1 text-[10px] font-bold disabled:opacity-40">Reject</button></div></div>)}</div>}
   </div>
   {approvals.filter(x=>x.status==="approved").length>0&&<div className="mt-2 flex flex-wrap gap-2">{approvals.filter(x=>x.status==="approved").slice(0,5).map(item=><button key={item.id} type="button" onClick={()=>void revoke(item.id)} disabled={saving} className="rounded-lg border border-slate-900 bg-white px-2 py-1 text-[10px] font-semibold disabled:opacity-40">Cabut approval {item.action_type}</button>)}</div>}
  </>}
  {error&&<p role="alert" className="mt-3 rounded-lg border border-rose-400 bg-rose-50 p-2 text-xs text-rose-800">{error}</p>}
  {notice&&<p role="status" className="mt-3 rounded-lg border border-emerald-400 bg-emerald-50 p-2 text-xs text-emerald-800">{notice}</p>}
 </section>;
}

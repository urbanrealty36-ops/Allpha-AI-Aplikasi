"use client";
import { FormEvent, useCallback, useState } from "react";
import Link from "next/link";

type Session={access_token:string;refresh_token:string;expires_at:number;user:{id:string;email?:string}};
type Operator={id:string;email?:string;scopes:string[]};
type Row=Record<string,unknown>&{id:string};
const apiBase=(process.env.NEXT_PUBLIC_API_BASE_URL||(process.env.NODE_ENV==="production"?"https://api.allpha.web.id":"http://localhost:8000")).replace(/\/$/,"");
const supabaseUrl=(process.env.NEXT_PUBLIC_SUPABASE_URL||"").replace(/\/$/,"");
const publishableKey=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY||"";
async function authRequest(body:Record<string,string>,grant:"password"|"refresh_token"):Promise<Session>{
 if(!supabaseUrl||!publishableKey)throw new Error("Konfigurasi Supabase public belum tersedia.");
 const response=await fetch(supabaseUrl+"/auth/v1/token?grant_type="+grant,{method:"POST",headers:{apikey:publishableKey,"Content-Type":"application/json"},body:JSON.stringify(body),cache:"no-store"});
 const data=await response.json().catch(()=>({}));
 if(!response.ok||!data.access_token||!data.refresh_token||!data.user?.id)throw new Error(data.error_description||data.msg||"Autentikasi gagal.");
 return {access_token:data.access_token,refresh_token:data.refresh_token,expires_at:Date.now()+Math.max(60,data.expires_in||3600)*1000,user:data.user};
}
async function apiFetch(path:string,session:Session,init:RequestInit={}){
 let active=session;if(active.expires_at<=Date.now()+30000)active=await authRequest({refresh_token:active.refresh_token},"refresh_token");
 const send=(token:string)=>fetch(apiBase+path,{...init,cache:"no-store",headers:{Accept:"application/json",...(init.body?{"Content-Type":"application/json"}:{}),...(init.headers||{}),Authorization:"Bearer "+token}});
 let response=await send(active.access_token);if(response.status===401){active=await authRequest({refresh_token:active.refresh_token},"refresh_token");response=await send(active.access_token);}return response;
}
async function read<T>(response:Response):Promise<T>{const data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.error?.message||data.detail?.message||"Permintaan gagal.");return data as T;}

export default function ContentLifecyclePage(){
 const [session,setSession]=useState<Session|null>(null);const [operator,setOperator]=useState<Operator|null>(null);
 const [email,setEmail]=useState("");const [password,setPassword]=useState("");
 const [events,setEvents]=useState<Row[]>([]);const [holds,setHolds]=useState<Row[]>([]);const [receipts,setReceipts]=useState<Row[]>([]);
 const [preview,setPreview]=useState<{content_candidates:Row[];abandoned_upload_candidates:Row[]}|null>(null);
 const [contentId,setContentId]=useState("");const [holdType,setHoldType]=useState("legal");const [reason,setReason]=useState("");
 const [busy,setBusy]=useState(false);const [error,setError]=useState("");const [notice,setNotice]=useState("");
 const call=useCallback(async<T,>(path:string,init:RequestInit={})=>read<T>(await apiFetch(path,session!,init)),[session]);
 const refresh=useCallback(async(active:Session)=>{
  const [e,h,r,p]=await Promise.all([
   read<{items:Row[]}>(await apiFetch("/v1/content/admin/lifecycle/events?limit=100",active)),
   read<{items:Row[]}>(await apiFetch("/v1/content/admin/retention/holds?active_only=false&limit=100",active)),
   read<{items:Row[]}>(await apiFetch("/v1/content/admin/retention/receipts?limit=100",active)),
   read<{content_candidates:Row[];abandoned_upload_candidates:Row[]}>(await apiFetch("/v1/content/admin/retention/preview",active))
  ]);
  setEvents(e.items||[]);setHolds(h.items||[]);setReceipts(r.items||[]);setPreview(p);
 },[]);
 async function login(e:FormEvent){e.preventDefault();setBusy(true);setError("");try{const active=await authRequest({email:email.trim(),password},"password");const a=await read<{operator:Operator}>(await apiFetch("/v1/admin/operator/access",active));if(!a.operator.scopes.includes("platform:content.moderate"))throw new Error("Scope platform:content.moderate diperlukan.");setSession(active);setOperator(a.operator);setPassword("");await refresh(active);}catch(x){setError(x instanceof Error?x.message:"Login gagal.");setSession(null);setOperator(null);}finally{setBusy(false);}}
 async function createHold(){if(!session||contentId.trim().length<30||reason.trim().length<8){setError("ID konten dan alasan hold minimal 8 karakter wajib diisi.");return;}setBusy(true);setError("");setNotice("");try{await call("/v1/content/admin/retention/holds",{method:"POST",body:JSON.stringify({content_id:contentId.trim(),hold_type:holdType,reason:reason.trim()})});setNotice("Legal/safety hold berhasil dicatat.");setContentId("");setReason("");await refresh(session);}catch(x){setError(x instanceof Error?x.message:"Pembuatan hold gagal.");}finally{setBusy(false);}}
 async function releaseHold(id:string){if(!session)return;const why=window.prompt("Alasan pelepasan hold (min. 8 karakter)");if(!why||why.trim().length<8)return;setBusy(true);setError("");try{await call("/v1/content/admin/retention/holds/"+id+"/release",{method:"POST",body:JSON.stringify({reason:why.trim()})});setNotice("Hold dilepas.");await refresh(session);}catch(x){setError(x instanceof Error?x.message:"Pelepasan hold gagal.");}finally{setBusy(false);}}
 async function enqueue(){if(!session||!window.confirm("Buat job penghapusan untuk konten yang sudah melewati 30 hari dan upload terbengkalai 7 hari? Worker akan memeriksa legal hold sebelum menghapus."))return;setBusy(true);setError("");try{const result=await call<{enqueued:number}>("/v1/content/admin/retention/enqueue",{method:"POST",body:JSON.stringify({confirm:true})});setNotice("Job retention dibuat: "+result.enqueued);await refresh(session);}catch(x){setError(x instanceof Error?x.message:"Enqueue retention gagal.");}finally{setBusy(false);}}
 return <main className="mx-auto min-h-screen max-w-6xl px-5 py-8 text-slate-900 dark:text-slate-100">
  <nav className="mb-6 flex justify-between"><Link href="/content-moderation" className="text-sm text-blue-600">← Moderasi konten</Link><span className="text-xs text-slate-500">WP-04 · Lifecycle governance</span></nav>
  <header className="mb-6"><p className="text-xs font-semibold uppercase tracking-widest text-cyan-700">Trust, Safety & Data Lifecycle</p><h1 className="mt-2 text-3xl font-semibold">Content Lifecycle Control</h1><p className="mt-2 text-sm text-slate-600 dark:text-slate-300">Audit lifecycle, legal hold, dry-run retention, recovery receipts dan operator actions.</p></header>
  {error&&<p role="alert" className="mb-4 rounded-xl border border-red-300 p-3 text-sm text-red-700">{error}</p>}{notice&&<p role="status" className="mb-4 rounded-xl border border-emerald-300 p-3 text-sm text-emerald-700">{notice}</p>}
  {!session||!operator?<form onSubmit={login} className="max-w-md space-y-4 rounded-2xl border p-5"><h2 className="font-semibold">Login operator</h2><input type="email" required value={email} onChange={e=>setEmail(e.target.value)} placeholder="Email" className="w-full rounded-xl border bg-transparent p-3"/><input type="password" required value={password} onChange={e=>setPassword(e.target.value)} placeholder="Password" className="w-full rounded-xl border bg-transparent p-3"/><button disabled={busy} className="rounded-xl bg-slate-900 px-4 py-2 text-white">{busy?"Memverifikasi…":"Masuk"}</button></form>:<>
   <div className="mb-5 flex flex-wrap items-center justify-between gap-3"><p className="text-xs text-slate-500">Operator: {operator.email||operator.id}</p><div className="flex gap-2"><button disabled={busy} onClick={()=>void refresh(session)} className="rounded-xl border px-3 py-2 text-sm">Refresh</button><button disabled={busy} onClick={()=>void enqueue()} className="rounded-xl bg-red-700 px-3 py-2 text-sm text-white">Enqueue retention jobs</button></div></div>
   <section className="mb-6 rounded-2xl border p-5"><h2 className="text-lg font-semibold">Retention dry-run preview</h2><p className="mt-1 text-sm text-slate-500">Preview tidak menghapus data. Executor akan memeriksa legal hold lagi sebelum purge.</p><div className="mt-3 grid gap-4 md:grid-cols-2"><div><strong>Soft-deleted ≥30 hari ({preview?.content_candidates.length||0})</strong>{preview?.content_candidates.map(x=><p key={x.id} className="mt-2 break-all text-xs">{String(x.id)} · {String(x.deleted_at)}</p>)}</div><div><strong>Upload abandoned ≥7 hari ({preview?.abandoned_upload_candidates.length||0})</strong>{preview?.abandoned_upload_candidates.map(x=><p key={x.id} className="mt-2 break-all text-xs">{String(x.id)} · {String(x.status)}</p>)}</div></div></section>
   <section className="mb-6 rounded-2xl border p-5"><h2 className="text-lg font-semibold">Create legal / safety hold</h2><div className="mt-3 grid gap-3 md:grid-cols-3"><input value={contentId} onChange={e=>setContentId(e.target.value)} placeholder="Content UUID" className="rounded-xl border bg-transparent p-3"/><select value={holdType} onChange={e=>setHoldType(e.target.value)} className="rounded-xl border bg-transparent p-3"><option value="legal">Legal</option><option value="safety">Safety</option><option value="regulatory">Regulatory</option></select><input value={reason} onChange={e=>setReason(e.target.value)} placeholder="Alasan hold (min. 8 karakter)" className="rounded-xl border bg-transparent p-3"/></div><button disabled={busy} onClick={()=>void createHold()} className="mt-3 rounded-xl bg-slate-900 px-4 py-2 text-white">Buat hold</button><div className="mt-4 space-y-2">{holds.map(h=><div key={h.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border p-3"><div className="min-w-0"><p className="break-all text-sm font-medium">{String(h.hold_type)} · {String(h.content_id)}</p><p className="text-xs text-slate-500">{String(h.reason)} · {h.released_at?"Released":"ACTIVE"}</p></div>{!h.released_at&&<button disabled={busy} onClick={()=>void releaseHold(h.id)} className="rounded-lg border px-3 py-2 text-xs">Release hold</button>}</div>)}</div></section>
   <section className="mb-6 rounded-2xl border p-5"><h2 className="text-lg font-semibold">Deletion receipts</h2><p className="mt-1 text-sm text-slate-500">Backup policy: immutable backup expiry; no claim of immediate backup erasure.</p><div className="mt-3 space-y-2">{receipts.map(x=><div key={x.id} className="rounded-xl border p-3 text-xs"><p className="break-all">Job {String(x.job_id)} · {String(x.completed_at)}</p><p>{Array.isArray(x.deleted_objects)?x.deleted_objects.length:0} objects · {Array.isArray(x.deleted_rows)?x.deleted_rows.length:0} rows</p></div>)}</div></section>
   <section className="rounded-2xl border p-5"><h2 className="text-lg font-semibold">Lifecycle audit events</h2><div className="mt-3 max-h-[520px] space-y-2 overflow-auto">{events.map(x=><div key={x.id} className="rounded-xl border p-3 text-xs"><p className="font-semibold">{String(x.event_type)} · {String(x.created_at)}</p><p className="mt-1 break-all text-slate-500">Content {String(x.content_id||"—")} · Media {String(x.media_id||"—")} · Owner {String(x.owner_id||"—")}</p><pre className="mt-2 whitespace-pre-wrap break-all">{JSON.stringify(x.payload,null,2)}</pre></div>)}</div></section>
  </>}
 </main>;
}

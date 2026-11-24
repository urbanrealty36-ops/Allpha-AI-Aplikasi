"use client";

import { FormEvent, useCallback, useState } from "react";
import Link from "next/link";

type Session={access_token:string;refresh_token:string;expires_at:number;user:{id:string;email?:string}};
type Operator={id:string;email?:string;scopes:string[]};
type Cost={id:string;provider_id:string;model_id:string;model_version:string;pricing_version:string;policy_version:string;cost_unit:string;input_micro_cost_per_token:number;output_micro_cost_per_token:number;max_cost_microunits:number;max_prompt_bytes:number;max_output_tokens:number;max_latency_ms:number;status:string;policy_approved:boolean;policy_approval_reference?:string|null;effective_at?:string|null};
type ModerationPolicy={policy_version:string;approval_reference:string;configuration:Record<string,unknown>;status:string;effective_at:string;expires_at?:string|null;approved_by?:string|null};
type RuntimeStatus={configured:boolean;ready:boolean;reason?:string;missing_configuration?:string[];route?:Record<string,unknown>};
type UsageSummary={since:string;until:string;totals:{runs:number};by_provider_model:Array<{provider_id:string;model_id:string;usage_unit:string;runs:number;usage_units:number;cost_microunits:number;cost_unit:string;pricing_version:string}>};
type AuthPayload={access_token?:string;refresh_token?:string;expires_in?:number;user?:{id:string;email?:string};error_description?:string;msg?:string};
const apiBase=(process.env.NEXT_PUBLIC_API_BASE_URL||(process.env.NODE_ENV==="production"?"https://api.allpha.web.id":"http://localhost:8000")).replace(/\/$/,"");
const supabaseUrl=(process.env.NEXT_PUBLIC_SUPABASE_URL||"").replace(/\/$/,"");
const publishableKey=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY||"";

async function authRequest(body:Record<string,string>,grant:"password"|"refresh_token"):Promise<Session>{
 if(!supabaseUrl||!publishableKey)throw new Error("Konfigurasi Supabase public belum tersedia.");
 const response=await fetch(supabaseUrl+"/auth/v1/token?grant_type="+grant,{method:"POST",headers:{apikey:publishableKey,"Content-Type":"application/json"},body:JSON.stringify(body),cache:"no-store"});
 const data=await response.json().catch(()=>({})) as AuthPayload;
 if(!response.ok||!data.access_token||!data.refresh_token||!data.user?.id)throw new Error(data.error_description||data.msg||"Autentikasi gagal.");
 return {access_token:data.access_token,refresh_token:data.refresh_token,expires_at:Date.now()+Math.max(60,data.expires_in||3600)*1000,user:data.user};
}
async function apiFetch(path:string,session:Session,init:RequestInit={}){
 let active=session;
 if(active.expires_at<=Date.now()+30000)active=await authRequest({refresh_token:active.refresh_token},"refresh_token");
 const send=(token:string)=>fetch(apiBase+path,{...init,cache:"no-store",headers:{Accept:"application/json",...(init.body?{"Content-Type":"application/json"}:{}),...(init.headers||{}),Authorization:"Bearer "+token}});
 let response=await send(active.access_token);
 if(response.status===401){active=await authRequest({refresh_token:active.refresh_token},"refresh_token");response=await send(active.access_token);}
 return response;
}
async function read<T>(response:Response):Promise<T>{
 const data=await response.json().catch(()=>({})) as {detail?:{message?:string};error?:{message?:string}};
 if(!response.ok)throw new Error(data.detail?.message||data.error?.message||"Permintaan gagal (HTTP "+response.status+").");
 return data as T;
}

const field="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100";
const button="rounded-xl border px-3 py-2 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-40";
const primary="rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40";

export default function ModelGovernancePage(){
 const [session,setSession]=useState<Session|null>(null);
 const [operator,setOperator]=useState<Operator|null>(null);
 const [email,setEmail]=useState("");
 const [password,setPassword]=useState("");
 const [costs,setCosts]=useState<Cost[]>([]);
 const [moderation,setModeration]=useState<ModerationPolicy[]>([]);
 const [runtime,setRuntime]=useState<RuntimeStatus|null>(null);
 const [usage,setUsage]=useState<UsageSummary|null>(null);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [notice,setNotice]=useState("");
 const [reason,setReason]=useState("");
 const [approvalReference,setApprovalReference]=useState("");
 const [costForm,setCostForm]=useState({
  provider_id:"",model_id:"",model_version:"",pricing_version:"",policy_version:"1",cost_unit:"",
  input_micro_cost_per_token:"",output_micro_cost_per_token:"",max_cost_microunits:"",
  max_prompt_bytes:"16384",max_output_tokens:"1024",max_latency_ms:"30000"
 });
 const [moderationVersion,setModerationVersion]=useState("");
 const [moderationReference,setModerationReference]=useState("");

 const load=useCallback(async(active:Session)=>{
  const access=await read<{operator:Operator}>(await apiFetch("/v1/admin/operator/access",active));
  if(!access.operator.scopes.includes("platform:operations.read"))throw new Error("Scope platform:operations.read diperlukan.");
  setOperator(access.operator);
  const [costResult,moderationResult,runtimeResult,usageResult]=await Promise.all([
   read<{items:Cost[]}>(await apiFetch("/v1/admin/model-costs?limit=100",active)),
   read<{items:ModerationPolicy[]}>(await apiFetch("/v1/admin/model-costs/moderation-policies",active)),
   read<RuntimeStatus>(await apiFetch("/v1/admin/model-costs/runtime-status",active)),
   read<UsageSummary>(await apiFetch("/v1/admin/model-costs/usage-summary",active))
  ]);
  setCosts(costResult.items||[]);
  setModeration(moderationResult.items||[]);
  setRuntime(runtimeResult);
  setUsage(usageResult);
 },[]);

 async function login(event:FormEvent){
  event.preventDefault();setBusy(true);setError("");setNotice("");
  try{const active=await authRequest({email:email.trim(),password},"password");await load(active);setSession(active);setPassword("");}
  catch(cause){setSession(null);setOperator(null);setError(cause instanceof Error?cause.message:"Login operator gagal.");}
  finally{setBusy(false);}
 }
 async function refresh(){
  if(!session)return;setBusy(true);setError("");
  try{await load(session);}catch(cause){setError(cause instanceof Error?cause.message:"Model governance gagal dimuat.");}
  finally{setBusy(false);}
 }
 async function action(path:string,method:string,body?:Record<string,unknown>,success?:string){
  if(!session)return;setBusy(true);setError("");setNotice("");
  try{
   await read(await apiFetch(path,session,{method,...(body?{body:JSON.stringify(body)}:{})}));
   setNotice(success||"Perubahan tersimpan.");await load(session);
  }catch(cause){setError(cause instanceof Error?cause.message:"Aksi governance gagal.");}
  finally{setBusy(false);}
 }
 async function createCost(event:FormEvent){
  event.preventDefault();
  const numeric=["input_micro_cost_per_token","output_micro_cost_per_token","max_cost_microunits","max_prompt_bytes","max_output_tokens","max_latency_ms"] as const;
  const payload:Record<string,unknown>={...costForm};
  for(const key of numeric){const value=Number(costForm[key]);if(!Number.isSafeInteger(value)){setError("Semua batas biaya dan limit harus berupa bilangan bulat.");return;}payload[key]=value;}
  await action("/v1/admin/model-costs","POST",payload,"Draft tarif dibuat. Tarif belum aktif dan belum menyetujui eksekusi model.");
 }
 async function createModeration(event:FormEvent){
  event.preventDefault();
  await action("/v1/admin/model-costs/moderation-policies","POST",{policy_version:moderationVersion.trim(),approval_reference:moderationReference.trim()},
   "Draft moderation dibuat dalam mode manual-review-only.");
  setModerationVersion("");setModerationReference("");
 }
 const canReview=operator?.scopes.includes("platform:capabilities.review")||false;
 const canHighRisk=operator?.scopes.includes("platform:capabilities.review.high_risk")||false;
 return <main className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6">
  <header className="flex flex-wrap items-center justify-between gap-3">
   <div><p className="text-xs font-semibold uppercase tracking-widest text-indigo-600">Allpha Super Admin</p><h1 className="text-2xl font-bold">AI Model Governance</h1><p className="mt-1 text-sm text-slate-500">Provider readiness, pricing, execution policy, output moderation and usage.</p></div>
   <nav className="flex flex-wrap gap-3 text-sm"><Link className="underline" href="/agent-capabilities">Agent Capabilities</Link><Link className="underline" href="/billing-governance">Billing Governance</Link><Link className="underline" href="/agent-social-audit">Identity Audit</Link></nav>
  </header>
  {!session?<form onSubmit={login} className="mx-auto grid max-w-md gap-3 rounded-2xl border p-5"><h2 className="font-semibold">Operator Login</h2><label className="grid gap-1 text-sm">Email<input className={field} type="email" autoComplete="username" value={email} onChange={e=>setEmail(e.target.value)} required/></label><label className="grid gap-1 text-sm">Password<input className={field} type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} required/></label><button disabled={busy} className={primary}>{busy?"Memproses…":"Login Operator"}</button></form>:<>
   <section className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border p-4"><div><p className="text-sm font-semibold">{operator?.email||operator?.id}</p><p className="text-xs text-slate-500">Scopes: {operator?.scopes.join(", ")}</p></div><button disabled={busy} className={button} onClick={()=>void refresh()}>Refresh governance</button></section>
   {error&&<p role="alert" className="rounded-xl border border-rose-300 bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
   {notice&&<p role="status" className="rounded-xl border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</p>}
   <section className="rounded-2xl border p-4">
    <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-lg font-semibold">Model Router runtime status</h2><span className={"rounded-full px-2.5 py-1 text-xs font-semibold "+(runtime?.ready?"bg-emerald-100 text-emerald-800":"bg-amber-100 text-amber-800")}>{runtime?.ready?"READY":"FAIL-CLOSED"}</span></div>
    <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{runtime?.ready?"Provider, tariff and execution policy preflight succeeded.":"Model execution is unavailable until all server-side provider, policy and pricing requirements are configured."}</p>
    {runtime?.route&&<pre className="mt-3 overflow-auto rounded-xl bg-slate-100 p-3 text-xs dark:bg-slate-900">{JSON.stringify(runtime.route,null,2)}</pre>}
    {!!runtime?.missing_configuration?.length&&<div className="mt-3"><p className="text-xs font-semibold">Missing server configuration</p><div className="mt-2 flex flex-wrap gap-1.5">{runtime.missing_configuration.map(key=><span key={key} className="rounded-lg bg-amber-50 px-2 py-1 text-xs text-amber-900">{key}</span>)}</div></div>}
    <p className="mt-3 text-xs text-slate-500">Provider API keys must be configured as Railway secrets. This page never accepts or displays provider secrets.</p>
   </section>
   <section className="space-y-3 rounded-2xl border p-4">
    <div className="flex flex-wrap items-center justify-between"><h2 className="text-lg font-semibold">Provider/model tariff and execution policy</h2><span className="text-xs text-slate-500">{costs.length} configurations</span></div>
    <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-left text-sm"><thead><tr className="border-b text-xs text-slate-500"><th className="p-2">Provider / Model</th><th className="p-2">Tariff</th><th className="p-2">Limits</th><th className="p-2">Status</th><th className="p-2">Governance</th><th className="p-2">Actions</th></tr></thead><tbody>
     {costs.map(item=><tr key={item.id} className="border-b align-top"><td className="p-2"><strong>{item.provider_id}</strong><p className="text-xs text-slate-500">{item.model_id} · {item.model_version}</p><p className="text-xs text-slate-500">{item.id}</p></td><td className="p-2 text-xs">{item.pricing_version}<p>{item.input_micro_cost_per_token} / {item.output_micro_cost_per_token} micro/token</p><p>{item.cost_unit}</p></td><td className="p-2 text-xs">Max cost {item.max_cost_microunits}<p>{item.max_prompt_bytes} bytes · {item.max_output_tokens} tokens</p><p>{item.max_latency_ms} ms</p></td><td className="p-2"><span className="rounded-full border px-2 py-1 text-xs">{item.status}</span></td><td className="p-2 text-xs"><strong>{item.policy_approved?"Policy approved":"Policy not approved"}</strong><p>Policy {item.policy_version}</p><p>{item.policy_approval_reference||"No approval reference"}</p></td><td className="p-2"><div className="flex flex-wrap gap-1.5">
      {item.status==="draft"&&<button disabled={busy||!canHighRisk} className={button} onClick={()=>void action("/v1/admin/model-costs/"+item.id+"/activate","POST",{reason:"Tariff activation from Model Governance."},"Tariff activated; model policy remains unapproved.")}>Activate tariff</button>}
      {item.status==="active"&&!item.policy_approved&&<button disabled={busy||!canHighRisk||reason.trim().length<8||approvalReference.trim().length<8} className={button} onClick={()=>void action("/v1/admin/model-costs/"+item.id+"/approve-policy","POST",{reason,approval_reference:approvalReference},"Model execution policy approved; provider runtime still needs secrets.")}>Approve policy</button>}
      {item.status==="active"&&item.policy_approved&&<button disabled={busy||!canHighRisk||reason.trim().length<8} className={button} onClick={()=>void action("/v1/admin/model-costs/"+item.id+"/revoke-policy","POST",{reason},"Model execution policy revoked.")}>Revoke policy</button>}
      {item.status!=="archived"&&<button disabled={busy||!canHighRisk||reason.trim().length<8} className={button} onClick={()=>void action("/v1/admin/model-costs/"+item.id+"/archive","POST",{reason},"Tariff archived and model policy approval revoked.")}>Archive</button>}
     </div></td></tr>)}
     {costs.length===0&&<tr><td colSpan={6} className="p-6 text-center text-sm text-slate-500">Belum ada konfigurasi tarif. Tambahkan draft berdasarkan kontrak provider dan pricing yang benar-benar berlaku.</td></tr>}
    </tbody></table></div>
    <div className="grid gap-3 rounded-xl bg-slate-50 p-3 dark:bg-slate-900 sm:grid-cols-2"><label className="grid gap-1 text-xs">Alasan governance<input className={field} value={reason} onChange={e=>setReason(e.target.value)} minLength={8} placeholder="Alasan perubahan / approval"/></label><label className="grid gap-1 text-xs">Approval reference<input className={field} value={approvalReference} onChange={e=>setApprovalReference(e.target.value)} minLength={8} placeholder="Dokumen/kontrak/ticket reference"/></label></div>
    {canReview&&<form onSubmit={createCost} className="grid gap-3 rounded-xl border p-3 sm:grid-cols-3">
     <h3 className="sm:col-span-3 font-semibold">Create tariff draft</h3>
     {(["provider_id","model_id","model_version","pricing_version","policy_version","cost_unit","input_micro_cost_per_token","output_micro_cost_per_token","max_cost_microunits","max_prompt_bytes","max_output_tokens","max_latency_ms"] as const).map(key=><label key={key} className="grid gap-1 text-xs">{key.replaceAll("_"," ")}<input className={field} type={key.includes("cost")||key.includes("bytes")||key.includes("tokens")||key.includes("latency")?"number":"text"} min={key.includes("cost")||key.includes("bytes")||key.includes("tokens")||key.includes("latency")?0:undefined} value={costForm[key]} onChange={e=>setCostForm(current=>({...current,[key]:e.target.value}))} required/></label>)}
     <button disabled={busy} className={primary+" sm:col-span-3"}>Create draft tariff</button>
    </form>}
   </section>
   <section className="space-y-3 rounded-2xl border p-4">
    <div className="flex flex-wrap items-center justify-between"><h2 className="text-lg font-semibold">Generation output moderation</h2><span className="text-xs text-slate-500">{moderation.length} policies</span></div>
    <p className="text-sm text-slate-600 dark:text-slate-300">Only the built-in manual-review-only policy is configurable here. It never auto-approves generated content.</p>
    {moderation.map(item=><div key={item.policy_version} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border p-3"><div><strong>{item.policy_version}</strong><p className="text-xs text-slate-500">{item.status} · {item.approval_reference}</p><p className="text-xs text-slate-500">mode: {String(item.configuration.mode||"unknown")}</p></div><div className="flex flex-wrap gap-2">{item.status==="draft"&&<button disabled={busy||!canHighRisk||reason.trim().length<8||approvalReference.trim().length<3} className={button} onClick={()=>void action("/v1/admin/model-costs/moderation-policies/"+encodeURIComponent(item.policy_version)+"/approve","POST",{reason,approval_reference:approvalReference},"Manual-review-only moderation policy approved.")}>Approve manual review</button>}{item.status!=="retired"&&<button disabled={busy||!canHighRisk||reason.trim().length<8} className={button} onClick={()=>void action("/v1/admin/model-costs/moderation-policies/"+encodeURIComponent(item.policy_version)+"/retire","POST",{reason},"Moderation policy retired.")}>Retire</button>}</div></div>)}
    {moderation.length===0&&<p className="rounded-xl border border-dashed p-5 text-center text-sm text-slate-500">Belum ada output moderation policy. Generation tetap fail-closed sampai policy disetujui.</p>}
    {canReview&&<form onSubmit={createModeration} className="grid gap-3 rounded-xl border p-3 sm:grid-cols-3"><h3 className="sm:col-span-3 font-semibold">Create manual-review-only policy draft</h3><label className="grid gap-1 text-xs">Policy version<input className={field} value={moderationVersion} onChange={e=>setModerationVersion(e.target.value)} required/></label><label className="grid gap-1 text-xs">Tracking reference<input className={field} value={moderationReference} onChange={e=>setModerationReference(e.target.value)} required/></label><div className="flex items-end"><button disabled={busy} className={primary}>Create moderation draft</button></div></form>}
   </section>
   <section className="space-y-3 rounded-2xl border p-4"><div className="flex flex-wrap items-center justify-between"><h2 className="text-lg font-semibold">Usage metering</h2><span className="text-xs text-slate-500">{usage?.totals.runs??0} recorded runs (last 30 days)</span></div>
    {usage?.by_provider_model?.length?<div className="overflow-x-auto"><table className="w-full min-w-[600px] text-sm"><thead><tr className="border-b text-xs text-slate-500"><th className="p-2">Provider / Model</th><th className="p-2">Runs</th><th className="p-2">Usage</th><th className="p-2">Cost</th><th className="p-2">Pricing</th></tr></thead><tbody>{usage.by_provider_model.map((item,i)=><tr key={i} className="border-b"><td className="p-2">{item.provider_id}<p className="text-xs text-slate-500">{item.model_id}</p></td><td className="p-2">{item.runs}</td><td className="p-2">{item.usage_units} {item.usage_unit}</td><td className="p-2">{item.cost_microunits} {item.cost_unit}</td><td className="p-2">{item.pricing_version}</td></tr>)}</tbody></table></div>:<p className="rounded-xl border border-dashed p-5 text-center text-sm text-slate-500">Belum ada usage record. Tidak ada biaya sintetis yang ditampilkan.</p>}
   </section>
  </>}
 </main>;
}

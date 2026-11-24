"use client";

import { FormEvent, useCallback, useState } from "react";
import Link from "next/link";

type Session = { access_token:string; refresh_token:string; expires_at:number; user:{id:string;email?:string} };
type Operator = { id:string; email?:string; scopes:string[] };
type Capability = { id:string; agent_id:string; created_by:string; capability_key:string; description:string; required_permission_scopes:string[]; risk_level:string; status:string; created_at:string };
type RuntimePolicy = { id:string; agent_id:string; policy_version:number; policy_digest:string; approved_tool_keys:string[]; required_permission_scopes:string[]; risk_constraints?:Record<string,unknown>; status:string; created_at?:string; approved_at?:string };
type AuthPayload = { access_token?:string; refresh_token?:string; expires_in?:number; user?:{id:string;email?:string}; error_description?:string; msg?:string };
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

export default function AgentCapabilitiesGovernancePage(){
  const [session,setSession]=useState<Session|null>(null);
  const [operator,setOperator]=useState<Operator|null>(null);
  const [email,setEmail]=useState("");
  const [password,setPassword]=useState("");
  const [requests,setRequests]=useState<Capability[]>([]);
  const [policies,setPolicies]=useState<Record<string,RuntimePolicy[]>>({});
  const [selectedPolicy,setSelectedPolicy]=useState<Record<string,string>>({});
  const [reasons,setReasons]=useState<Record<string,string>>({});
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const [policyAgentId,setPolicyAgentId]=useState("");
  const [policyVersion,setPolicyVersion]=useState("1");
  const [policyTools,setPolicyTools]=useState("");
  const [policyScopes,setPolicyScopes]=useState("");
  const [policyConstraints,setPolicyConstraints]=useState("{}");
  const [policyReason,setPolicyReason]=useState("");
  const [policyDrafts,setPolicyDrafts]=useState<RuntimePolicy[]>([]);
  const [policyApproved,setPolicyApproved]=useState<RuntimePolicy[]>([]);
  const [policyRevoked,setPolicyRevoked]=useState<RuntimePolicy[]>([]);

  const load=useCallback(async(active:Session)=>{
    const access=await read<{operator:Operator}>(await apiFetch("/v1/admin/operator/access",active));
    if(!access.operator.scopes.includes("platform:capabilities.review"))throw new Error("Scope platform:capabilities.review diperlukan.");
    setOperator(access.operator);
    const body=await read<{items:Capability[]}>(await apiFetch("/v1/admin/operator/capabilities?limit=100",active));
    const items=body.items||[];setRequests(items);
    const agentIds=[...new Set(items.map(item=>item.agent_id))];
    const policyPairs=await Promise.all(agentIds.map(async id=>{
      const result=await read<{items:RuntimePolicy[]}>(await apiFetch("/v1/admin/operator/runtime-policies?agent_id="+encodeURIComponent(id),active));
      return [id,result.items||[]] as const;
    }));
    const map=Object.fromEntries(policyPairs);
    setPolicies(map);
    setSelectedPolicy(current=>{
      const next={...current};
      for(const item of items){
        const available=map[item.agent_id]||[];
        if(!next[item.id]&&available.length)next[item.id]=String(available[0].policy_version);
      }
      return next;
    });
  },[]);

  async function login(event:FormEvent){
    event.preventDefault();setBusy(true);setError("");setNotice("");
    try{const active=await authRequest({email:email.trim(),password},"password");await load(active);setSession(active);setPassword("");}
    catch(cause){setSession(null);setOperator(null);setError(cause instanceof Error?cause.message:"Login operator gagal.");}
    finally{setBusy(false);}
  }

  async function refresh(){
    if(!session)return;setBusy(true);setError("");
    try{await load(session);}catch(cause){setError(cause instanceof Error?cause.message:"Capability requests gagal dimuat.");}
    finally{setBusy(false);}
  }

  async function loadPolicyInventory(agentId=policyAgentId){
    if(!session)return;
    const id=agentId.trim();
    if(!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(id)){
      setError("Agent ID harus UUID valid.");return;
    }
    setBusy(true);setError("");
    try{
      const [drafts,approved,revoked]=await Promise.all(["draft","approved","revoked"].map(async status=>
        read<{items:RuntimePolicy[]}>(await apiFetch("/v1/admin/operator/runtime-policies?agent_id="+encodeURIComponent(id)+"&status="+status,session))
      ));
      setPolicyDrafts(drafts.items||[]);setPolicyApproved(approved.items||[]);setPolicyRevoked(revoked.items||[]);
      setPolicyAgentId(id);
    }catch(cause){setError(cause instanceof Error?cause.message:"Runtime policy inventory gagal dimuat.");}
    finally{setBusy(false);}
  }

  async function createRuntimePolicy(event:FormEvent){
    event.preventDefault();if(!session)return;
    let constraints:Record<string,unknown>;
    try{const parsed=JSON.parse(policyConstraints);if(!parsed||Array.isArray(parsed)||typeof parsed!=="object")throw new Error();constraints=parsed;}
    catch{setError("Risk constraints harus JSON object yang valid.");return;}
    const tools=[...new Set(policyTools.split(",").map(value=>value.trim()).filter(Boolean))];
    const scopes=[...new Set(policyScopes.split(",").map(value=>value.trim()).filter(Boolean))];
    if(!policyAgentId.trim()||!Number.isInteger(Number(policyVersion))||Number(policyVersion)<1||!tools.length){
      setError("Agent UUID, policy version dan minimal satu tool key wajib diisi.");return;
    }
    setBusy(true);setError("");setNotice("");
    try{
      await read(await apiFetch("/v1/admin/operator/runtime-policies",session,{method:"POST",body:JSON.stringify({
        agent_id:policyAgentId.trim(),policy_version:Number(policyVersion),approved_tool_keys:tools,
        required_permission_scopes:scopes,risk_constraints:constraints,
      })}));
      setNotice("Runtime policy draft tersimpan. Belum aktif sampai operator dengan high-risk review scope menyetujuinya.");
      await loadPolicyInventory(policyAgentId);
    }catch(cause){setError(cause instanceof Error?cause.message:"Runtime policy draft gagal dibuat.");}
    finally{setBusy(false);}
  }

  async function reviewRuntimePolicy(policy:RuntimePolicy,decision:"approve"|"revoke"){
    if(!session)return;
    if(!operator?.scopes.includes("platform:capabilities.review.high_risk")){
      setError("Perubahan lifecycle runtime policy memerlukan scope platform:capabilities.review.high_risk.");return;
    }
    if(policyReason.trim().length<8){setError("Alasan review policy minimal 8 karakter.");return;}
    setBusy(true);setError("");setNotice("");
    try{
      await read(await apiFetch("/v1/admin/operator/runtime-policies/"+encodeURIComponent(policy.id)+"/"+(decision==="approve"?"approve":"revoke"),session,{
        method:"POST",body:JSON.stringify({reason:policyReason.trim()}),
      }));
      setPolicyReason("");
      setNotice(decision==="approve"?"Runtime policy disetujui dan aktif untuk evaluasi capability.":"Runtime policy dicabut; Runtime tidak boleh menggunakan policy ini.");
      await loadPolicyInventory(policy.agent_id);
      await load(session);
    }catch(cause){setError(cause instanceof Error?cause.message:"Perubahan lifecycle runtime policy gagal.");}
    finally{setBusy(false);}
  }

  async function review(item:Capability,decision:"approved"|"denied"){
    if(!session)return;
    const reason=(reasons[item.id]||"").trim();
    if(reason.length<8){setError("Alasan review minimal 8 karakter.");return;}
    const highRisk=["high","critical"].includes(item.risk_level);
    if(highRisk&&!operator?.scopes.includes("platform:capabilities.review.high_risk")){setError("Capability high/critical memerlukan scope platform:capabilities.review.high_risk.");return;}
    const policyVersion=selectedPolicy[item.id];
    if(decision==="approved"&&!policyVersion){setError("Pilih approved runtime policy untuk Agent ini sebelum menyetujui capability.");return;}
    setBusy(true);setError("");setNotice("");
    try{
      const payload:Record<string,unknown>={decision,reason};
      if(decision==="approved")payload.policy_version=Number(policyVersion);
      await read(await apiFetch("/v1/admin/operator/capabilities/"+encodeURIComponent(item.id)+"/review",session,{method:"POST",body:JSON.stringify(payload)}));
      setNotice(decision==="approved"?"Capability disetujui dengan policy version yang aktif. Runtime tetap memeriksa policy, scope, tool dan owner saat eksekusi.":"Capability ditolak dan tidak memperoleh otorisasi Runtime.");
      setReasons(current=>({...current,[item.id]:""}));
      await load(session);
    }catch(cause){setError(cause instanceof Error?cause.message:"Review capability gagal.");}
    finally{setBusy(false);}
  }

  const field="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100";
  return <main className="mx-auto max-w-6xl space-y-6 p-4 sm:p-6">
    <header className="flex flex-wrap items-center justify-between gap-3">
      <div><p className="text-xs font-semibold uppercase tracking-widest text-indigo-600">Allpha Super Admin</p><h1 className="text-2xl font-bold">Agent Capability Governance</h1><p className="mt-1 text-sm text-slate-500">Review capability requests against approved Agent Runtime Policies.</p></div>
      <nav className="flex flex-wrap gap-3 text-sm"><Link className="underline" href="/agent-social-audit">Identity & License Audit</Link><Link className="underline" href="/billing-governance">Billing Governance</Link></nav>
    </header>
    {!session?<form onSubmit={login} className="mx-auto grid max-w-md gap-3 rounded-2xl border p-5"><h2 className="font-semibold">Operator Login</h2><label className="grid gap-1 text-sm">Email<input className={field} type="email" autoComplete="username" value={email} onChange={e=>setEmail(e.target.value)} required/></label><label className="grid gap-1 text-sm">Password<input className={field} type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} required/></label><button disabled={busy} className="rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50">{busy?"Memproses…":"Login Operator"}</button></form>:<>
      <section className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border p-4"><div><p className="text-sm font-semibold">{operator?.email||operator?.id}</p><p className="text-xs text-slate-500">Scope: {operator?.scopes.join(", ")}</p></div><button onClick={()=>void refresh()} disabled={busy} className="rounded-xl border px-4 py-2 text-sm disabled:opacity-50">Refresh queue</button></section>
      {error&&<p role="alert" className="rounded-xl border border-rose-300 bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
      {notice&&<p role="status" className="rounded-xl border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</p>}
      <section className="space-y-4 rounded-2xl border p-4">
        <div><h2 className="text-lg font-semibold">Agent Runtime Policy Registry</h2><p className="text-sm text-slate-500">Buat policy draft, tinjau daftar policy dan aktifkan melalui high-risk approval. Runtime hanya menggunakan policy berstatus approved.</p></div>
        <div className="grid gap-3 md:grid-cols-[1fr_auto]"><label className="grid gap-1 text-sm">Target Agent UUID<input className={field} value={policyAgentId} onChange={e=>setPolicyAgentId(e.target.value)} placeholder="UUID Agent"/></label><button type="button" disabled={busy||!policyAgentId.trim()} onClick={()=>void loadPolicyInventory()} className="self-end rounded-xl border px-4 py-2 text-sm disabled:opacity-50">Load policy inventory</button></div>
        <form onSubmit={createRuntimePolicy} className="grid gap-3 rounded-xl bg-slate-50 p-3 dark:bg-slate-900 md:grid-cols-2">
          <label className="grid gap-1 text-sm">Policy version<input className={field} type="number" min="1" step="1" value={policyVersion} onChange={e=>setPolicyVersion(e.target.value)} required/></label>
          <label className="grid gap-1 text-sm">Approved tool keys (comma separated)<input className={field} value={policyTools} onChange={e=>setPolicyTools(e.target.value)} placeholder="web_search, knowledge_search" required/></label>
          <label className="grid gap-1 text-sm md:col-span-2">Required permission scopes (comma separated)<input className={field} value={policyScopes} onChange={e=>setPolicyScopes(e.target.value)} placeholder="network.read, knowledge.read"/></label>
          <label className="grid gap-1 text-sm md:col-span-2">Risk constraints JSON<textarea className={field} rows={3} value={policyConstraints} onChange={e=>setPolicyConstraints(e.target.value)}/></label>
          <button disabled={busy||!operator?.scopes.includes("platform:capabilities.review")} className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 md:col-span-2">Create runtime policy draft</button>
        </form>
        <label className="grid gap-1 text-sm">Policy approval / revocation reason<textarea className={field} rows={2} minLength={8} value={policyReason} onChange={e=>setPolicyReason(e.target.value)} placeholder="Alasan review policy (min. 8 karakter)"/></label>
        <div className="grid gap-3 lg:grid-cols-3">
          <div className="rounded-xl border p-3"><h3 className="mb-2 font-semibold">Draft ({policyDrafts.length})</h3>{policyDrafts.map(item=><div key={item.id} className="mb-2 rounded-lg bg-slate-50 p-2 text-xs dark:bg-slate-900"><p className="font-semibold">v{item.policy_version} · {item.policy_digest.slice(0,12)}…</p><p>{item.approved_tool_keys.join(", ")}</p><button type="button" disabled={busy||!operator?.scopes.includes("platform:capabilities.review.high_risk")||policyReason.trim().length<8} onClick={()=>void reviewRuntimePolicy(item,"approve")} className="mt-2 rounded-lg bg-emerald-700 px-3 py-1.5 font-semibold text-white disabled:opacity-40">Approve</button></div>)}</div>
          <div className="rounded-xl border p-3"><h3 className="mb-2 font-semibold">Approved ({policyApproved.length})</h3>{policyApproved.map(item=><div key={item.id} className="mb-2 rounded-lg bg-emerald-50 p-2 text-xs dark:bg-emerald-950"><p className="font-semibold">v{item.policy_version} · active</p><p>{item.approved_tool_keys.join(", ")}</p><button type="button" disabled={busy||!operator?.scopes.includes("platform:capabilities.review.high_risk")||policyReason.trim().length<8} onClick={()=>void reviewRuntimePolicy(item,"revoke")} className="mt-2 rounded-lg border border-rose-300 px-3 py-1.5 font-semibold text-rose-700 disabled:opacity-40">Revoke</button></div>)}</div>
          <div className="rounded-xl border p-3"><h3 className="mb-2 font-semibold">Revoked ({policyRevoked.length})</h3>{policyRevoked.map(item=><div key={item.id} className="mb-2 rounded-lg bg-slate-50 p-2 text-xs text-slate-500 dark:bg-slate-900"><p className="font-semibold">v{item.policy_version} · revoked</p><p>{item.approved_tool_keys.join(", ")}</p></div>)}</div>
        </div>
        <p className="text-xs text-slate-500">Paid Skill license terms remain blocked unless a matching Billing entitlement exists. Capability approval never bypasses Agent ownership, permission scope or Runtime policy checks.</p>
      </section>
      <section className="space-y-3"><div className="flex items-center justify-between"><h2 className="text-lg font-semibold">Pending capability requests</h2><span className="text-sm text-slate-500">{requests.length} pending</span></div>
        {requests.length===0?<div className="rounded-2xl border border-dashed p-8 text-center text-sm text-slate-500">Tidak ada capability request yang menunggu review.</div>:requests.map(item=>{
          const available=policies[item.agent_id]||[];
          const selected=available.find(policy=>String(policy.policy_version)===selectedPolicy[item.id]);
          const toolAllowed=!!selected?.approved_tool_keys?.includes(item.capability_key);
          const scopesAllowed=!!selected&&((item.required_permission_scopes||[]).every(scope=>(selected.required_permission_scopes||[]).includes(scope)));
          const highRisk=["high","critical"].includes(item.risk_level);
          const highScope=operator?.scopes.includes("platform:capabilities.review.high_risk")||false;
          return <article key={item.id} className="space-y-3 rounded-2xl border p-4">
            <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-semibold">{item.capability_key}</h3><p className="text-xs text-slate-500">Agent {item.agent_id} · Requested by {item.created_by}</p></div><span className={"rounded-full px-2.5 py-1 text-xs font-semibold "+(highRisk?"bg-rose-100 text-rose-800":"bg-amber-100 text-amber-800")}>{item.risk_level} risk</span></div>
            <p className="text-sm text-slate-700 dark:text-slate-300">{item.description}</p>
            <div className="flex flex-wrap gap-1.5">{(item.required_permission_scopes||[]).map(scope=><span key={scope} className="rounded-lg bg-slate-100 px-2 py-1 text-xs dark:bg-slate-800">{scope}</span>)}</div>
            <label className="grid gap-1 text-sm">Approved Runtime Policy
              <select className={field} value={selectedPolicy[item.id]||""} onChange={e=>setSelectedPolicy(current=>({...current,[item.id]:e.target.value}))}><option value="">Pilih policy version</option>{available.map(policy=><option key={policy.id} value={policy.policy_version}>v{policy.policy_version} · {policy.policy_digest.slice(0,12)}…</option>)}</select>
            </label>
            {selected&&<p className={"text-xs "+(toolAllowed&&scopesAllowed?"text-emerald-700":"text-rose-700")}>Tool {toolAllowed?"diizinkan":"tidak tercantum"} · Permission scopes {scopesAllowed?"sesuai":"melampaui policy"}</p>}
            {available.length===0&&<p className="text-xs text-rose-700">Belum ada approved runtime policy untuk Agent ini. Capability tidak dapat disetujui sebelum policy dibuat dan diaktifkan.</p>}
            {highRisk&&!highScope&&<p className="text-xs text-rose-700">Review high/critical memerlukan scope tambahan platform:capabilities.review.high_risk.</p>}
            <label className="grid gap-1 text-sm">Alasan review<textarea className={field} rows={2} minLength={8} value={reasons[item.id]||""} onChange={e=>setReasons(current=>({...current,[item.id]:e.target.value}))} placeholder="Jelaskan dasar persetujuan atau penolakan…"/></label>
            <div className="flex flex-wrap gap-2"><button disabled={busy||!toolAllowed||!scopesAllowed||!selected||highRisk&&!highScope} onClick={()=>void review(item,"approved")} className="rounded-xl bg-emerald-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">Approve with policy</button><button disabled={busy||highRisk&&!highScope} onClick={()=>void review(item,"denied")} className="rounded-xl border border-rose-300 px-4 py-2 text-sm font-semibold text-rose-700 disabled:opacity-40">Deny</button></div>
          </article>;
        })}
      </section>
    </>}
  </main>;
}

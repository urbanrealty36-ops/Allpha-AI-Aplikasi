"use client";
import {useCallback,useEffect,useMemo,useState} from "react";
import {useParams} from "next/navigation";
import Link from "next/link";
import type {Session} from "@supabase/supabase-js";
import {getBrowserSupabase} from "../../../../lib/supabase";

type PersistentT="working"|"episodic"|"semantic"|"procedural"|"long_term";
type T=PersistentT|"conversation";
type Policy={id:string;memory_type:T;enabled:boolean;retention_days:number;policy_version:number};
type Item={id:string;memory_type:PersistentT;content:string;classification:string;purpose:string;status:string;version:number;retention_expires_at:string;pinned_at?:string|null};
type RetrievedItem={id:string;memory_type:PersistentT;content:string;classification:string;purpose:string;retrieval_method:"keyword"|"metadata";retrieval_score:number};
type MemoryEvent={id:string;event_type:string;details:Record<string,unknown>;created_at:string};
const api=(process.env.NEXT_PUBLIC_API_BASE_URL||(process.env.NODE_ENV==="production"?"https://api.allpha.web.id":"http://localhost:8000")).replace(/\/$/,"");
const defs:{key:T;title:string;description:string;days:number}[]=[
{key:"conversation",title:"Conversation Memory",description:"Konteks baca-saja dari Messaging kanonis. Tidak disalin ke Memory items; memerlukan consent Restricted dan dibatasi retensi.",days:30},
{key:"working",title:"Working Memory",description:"Konteks tugas/sesi sementara, maksimum 24 jam.",days:1},
{key:"episodic",title:"Episodic Memory",description:"Ringkasan kejadian dengan aktor, waktu dan provenance.",days:30},
{key:"semantic",title:"Semantic Memory",description:"Fakta dan konsep dengan sumber, confidence dan scope.",days:90},
{key:"procedural",title:"Procedural Memory",description:"Pola reusable; tidak pernah memberikan tool authority.",days:90},
{key:"long_term",title:"Long-term Memory",description:"Memori persisten dengan consent, retensi, koreksi dan penghapusan.",days:365}];
async function err(r:Response){const b=await r.json().catch(()=>({}));return b?.error?.message??b?.detail?.message??"Permintaan gagal ("+r.status+").";}

export default function AgentMemoryPage(){
 const params=useParams<{agentId:string}>(),agentId=params.agentId,supabase=useMemo(()=>getBrowserSupabase(),[]);
 const [session,setSession]=useState<Session|null>(null),[policies,setPolicies]=useState<Policy[]>([]),[items,setItems]=useState<Item[]>([]),[events,setEvents]=useState<MemoryEvent[]>([]);
 const [enabled,setEnabled]=useState<Record<string,boolean>>({}),[retention,setRetention]=useState<Record<string,number>>({}),[consent,setConsent]=useState(false);
 const [loading,setLoading]=useState(true),[saving,setSaving]=useState(""),[error,setError]=useState(""),[notice,setNotice]=useState("");
 const [editing,setEditing]=useState(""),[draft,setDraft]=useState("");
 const [retrievalQuery,setRetrievalQuery]=useState(""),[retrievalPurpose,setRetrievalPurpose]=useState("agent_generation_context"),[retrievalMaxSensitivity,setRetrievalMaxSensitivity]=useState(""),[retrievalMode,setRetrievalMode]=useState(""),[retrievalResults,setRetrievalResults]=useState<RetrievedItem[]>([]),[retrievalBusy,setRetrievalBusy]=useState(false);
 const [proposalType,setProposalType]=useState<PersistentT>("episodic"),[proposalPurpose,setProposalPurpose]=useState("agent_generation_context"),[proposalClass,setProposalClass]=useState("internal"),[proposalText,setProposalText]=useState("");
 const load=useCallback(async(s:Session)=>{
  setLoading(true);setError("");
  try{
   const h={Authorization:"Bearer "+s.access_token,Accept:"application/json"};
   const [pr,ir,er]=await Promise.all([
    fetch(api+"/v1/memory/policies?agent_id="+encodeURIComponent(agentId),{headers:h,cache:"no-store"}),
    fetch(api+"/v1/memory/items?agent_id="+encodeURIComponent(agentId)+"&limit=100",{headers:h,cache:"no-store"}),
    fetch(api+"/v1/memory/events?agent_id="+encodeURIComponent(agentId)+"&limit=100",{headers:h,cache:"no-store"})]);
   if(!pr.ok)throw new Error(await err(pr));if(!ir.ok)throw new Error(await err(ir));if(!er.ok)throw new Error(await err(er));
   const [p,i,e]=await Promise.all([pr.json(),ir.json(),er.json()]),list:Policy[]=Array.isArray(p.items)?p.items:[];
   setPolicies(list);setItems(Array.isArray(i.items)?i.items:[]);setEvents(Array.isArray(e.items)?e.items:[]);
   setEnabled(Object.fromEntries(defs.map(d=>[d.key,!!list.find(x=>x.memory_type===d.key)?.enabled])));
   setRetention(Object.fromEntries(defs.map(d=>[d.key,list.find(x=>x.memory_type===d.key)?.retention_days??d.days])));
  }catch(e){setError(e instanceof Error?e.message:"Memory Coordinator tidak dapat dimuat.");}finally{setLoading(false);}
 },[agentId]);
 useEffect(()=>{
  if(!supabase){setLoading(false);setError("Autentikasi belum tersedia.");return;}
  let alive=true;
  void supabase.auth.getSession().then(({data})=>{if(!alive)return;setSession(data.session);if(data.session)void load(data.session);else{setLoading(false);setError("Masuk terlebih dahulu.");}});
  const {data:sub}=supabase.auth.onAuthStateChange((_event,s)=>{if(!alive)return;setSession(s);if(s)void load(s);else{setItems([]);setPolicies([]);setLoading(false);setError("Sesi berakhir.");}});
  return()=>{alive=false;sub.subscription.unsubscribe();};
 },[supabase,load]);
 async function savePolicy(type:T){
  if(!session)return;const on=!!enabled[type];if(on&&!consent){setError("Berikan persetujuan eksplisit terlebih dahulu.");return;}
  setSaving(type);setError("");setNotice("");
  try{
   const r=await fetch(api+"/v1/memory/policies/"+type,{method:"PUT",headers:{Authorization:"Bearer "+session.access_token,"Content-Type":"application/json"},
    body:JSON.stringify({agent_id:agentId,enabled:on,consent_version:on?"allpha.memory.v1":null,
     allowed_purposes:on?["agent_generation_context","agent_runtime_context"]:[],
     allowed_sensitivities:on?(type==="conversation"?["restricted"]:["public","internal","confidential"]):[],retention_days:type==="working"?1:Number(retention[type]??30)})});
   if(!r.ok)throw new Error(await err(r));setNotice(on?"Policy Memory diaktifkan dengan approval manual.":"Policy dinonaktifkan; retrieval akan berhenti.");await load(session);
  }catch(e){setError(e instanceof Error?e.message:"Policy gagal disimpan.");}finally{setSaving("");}
 }
 async function revokeAll(){
  if(!session||!window.confirm("Cabut persetujuan semua kelas Memory untuk Agent ini?"))return;
  setSaving("all");setError("");setNotice("");
  try{
   for(const d of defs){
    const r=await fetch(api+"/v1/memory/policies/"+d.key,{method:"PUT",headers:{Authorization:"Bearer "+session.access_token,"Content-Type":"application/json"},
     body:JSON.stringify({agent_id:agentId,enabled:false,consent_version:null,allowed_purposes:[],allowed_sensitivities:[],retention_days:d.key==="working"?1:Number(retention[d.key]??d.days)})});
    if(!r.ok)throw new Error(await err(r));
   }
   setConsent(false);setEnabled({});setNotice("Semua persetujuan Memory dicabut; item lama tidak lagi memenuhi policy version untuk retrieval.");await load(session);
  }catch(e){setError(e instanceof Error?e.message:"Pencabutan consent tidak selesai; periksa setiap policy.");await load(session);}
  finally{setSaving("");}
 }
 async function retrieveMemory(){
  if(!session)return;setRetrievalBusy(true);setError("");setNotice("");
  try{
   const r=await fetch(api+"/v1/memory/context",{method:"POST",headers:{Authorization:"Bearer "+session.access_token,"Content-Type":"application/json"},
    body:JSON.stringify({agent_id:agentId,purpose:retrievalPurpose,query:retrievalQuery.trim()||null,max_sensitivity:retrievalMaxSensitivity||null,limit:12})});
   if(!r.ok)throw new Error(await err(r));const body=await r.json();setRetrievalResults(Array.isArray(body.items)?body.items:[]);setRetrievalMode(body.retrieval_mode??"");
  }catch(e){setError(e instanceof Error?e.message:"Retrieval Memory gagal.");}finally{setRetrievalBusy(false);}
 }
 async function createProposal(){
  if(!session)return;
  const policy=policies.find(x=>x.memory_type===proposalType);
  if(!policy?.enabled){setError("Aktifkan consent untuk kelas Memory ini sebelum membuat proposal.");return;}
  if(!proposalText.trim()){setError("Isi konten proposal terlebih dahulu.");return;}
  setSaving("proposal");setError("");setNotice("");
  try{
   const r=await fetch(api+"/v1/memory/proposals",{method:"POST",headers:{Authorization:"Bearer "+session.access_token,"Content-Type":"application/json"},
    body:JSON.stringify({agent_id:agentId,memory_type:proposalType,purpose:proposalPurpose,classification:proposalClass,content:proposalText.trim(),source_ref:{kind:"owner_manual"},provenance:{created_by:"owner",capture_mode:"manual"},retention_days:proposalType==="working"?1:undefined})});
   if(!r.ok)throw new Error(await err(r));
   setProposalText("");setNotice("Proposal tersimpan untuk keputusan pemilik. Proposal belum aktif dan belum masuk retrieval.");await load(session);
  }catch(e){setError(e instanceof Error?e.message:"Proposal Memory gagal dibuat.");}finally{setSaving("");}
 }
 async function decide(item:Item,decision:"approve"|"reject"){
  if(!session)return;setSaving(item.id);
  try{const r=await fetch(api+"/v1/memory/items/"+item.id+"/decision",{method:"POST",headers:{Authorization:"Bearer "+session.access_token,"Content-Type":"application/json"},body:JSON.stringify({decision})});
   if(!r.ok)throw new Error(await err(r));setNotice(decision==="approve"?"Proposal disetujui.":"Proposal ditolak.");await load(session);
  }catch(e){setError(e instanceof Error?e.message:"Keputusan proposal gagal.");}finally{setSaving("");}
 }
 async function correct(item:Item){
  if(!session)return;setSaving(item.id);
  try{const r=await fetch(api+"/v1/memory/items/"+item.id,{method:"PATCH",headers:{Authorization:"Bearer "+session.access_token,"Content-Type":"application/json"},body:JSON.stringify({content:draft})});
   if(!r.ok)throw new Error(await err(r));setEditing("");setNotice("Memori dikoreksi.");await load(session);
  }catch(e){setError(e instanceof Error?e.message:"Koreksi gagal.");}finally{setSaving("");}
 }
 async function remove(item:Item){
  if(!session||!window.confirm("Hapus memori ini?"))return;setSaving(item.id);
  try{const r=await fetch(api+"/v1/memory/items/"+item.id,{method:"DELETE",headers:{Authorization:"Bearer "+session.access_token}});
   if(!r.ok)throw new Error(await err(r));setNotice("Memori dihapus dan tidak lagi tersedia dalam retrieval.");await load(session);
  }catch(e){setError(e instanceof Error?e.message:"Penghapusan gagal.");}finally{setSaving("");}
 }
 async function pin(item:Item,pinned:boolean){
  if(!session)return;setSaving(item.id);
  try{const r=await fetch(api+"/v1/memory/items/"+item.id+"/pin",{method:"POST",headers:{Authorization:"Bearer "+session.access_token,"Content-Type":"application/json"},body:JSON.stringify({pinned})});
   if(!r.ok)throw new Error(await err(r));setNotice(pinned?"Memori disematkan. Retensi tetap berjalan sesuai policy.":"Sematan Memori dilepas.");await load(session);
  }catch(e){setError(e instanceof Error?e.message:"Perubahan pin gagal.");}finally{setSaving("");}
 }
 async function expireItem(item:Item){
  if(!session||!window.confirm("Akhiri Memory ini sekarang? Konten akan dikosongkan dan tidak dapat dipulihkan."))return;setSaving(item.id);
  try{const r=await fetch(api+"/v1/memory/items/"+item.id+"/expire",{method:"POST",headers:{Authorization:"Bearer "+session.access_token}});
   if(!r.ok)throw new Error(await err(r));setNotice("Memory di-expire; konten privat dikosongkan dan audit dipertahankan.");await load(session);
  }catch(e){setError(e instanceof Error?e.message:"Expiry Memory gagal.");}finally{setSaving("");}
 }
 if(loading)return <main className="mx-auto max-w-5xl p-6">Memuat Memory Studio…</main>;
 return <main className="mx-auto max-w-5xl space-y-6 p-4 sm:p-6">
  <header className="flex flex-wrap items-end justify-between gap-3 border-b pb-5">
   <div><p className="text-xs font-semibold uppercase tracking-[0.18em] text-neutral-500">Allpha · Agent Intelligence</p><h1 className="mt-2 text-3xl font-semibold">Memory Studio</h1><p className="mt-2 max-w-2xl text-sm text-neutral-600">Consent, klasifikasi, retensi, proposal, koreksi dan penghapusan memori privat Agent.</p></div>
   <Link href={"/agents/"+agentId+"/studio"} className="rounded-xl border px-4 py-2 text-sm font-medium">Kembali ke Agent Studio</Link>
  </header>
  {error&&<div role="alert" className="rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-900">{error}</div>}
  {notice&&<div role="status" className="rounded-xl border p-3 text-sm">{notice}</div>}
  <section className="rounded-2xl border p-4 sm:p-5">
   <h2 className="text-lg font-semibold">Consent dan kebijakan penyimpanan</h2>
   <p className="mt-1 text-sm text-neutral-600">Semua kelas persisten nonaktif secara default. Model hanya boleh mengusulkan memori; pemilik harus menyetujui setiap proposal. External Consumer tidak memperoleh memori privat pemilik. Perubahan policy version akan mengakhiri dan membersihkan item lama agar tidak dipakai dengan consent yang berbeda.</p><p className="mt-2 text-xs text-neutral-500">Memory Coordinator aktif. Setiap proposal tetap menunggu persetujuan pemilik; pin tidak memperpanjang retensi dan item yang di-expire langsung dihapus dari retrieval.</p>
   <label className="mt-4 flex items-start gap-3 rounded-xl border p-3 text-sm"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)} className="mt-1"/><span><strong>Persetujuan eksplisit pemilik</strong><span className="block text-neutral-600">Saya mengizinkan penyimpanan sesuai jenis, tujuan, klasifikasi dan masa retensi yang saya aktifkan. Persetujuan dapat dicabut kapan saja.</span></span></label>
   <div className="mt-3 flex justify-end"><button disabled={saving==="all"} onClick={()=>void revokeAll()} className="rounded-xl border border-red-300 px-4 py-2 text-sm text-red-700 disabled:opacity-50">{saving==="all"?"Mencabut…":"Cabut semua persetujuan"}</button></div>
   <div className="mt-4 grid gap-3">{defs.map(d=>{const p=policies.find(x=>x.memory_type===d.key);const on=!!enabled[d.key];return <article key={d.key} className="rounded-xl border p-4">
    <div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0 flex-1"><div className="flex items-center gap-2"><h3 className="font-semibold">{d.title}</h3><span className="rounded-full border px-2 py-0.5 text-xs">{on?"Aktif":"Nonaktif"}</span></div><p className="mt-1 text-sm text-neutral-600">{d.description}</p><p className="mt-2 text-xs text-neutral-500">Policy v{p?.policy_version??0} · Retensi {retention[d.key]??d.days} hari · Approval manual</p></div><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={on} onChange={e=>setEnabled(v=>({...v,[d.key]:e.target.checked}))}/>Aktifkan</label></div>
    <div className="mt-3 flex flex-wrap items-center justify-between gap-2"><label className="flex items-center gap-2 text-xs text-neutral-600">Retensi (hari)<input type="number" min={1} max={3650} disabled={d.key==="working"||!on} value={retention[d.key]??d.days} onChange={e=>setRetention(v=>({...v,[d.key]:Number(e.target.value)}))} className="w-24 rounded-lg border px-2 py-1 text-sm text-neutral-900 disabled:opacity-50"/></label><button disabled={saving===d.key||(on&&!consent)} onClick={()=>void savePolicy(d.key)} className="rounded-xl bg-neutral-900 px-4 py-2 text-sm text-white disabled:opacity-50">{saving===d.key?"Menyimpan…":"Simpan kebijakan"}</button></div>
   </article>;})}</div>
  </section>
  <section className="rounded-2xl border p-4 sm:p-5"><h2 className="text-lg font-semibold">Conversation Memory · Messaging kanonis</h2><p className="mt-1 text-sm text-neutral-600">Aktifkan consent terpisah di atas untuk mengizinkan Agent membaca konteks percakapan milik participant yang terverifikasi. Pesan tetap berada di conversations/messages, tidak disalin ke agent_memory_items, tidak dapat diubah dari Memory Studio, dan retrieval memakai klasifikasi Restricted serta batas retensi policy.</p><span className="mt-3 inline-flex rounded-full border px-2 py-1 text-xs">Participant-scoped · Read-only · Consent-gated</span></section>
  <section className="space-y-3 rounded-2xl border p-4 sm:p-5">
   <div><h2 className="text-lg font-semibold">Cari konteks Memory</h2><p className="mt-1 text-sm text-neutral-600">Gunakan retrieval API dengan scope Agent dan tujuan yang dipilih. Pencarian memakai ranking full-text PostgreSQL atau recency metadata, selalu mengikuti consent, klasifikasi, policy version, retensi dan ownership di backend.</p></div>
   <div className="flex flex-col gap-2 sm:flex-row"><input value={retrievalQuery} onChange={e=>setRetrievalQuery(e.target.value)} maxLength={300} placeholder="Cari fakta atau konteks (opsional)" className="min-w-0 flex-1 rounded-xl border px-3 py-2 text-sm"/><select value={retrievalPurpose} onChange={e=>setRetrievalPurpose(e.target.value)} className="rounded-xl border bg-white px-3 py-2 text-sm text-neutral-900"><option value="agent_generation_context">Generation</option><option value="agent_runtime_context">Agent Runtime</option></select><select value={retrievalMaxSensitivity} onChange={e=>setRetrievalMaxSensitivity(e.target.value)} aria-label="Batas klasifikasi Memory" className="rounded-xl border bg-white px-3 py-2 text-sm text-neutral-900"><option value="">Semua klasifikasi yang diizinkan</option><option value="public">Maks. Public</option><option value="internal">Maks. Internal</option><option value="confidential">Maks. Confidential</option><option value="restricted">Maks. Restricted</option></select><button disabled={retrievalBusy||!policies.some(p=>p.enabled&&p.memory_type!=="conversation")} onClick={()=>void retrieveMemory()} className="rounded-xl bg-neutral-900 px-4 py-2 text-sm text-white disabled:opacity-50">{retrievalBusy?"Mencari…":"Cari Memory"}</button></div>
   {retrievalMode&&<p className="text-xs text-neutral-500">Mode: {retrievalMode==="keyword_ranked"?"Keyword ranked (ts_rank_cd)":retrievalMode==="metadata_recency"?"Metadata / recency":"—"} · Vector/hybrid masih menunggu persetujuan profil embedding dan index.</p>}
   {retrievalResults.length===0?<p className="text-xs text-neutral-500">Belum ada hasil retrieval pada sesi ini. Periksa consent, status approval, scope Agent, dan masa retensi.</p>:<div className="space-y-2">{retrievalResults.map(item=><article key={item.id} className="rounded-xl border p-3"><div className="flex flex-wrap items-center gap-2 text-xs"><strong className="capitalize">{item.memory_type.replace("_"," ")}</strong><span className="rounded-full border px-2 py-0.5">{item.classification}</span><span className="text-neutral-500">{item.retrieval_method} · score {Number(item.retrieval_score??0).toFixed(3)}</span></div><p className="mt-2 whitespace-pre-wrap text-sm">{item.content}</p></article>)}</div>}
  </section>
  <section className="space-y-3 rounded-2xl border p-4 sm:p-5">
   <div><h2 className="text-lg font-semibold">Ajukan Memory secara manual</h2><p className="mt-1 text-sm text-neutral-600">Buat proposal manual, atau gunakan instruksi eksplisit “ingat bahwa…” di Agent Chat milik owner. Instruksi tersebut hanya membuat proposal pending jika consent Long-term Memory aktif; tidak ada ekstraksi inferensial oleh model. Persetujuan tetap diperlukan.</p></div>
   <div className="grid gap-3 sm:grid-cols-3">
    <label className="space-y-1 text-xs font-medium text-neutral-600">Kelas Memory<select value={proposalType} onChange={e=>setProposalType(e.target.value as PersistentT)} className="w-full rounded-xl border bg-white px-3 py-2 text-sm text-neutral-900">{defs.filter(d=>d.key!=="conversation").map(d=><option key={d.key} value={d.key} disabled={!policies.find(p=>p.memory_type===d.key)?.enabled}>{d.title}{policies.find(p=>p.memory_type===d.key)?.enabled?"":" · consent nonaktif"}</option>)}</select></label>
    <label className="space-y-1 text-xs font-medium text-neutral-600">Tujuan<select value={proposalPurpose} onChange={e=>setProposalPurpose(e.target.value)} className="w-full rounded-xl border bg-white px-3 py-2 text-sm text-neutral-900"><option value="agent_generation_context">Generation context</option><option value="agent_runtime_context">Agent runtime context</option></select></label>
    <label className="space-y-1 text-xs font-medium text-neutral-600">Klasifikasi<select value={proposalClass} onChange={e=>setProposalClass(e.target.value)} className="w-full rounded-xl border bg-white px-3 py-2 text-sm text-neutral-900"><option value="public">Public</option><option value="internal">Internal</option><option value="confidential">Confidential</option></select></label>
   </div>
   <textarea value={proposalText} onChange={e=>setProposalText(e.target.value)} rows={4} maxLength={8000} placeholder="Tuliskan fakta, preferensi atau kejadian yang ingin diajukan sebagai Memory…" className="w-full rounded-xl border p-3 text-sm"/>
   <div className="flex flex-wrap items-center justify-between gap-2"><span className="text-xs text-neutral-500">{proposalText.length}/8000 karakter · Manual owner input</span><button disabled={saving==="proposal"||!policies.some(p=>p.memory_type===proposalType&&p.enabled)||!proposalText.trim()} onClick={()=>void createProposal()} className="rounded-xl bg-neutral-900 px-4 py-2 text-sm text-white disabled:opacity-50">{saving==="proposal"?"Menyimpan proposal…":"Ajukan untuk persetujuan"}</button></div>
   {!policies.some(p=>p.memory_type===proposalType&&p.enabled)&&<p className="text-xs text-amber-700">Kelas yang dipilih belum memiliki consent aktif. Proposal tetap diblokir oleh UI dan API sampai pemilik mengaktifkan policy.</p>}
  </section>
  <section className="space-y-3 rounded-2xl border p-4 sm:p-5"><div><h2 className="text-lg font-semibold">Memory proposals dan item tersimpan</h2><p className="mt-1 text-sm text-neutral-600">Hanya item yang disetujui dan policy version-nya masih berlaku yang masuk retrieval. Saat ini ranked keyword/metadata; vector/hybrid menunggu persetujuan profil embedding, dimensi dan index.</p></div>
   {items.length===0?<p className="rounded-xl border border-dashed p-4 text-sm text-neutral-600">Belum ada proposal atau item Memory.</p>:items.map(item=><article key={item.id} className="rounded-xl border p-4">
    <div className="flex flex-wrap items-center justify-between gap-2"><div className="flex flex-wrap items-center gap-2"><strong className="capitalize">{item.memory_type.replace("_"," ")}</strong><span className="rounded-full border px-2 py-0.5 text-xs">{item.status}</span><span className="rounded-full border px-2 py-0.5 text-xs">{item.classification}</span>{item.pinned_at&&<span className="rounded-full border px-2 py-0.5 text-xs">Disematkan</span>}</div><span className="text-xs text-neutral-500">v{item.version}</span></div>
    {editing===item.id?<div className="mt-3 space-y-2"><textarea value={draft} onChange={e=>setDraft(e.target.value)} rows={4} maxLength={8000} className="w-full rounded-xl border p-3 text-sm"/><div className="flex gap-2"><button disabled={saving===item.id} onClick={()=>void correct(item)} className="rounded-lg bg-neutral-900 px-3 py-2 text-xs text-white">Simpan koreksi</button><button onClick={()=>setEditing("")} className="rounded-lg border px-3 py-2 text-xs">Batal</button></div></div>:<p className="mt-3 whitespace-pre-wrap text-sm leading-6">{item.content}</p>}
    <p className="mt-2 text-xs text-neutral-500">Tujuan: {item.purpose} · Kedaluwarsa: {new Date(item.retention_expires_at).toLocaleDateString("id-ID")}</p>
    <div className="mt-3 flex flex-wrap gap-2">{item.status==="pending"&&<><button disabled={saving===item.id} onClick={()=>void decide(item,"approve")} className="rounded-lg bg-neutral-900 px-3 py-2 text-xs text-white">Setujui</button><button disabled={saving===item.id} onClick={()=>void decide(item,"reject")} className="rounded-lg border px-3 py-2 text-xs">Tolak</button></>}{item.status==="active"&&<><button disabled={saving===item.id} onClick={()=>void pin(item,!item.pinned_at)} className="rounded-lg border px-3 py-2 text-xs">{item.pinned_at?"Lepas pin":"Sematkan"}</button><button disabled={saving===item.id} onClick={()=>void expireItem(item)} className="rounded-lg border border-amber-300 px-3 py-2 text-xs text-amber-800">Expire sekarang</button><button onClick={()=>{setEditing(item.id);setDraft(item.content);}} className="rounded-lg border px-3 py-2 text-xs">Koreksi</button><button disabled={saving===item.id} onClick={()=>void remove(item)} className="rounded-lg border border-red-300 px-3 py-2 text-xs text-red-700">Hapus</button></>}</div>
   </article>)}
  </section>
  <section className="space-y-3 rounded-2xl border p-4 sm:p-5">
   <div><h2 className="text-lg font-semibold">Riwayat persetujuan dan audit Memory</h2><p className="mt-1 text-sm text-neutral-600">Event hanya menyimpan metadata governance, versi policy dan hash; konten privat tidak disalin ke audit event.</p></div>
   {events.length===0?<p className="text-xs text-neutral-500">Belum ada event Memory.</p>:<div className="space-y-2">{events.map(event=><article key={event.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border p-3"><div><strong className="text-sm">{event.event_type.replaceAll("_"," ")}</strong><p className="mt-1 text-xs text-neutral-500">{JSON.stringify(event.details)}</p></div><time className="text-xs text-neutral-500">{new Date(event.created_at).toLocaleString("id-ID")}</time></article>)}</div>}
  </section>
 </main>;
}
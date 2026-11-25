import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Alert, Pressable, ScrollView, Text, TextInput, View } from "react-native";

type PersistentMemoryType="working"|"episodic"|"semantic"|"procedural"|"long_term";
type PolicyMemoryType=PersistentMemoryType|"conversation";
type MemoryPolicy={id:string;memory_type:PolicyMemoryType;enabled:boolean;consent_version?:string|null;allowed_purposes:string[];allowed_sensitivities:string[];retention_days:number;policy_version:number;consent_revoked_at?:string|null};
type MemoryItem={id:string;memory_type:PersistentMemoryType;purpose:string;classification:string;content:string;status:string;confidence?:number|null;retention_expires_at:string;created_at:string;version:number;pinned_at?:string|null};
type MemoryEvent={id:string;event_type:string;details:Record<string,unknown>;created_at:string};
type KnowledgeHit={source_id:string;source_version:number;chunk_id:string;content:string;content_sha256:string;source_location:Record<string,unknown>;sensitivity:string;retrieval_method:"vector"|"keyword"|"hybrid";score:number;provider_id?:string|null;model_id?:string|null;model_version?:string|null;index_generation?:string|null};
type Props={apiBase:string;agentId:string;getAccessToken:()=>Promise<string>;onBack:()=>void};

const TYPES:PolicyMemoryType[]=["conversation","working","episodic","semantic","procedural","long_term"];
const LABELS:Record<PolicyMemoryType,string>={conversation:"Conversation",working:"Working",episodic:"Episodic",semantic:"Semantic",procedural:"Procedural",long_term:"Long-term"};
const PURPOSES=["agent_generation_context","agent_runtime_context","workflow_context","personalization_context"];
const SENSITIVITIES=["public","internal"];

export function AgentMemoryCenter({apiBase,agentId,getAccessToken,onBack}:Props){
 const [policies,setPolicies]=useState<MemoryPolicy[]>([]);
 const [items,setItems]=useState<MemoryItem[]>([]);
 const [events,setEvents]=useState<MemoryEvent[]>([]);
 const [loading,setLoading]=useState(true);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [notice,setNotice]=useState("");
 const [proposal,setProposal]=useState("");
 const [query,setQuery]=useState("");
 const [retrieved,setRetrieved]=useState<MemoryItem[]>([]);
 const [knowledgeQuery,setKnowledgeQuery]=useState("");
 const [knowledgeHits,setKnowledgeHits]=useState<KnowledgeHit[]>([]);
 const [knowledgeTrace,setKnowledgeTrace]=useState("");
 const [knowledgeBusy,setKnowledgeBusy]=useState(false);
 const [knowledgeError,setKnowledgeError]=useState("");
 const [correcting,setCorrecting]=useState<Record<string,string>>({});

 const request=useCallback(async(path:string,init:RequestInit={})=>{
  const token=await getAccessToken();
  const headers=new Headers(init.headers);
  headers.set("Authorization","Bearer "+token);headers.set("Accept","application/json");
  if(init.body&&!headers.has("Content-Type"))headers.set("Content-Type","application/json");
  const response=await fetch(apiBase+path,{...init,headers,cache:"no-store"});
  const body=response.status===204?null:await response.json().catch(()=>null);
  if(!response.ok)throw new Error(body?.detail?.message||body?.error?.message||"Memory request gagal ("+response.status+").");
  return body;
 },[apiBase,getAccessToken]);

 const load=useCallback(async()=>{
  setLoading(true);setError("");
  try{
   const suffix="?agent_id="+encodeURIComponent(agentId);
   const [policyBody,itemBody,eventBody]=await Promise.all([
    request("/v1/memory/policies"+suffix),
    request("/v1/memory/items"+suffix+"&limit=100"),
    request("/v1/memory/events"+suffix+"&limit=50"),
   ]);
   setPolicies(Array.isArray(policyBody?.items)?policyBody.items:[]);
   setItems(Array.isArray(itemBody?.items)?itemBody.items:[]);
   setEvents(Array.isArray(eventBody?.items)?eventBody.items:[]);
  }catch(cause){setError(cause instanceof Error?cause.message:"Memory tidak dapat dimuat.");}
  finally{setLoading(false);}
 },[agentId,request]);

 useEffect(()=>{void load();},[load]);

 async function savePolicy(type:PolicyMemoryType,enabled:boolean){
  const existing=policies.find(item=>item.memory_type===type);
  setBusy(true);setError("");setNotice("");
  try{
   await request("/v1/memory/policies/"+type,{method:"PUT",body:JSON.stringify({
    agent_id:agentId,enabled,consent_version:enabled?"allpha.memory.v1":null,
    allowed_purposes:enabled?PURPOSES:[],allowed_sensitivities:enabled?(type==="conversation"?["restricted"]:SENSITIVITIES):[],
    retention_days:existing?.retention_days??(type==="working"?1:30),
   })});
   setNotice(enabled?LABELS[type]+" Memory aktif dengan persetujuan eksplisit.":"Persetujuan "+LABELS[type]+" Memory dicabut; retrieval dibatasi.");
   await load();
  }catch(cause){setError(cause instanceof Error?cause.message:"Kebijakan Memory gagal disimpan.");}
  finally{setBusy(false);}
 }

 async function createProposal(){
  const value=proposal.trim();if(!value)return;
  setBusy(true);setError("");setNotice("");
  try{
   await request("/v1/memory/proposals",{method:"POST",body:JSON.stringify({
    agent_id:agentId,memory_type:"long_term",purpose:"agent_runtime_context",
    classification:"internal",content:value,source_ref:{kind:"owner_manual_native"},
    provenance:{created_by:"owner",capture_mode:"explicit_owner_action"},confidence:1,retention_days:30,
   })});
   setProposal("");setNotice("Usulan Memory tersimpan dan menunggu persetujuan pemilik.");await load();
  }catch(cause){setError(cause instanceof Error?cause.message:"Usulan Memory gagal disimpan.");}
  finally{setBusy(false);}
 }

 async function decide(item:MemoryItem,decision:"approve"|"reject"){
  setBusy(true);setError("");setNotice("");
  try{
   await request("/v1/memory/items/"+encodeURIComponent(item.id)+"/decision",{method:"POST",body:JSON.stringify({decision})});
   setNotice(decision==="approve"?"Memory disetujui dan dapat dipakai sesuai policy.":"Usulan Memory ditolak.");
   await load();
  }catch(cause){setError(cause instanceof Error?cause.message:"Keputusan Memory gagal.");}
  finally{setBusy(false);}
 }

 async function correct(item:MemoryItem){
  const value=(correcting[item.id]||"").trim();if(!value)return;
  setBusy(true);setError("");setNotice("");
  try{
   await request("/v1/memory/items/"+encodeURIComponent(item.id),{method:"PATCH",body:JSON.stringify({content:value})});
   setCorrecting(current=>({...current,[item.id]:""}));setNotice("Memory diperbarui dengan versi baru.");await load();
  }catch(cause){setError(cause instanceof Error?cause.message:"Koreksi Memory gagal.");}
  finally{setBusy(false);}
 }

 async function remove(item:MemoryItem){
  setBusy(true);setError("");setNotice("");
  try{
   await request("/v1/memory/items/"+encodeURIComponent(item.id),{method:"DELETE"});
   setNotice("Memory dihapus dan retrieval access dicabut.");await load();
  }catch(cause){setError(cause instanceof Error?cause.message:"Memory gagal dihapus.");}
  finally{setBusy(false);}
 }
 async function pin(item:MemoryItem,pinned:boolean){
  setBusy(true);setError("");setNotice("");
  try{
   await request("/v1/memory/items/"+encodeURIComponent(item.id)+"/pin",{method:"POST",body:JSON.stringify({pinned})});
   setNotice(pinned?"Memory disematkan; retensi tetap berjalan.":"Sematan Memory dilepas.");await load();
  }catch(cause){setError(cause instanceof Error?cause.message:"Perubahan pin gagal.");}
  finally{setBusy(false);}
 }

 function expireItem(item:MemoryItem){
  Alert.alert("Expire Memory","Konten privat akan dikosongkan sekarang dan tidak dapat dipulihkan. Audit event tetap disimpan.",[
   {text:"Batal",style:"cancel"},
   {text:"Expire sekarang",style:"destructive",onPress:()=>{void (async()=>{
    setBusy(true);setError("");setNotice("");
    try{
     await request("/v1/memory/items/"+encodeURIComponent(item.id)+"/expire",{method:"POST"});
     setNotice("Memory di-expire; konten dikosongkan dan audit dipertahankan.");await load();
    }catch(cause){setError(cause instanceof Error?cause.message:"Expiry Memory gagal.");}
    finally{setBusy(false);}
   })();}},
  ]);
 }


 async function retrieveKnowledge(){
  const value=knowledgeQuery.trim();if(!value)return;
  setKnowledgeBusy(true);setKnowledgeError("");setKnowledgeHits([]);setKnowledgeTrace("");
  try{
   const body=await request("/v1/agents/"+encodeURIComponent(agentId)+"/knowledge/retrieve",{
    method:"POST",body:JSON.stringify({query:value,limit:12}),
   });
   setKnowledgeHits(Array.isArray(body?.results)?body.results:[]);
   setKnowledgeTrace(typeof body?.trace_id==="string"?body.trace_id:"");
  }catch(cause){
   setKnowledgeError(cause instanceof Error?cause.message:"Knowledge retrieval belum tersedia.");
  }finally{setKnowledgeBusy(false);}
 }

 async function retrieve(){
  setBusy(true);setError("");setRetrieved([]);
  try{
   const body=await request("/v1/memory/context",{method:"POST",body:JSON.stringify({
    agent_id:agentId,purpose:"agent_runtime_context",query:query.trim()||null,
    max_sensitivity:"internal",limit:12,
   })});
   setRetrieved(Array.isArray(body?.items)?body.items:[]);
  }catch(cause){setError(cause instanceof Error?cause.message:"Preview retrieval gagal.");}
  finally{setBusy(false);}
 }

 const card={backgroundColor:"#151D31",borderColor:"#34405D",borderWidth:1,borderRadius:14,padding:14,marginBottom:10} as const;
 const field={backgroundColor:"#0E1628",borderColor:"#3A4663",borderWidth:1,borderRadius:10,padding:11,color:"#FFFFFF",marginTop:7} as const;
 const button=(label:string,onPress:()=>void,disabled=false,danger=false)=>(
  <Pressable accessibilityRole="button" accessibilityState={{disabled}} disabled={disabled} onPress={onPress}
   style={{backgroundColor:danger?"#7F2940":"#2B4778",borderRadius:10,paddingVertical:10,paddingHorizontal:13,opacity:disabled?0.5:1,alignSelf:"flex-start"}}>
   <Text style={{color:"#FFFFFF",fontWeight:"700"}}>{label}</Text>
  </Pressable>
 );

 return <ScrollView style={{flex:1,backgroundColor:"#0B1020"}} contentContainerStyle={{padding:16,paddingBottom:36}}>
  <View style={{flexDirection:"row",alignItems:"center",justifyContent:"space-between",marginBottom:14}}>
   <View style={{flex:1,marginRight:12}}><Text style={{color:"#7DD3FC",fontSize:11,fontWeight:"800",letterSpacing:1.5}}>AGENT STUDIO · MEMORY</Text><Text style={{color:"#FFFFFF",fontSize:22,fontWeight:"800",marginTop:4}}>Memory Center</Text><Text style={{color:"#9AA7C1",fontSize:12,marginTop:4}}>Owner-private · Agent {agentId.slice(0,8)}…</Text></View>
   {button("Kembali",onBack,busy)}
  </View>
  <View style={card}>
   <Text style={{color:"#FFFFFF",fontWeight:"800",fontSize:15}}>Persetujuan dan retensi</Text>
   <Text style={{color:"#AAB5CA",fontSize:12,lineHeight:18,marginTop:6}}>Memory hanya dipakai setelah pemilik mengaktifkan kelasnya. Conversation membaca pesan dari Messaging kanonis, read-only, tidak disalin ke Memory items, dan memerlukan consent Restricted. Usulan persistent Memory tetap menunggu persetujuan; Working Memory dibatasi satu hari.</Text>
   {TYPES.map(type=>{
    const policy=policies.find(item=>item.memory_type===type);
    const enabled=policy?.enabled===true&&!policy.consent_revoked_at;
    return <View key={type} style={{borderTopWidth:1,borderTopColor:"#303B56",paddingTop:10,marginTop:10,flexDirection:"row",alignItems:"center",justifyContent:"space-between"}}>
     <View style={{flex:1,marginRight:12}}><Text style={{color:"#FFFFFF",fontWeight:"700"}}>{LABELS[type]} Memory</Text><Text style={{color:"#91A0BA",fontSize:11,marginTop:3}}>{enabled?"Aktif · policy v"+policy?.policy_version:"Nonaktif · belum ada consent aktif"}</Text></View>
     {button(enabled?"Cabut consent":"Setujui & aktifkan",()=>void savePolicy(type,!enabled),busy,!enabled)}
    </View>;
   })}
  </View>
  <View style={card}>
   <Text style={{color:"#FFFFFF",fontWeight:"800",fontSize:15}}>Usulan Memory manual</Text>
   <Text style={{color:"#AAB5CA",fontSize:12,marginTop:5}}>Teks yang Anda masukkan menjadi proposal Long-term dengan klasifikasi internal dan retensi maksimal 30 hari. Persetujuan tetap diperlukan.</Text>
   <TextInput value={proposal} onChangeText={setProposal} multiline maxLength={8000} placeholder="Contoh: Agent perlu menggunakan format ringkasan dengan poin-poin..." placeholderTextColor="#72809A" style={[field,{minHeight:82,textAlignVertical:"top"}]}/>
   <View style={{marginTop:10}}>{button("Ajukan Memory",()=>void createProposal(),busy||!proposal.trim())}</View>
  </View>
  <View style={card}>
   <View style={{flexDirection:"row",justifyContent:"space-between",alignItems:"center"}}><Text style={{color:"#FFFFFF",fontWeight:"800",fontSize:15}}>Items & proposals</Text>{button("Refresh",()=>void load(),busy)}</View>
   {loading?<ActivityIndicator color="#7DD3FC" style={{margin:16}}/>:items.length===0?<Text style={{color:"#91A0BA",fontSize:12,marginTop:12}}>Belum ada Memory untuk Agent ini.</Text>:items.map(item=><View key={item.id} style={{borderTopWidth:1,borderTopColor:"#303B56",paddingTop:11,marginTop:11}}>
    <Text style={{color:"#FFFFFF",fontWeight:"700"}}>{LABELS[item.memory_type]} · {item.status} · {item.classification}{item.pinned_at?" · Disematkan":""}</Text>
    <Text style={{color:"#C7D0E0",fontSize:13,lineHeight:19,marginTop:6}}>{item.content||"(konten sudah dihapus sesuai retensi)"}</Text>
    <Text style={{color:"#8190AA",fontSize:10,marginTop:5}}>Versi {item.version} · Retensi {new Date(item.retention_expires_at).toLocaleDateString("id-ID")}</Text>
    {item.status==="pending"&&<View style={{flexDirection:"row",gap:8,marginTop:9}}>{button("Setujui",()=>void decide(item,"approve"),busy)}{button("Tolak",()=>void decide(item,"reject"),busy,true)}</View>}
    {item.status==="active"&&<><TextInput value={correcting[item.id]??item.content} onChangeText={value=>setCorrecting(current=>({...current,[item.id]:value}))} multiline maxLength={8000} style={[field,{minHeight:64,textAlignVertical:"top"}]}/><View style={{flexDirection:"row",gap:8,marginTop:9,flexWrap:"wrap"}}>{button(item.pinned_at?"Lepas pin":"Sematkan",()=>void pin(item,!item.pinned_at),busy)}{button("Expire sekarang",()=>expireItem(item),busy,true)}{button("Simpan koreksi",()=>void correct(item),busy)}{button("Hapus",()=>void remove(item),busy,true)}</View></>}
   </View>)}
  </View>
  <View style={card}>
   <Text style={{color:"#FFFFFF",fontWeight:"800",fontSize:15}}>Retrieval preview</Text>
   <Text style={{color:"#AAB5CA",fontSize:12,marginTop:5}}>Preview hanya mencari Memory aktif dalam Agent dan batas sensitivitas internal.</Text>
   <TextInput value={query} onChangeText={setQuery} placeholder="Cari konteks Memory..." placeholderTextColor="#72809A" style={field}/>
   <View style={{marginTop:10}}>{button("Cari Memory",()=>void retrieve(),busy)}</View>
   {retrieved.map(item=><Text key={item.id} style={{color:"#C7D0E0",fontSize:12,lineHeight:18,marginTop:10}}>{item.content}</Text>)}
  </View>

  <View style={card}>
   <Text style={{color:"#FFFFFF",fontWeight:"800",fontSize:15}}>Knowledge & RAG · Agent context</Text>
   <Text style={{color:"#AAB5CA",fontSize:12,lineHeight:18,marginTop:5}}>Pencarian memakai endpoint Knowledge FastAPI yang sama dengan Web. Owner, Agent, source scope, sensitivitas dan consent ditentukan ulang oleh server; aplikasi tidak mengirim owner ID atau izin sensitivitas.</Text>
   <TextInput value={knowledgeQuery} onChangeText={setKnowledgeQuery} multiline maxLength={4000} placeholder="Cari konteks dari dokumen Agent..." placeholderTextColor="#72809A" style={[field,{minHeight:72,textAlignVertical:"top"}]}/>
   <View style={{marginTop:10}}>{button(knowledgeBusy?"Mengambil konteks...":"Cari Knowledge",()=>void retrieveKnowledge(),knowledgeBusy||!knowledgeQuery.trim())}</View>
   {!!knowledgeError&&<Text accessibilityRole="alert" style={{color:"#FDA4AF",fontSize:12,marginTop:10}}>{knowledgeError} Tidak ada hasil contoh yang ditampilkan; retrieval tetap tertutup jika consent, source grant atau index belum tersedia.</Text>}
   {!!knowledgeTrace&&<Text style={{color:"#8190AA",fontSize:10,marginTop:9}}>Trace {knowledgeTrace}</Text>}
   {knowledgeHits.length===0&&!knowledgeBusy&&!knowledgeError&&!!knowledgeTrace&&<Text style={{color:"#91A0BA",fontSize:12,marginTop:8}}>Tidak ada potongan yang diizinkan untuk query ini.</Text>}
   {knowledgeHits.map((hit,index)=><View key={hit.chunk_id} style={{borderTopWidth:1,borderTopColor:"#303B56",paddingTop:10,marginTop:10}}>
    <Text style={{color:"#FFFFFF",fontWeight:"700"}}>Citation {index+1} · source {hit.source_id} · v{hit.source_version}</Text>
    <Text style={{color:"#91A0BA",fontSize:10,marginTop:4}}>{hit.retrieval_method} · {hit.sensitivity} · score {Number.isFinite(hit.score)?hit.score.toFixed(3):"—"}</Text>
    <Text style={{color:"#C7D0E0",fontSize:12,lineHeight:18,marginTop:7}}>{hit.content}</Text>
    <Text style={{color:"#8190AA",fontSize:10,marginTop:5}}>Chunk {hit.chunk_id} · SHA-256 {hit.content_sha256}</Text>
    <Text style={{color:"#8190AA",fontSize:10,marginTop:3}}>Lokasi {JSON.stringify(hit.source_location)}</Text>
    {(hit.provider_id||hit.model_id||hit.model_version||hit.index_generation)&&<Text style={{color:"#8190AA",fontSize:10,marginTop:3}}>Index { [hit.provider_id,hit.model_id,hit.model_version,hit.index_generation].filter(Boolean).join(" · ") }</Text>}
   </View>)}
  </View>
  <View style={card}>
   <Text style={{color:"#FFFFFF",fontWeight:"800",fontSize:15}}>Audit events</Text>
   {events.slice(0,12).map(event=><View key={event.id} style={{borderTopWidth:1,borderTopColor:"#303B56",paddingTop:8,marginTop:8}}><Text style={{color:"#C7D0E0",fontSize:12}}>{event.event_type}</Text><Text style={{color:"#8190AA",fontSize:10,marginTop:3}}>{new Date(event.created_at).toLocaleString("id-ID")}</Text></View>)}
  </View>
  {!!error&&<Text accessibilityRole="alert" style={{color:"#FDA4AF",marginBottom:10}}>{error}</Text>}
  {!!notice&&<Text style={{color:"#86EFAC",marginBottom:10}}>{notice}</Text>}
 </ScrollView>;
}

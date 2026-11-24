import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, TextInput, View } from "react-native";

type MemoryType="working"|"episodic"|"semantic"|"procedural"|"long_term";
type MemoryPolicy={id:string;memory_type:MemoryType;enabled:boolean;consent_version?:string|null;allowed_purposes:string[];allowed_sensitivities:string[];retention_days:number;policy_version:number;consent_revoked_at?:string|null};
type MemoryItem={id:string;memory_type:MemoryType;purpose:string;classification:string;content:string;status:string;confidence?:number|null;retention_expires_at:string;created_at:string;version:number};
type MemoryEvent={id:string;event_type:string;details:Record<string,unknown>;created_at:string};
type Props={apiBase:string;agentId:string;getAccessToken:()=>Promise<string>;onBack:()=>void};

const TYPES:MemoryType[]=["working","episodic","semantic","procedural","long_term"];
const LABELS:Record<MemoryType,string>={working:"Working",episodic:"Episodic",semantic:"Semantic",procedural:"Procedural",long_term:"Long-term"};
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

 async function savePolicy(type:MemoryType,enabled:boolean){
  const existing=policies.find(item=>item.memory_type===type);
  setBusy(true);setError("");setNotice("");
  try{
   await request("/v1/memory/policies/"+type,{method:"PUT",body:JSON.stringify({
    agent_id:agentId,enabled,consent_version:enabled?"allpha.memory.v1":null,
    allowed_purposes:enabled?PURPOSES:[],allowed_sensitivities:enabled?SENSITIVITIES:[],
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
   <Text style={{color:"#AAB5CA",fontSize:12,lineHeight:18,marginTop:6}}>Memory hanya disimpan setelah pemilik mengaktifkan kelasnya. Usulan tetap menunggu persetujuan. Pencabutan consent langsung membatasi retrieval; Working Memory dibatasi satu hari.</Text>
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
    <Text style={{color:"#FFFFFF",fontWeight:"700"}}>{LABELS[item.memory_type]} · {item.status} · {item.classification}</Text>
    <Text style={{color:"#C7D0E0",fontSize:13,lineHeight:19,marginTop:6}}>{item.content||"(konten sudah dihapus sesuai retensi)"}</Text>
    <Text style={{color:"#8190AA",fontSize:10,marginTop:5}}>Versi {item.version} · Retensi {new Date(item.retention_expires_at).toLocaleDateString("id-ID")}</Text>
    {item.status==="pending"&&<View style={{flexDirection:"row",gap:8,marginTop:9}}>{button("Setujui",()=>void decide(item,"approve"),busy)}{button("Tolak",()=>void decide(item,"reject"),busy,true)}</View>}
    {item.status==="active"&&<><TextInput value={correcting[item.id]??item.content} onChangeText={value=>setCorrecting(current=>({...current,[item.id]:value}))} multiline maxLength={8000} style={[field,{minHeight:64,textAlignVertical:"top"}]}/><View style={{flexDirection:"row",gap:8,marginTop:9}}>{button("Simpan koreksi",()=>void correct(item),busy)}{button("Hapus",()=>void remove(item),busy,true)}</View></>}
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
   <Text style={{color:"#FFFFFF",fontWeight:"800",fontSize:15}}>Audit events</Text>
   {events.slice(0,12).map(event=><View key={event.id} style={{borderTopWidth:1,borderTopColor:"#303B56",paddingTop:8,marginTop:8}}><Text style={{color:"#C7D0E0",fontSize:12}}>{event.event_type}</Text><Text style={{color:"#8190AA",fontSize:10,marginTop:3}}>{new Date(event.created_at).toLocaleString("id-ID")}</Text></View>)}
  </View>
  {!!error&&<Text accessibilityRole="alert" style={{color:"#FDA4AF",marginBottom:10}}>{error}</Text>}
  {!!notice&&<Text style={{color:"#86EFAC",marginBottom:10}}>{notice}</Text>}
 </ScrollView>;
}

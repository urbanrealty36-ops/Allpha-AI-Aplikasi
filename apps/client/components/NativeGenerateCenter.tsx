import React, { useEffect, useState } from "react";
import { ActivityIndicator, Alert, Pressable, ScrollView, Text, TextInput, View } from "react-native";

type Agent = { id: string; display_name: string; status: string };
type Skill = { id: string; name: string; status: string; version: number };
type Capability = { capability_key: string; status: string };
type Job = { status: string; artifact_available?: boolean; error_code?: string | null };

export function NativeGenerateCenter({ apiBase, getAccessToken }: { apiBase: string; getAccessToken: () => Promise<string> }) {
  const [agents,setAgents]=useState<Agent[]>([]);
  const [skills,setSkills]=useState<Skill[]>([]);
  const [capabilities,setCapabilities]=useState<Capability[]>([]);
  const [agentId,setAgentId]=useState("");
  const [skillId,setSkillId]=useState("");
  const [capabilityId,setCapabilityId]=useState("");
  const [prompt,setPrompt]=useState("");
  const [busy,setBusy]=useState(false);
  const [loading,setLoading]=useState(true);
  const [jobId,setJobId]=useState("");
  const [result,setResult]=useState("");
  const [notice,setNotice]=useState("");
  const [error,setError]=useState("");

  async function api(path:string, token:string, init:RequestInit={}) {
    const response=await fetch(apiBase+path,{...init,headers:{
      Authorization:"Bearer "+token,Accept:"application/json",
      ...(init.body?{"Content-Type":"application/json"}:{}),...(init.headers||{}),
    },cache:"no-store"});
    const body=await response.json().catch(()=>({}));
    if(!response.ok) throw new Error(body?.detail?.message||body?.error?.message||"Permintaan generation gagal.");
    return body;
  }

  useEffect(()=>{
    let active=true;
    void (async()=>{
      try {
        const token=await getAccessToken();
        const data=await api("/v1/agents",token);
        const items=(data.items||[]).filter((item:Agent)=>item.status==="active");
        if(active){setAgents(items);if(items.length)setAgentId(items[0].id);}
        if(!items.length&&active)setNotice("Belum ada Agent aktif yang dapat digunakan.");
      } catch(cause){if(active)setError(cause instanceof Error?cause.message:"Agent tidak dapat dimuat.");}
      finally{if(active)setLoading(false);}
    })();
    return ()=>{active=false;};
  },[apiBase,getAccessToken]);

  useEffect(()=>{
    if(!agentId)return;
    let active=true;
    setSkills([]);setCapabilities([]);setSkillId("");setCapabilityId("");
    void (async()=>{
      try{
        const token=await getAccessToken();
        const [skillData,capData]=await Promise.all([
          api("/v1/agents/"+encodeURIComponent(agentId)+"/skills",token),
          api("/v1/agents/"+encodeURIComponent(agentId)+"/capabilities",token),
        ]);
        const nextSkills=(skillData.items||[]).filter((x:Skill)=>x.status==="published");
        const nextCaps=(capData.items||[]).filter((x:Capability)=>x.status==="approved");
        if(active){setSkills(nextSkills);setCapabilities(nextCaps);if(nextSkills[0])setSkillId(nextSkills[0].id);if(nextCaps[0])setCapabilityId(nextCaps[0].capability_key);}
      }catch(cause){if(active)setError(cause instanceof Error?cause.message:"Skill dan capability tidak dapat dimuat.");}
    })();
    return ()=>{active=false;};
  },[agentId,getAccessToken,apiBase]);

  async function runGeneration(){
    if(!agentId||!skillId||!capabilityId||!prompt.trim()||busy)return;
    setBusy(true);setError("");setNotice("");setResult("");setJobId("");
    try{
      const token=await getAccessToken();
      const body={agent_id:agentId,skill_id:skillId,capability_id:capabilityId,prompt:prompt.trim(),max_output_tokens:1800};
      const quote=await api("/v1/generation/quote",token,{method:"POST",body:JSON.stringify(body)});
      if(!quote.quote_id||Date.parse(quote.expires_at)<=Date.now()||!Number.isSafeInteger(quote.estimated_credits)||quote.estimated_credits<=0)throw new Error("Quote tidak valid atau telah kedaluwarsa.");
      Alert.alert("Konfirmasi AI Credits","Estimasi "+quote.estimated_credits.toLocaleString("id-ID")+" AI Credits · "+quote.model_id,[
        {text:"Batal",style:"cancel",onPress:()=>{setNotice("Dibatalkan sebelum reservasi. Tidak ada kredit yang dipotong.");setBusy(false);}},
        {text:"Lanjutkan",onPress:()=>{void createAndPoll(token,body,quote);}},
      ]);
    }catch(cause){setError(cause instanceof Error?cause.message:"Generation belum dapat dimulai.");setBusy(false);}
  }

  async function createAndPoll(token:string,body:Record<string,unknown>,quote:Record<string,any>){
    try{
      const created=await api("/v1/generation/jobs",token,{method:"POST",headers:{"Idempotency-Key":createNativeId()},body:JSON.stringify({...body,quoted_credits:quote.estimated_credits,quoted_policy_version:quote.policy_version,quoted_tariff_version:quote.tariff_version,quoted_model_id:quote.model_id})});
      if(!created.job_id)throw new Error("Generation Job belum terkonfirmasi.");
      setJobId(created.job_id);
      for(let attempt=0;attempt<60;attempt++){
        await new Promise(resolve=>setTimeout(resolve,2000));
        const status=await api("/v1/generation/jobs/"+created.job_id,token);
        const job=status.job as Job|undefined;
        if(!job)throw new Error("Status Generation Job tidak ditemukan.");
        if(job.status==="succeeded"&&job.artifact_available){
          const artifact=await api("/v1/generation/jobs/"+created.job_id+"/artifact",token);
          const response=await fetch(artifact.url,{cache:"no-store"});
          if(!response.ok)throw new Error("Artefak privat tidak dapat diunduh.");
          setResult(await response.text());
          setNotice("Hasil lolos moderasi dan tersimpan sebagai artefak privat.");
          return;
        }
        if(job.status==="pending_reconciliation")throw new Error("Hasil masih dalam rekonsiliasi. Tidak ada pengulangan provider otomatis.");
        if(job.status==="failed"||job.status==="cancelled")throw new Error(job.error_code||"Generation gagal.");
      }
      setNotice("Job masih diproses. Periksa kembali riwayat Generation; permintaan tidak dikirim ulang.");
    }catch(cause){setError(cause instanceof Error?cause.message:"Generation tidak selesai.");}
    finally{setBusy(false);}
  }

  return <ScrollView contentContainerStyle={{gap:14,paddingBottom:30}}>
    <View style={{borderRadius:22,borderWidth:1,borderColor:"#35405C",backgroundColor:"#141B31",padding:16,gap:10}}>
      <Text style={{color:"#A5B4FC",fontSize:11,fontWeight:"900",letterSpacing:1.5}}>ALLPHA CREATOR STUDIO</Text>
      <Text style={{color:"#F8FAFC",fontSize:22,fontWeight:"900"}}>AI Generate</Text>
      <Text style={{color:"#AAB4CC",fontSize:13}}>Pilih Agent aktif, Skill published dan capability approved. AI Credits dihitung oleh API.</Text>
      {loading?<ActivityIndicator color="#A5B4FC"/>:<>
        <Text style={{color:"#E2E8F0",fontWeight:"800"}}>AI Agent</Text>
        {agents.map(agent=><Pressable key={agent.id} onPress={()=>setAgentId(agent.id)} style={{borderWidth:1,borderColor:agentId===agent.id?"#A5B4FC":"#35405C",borderRadius:12,padding:11}}><Text style={{color:"#F8FAFC",fontWeight:"700"}}>{agent.display_name}{agentId===agent.id?"  ✓":""}</Text></Pressable>)}
        <Text style={{color:"#E2E8F0",fontWeight:"800"}}>Skill published</Text>
        {skills.map(skill=><Pressable key={skill.id} onPress={()=>setSkillId(skill.id)} style={{borderWidth:1,borderColor:skillId===skill.id?"#A5B4FC":"#35405C",borderRadius:12,padding:11}}><Text style={{color:"#F8FAFC"}}>{skill.name} · v{skill.version}{skillId===skill.id?"  ✓":""}</Text></Pressable>)}
        <Text style={{color:"#E2E8F0",fontWeight:"800"}}>Capability approved</Text>
        {capabilities.map(cap=><Pressable key={cap.capability_key} onPress={()=>setCapabilityId(cap.capability_key)} style={{borderWidth:1,borderColor:capabilityId===cap.capability_key?"#A5B4FC":"#35405C",borderRadius:12,padding:11}}><Text style={{color:"#F8FAFC"}}>{cap.capability_key}{capabilityId===cap.capability_key?"  ✓":""}</Text></Pressable>)}
        <TextInput accessibilityLabel="Instruksi generation" value={prompt} onChangeText={setPrompt} multiline maxLength={32768} placeholder="Jelaskan konten yang ingin dibuat…" placeholderTextColor="#8490AA" style={{minHeight:130,borderRadius:14,borderWidth:1,borderColor:"#35405C",padding:12,color:"#F8FAFC",textAlignVertical:"top"}}/>
        <Pressable disabled={busy||!skillId||!capabilityId||!prompt.trim()} onPress={()=>void runGeneration()} style={{borderRadius:999,backgroundColor:"#A5B4FC",padding:14,alignItems:"center",opacity:busy||!skillId||!capabilityId||!prompt.trim()?0.5:1}}><Text style={{color:"#111827",fontWeight:"900"}}>{busy?"Memproses…":"Minta Quote & Generate"}</Text></Pressable>
      </>}
      {!!jobId&&<Text style={{color:"#CBD5E1",fontSize:11}}>Job: {jobId}</Text>}
      {!!notice&&<Text style={{color:"#86EFAC",fontSize:12}}>{notice}</Text>}
      {!!error&&<Text accessibilityRole="alert" style={{color:"#FCA5A5",fontSize:12}}>{error}</Text>}
    </View>
    {!!result&&<View style={{borderRadius:22,borderWidth:1,borderColor:"#35405C",backgroundColor:"#141B31",padding:16,gap:10}}><Text style={{color:"#A5B4FC",fontWeight:"900"}}>HASIL GENERATION · PRIVATE</Text><Text selectable style={{color:"#F8FAFC",fontSize:14,lineHeight:21}}>{result}</Text></View>}
  </ScrollView>;
}

function createNativeId() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, token => {
    const random = Math.floor(Math.random() * 16);
    return (token === "x" ? random : (random & 3) | 8).toString(16);
  });
}

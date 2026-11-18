import React, { useEffect, useState } from "react";
import { ActivityIndicator, Alert, Pressable, ScrollView, Text, TextInput, View } from "react-native";

type Agent = { id: string; display_name: string; status: string };
type Skill = { id: string; name: string; status: string; version: number };
type Capability = { capability_key: string; status: string };
type ToolContract = { key: string; description: string; input_schema: { properties?: Record<string, { type?: string }>; required?: string[] } };
type ExternalAgent = { agent: Agent; skill: Skill; capabilities: Capability[]; consumer_grant_id: string; granted_scopes: string[]; tool_contracts?: ToolContract[] };
type Job = { status: string; moderation_status?: string | null; artifact_available?: boolean; artifact_deletion_status?: "available" | "pending" | "deleted" | "dead" | "unavailable"; error_code?: string | null; owner_reward_status?: string | null };

export function NativeGenerateCenter({ apiBase, getAccessToken, initialJobId = null }: { apiBase: string; getAccessToken: () => Promise<string>; initialJobId?: string | null }) {
  const [agents,setAgents]=useState<Agent[]>([]);
  const [externalAgents,setExternalAgents]=useState<ExternalAgent[]>([]);
  const [consumerGrantId,setConsumerGrantId]=useState("");
  const [skills,setSkills]=useState<Skill[]>([]);
  const [capabilities,setCapabilities]=useState<Capability[]>([]);
  const [agentId,setAgentId]=useState("");
  const [skillId,setSkillId]=useState("");
  const [capabilityId,setCapabilityId]=useState("");
  const [prompt,setPrompt]=useState("");
  const [knowledgeQuery,setKnowledgeQuery]=useState("");
  const [toolInputsJson,setToolInputsJson]=useState("{}");
  const [busy,setBusy]=useState(false);
  const [canCancelGeneration,setCanCancelGeneration]=useState(false);
  const [deletingArtifact,setDeletingArtifact]=useState(false);
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
        let shared:ExternalAgent[]=[];
        try{
          const sharedData=await api("/v1/generation/agents",token);
          shared=(sharedData.items||[]).filter((item:ExternalAgent)=>item.agent?.status==="active"&&item.skill?.status==="published"&&!!item.consumer_grant_id);
        }catch{/* Own-Agent generation remains available when the optional grant catalog is unavailable. */}
        if(active){setAgents(items);setExternalAgents(shared);if(items.length)setAgentId(items[0].id);}
        if(!items.length&&!shared.length&&active)setNotice("Belum ada Agent milik Anda atau Agent eksternal yang memberikan grant generation.");
      } catch(cause){if(active)setError(cause instanceof Error?cause.message:"Agent tidak dapat dimuat.");}
      finally{if(active)setLoading(false);}
    })();
    return ()=>{active=false;};
  },[apiBase,getAccessToken]);

  useEffect(()=>{
    if(!agentId)return;
    let active=true;
    setSkills([]);setCapabilities([]);setSkillId("");setCapabilityId("");
    if(consumerGrantId){
      const shared=externalAgents.find(item=>item.consumer_grant_id===consumerGrantId&&item.agent.id===agentId);
      if(!shared){setError("Grant Agent eksternal tidak lagi tersedia.");return()=>{active=false;};}
      const approved=shared.capabilities.filter(item=>item.status==="approved");
      setSkills([shared.skill]);setCapabilities(approved);setSkillId(shared.skill.id);setCapabilityId(approved[0]?.capability_key||"");
      if(!approved.length)setError("Agent eksternal belum memiliki capability approved.");
      return()=>{active=false;};
    }
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
  },[agentId,consumerGrantId,externalAgents,getAccessToken,apiBase]);

  useEffect(()=>{
    if(!initialJobId)return;
    let active=true;
    void (async()=>{
      setBusy(true);setError("");setNotice("");setJobId(initialJobId);
      try{
        const token=await getAccessToken();
        const status=await api("/v1/generation/jobs/"+encodeURIComponent(initialJobId),token);
        const job=status.job as Job|undefined;
        if(!job)throw new Error("Generation Job tidak ditemukan.");
        setCanCancelGeneration(job.status === "queued");
        if(job.artifact_deletion_status==="pending"){
          setNotice("Penghapusan artefak sedang diproses. Akses file telah dinonaktifkan.");
          return;
        }
        if(job.artifact_deletion_status==="deleted"){
          setNotice("Artefak privat ini sudah dihapus oleh pemiliknya.");
          return;
        }
        if(job.artifact_deletion_status==="dead"){
          setNotice("Penghapusan artefak membutuhkan pemulihan operator. Artefak tetap privat; hubungi dukungan Allpha.");
          return;
        }
        if(job.status==="pending_reconciliation"&&job.moderation_status==="review_required"){
          setNotice("Output generation sedang menunggu pemeriksaan Human. Artefak tetap privat sampai reviewer menyetujui; jangan kirim ulang permintaan ini.");
          return;
        }
        if(job.status==="pending_reconciliation"){
          setNotice("Status provider atau settlement belum dapat dipastikan. Job masuk rekonsiliasi; jangan kirim ulang permintaan ini.");
          return;
        }
        if(job.status!=="succeeded"||!job.artifact_available){
          setNotice("Generation Job belum memiliki artefak yang dapat dibuka ("+job.status+").");
          return;
        }
        const artifact=await api("/v1/generation/jobs/"+encodeURIComponent(initialJobId)+"/artifact",token);
        if(!artifact.url)throw new Error("Referensi artefak privat belum tersedia.");
        const response=await fetch(artifact.url,{cache:"no-store"});
        if(!response.ok)throw new Error("Unduhan artefak privat gagal.");
        const output=await response.text();
        if(active){
          setResult(output);
          setNotice("Artefak privat dibuka dari DM. Creator reward: "+(job.owner_reward_status||"pending_policy")+".");
        }
      }catch(cause){if(active)setError(cause instanceof Error?cause.message:"Artefak privat tidak dapat dibuka.");}
      finally{if(active)setBusy(false);}
    })();
    return()=>{active=false;};
  },[initialJobId,apiBase,getAccessToken]);

  function cancelQueuedGeneration(){
    if(!jobId||!canCancelGeneration||busy)return;
    Alert.alert("Batalkan antrean Generation","Pembatalan hanya tersedia sebelum worker memanggil provider. Jika policy tidak mengizinkan pelepasan, reservasi akan menunggu rekonsiliasi.",[
      {text:"Kembali",style:"cancel"},
      {text:"Batalkan antrean",style:"destructive",onPress:()=>{void (async()=>{
        setError("");
        try{
          const token=await getAccessToken();
          const result=await api("/v1/generation/jobs/"+encodeURIComponent(jobId)+"/cancel",token,{method:"POST"}) as {status?:string};
          setCanCancelGeneration(false);
          setNotice(result.status==="cancelled"?"Antrean dibatalkan sebelum provider dipanggil. Reservasi dilepas sesuai policy aktif.":"Pembatalan tercatat, tetapi reservasi menunggu rekonsiliasi policy.");
        }catch(cause){setError(cause instanceof Error?cause.message:"Pembatalan antrean belum dapat dikonfirmasi.");}
      })();}},
    ]);
  }

  function requestArtifactDeletion(){
    if(!jobId||!result||deletingArtifact)return;
    Alert.alert(
      "Hapus artefak privat",
      "URL baru akan diblokir. URL sementara yang sudah diterbitkan dapat berlaku sampai 60 detik atau sampai objek Storage dihapus.",
      [
        {text:"Batal",style:"cancel"},
        {text:"Hapus artefak",style:"destructive",onPress:()=>{void (async()=>{
          setDeletingArtifact(true);setError("");
          try{
            const token=await getAccessToken();
            const deleted=await api("/v1/generation/jobs/"+encodeURIComponent(jobId)+"/artifact",token,{
              method:"DELETE",headers:{"Idempotency-Key":createNativeId()},
            }) as {status?:string};
            setResult("");
            setNotice(deleted.status==="succeeded"?"Artefak privat sudah dihapus.":deleted.status==="dead"?"Penghapusan membutuhkan pemulihan operator. Artefak tetap privat.":"Permintaan penghapusan diterima. URL baru diblokir; URL lama berakhir maksimal 60 detik atau saat objek Storage dihapus.");
          }catch(cause){setError(cause instanceof Error?cause.message:"Penghapusan artefak belum dapat dikonfirmasi.");}
          finally{setDeletingArtifact(false);}
        })();}},
      ],
    );
  }

  async function runGeneration(){
    if(!agentId||!skillId||!capabilityId||!prompt.trim()||busy)return;
    setBusy(true);setCanCancelGeneration(false);setError("");setNotice("");setResult("");setJobId("");
    try{
      const token=await getAccessToken();
      const selectedExternal=externalAgents.find(item=>item.consumer_grant_id===consumerGrantId);
      const externalKnowledgeAllowed=!!selectedExternal?.granted_scopes.includes("knowledge_public_read");
      let toolInputs:Record<string,Record<string,unknown>>={};
      if(consumerGrantId&&(selectedExternal?.tool_contracts||[]).length){
        let parsed:unknown;
        try{parsed=JSON.parse(toolInputsJson);}catch{throw new Error("Tool inputs harus berupa JSON object yang valid.");}
        if(!parsed||typeof parsed!=="object"||Array.isArray(parsed))throw new Error("Tool inputs harus berupa JSON object keyed by tool key.");
        toolInputs=parsed as Record<string,Record<string,unknown>>;
      }
      const body={agent_id:agentId,skill_id:skillId,capability_id:capabilityId,prompt:prompt.trim(),max_output_tokens:1800,...(consumerGrantId?{consumer_grant_id:consumerGrantId}:{}),...(Object.keys(toolInputs).length?{tool_inputs:toolInputs}:{}),...((!consumerGrantId||externalKnowledgeAllowed)&&knowledgeQuery.trim()?{knowledge_query:knowledgeQuery.trim()}: {})};
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
      const created=await api("/v1/generation/jobs",token,{method:"POST",headers:{"Idempotency-Key":createNativeId()},body:JSON.stringify({...body,quoted_credits:quote.estimated_credits,quoted_policy_version:quote.policy_version,quoted_tariff_version:quote.tariff_version,quoted_model_id:quote.model_id,quoted_agent_snapshot_sha256:quote.agent_snapshot_sha256,quoted_skill_snapshot_sha256:quote.skill_snapshot_sha256,...(quote.knowledge_context_sha256?{quoted_knowledge_context_sha256:quote.knowledge_context_sha256}:{}),...(quote.tool_inputs_sha256?{quoted_tool_inputs_sha256:quote.tool_inputs_sha256}:{})})});
      if(!created.job_id)throw new Error("Generation Job belum terkonfirmasi.");
      setJobId(created.job_id);
      setCanCancelGeneration(true);
      for(let attempt=0;attempt<60;attempt++){
        await new Promise(resolve=>setTimeout(resolve,2000));
        const status=await api("/v1/generation/jobs/"+created.job_id,token);
        const job=status.job as Job|undefined;
        if(!job)throw new Error("Status Generation Job tidak ditemukan.");
        setCanCancelGeneration(job.status === "queued");
        if(job.status==="succeeded"&&job.artifact_available){
          const artifact=await api("/v1/generation/jobs/"+created.job_id+"/artifact",token);
          const response=await fetch(artifact.url,{cache:"no-store"});
          if(!response.ok)throw new Error("Artefak privat tidak dapat diunduh.");
          setResult(await response.text());
          setNotice("Hasil lolos moderasi dan tersimpan sebagai artefak privat. Creator reward: "+(job.owner_reward_status||"pending_policy")+".");
          return;
        }
        if(job.status==="cancelled"){
          setNotice("Generation dibatalkan sebelum worker memanggil provider. Tidak ada output yang dibuat.");
          return;
        }
        if(job.status==="pending_reconciliation"){
          if(job.moderation_status==="review_required"){
            setNotice("Output sudah diterima dan sedang menunggu pemeriksaan Human. Artefak tetap privat sampai reviewer menyetujui; permintaan tidak dikirim ulang.");
            return;
          }
          if(job.error_code==="cancel_release_policy_not_approved"){
            setNotice("Pembatalan tercatat, tetapi policy belum mengizinkan pelepasan reservasi. Saldo menunggu rekonsiliasi.");
            return;
          }
          throw new Error("Hasil masih dalam rekonsiliasi. Tidak ada pengulangan provider otomatis.");
        }
        if(job.status==="failed")throw new Error(job.error_code||"Generation gagal.");
      }
      setNotice("Job masih diproses. Periksa kembali riwayat Generation; permintaan tidak dikirim ulang.");
    }catch(cause){setError(cause instanceof Error?cause.message:"Generation tidak selesai.");}
    finally{setBusy(false);setCanCancelGeneration(false);}
  }

  return <ScrollView contentContainerStyle={{gap:14,paddingBottom:30}}>
    <View style={{borderRadius:22,borderWidth:1,borderColor:"#35405C",backgroundColor:"#141B31",padding:16,gap:10}}>
      <Text style={{color:"#A5B4FC",fontSize:11,fontWeight:"900",letterSpacing:1.5}}>ALLPHA CREATOR STUDIO</Text>
      <Text style={{color:"#F8FAFC",fontSize:22,fontWeight:"900"}}>AI Generate</Text>
      <Text style={{color:"#AAB4CC",fontSize:13}}>Pilih Agent aktif, Skill published dan capability approved. AI Credits dihitung oleh API.</Text>
      {loading?<ActivityIndicator color="#A5B4FC"/>:<>
        <Text style={{color:"#E2E8F0",fontWeight:"800"}}>AI Agent</Text>
        {agents.map(agent=><Pressable key={agent.id} onPress={()=>{setAgentId(agent.id);setConsumerGrantId("");setKnowledgeQuery("");}} style={{borderWidth:1,borderColor:agentId===agent.id&&!consumerGrantId?"#A5B4FC":"#35405C",borderRadius:12,padding:11}}><Text style={{color:"#F8FAFC",fontWeight:"700"}}>{agent.display_name} · Milik saya{agentId===agent.id&&!consumerGrantId?"  ✓":""}</Text></Pressable>)}
        {externalAgents.map(item=><Pressable key={item.consumer_grant_id} onPress={()=>{setAgentId(item.agent.id);setConsumerGrantId(item.consumer_grant_id);setKnowledgeQuery("");setToolInputsJson(makeToolInputsTemplate(item.tool_contracts||[]));}} style={{borderWidth:1,borderColor:consumerGrantId===item.consumer_grant_id?"#A5B4FC":"#35405C",borderRadius:12,padding:11}}><Text style={{color:"#F8FAFC",fontWeight:"700"}}>{item.agent.display_name} · Grant pemilik{consumerGrantId===item.consumer_grant_id?"  ✓":""}</Text></Pressable>)}
        <Text style={{color:"#E2E8F0",fontWeight:"800"}}>Skill published</Text>
        {skills.map(skill=><Pressable key={skill.id} onPress={()=>setSkillId(skill.id)} style={{borderWidth:1,borderColor:skillId===skill.id?"#A5B4FC":"#35405C",borderRadius:12,padding:11}}><Text style={{color:"#F8FAFC"}}>{skill.name} · v{skill.version}{skillId===skill.id?"  ✓":""}</Text></Pressable>)}
        <Text style={{color:"#E2E8F0",fontWeight:"800"}}>Capability approved</Text>
        {capabilities.map(cap=><Pressable key={cap.capability_key} onPress={()=>setCapabilityId(cap.capability_key)} style={{borderWidth:1,borderColor:capabilityId===cap.capability_key?"#A5B4FC":"#35405C",borderRadius:12,padding:11}}><Text style={{color:"#F8FAFC"}}>{cap.capability_key}{capabilityId===cap.capability_key?"  ✓":""}</Text></Pressable>)}
        <TextInput accessibilityLabel="Instruksi generation" value={prompt} onChangeText={setPrompt} multiline maxLength={32768} placeholder="Jelaskan konten yang ingin dibuat…" placeholderTextColor="#8490AA" style={{minHeight:130,borderRadius:14,borderWidth:1,borderColor:"#35405C",padding:12,color:"#F8FAFC",textAlignVertical:"top"}}/>
        {!!externalAgents.find(item=>item.consumer_grant_id===consumerGrantId)?.tool_contracts?.length&&<>
          <Text style={{color:"#E2E8F0",fontWeight:"800"}}>Typed tool inputs · JSON</Text>
          <Text style={{color:"#AAB4CC",fontSize:12}}>Isi object sesuai kontrak setiap tool. API akan memvalidasi tipe, required fields, permission dan grant sebelum reservasi kredit.</Text>
          {externalAgents.find(item=>item.consumer_grant_id===consumerGrantId)?.tool_contracts?.map(contract=><Text key={contract.key} style={{color:"#CBD5E1",fontSize:11}}>{contract.key}: {contract.description} · schema {JSON.stringify(contract.input_schema)}</Text>)}
          <TextInput accessibilityLabel="Typed tool inputs JSON" value={toolInputsJson} onChangeText={setToolInputsJson} multiline autoCapitalize="none" autoCorrect={false} placeholder='{"text.normalize":{"text":"..."}}' placeholderTextColor="#8490AA" style={{minHeight:150,borderRadius:14,borderWidth:1,borderColor:"#35405C",padding:12,color:"#F8FAFC",textAlignVertical:"top",fontFamily:"monospace"}}/>
        </>}
        <Text style={{color:"#E2E8F0",fontWeight:"800"}}>Knowledge context (opsional)</Text>
        <TextInput accessibilityLabel="Query Knowledge" value={knowledgeQuery} onChangeText={setKnowledgeQuery} editable={!consumerGrantId||!!externalAgents.find(item=>item.consumer_grant_id===consumerGrantId)?.granted_scopes.includes("knowledge_public_read")} multiline maxLength={4000} placeholder={consumerGrantId&&!externalAgents.find(item=>item.consumer_grant_id===consumerGrantId)?.granted_scopes.includes("knowledge_public_read")?"Owner belum memberikan scope Knowledge publik.":"Cari sumber Knowledge yang diizinkan…"} placeholderTextColor="#8490AA" style={{minHeight:74,borderRadius:14,borderWidth:1,borderColor:"#35405C",padding:12,color:"#F8FAFC",textAlignVertical:"top",opacity:consumerGrantId?0.5:1}}/>
        <Pressable disabled={busy||!skillId||!capabilityId||!prompt.trim()} onPress={()=>void runGeneration()} style={{borderRadius:999,backgroundColor:"#A5B4FC",padding:14,alignItems:"center",opacity:busy||!skillId||!capabilityId||!prompt.trim()?0.5:1}}><Text style={{color:"#111827",fontWeight:"900"}}>{busy?"Memproses…":"Minta Quote & Generate"}</Text></Pressable>
      </>}
      {!!jobId&&<Text style={{color:"#CBD5E1",fontSize:11}}>Job: {jobId}</Text>}
      {!!jobId&&canCancelGeneration&&<Pressable accessibilityRole="button" onPress={cancelQueuedGeneration} disabled={busy} style={{borderRadius:999,borderWidth:1,borderColor:"#FDA4AF",padding:12,alignItems:"center",opacity:busy?0.5:1}}><Text style={{color:"#FDA4AF",fontWeight:"900"}}>Batalkan antrean sebelum diproses</Text></Pressable>}
      {!!notice&&<Text style={{color:"#86EFAC",fontSize:12}}>{notice}</Text>}
      {!!error&&<Text accessibilityRole="alert" style={{color:"#FCA5A5",fontSize:12}}>{error}</Text>}
    </View>
    {!!result&&<View style={{borderRadius:22,borderWidth:1,borderColor:"#35405C",backgroundColor:"#141B31",padding:16,gap:10}}><Text style={{color:"#A5B4FC",fontWeight:"900"}}>HASIL GENERATION · PRIVATE</Text><Text selectable style={{color:"#F8FAFC",fontSize:14,lineHeight:21}}>{result}</Text><Pressable disabled={deletingArtifact||busy} onPress={requestArtifactDeletion} style={{borderRadius:12,borderWidth:1,borderColor:"#FDA4AF",padding:12,alignItems:"center",opacity:deletingArtifact||busy?0.5:1}}><Text style={{color:"#FDA4AF",fontWeight:"900"}}>{deletingArtifact?"Menghapus…":"Hapus artefak privat"}</Text></Pressable></View>}
  </ScrollView>;
}

function createNativeId() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, token => {
    const random = Math.floor(Math.random() * 16);
    return (token === "x" ? random : (random & 3) | 8).toString(16);
  });
}


function makeToolInputsTemplate(contracts: ToolContract[]): string {
  const defaultValue = (type?: string): unknown => {
    if (type === "string") return "";
    if (type === "integer" || type === "number") return 1;
    if (type === "boolean") return false;
    if (type === "array") return [];
    if (type === "object") return {};
    return null;
  };
  const value = Object.fromEntries(contracts.map(contract => {
    const properties = contract.input_schema?.properties || {};
    const required = contract.input_schema?.required || [];
    return [contract.key, Object.fromEntries(required.map(key => [key, defaultValue(properties[key]?.type)]))];
  }));
  return JSON.stringify(value, null, 2);
}

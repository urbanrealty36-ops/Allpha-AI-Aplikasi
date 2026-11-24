import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

type Definition={id:string;workflow_key:string;version:number;status:string;digest:string;definition:Record<string,unknown>;created_at:string};
type WorkflowStep={id:string;node_key:string;node_kind:string;status:string;output_payload?:Record<string,unknown>|null;error_code?:string|null;attempts?:number;max_attempts?:number};
type WorkflowEvent={sequence:number;event_type:string;step_key?:string|null;details?:Record<string,unknown>;created_at:string};
type WorkflowRun={id:string;definition_id:string;definition_version:number;status:string;trace_id:string;created_at:string;updated_at:string;completed_at?:string|null;steps?:WorkflowStep[];events?:WorkflowEvent[]};
type Props={apiBase:string;getAccessToken:()=>Promise<string>};

const DEFINITION_HINT="{\n  \"workflow_key\": \"workflow-key-anda\",\n  \"version\": 1,\n  \"max_runtime_seconds\": 120,\n  \"max_retries\": 1,\n  \"nodes\": [{ \"key\": \"hasil\", \"kind\": \"constant\", \"config\": { \"value\": \"hasil\" }, \"timeout_seconds\": 5 }],\n  \"edges\": []\n}";
const INPUT_HINT="{ \"message\": \"isi input workflow\" }";

export function WorkflowCenter({apiBase,getAccessToken}:Props){
 const [definitions,setDefinitions]=useState<Definition[]>([]);
 const [runs,setRuns]=useState<WorkflowRun[]>([]);
 const [selectedDefinitionId,setSelectedDefinitionId]=useState("");
 const [selectedRun,setSelectedRun]=useState<WorkflowRun|null>(null);
 const [definitionText,setDefinitionText]=useState("");
 const [inputText,setInputText]=useState("{}");
 const [loading,setLoading]=useState(true);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [notice,setNotice]=useState("");

 const request=useCallback(async(path:string,init:RequestInit={})=>{
  const token=await getAccessToken();
  const headers=new Headers(init.headers);
  headers.set("Authorization","Bearer "+token);headers.set("Accept","application/json");
  if(init.body&&!headers.has("Content-Type"))headers.set("Content-Type","application/json");
  const response=await fetch(apiBase+path,{...init,headers,cache:"no-store"});
  const body=response.status===204?null:await response.json().catch(()=>null);
  if(!response.ok)throw new Error(body?.detail?.message||body?.error?.message||"Workflow request gagal ("+response.status+").");
  return body;
 },[apiBase,getAccessToken]);

 const refresh=useCallback(async()=>{
  setLoading(true);setError("");
  try{
   const [definitionBody,runBody]=await Promise.all([request("/v1/workflows/definitions?limit=100"),request("/v1/workflows/runs?limit=100")]);
   const nextDefinitions=Array.isArray(definitionBody?.items)?definitionBody.items:[];
   setDefinitions(nextDefinitions);setRuns(Array.isArray(runBody?.items)?runBody.items:[]);
   setSelectedDefinitionId(current=>nextDefinitions.some((item:Definition)=>item.id===current)?current:(nextDefinitions[0]?.id||""));
  }catch(cause){setError(cause instanceof Error?cause.message:"Workflow tidak dapat dimuat.");}
  finally{setLoading(false);}
 },[request]);
 useEffect(()=>{void refresh();},[refresh]);

 async function createDefinition(){
  let definition:unknown;
  try{definition=JSON.parse(definitionText);}catch{setError("Definisi harus berupa JSON yang valid.");return;}
  setBusy(true);setError("");setNotice("");
  try{
   const body=await request("/v1/workflows/definitions",{method:"POST",body:JSON.stringify({definition})});
   setNotice("Definisi workflow tersimpan melalui FastAPI.");setDefinitionText("");await refresh();
   if(body?.definition?.id)setSelectedDefinitionId(body.definition.id);
  }catch(cause){setError(cause instanceof Error?cause.message:"Definisi workflow gagal disimpan.");}
  finally{setBusy(false);}
 }

 async function createRun(){
  if(!selectedDefinitionId){setError("Pilih definisi workflow terlebih dahulu.");return;}
  let input_payload:unknown;
  try{input_payload=JSON.parse(inputText);}catch{setError("Input workflow harus berupa JSON yang valid.");return;}
  if(!input_payload||typeof input_payload!=="object"||Array.isArray(input_payload)){setError("Input workflow harus berupa objek JSON.");return;}
  setBusy(true);setError("");setNotice("");
  try{
   const body=await request("/v1/workflows/definitions/"+encodeURIComponent(selectedDefinitionId)+"/runs",{method:"POST",body:JSON.stringify({input_payload})});
   const runId=body?.run?.id;setNotice("Workflow run tercatat. Worker memproses step dan checkpoint secara terpisah.");
   await refresh();if(runId)await inspectRun(runId);
  }catch(cause){setError(cause instanceof Error?cause.message:"Workflow run gagal dibuat.");}
  finally{setBusy(false);}
 }

 async function inspectRun(runId:string){
  setError("");
  try{const body=await request("/v1/workflows/runs/"+encodeURIComponent(runId));setSelectedRun(body?.run||null);}
  catch(cause){setError(cause instanceof Error?cause.message:"Detail workflow tidak dapat dimuat.");}
 }

 async function cancelRun(runId:string){
  Alert.alert("Batalkan workflow","Permintaan pembatalan akan dicatat oleh Workflow Engine.",[
   {text:"Kembali",style:"cancel"},
   {text:"Batalkan",style:"destructive",onPress:()=>void performCancel(runId)},
  ]);
 }
 async function performCancel(runId:string){
  setBusy(true);setError("");setNotice("");
  try{
   const body=await request("/v1/workflows/runs/"+encodeURIComponent(runId)+"/cancel",{method:"POST",body:"{}"});
   setSelectedRun(body?.run||null);setNotice("Permintaan pembatalan workflow diproses.");await refresh();await inspectRun(runId);
  }catch(cause){setError(cause instanceof Error?cause.message:"Workflow tidak dapat dibatalkan.");}
  finally{setBusy(false);}
 }

 return <ScrollView contentContainerStyle={styles.page}>
  <View style={styles.header}>
   <Text style={styles.kicker}>ENG-P11 · CHECKPOINT / RESUME</Text>
   <Text style={styles.title}>Workflow Engine</Text>
   <Text style={styles.copy}>Definisi berversi, run durable, step lease, checkpoint, retry, cancellation, dan event log melalui FastAPI kanonis.</Text>
   <Pressable onPress={()=>void refresh()} disabled={loading||busy} style={styles.secondaryButton}><Text style={styles.secondaryText}>{loading?"Memuat…":"Muat ulang"}</Text></Pressable>
  </View>
  {error?<Text accessibilityRole="alert" style={styles.error}>{error}</Text>:null}
  {notice?<Text style={styles.success}>{notice}</Text>:null}
  <View style={styles.card}>
   <Text style={styles.kicker}>VERSIONED DEFINITION</Text><Text style={styles.sectionTitle}>Simpan definisi workflow</Text>
   <Text style={styles.copy}>JSON deklaratif. Node yang belum didukung ditolak oleh API; tidak ada arbitrary code execution.</Text>
   <TextInput accessibilityLabel="Workflow definition JSON" multiline value={definitionText} onChangeText={setDefinitionText} placeholder={DEFINITION_HINT} placeholderTextColor="#7D89A7" autoCapitalize="none" style={styles.codeInput}/>
   <Pressable disabled={busy||!definitionText.trim()} onPress={()=>void createDefinition()} style={[styles.primaryButton,(busy||!definitionText.trim())&&styles.disabled]}><Text style={styles.primaryText}>{busy?"Menyimpan…":"Validasi & simpan versi"}</Text></Pressable>
   <Text style={styles.sectionTitle}>Definisi tersimpan ({definitions.length})</Text>
   {loading?<ActivityIndicator color="#A5B4FC"/>:definitions.length===0?<Text style={styles.muted}>Belum ada definisi workflow milik akun ini.</Text>:definitions.map(item=><Pressable key={item.id} onPress={()=>setSelectedDefinitionId(item.id)} style={[styles.row,selectedDefinitionId===item.id&&styles.selected]}><Text style={styles.body}>{item.workflow_key} · v{item.version}</Text><Text style={styles.muted}>{item.status} · {item.id}</Text><Text style={styles.muted}>Digest {item.digest.slice(0,20)}…</Text></Pressable>)}
  </View>
  <View style={styles.card}>
   <Text style={styles.kicker}>DURABLE RUN</Text><Text style={styles.sectionTitle}>Jalankan workflow</Text>
   <Text style={styles.muted}>Definisi terpilih: {definitions.find(item=>item.id===selectedDefinitionId)?.workflow_key||"Belum dipilih"}</Text>
   <TextInput accessibilityLabel="Workflow input JSON object" multiline value={inputText} onChangeText={setInputText} placeholder={INPUT_HINT} placeholderTextColor="#7D89A7" autoCapitalize="none" style={styles.codeInput}/>
   <Pressable disabled={busy||!selectedDefinitionId} onPress={()=>void createRun()} style={[styles.primaryButton,(busy||!selectedDefinitionId)&&styles.disabled]}><Text style={styles.primaryText}>{busy?"Memproses…":"Buat workflow run"}</Text></Pressable>
  </View>
  <View style={styles.card}>
   <Text style={styles.kicker}>PERSISTED RUNS</Text><Text style={styles.sectionTitle}>Riwayat run ({runs.length})</Text>
   {loading?<ActivityIndicator color="#A5B4FC"/>:runs.length===0?<Text style={styles.muted}>Belum ada workflow run tersimpan.</Text>:runs.map(run=><View key={run.id} style={styles.row}>
    <Pressable onPress={()=>void inspectRun(run.id)} style={styles.runSelect}><Text style={styles.body}>{run.status}</Text><Text style={styles.muted}>{run.id}</Text><Text style={styles.muted}>{new Date(run.created_at).toLocaleString("id-ID")}</Text></Pressable>
    {["created","queued","running"].includes(run.status)&&<Pressable disabled={busy} onPress={()=>void cancelRun(run.id)} style={styles.cancelButton}><Text style={styles.cancelText}>Batalkan</Text></Pressable>}
   </View>)}
  </View>
  {selectedRun&&<View style={styles.card}>
   <Text style={styles.kicker}>RUN DETAIL / TRACE</Text><Text style={styles.sectionTitle}>Detail run</Text>
   <Text style={styles.body}>Status: {selectedRun.status} · v{selectedRun.definition_version}</Text><Text style={styles.muted}>Run {selectedRun.id}</Text><Text style={styles.muted}>Trace {selectedRun.trace_id}</Text>
   <Pressable disabled={busy} onPress={()=>void inspectRun(selectedRun.id)} style={styles.secondaryButton}><Text style={styles.secondaryText}>Refresh detail</Text></Pressable>
   <Text style={styles.sectionTitle}>Steps / checkpoints ({selectedRun.steps?.length||0})</Text>
   {(selectedRun.steps||[]).map(step=><View key={step.id} style={styles.row}><Text style={styles.body}>{step.node_key} · {step.node_kind} · {step.status}</Text><Text style={styles.muted}>Percobaan {step.attempts??0}/{step.max_attempts??0}</Text>{step.error_code?<Text style={styles.error}>{step.error_code}</Text>:null}{step.output_payload?<Text style={styles.code}>{JSON.stringify(step.output_payload,null,2)}</Text>:null}</View>)}
   <Text style={styles.sectionTitle}>Event log ({selectedRun.events?.length||0})</Text>
   {(selectedRun.events||[]).map(event=><View key={event.sequence} style={styles.row}><Text style={styles.body}>#{event.sequence} · {event.event_type}{event.step_key?" · "+event.step_key:""}</Text><Text style={styles.muted}>{new Date(event.created_at).toLocaleString("id-ID")}</Text>{event.details?<Text style={styles.code}>{JSON.stringify(event.details)}</Text>:null}</View>)}
  </View>}
 </ScrollView>;
}

const styles=StyleSheet.create({
 page:{padding:16,paddingBottom:40,gap:14,backgroundColor:"#0B1020"},header:{gap:8,paddingVertical:6},
 kicker:{color:"#A5B4FC",fontSize:10,fontWeight:"800",letterSpacing:2},title:{color:"#F7F8FF",fontSize:25,fontWeight:"900"},
 sectionTitle:{color:"#F7F8FF",fontSize:17,fontWeight:"800",marginTop:4},copy:{color:"#A5ADC3",fontSize:13,lineHeight:19},
 muted:{color:"#9AA5BF",fontSize:11,lineHeight:17},body:{color:"#E7EAF5",fontSize:13,lineHeight:19,fontWeight:"700"},
 card:{backgroundColor:"#141B31",borderColor:"#29314B",borderWidth:1,borderRadius:18,padding:14,gap:10},
 codeInput:{minHeight:130,borderRadius:12,borderWidth:1,borderColor:"#394462",backgroundColor:"#0D1326",color:"#F7F8FF",padding:12,textAlignVertical:"top",fontFamily:"monospace",fontSize:11},
 code:{color:"#C6D2F1",backgroundColor:"#0D1326",padding:10,borderRadius:10,fontSize:10,fontFamily:"monospace"},
 primaryButton:{minHeight:46,borderRadius:12,backgroundColor:"#A5B4FC",alignItems:"center",justifyContent:"center",padding:12},primaryText:{color:"#11162B",fontWeight:"900",fontSize:13},
 secondaryButton:{alignSelf:"flex-start",borderRadius:12,borderWidth:1,borderColor:"#4A5678",paddingVertical:10,paddingHorizontal:14},secondaryText:{color:"#E5E7F6",fontWeight:"700",fontSize:12},
 cancelButton:{borderRadius:10,borderWidth:1,borderColor:"#8D4455",padding:8},cancelText:{color:"#FCA5A5",fontWeight:"700",fontSize:11},
 row:{borderTopWidth:1,borderTopColor:"#29314B",paddingVertical:10,gap:6},selected:{borderColor:"#818CF8",borderWidth:1,borderRadius:10,padding:10},runSelect:{gap:3},
 disabled:{opacity:0.45},error:{color:"#FCA5A5",backgroundColor:"#321D2B",padding:10,borderRadius:10,fontSize:12},
 success:{color:"#86EFAC",backgroundColor:"#12302C",padding:10,borderRadius:10,fontSize:12},
});

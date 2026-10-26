"use client";

import { useCallback, useEffect, useState } from "react";
import { getBrowserSupabase } from "../../lib/supabase";

type Node = { node_id:string; parent_id:string|null; level:string; slug:string; display_name:string; coordinates:Record<string,unknown>|null; landmarks:Record<string,unknown>[]; scene_key:string|null; child_count:number; version:number };
type Asset = { asset_id:string; asset_version:number; asset_key:string; display_name:string; category:string; sha256:string; byte_size:number; published_at:string|null };
const API=(process.env.NEXT_PUBLIC_API_BASE_URL||"https://api.allpha.web.id").replace(/\/$/,"");
async function authenticatedHeaders(): Promise<Record<string, string>> {
 const supabase = getBrowserSupabase();
 const { data } = supabase ? await supabase.auth.getSession() : { data: { session: null } };
 if (!data.session) throw new Error("Masuk untuk memuat katalog Universe 3D.");
 return { Accept: "application/json", Authorization: "Bearer " + data.session.access_token };
}
\nconst CATEGORIES=["universe","galaxy","world","orbit","capsule","district","booth","content-feed","agent-character","live-stage","human-live","sticker-social","animation","navigation-fx"];

export function SpatialNavigationBrowser(){
 const [items,setItems]=useState<Node[]>([]),[trail,setTrail]=useState<Node[]>([]),[assets,setAssets]=useState<Asset[]>([]);
 const [category,setCategory]=useState(""),[loading,setLoading]=useState(true),[assetLoading,setAssetLoading]=useState(true),[error,setError]=useState(""),[assetError,setAssetError]=useState("");
 const loadNodes=useCallback(async(parentKey?:string)=>{
  setLoading(true);setError("");
  try{const url=new URL(API+"/v1/spatial/navigation/nodes");if(parentKey)url.searchParams.set("parent_key",parentKey);url.searchParams.set("limit","100");
   const response=await fetch(url.toString(),{cache:"no-store",headers:await authenticatedHeaders()});
   const body=await response.json().catch(()=>({}));
   if(!response.ok)throw new Error(body?.detail?.message||"Navigasi Universe belum tersedia.");
   setItems(Array.isArray(body.items)?body.items:[]);
  }catch(e){setItems([]);setError(e instanceof Error?e.message:"Navigasi gagal dimuat.");}finally{setLoading(false);}
 },[]);
 const loadAssets=useCallback(async()=>{
  setAssetLoading(true);setAssetError("");
  try{const url=new URL(API+"/v1/spatial/assets");url.searchParams.set("limit","100");if(category)url.searchParams.set("category",category);
   const response=await fetch(url.toString(),{cache:"no-store",headers:{Accept:"application/json"}});
   const body=await response.json().catch(()=>({}));
   if(!response.ok)throw new Error(body?.detail?.message||"Katalog aset belum tersedia.");
   setAssets(Array.isArray(body.items)?body.items:[]);
  }catch(e){setAssets([]);setAssetError(e instanceof Error?e.message:"Katalog aset gagal dimuat.");}finally{setAssetLoading(false);}
 },[category]);
 useEffect(()=>{void loadNodes();},[loadNodes]);
 useEffect(()=>{void loadAssets();},[loadAssets]);
 const openNode=(node:Node)=>{setTrail((prev)=>[...prev,node]);void loadNodes(node.node_id);};
 const goTo=(index:number)=>{const next=trail.slice(0,index+1);setTrail(next);void loadNodes(next[next.length-1]?.node_id);};
 return <main style={{maxWidth:1100,margin:"0 auto",padding:24,color:"#172033"}}>
  <header style={{marginBottom:24}}><p style={{fontSize:12,letterSpacing:1,textTransform:"uppercase",color:"#64748b"}}>ALLPHA UNIVERSE · ENG-P21</p><h1 style={{fontSize:30,fontWeight:700}}>Navigasi Universe</h1><p style={{color:"#475569"}}>Hierarki dan katalog aset membaca data yang sudah dipublikasikan melalui FastAPI. Aset TEST_ONLY tidak ditampilkan.</p></header>
  <section style={{border:"1px solid #dbe2ea",borderRadius:16,padding:18,marginBottom:20}}>
   <h2 style={{fontSize:20,fontWeight:650}}>Hierarki spasial</h2>
   <nav aria-label="Jejak navigasi" style={{display:"flex",gap:8,flexWrap:"wrap",margin:"12px 0"}}><button onClick={()=>{setTrail([]);void loadNodes();}} style={button}>Universe</button>{trail.map((node,i)=><button key={node.node_id} onClick={()=>goTo(i)} style={button}>{node.display_name}</button>)}</nav>
   {loading?<p role="status">Memuat node publik…</p>:error?<div role="alert"><p>{error}</p><button style={button} onClick={()=>void loadNodes(trail.at(-1)?.node_id)}>Coba lagi</button></div>:items.length===0?<p role="status" style={{color:"#64748b"}}>Belum ada node publik pada tingkat ini. Node baru akan tampil setelah dibuat, divalidasi, dan dipublikasikan melalui alur kanonis.</p>:
   <ul style={{listStyle:"none",padding:0,display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(220px,1fr))",gap:10}}>{items.map(node=><li key={node.node_id} style={{border:"1px solid #e2e8f0",borderRadius:12,padding:14}}><p style={{fontSize:11,color:"#64748b",textTransform:"uppercase"}}>{node.level} · v{node.version}</p><h3 style={{fontWeight:650,margin:"4px 0 8px"}}>{node.display_name}</h3><p style={{fontSize:13,color:"#64748b"}}>{node.child_count} sub-node{node.child_count===1?"":"s"}{node.scene_key?" · Scene "+node.scene_key:""}</p><button style={button} onClick={()=>openNode(node)} disabled={!node.child_count}>Buka children</button></li>)}</ul>}
  </section>
  <section style={{border:"1px solid #dbe2ea",borderRadius:16,padding:18}}>
   <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",gap:12,flexWrap:"wrap"}}><h2 style={{fontSize:20,fontWeight:650}}>GLB yang dipublikasikan</h2><label style={{fontSize:14}}>Kategori <select value={category} onChange={e=>setCategory(e.target.value)} style={{marginLeft:8,padding:8,border:"1px solid #cbd5e1",borderRadius:8}}><option value="">Semua 14 kategori</option>{CATEGORIES.map(c=><option key={c} value={c}>{c}</option>)}</select></label></div>
   {assetLoading?<p role="status">Memuat katalog aset…</p>:assetError?<div role="alert"><p>{assetError}</p><button style={button} onClick={()=>void loadAssets()}>Coba lagi</button></div>:assets.length===0?<p role="status" style={{color:"#64748b",marginTop:12}}>Belum ada versi GLB yang memenuhi status published + approved pada katalog publik. Inventaris privat tidak ditampilkan sebagai aset publik.</p>:<ul style={{listStyle:"none",padding:0,display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(220px,1fr))",gap:10,marginTop:14}}>{assets.map(asset=><li key={asset.asset_id+":"+asset.asset_version} style={{border:"1px solid #e2e8f0",borderRadius:12,padding:14}}><p style={{fontSize:11,color:"#64748b"}}>{asset.category} · v{asset.asset_version}</p><h3 style={{fontWeight:650,margin:"4px 0"}}>{asset.display_name}</h3><p style={{fontSize:12,color:"#64748b"}}>{(asset.byte_size/1048576).toFixed(2)} MiB · SHA-256 {asset.sha256.slice(0,12)}…</p></li>)}</ul>}
  </section>
 </main>;
}
const button:React.CSSProperties={border:"1px solid #cbd5e1",borderRadius:8,padding:"8px 12px",background:"#fff",color:"#172033",cursor:"pointer"};

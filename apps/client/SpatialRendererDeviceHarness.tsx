import React, { Component, Suspense, useCallback, useEffect, useState, type ReactNode } from "react";
import { SafeAreaView, Text, View } from "react-native";
import { Canvas, useLoader } from "@react-three/fiber/native";
import { Box3, Vector3 } from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { configureAllphaGLTFLoader } from "./lib/spatial/configureAllphaGLTFLoader";

const assetUrl = process.env.EXPO_PUBLIC_SPATIAL_TEST_ASSET_URL || "";

class TestBoundary extends Component<{children: ReactNode; onError: (error: Error) => void},{failed:boolean}> {
  state={failed:false};
  static getDerivedStateFromError(){return {failed:true};}
  componentDidCatch(error:Error){console.error("SPATIAL_DEVICE_BOUNDARY_ERROR", error?.stack || error?.message || String(error));this.props.onError(error);}
  render(){return this.state.failed?null:this.props.children;}
}
function Model({url,onLoaded,onError}:{url:string;onLoaded:(value:string)=>void;onError:(error:Error)=>void}) {
  const gltf=useLoader(GLTFLoader,url,configureAllphaGLTFLoader);
  useEffect(()=>{
    let meshNodes=0,skinnedMeshNodes=0,textureReferences=0;
    gltf.scene.traverse((node:any)=>{
      if(node.isMesh){meshNodes++;if(node.isSkinnedMesh)skinnedMeshNodes++;}
      const mats=Array.isArray(node.material)?node.material:(node.material?[node.material]:[]);
      for(const mat of mats) for(const value of Object.values(mat as Record<string,any>)) if(value?.isTexture) textureReferences++;
    });
    const bounds=new Box3().setFromObject(gltf.scene);
    const size=bounds.getSize(new Vector3());
    if(meshNodes===0||skinnedMeshNodes===0||bounds.isEmpty()||Math.max(size.x,size.y,size.z)<=0) {
      onError(new Error("GLTFLoader produced no valid skinned avatar geometry"));
      return;
    }
    const result={assetUrl:url,meshNodes,skinnedMeshNodes,textureReferences,animationClips:gltf.animations.length,bounds:{x:size.x,y:size.y,z:size.z}};
    console.log("SPATIAL_DEVICE_TEST_RESULT:PASS "+JSON.stringify(result));
    onLoaded(JSON.stringify(result));
  },[gltf,onLoaded,onError,url]);
  return <primitive object={gltf.scene}/>;
}
export default function SpatialRendererDeviceHarness(){
  const [status,setStatus]=useState("RUNNING");
  const [details,setDetails]=useState("");
  const loaded=useCallback((value:string)=>{setStatus("PASS");setDetails(value);},[]);
  const fail=useCallback((error:Error)=>{const message=error?.message||String(error);const diagnostic=[message,error?.stack].filter(Boolean).join("\\n");setStatus("FAIL");setDetails(diagnostic);console.error("SPATIAL_DEVICE_TEST_RESULT:FAIL "+diagnostic);},[]);
  return <SafeAreaView style={{flex:1,backgroundColor:"#f4f5f7",padding:16}}>
    <Text style={{fontSize:22,fontWeight:"700",color:"#172033"}}>Allpha Spatial Device Regression</Text>
    <Text style={{marginTop:8,color:"#334155"}}>Test-only acquired avatar. Not a production publication.</Text>
    <View style={{height:420,marginTop:12,backgroundColor:"#e2e8f0"}}>
      {assetUrl ? <TestBoundary onError={fail}><Canvas camera={{position:[2,1.5,2],fov:45}}><ambientLight intensity={1.8}/><directionalLight position={[4,6,5]} intensity={2}/><Suspense fallback={null}><Model url={assetUrl} onLoaded={loaded} onError={fail}/></Suspense></Canvas></TestBoundary> : <Text>EXPO_PUBLIC_SPATIAL_TEST_ASSET_URL is missing.</Text>}
    </View>
    <Text testID="spatial-device-status" accessibilityLabel={"spatial-device-status:"+status} style={{fontSize:18,fontWeight:"700",marginTop:12}}>STATUS: {status}</Text>
    <Text selectable style={{fontSize:11,marginTop:8,color:"#475569"}}>{details}</Text>
  </SafeAreaView>;
}

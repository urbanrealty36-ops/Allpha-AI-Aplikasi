import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";
import { setTimeout as delay } from "node:timers/promises";
import { chromium } from "playwright";

const repoRoot = process.cwd();
const listPath = process.argv[2] || ".artifacts/acquired/avatar-files.txt";
const outDir = process.argv[3] || ".artifacts/acquired/results/browser-visual";
const files = fs.readFileSync(listPath,"utf8").split(/\r?\n/u).filter(Boolean);
if (files.length !== 232) throw new Error(`Expected 232 actual acquired avatar files, got ${files.length}`);
fs.mkdirSync(outDir,{recursive:true});
const server=spawn("python3",["-m","http.server","8765","--bind","127.0.0.1"],{cwd:repoRoot,stdio:"ignore"});
let browser;
try {
  let ready=false;
  for(let i=0;i<50;i++){
    try { const r=await fetch("http://127.0.0.1:8765/tools/3d-assets/browser-glb-visual-test.html"); if(r.ok){ready=true;break;} } catch {}
    await delay(200);
  }
  if(!ready) throw new Error("static test server did not become ready");
  browser=await chromium.launch({headless:true,args:["--no-sandbox","--disable-dev-shm-usage","--enable-webgl","--ignore-gpu-blocklist","--use-gl=angle","--use-angle=swiftshader"]});
  const rows=[];
  const screenshotEvery=Math.ceil(files.length/12);
  for(let i=0;i<files.length;i++){
    const absolute=path.resolve(files[i]);
    const rel=path.relative(repoRoot,absolute).split(path.sep).map(encodeURIComponent).join("/");
    const context=await browser.newContext({viewport:{width:540,height:560},deviceScaleFactor:1});
    const page=await context.newPage();
    const errors=[];
    page.on("pageerror",e=>{
      const message=String(e);
      errors.push(message);
      page.evaluate((text)=>{window.__spatialTestResult={status:"failed",error:text};},message).catch(()=>{});
    });
    const url="http://127.0.0.1:8765/tools/3d-assets/browser-glb-visual-test.html?asset="+encodeURIComponent("/"+rel);
    try {
      await page.goto(url,{waitUntil:"load",timeout:30000});
      await page.waitForFunction(()=>window.__spatialTestResult?.status==="passed"||window.__spatialTestResult?.status==="failed",null,{timeout:10000});
      const result=await page.evaluate(()=>window.__spatialTestResult);
      rows.push({index:i+1,file:path.basename(absolute),...result,pageErrors:errors});
      if(result.status==="passed" && (i%screenshotEvery===0 || i===files.length-1)){
        await page.locator("#stage").screenshot({path:path.join(outDir,`${String(i+1).padStart(3,"0")}-${path.basename(absolute,".glb")}.png`)});
      }
      if(result.status!=="passed" && errors.length===0) errors.push(result.error||"unknown browser failure");
    } catch(error) {
      rows.push({index:i+1,file:path.basename(absolute),status:"failed",error:String(error),pageErrors:errors});
    } finally { await context.close(); }
    if((i+1)%20===0) console.log(JSON.stringify({processed:i+1,total:files.length,passed:rows.filter(x=>x.status==="passed").length,failed:rows.filter(x=>x.status!=="passed").length}));
  }
  const summary={
    test:"real acquired avatar GLTFLoader texture decode + WebGL frame",
    total:rows.length,passed:rows.filter(x=>x.status==="passed").length,failed:rows.filter(x=>x.status!=="passed").length,
    withTextures:rows.filter(x=>x.status==="passed"&&x.textureObjects>0).length,
    decodedTextureImages:rows.reduce((s,x)=>s+(x.decodedTextureImages||0),0),
    drawCalls:rows.reduce((s,x)=>s+(x.drawCalls||0),0),
    screenshotCount:fs.readdirSync(outDir).filter(n=>n.endsWith(".png")).length,
    caveat:"One headless WebGL frame per real asset; not Android/iOS physical-device acceptance."
  };
  fs.writeFileSync(path.join(outDir,"results.json"),JSON.stringify(rows,null,2));
  fs.writeFileSync(path.join(outDir,"summary.json"),JSON.stringify(summary,null,2));
  console.log(JSON.stringify(summary,null,2));
  if(summary.failed) process.exitCode=1;
} finally {
  if(browser) await browser.close();
  server.kill("SIGTERM");
}

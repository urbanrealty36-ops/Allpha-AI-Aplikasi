#!/usr/bin/env python3
"""Acquire and audit GLB assets from the seven explicitly approved public repositories.
Downloads are written only to the workflow workspace/artifact; nothing is published to production.
"""
import argparse, csv, hashlib, json, os, re, shutil, time
from pathlib import Path
from urllib.parse import quote
import requests

SOURCES = [
 {"repo":"rostock/3DModels","ref":"main","license_hint":"CC0-1.0","mode":"tree"},
 {"repo":"ToxSam/os3a-gallery","ref":"main","license_hint":"CATALOG_ONLY","mode":"catalog"},
 {"repo":"SpectraStudios/SourceCityToolkit_glb","ref":"main","license_hint":"CC0 with texture exceptions; review","mode":"tree"},
 {"repo":"c-frame/valid-avatars-glb","ref":"main","license_hint":"MIT; likeness/underlying rights review","mode":"tree"},
 {"repo":"KhronosGroupArchives/glTF-Sample-Models","ref":"master","license_hint":"Per-model license; review required","mode":"tree"},
 {"repo":"ramjigeddam/3d","ref":"master","license_hint":"UNKNOWN — quarantine pending license","mode":"tree"},
 {"repo":"ToxSam/open-source-3D-assets","ref":"main","license_hint":"Registry metadata only; verify each collection/source","mode":"catalog"},
]
CATEGORIES = [
 "universe","galaxy","world","orbit","capsule","district","booth","content-feed",
 "agent-character","live-stage","human-live","sticker-social","animation","navigation-fx"
]
def category(path, repo):
 s=(path+" "+repo).lower().replace("_"," ").replace("-"," ")
 rules=[
  ("agent-character",r"avatar|character|robot|human|person|soldier|knight|fox|wolf"),
  ("live-stage",r"stage|podcast|talkshow|presentation|classroom|news|concert|studio"),
  ("booth",r"booth|stall|market|shop|store|kiosk|tenant|ad billboard|advert"),
  ("district",r"city|street|intersection|building|apartment|house|road|urban|market"),
  ("world",r"world|environment|landscape|terrain|island|forest|desert"),
  ("universe",r"universe|space|planetary|cosmos"),
  ("galaxy",r"galaxy|nebula|starfield|solar system"),
  ("orbit",r"orbit|satellite|space station"),
  ("capsule",r"capsule|container|pod"),
  ("content-feed",r"screen|phone|media|feed|video|camera|monitor"),
  ("human-live",r"human live|livestream|streamer"),
  ("sticker-social",r"sticker|emoji|icon|social"),
  ("animation",r"animation|rig|walk cycle|motion"),
  ("navigation-fx",r"arrow|portal|gate|waypoint|navigation|fx|effect|sign|traffic light"),
 ]
 for c,pat in rules:
  if re.search(pat,s): return c
 return "unmapped" # unknown assets remain unmapped until evidence-based human/catalog review
def api_get(url, session):
 for attempt in range(5):
  r=session.get(url,timeout=90)
  if r.status_code in (403,429):
   time.sleep(min(10*(attempt+1),45)); continue
  r.raise_for_status()
  return r
 raise RuntimeError("API rate limit exceeded: "+url)
def get_tree(source, session):
 url=f"https://api.github.com/repos/{source['repo']}/git/trees/{source['ref']}?recursive=1"
 data=api_get(url,session).json()
 if data.get("truncated"): print("WARNING truncated tree:",source["repo"])
 return [x for x in data.get("tree",[]) if x.get("type")=="blob" and x.get("path","").lower().endswith(".glb")]
def catalog_assets(source, session):
 # Both ToxSam repositories are registries; traverse projects.json and collection JSON metadata.
 root="https://raw.githubusercontent.com/ToxSam/open-source-3D-assets/main/"
 try: projects=api_get(root+"data/projects.json",session).json()
 except Exception as e: return [],[{"repo":source["repo"],"error":"projects.json: "+str(e)}]
 out=[]; errors=[]
 for project in projects:
  file=project.get("asset_data_file")
  if not file: continue
  try:
   assets=api_get(root+file,session).json()
   records=assets if isinstance(assets,list) else assets.get("assets",[]) if isinstance(assets,dict) else []
   for a in records:
    if not isinstance(a,dict): continue
    raw=a.get("url") or a.get("model_url") or a.get("download_url") or a.get("file_url") or a.get("src")
    fmt=str(a.get("format","") or a.get("file_format","")).lower()
    if not raw and isinstance(a.get("files"),list):
     raw=next((f.get("url") for f in a["files"] if isinstance(f,dict) and (str(f.get("format","")).lower()=="glb" or str(f.get("url","")).lower().endswith(".glb"))),None)
    if raw and (".glb" in raw.lower() or fmt=="glb"):
     out.append({"path":file+"#"+str(a.get("id") or a.get("name") or len(out)),
      "url":raw,"license":a.get("license") or project.get("license") or "UNKNOWN",
      "collection":project.get("name"),"repo":source["repo"]})
  except Exception as e: errors.append({"repo":source["repo"],"path":file,"error":str(e)})
 # os3a-gallery is a discovery site, not a binary source; entries are represented by the canonical registry above.
 return out,errors
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--out",default="allpha-glb-acquisition")
 # GitHub push events may expose an empty input variable; empty means use the safe default.
 p.add_argument("--max-assets",type=int,default=int(os.getenv("MAX_ASSETS") or "1200"))
 p.add_argument("--max-bytes",type=int,default=int(os.getenv("MAX_BYTES") or "3000000000"))
 a=p.parse_args()
 out=Path(a.out); files=out/"assets"; files.mkdir(parents=True,exist_ok=True)
 s=requests.Session(); s.headers.update({"Accept":"application/vnd.github+json","User-Agent":"Allpha-GLB-Audit/1.0"})
 token=os.getenv("GITHUB_TOKEN")
 if token: s.headers["Authorization"]="Bearer "+token
 candidates=[]; errors=[]; source_stats=[]
 for src in SOURCES:
  if src["mode"]=="catalog":
   rows,errs=catalog_assets(src,s); candidates.extend(rows); errors.extend(errs)
   source_stats.append({"repo":src["repo"],"kind":"catalog","candidate_glb":len(rows)})
  else:
   try:
    rows=get_tree(src,s)
    for x in rows:
     candidates.append({"repo":src["repo"],"path":x["path"],"url":f"https://raw.githubusercontent.com/{src['repo']}/{src['ref']}/{quote(x['path'],safe='/')}","license":src["license_hint"],"size_hint":x.get("size")})
    source_stats.append({"repo":src["repo"],"kind":"direct","candidate_glb":len(rows)})
   except Exception as e:
    errors.append({"repo":src["repo"],"error":str(e)}); source_stats.append({"repo":src["repo"],"kind":"direct","error":str(e)})
 seen_urls=set(); unique=[]
 for c in candidates:
  if c.get("url") and c["url"] not in seen_urls:
   seen_urls.add(c["url"]); unique.append(c)
 manifest=[]; hashes={}; total=0
 for i,c in enumerate(unique):
  if len(manifest)>=a.max_assets: break
  candidate_category=category(c.get("path",""),c.get("repo",""))
  row={**c,"category":candidate_category,
       "category_mapping_status":"heuristic_candidate" if candidate_category in CATEGORIES else "unmapped",
       "status":"PENDING","bytes":0,"sha256":"","dedupe_of":"","local_file":"","review":"REVIEW_REQUIRED"}
  url=c.get("url","")
  try:
   with s.get(url,stream=True,timeout=120,allow_redirects=True) as r:
    r.raise_for_status()
    length=int(r.headers.get("Content-Length") or 0)
    if total+length>a.max_bytes and length:
     row["status"]="SKIPPED_MAX_BYTES"; manifest.append(row); continue
    tmp=files/(f".{i}.part"); h=hashlib.sha256(); size=0
    with open(tmp,"wb") as f:
     for chunk in r.iter_content(1024*1024):
      if not chunk: continue
      size+=len(chunk)
      if total+size>a.max_bytes: raise RuntimeError("MAX_BYTES exceeded during streaming")
      h.update(chunk); f.write(chunk)
    digest=h.hexdigest(); row["bytes"]=size; row["sha256"]=digest
    if size<12:
     row["status"]="FAILED_INVALID_SMALL_FILE"; tmp.unlink(missing_ok=True)
    elif digest in hashes:
     row["status"]="DUPLICATE_SHA256"; row["dedupe_of"]=hashes[digest]; tmp.unlink(missing_ok=True)
    else:
     safe=re.sub(r"[^A-Za-z0-9._-]+","_",Path(c.get("path","asset.glb").split("#")[0]).name)
     dest=files/(digest[:12]+"_"+safe)
     tmp.replace(dest); row["local_file"]=str(dest.relative_to(out)); row["status"]="DOWNLOADED"
     hashes[digest]=row["local_file"]; total+=size
     if "UNKNOWN" in str(row["license"]).upper() or "review" in str(row["license"]).lower(): row["review"]="QUARANTINE_LICENSE"
     else: row["review"]="LICENSE_REVIEW_STILL_REQUIRED"
  except Exception as e:
   row["status"]="FAILED_DOWNLOAD"; row["error"]=str(e)[:500]; errors.append({"repo":c.get("repo"),"path":c.get("path"),"error":str(e)[:500]})
  manifest.append(row)
  if i and i%50==0: print(f"Processed {i}/{len(unique)} candidates; downloaded bytes={total}")
 fields=sorted({k for row in manifest for k in row})
 with open(out/"manifest.csv","w",newline="",encoding="utf-8") as f:
  w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(manifest)
 summary={"sources":source_stats,"candidate_urls":len(candidates),"unique_urls":len(unique),"processed":len(manifest),
 "downloaded":sum(x["status"]=="DOWNLOADED" for x in manifest),
 "duplicate_hashes":sum(x["status"]=="DUPLICATE_SHA256" for x in manifest),
 "failed":sum(x["status"]=="FAILED_DOWNLOAD" for x in manifest),
 "skipped_limits":sum(x["status"].startswith("SKIPPED") for x in manifest),
 "unique_sha256":len(hashes),"downloaded_bytes":total,"errors":errors,
 "unmapped_candidates":sum(x["category"]=="unmapped" for x in manifest),
 "categories":{c:sum(x["category"]==c for x in manifest) for c in CATEGORIES},
 "important":"This is an acquisition inventory only. Category is heuristic; no asset is approved for production, redistributed or uploaded to Supabase automatically. Check per-file license, GLB validity, dependencies, malware/safety, size/performance, and visual QA."}
 (out/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
 (out/"errors.json").write_text(json.dumps(errors,indent=2,ensure_ascii=False),encoding="utf-8")
 print(json.dumps({k:v for k,v in summary.items() if k not in ("errors","sources")},indent=2))
if __name__=="__main__": main()

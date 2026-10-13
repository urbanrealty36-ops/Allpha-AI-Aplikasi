#!/usr/bin/env python3
"""Read-only GLB structural audit of a previously acquired Allpha artifact."""
import argparse, csv, hashlib, json, struct
from pathlib import Path

def parse_glb(path):
    r={"glb_header_valid":False,"json_chunk_valid":False,"external_uri_count":0,
       "scene_count":0,"node_count":0,"mesh_count":0,"material_count":0,
       "animation_count":0,"image_count":0,"accessor_count":0,"triangle_count_estimate":0,"parse_error":""}
    try:
        size=path.stat().st_size
        with path.open("rb") as f:
            header=f.read(12)
            if len(header)!=12: raise ValueError("short header")
            magic,version,length=struct.unpack("<4sII",header)
            if magic!=b"glTF": raise ValueError("magic is not glTF; possible HTML/error body")
            if version!=2: raise ValueError(f"unsupported GLB version {version}")
            if length!=size: raise ValueError(f"header length {length} != file size {size}")
            r["glb_header_valid"]=True
            ch=f.read(8)
            if len(ch)!=8: raise ValueError("missing JSON chunk")
            n,typ=struct.unpack("<I4s",ch)
            if typ!=b"JSON": raise ValueError("first chunk is not JSON")
            raw=f.read(n)
            if len(raw)!=n: raise ValueError("truncated JSON chunk")
            doc=json.loads(raw.decode("utf-8").rstrip("\\x00 \\t\\r\\n"))
        r["json_chunk_valid"]=True
        for k,o in [("scenes","scene_count"),("nodes","node_count"),("meshes","mesh_count"),("materials","material_count"),("animations","animation_count"),("images","image_count"),("accessors","accessor_count")]:
            r[o]=len(doc.get(k,[]) or [])
        uris=[]
        for group in ("buffers","images"):
            for obj in doc.get(group,[]) or []:
                uri=obj.get("uri") if isinstance(obj,dict) else None
                if uri and not uri.startswith("data:"): uris.append(uri)
        r["external_uri_count"]=len(uris); r["external_uris"]=";".join(uris[:25])
        accessors=doc.get("accessors",[]) or []; tri=0
        for mesh in doc.get("meshes",[]) or []:
            for prim in mesh.get("primitives",[]) or []:
                if prim.get("mode",4)!=4: continue
                idx=prim.get("indices")
                if isinstance(idx,int) and 0<=idx<len(accessors): tri+=int(accessors[idx].get("count",0))//3
                else:
                    pos=prim.get("attributes",{}).get("POSITION")
                    if isinstance(pos,int) and 0<=pos<len(accessors): tri+=int(accessors[pos].get("count",0))//3
        r["triangle_count_estimate"]=tri
        r["has_scene"]=bool(doc.get("scenes"))
        r["default_scene_valid"]=("scene" not in doc or (isinstance(doc.get("scene"),int) and 0<=doc["scene"]<len(doc.get("scenes",[]))))
        r["extensions_used"]=";".join(doc.get("extensionsUsed",[]) or [])
        r["extensions_required"]=";".join(doc.get("extensionsRequired",[]) or [])
    except Exception as e: r["parse_error"]=str(e)[:400]
    return r

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True)
    p.add_argument("--out",default="allpha-glb-asset-audit")
    p.add_argument("--max-file-mib",type=float,default=50.0)
    p.add_argument("--max-triangles",type=int,default=300000)
    a=p.parse_args(); root=Path(a.root); out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
    mp=root/"manifest.csv"
    if not mp.exists(): raise SystemExit("manifest not found: "+str(mp))
    with mp.open(newline="",encoding="utf-8") as f: rows=list(csv.DictReader(f))
    reports=[]; totals={"manifest_rows":len(rows),"files_found":0,"structurally_valid":0,"structurally_invalid":0,"missing_files":0,"duplicate_references":0,"license_quarantine":0,"external_dependency_files":0,"oversize_files":0,"high_triangle_files":0}
    for row in rows:
        status=row.get("status")
        if status not in ("DOWNLOADED","DUPLICATE_SHA256"): continue
        r=dict(row)
        lic=(row.get("license") or "UNKNOWN").lower()
        license_review=not lic.strip() or "unknown" in lic or "review" in lic or "exception" in lic or "mit;" in lic or "quarantine" in lic
        if status=="DUPLICATE_SHA256":
            # A duplicate is a manifest reference to an already-downloaded SHA-256,
            # not a missing binary. Preserve the source/license evidence without
            # attempting to audit a second copy of the same bytes.
            r.update({"audit_status":"DUPLICATE_REFERENCE","parse_error":"","license_review_required":license_review,
                      "license_gate":"REVIEW_REQUIRED" if license_review else "SOURCE_HINT_ONLY",
                      "production_approved":False,"flags":"DUPLICATE_SHA256_REFERENCE"})
            totals["duplicate_references"]+=1
            if license_review: totals["license_quarantine"]+=1
            reports.append(r)
            continue
        local=row.get("local_file",""); file=root/local if local else None
        if not file or not file.is_file():
            r.update({"audit_status":"MISSING_FILE","parse_error":"manifest path missing"}); totals["missing_files"]+=1; reports.append(r); continue
        totals["files_found"]+=1; size=file.stat().st_size; h=hashlib.sha256()
        with file.open("rb") as f:
            for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
        digest=h.hexdigest(); parsed=parse_glb(file); r.update(parsed)
        r["actual_bytes"]=size; r["actual_sha256"]=digest
        r["size_matches_manifest"]=(str(size)==str(row.get("bytes","")))
        r["sha256_matches_manifest"]=(digest==row.get("sha256",""))
        r["license_review_required"]=license_review; r["license_gate"]="REVIEW_REQUIRED" if license_review else "SOURCE_HINT_ONLY"
        r["oversize_for_mobile"]=size>a.max_file_mib*1024*1024
        r["high_triangle_count"]=int(parsed.get("triangle_count_estimate",0))>a.max_triangles
        flags=[]
        if not parsed["glb_header_valid"] or not parsed["json_chunk_valid"]: flags.append("INVALID_GLB_STRUCTURE")
        if not r["size_matches_manifest"] or not r["sha256_matches_manifest"]: flags.append("INTEGRITY_MISMATCH")
        if parsed.get("external_uri_count",0): flags.append("EXTERNAL_DEPENDENCIES")
        if license_review: flags.append("LICENSE_REVIEW")
        if r["oversize_for_mobile"]: flags.append("OVERSIZE_MOBILE")
        if r["high_triangle_count"]: flags.append("HIGH_TRIANGLES")
        if not parsed.get("scene_count",0): flags.append("NO_SCENE")
        r["flags"]=";".join(flags)
        r["audit_status"]="STRUCTURE_PASS_REVIEW_REQUIRED" if parsed["glb_header_valid"] and parsed["json_chunk_valid"] else "STRUCTURE_FAIL"
        if parsed["glb_header_valid"] and parsed["json_chunk_valid"]: totals["structurally_valid"]+=1
        else: totals["structurally_invalid"]+=1
        if license_review: totals["license_quarantine"]+=1
        if parsed.get("external_uri_count",0): totals["external_dependency_files"]+=1
        if r["oversize_for_mobile"]: totals["oversize_files"]+=1
        if r["high_triangle_count"]: totals["high_triangle_files"]+=1
        r["production_approved"]=False
        reports.append(r)
    fields=sorted({k for r in reports for k in r})
    with (out/"asset-audit.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(reports)
    summary={**totals,"max_file_mib_threshold":a.max_file_mib,"max_triangle_threshold":a.max_triangles,
      "unique_downloaded_assets_audited":sum(1 for r in reports if r.get("status")=="DOWNLOADED"),
      "duplicate_references_audited":totals["duplicate_references"],
      "production_approved":0,"gate":"REQUIRES_LICENSE_VISUAL_MOBILE_RUNTIME_REVIEW",
      "note":"Structural audit only; not legal clearance, visual QA, malware scan, GPU performance, or renderer compatibility."}
    (out/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    # Produce a conservative per-reference license qualification queue. Repository
    # license metadata is only a lead; no item is marked production-approved here.
    license_rows=[]
    for r in reports:
        repo=(r.get("repo") or "").strip()
        lic=(r.get("license") or "UNKNOWN").strip()
        if repo=="rostock/3DModels" and lic=="CC0-1.0":
            disposition="ALLOW_STAGING_CC0_REPOSITORY_LICENSE"
            reason="The source repository publishes a CC0-1.0 LICENSE and its catalog points to that license. Allowed for non-production staging only; retain source URL/hash and verify embedded content and provenance before production."
        elif repo=="SpectraStudios/SourceCityToolkit_glb":
            disposition="QUARANTINE_TEXTURE_EXCEPTION_REVIEW"
            reason="Source indicates texture exceptions; inspect the exact model and all embedded/external textures before redistribution."
        elif repo=="c-frame/valid-avatars-glb":
            disposition="QUARANTINE_LIKENESS_AND_UNDERLYING_RIGHTS"
            reason="MIT code/model license hint does not establish rights to likeness, identity, or third-party underlying material."
        elif repo=="ramjigeddam/3d" or "unknown" in lic.lower():
            disposition="QUARANTINE_NO_LICENSE_EVIDENCE"
            reason="No reliable per-asset redistribution license evidence recorded; keep out of production."
        else:
            disposition="REQUIRES_PER_MODEL_LICENSE_REVIEW"
            reason="No source-specific clearance rule applies; inspect the exact asset license and dependencies."
        license_rows.append({
            "repo":repo,"path":r.get("path",""),"url":r.get("url",""),
            "status":r.get("status",""),"sha256":r.get("sha256",""),
            "dedupe_of":r.get("dedupe_of",""),"license_hint":lic,
            "qualification":disposition,"reason":reason,"production_approved":False
        })
    lfields=["repo","path","url","status","sha256","dedupe_of","license_hint","qualification","reason","production_approved"]
    with (out/"license-qualification.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=lfields); w.writeheader(); w.writerows(license_rows)
    staging_allowlist=[x for x in license_rows if x["qualification"]=="ALLOW_STAGING_CC0_REPOSITORY_LICENSE" and x["status"]=="DOWNLOADED"]
    with (out/"license-staging-allowlist.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=lfields); w.writeheader(); w.writerows(staging_allowlist)
    quarantine=[x for x in license_rows if x["qualification"]!="ALLOW_STAGING_CC0_REPOSITORY_LICENSE"]
    with (out/"license-quarantine.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=lfields); w.writeheader(); w.writerows(quarantine)
    from collections import Counter
    qualification_counts=Counter(x["qualification"] for x in license_rows)
    summary["license_qualification_rows"]=len(license_rows)
    summary["license_qualification_counts"]=dict(sorted(qualification_counts.items()))
    summary["staging_allowlist_rows"]=len(staging_allowlist)
    summary["quarantine_rows"]=len(quarantine)
    summary["production_approved"]=0
    (out/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    (out/"runtime-readiness.md").write_text("# Allpha GLB Asset Audit - Runtime Readiness\\n\\nThis audit reads the existing acquisition artifact; it does not rerun acquisition or upload to production.\\n\\nDuplicate SHA-256 references are reported separately and are not treated as missing binaries. Structure PASS only confirms GLB v2 header, declared byte length and JSON chunk. The license-staging-allowlist CSV permits non-production staging only; it is not production/legal clearance. License-quarantine CSV records assets excluded from staging pending review. External URIs require dependency resolution. Size and triangle thresholds are triage heuristics. Every asset remains NOT APPROVED pending license, visual, security, mobile-performance and renderer QA.\\n",encoding="utf-8")
    print(json.dumps(summary,indent=2))
if __name__=="__main__": main()

"""Owner-scoped knowledge-source upload and processing lifecycle."""
from __future__ import annotations
import hashlib, io, os, re, uuid, zipfile, xml.etree.ElementTree as ET
from typing import Any
import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from allpha_api.auth import current_user, user_db_request

router = APIRouter(prefix="/v1/agents/{agent_id}/knowledge", tags=["agent-knowledge"])
MAX_BYTES = 15 * 1024 * 1024
ALLOWED = {".pdf": {"application/pdf"}, ".md": {"text/markdown","text/plain","application/octet-stream"}, ".txt": {"text/plain","text/markdown","application/octet-stream"}, ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}}
SOURCE_FIELDS = "id,agent_id,owner_id,filename,media_type,size_bytes,sha256,storage_path,source_version,status,processing_stage,error_code,provenance,created_at,updated_at"
JOB_FIELDS = "id,source_id,agent_id,owner_id,status,stage,attempt,progress,error_code,created_at,updated_at"

class RetryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str | None = Field(default=None, max_length=300)

async def _owned(agent_id: uuid.UUID, request: Request, user: dict[str, Any]) -> str:
    token = getattr(request.state, "supabase_access_token", None)
    rows = await user_db_request("GET","agent_ownerships",token,params={"select":"agent_id","agent_id":f"eq.{agent_id}","owner_user_id":f"eq.{user['id']}","status":"eq.active","limit":"1"})
    if not rows: raise HTTPException(404,detail={"code":"AGENT_NOT_FOUND","message":"Agent tidak ditemukan."})
    return token

def _storage_config():
    url=os.getenv("SUPABASE_URL","").rstrip("/"); key=os.getenv("SUPABASE_PUBLISHABLE_KEY","")
    if not url or not key: raise HTTPException(503,detail={"code":"STORAGE_NOT_CONFIGURED","message":"Storage belum dikonfigurasi."})
    return url,key

async def _storage(method: str,path: str,token: str,data: bytes|None=None,media_type: str|None=None):
    url,key=_storage_config(); headers={"apikey":key,"Authorization":f"Bearer {token}"}
    if media_type: headers["Content-Type"]=media_type
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20,connect=4)) as c: r=await c.request(method,f"{url}/storage/v1/object/{path}",headers=headers,content=data)
    except httpx.HTTPError as exc: raise HTTPException(503,detail={"code":"STORAGE_UNAVAILABLE","message":"Penyimpanan dokumen tidak tersedia."}) from exc
    if r.status_code not in (200,201,204):
        status=403 if r.status_code in (401,403) else 503
        raise HTTPException(status,detail={"code":"STORAGE_OPERATION_FAILED","message":"Operasi penyimpanan dokumen gagal."})

async def _scan(data: bytes,filename: str,media_type: str):
    endpoint=os.getenv("ALLPHA_DOCUMENT_SCANNER_URL","").strip()
    if not endpoint: raise HTTPException(503,detail={"code":"SCANNER_NOT_CONFIGURED","message":"Dokumen tetap dikarantina sampai pemindai malware dikonfigurasi."})
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(12,connect=3)) as c: r=await c.post(endpoint,files={"file":(filename,data,media_type)})
    except httpx.HTTPError as exc: raise HTTPException(503,detail={"code":"SCANNER_UNAVAILABLE","message":"Pemindai malware tidak tersedia; dokumen tetap dikarantina."}) from exc
    try: verdict=r.json().get("verdict") if r.status_code==200 else None
    except (ValueError,AttributeError): verdict=None
    if verdict!="clean": raise HTTPException(422,detail={"code":"MALWARE_SCAN_REJECTED","message":"Dokumen ditolak atau pemindai tidak memberikan verdict clean."})

def _extract(filename: str,data: bytes):
    ext=os.path.splitext(filename.lower())[1]
    if ext in (".txt",".md"):
        try: return [{"location":{"kind":"document","index":1},"text":data.decode("utf-8-sig")}]
        except UnicodeDecodeError as exc: raise ValueError("INVALID_TEXT_ENCODING") from exc
    if ext==".pdf":
        from pypdf import PdfReader
        reader=PdfReader(io.BytesIO(data),strict=True)
        return [{"location":{"kind":"page","index":i},"text":page.extract_text() or ""} for i,page in enumerate(reader.pages,1)]
    if ext==".docx":
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if "word/document.xml" not in z.namelist(): raise ValueError("INVALID_DOCX")
            root=ET.fromstring(z.read("word/document.xml"))
        ns={"w":"http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        return [{"location":{"kind":"paragraph","index":i},"text":"".join(p.itertext()).strip()} for i,p in enumerate(root.findall(".//w:p",ns),1) if "".join(p.itertext()).strip()]
    raise ValueError("UNSUPPORTED_FORMAT")

def _chunk(pages):
    out=[]
    for page in pages:
        text=re.sub(r"\x00","",str(page["text"])).strip()
        for offset in range(0,len(text),1800):
            value=text[offset:offset+1800].strip()
            if value: out.append({"content":value,"source_location":{**page["location"],"offset":offset}})
    return out

async def _source(agent_id,source_id,token,user):
    rows=await user_db_request("GET","agent_knowledge_sources",token,params={"select":SOURCE_FIELDS,"id":f"eq.{source_id}","agent_id":f"eq.{agent_id}","owner_id":f"eq.{user['id']}","limit":"1"})
    if not rows: raise HTTPException(404,detail={"code":"SOURCE_NOT_FOUND","message":"Sumber pengetahuan tidak ditemukan."})
    return rows[0]

@router.post("/sources",status_code=201)
async def upload_source(agent_id: uuid.UUID,request: Request,file: UploadFile=File(...),user: dict[str,Any]=Depends(current_user)):
    token=await _owned(agent_id,request,user); filename=os.path.basename((file.filename or "").replace("\\","/")).strip()
    ext=os.path.splitext(filename.lower())[1]; media=(file.content_type or "application/octet-stream").split(";")[0].lower()
    if not filename or ext not in ALLOWED or media not in ALLOWED[ext]: raise HTTPException(415,detail={"code":"UNSUPPORTED_DOCUMENT","message":"Format yang didukung: PDF, Markdown, TXT, dan DOCX."})
    data=await file.read(MAX_BYTES+1)
    if not data: raise HTTPException(422,detail={"code":"EMPTY_DOCUMENT","message":"Dokumen kosong."})
    if len(data)>MAX_BYTES: raise HTTPException(413,detail={"code":"DOCUMENT_TOO_LARGE","message":"Ukuran maksimum dokumen adalah 15 MiB."})
    if ext==".pdf" and not data.startswith(b"%PDF-"): raise HTTPException(422,detail={"code":"INVALID_FILE_SIGNATURE","message":"Signature PDF tidak valid."})
    if ext==".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                if "word/document.xml" not in z.namelist(): raise ValueError()
        except (zipfile.BadZipFile,ValueError): raise HTTPException(422,detail={"code":"INVALID_FILE_SIGNATURE","message":"Struktur DOCX tidak valid."})
    sid=uuid.uuid4(); digest=hashlib.sha256(data).hexdigest(); path=f"{user['id']}/{agent_id}/{sid}/{filename}"
    body={"id":str(sid),"agent_id":str(agent_id),"owner_id":user["id"],"filename":filename,"media_type":media,"size_bytes":len(data),"sha256":digest,"storage_path":path,"source_version":1,"status":"quarantined","processing_stage":"awaiting_malware_scan","provenance":{"kind":"user_upload","filename":filename,"sha256":digest,"source_version":1}}
    rows=await user_db_request("POST","agent_knowledge_sources",token,params={"select":SOURCE_FIELDS},body=body,prefer="return=representation")
    if not rows: raise HTTPException(500,detail={"code":"SOURCE_CREATE_FAILED","message":"Metadata dokumen gagal disimpan."})
    try: await _storage("POST",f"agent-knowledge/{path}",token,data,media)
    except HTTPException:
        await user_db_request("DELETE","agent_knowledge_sources",token,params={"id":f"eq.{sid}"}); raise
    jobs=await user_db_request("POST","agent_knowledge_jobs",token,params={"select":JOB_FIELDS},body={"source_id":str(sid),"agent_id":str(agent_id),"owner_id":user["id"],"status":"queued","stage":"awaiting_malware_scan","attempt":0,"progress":0},prefer="return=representation")
    return {"source":rows[0],"job":jobs[0] if jobs else None,"publication":"private","retrieval_ready":False}

@router.get("/sources")
async def list_sources(agent_id: uuid.UUID,request: Request,user: dict[str,Any]=Depends(current_user)):
    token=await _owned(agent_id,request,user)
    rows=await user_db_request("GET","agent_knowledge_sources",token,params={"select":SOURCE_FIELDS,"agent_id":f"eq.{agent_id}","owner_id":f"eq.{user['id']}","order":"created_at.desc","limit":"100"})
    return {"items":rows or []}

@router.get("/sources/{source_id}")
async def get_source(agent_id: uuid.UUID,source_id: uuid.UUID,request: Request,user: dict[str,Any]=Depends(current_user)):
    token=await _owned(agent_id,request,user); source=await _source(agent_id,source_id,token,user)
    jobs=await user_db_request("GET","agent_knowledge_jobs",token,params={"select":JOB_FIELDS,"source_id":f"eq.{source_id}","agent_id":f"eq.{agent_id}","owner_id":f"eq.{user['id']}","order":"created_at.desc","limit":"20"})
    return {"source":source,"jobs":jobs or []}

@router.post("/sources/{source_id}/process")
async def process_source(agent_id: uuid.UUID,source_id: uuid.UUID,request: Request,user: dict[str,Any]=Depends(current_user)):
    token=await _owned(agent_id,request,user); source=await _source(agent_id,source_id,token,user)
    if source["status"] not in ("quarantined","failed"): raise HTTPException(409,detail={"code":"SOURCE_STATE_CONFLICT","message":"Sumber tidak berada pada status yang dapat diproses ulang."})
    jobs=await user_db_request("POST","agent_knowledge_jobs",token,params={"select":JOB_FIELDS},body={"source_id":str(source_id),"agent_id":str(agent_id),"owner_id":user["id"],"status":"processing","stage":"malware_scan","attempt":1,"progress":5},prefer="return=representation")
    job=jobs[0] if jobs else None
    try:
        url,key=_storage_config()
        async with httpx.AsyncClient(timeout=httpx.Timeout(20,connect=4)) as c: r=await c.get(f"{url}/storage/v1/object/authenticated/agent-knowledge/{source['storage_path']}",headers={"apikey":key,"Authorization":f"Bearer {token}"})
        if r.status_code!=200: raise HTTPException(503,detail={"code":"STORAGE_UNAVAILABLE","message":"Dokumen karantina tidak dapat dibaca."})
        await _scan(r.content,source["filename"],source["media_type"])
        chunks=_chunk(_extract(source["filename"],r.content))
        if not chunks: raise HTTPException(422,detail={"code":"NO_TEXT_EXTRACTED","message":"Tidak ada teks yang dapat diekstrak dari dokumen."})
        await user_db_request("DELETE","agent_knowledge_chunks",token,params={"source_id":f"eq.{source_id}","owner_id":f"eq.{user['id']}"})
        for start in range(0,len(chunks),50):
            batch=[{"source_id":str(source_id),"agent_id":str(agent_id),"owner_id":user["id"],"chunk_index":start+i,"content":v["content"],"source_location":v["source_location"],"source_version":source.get("source_version",1),"content_sha256":hashlib.sha256(v["content"].encode()).hexdigest()} for i,v in enumerate(chunks[start:start+50])]
            await user_db_request("POST","agent_knowledge_chunks",token,body=batch,prefer="return=minimal")
        await user_db_request("PATCH","agent_knowledge_sources",token,params={"id":f"eq.{source_id}","owner_id":f"eq.{user['id']}","agent_id":f"eq.{agent_id}"},body={"status":"indexed_pending_embeddings","processing_stage":"text_extracted","error_code":None})
        if job: await user_db_request("PATCH","agent_knowledge_jobs",token,params={"id":f"eq.{job['id']}"},body={"status":"succeeded","stage":"text_extracted","progress":70})
        return {"source_id":str(source_id),"status":"indexed_pending_embeddings","chunks_created":len(chunks),"retrieval_ready":False,"next_dependency":"ENG-P09 Model Router embeddings and retrieval indexing"}
    except HTTPException as exc:
        code=(exc.detail.get("code") if isinstance(exc.detail,dict) else None) or "PROCESSING_FAILED"
        await user_db_request("PATCH","agent_knowledge_sources",token,params={"id":f"eq.{source_id}","owner_id":f"eq.{user['id']}","agent_id":f"eq.{agent_id}"},body={"status":"failed","processing_stage":"failed","error_code":code})
        if job: await user_db_request("PATCH","agent_knowledge_jobs",token,params={"id":f"eq.{job['id']}"},body={"status":"failed","stage":"failed","error_code":code})
        raise

@router.post("/sources/{source_id}/retry")
async def retry_source(agent_id: uuid.UUID,source_id: uuid.UUID,payload: RetryRequest,request: Request,user: dict[str,Any]=Depends(current_user)):
    token=await _owned(agent_id,request,user); source=await _source(agent_id,source_id,token,user)
    if source["status"] not in ("failed","quarantined"): raise HTTPException(409,detail={"code":"SOURCE_STATE_CONFLICT","message":"Retry hanya tersedia untuk sumber gagal atau masih dikarantina."})
    return {**(await process_source(agent_id,source_id,request,user)),"retry_reason":payload.reason}

@router.delete("/sources/{source_id}",status_code=204)
async def delete_source(agent_id: uuid.UUID,source_id: uuid.UUID,request: Request,user: dict[str,Any]=Depends(current_user)):
    token=await _owned(agent_id,request,user); source=await _source(agent_id,source_id,token,user)
    await _storage("DELETE",f"agent-knowledge/{source['storage_path']}",token)
    await user_db_request("DELETE","agent_knowledge_sources",token,params={"id":f"eq.{source_id}","agent_id":f"eq.{agent_id}","owner_id":f"eq.{user['id']}"})

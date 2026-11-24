"""Shared fakes for knowledge ingestion worker tests (importable helper, not a test module)."""
import hashlib


OWNER="11111111-1111-4111-8111-111111111111"
AGENT="22222222-2222-4222-8222-222222222222"
SOURCE="33333333-3333-4333-8333-333333333333"
JOB="44444444-4444-4444-8444-444444444444"
LEASE="55555555-5555-4555-8555-555555555555"
DATA=b"Private knowledge source"


class FakeStore:
    def __init__(self, data=DATA):
        self.data=data
        self.claimed=False
        self.states=[]
        self.batches=[]
        self.completed=[]
        self.failures=[]
    async def claim(self, *, lease_seconds, stage):
        assert stage=="awaiting_malware_scan"
        if self.claimed:return None
        self.claimed=True
        return {"id":JOB,"source_id":SOURCE,"agent_id":AGENT,"owner_id":OWNER,
                "source_version":1,"lease_token":LEASE,"attempt":1,"stage":stage}
    async def load_source(self, job):
        return {"id":SOURCE,"agent_id":AGENT,"owner_id":OWNER,"filename":"notes.txt",
                "media_type":"text/plain","size_bytes":len(self.data),
                "sha256":hashlib.sha256(self.data).hexdigest(),"storage_path":f"{OWNER}/{AGENT}/{SOURCE}/notes.txt",
                "source_version":1,"status":"quarantined","sensitivity":"internal",
                "provenance":{"sensitivity":"internal"}}
    async def update_source_state(self, job, *, status, stage, error_code=None, scanner_receipt=None):
        self.states.append((status,stage,error_code,scanner_receipt))
        return True
    async def persist_document_chunk_batch(self, job, *, chunks, reset):
        self.batches.append((chunks,reset))
        return len(chunks)
    async def complete_document_parse(self, job, *, expected_chunk_count):
        self.completed.append(expected_chunk_count)
        return {"source_id":SOURCE,"source_version":1,"chunks_created":expected_chunk_count,
                "embedding_job_id":"embedding-job","embedding_job_status":"queued","retrieval_ready":False}
    async def fail_document_job(self, job, *, error_code, stage, retryable, retry_delay_seconds=30):
        self.failures.append((error_code,stage,retryable,retry_delay_seconds))
        return "queued" if retryable else "failed"


class FakeStorage:
    def __init__(self,data=DATA):self.data=data
    async def download(self,path):
        assert path.endswith("/notes.txt")
        return self.data

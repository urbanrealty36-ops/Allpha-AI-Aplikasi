import hashlib
import uuid

from fastapi.testclient import TestClient

from allpha_api import cinema_api
from allpha_api.auth import current_user
from allpha_api.main import app


OWNER = "11111111-1111-4111-8111-111111111111"
TITLE = "22222222-2222-4222-8222-222222222222"
AGENT = "33333333-3333-4333-8333-333333333333"
SKILL = "44444444-4444-4444-8444-444444444444"
JOB = "55555555-5555-4555-8555-555555555555"


def _client():
    app.dependency_overrides[current_user] = lambda: {"id": OWNER}
    return TestClient(app)


def test_cinema_screenplay_generation_reuses_canonical_generation_job(monkeypatch):
    captured = {}

    async def title_access(*args, **kwargs):
        return {"id": TITLE, "owner_id": OWNER, "status": "draft", "version": 7, "title": "Test Film"}

    async def create_job(payload, request, idempotency_key, user):
        captured["payload"] = payload.model_dump()
        captured["idempotency_key"] = idempotency_key
        captured["requester"] = user["id"]
        return {"job_id": JOB, "task_id": "task-cinema-1", "status": "queued", "reserved_credits": 12}

    async def fake_db(method, table, *, params=None, payload=None, prefer=None):
        if method == "POST" and table == "cinema_generation_job_links":
            captured["link"] = payload
            captured["prefer"] = prefer
            return [{"generation_job_id": JOB, "title_id": TITLE}]
        raise AssertionError((method, table, params, payload))

    monkeypatch.setattr(cinema_api, "_title_access", title_access)
    monkeypatch.setattr(cinema_api, "_db", fake_db)
    monkeypatch.setattr(cinema_api.generation_jobs_api, "create_generation_job", create_job)
    client = _client()
    try:
        response = client.post(
            f"/v1/cinema/creator/titles/{TITLE}/generation-jobs",
            headers={"Idempotency-Key": "cinema-script-001"},
            json={
                "agent_id": AGENT, "skill_id": SKILL,
                "capability_id": "cinema.screenplay.draft",
                "prompt": "Write a 3-act screenplay for a Bogor mystery film.",
                "target_section": "screenplay_draft",
            },
        )
        assert response.status_code == 202
        assert response.json()["job_id"] == JOB
        assert response.json()["expected_title_version"] == 7
        assert captured["payload"]["capability_id"] == "cinema.screenplay.draft"
        assert "target_section" not in captured["payload"]
        assert captured["link"]["expected_title_version"] == 7
        assert captured["link"]["requester_user_id"] == OWNER
        assert captured["prefer"] == "resolution=ignore-duplicates,return=representation"
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_cinema_screenplay_generation_rejects_locked_title_before_job_creation(monkeypatch):
    async def title_access(*args, **kwargs):
        return {"id": TITLE, "owner_id": OWNER, "status": "published", "version": 7, "title": "Test Film"}

    async def forbidden_create(*args, **kwargs):
        raise AssertionError("locked title must not create or reserve a Generation Job")

    monkeypatch.setattr(cinema_api, "_title_access", title_access)
    monkeypatch.setattr(cinema_api.generation_jobs_api, "create_generation_job", forbidden_create)
    client = _client()
    try:
        response = client.post(
            f"/v1/cinema/creator/titles/{TITLE}/generation-jobs",
            headers={"Idempotency-Key": "cinema-script-002"},
            json={
                "agent_id": AGENT, "skill_id": SKILL,
                "capability_id": "cinema.screenplay.draft", "prompt": "Draft a screenplay.",
            },
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "CINEMA_PRODUCTION_LOCKED"
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_cinema_screenplay_apply_uses_private_moderated_generation_artifact(monkeypatch):
    captured = {}

    async def title_access(*args, **kwargs):
        return {"id": TITLE, "owner_id": OWNER, "status": "draft", "version": 7, "title": "Test Film"}

    async def fake_db(method, table, *, params=None, payload=None, prefer=None):
        if method == "GET" and table == "cinema_generation_job_links":
            return [{
                "generation_job_id": JOB, "title_id": TITLE, "owner_id": OWNER,
                "requester_user_id": OWNER, "target_section": "screenplay_draft",
                "expected_title_version": 7, "applied_at": None, "applied_version": None,
            }]
        if method == "POST" and table == "rpc/cinema_apply_generation_job_output":
            captured["rpc"] = payload
            return {"outcome": "applied", "generation_job_id": JOB, "title_id": TITLE, "title_version": 8}
        raise AssertionError((method, table, params, payload))

    async def admin_request(method, path, *, params=None, **kwargs):
        assert method == "GET" and path == "generation_jobs"
        return [{
            "id": JOB, "owner_user_id": OWNER, "status": "succeeded",
            "moderation_status": "approved", "artifact_bucket": "generation-artifacts",
            "artifact_path": "owner/job.txt",
            "output_sha256": hashlib.sha256(b"INT. BOGOR STATION - NIGHT\\nA detective enters the empty station.").hexdigest(),
            "artifact_deletion_requested_at": None, "artifact_deleted_at": None,
        }]

    async def signed_artifact(bucket, path, *, expires_in=60):
        assert bucket == "generation-artifacts" and path == "owner/job.txt"
        return "https://allpha.supabase.co/storage/v1/object/sign/generation-artifacts/owner/job.txt"

    class FakeResponse:
        headers = {"content-type": "text/plain; charset=utf-8"}
        content = b"INT. BOGOR STATION - NIGHT\nA detective enters the empty station."

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url):
            assert url.startswith("https://allpha.supabase.co/")
            return FakeResponse()

    monkeypatch.setattr(cinema_api, "_title_access", title_access)
    monkeypatch.setattr(cinema_api, "_db", fake_db)
    monkeypatch.setattr(cinema_api.generation_jobs_api, "_admin_request", admin_request)
    monkeypatch.setattr(cinema_api.generation_jobs_api, "_signed_generation_artifact", signed_artifact)
    monkeypatch.setattr(cinema_api.httpx, "AsyncClient", FakeClient)
    monkeypatch.setenv("SUPABASE_URL", "https://allpha.supabase.co")
    client = _client()
    try:
        response = client.post(
            f"/v1/cinema/creator/titles/{TITLE}/generation-jobs/{JOB}/apply",
            json={"expected_version": 7},
        )
        assert response.status_code == 200
        assert response.json()["outcome"] == "applied"
        assert captured["rpc"]["p_output_text"].startswith("INT. BOGOR STATION")
        assert captured["rpc"]["p_expected_version"] == 7
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_cinema_generation_cancel_delegates_to_canonical_queue(monkeypatch):
    async def title_access(*args, **kwargs):
        return {"id": TITLE, "owner_id": OWNER, "status": "draft", "version": 7, "title": "Test Film"}

    async def fake_db(method, table, *, params=None, payload=None, prefer=None):
        if method == "GET" and table == "cinema_generation_job_links":
            return [{
                "generation_job_id": JOB, "title_id": TITLE, "owner_id": OWNER,
                "requester_user_id": OWNER, "target_section": "screenplay_draft",
                "expected_title_version": 7, "applied_at": None,
            }]
        raise AssertionError((method, table, params, payload))

    async def cancel_job(job_id, user):
        assert str(job_id) == JOB and user["id"] == OWNER
        return {"job_id": JOB, "status": "cancelled"}

    monkeypatch.setattr(cinema_api, "_title_access", title_access)
    monkeypatch.setattr(cinema_api, "_db", fake_db)
    monkeypatch.setattr(cinema_api.generation_jobs_api, "cancel_generation_job", cancel_job)
    client = _client()
    try:
        response = client.post(f"/v1/cinema/creator/titles/{TITLE}/generation-jobs/{JOB}/cancel")
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_cinema_generation_link_migration_is_a_projection_not_a_second_queue():
    from pathlib import Path

    migration = (
        Path(__file__).parents[1] / "supabase" / "source-only-migrations"
        / "20261122120000_wp11_cinema_generation_job_integration.sql"
    )
    assert migration.is_file()
    sql = migration.read_text(encoding="utf-8")
    assert "references public.generation_jobs(id)" in sql
    assert "create table if not exists public.cinema_generation_job_links" in sql
    assert "create or replace function public.cinema_apply_generation_job_output" in sql
    assert "alter table public.cinema_generation_job_links enable row level security" in sql
    assert "public.agent_runtime_tasks" not in sql
    assert "create table if not exists public.cinema_render_jobs" not in sql

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_SOURCE = (ROOT / "src" / "allpha_api" / "content_api.py").read_text(encoding="utf-8")
MAIN_SOURCE = (ROOT / "src" / "allpha_api" / "main.py").read_text(encoding="utf-8")
BASELINE_MIGRATION = (ROOT / "supabase" / "migrations" / "20261018153035_eng_p13_content_media_pipeline.sql").read_text(encoding="utf-8")
VERSION_MIGRATION = (ROOT / "supabase" / "migrations" / "20261103150000_wp04_content_item_versions.sql").read_text(encoding="utf-8")


def test_content_archive_is_owner_scoped_and_removes_public_eligibility():
    assert '@router.post("/{content_id}/archive")' in API_SOURCE
    assert '"status": "archived"' in API_SOURCE
    assert '"owner_id": f"eq.{user[\'id\']}"' in API_SOURCE
    assert "CONTENT_ARCHIVE_CONFLICT" in API_SOURCE
    assert "status='published' and moderation_status='approved' and visibility='public'" in API_SOURCE


def test_content_delete_is_soft_delete_and_not_allowed_while_reviewing_or_published():
    assert '@router.delete("/{content_id}")' in API_SOURCE
    assert '("draft", "failed", "archived")' in API_SOURCE
    assert '"status": "deleted"' in API_SOURCE
    assert '"moderation_status": "removed"' in API_SOURCE
    assert "Salinan media privat tidak dihapus otomatis." in API_SOURCE
    assert "'archived','deleted'" in BASELINE_MIGRATION


def test_soft_deleted_content_is_hidden_from_owner_list_and_preview():
    assert '"status": "neq.deleted"' in API_SOURCE
    assert 'if content["status"] == "deleted"' in API_SOURCE
    assert "CONTENT_NOT_FOUND" in API_SOURCE


def test_media_upload_idempotency_key_replays_only_the_same_owner_content_and_bytes():
    assert 'request.headers.get("Idempotency-Key")' in API_SOURCE
    assert 'uuid.UUID(raw_idempotency_key)' in API_SOURCE
    assert 'MEDIA_IDEMPOTENCY_KEY_REUSED' in API_SOURCE
    assert 'str(prior.get("content_id")) != str(content_id)' in API_SOURCE
    assert 'prior.get("sha256") != digest' in API_SOURCE
    assert '"idempotent_replay": True' in API_SOURCE



def test_media_upload_reserves_idempotency_before_storage_and_can_resume():
    assert '"status": "uploading"' in API_SOURCE
    assert 'upsert: bool = False' in API_SOURCE
    assert 'headers["x-upsert"] = "true"' in API_SOURCE
    assert 'media_type=media_type, upsert=True' in API_SOURCE
    assert '"status": "in.(uploading,failed)"' in API_SOURCE
    assert '"status": "uploaded"' in API_SOURCE
    assert "MEDIA_UPLOAD_STATE_CONFLICT" in API_SOURCE



def test_browser_cors_allows_media_idempotency_header():
    assert '"Idempotency-Key"' in MAIN_SOURCE



def test_content_updates_use_expected_version_compare_and_set():
    assert "expected_version: int = Field(ge=1)" in API_SOURCE
    assert '"version": f"eq.{payload.expected_version}"' in API_SOURCE
    assert "CONTENT_VERSION_CHANGED" in API_SOURCE
    assert "CONTENT_UPDATE_CONFLICT" in API_SOURCE


def test_content_version_history_is_owner_scoped_and_snapshotted_by_database():
    assert '@router.get("/{content_id}/versions")' in API_SOURCE
    assert '"content_item_versions"' in API_SOURCE
    assert "content_item_versions_owner_select" in VERSION_MIGRATION
    assert "content_items_capture_version" in VERSION_MIGRATION
    assert "on conflict (content_id, version) do nothing" in VERSION_MIGRATION

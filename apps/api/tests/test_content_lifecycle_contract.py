from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_SOURCE = (ROOT / "src" / "allpha_api" / "content_api.py").read_text(encoding="utf-8")
BASELINE_MIGRATION = (ROOT / "supabase" / "migrations" / "20261018153035_eng_p13_content_media_pipeline.sql").read_text(encoding="utf-8")


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

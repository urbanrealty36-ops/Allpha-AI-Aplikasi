import uuid

from allpha_api.account_lifecycle_api import _valid_export_storage_path


USER_ID = "11111111-1111-4111-8111-111111111111"
JOB_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
LEASE_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def test_accepts_legacy_completed_export_path():
    assert _valid_export_storage_path(USER_ID, JOB_ID, f"{USER_ID}/{JOB_ID}.json.gz")


def test_accepts_lease_scoped_export_path():
    assert _valid_export_storage_path(USER_ID, JOB_ID, f"{USER_ID}/{JOB_ID}/{LEASE_ID}.json.gz")


def test_rejects_export_path_for_another_user_or_job():
    assert not _valid_export_storage_path(USER_ID, JOB_ID, f"22222222-2222-4222-8222-222222222222/{JOB_ID}/{LEASE_ID}.json.gz")
    assert not _valid_export_storage_path(USER_ID, JOB_ID, f"{USER_ID}/cccccccc-cccc-4ccc-8ccc-cccccccccccc/{LEASE_ID}.json.gz")


def test_rejects_path_traversal_and_non_uuid_lease_tokens():
    assert not _valid_export_storage_path(USER_ID, JOB_ID, f"{USER_ID}/{JOB_ID}/../other.json.gz")
    assert not _valid_export_storage_path(USER_ID, JOB_ID, f"{USER_ID}/{JOB_ID}/not-a-uuid.json.gz")

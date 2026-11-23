"""ENG-P03 account export worker lease-heartbeat regressions."""
import asyncio

from allpha_api.account_lifecycle_worker import AccountLifecycleWorker


JOB = {
    "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "user_id": "11111111-1111-4111-8111-111111111111",
    "lease_token": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    "attempts": 1,
}


def _worker():
    worker = object.__new__(AccountLifecycleWorker)
    worker.worker_id = "test-account-export-worker"
    worker.lease_heartbeat_seconds = 0.01
    return worker


def test_export_worker_renews_lease_while_snapshot_is_running():
    async def scenario():
        worker = _worker()
        snapshot_started = asyncio.Event()
        release_snapshot = asyncio.Event()
        renewals = 0
        completed = []
        uploaded = []

        async def rpc(name, payload):
            nonlocal renewals
            if name == "renew_account_export_job_lease":
                renewals += 1
                return True
            if name == "update_account_export_job_progress":
                return True
            if name == "build_my_account_export_snapshot":
                snapshot_started.set()
                await release_snapshot.wait()
                return {"schema_version": "1.0", "source_count": 1, "manifest": [{"source": "profile", "row_count": 1}], "data": {"profile": []}}
            if name == "complete_account_export_job":
                completed.append(payload)
                return True
            raise AssertionError(name)

        async def upload(path, payload):
            uploaded.append((path, payload))

        worker.rpc = rpc
        worker.upload = upload
        task = asyncio.create_task(worker.process(JOB))
        await asyncio.wait_for(snapshot_started.wait(), timeout=1)
        for _ in range(100):
            if renewals >= 2:
                break
            await asyncio.sleep(0.005)
        assert renewals >= 2, "long-running export snapshot must renew its lease"
        release_snapshot.set()
        await asyncio.wait_for(task, timeout=1)

        assert len(uploaded) == 1
        assert len(completed) == 1
        assert completed[0]["p_storage_path"] == f"{JOB['user_id']}/{JOB['id']}/{JOB['lease_token']}.json.gz"

    asyncio.run(scenario())


def test_export_worker_does_not_publish_after_lease_is_lost():
    async def scenario():
        worker = _worker()
        snapshot_started = asyncio.Event()
        release_snapshot = asyncio.Event()
        second_renewal = asyncio.Event()
        renewals = 0
        uploads = []
        calls = []

        async def rpc(name, payload):
            nonlocal renewals
            calls.append(name)
            if name == "renew_account_export_job_lease":
                renewals += 1
                if renewals == 1:
                    return True
                second_renewal.set()
                return False
            if name == "update_account_export_job_progress":
                return True
            if name == "build_my_account_export_snapshot":
                snapshot_started.set()
                await release_snapshot.wait()
                return {"schema_version": "1.0", "source_count": 0, "manifest": [], "data": {}}
            if name == "fail_account_export_job":
                return False
            raise AssertionError(f"lease-lost export must not call {name}")

        async def upload(path, payload):
            uploads.append(path)

        worker.rpc = rpc
        worker.upload = upload
        task = asyncio.create_task(worker.process(JOB))
        await asyncio.wait_for(snapshot_started.wait(), timeout=1)
        await asyncio.wait_for(second_renewal.wait(), timeout=1)
        release_snapshot.set()
        await asyncio.wait_for(task, timeout=1)

        assert uploads == []
        assert "complete_account_export_job" not in calls
        assert "fail_account_export_job" in calls

    asyncio.run(scenario())


def test_export_worker_rejects_manifest_that_omits_a_data_source():
    async def scenario():
        worker = _worker()
        uploads = []
        calls = []

        async def rpc(name, payload):
            calls.append(name)
            if name == "renew_account_export_job_lease":
                return True
            if name == "update_account_export_job_progress":
                return True
            if name == "build_my_account_export_snapshot":
                return {
                    "schema_version": "1.0",
                    "source_count": 2,
                    "manifest": [{"source": "profile", "row_count": 1}],
                    "data": {"profile": [{"id": JOB["user_id"]}]},
                }
            if name == "fail_account_export_job":
                return True
            raise AssertionError(f"incomplete snapshot must not call {name}")

        async def upload(path, payload):
            uploads.append(path)

        worker.rpc = rpc
        worker.upload = upload
        await worker.process(JOB)

        assert uploads == []
        assert "complete_account_export_job" not in calls
        assert "fail_account_export_job" in calls

    asyncio.run(scenario())


def test_export_worker_removes_lease_scoped_artifact_after_explicit_completion_rejection():
    async def scenario():
        worker = _worker()
        deleted = []
        calls = []

        async def rpc(name, payload):
            calls.append(name)
            if name == "renew_account_export_job_lease":
                return True
            if name == "update_account_export_job_progress":
                return True
            if name == "build_my_account_export_snapshot":
                return {"schema_version": "1.0", "source_count": 0, "manifest": [], "data": {}}
            if name == "complete_account_export_job":
                return False
            if name == "fail_account_export_job":
                return True
            raise AssertionError(name)

        async def upload(path, payload):
            return None

        async def delete_upload(path):
            deleted.append(path)

        worker.rpc = rpc
        worker.upload = upload
        worker.delete_upload = delete_upload
        await worker.process(JOB)

        expected = f"{JOB['user_id']}/{JOB['id']}/{JOB['lease_token']}.json.gz"
        assert deleted == [expected]
        assert "complete_account_export_job" in calls

    asyncio.run(scenario())


def test_export_worker_retains_artifact_when_completion_result_is_ambiguous():
    async def scenario():
        worker = _worker()
        deleted = []
        calls = []

        async def rpc(name, payload):
            calls.append(name)
            if name == "renew_account_export_job_lease":
                return True
            if name == "update_account_export_job_progress":
                return True
            if name == "build_my_account_export_snapshot":
                return {"schema_version": "1.0", "source_count": 0, "manifest": [], "data": {}}
            if name == "complete_account_export_job":
                raise TimeoutError("response lost after request")
            if name == "fail_account_export_job":
                return False
            raise AssertionError(name)

        async def upload(path, payload):
            return None

        async def delete_upload(path):
            deleted.append(path)

        worker.rpc = rpc
        worker.upload = upload
        worker.delete_upload = delete_upload
        await worker.process(JOB)

        assert deleted == []
        assert "complete_account_export_job" in calls

    asyncio.run(scenario())


def test_expired_export_cleanup_worker_deletes_artifact_then_confirms_database_state(monkeypatch):
    async def scenario():
        worker = _worker()
        monkeypatch.setenv('ACCOUNT_EXPORT_CLEANUP_ENABLED', 'true')
        deleted = []
        calls = []

        async def rpc(name, payload):
            calls.append((name, payload))
            if name == "enqueue_expired_account_export_artifacts":
                return 1
            if name == "claim_account_export_artifact_cleanup_jobs":
                return [{
                    "id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
                    "export_job_id": JOB["id"],
                    "storage_bucket": "account-exports",
                    "storage_path": f"{JOB['user_id']}/{JOB['id']}/{JOB['lease_token']}.json.gz",
                    "lease_token": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
                    "attempts": 1,
                }]
            if name == "complete_account_export_artifact_cleanup_job":
                return True
            raise AssertionError(name)

        async def delete_upload(path):
            deleted.append(path)

        worker.rpc = rpc
        worker.delete_upload = delete_upload
        assert await worker.cleanup_batch() == 1
        assert deleted == [f"{JOB['user_id']}/{JOB['id']}/{JOB['lease_token']}.json.gz"]
        assert calls[-1][0] == "complete_account_export_artifact_cleanup_job"

    asyncio.run(scenario())


def test_expired_export_cleanup_retries_when_storage_delete_fails(monkeypatch):
    async def scenario():
        worker = _worker()
        monkeypatch.setenv('ACCOUNT_EXPORT_CLEANUP_ENABLED', 'true')
        failed = []

        async def rpc(name, payload):
            if name == "enqueue_expired_account_export_artifacts":
                return 1
            if name == "claim_account_export_artifact_cleanup_jobs":
                return [{
                    "id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
                    "export_job_id": JOB["id"],
                    "storage_bucket": "account-exports",
                    "storage_path": f"{JOB['user_id']}/{JOB['id']}/{JOB['lease_token']}.json.gz",
                    "lease_token": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
                    "attempts": 2,
                }]
            if name == "fail_account_export_artifact_cleanup_job":
                failed.append(payload)
                return True
            raise AssertionError(name)

        async def delete_upload(path):
            raise RuntimeError("storage unavailable")

        worker.rpc = rpc
        worker.delete_upload = delete_upload
        assert await worker.cleanup_batch() == 1
        assert len(failed) == 1
        assert failed[0]["p_error_code"] == "RuntimeError"
        assert failed[0]["p_retry_seconds"] == 60

    asyncio.run(scenario())


def test_expired_export_cleanup_is_disabled_until_schema_migration_is_applied(monkeypatch):
    async def scenario():
        worker = _worker()
        calls = []

        async def rpc(name, payload):
            calls.append(name)
            return []

        worker.rpc = rpc
        monkeypatch.delenv("ACCOUNT_EXPORT_CLEANUP_ENABLED", raising=False)
        assert await worker.cleanup_batch() == 0
        assert calls == []

    asyncio.run(scenario())


def test_deletion_governance_worker_is_disabled_until_forward_migration_is_applied(monkeypatch):
    async def scenario():
        worker = _worker()
        calls = []

        async def rpc(name, payload):
            calls.append((name, payload))
            return []

        worker.rpc = rpc
        monkeypatch.delenv("ACCOUNT_DELETION_GOVERNANCE_ENABLED", raising=False)
        assert await worker.deletion_governance_batch() == 0
        assert calls == []

    asyncio.run(scenario())


def test_deletion_governance_worker_calls_service_only_evaluator():
    async def scenario():
        worker = _worker()
        calls = []

        async def rpc(name, payload):
            calls.append((name, payload))
            return [{"processed_count": 3, "blocked_count": 1, "unblocked_count": 1, "policy_pending_count": 1}]

        worker.rpc = rpc
        import os
        os.environ["ACCOUNT_DELETION_GOVERNANCE_ENABLED"] = "true"
        try:
            assert await worker.deletion_governance_batch() == 3
        finally:
            os.environ.pop("ACCOUNT_DELETION_GOVERNANCE_ENABLED", None)
        assert calls == [("evaluate_account_deletion_governance", {"p_limit": 100})]

    asyncio.run(scenario())

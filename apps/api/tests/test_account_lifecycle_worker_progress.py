import asyncio

from allpha_api.account_lifecycle_worker import AccountLifecycleWorker


def test_export_worker_persists_progress_at_real_processing_boundaries():
    worker = AccountLifecycleWorker.__new__(AccountLifecycleWorker)
    worker.lease_heartbeat_seconds = 240
    calls = []

    async def rpc(name, payload):
        calls.append((name, payload))
        if name in {"renew_account_export_job_lease", "update_account_export_job_progress", "complete_account_export_job"}:
            return True
        if name == "build_my_account_export_snapshot":
            return {
                "schema_version": "1.0",
                "manifest": [{"source": "profile", "row_count": 0}],
                "data": {"profile": []},
                "source_count": 1,
            }
        raise AssertionError(f"Unexpected worker RPC: {name}")

    async def upload(_path, _payload):
        calls.append(("storage_upload", {"path": _path}))

    worker.rpc = rpc
    worker.upload = upload

    asyncio.run(worker.process({
        "id": "8b7f60e0-3b86-4f86-9c79-5a1bca82bb11",
        "user_id": "c2e95c5e-4a8f-46a0-a5b0-28c4c05dd5f2",
        "lease_token": "1d66a3a8-9a7a-4df0-81a4-09f2a0b40f44",
        "attempts": 1,
    }))

    progress = [
        payload for name, payload in calls
        if name == "update_account_export_job_progress"
    ]
    assert [(item["p_progress_percent"], item["p_progress_stage"]) for item in progress] == [
        (10, "snapshot"),
        (50, "compress"),
        (75, "upload"),
        (90, "publishing"),
    ]
    names = [name for name, _ in calls]
    upload_index = names.index("storage_upload")
    progress_calls = [
        (index, payload["p_progress_stage"])
        for index, (name, payload) in enumerate(calls)
        if name == "update_account_export_job_progress"
    ]
    assert progress_calls[2][0] < upload_index < progress_calls[3][0]
    assert names.index("complete_account_export_job") > progress_calls[3][0]


def test_export_worker_fails_closed_when_progress_write_loses_lease():
    worker = AccountLifecycleWorker.__new__(AccountLifecycleWorker)

    async def rpc(_name, _payload):
        return False

    worker.rpc = rpc

    async def exercise():
        try:
            await worker.set_progress("job", "lease", 10, "snapshot")
        except RuntimeError as exc:
            assert str(exc) == "ACCOUNT_EXPORT_PROGRESS_NOT_RECORDED"
        else:
            raise AssertionError("Progress update must fail when the lease is not current")

    asyncio.run(exercise())

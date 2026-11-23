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
            if name == "build_my_account_export_snapshot":
                snapshot_started.set()
                await release_snapshot.wait()
                return {"schema_version": "1.0", "source_count": 1, "manifest": [], "data": {}}
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
        assert completed[0]["p_storage_path"] == f"{JOB['user_id']}/{JOB['id']}.json.gz"

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

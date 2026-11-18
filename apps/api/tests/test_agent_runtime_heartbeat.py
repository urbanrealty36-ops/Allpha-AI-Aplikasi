import asyncio

from allpha_api.agent_runtime_api import _runtime_lease_heartbeat


class ImmediateHeartbeatStop:
    def __init__(self):
        self.waited = False

    def is_set(self):
        return self.waited

    async def wait(self):
        if not self.waited:
            self.waited = True
            raise asyncio.TimeoutError
        return True


class HeartbeatStore:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def heartbeat_task(self, owner_id, task_id, lease_token, task_version, *, lease_seconds):
        self.calls.append((owner_id, task_id, lease_token, task_version, lease_seconds))
        return self.result


def test_runtime_heartbeat_renews_and_surfaces_owner_cancellation():
    async def scenario():
        stop = ImmediateHeartbeatStop()
        lost = asyncio.Event()
        cancelled = asyncio.Event()
        store = HeartbeatStore({"cancel_requested": True})
        await _runtime_lease_heartbeat(
            store, "owner-1", "task-1", "lease-1", 7, stop, lost, cancelled,
        )
        assert store.calls == [("owner-1", "task-1", "lease-1", 7, 60)]
        assert cancelled.is_set()
        assert not lost.is_set()

    asyncio.run(scenario())


def test_runtime_heartbeat_marks_lease_lost_when_database_rejects_renewal():
    async def scenario():
        stop = ImmediateHeartbeatStop()
        lost = asyncio.Event()
        cancelled = asyncio.Event()
        store = HeartbeatStore(None)
        await _runtime_lease_heartbeat(
            store, "owner-1", "task-1", "lease-1", 7, stop, lost, cancelled,
        )
        assert lost.is_set()
        assert not cancelled.is_set()

    asyncio.run(scenario())

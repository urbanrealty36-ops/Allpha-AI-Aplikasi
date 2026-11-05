import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_wp04_vercel_cron_uses_single_daily_bounded_orchestrator():
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    assert config["crons"] == [{
        "path": "/internal/cron/platform-lifecycle",
        "schedule": "17 3 * * *",
    }]


def test_wp04_vercel_orchestrator_never_starts_daemon_workers():
    source = (ROOT / "src" / "allpha_api" / "wp04_vercel_cron.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    attribute_calls = [node.func.attr for node in calls if isinstance(node.func, ast.Attribute)]
    getattr_calls = [node for node in calls if isinstance(node.func, ast.Name) and node.func.id == "getattr"]
    worker_method_names = {node.args[1].value for node in getattr_calls
                           if len(node.args) > 1 and isinstance(node.args[1], ast.Constant)}
    assert {"batch", "process_batch"}.issubset(worker_method_names)
    assert "run" not in worker_method_names
    assert "approved_scanner_adapter_not_configured" in source or "CLAMAV_HOST" in source
    assert "status\": \"deferred\"" in source
    assert "enqueue_expired_content_retention_jobs" in source
    for gate in ("CONTENT_RETENTION_PURGE_ENABLED", "CONTENT_RETENTION_BACKUP_VERIFIED",
                 "CONTENT_RETENTION_RESTORE_DRILL_VERIFIED", "CONTENT_RETENTION_LEGAL_HOLD_VERIFIED",
                 "CONTENT_RETENTION_APPROVAL_VERIFIED"):
        assert gate in source


def test_wp04_platform_cron_is_authenticated_and_runs_bounded_wp04_batches():
    source = (ROOT / "src" / "allpha_api" / "main.py").read_text(encoding="utf-8")
    assert '@app.get("/internal/cron/platform-lifecycle"' in source
    assert 'hmac.compare_digest(authorization, f"Bearer {secret}")' in source
    assert "run_wp04_vercel_batches" in source

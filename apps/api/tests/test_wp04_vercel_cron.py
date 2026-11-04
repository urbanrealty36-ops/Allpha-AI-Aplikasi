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
    called = [node.func.attr for node in calls if isinstance(node.func, ast.Attribute)]
    assert "batch" in called
    assert "run" not in called
    assert "approved_scanner_adapter_not_configured" in source
    assert 'os.getenv("CONTENT_RETENTION_PURGE_ENABLED", "false")' in source


def test_wp04_platform_cron_is_authenticated_and_runs_bounded_wp04_batches():
    source = (ROOT / "src" / "allpha_api" / "main.py").read_text(encoding="utf-8")
    assert '@app.get("/internal/cron/platform-lifecycle"' in source
    assert 'hmac.compare_digest(authorization, f"Bearer {secret}")' in source
    assert "run_wp04_vercel_batches" in source

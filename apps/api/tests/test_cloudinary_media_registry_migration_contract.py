from __future__ import annotations

import re
from pathlib import Path


def test_cloudinary_media_registry_allows_terminal_deleted_state():
    migration = (
        Path(__file__).parents[1]
        / "supabase"
        / "source-only-migrations"
        / "20261125190000_eng_p13_cloudinary_media_registry.sql"
    ).read_text(encoding="utf-8")

    match = re.search(
        r"add constraint content_media_status_check\s+check\s*\(status in \((.*?)\)\)",
        migration,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match is not None
    assert "'deleted'" in match.group(1)

    readiness = re.search(
        r"content_media_status_check'\s*,\s*'deleted'",
        migration,
        flags=re.IGNORECASE,
    )
    assert readiness is not None

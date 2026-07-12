"""Tests for log store and report helpers."""

from __future__ import annotations

import asyncio
from pathlib import Path

from blender_ai_sidecar import app_log
from blender_ai_sidecar.store.db import Database


def test_log_and_report_roundtrip(tmp_path: Path):
    async def run():
        db = Database(tmp_path / "test.sqlite")
        await db.connect()
        entry = await app_log.emit(
            db,
            "error",
            "sidecar",
            "boom",
            component="test",
            detail={"x": 1},
        )
        assert entry["level"] == "error"
        logs = await db.list_logs(level="error")
        assert any(l["message"] == "boom" for l in logs)

        report = await app_log.create_report(
            db,
            tmp_path,
            kind="crash",
            source="test",
            summary="unit crash",
            detail={"traceback": "Traceback..."},
        )
        assert report["id"]
        assert Path(report["file_path"]).is_file()
        listed = await db.list_reports()
        assert any(r["summary"] == "unit crash" for r in listed)
        await db.clear_logs()
        assert await db.list_logs() == []
        await db.close()

    asyncio.run(run())

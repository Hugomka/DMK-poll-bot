# tests/test_logger.py

import io
import json
from contextlib import redirect_stdout

from apps.utils import logger as lg
from tests.base import BaseTestCase


class TestLogger(BaseTestCase):
    async def test_log_job_prints_and_counts(self):
        # Start met een schone tellerstand
        lg._metrics = {"jobs_executed": 0, "jobs_skipped": 0, "jobs_failed": 0}

        # 1) Executed
        buf = io.StringIO()
        with redirect_stdout(buf):
            lg.log_job(job="update_all_polls", channel_id=123, status="executed")
        out1 = json.loads(buf.getvalue())

        # Gecontroleerde velden aanwezig
        assert out1["job"] == "update_all_polls"
        assert out1["status"] == "executed"
        assert out1["channel_id"] == 123
        # Velden die None waren, ontbreken in de JSON
        assert "guild_id" not in out1
        assert "user_id" not in out1
        assert "message_id" not in out1
        # Timestamp bestaat (waarde maakt niet uit)
        assert "timestamp" in out1

        # Teller geüpdatet
        m = lg.get_metrics()
        assert m["jobs_executed"] == 1
        assert m["jobs_skipped"] == 0
        assert m["jobs_failed"] == 0

        # 2) Skipped
        buf = io.StringIO()
        with redirect_stdout(buf):
            lg.log_job(job="notify", dag="vrijdag", status="skipped")
        out2 = json.loads(buf.getvalue())
        assert out2["job"] == "notify"
        assert out2["status"] == "skipped"
        assert out2["dag"] == "vrijdag"

        m = lg.get_metrics()
        assert m["jobs_executed"] == 1
        assert m["jobs_skipped"] == 1
        assert m["jobs_failed"] == 0

        # 3) Failed
        buf = io.StringIO()
        with redirect_stdout(buf):
            lg.log_job(job="reset_polls", status="failed", attempt=2, duration=0.5)
        out3 = json.loads(buf.getvalue())
        assert out3["job"] == "reset_polls"
        assert out3["status"] == "failed"
        assert out3["attempt"] == 2
        assert out3["duration"] == 0.5

        m = lg.get_metrics()
        assert m["jobs_executed"] == 1
        assert m["jobs_skipped"] == 1
        assert m["jobs_failed"] == 1

    async def test_log_startup_prints_json(self):
        missed = ["update_all_polls", "notify_vrijdag", "notify_zaterdag"]
        buf = io.StringIO()
        with redirect_stdout(buf):
            lg.log_startup(missed)
        out = json.loads(buf.getvalue())
        assert out["event"] == "startup"
        assert out["missed_jobs"] == missed
        assert "timestamp" in out

    async def test_get_metrics_returns_copy(self):
        # Zet een bekende staat
        lg._metrics = {"jobs_executed": 2, "jobs_skipped": 3, "jobs_failed": 4}

        snap = lg.get_metrics()
        # Wijzig de snapshot — originele _metrics mag niet wijzigen
        snap["jobs_executed"] = 999

        # Nieuwe snapshot ophalen: moet de originele waarden tonen
        snap2 = lg.get_metrics()
        assert snap2["jobs_executed"] == 2
        assert snap2["jobs_skipped"] == 3
        assert snap2["jobs_failed"] == 4

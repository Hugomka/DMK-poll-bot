# tests/test_scheduler_state_io.py

import json
import os
import tempfile
import unittest
from unittest.mock import mock_open, patch

from apps import scheduler


class SchedulerStateIOTestCase(unittest.IsolatedAsyncioTestCase):
    """Tests voor state I/O helpers (_read_state en _write_state)."""

    async def test_read_state_corrupt_or_missing_returns_empty_dict(self):
        """Test dat _read_state leeg dict teruggeeft bij corrupt/missing bestand."""

        # Test 1: Bestand bestaat niet
        with patch.object(scheduler, "STATE_PATH", "/nope/does-not-exist.json"):
            result = scheduler._read_state()
            self.assertEqual(result, {})

        # Test 2: Corrupt JSON
        corrupt_json = "{ this is not valid json }"
        m = mock_open(read_data=corrupt_json)
        with (
            patch.object(scheduler, "STATE_PATH", "test.json"),
            patch("builtins.open", m),
        ):
            result = scheduler._read_state()
            self.assertEqual(result, {})

        # Test 3: Andere exception tijdens lezen
        def fake_open(*_args, **_kwargs):
            raise PermissionError("no access")

        with (
            patch.object(scheduler, "STATE_PATH", "test.json"),
            patch("builtins.open", side_effect=fake_open),
        ):
            result = scheduler._read_state()
            self.assertEqual(result, {})

    async def test_write_state_happy_path(self):
        """Test dat _write_state correct schrijft via .tmp → replace."""

        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = os.path.join(tmpdir, "state.json")
            state_data = {
                "update_all_polls": "2024-05-27T18:00:00",
                "reset_polls": "2024-05-28T20:00:00",
            }

            with patch.object(scheduler, "STATE_PATH", state_path):
                scheduler._write_state(state_data)

            # Assert: Bestand bestaat
            self.assertTrue(os.path.exists(state_path))

            # Assert: .tmp bestand is verwijderd (via os.replace)
            tmp_path = f"{state_path}.tmp"
            self.assertFalse(os.path.exists(tmp_path))

            # Assert: Inhoud klopt
            with open(state_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            self.assertEqual(loaded, state_data)


if __name__ == "__main__":
    unittest.main()

# tests/test_zichtbaarheid.py

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from apps.utils.poll_settings import should_hide_counts, toggle_visibility, reset_settings

class TestZichtbaarheid(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        reset_settings()
        self.channel_id = 123456789
        self.dag = "vrijdag"

    async def test_default_zichtbaarheid_altijd(self):
        nu = datetime(2025, 8, 16, 12, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))  # zaterdag
        self.assertFalse(should_hide_counts(self.channel_id, self.dag, nu))

    async def test_deadline_voor_18u(self):
        toggle_visibility(self.channel_id, self.dag, tijd="18:00")
        nu = datetime(2025, 8, 15, 17, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))  # vrijdag 17:00
        self.assertTrue(should_hide_counts(self.channel_id, self.dag, nu))

    async def test_deadline_na_18u(self):
        toggle_visibility(self.channel_id, self.dag, tijd="18:00")
        nu = datetime(2025, 8, 15, 19, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))  # vrijdag 19:00
        self.assertFalse(should_hide_counts(self.channel_id, self.dag, nu))

    async def test_onbekende_dag_geeft_false(self):
        nu = datetime(2025, 8, 16, 12, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
        self.assertFalse(should_hide_counts(self.channel_id, "maansdag", nu))  # dag bestaat niet

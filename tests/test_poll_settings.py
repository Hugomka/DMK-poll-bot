# tests/test_poll_settings.py

import os
from datetime import datetime, timedelta

from apps.utils import poll_settings
from tests.base import BaseTestCase


class TestPollSettings(BaseTestCase):
    # Helpers
    def _dt_for_weekday(
        self, weekday: int, hour: int = 12, minute: int = 0
    ) -> datetime:
        """
        Maak een datetime met gewenste weekday (ma=0 … zo=6) in dezelfde week.
        We nemen vandaag als basis en schuiven naar de juiste weekday.
        """
        today = datetime.now()
        diff = weekday - today.weekday()
        base = today + timedelta(days=diff)
        return base.replace(hour=hour, minute=minute, second=0, microsecond=0)

    #  _load_data: JSONDecodeError → pass
    async def test_load_data_corrupt_file_uses_defaults(self):
        # Schrijf expres kapotte JSON naar SETTINGS_FILE
        settings_path = os.environ["SETTINGS_FILE"]
        with open(settings_path, "w", encoding="utf-8") as f:
            f.write("{ dit is geen geldige json")

        # get_setting triggert _load_data → JSONDecodeError-pad → {}
        instelling = poll_settings.get_setting(channel_id=123, dag="vrijdag")
        self.assertEqual(instelling, {"modus": "deadline", "tijd": "18:00"})

    #  set_visibility: modus == 'altijd'
    async def test_set_visibility_altijd_forces_1800(self):
        result = poll_settings.set_visibility(
            1, "vrijdag", modus="altijd", tijd="12:34"
        )
        self.assertEqual(result, {"modus": "altijd", "tijd": "18:00"})
        # opgeslagen waarde checken
        saved = poll_settings.get_setting(1, "vrijdag")
        self.assertEqual(saved, {"modus": "altijd", "tijd": "18:00"})

    #  should_hide_counts: modus == 'altijd' → False
    async def test_should_hide_counts_altijd_returns_false(self):
        poll_settings.set_visibility(1, "zaterdag", modus="altijd")
        now = self._dt_for_weekday(poll_settings.DAYS_INDEX["zaterdag"], 10, 0)
        self.assertFalse(poll_settings.should_hide_counts(1, "zaterdag", now))

    #  should_hide_counts: ongeldige tijd → fallback 18:00
    async def test_should_hide_counts_invalid_time_uses_default_1800(self):
        # Stel een niet-parsbare tijd in
        poll_settings.set_visibility(1, "vrijdag", modus="deadline", tijd="xx:yy")
        # Neem vrijdag om 17:59 → nog verbergen (gebruikt fallback 18:00)
        now = self._dt_for_weekday(poll_settings.DAYS_INDEX["vrijdag"], 17, 59)
        self.assertTrue(poll_settings.should_hide_counts(1, "vrijdag", now))

    #  should_hide_counts: onbekende dag → False
    async def test_should_hide_counts_unknown_day_returns_false(self):
        poll_settings.set_visibility(1, "vrijdag", modus="deadline", tijd="18:00")
        now = self._dt_for_weekday(poll_settings.DAYS_INDEX["vrijdag"], 12, 0)
        self.assertFalse(poll_settings.should_hide_counts(1, "onbekendedag", now))

    #  should_hide_counts: huidige_idx > target_idx → False
    async def test_should_hide_counts_after_day_returns_false(self):
        # Stel dinsdag als deadline-dag in
        poll_settings.set_visibility(1, "dinsdag", modus="deadline", tijd="18:00")
        # Kies donderdag (3) als 'nu' → na de dag (1) ⇒ False
        now = self._dt_for_weekday(3, 10, 0)  # donderdag
        self.assertFalse(poll_settings.should_hide_counts(1, "dinsdag", now))

    #  is_paused / set_paused (95-99) & toggle_paused
    async def test_paused_set_and_toggle(self):
        # default: niet gepauzeerd
        self.assertFalse(poll_settings.is_paused(42))

        # set True
        self.assertTrue(poll_settings.set_paused(42, True))
        self.assertTrue(poll_settings.is_paused(42))

        # set False
        self.assertFalse(poll_settings.set_paused(42, False))
        self.assertFalse(poll_settings.is_paused(42))

        # toggle: False → True
        self.assertTrue(poll_settings.toggle_paused(42))
        self.assertTrue(poll_settings.is_paused(42))

        # toggle: True → False
        self.assertFalse(poll_settings.toggle_paused(42))
        self.assertFalse(poll_settings.is_paused(42))

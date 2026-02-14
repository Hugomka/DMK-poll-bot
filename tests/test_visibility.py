# tests/test_visibility.py

import unittest
from datetime import date, datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from apps.logic.visibility import (
    _has_explicit_setting,
    is_vote_button_visible,
)
from apps.utils.poll_settings import set_visibility
from tests.base import BaseTestCase

AMS = ZoneInfo("Europe/Amsterdam")


class DummyOpt:
    def __init__(self, dag: str, tijd: str):
        self.dag = dag
        self.tijd = tijd
        self.emoji = "🟢"


class TestVisibilityButtons(BaseTestCase):

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.channel_id = 999_888
        self.vrijdag = "vrijdag"
        self.zaterdag = "zaterdag"
        self.zondag = "zondag"

    # ---- Bewaker & dagrelatie ----

    async def test_unknown_day_returns_false(self):
        now = datetime(2025, 8, 15, 12, 0, tzinfo=AMS)  # Vrijdag
        self.assertFalse(
            is_vote_button_visible(self.channel_id, "moonsday", "om 19:00 uur", now)
        )

    async def test_past_day_buttons_hidden(self):
        now = datetime(2025, 8, 16, 12, 0, tzinfo=AMS)  # Zaterdag
        # Vraag is voor vrijdag terwijl het al zaterdag is
        self.assertFalse(
            is_vote_button_visible(self.channel_id, self.vrijdag, "om 19:00 uur", now)
        )

    async def test_future_day_buttons_visible(self):
        now = datetime(2025, 8, 15, 12, 0, tzinfo=AMS)  # Vrijdag
        # Vraag is voor zaterdag terwijl het nog vrijdag is
        self.assertTrue(
            is_vote_button_visible(self.channel_id, self.zaterdag, "om 19:00 uur", now)
        )

    # ---- Dezelfde dag, normale tijden ----

    async def test_same_day_1900_before_and_after(self):
        # Vrijdag: 18:59 -> zichtbaar; 19:00 -> uit
        before = datetime(2025, 8, 15, 18, 59, tzinfo=AMS)
        after = datetime(2025, 8, 15, 19, 0, tzinfo=AMS)
        self.assertTrue(
            is_vote_button_visible(
                self.channel_id, self.vrijdag, "om 19:00 uur", before
            )
        )
        self.assertFalse(
            is_vote_button_visible(self.channel_id, self.vrijdag, "om 19:00 uur", after)
        )

    async def test_same_day_2030_before_and_after(self):
        # Vrijdag: 20:29 -> zichtbaar; 20:30 -> uit
        before = datetime(2025, 8, 15, 20, 29, tzinfo=AMS)
        after = datetime(2025, 8, 15, 20, 30, tzinfo=AMS)
        self.assertTrue(
            is_vote_button_visible(
                self.channel_id, self.vrijdag, "om 20:30 uur", before
            )
        )
        self.assertFalse(
            is_vote_button_visible(self.channel_id, self.vrijdag, "om 20:30 uur", after)
        )

    # ---- Specials ("misschien" en "niet meedoen") ----

    async def test_specials_visible_until_next_slot_then_off(self):
        # Met standaard opties bestaat 20:30, dus na 19:00 maar vóór 20:30 nog zichtbaar
        at_1910 = datetime(2025, 8, 15, 19, 10, tzinfo=AMS)
        self.assertTrue(
            is_vote_button_visible(self.channel_id, self.vrijdag, "misschien", at_1910)
        )

        # Na het laatste slot (20:31) moeten specials uit
        at_2031 = datetime(2025, 8, 15, 20, 31, tzinfo=AMS)
        self.assertFalse(
            is_vote_button_visible(self.channel_id, self.vrijdag, "misschien", at_2031)
        )

    async def test_specials_no_times_available_returns_false(self):
        # Patch get_poll_options zodat er GEEN tijden voor vrijdag zijn
        with patch(
            "apps.logic.visibility.get_poll_options",
            return_value=[DummyOpt("zaterdag", "om 19:00 uur")],
        ):
            now = datetime(2025, 8, 15, 12, 0, tzinfo=AMS)  # vrijdag
            self.assertFalse(
                is_vote_button_visible(self.channel_id, self.vrijdag, "misschien", now)
            )

    # ---- Expliciete deadline gedrag ----

    async def test_explicit_deadline_cuts_all_buttons_after_deadline(self):
        # Admin zet expliciet deadline op 18:00
        set_visibility(self.channel_id, self.vrijdag, modus="deadline", tijd="18:00")
        at_1800 = datetime(2025, 8, 15, 18, 0, tzinfo=AMS)
        # Normale tijd
        self.assertFalse(
            is_vote_button_visible(
                self.channel_id, self.vrijdag, "om 20:30 uur", at_1800
            )
        )
        # Specials ook uit
        self.assertFalse(
            is_vote_button_visible(self.channel_id, self.vrijdag, "misschien", at_1800)
        )

    async def test_explicit_deadline_before_deadline_still_allows_buttons(self):
        set_visibility(self.channel_id, self.vrijdag, modus="deadline", tijd="18:00")
        at_1700 = datetime(2025, 8, 15, 17, 0, tzinfo=AMS)
        self.assertTrue(
            is_vote_button_visible(
                self.channel_id, self.vrijdag, "om 20:30 uur", at_1700
            )
        )
        self.assertTrue(
            is_vote_button_visible(self.channel_id, self.vrijdag, "misschien", at_1700)
        )

    async def test_explicit_deadline_invalid_time_parses_to_1800(self):
        # Zet een ongeldige tijd → parser valt terug op 18:00
        set_visibility(self.channel_id, self.vrijdag, modus="deadline", tijd="abc")
        at_1801 = datetime(2025, 8, 15, 18, 1, tzinfo=AMS)
        self.assertFalse(
            is_vote_button_visible(
                self.channel_id, self.vrijdag, "om 20:30 uur", at_1801
            )
        )

    # ---- _has_explicit_setting coverage ----

    async def test_has_explicit_setting_true_and_false(self):
        # False zonder opgeslagen instelling (BaseTestCase already uses temp file)
        self.assertFalse(_has_explicit_setting(self.channel_id, self.vrijdag))

        # True na set_visibility
        set_visibility(self.channel_id, self.vrijdag, modus="deadline", tijd="18:00")
        self.assertTrue(_has_explicit_setting(self.channel_id, self.vrijdag))

    async def test_has_explicit_setting_when_loader_is_none(self):
        # Patch loader naar None → functie moet False retourneren
        import apps.logic.visibility as vis

        original = getattr(vis, "_load_settings_data", None)
        try:
            setattr(vis, "_load_settings_data", None)
            self.assertFalse(_has_explicit_setting(self.channel_id, self.vrijdag))
        finally:
            setattr(vis, "_load_settings_data", original)

    async def test_has_explicit_setting_when_loader_raises_exception(self):
        # Forceer exception in _load_settings_data → except-pad (return False)
        import apps.logic.visibility as vis

        def boom():
            raise RuntimeError("boom")

        original = getattr(vis, "_load_settings_data", None)
        try:
            setattr(vis, "_load_settings_data", boom)
            self.assertFalse(_has_explicit_setting(self.channel_id, self.vrijdag))
        finally:
            setattr(vis, "_load_settings_data", original)

    # ---- Exceptietakken binnen is_vote_button_visible ----

    async def test_is_visible_handles_get_setting_exception(self):
        # Zorg dat er een expliciete setting is, zodat we in de try/except komen
        set_visibility(self.channel_id, self.vrijdag, modus="deadline", tijd="18:00")
        with patch(
            "apps.logic.visibility.get_setting", side_effect=RuntimeError("fail")
        ):
            # Voor 20:30 en zonder bruikbaar setting-object valt hij terug op {} en gaat door op tijdslot-logica
            now = datetime(2025, 8, 15, 17, 0, tzinfo=AMS)
            self.assertTrue(
                is_vote_button_visible(
                    self.channel_id, self.vrijdag, "om 20:30 uur", now
                )
            )

    async def test_is_visible_handles_get_poll_options_exception(self):
        with patch(
            "apps.logic.visibility.get_poll_options", side_effect=RuntimeError("kapot")
        ):
            # Specials met exception → tijden = [] → False
            now = datetime(2025, 8, 15, 19, 10, tzinfo=AMS)
            self.assertFalse(
                is_vote_button_visible(self.channel_id, self.vrijdag, "misschien", now)
            )


    # ---- Twee-periodesysteem: datum-parameter ----

    async def test_cross_period_maandag_visible_on_zaterdag_with_datum(self):
        """Op zaterdag moet maandag (volgende week) zichtbaar zijn als datum is meegegeven."""
        # Zaterdag 16 aug 2025
        now = datetime(2025, 8, 16, 22, 0, tzinfo=AMS)
        # Maandag 18 aug 2025 (volgende week, in de toekomst)
        maandag_datum = date(2025, 8, 18)
        self.assertTrue(
            is_vote_button_visible(
                self.channel_id, "maandag", "om 19:00 uur", now, datum=maandag_datum
            )
        )

    async def test_cross_period_maandag_hidden_on_zaterdag_without_datum(self):
        """Zonder datum valt maandag (index 0) < zaterdag (index 5) → verborgen (backwards compat)."""
        now = datetime(2025, 8, 16, 22, 0, tzinfo=AMS)
        self.assertFalse(
            is_vote_button_visible(
                self.channel_id, "maandag", "om 19:00 uur", now
            )
        )

    async def test_datum_in_past_returns_false(self):
        """Een dag met een datum in het verleden moet onzichtbaar zijn."""
        now = datetime(2025, 8, 16, 12, 0, tzinfo=AMS)  # Zaterdag
        vrijdag_datum = date(2025, 8, 15)  # Gisteren
        self.assertFalse(
            is_vote_button_visible(
                self.channel_id, self.vrijdag, "om 19:00 uur", now, datum=vrijdag_datum
            )
        )

    async def test_datum_today_falls_through_to_time_logic(self):
        """Datum == vandaag moet doorvallen naar de zelfde-dag tijdlogica."""
        # Vrijdag 15 aug, 18:59 → 19:00-knop nog zichtbaar
        now_before = datetime(2025, 8, 15, 18, 59, tzinfo=AMS)
        today = date(2025, 8, 15)
        self.assertTrue(
            is_vote_button_visible(
                self.channel_id, self.vrijdag, "om 19:00 uur", now_before, datum=today
            )
        )
        # Vrijdag 15 aug, 19:00 → 19:00-knop uit
        now_after = datetime(2025, 8, 15, 19, 0, tzinfo=AMS)
        self.assertFalse(
            is_vote_button_visible(
                self.channel_id, self.vrijdag, "om 19:00 uur", now_after, datum=today
            )
        )

    async def test_cross_period_all_weekdays_visible_on_zaterdag(self):
        """Op zaterdag moeten alle ma-do dagen zichtbaar zijn met juiste datums."""
        now = datetime(2025, 8, 16, 22, 0, tzinfo=AMS)  # Zaterdag
        for dag, dag_date in [
            ("maandag", date(2025, 8, 18)),
            ("dinsdag", date(2025, 8, 19)),
            ("woensdag", date(2025, 8, 20)),
            ("donderdag", date(2025, 8, 21)),
        ]:
            with self.subTest(dag=dag):
                self.assertTrue(
                    is_vote_button_visible(
                        self.channel_id, dag, "om 19:00 uur", now, datum=dag_date
                    )
                )


if __name__ == "__main__":
    unittest.main()

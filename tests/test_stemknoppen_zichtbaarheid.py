# tests\test_stemknoppen_zichtbaarheid.py

from datetime import datetime
from zoneinfo import ZoneInfo
from apps.logic.visibility import is_vote_button_visible
from apps.utils.poll_settings import reset_settings, set_visibility
from tests.base import BaseTestCase


class TestStemknopZichtbaarheid(BaseTestCase):

    async def asyncSetUp(self):
        await super().asyncSetUp()
        reset_settings()
        self.channel_id = 123456
        self.dag = "vrijdag"

    # 🎯 Voorbeeld: vrijdag 18:00, stemmen voor 20:30 mag nog
    def test_knop_is_zichtbaar_voor_deadline(self):
        now = datetime(2025, 8, 22, 18, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
        zichtbaar = is_vote_button_visible(self.channel_id, self.dag, "om 20:30 uur", now)
        self.assertTrue(zichtbaar)

    # ⛔ Voorbeeld: zaterdag 00:00, vrijdag is al voorbij
    def test_knop_is_onzichtbaar_na_deadline(self):
        # Vrijdag 29 aug 2025 om 21:00 → ná de deadline voor vrijdag 20:30
        now = datetime(2025, 8, 29, 21, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
        zichtbaar = is_vote_button_visible(self.channel_id, self.dag, "om 20:30 uur", now)
        self.assertFalse(zichtbaar)

    # ⛔ Bij zichtbaarheidstype "deadline" worden knoppen direct verborgen op deadline
    def test_alle_knoppen_verbergen_bij_zichtbaarheid_deadline(self):
        set_visibility(self.channel_id, self.dag, modus="deadline", tijd="18:00")
        now = datetime(2025, 8, 22, 18, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
        zichtbaar = is_vote_button_visible(self.channel_id, self.dag, "om 20:30 uur", now)
        self.assertFalse(zichtbaar)

    # ⛔ Specials ("misschien", "niet meedoen") zijn ook verlopen na hun dag
    def test_specials_ook_verlopen_na_dag(self):
        now = datetime(2025, 8, 17, 18, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))  # zondag
        zichtbaar = is_vote_button_visible(self.channel_id, "vrijdag", "misschien", now)
        self.assertFalse(zichtbaar)

        zichtbaar2 = is_vote_button_visible(self.channel_id, "zaterdag", "niet meedoen", now)
        self.assertFalse(zichtbaar2)

    # ✅ Specials zijn zichtbaar zolang dag nog bezig is (voor sluiting)
    def test_specials_zichtbaar_voor_deadline(self):
        now = datetime(2025, 8, 17, 18, 55, tzinfo=ZoneInfo("Europe/Amsterdam"))  # zondag
        zichtbaar = is_vote_button_visible(self.channel_id, "zondag", "misschien", now)
        self.assertTrue(zichtbaar)

        zichtbaar2 = is_vote_button_visible(self.channel_id, "zondag", "niet meedoen", now)
        self.assertTrue(zichtbaar2)

    # ✅ Na 19:00 mag je nog stemmen voor 20:30 → specials ook nog zichtbaar
    def test_specials_zichtbaar_na_1900_maar_voor_2030(self):
        now = datetime(2025, 8, 17, 19, 1, tzinfo=ZoneInfo("Europe/Amsterdam"))
        zichtbaar1 = is_vote_button_visible(self.channel_id, "zondag", "misschien", now)
        zichtbaar2 = is_vote_button_visible(self.channel_id, "zondag", "niet meedoen", now)
        self.assertTrue(zichtbaar1)
        self.assertTrue(zichtbaar2)

    # ⛔ Na 20:30 is alles verlopen, ook specials
    def test_specials_verlopen_na_laatste_tijdslot(self):
        now = datetime(2025, 8, 17, 20, 31, tzinfo=ZoneInfo("Europe/Amsterdam"))
        zichtbaar = is_vote_button_visible(self.channel_id, "zondag", "misschien", now)
        self.assertFalse(zichtbaar)

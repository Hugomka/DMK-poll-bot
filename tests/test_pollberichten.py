# tests\test_pollberichten.py

from apps.utils.poll_message import build_poll_message_for_day_async
from apps.utils.poll_settings import reset_settings
from apps.utils.poll_storage import reset_votes
from tests.base import BaseTestCase

class TestPollBerichten(BaseTestCase):

    async def asyncSetUp(self):
        await super().asyncSetUp()
        await reset_votes()
        reset_settings()

    async def test_pollbericht_zonder_stemmen(self):
        bericht = await build_poll_message_for_day_async("vrijdag", hide_counts=False, pauze=False)
        self.assertIn("vrijdag", bericht.lower())
        self.assertIn("0 stemmen", bericht)

    async def test_pollbericht_met_pauze(self):
        bericht = await build_poll_message_for_day_async("zaterdag", hide_counts=False, pauze=True)
        self.assertIn("gepauzeerd", bericht.lower())

    async def test_pollbericht_verbergt_aantallen(self):
        bericht = await build_poll_message_for_day_async("zondag", hide_counts=True, pauze=False)
        self.assertIn("stemmen verborgen", bericht.lower())

    async def test_pollbericht_met_geen_opties(self):
        from unittest.mock import patch

        with patch("apps.utils.message_builder.get_poll_options", return_value=[]):
            bericht = await build_poll_message_for_day_async("vrijdag", hide_counts=False, pauze=False)
            self.assertIn("geen opties gevonden", bericht.lower())

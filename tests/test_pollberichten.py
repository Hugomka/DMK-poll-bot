# tests/test_pollberichten.py

import unittest
from apps.utils.poll_message import build_poll_message_for_day_async
from apps.utils.poll_settings import reset_settings
from apps.utils.poll_storage import reset_votes, toggle_vote
from apps.utils.poll_settings import toggle_name_display
from unittest.mock import AsyncMock, MagicMock, patch

class TestPollBerichten(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
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

    async def test_pollbericht_met_namen_weergegeven(self):
        # Zet de instelling aan voor tonen van namen
        kanaal_id = 123456
        toggle_name_display(kanaal_id)  # zet op True

        # Simuleer een stem
        await toggle_vote("111", "vrijdag", "om 19:00 uur")

        # Mock een guild en member
        mock_guild = MagicMock()
        mock_member = MagicMock()
        mock_member.mention = "@Goldway"
        mock_guild.get_member.return_value = mock_member
        mock_guild.id = kanaal_id

        bericht = await build_poll_message_for_day_async(
            "vrijdag",
            hide_counts=False,
            pauze=False,
            guild=mock_guild
        )

        self.assertIn("om 19:00 uur", bericht)
        self.assertIn("@Goldway", bericht)

    async def test_pollbericht_met_namen_uit(self):
        kanaal_id = 123456
        toggle_name_display(kanaal_id)  # eerst aan
        toggle_name_display(kanaal_id)  # weer uit

        await toggle_vote("222", "zaterdag", "om 20:30 uur")

        mock_guild = MagicMock()
        mock_member = MagicMock()
        mock_member.mention = "@Rick"
        mock_guild.get_member.return_value = mock_member
        mock_guild.id = kanaal_id

        bericht = await build_poll_message_for_day_async(
            "zaterdag",
            hide_counts=False,
            pauze=False,
            guild=mock_guild
        )

        self.assertIn("om 20:30 uur", bericht)
        self.assertNotIn("@Rick", bericht)  # naam mag niet zichtbaar zijn

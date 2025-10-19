# tests/test_guests.py

import unittest
from unittest.mock import AsyncMock, MagicMock

from apps.commands.poll_status import PollStatus
from apps.utils.poll_storage import (
    add_guest_votes,
    get_votes_for_option,
    load_votes,
    remove_guest_votes,
    toggle_vote,
)
from tests.base import BaseTestCase

DAG = "vrijdag"
TIJD = "om 20:30 uur"
OWNER = "111"  # String is prima; poll_storage gebruikt strings als keys


class TestGasten(BaseTestCase):

    async def asyncSetUp(self):
        await super().asyncSetUp()
        # Cog + bot mock
        self.mock_bot = MagicMock()
        self.cog = PollStatus(self.mock_bot)

    # --- /gast-add: gasten worden toegevoegd en tellen mee ---
    async def test_gast_add_telt_mee(self):
        # Voeg 2 gasten toe
        toegevoegd, overgeslagen = await add_guest_votes(
            OWNER, DAG, TIJD, ["Toad", "Luigi"], 1, 123
        )

        self.assertEqual(sorted(toegevoegd), ["Luigi", "Toad"])
        self.assertEqual(overgeslagen, [])

        # Controleren dat ze in votes zitten
        votes = await load_votes(1, 123)
        self.assertIn(f"{OWNER}_guest::Toad", votes)
        self.assertIn(f"{OWNER}_guest::Luigi", votes)
        self.assertIn(TIJD, votes[f"{OWNER}_guest::Toad"][DAG])
        self.assertIn(TIJD, votes[f"{OWNER}_guest::Luigi"][DAG])

        # Aantal stemmen voor dit slot = 2 (alleen gasten)
        count = await get_votes_for_option(DAG, TIJD, 1, 123)
        self.assertEqual(count, 2)

    # --- /gast-remove: specifieke namen worden verwijderd ---
    async def test_gast_remove_verwijdert_correct(self):
        # Start met drie gasten
        await add_guest_votes(OWNER, DAG, TIJD, ["Toad", "Luigi", "Peach"], 1, 123)

        # Verwijder er twee
        verwijderd, nietgevonden = await remove_guest_votes(
            int(OWNER), DAG, TIJD, ["Toad", "Peach"], 1, 123
        )

        self.assertCountEqual(verwijderd, ["Toad", "Peach"])
        self.assertEqual(nietgevonden, [])

        # Overgebleven: alleen Luigi
        votes = await load_votes(1, 123)
        self.assertNotIn(f"{OWNER}_guest::Toad", votes)  # helemaal opgeruimd
        self.assertNotIn(f"{OWNER}_guest::Peach", votes)  # helemaal opgeruimd
        self.assertIn(f"{OWNER}_guest::Luigi", votes)

        # Count is nu 1
        count = await get_votes_for_option(DAG, TIJD, 1, 123)
        self.assertEqual(count, 1)

    # --- Status: owner stemt + 2 gasten -> gegroepeerde tekst + juiste count ---
    async def test_status_embed_met_owner_en_gasten(self):
        # Namen tonen aanzetten voor kanaal
        kanaal_id = 123456

        # Owner stemt zelf ook
        await toggle_vote(OWNER, DAG, TIJD, 0, kanaal_id)
        # Voeg 2 gasten toe
        await add_guest_votes(OWNER, DAG, TIJD, ["Toad", "Luigi"], 0, kanaal_id)

        # Mock guild & member
        mock_guild = MagicMock()
        mock_guild.id = 0
        mock_member = MagicMock()
        mock_member.display_name = "Mario"
        mock_member.global_name = None
        mock_member.name = "Mario"
        mock_guild.get_member.return_value = mock_member
        mock_guild.fetch_member = AsyncMock(return_value=mock_member)

        mock_channel = MagicMock()
        mock_channel.id = kanaal_id
        mock_channel.guild = mock_guild

        mock_user = MagicMock()
        mock_user.guild_permissions.administrator = True

        interaction = MagicMock()
        interaction.guild = mock_guild
        interaction.channel = mock_channel
        interaction.user = mock_user
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        # Run: /dmk-poll-status
        await self.cog._status_impl(interaction)

        # Controleer dat embed is verstuurd
        interaction.followup.send.assert_called()
        kwargs = interaction.followup.send.call_args.kwargs
        embed = kwargs.get("embed")
        self.assertIsNotNone(embed)
        assert embed is not None

        # Embed zou 3 stemmen moeten bevatten
        all_text = str(embed.description) + "".join(f.value for f in embed.fields)
        self.assertIn("**3** stemmen", all_text)
        # Gecombineerde weergave: @Mario (@Mario: Toad, Luigi)
        self.assertIn("@Mario (@Mario: Toad, Luigi)", all_text)

    # --- Status: alleen gasten (owner stemt niet) -> compact en juiste count ---
    async def test_status_embed_alleen_gasten(self):
        kanaal_id = 7890

        # Owner stemt NIET, maar heeft 2 gasten
        await add_guest_votes(OWNER, DAG, TIJD, ["Anna", "Maria"], 0, kanaal_id)

        mock_guild = MagicMock()
        mock_guild.id = 0
        mock_member = MagicMock()
        mock_member.display_name = "Mario"
        mock_member.global_name = None
        mock_member.name = "Mario"
        mock_guild.get_member.return_value = mock_member
        mock_guild.fetch_member = AsyncMock(return_value=mock_member)

        mock_channel = MagicMock()
        mock_channel.id = kanaal_id
        mock_channel.guild = mock_guild

        mock_user = MagicMock()
        mock_user.guild_permissions.administrator = True

        interaction = MagicMock()
        interaction.guild = mock_guild
        interaction.channel = mock_channel
        interaction.user = mock_user
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        await self.cog._status_impl(interaction)

        interaction.followup.send.assert_called()
        kwargs = interaction.followup.send.call_args.kwargs
        embed = kwargs.get("embed")
        self.assertIsNotNone(embed)
        assert embed is not None

        all_text = str(embed.description) + "".join(f.value for f in embed.fields)
        self.assertIn("**2** stemmen", all_text)
        self.assertIn("(@Mario: Anna, Maria)", all_text)


if __name__ == "__main__":
    unittest.main()

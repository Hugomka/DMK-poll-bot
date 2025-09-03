# tests/test_status.py

from unittest.mock import AsyncMock, MagicMock
from apps.commands.dmk_poll import DMKPoll
from apps.utils.poll_storage import toggle_vote
from apps.utils.poll_settings import toggle_name_display
from tests.base import BaseTestCase


class TestStatusCommand(BaseTestCase):

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.mock_bot = MagicMock()
        self.cog = DMKPoll(self.mock_bot)

    async def test_status_embed_toon_namen(self):
        # Zet naamweergave aan
        kanaal_id = 123456
        toggle_name_display(kanaal_id)

        # Simuleer stem
        await toggle_vote("111", "vrijdag", "om 19:00 uur")

        # Maak nep-interaction met guild en user
        mock_guild = MagicMock()
        mock_member = MagicMock()
        mock_member.mention = "@Goldway"
        mock_guild.get_member.return_value = mock_member
        mock_guild.fetch_member = AsyncMock(return_value=mock_member)
        mock_guild.id = kanaal_id

        mock_channel = MagicMock()
        mock_channel.id = kanaal_id
        mock_channel.guild = mock_guild

        mock_user = MagicMock()
        mock_user.guild_permissions.administrator = True

        interaction = MagicMock()
        interaction.channel = mock_channel
        interaction.user = mock_user
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        # ⏯️ Aanroepen van status
        await self.cog.status.callback(self.cog, interaction)

        # 🔍 Controleer dat een embed is gestuurd
        interaction.followup.send.assert_called()
        args, kwargs = interaction.followup.send.call_args
        self.assertEqual(args, (), "Expected no positional args in followup.send")
        embed = kwargs.get("embed")
        self.assertIsNotNone(embed)
        self.assertIn("@Goldway", str(embed.description) + str(embed.fields))

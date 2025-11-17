# tests/test_poll_config.py
"""
Tests voor poll_config command (apps/commands/poll_config.py).

Test coverage:
- poll_instelling command met poll-opties choice
- poll_instelling command met notificaties choice
- poll_instelling command zonder channel_id
- poll_instelling command met niet-text channel
- poll_instelling command met onbekende instelling
- poll_instelling command exception handling
"""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord import app_commands

from apps.commands import poll_config
from tests.base import BaseTestCase


class TestPollConfigCommand(BaseTestCase):
    """Tests voor poll_instelling command."""

    async def test_poll_instelling_poll_opties_success(self):
        """Test poll_instelling met poll-opties choice."""
        # Mock interaction
        interaction = MagicMock(spec=discord.Interaction)
        interaction.channel_id = 123456
        interaction.channel = MagicMock(spec=discord.TextChannel)
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()

        # Mock choice
        choice = MagicMock(spec=app_commands.Choice)
        choice.value = "poll-opties"

        # Mock embeds en views
        with patch(
            "apps.commands.poll_config.create_poll_options_settings_embed"
        ) as mock_embed, patch(
            "apps.commands.poll_config.PollOptionsSettingsView"
        ) as mock_view:
            mock_embed.return_value = MagicMock(spec=discord.Embed)
            mock_view.return_value = MagicMock()

            # Call command callback
            await poll_config.poll_instelling._callback(interaction, choice)  # type: ignore[arg-type]  # type: ignore[arg-type]

            # Check defer
            interaction.response.defer.assert_called_once_with(ephemeral=True)

            # Check dat followup.send called is met embed en view
            interaction.followup.send.assert_called_once()
            call_kwargs = interaction.followup.send.call_args[1]
            self.assertIn("embed", call_kwargs)
            self.assertIn("view", call_kwargs)
            self.assertTrue(call_kwargs["ephemeral"])

    async def test_poll_instelling_notificaties_success(self):
        """Test poll_instelling met notificaties choice."""
        # Mock interaction
        interaction = MagicMock(spec=discord.Interaction)
        interaction.channel_id = 123456
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()

        # Mock choice
        choice = MagicMock(spec=app_commands.Choice)
        choice.value = "notificaties"

        # Mock embeds en views
        with patch(
            "apps.commands.poll_config.create_notification_settings_embed"
        ) as mock_embed, patch(
            "apps.commands.poll_config.NotificationSettingsView"
        ) as mock_view:
            mock_embed.return_value = MagicMock(spec=discord.Embed)
            mock_view.return_value = MagicMock()

            # Call command callback
            await poll_config.poll_instelling._callback(interaction, choice)  # type: ignore[arg-type]  # type: ignore[arg-type]

            # Check defer
            interaction.response.defer.assert_called_once_with(ephemeral=True)

            # Check dat followup.send called is met embed en view
            interaction.followup.send.assert_called_once()
            call_kwargs = interaction.followup.send.call_args[1]
            self.assertIn("embed", call_kwargs)
            self.assertIn("view", call_kwargs)
            self.assertTrue(call_kwargs["ephemeral"])

    async def test_poll_instelling_no_channel_id(self):
        """Test poll_instelling zonder channel_id toont error."""
        # Mock interaction zonder channel_id
        interaction = MagicMock(spec=discord.Interaction)
        interaction.channel_id = None
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()

        # Mock choice
        choice = MagicMock(spec=app_commands.Choice)
        choice.value = "poll-opties"

        # Call command callback
        await poll_config.poll_instelling._callback(interaction, choice)  # type: ignore[arg-type]

        # Check dat error getoond wordt
        interaction.followup.send.assert_called_once()
        call_args = interaction.followup.send.call_args
        self.assertIn("Kan channel ID niet bepalen", call_args[0][0])
        self.assertTrue(call_args[1]["ephemeral"])

    async def test_poll_instelling_not_text_channel(self):
        """Test poll_instelling met niet-text channel toont error."""
        # Mock interaction met niet-text channel
        interaction = MagicMock(spec=discord.Interaction)
        interaction.channel_id = 123456
        interaction.channel = MagicMock(spec=discord.VoiceChannel)  # Geen TextChannel
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()

        # Mock choice
        choice = MagicMock(spec=app_commands.Choice)
        choice.value = "poll-opties"

        # Call command callback
        await poll_config.poll_instelling._callback(interaction, choice)  # type: ignore[arg-type]

        # Check dat error getoond wordt
        interaction.followup.send.assert_called_once()
        call_args = interaction.followup.send.call_args
        self.assertIn("text channels", call_args[0][0])
        self.assertTrue(call_args[1]["ephemeral"])

    async def test_poll_instelling_unknown_choice(self):
        """Test poll_instelling met onbekende choice toont error."""
        # Mock interaction
        interaction = MagicMock(spec=discord.Interaction)
        interaction.channel_id = 123456
        interaction.channel = MagicMock(spec=discord.TextChannel)
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()

        # Mock choice met onbekende value
        choice = MagicMock(spec=app_commands.Choice)
        choice.value = "onbekend"

        # Call command callback
        await poll_config.poll_instelling._callback(interaction, choice)  # type: ignore[arg-type]

        # Check dat error getoond wordt
        interaction.followup.send.assert_called_once()
        call_args = interaction.followup.send.call_args
        self.assertIn("Onbekende instelling", call_args[0][0])
        self.assertTrue(call_args[1]["ephemeral"])

    async def test_poll_instelling_exception_handling(self):
        """Test poll_instelling exception handling."""
        # Mock interaction
        interaction = MagicMock(spec=discord.Interaction)
        interaction.channel_id = 123456
        interaction.channel = MagicMock(spec=discord.TextChannel)
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()

        # Mock choice
        choice = MagicMock(spec=app_commands.Choice)
        choice.value = "poll-opties"

        # Mock embed dat exception gooit
        with patch(
            "apps.commands.poll_config.create_poll_options_settings_embed",
            side_effect=Exception("Test error"),
        ):
            # Call command callback directly
            await poll_config.poll_instelling._callback(interaction, choice)  # type: ignore[arg-type]

            # Check dat error via followup getoond wordt
            interaction.followup.send.assert_called_once()
            call_args = interaction.followup.send.call_args
            self.assertIn("Fout bij openen instellingen", call_args[0][0])
            self.assertIn("Test error", call_args[0][0])
            self.assertTrue(call_args[1]["ephemeral"])

    async def test_poll_instelling_setup(self):
        """Test dat setup command registreert."""
        from apps.commands.poll_config import setup

        # Mock bot
        mock_bot = MagicMock()
        mock_bot.tree = MagicMock()

        # Call setup
        await setup(mock_bot)

        # Check dat command geregistreerd is
        mock_bot.tree.add_command.assert_called_once_with(poll_config.poll_instelling)

# tests/test_poll_guests.py
"""
Tests voor poll_guests.py om coverage te verhogen van 53% naar 80%+
"""

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

from discord import app_commands

from apps.commands.poll_guests import PollGuests
from tests.base import BaseTestCase


def _mk_interaction(channel: Any = None, guild: Any = None, user: Any = None) -> Any:
    """Maakt een interaction-mock met response.defer en followup.send."""
    interaction = MagicMock()
    interaction.channel = channel
    interaction.guild = guild
    interaction.user = user or MagicMock(id=999)
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    return interaction


def _mk_choice(name: str, value: str) -> Any:
    """Maakt een app_commands.Choice mock."""
    choice = MagicMock(spec=app_commands.Choice)
    choice.name = name
    choice.value = value
    return choice


class TestPollGuestsAdd(BaseTestCase):
    """Tests voor /guest-add command"""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bot = MagicMock()
        self.cog = PollGuests(self.bot)

    async def _run(self, cmd, *args, **kwargs):
        """Roept een app_commands.Command aan via .callback(cog, ...)."""
        cb = getattr(cmd, "callback", None)
        if cb is not None:
            owner = getattr(cmd, "binding", None)
            if owner is None:
                owner = getattr(self, "cog", None)
            return await cb(owner, *args, **kwargs)
        return await cast(Any, cmd)(*args, **kwargs)

    def _last_content(self, mock_send) -> str:
        """Haal 'content' op uit kwargs of uit de eerste positionele arg."""
        if not mock_send.called:
            return ""
        args, kwargs = mock_send.call_args
        if "content" in kwargs and kwargs["content"] is not None:
            return kwargs["content"]
        if args and isinstance(args[0], str):
            return args[0]
        return ""

    async def test_gast_add_empty_names_returns_warning(self):
        """Test dat warning komt bij lege namen string"""
        channel = MagicMock()
        channel.id = 123
        guild = MagicMock()
        guild.id = 456
        user = MagicMock()
        user.id = 789
        interaction = _mk_interaction(channel=channel, guild=guild, user=user)
        slot = _mk_choice("Vrijdag 19:00", "vrijdag|om 19:00 uur")

        await self._run(self.cog.guest_add, interaction, slot, "")

        interaction.followup.send.assert_awaited_once()
        content = self._last_content(interaction.followup.send)
        assert "Geen geldige namen" in content

    async def test_gast_add_whitespace_only_names_returns_warning(self):
        """Test dat warning komt bij alleen whitespace"""
        channel = MagicMock()
        channel.id = 123
        guild = MagicMock()
        guild.id = 456
        user = MagicMock()
        user.id = 789
        interaction = _mk_interaction(channel=channel, guild=guild, user=user)
        slot = _mk_choice("Zaterdag 20:30", "zaterdag|om 20:30 uur")

        await self._run(self.cog.guest_add, interaction, slot, "  ,  ,  ")

        interaction.followup.send.assert_awaited_once()
        content = self._last_content(interaction.followup.send)
        assert "Geen geldige namen" in content

    async def test_gast_add_success_with_toegevoegd(self):
        """Test dat gasten succesvol toevoegen werkt met toegevoegd lijst"""
        channel = MagicMock()
        channel.id = 123
        guild = MagicMock()
        guild.id = 456
        user = MagicMock()
        user.id = 789
        interaction = _mk_interaction(channel=channel, guild=guild, user=user)
        slot = _mk_choice("Vrijdag 19:00", "vrijdag|om 19:00 uur")

        with patch(
            "apps.commands.poll_guests.add_guest_votes",
            new=AsyncMock(return_value=(["Mario", "Luigi"], [])),
        ) as mock_add, patch(
            "apps.commands.poll_guests.update_poll_message", new=AsyncMock()
        ) as mock_update:
            await self._run(self.cog.guest_add, interaction, slot, "Mario, Luigi")

        # add_guest_votes moet zijn aangeroepen met juiste parameters
        mock_add.assert_awaited_once_with(789, "vrijdag", "om 19:00 uur", ["Mario", "Luigi"], 456, 123)

        # update_poll_message moet zijn aangeroepen
        mock_update.assert_awaited_once_with(channel=channel, dag="vrijdag")

        # Moet bevestiging sturen met toegevoegd lijst
        interaction.followup.send.assert_awaited_once()
        content = self._last_content(interaction.followup.send)
        assert "vrijdag" in content.lower()
        assert "om 19:00 uur" in content.lower()
        assert "✅" in content
        assert "Toegevoegd" in content
        assert "Mario" in content
        assert "Luigi" in content

    async def test_gast_add_success_with_overgeslagen(self):
        """Test dat gasten toevoegen werkt met overgeslagen lijst"""
        channel = MagicMock()
        channel.id = 123
        guild = MagicMock()
        guild.id = 456
        user = MagicMock()
        user.id = 789
        interaction = _mk_interaction(channel=channel, guild=guild, user=user)
        slot = _mk_choice("Zaterdag 19:00", "zaterdag|om 19:00 uur")

        with patch(
            "apps.commands.poll_guests.add_guest_votes",
            new=AsyncMock(return_value=([], ["Peach", "Toad"])),
        ), patch("apps.commands.poll_guests.update_poll_message", new=AsyncMock()):
            await self._run(self.cog.guest_add, interaction, slot, "Peach, Toad")

        # Moet bevestiging sturen met overgeslagen lijst
        interaction.followup.send.assert_awaited_once()
        content = self._last_content(interaction.followup.send)
        assert "zaterdag" in content.lower()
        assert "ℹ️" in content
        assert "Overgeslagen" in content
        assert "bestond al" in content.lower()
        assert "Peach" in content
        assert "Toad" in content

    async def test_gast_add_success_with_both_toegevoegd_and_overgeslagen(self):
        """Test dat gasten toevoegen werkt met beide lijsten"""
        channel = MagicMock()
        channel.id = 123
        guild = MagicMock()
        guild.id = 456
        user = MagicMock()
        user.id = 789
        interaction = _mk_interaction(channel=channel, guild=guild, user=user)
        slot = _mk_choice("Zondag 20:30", "zondag|om 20:30 uur")

        with patch(
            "apps.commands.poll_guests.add_guest_votes",
            new=AsyncMock(return_value=(["Mario"], ["Luigi"])),
        ), patch("apps.commands.poll_guests.update_poll_message", new=AsyncMock()):
            await self._run(self.cog.guest_add, interaction, slot, "Mario, Luigi")

        # Moet beide secties tonen
        interaction.followup.send.assert_awaited_once()
        content = self._last_content(interaction.followup.send)
        assert "✅" in content
        assert "Toegevoegd" in content
        assert "Mario" in content
        assert "ℹ️" in content
        assert "Overgeslagen" in content
        assert "Luigi" in content

    async def test_gast_add_success_with_empty_results(self):
        """Test dat gasten toevoegen (niets gewijzigd) message toont"""
        channel = MagicMock()
        channel.id = 123
        guild = MagicMock()
        guild.id = 456
        user = MagicMock()
        user.id = 789
        interaction = _mk_interaction(channel=channel, guild=guild, user=user)
        slot = _mk_choice("Vrijdag 20:30", "vrijdag|om 20:30 uur")

        with patch(
            "apps.commands.poll_guests.add_guest_votes",
            new=AsyncMock(return_value=([], [])),
        ), patch("apps.commands.poll_guests.update_poll_message", new=AsyncMock()):
            await self._run(self.cog.guest_add, interaction, slot, "Mario")

        # Moet (niets gewijzigd) tonen
        interaction.followup.send.assert_awaited_once()
        content = self._last_content(interaction.followup.send)
        assert "niets gewijzigd" in content.lower()

    async def test_gast_add_with_semicolon_separator(self):
        """Test dat puntkomma separator werkt"""
        channel = MagicMock()
        channel.id = 123
        guild = MagicMock()
        guild.id = 456
        user = MagicMock()
        user.id = 789
        interaction = _mk_interaction(channel=channel, guild=guild, user=user)
        slot = _mk_choice("Vrijdag 19:00", "vrijdag|om 19:00 uur")

        with patch(
            "apps.commands.poll_guests.add_guest_votes",
            new=AsyncMock(return_value=(["Mario", "Luigi", "Peach"], [])),
        ) as mock_add, patch("apps.commands.poll_guests.update_poll_message", new=AsyncMock()):
            await self._run(self.cog.guest_add, interaction, slot, "Mario; Luigi; Peach")

        # Moet gesplitst zijn op puntkomma
        mock_add.assert_awaited_once()
        call_args = mock_add.call_args
        names_list = call_args[0][3]  # 4th positional argument
        assert names_list == ["Mario", "Luigi", "Peach"]

    async def test_gast_add_with_mixed_separators(self):
        """Test dat gemixte separators werken"""
        channel = MagicMock()
        channel.id = 123
        guild = MagicMock()
        guild.id = 456
        user = MagicMock()
        user.id = 789
        interaction = _mk_interaction(channel=channel, guild=guild, user=user)
        slot = _mk_choice("Zaterdag 19:00", "zaterdag|om 19:00 uur")

        with patch(
            "apps.commands.poll_guests.add_guest_votes",
            new=AsyncMock(return_value=(["Mario", "Luigi"], [])),
        ) as mock_add, patch("apps.commands.poll_guests.update_poll_message", new=AsyncMock()):
            await self._run(self.cog.guest_add, interaction, slot, "Mario, Luigi; Peach")

        # Moet gesplitst zijn op beide
        mock_add.assert_awaited_once()
        call_args = mock_add.call_args
        names_list = call_args[0][3]
        assert "Mario" in names_list
        assert "Luigi" in names_list
        assert "Peach" in names_list

    async def test_gast_add_without_guild(self):
        """Test dat guild ID "0" wordt als guild None is"""
        channel = MagicMock()
        channel.id = 123
        user = MagicMock()
        user.id = 789
        interaction = _mk_interaction(channel=channel, guild=None, user=user)
        slot = _mk_choice("Vrijdag 19:00", "vrijdag|om 19:00 uur")

        with patch(
            "apps.commands.poll_guests.add_guest_votes",
            new=AsyncMock(return_value=(["Mario"], [])),
        ) as mock_add, patch("apps.commands.poll_guests.update_poll_message", new=AsyncMock()):
            await self._run(self.cog.guest_add, interaction, slot, "Mario")

        # Moet guild "0" gebruiken
        mock_add.assert_awaited_once()
        call_args = mock_add.call_args
        guild_id = call_args[0][4]
        assert guild_id == "0"


class TestPollGuestsRemove(BaseTestCase):
    """Tests voor /guest-remove command"""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bot = MagicMock()
        self.cog = PollGuests(self.bot)

    async def _run(self, cmd, *args, **kwargs):
        """Roept een app_commands.Command aan via .callback(cog, ...)."""
        cb = getattr(cmd, "callback", None)
        if cb is not None:
            owner = getattr(cmd, "binding", None)
            if owner is None:
                owner = getattr(self, "cog", None)
            return await cb(owner, *args, **kwargs)
        return await cast(Any, cmd)(*args, **kwargs)

    def _last_content(self, mock_send) -> str:
        """Haal 'content' op uit kwargs of uit de eerste positionele arg."""
        if not mock_send.called:
            return ""
        args, kwargs = mock_send.call_args
        if "content" in kwargs and kwargs["content"] is not None:
            return kwargs["content"]
        if args and isinstance(args[0], str):
            return args[0]
        return ""

    async def test_gast_remove_empty_names_returns_warning(self):
        """Test dat warning komt bij lege namen string"""
        channel = MagicMock()
        channel.id = 123
        guild = MagicMock()
        guild.id = 456
        user = MagicMock()
        user.id = 789
        interaction = _mk_interaction(channel=channel, guild=guild, user=user)
        slot = _mk_choice("Vrijdag 19:00", "vrijdag|om 19:00 uur")

        await self._run(self.cog.guest_remove, interaction, slot, "")

        interaction.followup.send.assert_awaited_once()
        content = self._last_content(interaction.followup.send)
        assert "Geen geldige namen" in content

    async def test_gast_remove_success_with_verwijderd(self):
        """Test dat gasten succesvol verwijderen werkt met verwijderd lijst"""
        channel = MagicMock()
        channel.id = 123
        guild = MagicMock()
        guild.id = 456
        user = MagicMock()
        user.id = 789
        interaction = _mk_interaction(channel=channel, guild=guild, user=user)
        slot = _mk_choice("Vrijdag 19:00", "vrijdag|om 19:00 uur")

        with patch(
            "apps.commands.poll_guests.remove_guest_votes",
            new=AsyncMock(return_value=(["Mario", "Luigi"], [])),
        ) as mock_remove, patch(
            "apps.commands.poll_guests.update_poll_message", new=AsyncMock()
        ) as mock_update:
            await self._run(self.cog.guest_remove, interaction, slot, "Mario, Luigi")

        # remove_guest_votes moet zijn aangeroepen met juiste parameters
        mock_remove.assert_awaited_once_with(789, "vrijdag", "om 19:00 uur", ["Mario", "Luigi"], 456, 123)

        # update_poll_message moet zijn aangeroepen
        mock_update.assert_awaited_once_with(channel=channel, dag="vrijdag")

        # Moet bevestiging sturen met verwijderd lijst
        interaction.followup.send.assert_awaited_once()
        content = self._last_content(interaction.followup.send)
        assert "vrijdag" in content.lower()
        assert "verwijderd" in content.lower()
        assert "✅" in content
        assert "Verwijderd" in content
        assert "Mario" in content
        assert "Luigi" in content

    async def test_gast_remove_success_with_nietgevonden(self):
        """Test dat gasten verwijderen werkt met niet gevonden lijst"""
        channel = MagicMock()
        channel.id = 123
        guild = MagicMock()
        guild.id = 456
        user = MagicMock()
        user.id = 789
        interaction = _mk_interaction(channel=channel, guild=guild, user=user)
        slot = _mk_choice("Zaterdag 20:30", "zaterdag|om 20:30 uur")

        with patch(
            "apps.commands.poll_guests.remove_guest_votes",
            new=AsyncMock(return_value=([], ["Peach", "Toad"])),
        ), patch("apps.commands.poll_guests.update_poll_message", new=AsyncMock()):
            await self._run(self.cog.guest_remove, interaction, slot, "Peach, Toad")

        # Moet bevestiging sturen met niet gevonden lijst
        interaction.followup.send.assert_awaited_once()
        content = self._last_content(interaction.followup.send)
        assert "zaterdag" in content.lower()
        assert "ℹ️" in content
        assert "Niet gevonden" in content
        assert "Peach" in content
        assert "Toad" in content

    async def test_gast_remove_success_with_both_verwijderd_and_nietgevonden(self):
        """Test dat gasten verwijderen werkt met beide lijsten"""
        channel = MagicMock()
        channel.id = 123
        guild = MagicMock()
        guild.id = 456
        user = MagicMock()
        user.id = 789
        interaction = _mk_interaction(channel=channel, guild=guild, user=user)
        slot = _mk_choice("Zondag 19:00", "zondag|om 19:00 uur")

        with patch(
            "apps.commands.poll_guests.remove_guest_votes",
            new=AsyncMock(return_value=(["Mario"], ["Luigi"])),
        ), patch("apps.commands.poll_guests.update_poll_message", new=AsyncMock()):
            await self._run(self.cog.guest_remove, interaction, slot, "Mario, Luigi")

        # Moet beide secties tonen
        interaction.followup.send.assert_awaited_once()
        content = self._last_content(interaction.followup.send)
        assert "✅" in content
        assert "Verwijderd" in content
        assert "Mario" in content
        assert "ℹ️" in content
        assert "Niet gevonden" in content
        assert "Luigi" in content

    async def test_gast_remove_success_with_empty_results(self):
        """Test dat gasten verwijderen (niets gewijzigd) message toont"""
        channel = MagicMock()
        channel.id = 123
        guild = MagicMock()
        guild.id = 456
        user = MagicMock()
        user.id = 789
        interaction = _mk_interaction(channel=channel, guild=guild, user=user)
        slot = _mk_choice("Vrijdag 20:30", "vrijdag|om 20:30 uur")

        with patch(
            "apps.commands.poll_guests.remove_guest_votes",
            new=AsyncMock(return_value=([], [])),
        ), patch("apps.commands.poll_guests.update_poll_message", new=AsyncMock()):
            await self._run(self.cog.guest_remove, interaction, slot, "Mario")

        # Moet (niets gewijzigd) tonen
        interaction.followup.send.assert_awaited_once()
        content = self._last_content(interaction.followup.send)
        assert "niets gewijzigd" in content.lower()

    async def test_gast_remove_without_guild(self):
        """Test dat guild ID "0" wordt als guild None is"""
        channel = MagicMock()
        channel.id = 123
        user = MagicMock()
        user.id = 789
        interaction = _mk_interaction(channel=channel, guild=None, user=user)
        slot = _mk_choice("Vrijdag 19:00", "vrijdag|om 19:00 uur")

        with patch(
            "apps.commands.poll_guests.remove_guest_votes",
            new=AsyncMock(return_value=(["Mario"], [])),
        ) as mock_remove, patch("apps.commands.poll_guests.update_poll_message", new=AsyncMock()):
            await self._run(self.cog.guest_remove, interaction, slot, "Mario")

        # Moet guild "0" gebruiken
        mock_remove.assert_awaited_once()
        call_args = mock_remove.call_args
        guild_id = call_args[0][4]
        assert guild_id == "0"


class TestPollGuestsSetup(BaseTestCase):
    """Tests voor setup functie"""

    async def test_setup_adds_cog(self):
        """Test dat setup de PollGuests cog toevoegt"""
        bot = MagicMock()
        bot.add_cog = AsyncMock()

        from apps.commands.poll_guests import setup

        await setup(bot)

        bot.add_cog.assert_awaited_once()
        args, _ = bot.add_cog.call_args
        assert isinstance(args[0], PollGuests)


if __name__ == "__main__":
    import unittest

    unittest.main()

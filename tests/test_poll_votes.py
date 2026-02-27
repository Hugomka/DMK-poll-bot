# tests/test_poll_votes.py
"""
Tests voor poll_votes.py om coverage te verhogen van 52% naar 80%+
"""

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

from discord import app_commands

from apps.commands.poll_votes import PollVotes
from tests.base import BaseTestCase


def _mk_interaction(channel: Any = None) -> Any:
    """Maakt een interaction-mock met response.defer en followup.send."""
    interaction = MagicMock()
    interaction.channel = channel
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    return interaction


def _mk_choice(name: str, value: str) -> Any:
    """Maakt een app_commands.Choice mock."""
    choice = MagicMock(spec=app_commands.Choice)
    choice.name = name
    choice.value = value
    return choice


class TestPollVotesStemmen(BaseTestCase):
    """Tests voor /dmk-poll-stemmen command"""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bot = MagicMock()
        self.cog = PollVotes(self.bot)

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

    async def test_stemmen_no_channel_returns_error(self):
        """Test dat command error geeft als er geen kanaal is"""
        interaction = _mk_interaction(channel=None)
        actie = _mk_choice("Zichtbaar maken", "zichtbaar")

        await self._run(self.cog.stemmen, interaction, actie)

        interaction.followup.send.assert_awaited_once()
        content = self._last_content(interaction.followup.send)
        assert "Geen kanaal" in content

    async def test_stemmen_zichtbaar_alle_dagen(self):
        """Test dat stemmen zichtbaar maken werkt voor alle enabled dagen"""
        channel = MagicMock()
        channel.id = 123
        interaction = _mk_interaction(channel=channel)
        actie = _mk_choice("Zichtbaar maken", "altijd")

        with patch("apps.commands.poll_votes.set_visibility") as mock_set_visibility, patch(
            "apps.commands.poll_votes.update_poll_message", new=AsyncMock()
        ) as mock_update, patch(
            "apps.commands.poll_votes.get_enabled_period_days",
            return_value=[{"dag": d, "datum_iso": "2025-12-05"} for d in ["vrijdag", "zaterdag", "zondag"]]
        ):
            # Mock return value voor laatste dag (zondag)
            mock_set_visibility.return_value = {"modus": "altijd", "tijd": "18:00"}

            await self._run(self.cog.stemmen, interaction, actie, dag=None, tijd=None)

        # Moet voor alle 3 enabled dagen zijn aangeroepen (default: weekend)
        assert mock_set_visibility.call_count == 3
        mock_set_visibility.assert_any_call(123, "vrijdag", modus="altijd", tijd="18:00")
        mock_set_visibility.assert_any_call(123, "zaterdag", modus="altijd", tijd="18:00")
        mock_set_visibility.assert_any_call(123, "zondag", modus="altijd", tijd="18:00")

        # Moet berichten hebben ge-update
        assert mock_update.await_count == 3

        # Moet bevestiging hebben gestuurd met "alle dagen"
        interaction.followup.send.assert_awaited_once()
        content = self._last_content(interaction.followup.send)
        assert "alle dagen" in content.lower()
        assert "altijd zichtbaar" in content.lower()

    async def test_stemmen_zichtbaar_een_dag(self):
        """Test dat stemmen zichtbaar maken werkt voor één dag"""
        channel = MagicMock()
        channel.id = 123
        interaction = _mk_interaction(channel=channel)
        actie = _mk_choice("Zichtbaar maken", "altijd")
        dag = _mk_choice("Vrijdag", "vrijdag")

        with patch("apps.commands.poll_votes.set_visibility") as mock_set_visibility, patch(
            "apps.commands.poll_votes.update_poll_message", new=AsyncMock()
        ) as mock_update:
            # Mock return value
            mock_set_visibility.return_value = {"modus": "altijd", "tijd": "18:00"}

            await self._run(self.cog.stemmen, interaction, actie, dag=dag, tijd=None)

        # Moet alleen voor vrijdag zijn aangeroepen
        mock_set_visibility.assert_called_once_with(
            123, "vrijdag", modus="altijd", tijd="18:00"
        )

        # Moet bericht hebben ge-update
        mock_update.assert_awaited_once_with(channel, "vrijdag")

        # Moet bevestiging hebben gestuurd met dag naam
        interaction.followup.send.assert_awaited_once()
        content = self._last_content(interaction.followup.send)
        assert "vrijdag" in content.lower()
        assert "altijd zichtbaar" in content.lower()
        assert "alle dagen" not in content.lower()

    async def test_stemmen_verborgen_met_tijd(self):
        """Test dat stemmen verbergen werkt met opgegeven deadline tijd"""
        channel = MagicMock()
        channel.id = 123
        interaction = _mk_interaction(channel=channel)
        actie = _mk_choice("Verbergen tot deadline", "deadline")
        dag = _mk_choice("Zaterdag", "zaterdag")

        with patch("apps.commands.poll_votes.set_visibility") as mock_set_visibility, patch(
            "apps.commands.poll_votes.update_poll_message", new=AsyncMock()
        ):
            # Mock return value met custom tijd
            mock_set_visibility.return_value = {"modus": "deadline", "tijd": "19:30"}

            await self._run(
                self.cog.stemmen, interaction, actie, dag=dag, tijd="19:30"
            )

        # Moet deadline modus gebruiken met opgegeven tijd
        mock_set_visibility.assert_called_once_with(
            123, "zaterdag", modus="deadline", tijd="19:30"
        )

        # Moet bevestiging hebben gestuurd met verborgen tot tijd
        interaction.followup.send.assert_awaited_once()
        content = self._last_content(interaction.followup.send)
        assert "zaterdag" in content.lower()
        assert "verborgen tot 19:30" in content.lower()

    async def test_stemmen_verborgen_zonder_tijd_gebruikt_default(self):
        """Test dat stemmen verbergen fallback naar 18:00 gebruikt als geen tijd opgegeven"""
        channel = MagicMock()
        channel.id = 123
        interaction = _mk_interaction(channel=channel)
        actie = _mk_choice("Verbergen tot deadline", "deadline")
        dag = _mk_choice("Zondag", "zondag")

        with patch("apps.commands.poll_votes.set_visibility") as mock_set_visibility, patch(
            "apps.commands.poll_votes.update_poll_message", new=AsyncMock()
        ):
            # Mock return value met default tijd
            mock_set_visibility.return_value = {"modus": "deadline", "tijd": "18:00"}

            await self._run(self.cog.stemmen, interaction, actie, dag=dag, tijd=None)

        # Moet deadline modus gebruiken met default tijd 18:00
        mock_set_visibility.assert_called_once_with(
            123, "zondag", modus="deadline", tijd="18:00"
        )

        # Moet bevestiging hebben gestuurd met default tijd
        interaction.followup.send.assert_awaited_once()
        content = self._last_content(interaction.followup.send)
        assert "zondag" in content.lower()
        assert "verborgen tot 18:00" in content.lower()

    async def test_stemmen_verborgen_alle_dagen_met_tijd(self):
        """Test dat stemmen verbergen werkt voor alle enabled dagen met opgegeven tijd"""
        channel = MagicMock()
        channel.id = 123
        interaction = _mk_interaction(channel=channel)
        actie = _mk_choice("Verbergen tot deadline", "deadline")

        with patch("apps.commands.poll_votes.set_visibility") as mock_set_visibility, patch(
            "apps.commands.poll_votes.update_poll_message", new=AsyncMock()
        ) as mock_update, patch(
            "apps.commands.poll_votes.get_enabled_period_days",
            return_value=[{"dag": d, "datum_iso": "2025-12-05"} for d in ["vrijdag", "zaterdag", "zondag"]]
        ):
            # Mock return value voor laatste dag
            mock_set_visibility.return_value = {"modus": "deadline", "tijd": "20:00"}

            await self._run(
                self.cog.stemmen, interaction, actie, dag=None, tijd="20:00"
            )

        # Moet voor alle 3 enabled dagen zijn aangeroepen met custom tijd (default: weekend)
        assert mock_set_visibility.call_count == 3
        mock_set_visibility.assert_any_call(123, "vrijdag", modus="deadline", tijd="20:00")
        mock_set_visibility.assert_any_call(123, "zaterdag", modus="deadline", tijd="20:00")
        mock_set_visibility.assert_any_call(123, "zondag", modus="deadline", tijd="20:00")

        # Moet berichten hebben ge-update
        assert mock_update.await_count == 3

        # Moet bevestiging hebben gestuurd met "alle dagen"
        interaction.followup.send.assert_awaited_once()
        content = self._last_content(interaction.followup.send)
        assert "alle dagen" in content.lower()
        assert "verborgen tot 20:00" in content.lower()

    async def test_stemmen_verborgen_alle_dagen_zonder_tijd(self):
        """Test dat stemmen verbergen voor alle enabled dagen fallback naar 18:00 gebruikt"""
        channel = MagicMock()
        channel.id = 123
        interaction = _mk_interaction(channel=channel)
        actie = _mk_choice("Verbergen tot deadline", "deadline")

        with patch("apps.commands.poll_votes.set_visibility") as mock_set_visibility, patch(
            "apps.commands.poll_votes.update_poll_message", new=AsyncMock()
        ), patch(
            "apps.commands.poll_votes.get_enabled_period_days",
            return_value=[{"dag": d, "datum_iso": "2025-12-05"} for d in ["vrijdag", "zaterdag", "zondag"]]
        ):
            # Mock return value voor laatste dag
            mock_set_visibility.return_value = {"modus": "deadline", "tijd": "18:00"}

            await self._run(self.cog.stemmen, interaction, actie, dag=None, tijd=None)

        # Moet voor alle 3 enabled dagen zijn aangeroepen met default tijd (default: weekend)
        assert mock_set_visibility.call_count == 3
        mock_set_visibility.assert_any_call(123, "vrijdag", modus="deadline", tijd="18:00")
        mock_set_visibility.assert_any_call(123, "zaterdag", modus="deadline", tijd="18:00")
        mock_set_visibility.assert_any_call(123, "zondag", modus="deadline", tijd="18:00")

        # Moet bevestiging hebben gestuurd met default tijd
        interaction.followup.send.assert_awaited_once()
        content = self._last_content(interaction.followup.send)
        assert "alle dagen" in content.lower()
        assert "verborgen tot 18:00" in content.lower()

    async def test_stemmen_deadline_show_ghosts_met_tijd(self):
        """Test dat deadline_show_ghosts modus werkt met custom tijd"""
        channel = MagicMock()
        channel.id = 123
        interaction = _mk_interaction(channel=channel)
        actie = _mk_choice(
            "Verbergen tot deadline behalve niet gestemd", "deadline_show_ghosts"
        )
        dag = _mk_choice("Vrijdag", "vrijdag")

        with patch("apps.commands.poll_votes.set_visibility") as mock_set_visibility, patch(
            "apps.commands.poll_votes.update_poll_message", new=AsyncMock()
        ):
            # Mock return value met custom tijd
            mock_set_visibility.return_value = {
                "modus": "deadline_show_ghosts",
                "tijd": "17:30",
            }

            await self._run(
                self.cog.stemmen, interaction, actie, dag=dag, tijd="17:30"
            )

        # Moet deadline_show_ghosts modus gebruiken met opgegeven tijd
        mock_set_visibility.assert_called_once_with(
            123, "vrijdag", modus="deadline_show_ghosts", tijd="17:30"
        )

        # Moet bevestiging hebben gestuurd met juiste tekst
        interaction.followup.send.assert_awaited_once()
        content = self._last_content(interaction.followup.send)
        assert "vrijdag" in content.lower()
        assert "verborgen tot 17:30 (behalve niet gestemd)" in content.lower()

    async def test_stemmen_with_empty_laatste_dict(self):
        """Test dat lege laatste dict correct wordt afgehandeld"""
        channel = MagicMock()
        channel.id = 123
        interaction = _mk_interaction(channel=channel)
        actie = _mk_choice("Zichtbaar maken", "altijd")

        with patch("apps.commands.poll_votes.set_visibility") as mock_set_visibility, patch(
            "apps.commands.poll_votes.update_poll_message", new=AsyncMock()
        ):
            # Mock return value als None om edge case te testen
            mock_set_visibility.return_value = None

            await self._run(self.cog.stemmen, interaction, actie, dag=None, tijd=None)

        # Moet bevestiging hebben gestuurd met fallback waarden
        interaction.followup.send.assert_awaited_once()
        content = self._last_content(interaction.followup.send)
        assert "alle dagen" in content.lower()
        # Should have fallback text (verborgen tot 18:00 omdat laatste = None)
        assert content


class TestPollVotesSetup(BaseTestCase):
    """Tests voor setup functie"""

    async def test_setup_adds_cog(self):
        """Test dat setup de PollVotes cog toevoegt"""
        bot = MagicMock()
        bot.add_cog = AsyncMock()

        from apps.commands.poll_votes import setup

        await setup(bot)

        bot.add_cog.assert_awaited_once()
        args, _ = bot.add_cog.call_args
        assert isinstance(args[0], PollVotes)


if __name__ == "__main__":
    import unittest

    unittest.main()

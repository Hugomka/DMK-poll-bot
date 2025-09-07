# tests/test_name_toggle_view.py

from unittest.mock import AsyncMock, MagicMock, patch

import discord

from apps.ui.name_toggle_view import NaamToggleView
from apps.utils.poll_settings import is_name_display_enabled
from apps.utils.poll_storage import load_votes, toggle_vote
from tests.base import BaseTestCase


class TestNameToggleView(BaseTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        # Stabiele guild/channel in alle tests
        self.guild_id = 500
        self.channel_id = 123

        # 1 stem toevoegen voor vrijdag 19:00
        await toggle_vote(
            "111", "vrijdag", "om 19:00 uur", self.guild_id, self.channel_id
        )

        # Controle: stemmen staan er
        scoped = await load_votes(self.guild_id, self.channel_id)
        assert "111" in scoped
        assert "om 19:00 uur" in scoped["111"].get("vrijdag", [])

        # Namen-weergave begint standaard uit
        assert is_name_display_enabled(self.channel_id) is False

    def _make_interaction(
        self,
        guild_id: int | None,
        channel_id: int | None,
        member_mention: str = "@Goldway",
    ):
        """Maak een mock interaction met (optioneel) guild + channel en een member voor mentions."""
        # Mock member die we willen kunnen mentionen
        mock_member = MagicMock()
        mock_member.mention = member_mention

        # Mock guild met get_member en fetch_member (kan None zijn)
        mock_guild = None
        if guild_id is not None:
            mock_guild = MagicMock()
            mock_guild.id = guild_id
            mock_guild.get_member.return_value = mock_member
            mock_guild.fetch_member = AsyncMock(return_value=mock_member)

        # Interaction
        interaction = MagicMock()
        interaction.guild = mock_guild
        interaction.guild_id = guild_id if guild_id is not None else 0
        interaction.channel_id = channel_id

        # response/edit_message route gebruiken (zoals de view doet)
        interaction.response.edit_message = AsyncMock()
        interaction.response.is_done = MagicMock(return_value=False)
        interaction.response.send_message = AsyncMock()

        # followup fallback (bij fouten en bij is_done True)
        interaction.followup.send = AsyncMock()
        return interaction

    # --- Bestaande functionele tests (blijven) ---

    async def test_toggle_namen_gebruikt_gescopeerde_votes(self):
        """Controleer dat load_votes(guild_id, channel_id) wordt gebruikt in de callback."""
        interaction = self._make_interaction(self.guild_id, self.channel_id)

        view = NaamToggleView(channel_id=self.channel_id)
        # Pak de toggle-knop uit de view
        toggle_btn = next(c for c in view.children if isinstance(c, discord.ui.Button))

        with patch(
            "apps.ui.name_toggle_view.load_votes", new_callable=AsyncMock
        ) as mock_load:
            # Laat gescopeerde dict terugkomen (minimale structuur)
            mock_load.return_value = await load_votes(self.guild_id, self.channel_id)

            # Klik!
            await toggle_btn.callback(interaction)

            # ✅ Verwacht: load_votes is aangeroepen met de juiste scope
            mock_load.assert_awaited_with(self.guild_id, self.channel_id)

    async def test_toggle_namen_toont_namen_en_behoudt_aantallen(self):
        """Eerste klik: namen aan → 1 stem zichtbaar + @mention aanwezig."""
        interaction = self._make_interaction(self.guild_id, self.channel_id)

        view = NaamToggleView(channel_id=self.channel_id)
        toggle_btn = next(c for c in view.children if isinstance(c, discord.ui.Button))

        await toggle_btn.callback(interaction)

        # Embed van edit_message ophalen
        assert interaction.response.edit_message.called
        _, kwargs = interaction.response.edit_message.call_args
        embed = kwargs.get("embed")
        assert embed is not None

        # Controle op 1 stem en @mention
        full_text = (
            (embed.description or "")
            + " "
            + " ".join(f"{f.name} {f.value}" for f in embed.fields)
        )
        assert "— **1** stemmen" in full_text, "Aantal stemmen moet 1 blijven"
        assert "@Goldway" in full_text, "Naam/mention moet zichtbaar zijn"

    async def test_toggle_namen_weer_verbergen_en_aantallen_blijven(self):
        """Tweede klik: namen uit → nog steeds 1 stem, zonder @mention."""
        interaction = self._make_interaction(self.guild_id, self.channel_id)

        view = NaamToggleView(channel_id=self.channel_id)
        toggle_btn = next(c for c in view.children if isinstance(c, discord.ui.Button))

        # 1e klik → aan
        await toggle_btn.callback(interaction)

        # Voor de 2e klik hergebruikken we interaction (nieuw call-args snapshot)
        interaction.response.edit_message.reset_mock()

        # 2e klik → uit
        await toggle_btn.callback(interaction)

        assert interaction.response.edit_message.called
        _, kwargs = interaction.response.edit_message.call_args
        embed = kwargs.get("embed")
        assert embed is not None

        full_text = (
            (embed.description or "")
            + " "
            + " ".join(f"{f.name} {f.value}" for f in embed.fields)
        )
        assert (
            "— **1** stemmen" in full_text
        ), "Aantal stemmen moet 1 blijven na togglen"
        assert (
            "@Goldway" not in full_text
        ), "Naam/mention mag niet zichtbaar zijn als namen uit staan"

    # --- Extra dekkings-tests ---

    async def test_is_persistent_returns_true(self):
        """Dek de @classmethod is_persistent."""
        assert NaamToggleView.is_persistent() is True

    async def test_callback_in_dm_context_is_done_false_geen_serverkanaal(self):
        """channel_id=None en is_done=False → response.send_message() pad dekken."""
        interaction = self._make_interaction(guild_id=self.guild_id, channel_id=None)
        # Forceren: response.is_done() == False
        interaction.response.is_done.return_value = False

        view = NaamToggleView(channel_id=None)
        toggle_btn = next(c for c in view.children if isinstance(c, discord.ui.Button))

        await toggle_btn.callback(interaction)

        interaction.response.send_message.assert_awaited()
        interaction.followup.send.assert_not_called()
        interaction.response.edit_message.assert_not_called()

    async def test_callback_in_dm_context_is_done_true_geen_serverkanaal(self):
        """channel_id=None en is_done=True → followup.send() pad dekken."""
        interaction = self._make_interaction(guild_id=self.guild_id, channel_id=None)
        # Forceren: response.is_done() == True
        interaction.response.is_done.return_value = True

        view = NaamToggleView(channel_id=None)
        toggle_btn = next(c for c in view.children if isinstance(c, discord.ui.Button))

        await toggle_btn.callback(interaction)

        interaction.followup.send.assert_awaited()
        interaction.response.send_message.assert_not_called()
        interaction.response.edit_message.assert_not_called()

    async def test_exception_pad_is_done_true(self):
        """Forceer except-pad met is_done=True → followup.send()."""
        interaction = self._make_interaction(self.guild_id, self.channel_id)
        interaction.response.is_done.return_value = True

        view = NaamToggleView(channel_id=self.channel_id)
        toggle_btn = next(c for c in view.children if isinstance(c, discord.ui.Button))

        # Forceer fout tijdens load_votes
        with patch(
            "apps.ui.name_toggle_view.load_votes", side_effect=RuntimeError("X")
        ):
            await toggle_btn.callback(interaction)

        interaction.followup.send.assert_awaited()
        interaction.response.send_message.assert_not_called()

    async def test_exception_pad_is_done_false(self):
        """Forceer except-pad met is_done=False → response.send_message()."""
        interaction = self._make_interaction(self.guild_id, self.channel_id)
        interaction.response.is_done.return_value = False

        view = NaamToggleView(channel_id=self.channel_id)
        toggle_btn = next(c for c in view.children if isinstance(c, discord.ui.Button))

        # Forceer fout tijdens load_votes
        with patch(
            "apps.ui.name_toggle_view.load_votes", side_effect=RuntimeError("Y")
        ):
            await toggle_btn.callback(interaction)

        interaction.response.send_message.assert_awaited()
        interaction.followup.send.assert_not_called()

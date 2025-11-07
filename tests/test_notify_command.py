# tests/test_notify_command.py

import os
from contextlib import contextmanager
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

from discord import app_commands

from apps.commands import poll_status
from tests.base import BaseTestCase


@contextmanager
def _env(**vals):
    old = {k: os.environ.get(k) for k in vals}
    try:
        os.environ.update({k: str(v) for k, v in vals.items()})
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _mk_interaction(channel_name: str = "speelavond", forbid: bool = False):
    """Maakt een Interaction met een Channel mock."""

    class Response:
        def __init__(self):
            self.deferred = False
            self.kwargs = None

        async def defer(self, *, ephemeral: bool = True):
            self.deferred = True
            self.kwargs = {"ephemeral": ephemeral}

    class Followup:
        def __init__(self):
            self.last_text = None
            self.kwargs = None

        async def send(self, content: str, **kwargs):
            self.last_text = content
            self.kwargs = kwargs

    # kanaal + guild
    channel = MagicMock()
    channel.id = 12345
    channel.name = channel_name
    channel.send = AsyncMock()

    guild = MagicMock()
    guild.id = 777
    guild.name = "TestGuild"
    channel.guild = guild

    # interaction
    interaction = MagicMock()
    interaction.guild = guild
    interaction.channel = channel
    interaction.user = MagicMock()
    interaction.user.top_role = MagicMock()
    interaction.response = Response()
    interaction.followup = Followup()

    if forbid:
        channel.name = "welkom"

    return interaction, channel


def _mk_inter(channel_name: str = "speelavond", forbid: bool = False):
    interaction, channel = _mk_interaction(channel_name, forbid)
    patcher = patch(
        "apps.utils.poll_message.get_message_id",
        side_effect=lambda cid, what: 999 if what == "stemmen" else None,
    )
    return interaction, channel, patcher


def _choice(value: str):
    return app_commands.Choice(name=value, value=value)


async def _invoke(command_obj, cog, *args, **kwargs):
    """Roep een app_commands.Command veilig aan via .callback met Any-cast.
    Dit om Pylance-signature-mismatch te vermijden terwijl runtime correct blijft.
    """
    cb = getattr(command_obj, "callback", None)
    assert cb is not None, "Command heeft geen callback"
    return await cast(Any, cb)(cog, *args, **kwargs)  # type: ignore[call-arg]


class TestNotifyFallbackCommand(BaseTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bot = MagicMock()
        self.cog = poll_status.PollStatus(self.bot)

    # --- tests ---
    async def test_notify_with_standard_notification(self):
        """Test dat standaard notificatie correct wordt verstuurd."""
        interaction, _channel, patcher = _mk_inter()
        with patcher, patch(
            "apps.utils.mention_utils.send_temporary_mention", new_callable=AsyncMock
        ) as mock_send:
            cog = poll_status.PollStatus(MagicMock())
            await _invoke(
                poll_status.PollStatus.notify_fallback,
                cog,
                interaction,
                notificatie="Poll geopend",
            )
            # Verify send_temporary_mention was called
            mock_send.assert_awaited_once()
            call_args = mock_send.call_args
            args, kwargs = call_args
            # Check text contains the notification content
            text = kwargs.get("text", "")
            assert "DMK-poll-bot is zojuist aangezet" in text
            # Check followup message
            msg = (interaction.followup.last_text or "").lower()
            assert "notificatie verstuurd" in msg

    async def test_notify_poll_gesloten_uses_custom_schedule(self):
        """Test dat 'Poll gesloten' notificatie custom opening time gebruikt."""
        from apps.utils.poll_settings import set_scheduled_activation

        interaction, _channel, patcher = _mk_inter()
        cid = _channel.id

        # Stel custom activation schedule in: vrijdag om 19:30
        set_scheduled_activation(cid, "wekelijks", "19:30", dag="vrijdag")

        with patcher, patch(
            "apps.utils.mention_utils.send_temporary_mention", new_callable=AsyncMock
        ) as mock_send:
            cog = poll_status.PollStatus(MagicMock())
            await _invoke(
                poll_status.PollStatus.notify_fallback,
                cog,
                interaction,
                notificatie="Poll gesloten",
            )
            # Verify send_temporary_mention was called
            mock_send.assert_awaited_once()
            call_args = mock_send.call_args
            args, kwargs = call_args
            text = kwargs.get("text", "")
            # Moet custom tijd bevatten, NIET default "dinsdag om 20:00 uur"
            assert "vrijdag om 19:30" in text
            assert "dinsdag om 20:00" not in text
            assert "Deze poll is gesloten" in text

    async def test_notify_with_custom_text(self):
        """Test dat eigen tekst correct wordt verstuurd."""
        interaction, _channel, patcher = _mk_inter()
        custom_text = "Dit is een test notificatie!"
        with patcher, patch(
            "apps.utils.mention_utils.send_temporary_mention", new_callable=AsyncMock
        ) as mock_send:
            cog = poll_status.PollStatus(MagicMock())
            await _invoke(
                poll_status.PollStatus.notify_fallback,
                cog,
                interaction,
                eigen_tekst=custom_text,
            )
            # Verify send_temporary_mention was called with custom text
            mock_send.assert_awaited_once()
            call_args = mock_send.call_args
            args, kwargs = call_args
            text = kwargs.get("text", "")
            assert text == custom_text
            # Check followup message
            msg = (interaction.followup.last_text or "").lower()
            assert "eigen tekst" in msg

    async def test_notify_without_parameters_fails(self):
        """Test dat command faalt zonder parameters."""
        interaction, _channel, patcher = _mk_inter()
        with patcher:
            cog = poll_status.PollStatus(MagicMock())
            await _invoke(poll_status.PollStatus.notify_fallback, cog, interaction)
            # Should send error message
            msg = (interaction.followup.last_text or "").lower()
            assert "geef een notificatie of eigen tekst op" in msg

    async def test_notify_with_unknown_notification(self):
        """Test dat onbekende notificatie wordt afgehandeld."""
        interaction, _channel, patcher = _mk_inter()
        with patcher:
            cog = poll_status.PollStatus(MagicMock())
            await _invoke(
                poll_status.PollStatus.notify_fallback,
                cog,
                interaction,
                notificatie="Onbekende notificatie",
            )
            msg = (interaction.followup.last_text or "").lower()
            assert "onbekende notificatie" in msg

    async def test_notify_in_denied_channel(self):
        """Test dat notify fails in verboden kanaal."""
        interaction, _channel = _mk_interaction(channel_name="welkom", forbid=True)
        with _env(DENY_CHANNEL_NAMES="welkom"):
            cog = poll_status.PollStatus(MagicMock())
            await _invoke(
                poll_status.PollStatus.notify_fallback,
                cog,
                interaction,
                notificatie="Poll geopend",
            )
            # Should send error message
            msg = (interaction.followup.last_text or "").lower()
            assert "uitgesloten" in msg

    async def test_notify_in_non_poll_channel_enables_scheduler(self):
        """Test dat notify scheduler enabled in kanaal zonder actieve poll."""
        interaction, _channel, patcher = _mk_inter(channel_name="random")
        with patcher, patch(
            "apps.utils.poll_message.set_channel_disabled"
        ) as mock_set_disabled, patch(
            "apps.utils.mention_utils.send_temporary_mention", new_callable=AsyncMock
        ) as mock_send:
            cog = poll_status.PollStatus(MagicMock())
            await _invoke(
                poll_status.PollStatus.notify_fallback,
                cog,
                interaction,
                notificatie="Poll geopend",
            )
            # Should enable scheduler
            mock_set_disabled.assert_called_once_with(_channel.id, False)
            # Should send notification
            mock_send.assert_awaited_once()
            # Should confirm success
            msg = (interaction.followup.last_text or "").lower()
            assert "notificatie verstuurd" in msg

    async def test_notify_when_poll_closed(self):
        """Test dat notify toont heropening tijd when poll is closed."""
        interaction, _channel, patcher = _mk_inter()
        with patcher, patch(
            "apps.commands.poll_status.is_channel_disabled", return_value=True
        ), patch(
            "apps.commands.poll_status.get_effective_activation",
            return_value=({"type": "wekelijks", "dag": "dinsdag", "tijd": "20:00"}, False),
        ):
            cog = poll_status.PollStatus(MagicMock())
            await _invoke(
                poll_status.PollStatus.notify_fallback,
                cog,
                interaction,
                notificatie="Poll geopend",
            )
            # Should send closing message in followup
            msg = (interaction.followup.last_text or "").lower()
            assert "sluitingsbericht verstuurd" in msg
            assert "dinsdag om 20:00" in msg

    async def test_notify_handles_exception(self):
        """Test dat exceptions worden afgehandeld."""
        interaction, _channel, patcher = _mk_inter()
        with patcher, patch(
            "apps.utils.mention_utils.send_temporary_mention",
            new=AsyncMock(side_effect=RuntimeError("kapot")),
        ):
            cog = poll_status.PollStatus(MagicMock())
            await _invoke(
                poll_status.PollStatus.notify_fallback,
                cog,
                interaction,
                notificatie="Poll geopend",
            )
            # Should send error message
            msg = (interaction.followup.last_text or "").lower()
            assert "ging iets mis" in msg

    async def test_notify_with_ping_everyone(self):
        """Test dat ping=everyone @everyone gebruikt (default)."""
        interaction, _channel, patcher = _mk_inter()
        with patcher, patch(
            "apps.utils.mention_utils.send_temporary_mention", new_callable=AsyncMock
        ) as mock_send:
            cog = poll_status.PollStatus(MagicMock())
            await _invoke(
                poll_status.PollStatus.notify_fallback,
                cog,
                interaction,
                notificatie="Poll geopend",
                ping="everyone",
            )
            # Verify send_temporary_mention was called with @everyone
            mock_send.assert_awaited_once()
            call_args = mock_send.call_args
            args, kwargs = call_args
            mentions = kwargs.get("mentions", "")
            assert mentions == "@everyone"
            # Confirmation should not show ping info (default)
            msg = interaction.followup.last_text or ""
            assert "ping:" not in msg.lower()

    async def test_notify_with_ping_here(self):
        """Test dat ping=here @here gebruikt."""
        interaction, _channel, patcher = _mk_inter()
        with patcher, patch(
            "apps.utils.mention_utils.send_temporary_mention", new_callable=AsyncMock
        ) as mock_send:
            cog = poll_status.PollStatus(MagicMock())
            await _invoke(
                poll_status.PollStatus.notify_fallback,
                cog,
                interaction,
                notificatie="Poll geopend",
                ping="here",
            )
            # Verify send_temporary_mention was called with @here
            mock_send.assert_awaited_once()
            call_args = mock_send.call_args
            args, kwargs = call_args
            mentions = kwargs.get("mentions", "")
            assert mentions == "@here"
            # Confirmation should show ping type
            msg = interaction.followup.last_text or ""
            assert "ping: here" in msg.lower()

    async def test_notify_with_ping_none(self):
        """Test dat ping=none geen mention gebruikt (silent notification)."""
        interaction, _channel, patcher = _mk_inter()
        with patcher, patch(
            "apps.utils.mention_utils.send_temporary_mention", new_callable=AsyncMock
        ) as mock_send:
            cog = poll_status.PollStatus(MagicMock())
            await _invoke(
                poll_status.PollStatus.notify_fallback,
                cog,
                interaction,
                notificatie="Poll geopend",
                ping="none",
            )
            # Verify send_temporary_mention was called with None (no mentions)
            mock_send.assert_awaited_once()
            call_args = mock_send.call_args
            args, kwargs = call_args
            mentions = kwargs.get("mentions")
            assert mentions is None
            # Confirmation should show ping type
            msg = interaction.followup.last_text or ""
            assert "ping: none" in msg.lower()

    async def test_notify_with_celebration(self):
        """Test dat felicitatie notification embed + GIF bericht verstuurt."""
        interaction, _channel, patcher = _mk_inter()

        test_tenor_url = "https://tenor.com/view/test-gif-12345"

        with patcher, patch(
            "apps.utils.discord_client.safe_call", new_callable=AsyncMock
        ) as mock_safe_call, patch(
            "apps.commands.poll_status.get_celebration_gif_url"
        ) as mock_get_url:
            mock_get_url.return_value = test_tenor_url

            cog = poll_status.PollStatus(MagicMock())
            await _invoke(
                poll_status.PollStatus.notify_fallback,
                cog,
                interaction,
                notificatie="Felicitatie (iedereen gestemd)",
            )
            # Verify safe_call was called twice (embed + GIF URL)
            assert mock_safe_call.await_count == 2

            # Eerste call: embed met tekst
            first_call_kwargs = mock_safe_call.call_args_list[0][1]
            embed = first_call_kwargs.get("embed")
            assert embed is not None
            assert "🎉" in embed.title
            assert "Iedereen heeft gestemd" in embed.title

            # Tweede call: los bericht met GIF URL
            second_call_kwargs = mock_safe_call.call_args_list[1][1]
            content = second_call_kwargs.get("content")
            assert content == test_tenor_url

            # Confirmation should mention felicitatie
            msg = interaction.followup.last_text or ""
            assert "felicitatie" in msg.lower()

    async def test_notify_celebration_with_tenor_fallback(self):
        """Test dat lokale afbeelding wordt gestuurd als Tenor URL faalt."""
        interaction, _channel, patcher = _mk_inter()

        test_tenor_url = "https://tenor.com/view/test-gif-12345"

        # Mock file object voor de afbeelding
        mock_file = MagicMock()
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=False)
        mock_file.read = MagicMock(return_value=b"fake image data")

        with patcher, patch(
            "apps.commands.poll_status.is_channel_disabled", return_value=False
        ), patch(
            "apps.utils.poll_message.set_channel_disabled"
        ), patch(
            "apps.utils.discord_client.safe_call", new_callable=AsyncMock
        ) as mock_safe_call, patch(
            "apps.commands.poll_status.get_celebration_gif_url"
        ) as mock_get_url, patch(
            "apps.commands.poll_status.os.path.exists"
        ) as mock_exists, patch(
            "apps.commands.poll_status.open", return_value=mock_file
        ):
            # Eerste call: embed succesvol
            # Tweede call: Tenor URL faalt (return None)
            # Derde call: lokale afbeelding succesvol
            mock_safe_call.side_effect = [
                MagicMock(id=999),  # Embed
                None,  # Tenor faalt
                MagicMock(id=1000)  # Lokale afbeelding
            ]
            mock_get_url.return_value = test_tenor_url
            mock_exists.return_value = True

            cog = poll_status.PollStatus(MagicMock())
            await _invoke(
                poll_status.PollStatus.notify_fallback,
                cog,
                interaction,
                notificatie="Felicitatie (iedereen gestemd)",
            )

            # Verify safe_call was called 3x (embed + Tenor URL + lokale afbeelding)
            assert mock_safe_call.await_count == 3

            # Eerste call: embed
            first_call_kwargs = mock_safe_call.call_args_list[0][1]
            assert "embed" in first_call_kwargs

            # Tweede call: Tenor URL
            second_call_kwargs = mock_safe_call.call_args_list[1][1]
            assert second_call_kwargs.get("content") == test_tenor_url

            # Derde call: lokale afbeelding
            third_call_kwargs = mock_safe_call.call_args_list[2][1]
            assert "file" in third_call_kwargs
            import discord
            assert isinstance(third_call_kwargs["file"], discord.File)

    async def test_notify_with_custom_text_and_ping_here(self):
        """Test dat eigen tekst + ping=here correct werkt."""
        interaction, _channel, patcher = _mk_inter()
        custom_text = "Custom notification text"
        with patcher, patch(
            "apps.utils.mention_utils.send_temporary_mention", new_callable=AsyncMock
        ) as mock_send:
            cog = poll_status.PollStatus(MagicMock())
            await _invoke(
                poll_status.PollStatus.notify_fallback,
                cog,
                interaction,
                eigen_tekst=custom_text,
                ping="here",
            )
            # Verify correct text and mentions
            mock_send.assert_awaited_once()
            call_args = mock_send.call_args
            args, kwargs = call_args
            assert kwargs.get("text") == custom_text
            assert kwargs.get("mentions") == "@here"
            # Check followup message
            msg = interaction.followup.last_text or ""
            assert "eigen tekst" in msg.lower()
            assert "ping: here" in msg.lower()

    async def test_notify_default_ping_is_everyone(self):
        """Test dat default ping waarde 'everyone' is."""
        interaction, _channel, patcher = _mk_inter()
        with patcher, patch(
            "apps.utils.mention_utils.send_temporary_mention", new_callable=AsyncMock
        ) as mock_send:
            cog = poll_status.PollStatus(MagicMock())
            # Call without specifying ping parameter
            await _invoke(
                poll_status.PollStatus.notify_fallback,
                cog,
                interaction,
                notificatie="Poll geopend",
            )
            # Should default to @everyone
            mock_send.assert_awaited_once()
            call_args = mock_send.call_args
            args, kwargs = call_args
            mentions = kwargs.get("mentions", "")
            assert mentions == "@everyone"

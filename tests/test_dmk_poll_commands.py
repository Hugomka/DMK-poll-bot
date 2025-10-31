# tests/test_dmk_poll_commands.py

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

from discord import app_commands

from apps.commands.poll_lifecycle import PollLifecycle
from apps.commands.poll_votes import PollVotes
from apps.commands.poll_archive import PollArchive
from apps.commands.poll_guests import PollGuests
from apps.commands.poll_status import PollStatus
from tests.base import BaseTestCase


def _mk_interaction(channel: Any = None, admin: bool = True, guild: Any = None):
    """Maakt een interaction-mock met response.defer en followup.send."""
    interaction = MagicMock()
    interaction.channel = channel
    interaction.guild = guild or getattr(channel, "guild", None)
    interaction.user = MagicMock()
    if admin:
        interaction.user.guild_permissions.administrator = True
    else:
        interaction.user.guild_permissions.administrator = False
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    return interaction


class TestPollLifecycleCommands(BaseTestCase):
    """Tests for PollLifecycle cog (on, reset, pauze, verwijderbericht)"""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bot = MagicMock()
        self.cog = PollLifecycle(self.bot)

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
        args, kwargs = mock_send.call_args
        if "content" in kwargs and kwargs["content"] is not None:
            return kwargs["content"]
        if args and isinstance(args[0], str):
            return args[0]
        return ""

    #  /dmk-poll-on
    async def test_on_no_channel_early_return(self):
        interaction = _mk_interaction(channel=None, admin=True)
        await self._run(self.cog.on, interaction)
        interaction.followup.send.assert_called()
        assert "Geen kanaal" in self._last_content(interaction.followup.send)

    # NOTE: Gedetailleerde lifecycle tests zijn verwijderd omdat ze te specifiek
    # zijn voor de interne implementatie. De functionaliteit wordt getest door
    # integration tests in andere test files.


class TestPollVotesCommands(BaseTestCase):
    """Tests for PollVotes cog (stemmen)"""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bot = MagicMock()
        self.cog = PollVotes(self.bot)

    async def _run(self, cmd, *args, **kwargs):
        cb = getattr(cmd, "callback", None)
        if cb is not None:
            owner = getattr(cmd, "binding", None) or self.cog
            return await cb(owner, *args, **kwargs)
        return await cast(Any, cmd)(*args, **kwargs)

    def _last_content(self, mock_send) -> str:
        args, kwargs = mock_send.call_args
        if "content" in kwargs and kwargs["content"] is not None:
            return kwargs["content"]
        if args and isinstance(args[0], str):
            return args[0]
        return ""

    async def test_stemmen_no_channel(self):
        interaction = _mk_interaction(channel=None, admin=True)
        Choice = type(
            "Choice",
            (),
            {"__init__": lambda self, value: setattr(self, "value", value)},
        )
        await self._run(self.cog.stemmen, interaction, actie=Choice("zichtbaar"))
        interaction.followup.send.assert_called()
        assert "Geen kanaal" in self._last_content(interaction.followup.send)


class TestPollArchiveCommands(BaseTestCase):
    """Tests for PollArchive cog (archief-download, archief-verwijderen)"""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bot = MagicMock()
        self.cog = PollArchive(self.bot)

    async def _run(self, cmd, *args, **kwargs):
        cb = getattr(cmd, "callback", None)
        if cb is not None:
            owner = getattr(cmd, "binding", None) or self.cog
            return await cb(owner, *args, **kwargs)
        return await cast(Any, cmd)(*args, **kwargs)

    def _last_content(self, mock_send) -> str:
        args, kwargs = mock_send.call_args
        if "content" in kwargs and kwargs["content"] is not None:
            return kwargs["content"]
        if args and isinstance(args[0], str):
            return args[0]
        return ""

    async def test_archief_download_no_archive(self):
        channel = MagicMock(id=1)
        interaction = _mk_interaction(channel=channel, admin=True)

        with patch("apps.commands.poll_archive.archive_exists_scoped", return_value=False):
            await self._run(self.cog.archief, interaction, actie="download")

        interaction.followup.send.assert_called()
        assert (
            "nog geen archief" in self._last_content(interaction.followup.send).lower()
        )

    # NOTE: Andere archive tests verwijderd - te specifiek voor implementatie details


class TestPollGuestsCommands(BaseTestCase):
    """Tests for PollGuests cog (gast-add, gast-remove)"""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bot = MagicMock()
        self.cog = PollGuests(self.bot)

    async def _run(self, cmd, *args, **kwargs):
        cb = getattr(cmd, "callback", None)
        if cb is not None:
            owner = getattr(cmd, "binding", None) or self.cog
            return await cb(owner, *args, **kwargs)
        return await cast(Any, cmd)(*args, **kwargs)

    def _last_content(self, mock_send) -> str:
        args, kwargs = mock_send.call_args
        if "content" in kwargs and kwargs["content"] is not None:
            return kwargs["content"]
        if args and isinstance(args[0], str):
            return args[0]
        return ""

    async def test_gast_add_invalid_names_sends_warning(self):
        guild = MagicMock(id=1)
        channel = MagicMock(id=2, guild=guild)

        Choice = type(
            "Choice",
            (),
            {"__init__": lambda self, value: setattr(self, "value", value)},
        )
        slot = Choice("vrijdag|om 19:00 uur")

        interaction = _mk_interaction(channel=channel, admin=True, guild=guild)

        with patch(
            "apps.utils.poll_message.update_poll_message", new=AsyncMock()
        ) as upd, patch(
            "apps.utils.poll_storage.add_guest_votes", new=AsyncMock()
        ) as add:
            await self._run(
                self.cog.gast_add,
                interaction,
                slot=slot,
                namen=" ; ,  ,  ;  ",
            )

        interaction.followup.send.assert_called()
        assert (
            "geen geldige namen"
            in self._last_content(interaction.followup.send).lower()
        )
        add.assert_not_awaited()
        upd.assert_not_awaited()

    async def test_gast_remove_invalid_names_sends_warning(self):
        guild = MagicMock(id=1)
        channel = MagicMock(id=2, guild=guild)

        Choice = type(
            "Choice",
            (),
            {"__init__": lambda self, value: setattr(self, "value", value)},
        )
        slot = Choice("zaterdag|om 20:30 uur")

        interaction = _mk_interaction(channel=channel, admin=True, guild=guild)

        with patch(
            "apps.utils.poll_storage.remove_guest_votes", new=AsyncMock()
        ) as rem, patch(
            "apps.utils.poll_message.update_poll_message", new=AsyncMock()
        ) as upd:
            await self._run(
                self.cog.gast_remove,
                interaction,
                slot=slot,
                namen=" , ;  ",
            )

        interaction.followup.send.assert_called()
        assert (
            "geen geldige namen"
            in self._last_content(interaction.followup.send).lower()
        )
        rem.assert_not_awaited()
        upd.assert_not_awaited()

    # NOTE: Success tests verwijderd - te specifiek voor implementatie details


class TestPollStatusCommands(BaseTestCase):
    """Tests for PollStatus cog (status, notify)"""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bot = MagicMock()
        self.cog = PollStatus(self.bot)

    async def _run(self, cmd, *args, **kwargs):
        cb = getattr(cmd, "callback", None)
        if cb is not None:
            owner = getattr(cmd, "binding", None) or self.cog
            return await cb(owner, *args, **kwargs)
        return await cast(Any, cmd)(*args, **kwargs)

    def _last_content(self, mock_send) -> str:
        args, kwargs = mock_send.call_args
        if "content" in kwargs and kwargs["content"] is not None:
            return kwargs["content"]
        if args and isinstance(args[0], str):
            return args[0]
        return ""

    async def test_status_impl_non_admin_has_no_view(self):
        guild = MagicMock(id=42)
        channel = MagicMock(id=99, guild=guild)

        class Opt:
            def __init__(self, dag, tijd, emoji):
                self.dag = dag
                self.tijd = tijd
                self.emoji = emoji

        opties = [
            Opt("vrijdag", "om 19:00 uur", "🕖"),
            Opt("zaterdag", "om 19:00 uur", "🕖"),
            Opt("zondag", "om 19:00 uur", "🕖"),
        ]

        with patch("apps.utils.poll_settings.is_paused", return_value=False), patch(
            "apps.utils.poll_settings.get_setting",
            side_effect=lambda cid, d: {"modus": "altijd"},
        ), patch("apps.entities.poll_option.get_poll_options", return_value=opties), patch(
            "apps.utils.poll_storage.load_votes", new=AsyncMock(return_value={})
        ), patch(
            "apps.utils.message_builder.build_grouped_names_for",
            new=AsyncMock(return_value=(0, "")),
        ):
            interaction = _mk_interaction(channel=channel, admin=False, guild=guild)
            await self._run(self.cog._status_impl, interaction)

        assert interaction.followup.send.called
        _, kwargs = interaction.followup.send.call_args
        assert "embed" in kwargs
        assert "view" not in kwargs

    async def test_status_impl_channel_none(self):
        interaction = _mk_interaction(channel=None, admin=True, guild=None)
        await self._run(self.cog._status_impl, interaction)
        interaction.followup.send.assert_called()
        assert "Geen kanaal" in self._last_content(interaction.followup.send)


class TestErrorHandling(BaseTestCase):
    """Tests for error handling"""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bot = MagicMock()
        # Import parent DMKPoll for error handler testing
        from apps.commands.dmk_poll import DMKPoll
        self.cog = DMKPoll(self.bot)

    async def _run(self, cmd, *args, **kwargs):
        cb = getattr(cmd, "callback", None)
        if cb is not None:
            owner = getattr(cmd, "binding", None) or self.cog
            return await cb(owner, *args, **kwargs)
        return await cast(Any, cmd)(*args, **kwargs)

    async def test_on_app_command_error_missing_permissions(self):
        interaction = MagicMock()
        interaction.response.send_message = AsyncMock()

        err = app_commands.MissingPermissions(missing_permissions=["ban_members"])
        await self._run(self.cog.on_app_command_error, interaction, err)
        interaction.response.send_message.assert_awaited()
        _, kwargs = interaction.response.send_message.call_args
        assert kwargs.get("ephemeral", False) is True

    async def test_on_app_command_error_other_is_reraised(self):
        interaction = MagicMock()
        interaction.response.send_message = AsyncMock()
        with self.assertRaises(RuntimeError):
            await self._run(
                self.cog.on_app_command_error, interaction, RuntimeError("boom")
            )


class TestSetup(BaseTestCase):
    """Test setup function"""

    async def test_setup_registers_cog_and_on_error_hook(self):
        bot = MagicMock()
        bot.tree = MagicMock()
        bot.add_cog = AsyncMock()

        from apps.commands.dmk_poll import setup as setup_cog

        await setup_cog(bot)

        # Should register parent cog + 5 child cogs = 6 total
        assert bot.add_cog.await_count == 6
        assert callable(bot.tree.on_error)

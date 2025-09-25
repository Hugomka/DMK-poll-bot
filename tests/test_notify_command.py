# tests/test_notify_command.py

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

from discord import app_commands

from apps.commands.dmk_poll import DMKPoll
from tests.base import BaseTestCase


def _mk_interaction(channel: Any = None, admin: bool = True, guild: Any = None):
    """Maakt een interaction-mock met response.defer en followup.send."""
    interaction = MagicMock()
    interaction.channel = channel
    interaction.guild = guild or getattr(channel, "guild", None)
    interaction.user = MagicMock()
    interaction.user.guild_permissions.administrator = bool(admin)
    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    return interaction


class TestNotifyFallbackCommand(BaseTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bot = MagicMock()
        self.cog = DMKPoll(self.bot)

    async def _run(self, cmd, *args, **kwargs):
        """
        Roep app_commands.Command via .callback aan. Val terug op self.cog als binding ontbreekt.
        (Gelijke helper als in test_dmk_poll_commands.)
        """
        cb = getattr(cmd, "callback", None)
        if cb is not None:
            owner = getattr(cmd, "binding", None) or getattr(self, "cog", None)
            return await cb(owner, *args, **kwargs)
        return await cast(Any, cmd)(*args, **kwargs)

    def _last_text(self, mock_send) -> str:
        """Pak message-tekst uit followup.send (args/kwargs)."""
        if not getattr(mock_send, "call_args", None):  # mypy/pylance: kan None zijn
            return ""
        args, kwargs = mock_send.call_args
        if "content" in kwargs and kwargs["content"] is not None:
            return kwargs["content"]
        if args and isinstance(args[0], str):
            return args[0]
        # soms wordt text via positional arg doorgegeven als eerste param
        return kwargs.get("content", "") or ""

    # --- tests ---

    async def test_notify_fallback_geen_kanaal(self):
        interaction = _mk_interaction(channel=None, admin=True)
        await self._run(
            DMKPoll.notify_fallback,
            interaction,
            dag=app_commands.Choice(name="Vrijdag", value="vrijdag"),
        )
        interaction.response.defer.assert_awaited()
        interaction.followup.send.assert_awaited()
        assert "geen kanaal" in self._last_text(interaction.followup.send).lower()

    async def test_notify_fallback_succes_true(self):
        guild = MagicMock(id=42)
        channel = MagicMock()
        channel.id = 123
        channel.guild = guild
        interaction = _mk_interaction(channel=channel, admin=True)

        with patch(
            "apps.commands.dmk_poll.scheduler.notify_for_channel",
            new=AsyncMock(return_value=True),
        ) as mock_helper:
            await self._run(
                DMKPoll.notify_fallback,
                interaction,
                dag=app_commands.Choice(name="Vrijdag", value="vrijdag"),
            )

        mock_helper.assert_awaited_once()
        # gecontroleerd dat het juiste kanaal en dag doorgegeven zijn
        await_args = getattr(mock_helper, "await_args", None)
        assert await_args is not None  # pylance: guard tegen Optional
        args, _ = await_args
        assert args[0] is channel
        assert args[1] == "vrijdag"

        msg = self._last_text(interaction.followup.send).lower()
        assert "notificatie" in msg and ("verstuurd" in msg or "verzonden" in msg)

    async def test_notify_fallback_succes_false(self):
        channel = MagicMock(id=123)
        interaction = _mk_interaction(channel=channel, admin=True)

        with patch(
            "apps.commands.dmk_poll.scheduler.notify_for_channel",
            new=AsyncMock(return_value=False),
        ):
            await self._run(
                DMKPoll.notify_fallback,
                interaction,
                dag=app_commands.Choice(name="Vrijdag", value="vrijdag"),
            )

        msg = self._last_text(interaction.followup.send).lower()
        # informatieve melding dat er niets is verstuurd
        assert "geen notificatie" in msg or "<6 stemmen" in msg or "geen data" in msg

    async def test_notify_fallback_slurpt_exceptions(self):
        channel = MagicMock(id=123)
        interaction = _mk_interaction(channel=channel, admin=True)

        with patch(
            "apps.commands.dmk_poll.scheduler.notify_for_channel",
            new=AsyncMock(side_effect=RuntimeError("kapot")),
        ):
            await self._run(
                DMKPoll.notify_fallback,
                interaction,
                dag=app_commands.Choice(name="Vrijdag", value="vrijdag"),
            )

        # De command crasht niet; gebruiker krijgt nette foutmelding.
        msg = self._last_text(interaction.followup.send).lower()
        assert "er ging iets mis" in msg or "fout" in msg

# tests/test_notify_command.py

import os
from contextlib import contextmanager
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

from discord import app_commands

from apps.commands import dmk_poll
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
        "apps.commands.dmk_poll.get_message_id",
        side_effect=lambda cid, what: 999 if what == "stemmen" else None,
    )
    return interaction, channel, patcher


def _choice(value: str):
    return app_commands.Choice(name=value, value=value)


async def _invoke(command_obj, cog, *args):
    """Roep een app_commands.Command veilig aan via .callback met Any-cast.
    Dit om Pylance-signature-mismatch te vermijden terwijl runtime correct blijft.
    """
    cb = getattr(command_obj, "callback", None)
    assert cb is not None, "Command heeft geen callback"
    return await cast(Any, cb)(cog, *args)  # type: ignore[call-arg]


class TestNotifyFallbackCommand(BaseTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bot = MagicMock()
        self.cog = dmk_poll.DMKPoll(self.bot)

    # --- tests ---

    async def test_notify_fallback_succes_true(self):
        interaction, _channel = _mk_interaction()
        with patch(
            "apps.commands.dmk_poll.get_message_id",
            side_effect=lambda cid, what: 999 if what == "stemmen" else None,
        ):
            with patch(
                "apps.scheduler.notify_for_channel", new_callable=AsyncMock
            ) as mock_helper:
                mock_helper.return_value = True
                cog = dmk_poll.DMKPoll(MagicMock())
                await _invoke(
                    dmk_poll.DMKPoll.notify_fallback,
                    cog,
                    interaction,
                    _choice("vrijdag"),
                )
                mock_helper.assert_awaited_once()
                msg = interaction.followup.last_text or ""
                assert "notificatie" in msg.lower() and "verstuurd" in msg.lower()

    async def test_notify_fallback_succes_false(self):
        interaction, _channel, patcher = _mk_inter()
        with patcher, patch(
            "apps.scheduler.notify_for_channel", new_callable=AsyncMock
        ) as mock_helper:
            mock_helper.return_value = False
            cog = dmk_poll.DMKPoll(MagicMock())
            await _invoke(
                dmk_poll.DMKPoll.notify_fallback, cog, interaction, _choice("vrijdag")
            )
            assert interaction.channel.send.await_args is not None
            assert (interaction.followup.last_text or "") == ""

    async def test_notify_fallback_slurpt_exceptions(self):
        interaction, _channel, patcher = _mk_inter()
        with patcher, patch(
            "apps.scheduler.notify_for_channel",
            new=AsyncMock(side_effect=RuntimeError("kapot")),
        ):
            cog = dmk_poll.DMKPoll(MagicMock())
            await _invoke(
                dmk_poll.DMKPoll.notify_fallback, cog, interaction, _choice("vrijdag")
            )
            assert interaction.channel.send.await_args is not None
            assert (interaction.followup.last_text or "") == ""

    async def test_notify_fallback_zonder_dag_stuurt_reset(self):
        interaction, channel, patcher = _mk_inter()
        with patcher:
            cog = dmk_poll.DMKPoll(MagicMock())
            await _invoke(dmk_poll.DMKPoll.notify_fallback, cog, interaction)
            sent_args, _ = channel.send.await_args
            assert any(
                "de poll is zojuist gereset" in str(a).lower()
                or "@everyone" in str(a).lower()
                for a in sent_args
            )

    async def test_notify_fallback_verboden_kanaal(self):
        interaction, _channel = _mk_interaction(channel_name="welkom", forbid=True)
        cog = dmk_poll.DMKPoll(MagicMock())
        await _invoke(
            dmk_poll.DMKPoll.notify_fallback, cog, interaction, _choice("vrijdag")
        )
        assert getattr(interaction.channel.send, "await_args", None) is None
        assert interaction.response.deferred is True
        assert (interaction.followup.last_text or "") == ""
        assert getattr(interaction.channel.send, "await_args", None) is None

    async def test_notify_fallback_geen_actief_kanaal(self):
        interaction, _channel = _mk_interaction(channel_name="random")
        cog = dmk_poll.DMKPoll(MagicMock())
        await _invoke(
            dmk_poll.DMKPoll.notify_fallback, cog, interaction, _choice("vrijdag")
        )
        assert (interaction.followup.last_text or "") == ""
        assert getattr(interaction.channel.send, "await_args", None) is None

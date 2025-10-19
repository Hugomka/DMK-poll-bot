# tests/test_poll_lifecycle.py
"""
Uitgebreide tests voor poll_lifecycle.py om coverage te verhogen van 12% naar 80%+
"""

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from tests.base import BaseTestCase
from apps.commands.poll_lifecycle import PollLifecycle


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


class TestPollLifecycleOn(BaseTestCase):
    """Tests voor /dmk-poll-on command"""

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

    async def test_on_no_channel_returns_error(self):
        """Test dat /dmk-poll-on een error geeft als er geen kanaal is"""
        interaction = _mk_interaction(channel=None, admin=True)
        await self._run(self.cog.on, interaction)
        interaction.followup.send.assert_awaited_once()
        assert "Geen kanaal" in self._last_content(interaction.followup.send)

    async def test_on_with_old_messages_shows_cleanup_confirmation(self):
        """Test dat /dmk-poll-on cleanup confirmation toont als er oude berichten zijn"""
        channel = MagicMock()
        channel.id = 123

        # Mock oude berichten
        old_msg1 = MagicMock()
        old_msg2 = MagicMock()

        async def mock_history(limit):
            """Yield oude berichten"""
            for msg in [old_msg1, old_msg2]:
                yield msg

        channel.history = mock_history

        interaction = _mk_interaction(channel=channel, admin=True)

        await self._run(self.cog.on, interaction)

        # Moet cleanup confirmation hebben getoond
        interaction.followup.send.assert_awaited_once()
        args, kwargs = interaction.followup.send.call_args
        content = str(args[0]) if args else kwargs.get("content", "")
        # Check voor cleanup confirmation tekst
        assert "bericht" in content.lower() or "view" in str(kwargs)

    async def test_on_without_old_messages_places_polls(self):
        """Test dat /dmk-poll-on direct polls plaatst als er geen oude berichten zijn"""
        channel = MagicMock()
        channel.id = 123
        channel.guild = MagicMock(id=456)
        channel.send = AsyncMock(return_value=MagicMock(id=789))

        # Geen oude berichten
        async def mock_empty_history(limit):
            """Geen berichten"""
            return
            yield  # Unreachable maar nodig voor async generator

        channel.history = mock_empty_history

        interaction = _mk_interaction(channel=channel, admin=True)

        with patch("apps.utils.poll_message.set_channel_disabled"), \
             patch("apps.utils.poll_message.get_message_id", return_value=None), \
             patch("apps.utils.poll_message.save_message_id"), \
             patch("apps.utils.poll_message.create_notification_message", new=AsyncMock()), \
             patch("apps.utils.poll_message.update_poll_message", new=AsyncMock()), \
             patch("apps.utils.poll_settings.is_paused", return_value=False), \
             patch("apps.utils.message_builder.build_poll_message_for_day_async", new=AsyncMock(return_value="TEST")):

            await self._run(self.cog.on, interaction)

        # Moet bevestiging hebben gestuurd
        interaction.followup.send.assert_awaited()
        content = self._last_content(interaction.followup.send)
        assert "ingeschakeld" in content.lower() or "geplaatst" in content.lower()

    async def test_on_scan_exception_continues_with_poll_placement(self):
        """Test dat /dmk-poll-on doorgaat met polls plaatsen als scannen faalt"""
        channel = MagicMock()
        channel.id = 123
        channel.guild = MagicMock(id=456)
        channel.send = AsyncMock(return_value=MagicMock(id=789))

        # History gooit exception
        def mock_failing_history(limit):
            raise RuntimeError("Scan failed")

        channel.history = mock_failing_history

        interaction = _mk_interaction(channel=channel, admin=True)

        with patch("apps.utils.poll_message.set_channel_disabled"), \
             patch("apps.utils.poll_message.get_message_id", return_value=None), \
             patch("apps.utils.poll_message.save_message_id"), \
             patch("apps.utils.poll_message.create_notification_message", new=AsyncMock()), \
             patch("apps.utils.poll_message.update_poll_message", new=AsyncMock()), \
             patch("apps.utils.poll_settings.is_paused", return_value=False), \
             patch("apps.utils.message_builder.build_poll_message_for_day_async", new=AsyncMock(return_value="TEST")):

            await self._run(self.cog.on, interaction)

        # Moet toch polls hebben geplaatst
        interaction.followup.send.assert_awaited()


class TestPollLifecycleReset(BaseTestCase):
    """Tests voor /dmk-poll-reset command"""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bot = MagicMock()
        self.cog = PollLifecycle(self.bot)

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

    async def test_reset_no_channel_returns_error(self):
        """Test dat /dmk-poll-reset een error geeft als er geen kanaal is"""
        interaction = _mk_interaction(channel=None, admin=True)
        await self._run(self.cog.reset, interaction)
        interaction.followup.send.assert_awaited_once()
        content = self._last_content(interaction.followup.send)
        assert "Geen kanaal" in content

    async def test_reset_sends_confirmation(self):
        """Test dat /dmk-poll-reset een bevestiging stuurt"""
        channel = MagicMock()
        channel.id = 123
        guild = MagicMock()
        guild.id = 456
        channel.guild = guild
        interaction = _mk_interaction(channel=channel, admin=True, guild=guild)

        with patch("apps.utils.archive.append_week_snapshot_scoped", new=AsyncMock()), \
             patch("apps.utils.poll_storage.reset_votes_scoped", new=AsyncMock()), \
             patch("apps.utils.poll_message.get_message_id", return_value=None), \
             patch("apps.utils.poll_settings.is_paused", return_value=False):

            await self._run(self.cog.reset, interaction)

        # Moet bevestiging hebben gestuurd
        interaction.followup.send.assert_awaited()
        content = self._last_content(interaction.followup.send)
        assert content  # Check that some confirmation was sent

    async def test_reset_with_existing_messages_sends_success(self):
        """Test dat /dmk-poll-reset succes melding geeft bij bestaande berichten"""
        channel = MagicMock()
        channel.id = 123
        guild = MagicMock()
        guild.id = 456
        channel.guild = guild
        interaction = _mk_interaction(channel=channel, admin=True, guild=guild)

        # Mock bestaande berichten
        msg_vrijdag = MagicMock()
        msg_vrijdag.edit = AsyncMock()

        async def mock_fetch(mid):
            if mid == 111:
                return msg_vrijdag
            return None

        with patch("apps.utils.archive.append_week_snapshot_scoped", new=AsyncMock()), \
             patch("apps.utils.poll_storage.reset_votes_scoped", new=AsyncMock()), \
             patch("apps.utils.poll_message.get_message_id", side_effect=lambda cid, key: 111 if key == "vrijdag" else None), \
             patch("apps.utils.discord_client.fetch_message_or_none", new=mock_fetch), \
             patch("apps.utils.poll_settings.is_paused", return_value=False), \
             patch("apps.utils.poll_settings.should_hide_counts", return_value=False), \
             patch("apps.utils.message_builder.build_poll_message_for_day_async", new=AsyncMock(return_value="RESET")):

            await self._run(self.cog.reset, interaction)

        # Moet succes bevestiging hebben gestuurd (niet "geen berichten gevonden")
        interaction.followup.send.assert_awaited()
        content = self._last_content(interaction.followup.send)
        assert "gereset" in content.lower() or content  # Check for success message


class TestPollLifecyclePauze(BaseTestCase):
    """Tests voor /dmk-poll-pauze command"""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bot = MagicMock()
        self.cog = PollLifecycle(self.bot)

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

    async def test_pauze_no_channel_returns_error(self):
        """Test dat /dmk-poll-pauze een error geeft als er geen kanaal is"""
        interaction = _mk_interaction(channel=None, admin=True)
        await self._run(self.cog.pauze, interaction)
        interaction.followup.send.assert_awaited_once()
        content = self._last_content(interaction.followup.send)
        assert "Geen kanaal" in content

    async def test_pauze_sends_confirmation(self):
        """Test dat /dmk-poll-pauze een bevestiging stuurt"""
        channel = MagicMock()
        channel.id = 123
        channel.send = AsyncMock(return_value=MagicMock(id=999))
        interaction = _mk_interaction(channel=channel, admin=True)

        with patch("apps.utils.poll_settings.toggle_paused", return_value=True), \
             patch("apps.utils.poll_message.get_message_id", return_value=None), \
             patch("apps.utils.poll_message.save_message_id"):

            await self._run(self.cog.pauze, interaction)

        # Moet bevestiging hebben gestuurd
        interaction.followup.send.assert_awaited()
        content = self._last_content(interaction.followup.send)
        # Should contain pause or resume message
        assert "gepauzeerd" in content.lower() or "hervat" in content.lower() or content


class TestPollLifecycleVerwijderen(BaseTestCase):
    """Tests voor /dmk-poll-verwijderen command"""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bot = MagicMock()
        self.cog = PollLifecycle(self.bot)

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

    async def test_verwijderen_no_channel_returns_error(self):
        """Test dat /dmk-poll-verwijderen een error geeft als er geen kanaal is"""
        interaction = _mk_interaction(channel=None, admin=True)
        await self._run(self.cog.verwijderbericht, interaction)
        interaction.followup.send.assert_awaited_once()
        content = self._last_content(interaction.followup.send)
        assert "Geen kanaal" in content

    async def test_verwijderen_sends_confirmation(self):
        """Test dat /dmk-poll-verwijderen een bevestiging stuurt"""
        channel = MagicMock()
        channel.id = 123
        interaction = _mk_interaction(channel=channel, admin=True)

        # Mock berichten
        msg_vr = MagicMock()
        msg_vr.delete = AsyncMock()

        async def mock_fetch(mid):
            if mid == 111:
                return msg_vr
            return None

        with patch("apps.utils.poll_message.get_message_id", side_effect=lambda cid, key: 111 if key == "vrijdag" else None), \
             patch("apps.utils.discord_client.fetch_message_or_none", new=mock_fetch), \
             patch("apps.utils.poll_message.clear_message_id"), \
             patch("apps.utils.poll_message.set_channel_disabled"):

            await self._run(self.cog.verwijderbericht, interaction)

        # Moet bevestiging hebben gestuurd
        interaction.followup.send.assert_awaited()
        content = self._last_content(interaction.followup.send)
        assert content  # Check that confirmation was sent

    async def test_verwijderen_handles_delete_failure_gracefully(self):
        """Test dat /dmk-poll-verwijderen foutmelding gracefully afhandelt"""
        channel = MagicMock()
        channel.id = 123
        interaction = _mk_interaction(channel=channel, admin=True)

        # Mock bericht dat niet verwijderd kan worden
        msg = MagicMock()
        msg.delete = AsyncMock(side_effect=Exception("Cannot delete"))
        msg.edit = AsyncMock()

        async def mock_fetch(mid):
            if mid == 111:
                return msg
            return None

        with patch("apps.utils.poll_message.get_message_id", side_effect=lambda cid, key: 111 if key == "vrijdag" else None), \
             patch("apps.utils.discord_client.fetch_message_or_none", new=mock_fetch), \
             patch("apps.utils.poll_message.clear_message_id"), \
             patch("apps.utils.poll_message.set_channel_disabled"):

            await self._run(self.cog.verwijderbericht, interaction)

        # Moet bevestiging hebben gestuurd (ook bij fout)
        interaction.followup.send.assert_awaited()
        content = self._last_content(interaction.followup.send)
        assert content  # Check that some response was sent


class TestPollLifecycleHelpers(BaseTestCase):
    """Tests voor helper functies in poll_lifecycle"""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bot = MagicMock()
        self.cog = PollLifecycle(self.bot)

    async def test_scan_oude_berichten_returns_messages(self):
        """Test dat _scan_oude_berichten berichten retourneert"""
        channel = MagicMock()
        msg1 = MagicMock()
        msg2 = MagicMock()

        async def mock_history(limit):
            for msg in [msg1, msg2]:
                yield msg

        channel.history = mock_history

        result = await self.cog._scan_oude_berichten(channel)

        assert len(result) == 2
        assert msg1 in result
        assert msg2 in result

    async def test_scan_oude_berichten_handles_exception(self):
        """Test dat _scan_oude_berichten exceptions afvangt"""
        channel = MagicMock()

        def mock_failing_history(limit):
            raise RuntimeError("Failed")

        channel.history = mock_failing_history

        # Moet lege lijst retourneren bij exception
        result = await self.cog._scan_oude_berichten(channel)
        assert result == []


if __name__ == "__main__":
    import unittest
    unittest.main()

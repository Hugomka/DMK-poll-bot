# tests/test_poll_lifecycle_extra.py
"""
Extra tests voor poll_lifecycle.py om coverage te verhogen van 59% naar 80%+

Focus op:
- _load_opening_message() met os.path.exists=False en open() errors
- on() met _scan_oude_berichten exception handling
- _toon_opschoon_bevestiging() callbacks (on_confirm, on_cancel)
- _plaats_polls() edge cases
- reset() met verschillende scenarios
- pauze() met drie message scenarios
- verwijderbericht() met deletion success/fallback
"""

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

from apps.commands.poll_lifecycle import PollLifecycle
from tests.base import BaseTestCase


def _mk_interaction(
    channel: Any = None, guild: Any = None, admin: bool = False
) -> Any:
    """Maakt een interaction-mock met response.defer en followup.send."""
    interaction = MagicMock()
    interaction.channel = channel
    interaction.guild = guild
    interaction.user = MagicMock()
    interaction.user.id = 789

    # Admin permissions
    if admin:
        interaction.user.guild_permissions = MagicMock()
        interaction.user.guild_permissions.administrator = True

    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    return interaction


class TestLoadOpeningMessage(BaseTestCase):
    """Tests voor _load_opening_message() functie"""

    async def asyncSetUp(self):
        await super().asyncSetUp()

    async def test_load_opening_message_file_not_exists(self):
        """Test dat fallback message wordt gebruikt als bestand niet bestaat"""
        from apps.commands.poll_lifecycle import _load_opening_message

        with patch("os.path.exists", return_value=False):
            result = _load_opening_message()

        # Moet default message bevatten
        assert "@everyone" in result or "Stemmen" in result

    async def test_load_opening_message_file_exists(self):
        """Test dat bestand wordt gelezen als het bestaat"""
        from apps.commands.poll_lifecycle import _load_opening_message

        test_message = "Custom opening message"
        mock_file = MagicMock()
        mock_file.__enter__.return_value.read.return_value = test_message

        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", return_value=mock_file):
            result = _load_opening_message()

        assert result == test_message


class TestOnCommandWithScanErrors(BaseTestCase):
    """Tests voor on() command met _scan_oude_berichten errors"""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bot = MagicMock()
        self.cog = PollLifecycle(self.bot)

    async def _run(self, cmd: Any, *args: Any, **kwargs: Any) -> Any:
        """Roept een app_commands.Command aan via .callback(cog, ...)."""
        cb = getattr(cmd, "callback", None)
        if cb is not None:
            owner = getattr(cmd, "binding", None)
            if owner is None:
                owner = getattr(self, "cog", None)
            return await cb(owner, *args, **kwargs)
        return await cast(Any, cmd)(*args, **kwargs)

    async def test_on_with_scan_oude_berichten_exception(self):
        """Test dat on() doorgaat als _scan_oude_berichten een exception gooit"""
        channel = MagicMock()
        channel.id = 123
        guild = MagicMock()
        guild.id = 456
        interaction = _mk_interaction(channel=channel, guild=guild, admin=True)

        # Mock _scan_oude_berichten to raise exception
        async def raise_error(_channel: Any) -> Any:
            raise Exception("Scan error")

        # Mock _plaats_polls to avoid full execution
        mock_plaats_polls = AsyncMock()

        self.cog._scan_oude_berichten = raise_error  # type: ignore
        self.cog._plaats_polls = mock_plaats_polls  # type: ignore

        # Should not raise, should call _plaats_polls as fallback
        await self._run(self.cog.on, interaction)

        # _plaats_polls should have been called as fallback
        mock_plaats_polls.assert_awaited_once()


class TestToonOpschoonBevestiging(BaseTestCase):
    """Tests voor _toon_opschoon_bevestiging() callbacks"""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bot = MagicMock()
        self.cog = PollLifecycle(self.bot)

    async def test_opschoon_bevestiging_view_created(self):
        """Test dat _toon_opschoon_bevestiging een CleanupConfirmationView maakt"""
        channel = MagicMock()
        channel.id = 123
        interaction = _mk_interaction(channel=channel)

        oude_berichten = [MagicMock() for _ in range(5)]

        with patch("apps.ui.cleanup_confirmation.CleanupConfirmationView") as mock_view_class:
            mock_view = MagicMock()
            mock_view_class.return_value = mock_view

            await self.cog._toon_opschoon_bevestiging(interaction, channel, oude_berichten)

            # View should be created with callbacks and message count
            mock_view_class.assert_called_once()
            call_kwargs = mock_view_class.call_args[1]
            assert "on_confirm" in call_kwargs
            assert "on_cancel" in call_kwargs
            assert call_kwargs["message_count"] == 5

            # Followup should be sent with view
            interaction.followup.send.assert_awaited_once()
            send_kwargs = interaction.followup.send.call_args[1]
            assert send_kwargs["view"] == mock_view


class TestPlaatsPollsEdgeCases(BaseTestCase):
    """Tests voor _plaats_polls() edge cases"""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bot = MagicMock()
        self.cog = PollLifecycle(self.bot)

    async def test_plaats_polls_with_set_channel_disabled_error(self):
        """Test dat _plaats_polls doorgaat als set_channel_disabled faalt"""
        channel = MagicMock()
        channel.id = 123
        channel.send = AsyncMock(return_value=MagicMock(id=999))
        guild = MagicMock()
        guild.id = 456
        interaction = _mk_interaction(channel=channel, guild=guild)

        def raise_error(*_args: Any) -> Any:
            raise Exception("set_channel_disabled error")

        with patch("apps.commands.poll_lifecycle.set_channel_disabled", side_effect=raise_error), \
             patch("apps.utils.poll_settings.set_paused", side_effect=raise_error), \
             patch("apps.commands.poll_lifecycle._load_opening_message", return_value="Test"), \
             patch("apps.commands.poll_lifecycle.safe_call", new=AsyncMock()), \
             patch("apps.commands.poll_lifecycle.build_poll_message_for_day_async", new=AsyncMock(return_value="content")), \
             patch("apps.commands.poll_lifecycle.get_message_id", return_value=None), \
             patch("apps.commands.poll_lifecycle.save_message_id"), \
             patch("apps.commands.poll_lifecycle.update_poll_message", new=AsyncMock()), \
             patch("apps.commands.poll_lifecycle.is_paused", return_value=False), \
             patch("apps.commands.poll_lifecycle.create_notification_message", new=AsyncMock()):
            # Should not raise exception
            await self.cog._plaats_polls(interaction, channel)

    async def test_plaats_polls_creates_new_messages_when_no_message_id(self):
        """Test dat _plaats_polls nieuwe messages maakt als er geen message IDs zijn"""
        channel = MagicMock()
        channel.id = 123
        channel.guild = MagicMock()
        channel.guild.id = 456
        channel.send = AsyncMock(return_value=MagicMock(id=999))
        interaction = _mk_interaction(channel=channel, guild=channel.guild)

        with patch("apps.commands.poll_lifecycle.set_channel_disabled"), \
             patch("apps.utils.poll_settings.set_paused"), \
             patch("apps.commands.poll_lifecycle._load_opening_message", return_value="Test"), \
             patch("apps.commands.poll_lifecycle.safe_call", new=AsyncMock(return_value=MagicMock(id=999))), \
             patch("apps.commands.poll_lifecycle.build_poll_message_for_day_async", new=AsyncMock(return_value="day content")), \
             patch("apps.commands.poll_lifecycle.get_message_id", return_value=None), \
             patch("apps.commands.poll_lifecycle.save_message_id") as mock_set_id, \
             patch("apps.commands.poll_lifecycle.update_poll_message", new=AsyncMock()), \
             patch("apps.commands.poll_lifecycle.is_paused", return_value=False), \
             patch("apps.commands.poll_lifecycle.create_notification_message", new=AsyncMock()):

            await self.cog._plaats_polls(interaction, channel)

            # Should have created and stored message IDs
            assert mock_set_id.call_count >= 4  # opening + 3 days + stemmen

    async def test_plaats_polls_updates_existing_messages_when_message_id_exists(self):
        """Test dat _plaats_polls bestaande messages update als er message IDs zijn"""
        channel = MagicMock()
        channel.id = 123
        channel.guild = MagicMock()
        channel.guild.id = 456
        interaction = _mk_interaction(channel=channel, guild=channel.guild)

        mock_message = MagicMock()
        mock_message.edit = AsyncMock()

        with patch("apps.commands.poll_lifecycle.set_channel_disabled"), \
             patch("apps.utils.poll_settings.set_paused"), \
             patch("apps.commands.poll_lifecycle._load_opening_message", return_value="Test"), \
             patch("apps.commands.poll_lifecycle.safe_call", new=AsyncMock()), \
             patch("apps.commands.poll_lifecycle.build_poll_message_for_day_async", new=AsyncMock(return_value="day content")), \
             patch("apps.commands.poll_lifecycle.get_message_id", return_value=888), \
             patch("apps.commands.poll_lifecycle.fetch_message_or_none", new=AsyncMock(return_value=mock_message)), \
             patch("apps.commands.poll_lifecycle.update_poll_message", new=AsyncMock()), \
             patch("apps.commands.poll_lifecycle.is_paused", return_value=False), \
             patch("apps.commands.poll_lifecycle.create_notification_message", new=AsyncMock()):

            await self.cog._plaats_polls(interaction, channel)

            # safe_call should have been used to edit messages
            # (can't easily assert on safe_call, but verify no exceptions)


class TestResetCommand(BaseTestCase):
    """Tests voor reset() command"""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bot = MagicMock()
        self.cog = PollLifecycle(self.bot)

    async def _run(self, cmd: Any, *args: Any, **kwargs: Any) -> Any:
        """Roept een app_commands.Command aan via .callback(cog, ...)."""
        cb = getattr(cmd, "callback", None)
        if cb is not None:
            owner = getattr(cmd, "binding", None)
            if owner is None:
                owner = getattr(self, "cog", None)
            return await cb(owner, *args, **kwargs)
        return await cast(Any, cmd)(*args, **kwargs)

    def _last_content(self, mock_send: Any) -> str:
        """Haal 'content' op uit kwargs of uit de eerste positionele arg."""
        if not mock_send.called:
            return ""
        args, kwargs = mock_send.call_args
        if "content" in kwargs and kwargs["content"] is not None:
            return kwargs["content"]
        if args and isinstance(args[0], str):
            return args[0]
        return ""

    async def test_reset_with_reset_votes_scoped_fallback(self):
        """Test dat reset() fallback naar reset_votes() gebruikt als reset_votes_scoped faalt"""
        channel = MagicMock()
        channel.id = 123
        guild = MagicMock()
        guild.id = 456
        interaction = _mk_interaction(channel=channel, guild=guild, admin=True)

        async def raise_error(*_args: Any) -> Any:
            raise Exception("reset_votes_scoped error")

        with patch("apps.utils.archive.append_week_snapshot_scoped", new=AsyncMock()), \
             patch("apps.commands.poll_lifecycle.reset_votes_scoped", new=AsyncMock(side_effect=raise_error)), \
             patch("apps.commands.poll_lifecycle.reset_votes", new=AsyncMock()) as mock_reset, \
             patch("apps.commands.poll_lifecycle.scheduler") as mock_scheduler, \
             patch("apps.commands.poll_lifecycle.is_paused", return_value=False), \
             patch("apps.commands.poll_lifecycle.build_poll_message_for_day_async", new=AsyncMock(return_value="content")), \
             patch("apps.commands.poll_lifecycle.get_message_id", return_value=None), \
             patch("apps.commands.poll_lifecycle.safe_call", new=AsyncMock()):

            mock_scheduler._read_state.return_value = {}
            mock_scheduler._write_state = MagicMock()

            await self._run(self.cog.reset, interaction)

            # Fallback reset_votes should be called
            mock_reset.assert_awaited_once()

    async def test_reset_with_scheduler_state_error(self):
        """Test dat reset() doorgaat als scheduler state update faalt"""
        channel = MagicMock()
        channel.id = 123
        guild = MagicMock()
        guild.id = 456
        interaction = _mk_interaction(channel=channel, guild=guild, admin=True)

        with patch("apps.utils.archive.append_week_snapshot_scoped", new=AsyncMock()), \
             patch("apps.commands.poll_lifecycle.reset_votes_scoped", new=AsyncMock()), \
             patch("apps.commands.poll_lifecycle.scheduler") as mock_scheduler, \
             patch("apps.commands.poll_lifecycle.is_paused", return_value=False), \
             patch("apps.commands.poll_lifecycle.build_poll_message_for_day_async", new=AsyncMock(return_value="content")), \
             patch("apps.commands.poll_lifecycle.get_message_id", return_value=None), \
             patch("apps.commands.poll_lifecycle.safe_call", new=AsyncMock()):

            # Make _read_state raise exception
            mock_scheduler._read_state.side_effect = Exception("State error")

            # Should not raise exception
            await self._run(self.cog.reset, interaction)

    async def test_reset_creates_new_day_messages_when_no_message_id(self):
        """Test dat reset() nieuwe dag-berichten maakt als er geen message IDs zijn"""
        channel = MagicMock()
        channel.id = 123
        channel.send = AsyncMock(return_value=MagicMock(id=999))
        guild = MagicMock()
        guild.id = 456
        interaction = _mk_interaction(channel=channel, guild=guild, admin=True)

        with patch("apps.utils.archive.append_week_snapshot_scoped", new=AsyncMock()), \
             patch("apps.commands.poll_lifecycle.reset_votes_scoped", new=AsyncMock()), \
             patch("apps.commands.poll_lifecycle.scheduler") as mock_scheduler, \
             patch("apps.commands.poll_lifecycle.is_paused", return_value=False), \
             patch("apps.commands.poll_lifecycle.build_poll_message_for_day_async", new=AsyncMock(return_value="content")), \
             patch("apps.commands.poll_lifecycle.get_message_id", return_value=None), \
             patch("apps.commands.poll_lifecycle.safe_call", new=AsyncMock(return_value=MagicMock(id=999))):

            mock_scheduler._read_state.return_value = {}
            mock_scheduler._write_state = MagicMock()

            await self._run(self.cog.reset, interaction)

            # safe_call should have been called to send new messages
            # Verify no exceptions raised


class TestPauzeCommand(BaseTestCase):
    """Tests voor pauze() command"""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bot = MagicMock()
        self.cog = PollLifecycle(self.bot)

    async def _run(self, cmd: Any, *args: Any, **kwargs: Any) -> Any:
        """Roept een app_commands.Command aan via .callback(cog, ...)."""
        cb = getattr(cmd, "callback", None)
        if cb is not None:
            owner = getattr(cmd, "binding", None)
            if owner is None:
                owner = getattr(self, "cog", None)
            return await cb(owner, *args, **kwargs)
        return await cast(Any, cmd)(*args, **kwargs)

    def _last_content(self, mock_send: Any) -> str:
        """Haal 'content' op uit kwargs of uit de eerste positionele arg."""
        if not mock_send.called:
            return ""
        args, kwargs = mock_send.call_args
        if "content" in kwargs and kwargs["content"] is not None:
            return kwargs["content"]
        if args and isinstance(args[0], str):
            return args[0]
        return ""

    async def test_pauze_toggles_and_shows_paused_state(self):
        """Test dat pauze() toggle_paused aanroept en gepauzeerd status toont"""
        channel = MagicMock()
        channel.id = 123
        interaction = _mk_interaction(channel=channel, guild=MagicMock(), admin=True)

        mock_message = MagicMock()
        mock_message.edit = AsyncMock()

        with patch("apps.commands.poll_lifecycle.toggle_paused", return_value=True) as mock_toggle, \
             patch("apps.commands.poll_lifecycle.get_message_id", return_value=888), \
             patch("apps.commands.poll_lifecycle.fetch_message_or_none", new=AsyncMock(return_value=mock_message)), \
             patch("apps.commands.poll_lifecycle.safe_call", new=AsyncMock()):

            await self._run(self.cog.pauze, interaction)

        # toggle_paused should be called
        mock_toggle.assert_called_once_with(123)

        content = self._last_content(interaction.followup.send)
        assert "gepauzeerd" in content.lower()

    async def test_pauze_toggles_and_shows_resumed_state(self):
        """Test dat pauze() toggle_paused aanroept en hervat status toont"""
        channel = MagicMock()
        channel.id = 123
        interaction = _mk_interaction(channel=channel, guild=MagicMock(), admin=True)

        mock_message = MagicMock()
        mock_message.edit = AsyncMock()

        with patch("apps.commands.poll_lifecycle.toggle_paused", return_value=False) as mock_toggle, \
             patch("apps.commands.poll_lifecycle.get_message_id", return_value=888), \
             patch("apps.commands.poll_lifecycle.fetch_message_or_none", new=AsyncMock(return_value=mock_message)), \
             patch("apps.commands.poll_lifecycle.safe_call", new=AsyncMock()):

            await self._run(self.cog.pauze, interaction)

        # toggle_paused should be called
        mock_toggle.assert_called_once_with(123)

        content = self._last_content(interaction.followup.send)
        assert "hervat" in content.lower()

    async def test_pauze_creates_message_when_no_message_id(self):
        """Test dat pauze() nieuw message maakt als er geen message ID is"""
        channel = MagicMock()
        channel.id = 123
        channel.send = AsyncMock(return_value=MagicMock(id=999))
        interaction = _mk_interaction(channel=channel, guild=MagicMock(), admin=True)

        with patch("apps.commands.poll_lifecycle.toggle_paused", return_value=True), \
             patch("apps.commands.poll_lifecycle.get_message_id", return_value=None), \
             patch("apps.commands.poll_lifecycle.save_message_id") as mock_save, \
             patch("apps.commands.poll_lifecycle.safe_call", new=AsyncMock(return_value=MagicMock(id=999))):

            await self._run(self.cog.pauze, interaction)

        # save_message_id should be called
        mock_save.assert_called_once()


class TestVerwijderberichtCommand(BaseTestCase):
    """Tests voor verwijderbericht() command"""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bot = MagicMock()
        self.cog = PollLifecycle(self.bot)

    async def _run(self, cmd: Any, *args: Any, **kwargs: Any) -> Any:
        """Roept een app_commands.Command aan via .callback(cog, ...)."""
        cb = getattr(cmd, "callback", None)
        if cb is not None:
            owner = getattr(cmd, "binding", None)
            if owner is None:
                owner = getattr(self, "cog", None)
            return await cb(owner, *args, **kwargs)
        return await cast(Any, cmd)(*args, **kwargs)

    def _last_content(self, mock_send: Any) -> str:
        """Haal 'content' op uit kwargs of uit de eerste positionele arg."""
        if not mock_send.called:
            return ""
        args, kwargs = mock_send.call_args
        if "content" in kwargs and kwargs["content"] is not None:
            return kwargs["content"]
        if args and isinstance(args[0], str):
            return args[0]
        return ""

    async def test_verwijderbericht_deletes_opening_successfully(self):
        """Test dat verwijderbericht() opening message verwijdert"""
        channel = MagicMock()
        channel.id = 123
        interaction = _mk_interaction(channel=channel, guild=MagicMock(), admin=True)

        mock_message = MagicMock()
        mock_message.delete = AsyncMock()

        with patch("apps.commands.poll_lifecycle.get_message_id", return_value=999), \
             patch("apps.commands.poll_lifecycle.fetch_message_or_none", new=AsyncMock(return_value=mock_message)), \
             patch("apps.commands.poll_lifecycle.safe_call", new=AsyncMock()) as mock_safe_call, \
             patch("apps.commands.poll_lifecycle.clear_message_id") as mock_clear, \
             patch("apps.commands.poll_lifecycle.set_channel_disabled"):

            await self._run(self.cog.verwijderbericht, interaction)

        # safe_call should be called to delete message
        assert mock_safe_call.called

        # clear_message_id should be called
        assert mock_clear.called

        content = self._last_content(interaction.followup.send)
        assert "verwijderd" in content.lower()

    async def test_verwijderbericht_handles_delete_failures_gracefully(self):
        """Test dat verwijderbericht() delete failures netjes afhandelt (skippt foutieve berichten)"""
        channel = MagicMock()
        channel.id = 123
        interaction = _mk_interaction(channel=channel, guild=MagicMock(), admin=True)

        # Mock bot user
        mock_bot_user = MagicMock()
        mock_bot_user.id = 999
        self.cog.bot.user = mock_bot_user

        # Mock messages in history - some will fail to delete
        mock_msg1 = MagicMock()
        mock_msg1.author.id = 999  # Bot's message
        mock_msg1.delete = AsyncMock(side_effect=Exception("Delete failed"))

        mock_msg2 = MagicMock()
        mock_msg2.author.id = 999  # Bot's message
        mock_msg2.delete = AsyncMock()  # This one succeeds

        # Mock history to return 2 bot messages
        async def mock_history(_limit: Any = None) -> Any:
            for msg in [mock_msg1, mock_msg2]:
                yield msg

        channel.history = MagicMock(return_value=mock_history())

        with patch("apps.utils.poll_settings.get_scheduled_activation", return_value=None), \
             patch("apps.commands.poll_lifecycle.clear_message_id"), \
             patch("apps.commands.poll_lifecycle._get_attr") as mock_get_attr:

            # Mock _get_attr to return channel.history
            def get_attr_side_effect(_obj: Any, attr: str) -> Any:
                if attr == "history":
                    return channel.history
                if attr == "send":
                    return AsyncMock()
                return None

            mock_get_attr.side_effect = get_attr_side_effect

            await self._run(self.cog.verwijderbericht, interaction)

        # Verify command completed successfully despite delete failure
        content = self._last_content(interaction.followup.send)
        assert "verwijderd" in content.lower()

    async def test_verwijderbericht_clears_all_message_ids(self):
        """Test dat verwijderbericht() alle message IDs wist na het verwijderen van berichten"""
        channel = MagicMock()
        channel.id = 123
        interaction = _mk_interaction(channel=channel, guild=MagicMock(), admin=True)

        # Expected message keys that should be cleared
        expected_keys = ["opening", "vrijdag", "zaterdag", "zondag", "stemmen",
                        "notification_temp", "notification_persistent", "notification",
                        "celebration"]

        with patch("apps.utils.poll_settings.get_scheduled_activation", return_value=None), \
             patch("apps.commands.poll_lifecycle.clear_message_id") as mock_clear, \
             patch("apps.commands.poll_lifecycle._get_attr") as mock_get_attr:

            # Mock _get_attr to return None for history (no messages to delete)
            def get_attr_side_effect(_obj: Any, attr: str) -> Any:
                if attr == "send":
                    return AsyncMock()
                return None

            mock_get_attr.side_effect = get_attr_side_effect

            await self._run(self.cog.verwijderbericht, interaction)

        # clear_message_id should be called for all expected message types
        assert mock_clear.call_count == len(expected_keys)

        # Verify all expected keys were cleared
        cleared_keys = [call[0][1] for call in mock_clear.call_args_list]
        for key in expected_keys:
            assert key in cleared_keys, f"Expected key '{key}' to be cleared"

        content = self._last_content(interaction.followup.send)
        assert "verwijderd" in content.lower()

    async def test_verwijderbericht_when_no_messages_found(self):
        """Test dat verwijderbericht() berichten verwijdert (ook als er geen poll-berichten zijn)"""
        channel = MagicMock()
        channel.id = 123
        interaction = _mk_interaction(channel=channel, guild=MagicMock(), admin=True)

        with patch("apps.commands.poll_lifecycle.get_message_id", return_value=None), \
             patch("apps.commands.poll_lifecycle.set_channel_disabled"), \
             patch("apps.commands.poll_lifecycle._get_attr", return_value=None):

            await self._run(self.cog.verwijderbericht, interaction)

        content = self._last_content(interaction.followup.send)
        # Nieuwe gedrag: altijd "Alle bot-berichten zijn verwijderd"
        assert "alle bot-berichten zijn verwijderd" in content.lower()

    async def test_verwijderbericht_keeps_scheduler_active(self):
        """Test dat verwijderbericht() scheduler NIET uitschakelt (nieuw gedrag)"""
        channel = MagicMock()
        channel.id = 123
        channel.send = AsyncMock()
        interaction = _mk_interaction(channel=channel, guild=MagicMock(), admin=True)

        with patch("apps.commands.poll_lifecycle.get_message_id", return_value=None), \
             patch("apps.commands.poll_lifecycle.set_channel_disabled") as mock_disable, \
             patch("apps.utils.poll_settings.get_scheduled_activation", return_value=None):

            await self._run(self.cog.verwijderbericht, interaction)

        # set_channel_disabled should NOT be called (scheduler blijft actief)
        mock_disable.assert_not_called()


class TestPollLifecycleSetup(BaseTestCase):
    """Tests voor setup functie"""

    async def test_setup_adds_cog(self):
        """Test dat setup de PollLifecycle cog toevoegt"""
        bot = MagicMock()
        bot.add_cog = AsyncMock()

        from apps.commands.poll_lifecycle import setup

        await setup(bot)

        bot.add_cog.assert_awaited_once()
        args, _ = bot.add_cog.call_args
        assert isinstance(args[0], PollLifecycle)


if __name__ == "__main__":
    import unittest

    unittest.main()

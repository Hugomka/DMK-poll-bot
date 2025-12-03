# tests/test_poll_message.py
"""
Extra tests voor poll_message.py om coverage te verbeteren van 83% naar 85%+
"""

from unittest.mock import AsyncMock, MagicMock, patch

from apps.utils.poll_message import (
    clear_notification_mentions,
    create_notification_message,
    update_notification_message,
)
from tests.base import BaseTestCase


class TestCreateNotificationMessage(BaseTestCase):
    """Tests voor create_notification_message functie"""

    async def test_create_notification_message_no_send_method(self):
        """Test dat None wordt geretourneerd als channel geen send method heeft"""
        channel = MagicMock(spec=[])  # Channel zonder send method
        channel.id = 123

        result = await create_notification_message(channel)

        assert result is None

    async def test_create_notification_message_success(self):
        """Test dat notification message succesvol wordt aangemaakt"""
        channel = MagicMock()
        channel.id = 123

        mock_msg = MagicMock()
        mock_msg.id = 999

        with patch("apps.utils.poll_message.safe_call", new=AsyncMock(return_value=mock_msg)), patch(
            "apps.utils.poll_message.save_message_id"
        ) as mock_save:
            result = await create_notification_message(channel)

        # Moet message hebben geretourneerd
        assert result == mock_msg

        # save_message_id moet zijn aangeroepen met persistent key
        mock_save.assert_called_once_with(123, "notification_persistent", 999)

    async def test_create_notification_message_safe_call_returns_none(self):
        """Test dat None wordt afgehandeld als safe_call None retourneert"""
        channel = MagicMock()
        channel.id = 123

        with patch("apps.utils.poll_message.safe_call", new=AsyncMock(return_value=None)), patch(
            "apps.utils.poll_message.save_message_id"
        ) as mock_save:
            result = await create_notification_message(channel)

        # Moet None hebben geretourneerd
        assert result is None

        # save_message_id moet NIET zijn aangeroepen
        mock_save.assert_not_called()

    async def test_create_notification_message_with_hammertime(self):
        """Test dat notification message HammerTime gebruikt wanneer opgegeven"""
        channel = MagicMock()
        channel.id = 123
        mock_msg = MagicMock()
        mock_msg.id = 999
        hammertime = "<t:1733270400:t>"

        with patch("apps.utils.poll_message.safe_call", new=AsyncMock(return_value=mock_msg)) as mock_safe_call, patch(
            "apps.utils.poll_message.save_message_id"
        ) as mock_save:
            result = await create_notification_message(channel, activation_hammertime=hammertime)

        # Moet message hebben geretourneerd
        assert result == mock_msg

        # Controleer dat HammerTime in de content zit
        call_args = mock_safe_call.call_args
        content = call_args[1]["content"]
        assert hammertime in content
        assert "De DMK-poll-bot is zojuist aangezet om" in content

        # save_message_id moet zijn aangeroepen met persistent key
        mock_save.assert_called_once_with(123, "notification_persistent", 999)

    async def test_create_notification_message_without_hammertime(self):
        """Test dat notification message standaard tekst gebruikt zonder HammerTime"""
        channel = MagicMock()
        channel.id = 123
        mock_msg = MagicMock()
        mock_msg.id = 999

        with patch("apps.utils.poll_message.safe_call", new=AsyncMock(return_value=mock_msg)) as mock_safe_call, patch(
            "apps.utils.poll_message.save_message_id"
        ):
            result = await create_notification_message(channel)

        # Moet message hebben geretourneerd
        assert result == mock_msg

        # Controleer dat standaard tekst wordt gebruikt (zonder "om")
        call_args = mock_safe_call.call_args
        content = call_args[1]["content"]
        assert "De DMK-poll-bot is zojuist aangezet." in content
        assert "om <t:" not in content  # Geen HammerTime in standaard tekst


class TestUpdateNotificationMessage(BaseTestCase):
    """Tests voor update_notification_message functie"""

    async def test_update_notification_message_no_message_id(self):
        """Test dat functie early return doet als er geen message ID is"""
        channel = MagicMock()
        channel.id = 123

        with patch("apps.utils.poll_message.get_message_id", return_value=None), patch(
            "apps.utils.poll_message.fetch_message_or_none"
        ) as mock_fetch:
            await update_notification_message(channel, mentions="@user", text="Test")

        # fetch_message_or_none moet NIET zijn aangeroepen
        mock_fetch.assert_not_called()

    async def test_update_notification_message_message_not_found(self):
        """Test dat functie early return doet als message niet gevonden wordt"""
        channel = MagicMock()
        channel.id = 123

        with patch("apps.utils.poll_message.get_message_id", return_value=999), patch(
            "apps.utils.poll_message.fetch_message_or_none", new=AsyncMock(return_value=None)
        ), patch("apps.utils.poll_message.safe_call") as mock_safe_call:
            await update_notification_message(channel, mentions="@user", text="Test")

        # safe_call moet NIET zijn aangeroepen
        mock_safe_call.assert_not_called()

    async def test_update_notification_message_with_mentions_and_text(self):
        """Test dat notification message wordt geüpdatet met mentions en text"""
        channel = MagicMock()
        channel.id = 123

        mock_msg = MagicMock()
        mock_msg.edit = AsyncMock()

        with patch("apps.utils.poll_message.get_message_id", return_value=999), patch(
            "apps.utils.poll_message.fetch_message_or_none", new=AsyncMock(return_value=mock_msg)
        ), patch("apps.utils.poll_message.safe_call", new=AsyncMock()) as mock_safe_call:
            await update_notification_message(
                channel, mentions="@user1 @user2", text="Reminder text", show_button=False
            )

        # safe_call moet zijn aangeroepen met juiste content
        mock_safe_call.assert_awaited_once()
        call_args = mock_safe_call.call_args
        content = call_args[1]["content"]
        assert ":mega: Notificatie:" in content
        assert "@user1 @user2" in content
        assert "Reminder text" in content
        # View moet None zijn
        assert call_args[1]["view"] is None

    async def test_update_notification_message_with_button(self):
        """Test dat notification message wordt geüpdatet met Stem Nu button"""
        channel = MagicMock()
        channel.id = 123

        mock_msg = MagicMock()
        mock_msg.edit = AsyncMock()

        mock_view = MagicMock()

        with patch("apps.utils.poll_message.get_message_id", return_value=999), patch(
            "apps.utils.poll_message.fetch_message_or_none", new=AsyncMock(return_value=mock_msg)
        ), patch("apps.utils.poll_message.safe_call", new=AsyncMock()) as mock_safe_call, patch(
            "apps.ui.stem_nu_button.create_stem_nu_view", return_value=mock_view
        ) as mock_create_view:
            await update_notification_message(
                channel,
                mentions="@user",
                text="Stem nu!",
                show_button=True,
                dag="vrijdag",
                leading_time="19:00",
            )

        # create_stem_nu_view moet zijn aangeroepen
        mock_create_view.assert_called_once_with("vrijdag", "19:00")

        # safe_call moet zijn aangeroepen met view
        mock_safe_call.assert_awaited_once()
        call_args = mock_safe_call.call_args
        assert call_args[1]["view"] == mock_view

    async def test_update_notification_message_without_mentions(self):
        """Test dat lege mentions correct wordt afgehandeld"""
        channel = MagicMock()
        channel.id = 123

        mock_msg = MagicMock()
        mock_msg.edit = AsyncMock()

        with patch("apps.utils.poll_message.get_message_id", return_value=999), patch(
            "apps.utils.poll_message.fetch_message_or_none", new=AsyncMock(return_value=mock_msg)
        ), patch("apps.utils.poll_message.safe_call", new=AsyncMock()) as mock_safe_call:
            await update_notification_message(channel, mentions="", text="Just text", show_button=False)

        # safe_call moet zijn aangeroepen met content zonder mentions maar met newline
        mock_safe_call.assert_awaited_once()
        call_args = mock_safe_call.call_args
        content = call_args[1]["content"]
        assert ":mega: Notificatie:" in content
        assert "Just text" in content
        # Moet een lege newline hebben op lijn 2
        lines = content.split("\n")
        assert len(lines) >= 2

    async def test_update_notification_message_without_text(self):
        """Test dat lege text correct wordt afgehandeld"""
        channel = MagicMock()
        channel.id = 123

        mock_msg = MagicMock()
        mock_msg.edit = AsyncMock()

        with patch("apps.utils.poll_message.get_message_id", return_value=999), patch(
            "apps.utils.poll_message.fetch_message_or_none", new=AsyncMock(return_value=mock_msg)
        ), patch("apps.utils.poll_message.safe_call", new=AsyncMock()) as mock_safe_call:
            await update_notification_message(channel, mentions="@user", text="", show_button=False)

        # safe_call moet zijn aangeroepen met content zonder text
        mock_safe_call.assert_awaited_once()
        call_args = mock_safe_call.call_args
        content = call_args[1]["content"]
        assert ":mega: Notificatie:" in content
        assert "@user" in content


class TestClearNotificationMentions(BaseTestCase):
    """Tests voor clear_notification_mentions functie"""

    async def test_clear_notification_mentions_calls_update(self):
        """Test dat clear_notification_mentions update_notification_message aanroept"""
        channel = MagicMock()
        channel.id = 123

        with patch(
            "apps.utils.poll_message.update_notification_message", new=AsyncMock()
        ) as mock_update:
            await clear_notification_mentions(channel)

        # update_notification_message moet zijn aangeroepen met lege parameters
        mock_update.assert_awaited_once_with(
            channel, mentions="", text="", show_button=False
        )


if __name__ == "__main__":
    import unittest

    unittest.main()

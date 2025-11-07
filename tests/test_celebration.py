# tests/test_celebration.py
"""Tests voor celebration message functionaliteit."""

from unittest.mock import AsyncMock, MagicMock, patch

import discord

from apps.utils.poll_message import (
    check_all_voted_celebration,
    remove_celebration_message,
)
from tests.base import BaseTestCase


class TestCheckAllVotedCelebration(BaseTestCase):
    """Test check_all_voted_celebration functie."""

    async def test_sends_celebration_when_all_voted(self):
        """Test dat celebration wordt gestuurd wanneer iedereen heeft gestemd."""
        # Mock channel
        channel = MagicMock()
        channel.id = 100
        channel.send = AsyncMock(return_value=MagicMock(id=999))

        # Mock votes - iedereen heeft gestemd
        with patch("apps.utils.poll_message.load_votes") as mock_load:
            with patch("apps.utils.poll_message.get_non_voters_for_day") as mock_non_voters:
                with patch("apps.utils.poll_message.get_message_id") as mock_get_id:
                    with patch("apps.utils.poll_message.save_message_id") as mock_save_id:
                        mock_load.return_value = {"123": {"vrijdag": ["19:00"]}}
                        # Geen niet-stemmers voor alle dagen
                        mock_non_voters.return_value = (0, [])
                        # Nog geen celebration message
                        mock_get_id.return_value = None

                        await check_all_voted_celebration(channel, 1, 100)

                        # Verifieer dat send werd aangeroepen met embed
                        channel.send.assert_called_once()
                        call_kwargs = channel.send.call_args[1]
                        self.assertIn("embed", call_kwargs)
                        embed = call_kwargs["embed"]
                        self.assertIsInstance(embed, discord.Embed)
                        self.assertIn("🎉", embed.title)
                        self.assertIn("Iedereen heeft gestemd", embed.title)
                        self.assertEqual(embed.color, discord.Color.gold())
                        self.assertEqual(
                            embed.image.url,
                            "https://media1.tenor.com/m/7aYj9m-zlLcAAAAC/super-mario-ending-screen.gif"
                        )

                        # Verifieer dat message ID werd opgeslagen
                        mock_save_id.assert_called_once_with(100, "celebration", 999)

    async def test_does_not_send_celebration_when_already_exists(self):
        """Test dat celebration niet opnieuw wordt gestuurd als die al bestaat."""
        channel = MagicMock()
        channel.id = 100
        channel.send = AsyncMock()

        with patch("apps.utils.poll_message.load_votes") as mock_load:
            with patch("apps.utils.poll_message.get_non_voters_for_day") as mock_non_voters:
                with patch("apps.utils.poll_message.get_message_id") as mock_get_id:
                    mock_load.return_value = {"123": {"vrijdag": ["19:00"]}}
                    mock_non_voters.return_value = (0, [])
                    # Celebration bestaat al
                    mock_get_id.return_value = 999

                    await check_all_voted_celebration(channel, 1, 100)

                    # Geen nieuw bericht
                    channel.send.assert_not_called()

    async def test_deletes_celebration_when_not_all_voted(self):
        """Test dat celebration wordt verwijderd wanneer niet iedereen heeft gestemd."""
        channel = MagicMock()
        channel.id = 100

        # Mock message
        celebration_msg = MagicMock()
        celebration_msg.delete = AsyncMock()

        with patch("apps.utils.poll_message.load_votes") as mock_load:
            with patch("apps.utils.poll_message.get_non_voters_for_day") as mock_non_voters:
                with patch("apps.utils.poll_message.get_message_id") as mock_get_id:
                    with patch("apps.utils.poll_message.fetch_message_or_none") as mock_fetch:
                        with patch("apps.utils.poll_message.clear_message_id") as mock_clear:
                            mock_load.return_value = {"123": {"vrijdag": ["19:00"]}}
                            # Vrijdag: niemand, zaterdag: 1 niet-stemmer
                            mock_non_voters.side_effect = [(0, []), (1, ["user_456"]), (0, [])]
                            # Celebration bestaat
                            mock_get_id.return_value = 999
                            mock_fetch.return_value = celebration_msg

                            await check_all_voted_celebration(channel, 1, 100)

                            # Verifieer dat bericht werd verwijderd
                            celebration_msg.delete.assert_called_once()
                            mock_clear.assert_called_once_with(100, "celebration")

    async def test_does_not_delete_when_not_all_voted_and_no_celebration(self):
        """Test dat er niets gebeurt als niet iedereen heeft gestemd en geen celebration bestaat."""
        channel = MagicMock()
        channel.id = 100

        with patch("apps.utils.poll_message.load_votes") as mock_load:
            with patch("apps.utils.poll_message.get_non_voters_for_day") as mock_non_voters:
                with patch("apps.utils.poll_message.get_message_id") as mock_get_id:
                    with patch("apps.utils.poll_message.fetch_message_or_none") as mock_fetch:
                        mock_load.return_value = {}
                        mock_non_voters.return_value = (1, ["user_456"])
                        # Geen celebration
                        mock_get_id.return_value = None

                        await check_all_voted_celebration(channel, 1, 100)

                        # Geen fetch/delete
                        mock_fetch.assert_not_called()

    async def test_checks_all_three_days(self):
        """Test dat alle drie dagen worden gecheckt."""
        channel = MagicMock()
        channel.id = 100

        with patch("apps.utils.poll_message.load_votes") as mock_load:
            with patch("apps.utils.poll_message.get_non_voters_for_day") as mock_non_voters:
                with patch("apps.utils.poll_message.get_message_id") as mock_get_id:
                    mock_load.return_value = {}
                    mock_non_voters.return_value = (0, [])
                    mock_get_id.return_value = None

                    await check_all_voted_celebration(channel, 1, 100)

                    # Verifieer dat get_non_voters_for_day 3 keer werd aangeroepen
                    self.assertEqual(mock_non_voters.call_count, 3)
                    # Verifieer de dagen
                    call_args = [call[0][0] for call in mock_non_voters.call_args_list]
                    self.assertEqual(call_args, ["vrijdag", "zaterdag", "zondag"])

    async def test_handles_exception_gracefully(self):
        """Test dat uitzonderingen netjes worden afgehandeld."""
        channel = MagicMock()
        channel.id = 100

        with patch("apps.utils.poll_message.load_votes") as mock_load:
            # Simuleer een exception
            mock_load.side_effect = Exception("Test error")

            # Mag geen exception raisen
            await check_all_voted_celebration(channel, 1, 100)

    async def test_deletes_celebration_when_message_not_found(self):
        """Test dat celebration ID wordt gewist als bericht niet bestaat."""
        channel = MagicMock()
        channel.id = 100

        with patch("apps.utils.poll_message.load_votes") as mock_load:
            with patch("apps.utils.poll_message.get_non_voters_for_day") as mock_non_voters:
                with patch("apps.utils.poll_message.get_message_id") as mock_get_id:
                    with patch("apps.utils.poll_message.fetch_message_or_none") as mock_fetch:
                        with patch("apps.utils.poll_message.clear_message_id") as mock_clear:
                            mock_load.return_value = {}
                            mock_non_voters.return_value = (1, ["user_456"])
                            # Celebration bestaat
                            mock_get_id.return_value = 999
                            # Maar bericht is weg
                            mock_fetch.return_value = None

                            await check_all_voted_celebration(channel, 1, 100)

                            # ID moet gewist worden
                            mock_clear.assert_called_once_with(100, "celebration")


class TestRemoveCelebrationMessage(BaseTestCase):
    """Test remove_celebration_message functie."""

    async def test_removes_celebration_when_exists(self):
        """Test dat celebration wordt verwijderd wanneer die bestaat."""
        channel = MagicMock()

        # Mock message
        celebration_msg = MagicMock()
        celebration_msg.delete = AsyncMock()

        with patch("apps.utils.poll_message.get_message_id") as mock_get_id:
            with patch("apps.utils.poll_message.fetch_message_or_none") as mock_fetch:
                with patch("apps.utils.poll_message.clear_message_id") as mock_clear:
                    mock_get_id.return_value = 999
                    mock_fetch.return_value = celebration_msg

                    await remove_celebration_message(channel, 100)

                    # Verifieer dat bericht werd verwijderd
                    celebration_msg.delete.assert_called_once()
                    mock_clear.assert_called_once_with(100, "celebration")

    async def test_does_nothing_when_no_celebration(self):
        """Test dat er niets gebeurt als er geen celebration bestaat."""
        channel = MagicMock()

        with patch("apps.utils.poll_message.get_message_id") as mock_get_id:
            with patch("apps.utils.poll_message.fetch_message_or_none") as mock_fetch:
                mock_get_id.return_value = None

                await remove_celebration_message(channel, 100)

                # Geen fetch
                mock_fetch.assert_not_called()

    async def test_clears_id_when_message_not_found(self):
        """Test dat ID wordt gewist als bericht niet bestaat."""
        channel = MagicMock()

        with patch("apps.utils.poll_message.get_message_id") as mock_get_id:
            with patch("apps.utils.poll_message.fetch_message_or_none") as mock_fetch:
                with patch("apps.utils.poll_message.clear_message_id") as mock_clear:
                    mock_get_id.return_value = 999
                    mock_fetch.return_value = None

                    await remove_celebration_message(channel, 100)

                    # ID moet gewist worden
                    mock_clear.assert_called_once_with(100, "celebration")

    async def test_handles_exception_gracefully(self):
        """Test dat uitzonderingen netjes worden afgehandeld."""
        channel = MagicMock()

        with patch("apps.utils.poll_message.get_message_id") as mock_get_id:
            # Simuleer een exception
            mock_get_id.side_effect = Exception("Test error")

            # Mag geen exception raisen
            await remove_celebration_message(channel, 100)

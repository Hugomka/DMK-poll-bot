# tests/test_celebration.py
"""Tests voor celebration message functionaliteit."""

from unittest.mock import AsyncMock, MagicMock, patch

import discord

from apps.utils.poll_message import (
    LOCAL_CELEBRATION_IMAGE,
    check_all_voted_celebration,
    create_celebration_embed,
    remove_celebration_message,
)
from tests.base import BaseTestCase


class TestCreateCelebrationEmbed(BaseTestCase):
    """Test create_celebration_embed functie."""

    def test_creates_embed_with_correct_properties(self):
        """Test dat create_celebration_embed correct embed maakt (zonder GIF - die wordt apart gestuurd)."""
        embed = create_celebration_embed()

        # Verifieer embed properties
        self.assertIsInstance(embed, discord.Embed)
        self.assertIsNotNone(embed.title)
        self.assertTrue("🎉" in str(embed.title))
        self.assertTrue("Iedereen heeft gestemd" in str(embed.title))
        self.assertEqual(embed.color, discord.Color.gold())
        # Geen image - GIF wordt als los bericht gestuurd
        self.assertIsNone(embed.image.url)
        self.assertIsNotNone(embed.description)
        self.assertTrue("Bedankt voor jullie inzet" in str(embed.description))


class TestCheckAllVotedCelebration(BaseTestCase):
    """Test check_all_voted_celebration functie."""

    async def test_sends_celebration_when_all_voted(self):
        """Test dat celebration wordt gestuurd wanneer iedereen heeft gestemd."""
        # Mock channel
        channel = MagicMock()
        channel.id = 100
        channel.send = AsyncMock(return_value=MagicMock(id=999))

        test_tenor_url = "https://tenor.com/view/test-gif-12345"

        # Mock votes - iedereen heeft gestemd
        with patch("apps.utils.poll_message.get_non_voters_for_day") as mock_non_voters:
            with patch("apps.utils.poll_message.get_message_id") as mock_get_id:
                with patch("apps.utils.poll_message.save_message_id") as mock_save_id:
                    with patch("apps.utils.poll_message.get_celebration_gif_url") as mock_get_url:
                        # Geen niet-stemmers voor alle dagen
                        mock_non_voters.return_value = (0, [])
                        # Nog geen celebration message
                        mock_get_id.return_value = None
                        # Mock Tenor URL selector
                        mock_get_url.return_value = test_tenor_url

                        await check_all_voted_celebration(channel, 1, 100)

                        # Verifieer dat send 2x werd aangeroepen (embed + GIF URL)
                        self.assertEqual(channel.send.call_count, 2)

                        # Eerste call: embed met tekst
                        first_call_kwargs = channel.send.call_args_list[0][1]
                        self.assertIn("embed", first_call_kwargs)
                        embed = first_call_kwargs["embed"]
                        self.assertIsInstance(embed, discord.Embed)
                        self.assertIn("🎉", embed.title)
                        self.assertIn("Iedereen heeft gestemd", embed.title)
                        self.assertEqual(embed.color, discord.Color.gold())

                        # Tweede call: los bericht met GIF URL
                        second_call_kwargs = channel.send.call_args_list[1][1]
                        self.assertIn("content", second_call_kwargs)
                        self.assertEqual(second_call_kwargs["content"], test_tenor_url)

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

    async def test_sends_local_image_when_tenor_fails(self):
        """Test dat lokale afbeelding wordt gestuurd als Tenor URL faalt."""
        channel = MagicMock()
        channel.id = 100
        # Eerste send call: embed succesvol (return message)
        # Tweede send call: Tenor URL faalt (return None)
        # Derde send call: lokale afbeelding succesvol
        channel.send = AsyncMock(side_effect=[
            MagicMock(id=999),  # Embed succesvol
            None,  # Tenor URL faalt
            MagicMock(id=1000)  # Lokale afbeelding
        ])

        test_tenor_url = "https://tenor.com/view/test-gif-12345"

        # Mock discord.File directement om open() probleem te vermijden
        with patch("apps.utils.poll_message.get_non_voters_for_day") as mock_non_voters:
            with patch("apps.utils.poll_message.get_message_id") as mock_get_id:
                with patch("apps.utils.poll_message.save_message_id") as mock_save_id:
                    with patch("apps.utils.poll_message.get_celebration_gif_url") as mock_get_url:
                        with patch("apps.utils.poll_message.os.path.exists") as mock_exists:
                            with patch("apps.utils.poll_message.discord.File") as mock_file:
                                mock_non_voters.return_value = (0, [])
                                mock_get_id.return_value = None
                                mock_get_url.return_value = test_tenor_url
                                mock_exists.return_value = True
                                mock_file.return_value = MagicMock()

                                await check_all_voted_celebration(channel, 1, 100)

                                # Verifieer dat send 3x werd aangeroepen
                                self.assertEqual(channel.send.call_count, 3)

                                # Eerste call: embed
                                first_call = channel.send.call_args_list[0][1]
                                self.assertIn("embed", first_call)

                                # Tweede call: Tenor URL
                                second_call = channel.send.call_args_list[1][1]
                                self.assertEqual(second_call["content"], test_tenor_url)

                                # Derde call: lokale afbeelding
                                third_call = channel.send.call_args_list[2][1]
                                self.assertIn("file", third_call)
                                # Verifieer dat discord.File werd aangeroepen
                                mock_file.assert_called_once()

    async def test_does_not_send_local_image_when_tenor_succeeds(self):
        """Test dat lokale afbeelding NIET wordt gestuurd als Tenor URL werkt."""
        channel = MagicMock()
        channel.id = 100
        # Beide send calls succesvol
        channel.send = AsyncMock(side_effect=[
            MagicMock(id=999),  # Embed succesvol
            MagicMock(id=1000)  # Tenor URL succesvol
        ])

        test_tenor_url = "https://tenor.com/view/test-gif-12345"

        with patch("apps.utils.poll_message.get_non_voters_for_day") as mock_non_voters:
            with patch("apps.utils.poll_message.get_message_id") as mock_get_id:
                with patch("apps.utils.poll_message.save_message_id") as mock_save_id:
                    with patch("apps.utils.poll_message.get_celebration_gif_url") as mock_get_url:
                        mock_non_voters.return_value = (0, [])
                        mock_get_id.return_value = None
                        mock_get_url.return_value = test_tenor_url

                        await check_all_voted_celebration(channel, 1, 100)

                        # Verifieer dat send ALLEEN 2x werd aangeroepen (geen fallback)
                        self.assertEqual(channel.send.call_count, 2)

    async def test_does_not_send_local_image_when_file_not_exists(self):
        """Test dat lokale afbeelding NIET wordt gestuurd als bestand niet bestaat."""
        channel = MagicMock()
        channel.id = 100
        channel.send = AsyncMock(side_effect=[
            MagicMock(id=999),  # Embed succesvol
            None  # Tenor URL faalt
        ])

        test_tenor_url = "https://tenor.com/view/test-gif-12345"

        with patch("apps.utils.poll_message.get_non_voters_for_day") as mock_non_voters:
            with patch("apps.utils.poll_message.get_message_id") as mock_get_id:
                with patch("apps.utils.poll_message.save_message_id") as mock_save_id:
                    with patch("apps.utils.poll_message.get_celebration_gif_url") as mock_get_url:
                        with patch("apps.utils.poll_message.os.path.exists") as mock_exists:
                            mock_non_voters.return_value = (0, [])
                            mock_get_id.return_value = None
                            mock_get_url.return_value = test_tenor_url
                            mock_exists.return_value = False  # Bestand bestaat niet

                            await check_all_voted_celebration(channel, 1, 100)

                            # Verifieer dat send ALLEEN 2x werd aangeroepen (geen fallback)
                            self.assertEqual(channel.send.call_count, 2)


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

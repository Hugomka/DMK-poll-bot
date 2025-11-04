# tests/test_scheduler_helpers.py
"""Tests voor scheduler helper functies."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from apps import scheduler


class TestSchedulerHelpers(unittest.IsolatedAsyncioTestCase):
    """Test scheduler helper functies."""

    def test_is_deadline_mode_no_setting(self):
        """Test _is_deadline_mode zonder setting retourneert True."""
        with patch("apps.scheduler.get_setting", return_value=None):
            result = scheduler._is_deadline_mode(100, "vrijdag")
            self.assertTrue(result)

    def test_is_deadline_mode_non_dict_setting(self):
        """Test _is_deadline_mode met niet-dict setting retourneert True."""
        with patch("apps.scheduler.get_setting", return_value="invalid"):
            result = scheduler._is_deadline_mode(100, "vrijdag")
            self.assertTrue(result)

    def test_is_deadline_mode_explicit_deadline(self):
        """Test _is_deadline_mode met expliciete deadline modus."""
        with patch("apps.scheduler.get_setting", return_value={"modus": "deadline"}):
            result = scheduler._is_deadline_mode(100, "vrijdag")
            self.assertTrue(result)

    def test_is_deadline_mode_altijd(self):
        """Test _is_deadline_mode met altijd modus retourneert False."""
        with patch("apps.scheduler.get_setting", return_value={"modus": "altijd"}):
            result = scheduler._is_deadline_mode(100, "vrijdag")
            self.assertFalse(result)

    def test_get_deny_channel_names(self):
        """Test _get_deny_channel_names laadt env var correct."""
        with patch.dict(os.environ, {"DENY_CHANNEL_NAMES": "test,demo, spam "}, clear=False):
            result = scheduler._get_deny_channel_names()
            self.assertEqual(result, {"test", "demo", "spam"})

    def test_get_deny_channel_names_empty(self):
        """Test _get_deny_channel_names met lege env var."""
        with patch.dict(os.environ, {"DENY_CHANNEL_NAMES": ""}, clear=False):
            result = scheduler._get_deny_channel_names()
            self.assertEqual(result, set())

    def test_extract_owner_id_normal(self):
        """Test _extract_owner_id met normale user ID."""
        self.assertEqual(scheduler._extract_owner_id("12345"), "12345")
        self.assertEqual(scheduler._extract_owner_id(12345), "12345")

    def test_extract_owner_id_guest(self):
        """Test _extract_owner_id met guest vote."""
        self.assertEqual(scheduler._extract_owner_id("12345_guest::Jan"), "12345")
        self.assertEqual(scheduler._extract_owner_id("999_guest::Guest"), "999")

    async def test_load_channel_votes(self):
        """Test _load_channel_votes laadt stemmen correct."""
        guild = SimpleNamespace(id="100")
        channel = SimpleNamespace(id="200")

        with patch("apps.scheduler.load_votes", new_callable=AsyncMock) as mock_load:
            mock_load.return_value = {"user1": {"vrijdag": ["19:00"]}}
            result = await scheduler._load_channel_votes(guild, channel)

            mock_load.assert_awaited_once_with("100", "200")
            self.assertEqual(result, {"user1": {"vrijdag": ["19:00"]}})

    async def test_load_channel_votes_none(self):
        """Test _load_channel_votes met None retourneert lege dict."""
        guild = SimpleNamespace(id="100")
        channel = SimpleNamespace(id="200")

        with patch("apps.scheduler.load_votes", new_callable=AsyncMock) as mock_load:
            mock_load.return_value = None
            result = await scheduler._load_channel_votes(guild, channel)

            self.assertEqual(result, {})

    async def test_get_voted_ids_any_type(self):
        """Test _get_voted_ids met any vote type."""
        votes = {
            "100": {"vrijdag": ["19:00"], "zaterdag": []},
            "200": {"vrijdag": [], "zaterdag": ["20:30"]},
            "300": {"vrijdag": [], "zaterdag": []},  # Geen stemmen
        }

        result = await scheduler._get_voted_ids(votes)
        self.assertEqual(result, {100, 200})

    async def test_get_voted_ids_specific_dag(self):
        """Test _get_voted_ids voor specifieke dag."""
        votes = {
            "100": {"vrijdag": ["19:00"], "zaterdag": []},
            "200": {"vrijdag": [], "zaterdag": ["20:30"]},
        }

        result = await scheduler._get_voted_ids(votes, dag="vrijdag")
        self.assertEqual(result, {100})

        result = await scheduler._get_voted_ids(votes, dag="zaterdag")
        self.assertEqual(result, {200})

    async def test_get_voted_ids_misschien_type(self):
        """Test _get_voted_ids met misschien vote type."""
        votes = {
            "100": {"vrijdag": ["misschien"]},
            "200": {"vrijdag": ["19:00"]},
            "300": {"vrijdag": ["misschien", "19:00"]},
        }

        result = await scheduler._get_voted_ids(votes, dag="vrijdag", vote_type="misschien")
        self.assertEqual(result, {100, 300})

    async def test_get_voted_ids_with_guest(self):
        """Test _get_voted_ids met guest votes."""
        votes = {
            "100_guest::Jan": {"vrijdag": ["19:00"]},
            "200": {"zaterdag": ["20:30"]},
        }

        result = await scheduler._get_voted_ids(votes)
        self.assertEqual(result, {100, 200})

    async def test_get_voted_ids_invalid_data(self):
        """Test _get_voted_ids handelt ongeldige data af."""
        votes = {
            "invalid": {"vrijdag": ["19:00"]},  # Niet converteerbaar naar int
            "200": "not a dict",  # Geen dict
            "300": {"vrijdag": "not a list"},  # Geen lijst
        }

        result = await scheduler._get_voted_ids(votes)
        self.assertEqual(result, set())

    async def test_get_voted_ids_non_list_tijden(self):
        """Test _get_voted_ids met niet-lijst tijden."""
        votes = {
            "100": {"vrijdag": "not a list"},
            "200": {"vrijdag": None},
        }

        result = await scheduler._get_voted_ids(votes, dag="vrijdag")
        self.assertEqual(result, set())

    def test_get_non_voter_mentions(self):
        """Test _get_non_voter_mentions haalt non-voters op."""
        member1 = MagicMock()
        member1.id = 100
        member1.bot = False
        member1.mention = "<@100>"

        member2 = MagicMock()
        member2.id = 200
        member2.bot = False
        member2.mention = "<@200>"

        member3 = MagicMock()  # Bot
        member3.id = 300
        member3.bot = True
        member3.mention = "<@300>"

        channel = SimpleNamespace(members=[member1, member2, member3])
        voted_ids = {200}  # Member2 heeft gestemd

        result = scheduler._get_non_voter_mentions(channel, voted_ids)
        self.assertEqual(result, ["<@100>"])

    def test_get_non_voter_mentions_all_voted(self):
        """Test _get_non_voter_mentions als iedereen heeft gestemd."""
        member = MagicMock()
        member.id = 100
        member.bot = False
        member.mention = "<@100>"

        channel = SimpleNamespace(members=[member])
        voted_ids = {100}

        result = scheduler._get_non_voter_mentions(channel, voted_ids)
        self.assertEqual(result, [])

    def test_get_non_voter_mentions_no_id(self):
        """Test _get_non_voter_mentions met member zonder ID."""
        member = MagicMock()
        member.id = None
        member.bot = False

        channel = SimpleNamespace(members=[member])
        voted_ids = set()

        result = scheduler._get_non_voter_mentions(channel, voted_ids)
        self.assertEqual(result, [])

    async def test_delete_poll_message_no_message_id(self):
        """Test _delete_poll_message zonder message ID."""
        channel = MagicMock()

        with patch("apps.scheduler.get_message_id", return_value=None):
            await scheduler._delete_poll_message(channel, 100, "vrijdag")
            # Geen verdere calls verwacht

    async def test_update_or_create_message_no_send(self):
        """Test _update_or_create_message zonder send methode."""
        channel = MagicMock()
        del channel.send

        result = await scheduler._update_or_create_message(
            channel, 100, "test", "content"
        )
        self.assertIsNone(result)

    async def test_update_or_create_message_create_new(self):
        """Test _update_or_create_message maakt nieuw bericht."""
        channel = MagicMock()
        new_msg = MagicMock()
        new_msg.id = 999

        with (
            patch("apps.scheduler.get_message_id", return_value=None),
            patch("apps.scheduler.safe_call", new_callable=AsyncMock) as mock_safe_call,
            patch("apps.scheduler.save_message_id") as mock_save,
        ):
            mock_safe_call.return_value = new_msg

            result = await scheduler._update_or_create_message(
                channel, 100, "test", "content"
            )

            self.assertEqual(result, new_msg)
            mock_save.assert_called_once_with(100, "test", 999)

    async def test_update_or_create_message_update_existing(self):
        """Test _update_or_create_message update bestaand bericht."""
        channel = MagicMock()
        existing_msg = MagicMock()

        with (
            patch("apps.scheduler.get_message_id", return_value=123),
            patch(
                "apps.scheduler.fetch_message_or_none",
                new_callable=AsyncMock,
                return_value=existing_msg,
            ),
            patch("apps.scheduler.safe_call", new_callable=AsyncMock) as mock_safe_call,
        ):
            result = await scheduler._update_or_create_message(
                channel, 100, "test", "updated content"
            )

            self.assertEqual(result, existing_msg)
            mock_safe_call.assert_awaited_once()

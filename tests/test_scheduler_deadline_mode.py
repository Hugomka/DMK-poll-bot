# tests/test_scheduler_deadline_mode.py
#
# Unit tests voor deadline-modus filtering in scheduler notificaties

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from apps import scheduler
from tests.base import BaseTestCase


class TestSchedulerDeadlineMode(BaseTestCase):
    """Tests voor deadline-modus filtering in scheduler functies."""

    async def test_notify_non_voters_thursday_skips_altijd_mode(self):
        """Test dat notify_non_voters_thursday overgeslagen wordt voor 'altijd' modus kanalen."""

        bot = SimpleNamespace(guilds=[])
        guild = SimpleNamespace(id=1)
        channel = SimpleNamespace(
            id=10,
            name="dmk-poll",
            guild=guild,
            members=[
                SimpleNamespace(id=100, bot=False, mention="<@100>"),
            ],
        )
        bot.guilds = [guild]

        # User 100 heeft niet gestemd
        votes = {}

        def fake_get_channels(g):
            return [channel] if g == guild else []

        def fake_get_setting(cid, dag):
            # Retourneer 'altijd' modus voor alle dagen
            return {"modus": "altijd", "tijd": "18:00"}

        with (
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "is_paused", return_value=False),
            patch.object(scheduler, "get_message_id", return_value=999),
            patch.object(scheduler, "load_votes", new_callable=AsyncMock, return_value=votes),
            patch.object(scheduler, "get_setting", side_effect=fake_get_setting),
            patch.object(
                scheduler, "send_temporary_mention", new_callable=AsyncMock
            ) as mock_mention,
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            await scheduler.notify_non_voters_thursday(bot)

        # Assert: send_temporary_mention NIET aangeroepen (altijd modus)
        mock_mention.assert_not_awaited()

    async def test_notify_non_voters_thursday_runs_for_deadline_mode(self):
        """Test dat notify_non_voters_thursday WEL draait voor 'deadline' modus kanalen."""

        bot = SimpleNamespace(guilds=[])
        guild = SimpleNamespace(id=1)
        channel = SimpleNamespace(
            id=10,
            name="dmk-poll",
            guild=guild,
            members=[
                SimpleNamespace(id=100, bot=False, mention="<@100>"),
            ],
        )
        bot.guilds = [guild]

        # User 100 heeft niet gestemd
        votes = {}

        def fake_get_channels(g):
            return [channel] if g == guild else []

        def fake_get_setting(cid, dag):
            # Retourneer 'deadline' modus
            return {"modus": "deadline", "tijd": "18:00"}

        with (
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "is_paused", return_value=False),
            patch.object(scheduler, "get_message_id", return_value=999),
            patch.object(scheduler, "load_votes", new_callable=AsyncMock, return_value=votes),
            patch.object(scheduler, "get_setting", side_effect=fake_get_setting),
            patch.object(
                scheduler, "send_temporary_mention", new_callable=AsyncMock
            ) as mock_mention,
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            await scheduler.notify_non_voters_thursday(bot)

        # Assert: send_temporary_mention WEL aangeroepen (deadline modus)
        mock_mention.assert_awaited_once()

    async def test_notify_non_voters_skips_altijd_mode(self):
        """Test dat notify_non_voters (16:00) overgeslagen wordt voor 'altijd' modus kanalen."""

        bot = SimpleNamespace(guilds=[])
        guild = SimpleNamespace(id=1)
        channel = SimpleNamespace(
            id=10,
            name="dmk-poll",
            guild=guild,
            members=[
                SimpleNamespace(id=100, bot=False, mention="<@100>"),
            ],
        )
        bot.guilds = [guild]

        # User 100 heeft niet gestemd voor vrijdag
        votes = {}

        def fake_get_channels(g):
            return [channel] if g == guild else []

        def fake_get_setting(cid, dag):
            # Retourneer 'altijd' modus
            return {"modus": "altijd", "tijd": "18:00"}

        with (
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "is_paused", return_value=False),
            patch.object(scheduler, "get_message_id", return_value=999),
            patch.object(scheduler, "load_votes", new_callable=AsyncMock, return_value=votes),
            patch.object(scheduler, "get_setting", side_effect=fake_get_setting),
            patch.object(
                scheduler, "calculate_leading_time", new_callable=AsyncMock, return_value="19:00"
            ),
            patch.object(
                scheduler, "send_temporary_mention", new_callable=AsyncMock
            ) as mock_mention,
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            # Scheduler-modus: geen channel parameter
            result = await scheduler.notify_non_voters(bot, dag="vrijdag")

        # Assert: send_temporary_mention NIET aangeroepen (altijd modus)
        mock_mention.assert_not_awaited()
        self.assertFalse(result)

    async def test_notify_non_voters_runs_for_deadline_mode(self):
        """Test dat notify_non_voters (16:00) WEL draait voor 'deadline' modus kanalen."""

        bot = SimpleNamespace(guilds=[])
        guild = SimpleNamespace(id=1)
        channel = SimpleNamespace(
            id=10,
            name="dmk-poll",
            guild=guild,
            members=[
                SimpleNamespace(id=100, bot=False, mention="<@100>"),
            ],
        )
        bot.guilds = [guild]

        # User 100 heeft niet gestemd voor vrijdag
        votes = {}

        def fake_get_channels(g):
            return [channel] if g == guild else []

        def fake_get_setting(cid, dag):
            # Retourneer 'deadline' modus
            return {"modus": "deadline", "tijd": "18:00"}

        with (
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "is_paused", return_value=False),
            patch.object(scheduler, "get_message_id", return_value=999),
            patch.object(scheduler, "load_votes", new_callable=AsyncMock, return_value=votes),
            patch.object(scheduler, "get_setting", side_effect=fake_get_setting),
            patch.object(
                scheduler, "calculate_leading_time", new_callable=AsyncMock, return_value="19:00"
            ),
            patch.object(
                scheduler, "send_temporary_mention", new_callable=AsyncMock
            ) as mock_mention,
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            # Scheduler-modus: geen channel parameter
            result = await scheduler.notify_non_voters(bot, dag="vrijdag")

        # Assert: send_temporary_mention WEL aangeroepen (deadline modus)
        mock_mention.assert_awaited_once()
        self.assertTrue(result)

    async def test_notify_misschien_voters_skips_altijd_mode(self):
        """Test dat notify_misschien_voters overgeslagen wordt voor 'altijd' modus kanalen."""

        bot = SimpleNamespace(guilds=[])
        guild = SimpleNamespace(id=1)
        channel = SimpleNamespace(
            id=10,
            name="dmk-poll",
            guild=guild,
            members=[
                SimpleNamespace(id=100, bot=False, mention="<@100>"),
            ],
        )
        bot.guilds = [guild]

        # User 100 heeft "misschien" gestemd
        votes = {
            "100": {"vrijdag": ["misschien"]},
        }

        def fake_get_channels(g):
            return [channel] if g == guild else []

        def fake_get_setting(cid, dag):
            # Retourneer 'altijd' modus
            return {"modus": "altijd", "tijd": "18:00"}

        with (
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "is_paused", return_value=False),
            patch.object(scheduler, "get_message_id", return_value=999),
            patch.object(scheduler, "load_votes", new_callable=AsyncMock, return_value=votes),
            patch.object(scheduler, "get_setting", side_effect=fake_get_setting),
            patch.object(
                scheduler, "calculate_leading_time", new_callable=AsyncMock, return_value="19:00"
            ),
            patch.object(
                scheduler, "send_temporary_mention", new_callable=AsyncMock
            ) as mock_mention,
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            await scheduler.notify_misschien_voters(bot, "vrijdag")

        # Assert: send_temporary_mention NIET aangeroepen (altijd modus)
        mock_mention.assert_not_awaited()

    async def test_notify_misschien_voters_runs_for_deadline_mode(self):
        """Test dat notify_misschien_voters WEL draait voor 'deadline' modus kanalen."""

        bot = SimpleNamespace(guilds=[])
        guild = SimpleNamespace(id=1)
        channel = SimpleNamespace(
            id=10,
            name="dmk-poll",
            guild=guild,
            members=[
                SimpleNamespace(id=100, bot=False, mention="<@100>"),
            ],
        )
        bot.guilds = [guild]

        # User 100 heeft "misschien" gestemd
        votes = {
            "100": {"vrijdag": ["misschien"]},
        }

        def fake_get_channels(g):
            return [channel] if g == guild else []

        def fake_get_setting(cid, dag):
            # Retourneer 'deadline' modus
            return {"modus": "deadline", "tijd": "18:00"}

        with (
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "is_paused", return_value=False),
            patch.object(scheduler, "get_message_id", return_value=999),
            patch.object(scheduler, "load_votes", new_callable=AsyncMock, return_value=votes),
            patch.object(scheduler, "get_setting", side_effect=fake_get_setting),
            patch.object(
                scheduler, "calculate_leading_time", new_callable=AsyncMock, return_value="19:00"
            ),
            patch.object(
                scheduler, "send_temporary_mention", new_callable=AsyncMock
            ) as mock_mention,
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            await scheduler.notify_misschien_voters(bot, "vrijdag")

        # Assert: send_temporary_mention WEL aangeroepen (deadline modus)
        mock_mention.assert_awaited_once()

    async def test_convert_remaining_misschien_skips_altijd_mode(self):
        """Test dat convert_remaining_misschien overgeslagen wordt voor 'altijd' modus kanalen."""

        bot = SimpleNamespace(guilds=[])
        guild = SimpleNamespace(id=1)
        channel = SimpleNamespace(
            id=10,
            name="dmk-poll",
            guild=guild,
        )
        bot.guilds = [guild]

        # User 100 heeft "misschien" gestemd
        votes = {
            "100": {"vrijdag": ["misschien"]},
        }

        def fake_get_channels(g):
            return [channel] if g == guild else []

        def fake_get_setting(cid, dag):
            # Retourneer 'altijd' modus
            return {"modus": "altijd", "tijd": "18:00"}

        with (
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "is_paused", return_value=False),
            patch.object(scheduler, "get_message_id", return_value=999),
            patch.object(scheduler, "load_votes", new_callable=AsyncMock, return_value=votes),
            patch.object(scheduler, "get_setting", side_effect=fake_get_setting),
            patch("apps.utils.poll_storage.remove_vote", new_callable=AsyncMock) as mock_remove,
            patch("apps.utils.poll_storage.add_vote", new_callable=AsyncMock) as mock_add,
            patch.object(scheduler, "schedule_poll_update", return_value=None),
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            await scheduler.convert_remaining_misschien(bot, "vrijdag")

        # Assert: remove_vote en add_vote NIET aangeroepen (altijd modus)
        mock_remove.assert_not_awaited()
        mock_add.assert_not_awaited()

    async def test_convert_remaining_misschien_runs_for_deadline_mode(self):
        """Test dat convert_remaining_misschien WEL draaa it voor 'deadline' modus kanalen."""

        bot = SimpleNamespace(guilds=[])
        guild = SimpleNamespace(id=1)
        channel = SimpleNamespace(
            id=10,
            name="dmk-poll",
        )
        bot.guilds = [guild]

        # User 100 heeft "misschien" gestemd
        votes = {
            "100": {"vrijdag": ["misschien"]},
        }

        def fake_get_channels(g):
            return [channel] if g == guild else []

        def fake_get_setting(cid, dag):
            # Retourneer 'deadline' modus
            return {"modus": "deadline", "tijd": "18:00"}

        with (
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "is_paused", return_value=False),
            patch.object(scheduler, "get_message_id", return_value=999),
            patch.object(scheduler, "load_votes", new_callable=AsyncMock, return_value=votes),
            patch.object(scheduler, "get_setting", side_effect=fake_get_setting),
            patch("apps.utils.poll_storage.remove_vote", new_callable=AsyncMock) as mock_remove,
            patch("apps.utils.poll_storage.add_vote", new_callable=AsyncMock) as mock_add,
            patch.object(scheduler, "schedule_poll_update", return_value=None),
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            await scheduler.convert_remaining_misschien(bot, "vrijdag")

        # Assert: remove_vote en add_vote WEL aangeroepen (deadline modus)
        mock_remove.assert_awaited_once()
        mock_add.assert_awaited_once()

        # Verify correct parameters
        remove_args = mock_remove.call_args[0]
        add_args = mock_add.call_args[0]
        self.assertEqual(remove_args[0], "100")  # uid
        self.assertEqual(remove_args[1], "vrijdag")  # dag
        self.assertEqual(remove_args[2], "misschien")  # tijd
        self.assertEqual(add_args[0], "100")  # uid
        self.assertEqual(add_args[1], "vrijdag")  # dag
        self.assertEqual(add_args[2], "niet meedoen")  # tijd

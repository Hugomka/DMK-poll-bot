# tests/test_scheduler_update_all_polls.py

import os
import unittest
from unittest.mock import AsyncMock, patch

from apps import scheduler


class UpdateAllPollsTestCase(unittest.IsolatedAsyncioTestCase):
    """Tests voor update_all_polls functie."""

    async def test_update_all_polls_skips_disabled_channel(self):
        """Test dat uitgeschakelde kanalen worden geskipt."""

        class Channel:
            def __init__(self, id):
                self.id = id
                self.name = "dmk"

        class Guild:
            def __init__(self):
                self.id = 1

            @property
            def text_channels(self):
                return [Channel(10)]

        class Bot:
            def __init__(self):
                self.guilds = [Guild()]

        bot = Bot()

        def fake_get_channels(guild):
            return guild.text_channels

        with (
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(
                scheduler, "is_channel_disabled", return_value=True
            ),  # Kanaal disabled
            patch.object(
                scheduler, "schedule_poll_update", new_callable=AsyncMock
            ) as mock_schedule,
        ):
            await scheduler.update_all_polls(bot)

        # Assert: schedule_poll_update NIET aangeroepen
        mock_schedule.assert_not_awaited()

    async def test_update_all_polls_skips_deny_channel_names(self):
        """Test dat kanalen in DENY_CHANNEL_NAMES worden geskipt."""

        class Channel:
            def __init__(self, id, name):
                self.id = id
                self.name = name

        class Guild:
            def __init__(self):
                self.id = 1

            @property
            def text_channels(self):
                return [Channel(10, "dmk")]

        class Bot:
            def __init__(self):
                self.guilds = [Guild()]

        bot = Bot()

        def fake_get_channels(guild):
            return guild.text_channels

        with (
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(
                scheduler, "schedule_poll_update", new_callable=AsyncMock
            ) as mock_schedule,
            patch.dict(os.environ, {"DENY_CHANNEL_NAMES": "dmk"}, clear=False),
        ):
            await scheduler.update_all_polls(bot)

        # Assert: schedule_poll_update NIET aangeroepen
        mock_schedule.assert_not_awaited()

    async def test_update_all_polls_skips_when_allow_per_channel_and_no_poll(self):
        """Test dat kanalen zonder poll worden geskipt als ALLOW_FROM_PER_CHANNEL_ONLY=true."""

        class Channel:
            def __init__(self, id):
                self.id = id
                self.name = "dmk"

        class Guild:
            def __init__(self):
                self.id = 1

            @property
            def text_channels(self):
                return [Channel(10)]

        class Bot:
            def __init__(self):
                self.guilds = [Guild()]

        bot = Bot()

        def fake_get_channels(guild):
            return guild.text_channels

        def fake_get_message_id(cid, key):
            return None  # Geen polls

        with (
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "get_message_id", side_effect=fake_get_message_id),
            patch.object(
                scheduler, "schedule_poll_update", new_callable=AsyncMock
            ) as mock_schedule,
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            await scheduler.update_all_polls(bot)

        # Assert: schedule_poll_update NIET aangeroepen
        mock_schedule.assert_not_awaited()

    async def test_update_all_polls_schedules_updates_when_poll_exists(self):
        """Test dat updates worden gepland als er polls zijn."""

        class Channel:
            def __init__(self, id):
                self.id = id
                self.name = "dmk"

        class Guild:
            def __init__(self):
                self.id = 1

            @property
            def text_channels(self):
                return [Channel(10)]

        class Bot:
            def __init__(self):
                self.guilds = [Guild()]

        bot = Bot()

        def fake_get_channels(guild):
            return guild.text_channels

        def fake_get_message_id(cid, key):
            return 999  # Polls bestaan

        # Mock asyncio.gather
        gather_calls = []

        async def fake_gather(*tasks, **kwargs):
            # Await alle tasks zodat coroutines niet unawaited blijven
            for task in tasks:
                if hasattr(task, '__await__'):
                    try:
                        await task
                    except Exception:
                        pass
            gather_calls.append(len(tasks))
            return [None] * len(tasks)

        with (
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "get_message_id", side_effect=fake_get_message_id),
            patch.object(
                scheduler, "schedule_poll_update", new_callable=AsyncMock
            ) as mock_schedule,
            patch("asyncio.gather", side_effect=fake_gather),
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            await scheduler.update_all_polls(bot)

        # Assert: schedule_poll_update aangeroepen voor weekend dagen (default enabled)
        self.assertEqual(mock_schedule.call_count, 3)
        # Assert: gather is aangeroepen met 3 tasks
        self.assertEqual(len(gather_calls), 1)
        self.assertEqual(gather_calls[0], 3)

    async def test_update_all_polls_schedules_when_allow_false(self):
        """Test dat updates worden gepland als ALLOW_FROM_PER_CHANNEL_ONLY=false."""

        class Channel:
            def __init__(self, id):
                self.id = id
                self.name = "dmk"

        class Guild:
            def __init__(self):
                self.id = 1

            @property
            def text_channels(self):
                return [Channel(10)]

        class Bot:
            def __init__(self):
                self.guilds = [Guild()]

        bot = Bot()

        def fake_get_channels(guild):
            return guild.text_channels

        def fake_get_message_id(_cid, _key):
            return None  # Geen polls, maar ALLOW=false dus toch updates

        # Mock asyncio.gather
        gather_calls = []

        async def fake_gather(*tasks, **_kwargs):
            # Await alle tasks zodat coroutines niet unawaited blijven
            for task in tasks:
                if hasattr(task, '__await__'):
                    try:
                        await task
                    except Exception:
                        pass
            gather_calls.append(len(tasks))
            return [None] * len(tasks)

        with (
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "get_message_id", side_effect=fake_get_message_id),
            patch.object(
                scheduler, "schedule_poll_update", new_callable=AsyncMock
            ) as mock_schedule,
            patch("asyncio.gather", side_effect=fake_gather),
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "false"}, clear=False
            ),
        ):
            await scheduler.update_all_polls(bot)

        # Assert: schedule_poll_update aangeroepen voor weekend dagen (default enabled)
        self.assertEqual(mock_schedule.call_count, 3)
        # Assert: gather is aangeroepen met 3 tasks
        self.assertEqual(len(gather_calls), 1)
        self.assertEqual(gather_calls[0], 3)

    async def test_update_all_polls_handles_exception_in_get_message_id(self):
        """Test dat exceptions in get_message_id worden afgehandeld."""

        class Channel:
            def __init__(self, id):
                self.id = id
                self.name = "dmk"

        class Guild:
            def __init__(self):
                self.id = 1

            @property
            def text_channels(self):
                return [Channel(10)]

        class Bot:
            def __init__(self):
                self.guilds = [Guild()]

        bot = Bot()

        def fake_get_channels(guild):
            return guild.text_channels

        def fake_get_message_id(cid, key):
            raise RuntimeError("boom")

        with (
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "get_message_id", side_effect=fake_get_message_id),
            patch.object(
                scheduler, "schedule_poll_update", new_callable=AsyncMock
            ) as mock_schedule,
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            await scheduler.update_all_polls(bot)

        # Assert: schedule_poll_update NIET aangeroepen (exception → has_poll=False)
        mock_schedule.assert_not_awaited()

    async def test_update_all_polls_respects_enabled_days_setting(self):
        """Test dat alleen enabled dagen worden ge-update."""

        class Channel:
            def __init__(self, id):
                self.id = id
                self.name = "dmk"

        class Guild:
            def __init__(self):
                self.id = 1

            @property
            def text_channels(self):
                return [Channel(10)]

        class Bot:
            def __init__(self):
                self.guilds = [Guild()]

        bot = Bot()

        def fake_get_channels(guild):
            return guild.text_channels

        def fake_get_message_id(cid, key):
            return 999  # Polls bestaan

        def fake_get_enabled_period_days(_cid, reference_date):
            # Alleen zondag is enabled (andere dagen zijn disabled)
            return [{"dag": "zondag", "datum_iso": "2025-12-07"}]

        # Mock asyncio.gather
        gather_calls = []

        async def fake_gather(*tasks, **_kwargs):
            # Await alle tasks zodat coroutines niet unawaited blijven
            for task in tasks:
                if hasattr(task, '__await__'):
                    try:
                        await task
                    except Exception:
                        pass
            gather_calls.append(len(tasks))
            return [None] * len(tasks)

        # Mock fetch_message_or_none and safe_call for cleanup logic
        async def fake_fetch_message(_channel, _mid):
            return None  # No old message to clean up

        async def fake_safe_call(*_args, **_kwargs):
            pass

        with (
            patch.object(scheduler, "get_channels", side_effect=fake_get_channels),
            patch.object(scheduler, "is_channel_disabled", return_value=False),
            patch.object(scheduler, "get_message_id", side_effect=fake_get_message_id),
            patch("apps.scheduler.get_enabled_period_days", side_effect=fake_get_enabled_period_days),
            patch("apps.utils.discord_client.fetch_message_or_none", side_effect=fake_fetch_message),
            patch("apps.utils.discord_client.safe_call", side_effect=fake_safe_call),
            patch.object(
                scheduler, "schedule_poll_update", new_callable=AsyncMock
            ) as mock_schedule,
            patch("asyncio.gather", side_effect=fake_gather),
            patch.dict(
                os.environ, {"ALLOW_FROM_PER_CHANNEL_ONLY": "true"}, clear=False
            ),
        ):
            await scheduler.update_all_polls(bot)

        # Assert: schedule_poll_update aangeroepen voor alleen zondag (1x, niet 3x)
        self.assertEqual(mock_schedule.call_count, 1)
        # Verifieer dat het zondag was
        call_args = mock_schedule.call_args_list[0]
        self.assertEqual(call_args[0][1], "zondag")  # Tweede argument is dag
        # Assert: gather is aangeroepen met 1 task (alleen zondag)
        self.assertEqual(len(gather_calls), 1)
        self.assertEqual(gather_calls[0], 1)


if __name__ == "__main__":
    unittest.main()

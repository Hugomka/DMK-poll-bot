# tests/test_scheduler_setup.py

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from apps import scheduler


class SchedulerSetupTestCase(unittest.IsolatedAsyncioTestCase):
    """Tests voor scheduler setup."""

    async def test_setup_scheduler_registers_all_jobs(self):
        """Test dat setup_scheduler alle jobs registreert."""

        class Bot:
            guilds = []

        bot = Bot()

        # Track add_job calls
        added_jobs = []

        def fake_add_job(func, trigger, args=None, name=None, **kwargs):
            added_jobs.append(
                {
                    "func": func,
                    "trigger": trigger,
                    "args": args,
                    "name": name,
                }
            )

        # Track create_task calls
        created_tasks = []

        def fake_create_task(coro):
            # Sluit de coroutine om unawaited warning te voorkomen
            if hasattr(coro, "close"):
                coro.close()
            created_tasks.append(coro)
            # Return een mock Task object
            task = MagicMock()
            return task

        with (
            patch.object(scheduler.scheduler, "add_job", side_effect=fake_add_job),
            patch.object(scheduler.scheduler, "start") as mock_start,
            patch("asyncio.create_task", side_effect=fake_create_task),
            patch.object(scheduler, "_run_catch_up_with_lock", new_callable=AsyncMock),
        ):
            scheduler.setup_scheduler(bot)

        # Dynamisch op basis van REMINDER_DAYS (standaard: vr/za/zo = 3 dagen)
        # Per dag: herinnering + notificatie + convert misschien = 3 jobs
        # Vaste jobs: dagelijkse update + wekelijkse reset + tenor sync +
        #   vroege herinnering + activation + deactivation + retry = 7
        num_days = len(scheduler.REMINDER_DAYS)
        expected_jobs = num_days * 3 + 7
        self.assertEqual(len(added_jobs), expected_jobs)

        # Controleer dat juiste functies zijn geregistreerd
        job_funcs = [j["func"] for j in added_jobs]
        self.assertIn(scheduler.update_all_polls, job_funcs)
        self.assertIn(scheduler.reset_polls, job_funcs)
        self.assertIn(scheduler.notify_non_or_maybe_voters, job_funcs)
        self.assertIn(scheduler.notify_voters_if_avond_gaat_door, job_funcs)
        self.assertIn(scheduler.notify_non_voters_thursday, job_funcs)
        self.assertIn(scheduler.convert_remaining_misschien, job_funcs)
        self.assertIn(scheduler.activate_scheduled_polls, job_funcs)
        self.assertIn(scheduler.deactivate_scheduled_polls, job_funcs)
        self.assertIn(scheduler.sync_tenor_links_weekly, job_funcs)

        # Controleer notify_non_or_maybe_voters per geconfigureerde dag
        notify_non_voters_jobs = [
            j for j in added_jobs if j["func"] == scheduler.notify_non_or_maybe_voters
        ]
        self.assertEqual(len(notify_non_voters_jobs), num_days)

        # Controleer notify_voters_if_avond_gaat_door per geconfigureerde dag
        notify_voters_jobs = [
            j
            for j in added_jobs
            if j["func"] == scheduler.notify_voters_if_avond_gaat_door
        ]
        self.assertEqual(len(notify_voters_jobs), num_days)

        # Controleer dat de juiste dagen zijn meegegeven
        notify_non_voters_args = [j["args"] for j in notify_non_voters_jobs]
        for dag in scheduler.REMINDER_DAYS:
            self.assertIn([bot, dag], notify_non_voters_args)

        notify_voters_args = [j["args"] for j in notify_voters_jobs]
        for dag in scheduler.REMINDER_DAYS:
            self.assertIn([bot, dag], notify_voters_args)

        # Controleer update_all_polls (1x)
        update_jobs = [j for j in added_jobs if j["func"] == scheduler.update_all_polls]
        self.assertEqual(len(update_jobs), 1)
        self.assertEqual(update_jobs[0]["args"], [bot])

        # Controleer reset_polls (1x)
        reset_jobs = [j for j in added_jobs if j["func"] == scheduler.reset_polls]
        self.assertEqual(len(reset_jobs), 1)
        self.assertEqual(reset_jobs[0]["args"], [bot])

        # Controleer notify_non_voters_thursday (1x)
        thursday_jobs = [
            j for j in added_jobs if j["func"] == scheduler.notify_non_voters_thursday
        ]
        self.assertEqual(len(thursday_jobs), 1)
        self.assertEqual(thursday_jobs[0]["args"], [bot])

        # Controleer activate_scheduled_polls (1x, elke minuut)
        activation_jobs = [
            j for j in added_jobs if j["func"] == scheduler.activate_scheduled_polls
        ]
        self.assertEqual(len(activation_jobs), 1)
        self.assertEqual(activation_jobs[0]["args"], [bot])

        # Assert: scheduler.start is aangeroepen
        mock_start.assert_called_once()

        # Assert: asyncio.create_task is aangeroepen
        self.assertEqual(len(created_tasks), 1)


if __name__ == "__main__":
    unittest.main()

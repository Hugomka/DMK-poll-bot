# tests\test_reset_en_archief.py

import os
from apps.utils.poll_storage import toggle_vote, get_votes_for_option, reset_votes
from apps.utils.archive import append_week_snapshot, delete_archive, archive_exists
from datetime import datetime
from zoneinfo import ZoneInfo
from tests.base import BaseTestCase

class TestResetEnArchief(BaseTestCase):

    async def asyncSetUp(self):
        await super().asyncSetUp()
        await reset_votes()
        delete_archive()

    async def test_reset_zet_stemmen_op_nul(self):
        user = "999"
        await toggle_vote(user, "vrijdag", "om 19:00 uur")
        await reset_votes()
        aantal = await get_votes_for_option("vrijdag", "om 19:00 uur")
        self.assertEqual(aantal, 0)

    async def test_append_week_snapshot_maakt_csv(self):
        await toggle_vote("abc", "vrijdag", "om 19:00 uur")
        await append_week_snapshot(datetime.now(ZoneInfo("Europe/Amsterdam")))
        self.assertTrue(archive_exists())
        self.assertTrue(os.path.exists("archive/dmk_archive.csv"))

    async def test_append_leeg_snapshot(self):
        await append_week_snapshot(datetime.now(ZoneInfo("Europe/Amsterdam")))
        self.assertTrue(archive_exists())

    async def test_delete_archive_verwijdert_file(self):
        await append_week_snapshot(datetime.now(ZoneInfo("Europe/Amsterdam")))
        delete_archive()
        self.assertFalse(os.path.exists("archive/dmk_archive.csv"))


# tests/test_toggle_vote.py

import os

from apps.utils.poll_storage import get_user_votes, toggle_vote
from tests.base import BaseTestCase


class TestToggleVote(BaseTestCase):

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.user = "user123"

    async def asyncTearDown(self):
        if os.path.exists("votes_test.json"):
            os.remove("votes_test.json")

    async def test_aanvinken_van_tijd(self):
        await toggle_vote(self.user, "vrijdag", "om 19:00 uur", 1, 123)
        votes = await get_user_votes(self.user, 1, 123)
        self.assertEqual(votes["vrijdag"], ["om 19:00 uur"])

    async def test_tijd_toggle_uit(self):
        await toggle_vote(self.user, "vrijdag", "om 19:00 uur", 1, 123)
        await toggle_vote(self.user, "vrijdag", "om 19:00 uur", 1, 123)
        votes = await get_user_votes(self.user, 1, 123)
        self.assertEqual(votes["vrijdag"], [])

    async def test_tijd_wisselt_met_andere_tijd(self):
        await toggle_vote(self.user, "vrijdag", "om 19:00 uur", 1, 123)
        await toggle_vote(self.user, "vrijdag", "om 20:30 uur", 1, 123)
        votes = await get_user_votes(self.user, 1, 123)
        self.assertCountEqual(votes["vrijdag"], ["om 19:00 uur", "om 20:30 uur"])

    async def test_specials_vervangen_tijden(self):
        await toggle_vote(self.user, "vrijdag", "om 19:00 uur", 1, 123)
        await toggle_vote(self.user, "vrijdag", "misschien", 1, 123)
        votes = await get_user_votes(self.user, 1, 123)
        self.assertEqual(votes["vrijdag"], ["misschien"])

    async def test_specials_toggle_uit(self):
        await toggle_vote(self.user, "vrijdag", "misschien", 1, 123)
        await toggle_vote(self.user, "vrijdag", "misschien", 1, 123)
        votes = await get_user_votes(self.user, 1, 123)
        self.assertEqual(votes["vrijdag"], [])

    async def test_specials_zijn_exclusief(self):
        await toggle_vote(self.user, "vrijdag", "niet meedoen", 1, 123)
        await toggle_vote(self.user, "vrijdag", "misschien", 1, 123)
        votes = await get_user_votes(self.user, 1, 123)
        self.assertEqual(votes["vrijdag"], ["misschien"])

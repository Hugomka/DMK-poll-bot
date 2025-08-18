# tests\test_toggle_vote.py

import unittest
from apps.utils.poll_storage import toggle_vote, get_user_votes, reset_votes

class TestToggleVote(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        await reset_votes()
        self.user = "user123"

    async def test_aanvinken_van_tijd(self):
        await toggle_vote(self.user, "vrijdag", "om 19:00 uur")
        votes = await get_user_votes(self.user)
        self.assertEqual(votes["vrijdag"], ["om 19:00 uur"])

    async def test_tijd_toggle_uit(self):
        await toggle_vote(self.user, "vrijdag", "om 19:00 uur")
        await toggle_vote(self.user, "vrijdag", "om 19:00 uur")
        votes = await get_user_votes(self.user)
        self.assertEqual(votes["vrijdag"], [])

    async def test_tijd_wisselt_met_andere_tijd(self):
        await toggle_vote(self.user, "vrijdag", "om 19:00 uur")
        await toggle_vote(self.user, "vrijdag", "om 20:30 uur")
        votes = await get_user_votes(self.user)
        self.assertCountEqual(votes["vrijdag"], ["om 19:00 uur", "om 20:30 uur"])

    async def test_specials_vervangen_tijden(self):
        await toggle_vote(self.user, "vrijdag", "om 19:00 uur")
        await toggle_vote(self.user, "vrijdag", "misschien")
        votes = await get_user_votes(self.user)
        self.assertEqual(votes["vrijdag"], ["misschien"])

    async def test_specials_toggle_uit(self):
        await toggle_vote(self.user, "vrijdag", "misschien")
        await toggle_vote(self.user, "vrijdag", "misschien")
        votes = await get_user_votes(self.user)
        self.assertEqual(votes["vrijdag"], [])

    async def test_specials_zijn_exclusief(self):
        await toggle_vote(self.user, "vrijdag", "niet meedoen")
        await toggle_vote(self.user, "vrijdag", "misschien")
        votes = await get_user_votes(self.user)
        self.assertEqual(votes["vrijdag"], ["misschien"])

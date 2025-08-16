# tests\test_stemmen.py

import unittest
from apps.utils.poll_storage import toggle_vote, load_votes, reset_votes

class TestStemmen(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        await reset_votes()

    async def test_stem_toevoegen(self):
        user = "123"
        dag = "vrijdag"
        tijd = "om 19:00 uur"

        await toggle_vote(user, dag, tijd)
        votes = await load_votes()

        self.assertIn(tijd, votes[user][dag])

    async def test_stem_verwijderen(self):
        user = "456"
        dag = "zaterdag"
        tijd = "om 20:30 uur"

        await toggle_vote(user, dag, tijd)  # Voeg toe
        await toggle_vote(user, dag, tijd)  # Verwijder weer

        votes = await load_votes()
        self.assertNotIn(tijd, votes[user][dag])

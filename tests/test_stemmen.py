# tests\test_stemmen.py

import os
import unittest
from apps.utils.poll_storage import toggle_vote, load_votes, reset_votes
from tests.base import BaseTestCase

class TestStemmen(BaseTestCase):

    async def asyncSetUp(self):
        await super().asyncSetUp()
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

    async def test_meerdere_stemmen_op_1_dag(self):
        user = "222"
        dag = "zaterdag"
        await toggle_vote(user, dag, "om 19:00 uur")
        await toggle_vote(user, dag, "om 20:30 uur")
        votes = await load_votes()
        self.assertIn("om 19:00 uur", votes[user][dag])
        self.assertIn("om 20:30 uur", votes[user][dag])

    async def test_speciale_opties_vervangen_anderen(self):
        user = "333"
        dag = "zondag"
        await toggle_vote(user, dag, "om 19:00 uur")
        await toggle_vote(user, dag, "misschien")
        votes = await load_votes()
        self.assertEqual(votes[user][dag], ["misschien"])


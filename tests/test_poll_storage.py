# tests/test_poll_storage.py

import io
import os
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from apps.utils import poll_storage
from tests.base import BaseTestCase


def opt(dag, tijd):
    """Kleine helper voor poll-opties (heeft .dag en .tijd)."""
    return SimpleNamespace(dag=dag, tijd=tijd)


class TestPollStorage(BaseTestCase):
    def setUp(self):
        # handige defaults voor opties in meerdere tests
        self.default_options = [
            opt("vrijdag", "19:00"),
            opt("vrijdag", "20:30"),
            opt("zaterdag", "19:00"),
            opt("zaterdag", "20:30"),
            opt("zondag", "19:00"),
            opt("zondag", "20:30"),
        ]

    # --------------------------
    # _read_json: file mist → {}
    # --------------------------
    async def test_read_json_missing_returns_empty(self):
        # Zet tijdelijk een niet-bestaand pad om regel 43 te raken
        missing_path = "votes_missing_test.json"
        if os.path.exists(missing_path):
            os.remove(missing_path)

        with patch.dict(os.environ, {"VOTES_FILE": missing_path}, clear=False):
            root = await poll_storage.load_votes()  # gaat via _read_json → return {}
            self.assertEqual(root, {})

    # -------------------------------------
    # _read_json: kapotte JSON → print + {}
    # -------------------------------------
    async def test_read_json_corrupt_prints_and_returns_empty(self):
        corrupt_path = os.environ["VOTES_FILE"]  # BaseTestCase zet deze
        # Schrijf ongeldige JSON
        with open(corrupt_path, "w", encoding="utf-8") as f:
            f.write("{ not valid json")

        buf = io.StringIO()
        with redirect_stdout(buf):
            _ = await poll_storage.load_votes()  # triggert JSONDecodeError (51-53)
        self.assertIn("beschadigd", buf.getvalue())

        # Daarna moet root weer {} zijn
        root = await poll_storage.load_votes()
        self.assertEqual(root, {})

    # --------------------------
    # add_vote: ongeldige optie
    # --------------------------
    async def test_add_vote_invalid_option_prints_and_no_change(self):
        # Patch op HET MODULE-NIVEAU van poll_storage (niet op apps.entities.*)
        with patch(
            "apps.utils.poll_storage.get_poll_options",
            return_value=self.default_options,
        ), patch("apps.utils.poll_storage.is_valid_option", return_value=False):

            buf = io.StringIO()
            with redirect_stdout(buf):
                await poll_storage.add_vote("u1", "vrijdag", "19:00", 1, 2)

            self.assertIn("Ongeldige combinatie in add_vote", buf.getvalue())
            scoped = await poll_storage.load_votes(1, 2)
            self.assertEqual(scoped, {})  # niets opgeslagen

    # ---------------------------
    # toggle_vote: ongeldige optie
    # ---------------------------
    async def test_toggle_vote_invalid_returns_current_day_votes(self):
        with patch(
            "apps.utils.poll_storage.get_poll_options",
            return_value=self.default_options,
        ), patch("apps.utils.poll_storage.is_valid_option", return_value=False):

            res = await poll_storage.toggle_vote("u1", "vrijdag", "19:00", 1, 2)
            # user bestaat nog niet → _empty_days() geeft dag → get(dag, []) == []
            self.assertEqual(res, [])  # raakt regel 168

    # ---------------------------
    # remove_vote: ongeldige optie
    # ---------------------------
    async def test_remove_vote_invalid_option_prints_and_returns(self):
        with patch(
            "apps.utils.poll_storage.get_poll_options",
            return_value=self.default_options,
        ), patch("apps.utils.poll_storage.is_valid_option", return_value=False):

            buf = io.StringIO()
            with redirect_stdout(buf):
                await poll_storage.remove_vote("u1", "vrijdag", "19:00", 1, 2)

            self.assertIn("Ongeldige combinatie in remove_vote", buf.getvalue())
            scoped = await poll_storage.load_votes(1, 2)
            self.assertEqual(scoped, {})

    # -------------------------
    # add_vote: geldige optie(s)
    # -------------------------
    async def test_add_vote_valid_and_idempotent(self):
        with patch(
            "apps.utils.poll_storage.get_poll_options",
            return_value=self.default_options,
        ), patch("apps.utils.poll_storage.is_valid_option", return_value=True):

            # eerste keer toevoegen
            await poll_storage.add_vote("u1", "vrijdag", "19:00", 1, 2)
            scoped = await poll_storage.load_votes(1, 2)
            self.assertIn("u1", scoped)
            self.assertEqual(scoped["u1"]["vrijdag"], ["19:00"])

            # nog een keer zelfde → geen dubbele
            await poll_storage.add_vote("u1", "vrijdag", "19:00", 1, 2)
            scoped2 = await poll_storage.load_votes(1, 2)
            self.assertEqual(scoped2["u1"]["vrijdag"], ["19:00"])

    # ---------------------------
    # remove_vote: geldige optie
    # ---------------------------
    async def test_remove_vote_valid_removes_and_saves(self):
        with patch(
            "apps.utils.poll_storage.get_poll_options",
            return_value=self.default_options,
        ), patch("apps.utils.poll_storage.is_valid_option", return_value=True):

            # setup: voeg eerst toe
            await poll_storage.add_vote("u1", "vrijdag", "19:00", 1, 2)
            scoped = await poll_storage.load_votes(1, 2)
            self.assertEqual(scoped["u1"]["vrijdag"], ["19:00"])

            # verwijder
            await poll_storage.remove_vote("u1", "vrijdag", "19:00", 1, 2)
            scoped2 = await poll_storage.load_votes(1, 2)
            self.assertNotIn("19:00", scoped2["u1"].get("vrijdag", []))

    # -----------------------------------
    # add_guest_votes: ongeldige optie
    # -----------------------------------
    async def test_add_guest_votes_invalid_returns_all_as_skipped(self):
        with patch(
            "apps.utils.poll_storage.get_poll_options",
            return_value=self.default_options,
        ), patch("apps.utils.poll_storage.is_valid_option", return_value=False):

            added, skipped = await poll_storage.add_guest_votes(
                "owner", "vrijdag", "19:00", ["Alice"], 1, 2
            )
            self.assertEqual(added, [])
            self.assertEqual(skipped, ["Alice"])  # regel 263

    # ----------------------------------------------------
    # add_guest_votes: bestaande naam/tijd → overgeslagen
    # ----------------------------------------------------
    async def test_add_guest_votes_skips_existing(self):
        with patch(
            "apps.utils.poll_storage.get_poll_options",
            return_value=self.default_options,
        ), patch("apps.utils.poll_storage.is_valid_option", return_value=True):

            # eerste keer
            added1, skipped1 = await poll_storage.add_guest_votes(
                "owner", "vrijdag", "19:00", ["Alice"], 1, 2
            )
            self.assertEqual(added1, ["Alice"])
            self.assertEqual(skipped1, [])

            # nog eens precies hetzelfde → overgeslagen (281-282)
            added2, skipped2 = await poll_storage.add_guest_votes(
                "owner", "vrijdag", "19:00", ["Alice"], 1, 2
            )
            self.assertEqual(added2, [])
            self.assertEqual(skipped2, ["Alice"])

    # -------------------------------------------------
    # remove_guest_votes: ValueError-pad en else-pad
    # -------------------------------------------------
    async def test_remove_guest_votes_valueerror_and_notfound(self):
        with patch(
            "apps.utils.poll_storage.get_poll_options",
            return_value=self.default_options,
        ), patch("apps.utils.poll_storage.is_valid_option", return_value=True):

            # In-memory dict zodat TrickyList niet door JSON weggeschreven wordt
            class TrickyList(list):
                def remove(self, x):
                    raise ValueError("simulate race")

            gid, cid = "1", "2"
            key = "owner_guest::Bob"
            inmem = {key: {"vrijdag": TrickyList(["19:00"])}}

            async def fake_load_votes(g, c):
                self.assertEqual((g, c), (gid, cid))
                return inmem

            async def fake_save_votes_scoped(g, c, scoped):
                # niks doen; we testen alleen control-flow (except/else)
                self.assertIs(scoped, inmem)

            with patch(
                "apps.utils.poll_storage.load_votes", side_effect=fake_load_votes
            ), patch(
                "apps.utils.poll_storage.save_votes_scoped",
                side_effect=fake_save_votes_scoped,
            ):

                removed, notfound = await poll_storage.remove_guest_votes(
                    "owner", "vrijdag", "19:00", ["Bob"], gid, cid
                )
                self.assertEqual(removed, [])  # except ValueError
                self.assertEqual(notfound, ["Bob"])  # lijn 312-313

                # else-pad (320): gast niet aanwezig
                removed2, notfound2 = await poll_storage.remove_guest_votes(
                    "owner", "vrijdag", "19:00", ["Alice"], gid, cid
                )
                self.assertEqual(removed2, [])
                self.assertEqual(notfound2, ["Alice"])

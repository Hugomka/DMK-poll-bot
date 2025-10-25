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
            opt("vrijdag", "om 19:00 uur"),
            opt("vrijdag", "om 20:30 uur"),
            opt("zaterdag", "om 19:00 uur"),
            opt("zaterdag", "om 20:30 uur"),
            opt("zondag", "om 19:00 uur"),
            opt("zondag", "om 20:30 uur"),
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
                "owner", "vrijdag", "19:00", ["Mario"], 1, 2
            )
            self.assertEqual(added, [])
            self.assertEqual(skipped, ["Mario"])  # regel 263

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
                "owner", "vrijdag", "19:00", ["Mario"], 1, 2
            )
            self.assertEqual(added1, ["Mario"])
            self.assertEqual(skipped1, [])

            # nog eens precies hetzelfde → overgeslagen (281-282)
            added2, skipped2 = await poll_storage.add_guest_votes(
                "owner", "vrijdag", "19:00", ["Mario"], 1, 2
            )
            self.assertEqual(added2, [])
            self.assertEqual(skipped2, ["Mario"])

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
            key = "owner_guest::Luigi"
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
                    "owner", "vrijdag", "19:00", ["Luigi"], gid, cid
                )
                self.assertEqual(removed, [])  # except ValueError
                self.assertEqual(notfound, ["Luigi"])  # lijn 312-313

                # else-pad (320): gast niet aanwezig
                removed2, notfound2 = await poll_storage.remove_guest_votes(
                    "owner", "vrijdag", "19:00", ["Mario"], gid, cid
                )
                self.assertEqual(removed2, [])
                self.assertEqual(notfound2, ["Mario"])

    # ----------------------------------------------------
    # calculate_leading_time: Phase 3 vote analysis logic
    # ----------------------------------------------------
    async def test_calculate_leading_time_no_votes_returns_none(self):
        """Test met geen stemmen → None"""
        result = await poll_storage.calculate_leading_time(1, 2, "vrijdag")
        self.assertIsNone(result)

    async def test_calculate_leading_time_only_19_returns_19(self):
        """Test met alleen 19:00 stemmen → 19:00"""
        with patch(
            "apps.utils.poll_storage.get_poll_options",
            return_value=self.default_options,
        ), patch("apps.utils.poll_storage.is_valid_option", return_value=True):
            # Voeg 3 stemmen toe voor 19:00
            await poll_storage.add_vote("u1", "vrijdag", "om 19:00 uur", 1, 2)
            await poll_storage.add_vote("u2", "vrijdag", "om 19:00 uur", 1, 2)
            await poll_storage.add_vote("u3", "vrijdag", "om 19:00 uur", 1, 2)

            result = await poll_storage.calculate_leading_time(1, 2, "vrijdag")
            self.assertEqual(result, "19:00")

    async def test_calculate_leading_time_only_2030_returns_2030(self):
        """Test met alleen 20:30 stemmen → 20:30"""
        with patch(
            "apps.utils.poll_storage.get_poll_options",
            return_value=self.default_options,
        ), patch("apps.utils.poll_storage.is_valid_option", return_value=True):
            # Voeg 3 stemmen toe voor 20:30
            await poll_storage.add_vote("u1", "vrijdag", "om 20:30 uur", 1, 2)
            await poll_storage.add_vote("u2", "vrijdag", "om 20:30 uur", 1, 2)
            await poll_storage.add_vote("u3", "vrijdag", "om 20:30 uur", 1, 2)

            result = await poll_storage.calculate_leading_time(1, 2, "vrijdag")
            self.assertEqual(result, "20:30")

    async def test_calculate_leading_time_tie_prefers_2030(self):
        """Test met gelijkspel → 20:30 wint (tie-breaker regel)"""
        with patch(
            "apps.utils.poll_storage.get_poll_options",
            return_value=self.default_options,
        ), patch("apps.utils.poll_storage.is_valid_option", return_value=True):
            # 2 stemmen voor 19:00
            await poll_storage.add_vote("u1", "vrijdag", "om 19:00 uur", 1, 2)
            await poll_storage.add_vote("u2", "vrijdag", "om 19:00 uur", 1, 2)
            # 2 stemmen voor 20:30
            await poll_storage.add_vote("u3", "vrijdag", "om 20:30 uur", 1, 2)
            await poll_storage.add_vote("u4", "vrijdag", "om 20:30 uur", 1, 2)

            result = await poll_storage.calculate_leading_time(1, 2, "vrijdag")
            self.assertEqual(result, "20:30")

    async def test_calculate_leading_time_2030_wins_with_more_votes(self):
        """Test met meer stemmen voor 20:30 → 20:30 wint"""
        with patch(
            "apps.utils.poll_storage.get_poll_options",
            return_value=self.default_options,
        ), patch("apps.utils.poll_storage.is_valid_option", return_value=True):
            # 2 stemmen voor 19:00
            await poll_storage.add_vote("u1", "vrijdag", "om 19:00 uur", 1, 2)
            await poll_storage.add_vote("u2", "vrijdag", "om 19:00 uur", 1, 2)
            # 3 stemmen voor 20:30
            await poll_storage.add_vote("u3", "vrijdag", "om 20:30 uur", 1, 2)
            await poll_storage.add_vote("u4", "vrijdag", "om 20:30 uur", 1, 2)
            await poll_storage.add_vote("u5", "vrijdag", "om 20:30 uur", 1, 2)

            result = await poll_storage.calculate_leading_time(1, 2, "vrijdag")
            self.assertEqual(result, "20:30")

    async def test_calculate_leading_time_19_wins_with_more_votes(self):
        """Test met meer stemmen voor 19:00 → 19:00 wint"""
        with patch(
            "apps.utils.poll_storage.get_poll_options",
            return_value=self.default_options,
        ), patch("apps.utils.poll_storage.is_valid_option", return_value=True):
            # 5 stemmen voor 19:00
            await poll_storage.add_vote("u1", "vrijdag", "om 19:00 uur", 1, 2)
            await poll_storage.add_vote("u2", "vrijdag", "om 19:00 uur", 1, 2)
            await poll_storage.add_vote("u3", "vrijdag", "om 19:00 uur", 1, 2)
            await poll_storage.add_vote("u4", "vrijdag", "om 19:00 uur", 1, 2)
            await poll_storage.add_vote("u5", "vrijdag", "om 19:00 uur", 1, 2)
            # 2 stemmen voor 20:30
            await poll_storage.add_vote("u6", "vrijdag", "om 20:30 uur", 1, 2)
            await poll_storage.add_vote("u7", "vrijdag", "om 20:30 uur", 1, 2)

            result = await poll_storage.calculate_leading_time(1, 2, "vrijdag")
            self.assertEqual(result, "19:00")

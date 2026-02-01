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
    # _read_json: kapotte JSON → {}
    # -------------------------------------
    async def test_read_json_corrupt_returns_empty(self):
        corrupt_path = os.environ["VOTES_FILE"]  # BaseTestCase zet deze
        # Schrijf ongeldige JSON
        with open(corrupt_path, "w", encoding="utf-8") as f:
            f.write("{ not valid json")

        # triggert JSONDecodeError en returned {}
        root = await poll_storage.load_votes()
        self.assertEqual(root, {})

        # Daarna moet root nog steeds {} zijn
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

    # ----------------------------------------------------
    # _sync_user_vote_to_channel: syncs votes between channels
    # ----------------------------------------------------
    async def test_sync_user_vote_to_channel(self):
        """Test syncing user votes to another channel."""
        with patch(
            "apps.utils.poll_storage.get_poll_options",
            return_value=self.default_options,
        ), patch("apps.utils.poll_storage.is_valid_option", return_value=True):
            # First add a vote in channel 2
            await poll_storage.add_vote("u1", "vrijdag", "om 19:00 uur", 1, 2)

            # Sync to channel 3
            day_votes = ["om 19:00 uur", "om 20:30 uur"]
            await poll_storage._sync_user_vote_to_channel("1", "3", "u1", "vrijdag", day_votes)

            # Verify the votes are synced
            scoped = await poll_storage.load_votes(1, 3)
            self.assertIn("u1", scoped)
            self.assertEqual(scoped["u1"]["vrijdag"], ["om 19:00 uur", "om 20:30 uur"])

    async def test_toggle_vote_with_category_syncs_to_linked_channels(self):
        """Test toggle_vote syncs to linked channels when channel is in category."""
        with patch(
            "apps.utils.poll_storage.get_poll_options",
            return_value=self.default_options,
        ), patch("apps.utils.poll_storage.is_valid_option", return_value=True):
            # Mock channel with category
            channel = SimpleNamespace(id=2)

            # Mock get_vote_scope_channels to return multiple channels
            with patch(
                "apps.utils.poll_settings.get_vote_scope_channels",
                return_value=[2, 3],  # Two channels share votes
            ):
                result = await poll_storage.toggle_vote(
                    "u1", "vrijdag", "om 19:00 uur", 1, 2, channel=channel
                )
                self.assertEqual(result, ["om 19:00 uur"])

                # Verify the vote was synced to channel 3
                scoped3 = await poll_storage.load_votes(1, 3)
                self.assertIn("u1", scoped3)
                self.assertEqual(scoped3["u1"]["vrijdag"], ["om 19:00 uur"])

    # ----------------------------------------------------
    # was_misschien tracking: count and user IDs
    # ----------------------------------------------------
    async def test_get_was_misschien_count_returns_zero_when_no_tracking(self):
        """Test get_was_misschien_count returns 0 when no tracking entry."""
        count = await poll_storage.get_was_misschien_count("vrijdag", 1, 2)
        self.assertEqual(count, 0)

    async def test_get_was_misschien_user_ids_empty_list_default(self):
        """Test get_was_misschien_user_ids returns empty list by default."""
        user_ids = await poll_storage.get_was_misschien_user_ids("vrijdag", 1, 2)
        self.assertEqual(user_ids, [])

    async def test_set_and_get_was_misschien_user_ids(self):
        """Test setting and getting was_misschien user IDs."""
        with patch(
            "apps.utils.poll_storage.get_poll_options",
            return_value=self.default_options,
        ):
            # Set user IDs
            await poll_storage.set_was_misschien_user_ids(
                "vrijdag", ["111", "222", "333"], 1, 2
            )

            # Get them back
            user_ids = await poll_storage.get_was_misschien_user_ids("vrijdag", 1, 2)
            self.assertEqual(user_ids, ["111", "222", "333"])

            # Count should match
            count = await poll_storage.get_was_misschien_count("vrijdag", 1, 2)
            self.assertEqual(count, 3)

    async def test_get_was_misschien_user_ids_old_count_format(self):
        """Test backwards compatibility: old format stored count as single element."""
        with patch(
            "apps.utils.poll_storage.get_poll_options",
            return_value=self.default_options,
        ):
            # Use deprecated function to store old format
            await poll_storage.set_was_misschien_count("vrijdag", 5, 1, 2)

            # Should return empty list for old format (no user IDs available)
            user_ids = await poll_storage.get_was_misschien_user_ids("vrijdag", 1, 2)
            self.assertEqual(user_ids, [])

    async def test_set_was_misschien_count_deprecated(self):
        """Test deprecated set_was_misschien_count function."""
        with patch(
            "apps.utils.poll_storage.get_poll_options",
            return_value=self.default_options,
        ):
            # This function stores old format
            await poll_storage.set_was_misschien_count("zaterdag", 3, 1, 2)

            # Verify it was stored (old format stores count as single element)
            scoped = await poll_storage.load_votes(1, 2)
            tracking_id = poll_storage._was_misschien_id("2")
            self.assertIn(tracking_id, scoped)
            self.assertEqual(scoped[tracking_id]["zaterdag"], ["3"])

    async def test_reset_was_misschien_counts(self):
        """Test reset_was_misschien_counts removes all tracking."""
        with patch(
            "apps.utils.poll_storage.get_poll_options",
            return_value=self.default_options,
        ):
            # Set some tracking
            await poll_storage.set_was_misschien_user_ids(
                "vrijdag", ["111", "222"], 1, 2
            )
            await poll_storage.set_was_misschien_user_ids(
                "zaterdag", ["333"], 1, 2
            )

            # Verify it's there
            count = await poll_storage.get_was_misschien_count("vrijdag", 1, 2)
            self.assertEqual(count, 2)

            # Reset
            await poll_storage.reset_was_misschien_counts(1, 2)

            # Verify it's gone
            count = await poll_storage.get_was_misschien_count("vrijdag", 1, 2)
            self.assertEqual(count, 0)

    async def test_reset_was_misschien_counts_when_no_tracking(self):
        """Test reset_was_misschien_counts does nothing when no tracking exists."""
        # Should not raise any errors
        await poll_storage.reset_was_misschien_counts(1, 2)

        # Verify nothing changed
        count = await poll_storage.get_was_misschien_count("vrijdag", 1, 2)
        self.assertEqual(count, 0)

    # ----------------------------------------------------
    # Category-based vote scope functions
    # ----------------------------------------------------
    async def test_load_votes_for_scope_merges_channels(self):
        """Test load_votes_for_scope merges votes from multiple channels."""
        with patch(
            "apps.utils.poll_storage.get_poll_options",
            return_value=self.default_options,
        ), patch("apps.utils.poll_storage.is_valid_option", return_value=True):
            # Add votes in channel 2
            await poll_storage.add_vote("u1", "vrijdag", "om 19:00 uur", 1, 2)

            # Add votes in channel 3
            await poll_storage.add_vote("u2", "vrijdag", "om 20:30 uur", 1, 3)

            # Merge from both channels
            merged = await poll_storage.load_votes_for_scope(1, [2, 3])

            # Both users should be in merged
            self.assertIn("u1", merged)
            self.assertIn("u2", merged)
            self.assertEqual(merged["u1"]["vrijdag"], ["om 19:00 uur"])
            self.assertEqual(merged["u2"]["vrijdag"], ["om 20:30 uur"])

    async def test_load_votes_for_scope_skips_tracking_entries(self):
        """Test load_votes_for_scope skips entries starting with _."""
        with patch(
            "apps.utils.poll_storage.get_poll_options",
            return_value=self.default_options,
        ), patch("apps.utils.poll_storage.is_valid_option", return_value=True):
            # Add a regular vote
            await poll_storage.add_vote("u1", "vrijdag", "om 19:00 uur", 1, 2)

            # Add was_misschien tracking
            await poll_storage.set_was_misschien_user_ids("vrijdag", ["111"], 1, 2)

            # Merge should skip tracking entries
            merged = await poll_storage.load_votes_for_scope(1, [2])

            # Regular user should be there
            self.assertIn("u1", merged)

            # Tracking entry should NOT be there
            for key in merged.keys():
                self.assertFalse(key.startswith("_"), f"Tracking entry {key} should be skipped")

    async def test_load_votes_for_scope_first_occurrence_wins(self):
        """Test that first occurrence wins when same user is in multiple channels."""
        with patch(
            "apps.utils.poll_storage.get_poll_options",
            return_value=self.default_options,
        ), patch("apps.utils.poll_storage.is_valid_option", return_value=True):
            # Add vote in channel 2
            await poll_storage.add_vote("u1", "vrijdag", "om 19:00 uur", 1, 2)

            # Add different vote for same user in channel 3
            await poll_storage.add_vote("u1", "vrijdag", "om 20:30 uur", 1, 3)

            # Merge - channel 2 is first, so its data wins
            merged = await poll_storage.load_votes_for_scope(1, [2, 3])

            self.assertIn("u1", merged)
            # First occurrence (channel 2) wins
            self.assertEqual(merged["u1"]["vrijdag"], ["om 19:00 uur"])

    async def test_get_counts_for_day_scoped(self):
        """Test get_counts_for_day_scoped aggregates across channels."""
        with patch(
            "apps.utils.poll_storage.get_poll_options",
            return_value=self.default_options,
        ), patch("apps.utils.poll_storage.is_valid_option", return_value=True):
            # Add votes in channel 2
            await poll_storage.add_vote("u1", "vrijdag", "om 19:00 uur", 1, 2)
            await poll_storage.add_vote("u2", "vrijdag", "om 19:00 uur", 1, 2)

            # Add votes in channel 3
            await poll_storage.add_vote("u3", "vrijdag", "om 20:30 uur", 1, 3)

            # Get aggregated counts
            counts = await poll_storage.get_counts_for_day_scoped("vrijdag", 1, [2, 3])

            self.assertEqual(counts.get("om 19:00 uur", 0), 2)
            self.assertEqual(counts.get("om 20:30 uur", 0), 1)

    async def test_calculate_leading_time_scoped_no_votes(self):
        """Test calculate_leading_time_scoped with no votes returns None."""
        result = await poll_storage.calculate_leading_time_scoped(1, [2, 3], "vrijdag")
        self.assertIsNone(result)

    async def test_calculate_leading_time_scoped_2030_wins_tie(self):
        """Test calculate_leading_time_scoped: 20:30 wins on tie."""
        with patch(
            "apps.utils.poll_storage.get_poll_options",
            return_value=self.default_options,
        ), patch("apps.utils.poll_storage.is_valid_option", return_value=True):
            # 2 votes for 19:00
            await poll_storage.add_vote("u1", "vrijdag", "om 19:00 uur", 1, 2)
            await poll_storage.add_vote("u2", "vrijdag", "om 19:00 uur", 1, 2)
            # 2 votes for 20:30
            await poll_storage.add_vote("u3", "vrijdag", "om 20:30 uur", 1, 3)
            await poll_storage.add_vote("u4", "vrijdag", "om 20:30 uur", 1, 3)

            result = await poll_storage.calculate_leading_time_scoped(1, [2, 3], "vrijdag")
            self.assertEqual(result, "20:30")

    async def test_calculate_leading_time_scoped_19_wins(self):
        """Test calculate_leading_time_scoped: 19:00 wins with more votes."""
        with patch(
            "apps.utils.poll_storage.get_poll_options",
            return_value=self.default_options,
        ), patch("apps.utils.poll_storage.is_valid_option", return_value=True):
            # 3 votes for 19:00
            await poll_storage.add_vote("u1", "vrijdag", "om 19:00 uur", 1, 2)
            await poll_storage.add_vote("u2", "vrijdag", "om 19:00 uur", 1, 2)
            await poll_storage.add_vote("u3", "vrijdag", "om 19:00 uur", 1, 3)
            # 1 vote for 20:30
            await poll_storage.add_vote("u4", "vrijdag", "om 20:30 uur", 1, 3)

            result = await poll_storage.calculate_leading_time_scoped(1, [2, 3], "vrijdag")
            self.assertEqual(result, "19:00")

    async def test_get_non_voters_for_day_scoped(self):
        """Test get_non_voters_for_day_scoped identifies non-voters across channels."""
        with patch(
            "apps.utils.poll_storage.get_poll_options",
            return_value=self.default_options,
        ), patch("apps.utils.poll_storage.is_valid_option", return_value=True):
            # Add votes for u1 and u2
            await poll_storage.add_vote("111", "vrijdag", "om 19:00 uur", 1, 2)
            await poll_storage.add_vote("222", "vrijdag", "om 20:30 uur", 1, 3)

            # Create mock channels with members
            member1 = SimpleNamespace(id=111, bot=False)
            member2 = SimpleNamespace(id=222, bot=False)
            member3 = SimpleNamespace(id=333, bot=False)  # Non-voter
            bot_member = SimpleNamespace(id=999, bot=True)  # Bot - should be excluded

            channel2 = SimpleNamespace(members=[member1, member3, bot_member])
            channel3 = SimpleNamespace(members=[member2, member3])

            count, non_voter_ids = await poll_storage.get_non_voters_for_day_scoped(
                "vrijdag", 1, [2, 3], [channel2, channel3]
            )

            # Only member3 (333) should be non-voter
            self.assertEqual(count, 1)
            self.assertIn("333", non_voter_ids)
            self.assertNotIn("111", non_voter_ids)
            self.assertNotIn("222", non_voter_ids)
            self.assertNotIn("999", non_voter_ids)  # Bot excluded

    async def test_get_non_voters_for_day_scoped_counts_guests(self):
        """Test get_non_voters_for_day_scoped: guest votes count for owner."""
        with patch(
            "apps.utils.poll_storage.get_poll_options",
            return_value=self.default_options,
        ), patch("apps.utils.poll_storage.is_valid_option", return_value=True):
            # Add guest vote for u1 (111)
            await poll_storage.add_guest_votes(
                "111", "vrijdag", "om 19:00 uur", ["Mario"], 1, 2
            )

            # Create mock channel with members
            member1 = SimpleNamespace(id=111, bot=False)
            member2 = SimpleNamespace(id=222, bot=False)  # Non-voter

            channel = SimpleNamespace(members=[member1, member2])

            count, non_voter_ids = await poll_storage.get_non_voters_for_day_scoped(
                "vrijdag", 1, [2], [channel]
            )

            # Only member2 (222) should be non-voter - u1 voted via guest
            self.assertEqual(count, 1)
            self.assertIn("222", non_voter_ids)
            self.assertNotIn("111", non_voter_ids)

    async def test_get_voters_for_time_scoped(self):
        """Test get_voters_for_time_scoped returns correct voter IDs."""
        with patch(
            "apps.utils.poll_storage.get_poll_options",
            return_value=self.default_options,
        ), patch("apps.utils.poll_storage.is_valid_option", return_value=True):
            # Add votes for different times
            await poll_storage.add_vote("u1", "vrijdag", "om 19:00 uur", 1, 2)
            await poll_storage.add_vote("u2", "vrijdag", "om 19:00 uur", 1, 3)
            await poll_storage.add_vote("u3", "vrijdag", "om 20:30 uur", 1, 2)

            # Get voters for 19:00
            voters_19 = await poll_storage.get_voters_for_time_scoped(
                "vrijdag", "om 19:00 uur", 1, [2, 3]
            )
            self.assertEqual(len(voters_19), 2)
            self.assertIn("u1", voters_19)
            self.assertIn("u2", voters_19)

            # Get voters for 20:30
            voters_2030 = await poll_storage.get_voters_for_time_scoped(
                "vrijdag", "om 20:30 uur", 1, [2, 3]
            )
            self.assertEqual(len(voters_2030), 1)
            self.assertIn("u3", voters_2030)

    async def test_get_voters_for_time_scoped_no_voters(self):
        """Test get_voters_for_time_scoped returns empty list when no voters."""
        voters = await poll_storage.get_voters_for_time_scoped(
            "vrijdag", "om 19:00 uur", 1, [2, 3]
        )
        self.assertEqual(voters, [])

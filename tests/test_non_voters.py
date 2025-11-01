"""Tests for non-voter tracking functionality in poll_storage.py"""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from apps.utils.poll_storage import (
    _extract_user_id_from_non_voter,
    _is_non_voter_id,
    _non_voter_id,
    get_non_voters_for_day,
    load_votes,
    reset_votes_scoped,
    toggle_vote,
    update_non_voters,
)


class TestNonVoterHelpers(unittest.IsolatedAsyncioTestCase):
    """Test helper functions for non-voter tracking"""

    def test_non_voter_id_generation(self):
        """Test that non-voter IDs are generated correctly"""
        self.assertEqual(_non_voter_id(123), "_non_voter::123")
        self.assertEqual(_non_voter_id("456"), "_non_voter::456")

    def test_is_non_voter_id_true(self):
        """Test that non-voter IDs are correctly identified"""
        self.assertTrue(_is_non_voter_id("_non_voter::123"))
        self.assertTrue(_is_non_voter_id("_non_voter::456"))

    def test_is_non_voter_id_false(self):
        """Test that regular IDs are not identified as non-voter IDs"""
        self.assertFalse(_is_non_voter_id("123"))
        self.assertFalse(_is_non_voter_id("user_123"))
        self.assertFalse(_is_non_voter_id(123))  # Not a string
        self.assertFalse(_is_non_voter_id(""))

    def test_extract_user_id_from_non_voter(self):
        """Test extracting user ID from non-voter ID"""
        self.assertEqual(_extract_user_id_from_non_voter("_non_voter::123"), "123")
        self.assertEqual(_extract_user_id_from_non_voter("_non_voter::456"), "456")

    def test_extract_user_id_from_regular_id(self):
        """Test that regular IDs are returned unchanged"""
        self.assertEqual(_extract_user_id_from_non_voter("123"), "123")
        self.assertEqual(_extract_user_id_from_non_voter("user_456"), "user_456")


class TestUpdateNonVoters(unittest.IsolatedAsyncioTestCase):
    """Test update_non_voters function"""

    async def asyncSetUp(self):
        await reset_votes_scoped(1, 123)

    async def asyncTearDown(self):
        await reset_votes_scoped(1, 123)

    async def test_update_non_voters_no_channel(self):
        """Test that update_non_voters returns early when channel is None"""
        # Should not raise an error
        await update_non_voters(1, 123, None)
        votes = await load_votes(1, 123)
        self.assertEqual(votes, {})

    async def test_update_non_voters_with_all_voted(self):
        """Test non-voters when everyone has voted"""
        # Create mock members
        member1 = SimpleNamespace(id=100, bot=False)
        member2 = SimpleNamespace(id=200, bot=False)
        mock_channel = SimpleNamespace(members=[member1, member2])

        # Both members vote
        await toggle_vote(100, "vrijdag", "om 19:00 uur", 1, 123)
        await toggle_vote(200, "vrijdag", "om 20:30 uur", 1, 123)

        # Update non-voters
        await update_non_voters(1, 123, mock_channel)

        # Check that no non-voters are stored for vrijdag
        count, ids = await get_non_voters_for_day("vrijdag", 1, 123)
        self.assertEqual(count, 0)
        self.assertEqual(ids, [])

    async def test_update_non_voters_with_some_non_voters(self):
        """Test non-voters when some members haven't voted"""
        # Create mock members
        member1 = SimpleNamespace(id=100, bot=False)
        member2 = SimpleNamespace(id=200, bot=False)
        member3 = SimpleNamespace(id=300, bot=False)
        mock_channel = SimpleNamespace(members=[member1, member2, member3])

        # Only member1 votes
        await toggle_vote(100, "vrijdag", "om 19:00 uur", 1, 123)

        # Update non-voters
        await update_non_voters(1, 123, mock_channel)

        # Check that members 2 and 3 are non-voters
        count, ids = await get_non_voters_for_day("vrijdag", 1, 123)
        self.assertEqual(count, 2)
        self.assertIn("200", ids)
        self.assertIn("300", ids)

    async def test_update_non_voters_excludes_bots(self):
        """Test that bots are excluded from non-voter tracking"""
        # Create mock members including a bot
        member1 = SimpleNamespace(id=100, bot=False)
        bot_member = SimpleNamespace(id=999, bot=True)
        mock_channel = SimpleNamespace(members=[member1, bot_member])

        # Nobody votes
        # Update non-voters
        await update_non_voters(1, 123, mock_channel)

        # Check that only member1 is a non-voter (bot is excluded)
        count, ids = await get_non_voters_for_day("vrijdag", 1, 123)
        self.assertEqual(count, 1)
        self.assertIn("100", ids)
        self.assertNotIn("999", ids)

    async def test_update_non_voters_handles_guests(self):
        """Test that guests are counted via their owner"""
        from apps.utils.poll_storage import add_guest_votes

        # Create mock members
        owner = SimpleNamespace(id=100, bot=False)
        member2 = SimpleNamespace(id=200, bot=False)
        mock_channel = SimpleNamespace(members=[owner, member2])

        # Owner adds a guest
        await add_guest_votes(100, "vrijdag", "om 19:00 uur", ["Gast1"], 1, 123)

        # Update non-voters
        await update_non_voters(1, 123, mock_channel)

        # Owner voted via guest, so only member2 is non-voter
        count, ids = await get_non_voters_for_day("vrijdag", 1, 123)
        self.assertEqual(count, 1)
        self.assertIn("200", ids)
        self.assertNotIn("100", ids)

    async def test_update_non_voters_removes_old_entries(self):
        """Test that old non-voter entries are removed when member votes"""
        # Create mock members
        member1 = SimpleNamespace(id=100, bot=False)
        mock_channel = SimpleNamespace(members=[member1])

        # First update: member1 is a non-voter
        await update_non_voters(1, 123, mock_channel)
        count, ids = await get_non_voters_for_day("vrijdag", 1, 123)
        self.assertEqual(count, 1)
        self.assertIn("100", ids)

        # Member1 votes
        await toggle_vote(100, "vrijdag", "om 19:00 uur", 1, 123)

        # Second update: member1 should be removed from non-voters
        await update_non_voters(1, 123, mock_channel)
        count, ids = await get_non_voters_for_day("vrijdag", 1, 123)
        self.assertEqual(count, 0)
        self.assertEqual(ids, [])

    async def test_update_non_voters_per_day_tracking(self):
        """Test that non-voters are tracked separately per day"""
        # Create mock members
        member1 = SimpleNamespace(id=100, bot=False)
        member2 = SimpleNamespace(id=200, bot=False)
        mock_channel = SimpleNamespace(members=[member1, member2])

        # Member1 votes for vrijdag only
        await toggle_vote(100, "vrijdag", "om 19:00 uur", 1, 123)

        # Update non-voters
        await update_non_voters(1, 123, mock_channel)

        # Vrijdag: only member2 is non-voter
        count_vr, ids_vr = await get_non_voters_for_day("vrijdag", 1, 123)
        self.assertEqual(count_vr, 1)
        self.assertIn("200", ids_vr)

        # Zaterdag: both are non-voters
        count_za, ids_za = await get_non_voters_for_day("zaterdag", 1, 123)
        self.assertEqual(count_za, 2)
        self.assertIn("100", ids_za)
        self.assertIn("200", ids_za)

    async def test_update_non_voters_with_member_no_id(self):
        """Test handling of members without ID attribute"""
        # Create mock member without id
        member_no_id = SimpleNamespace(bot=False)
        # Remove id attribute entirely
        delattr(member_no_id, "id") if hasattr(member_no_id, "id") else None

        mock_channel = SimpleNamespace(members=[member_no_id])

        # Should not crash
        await update_non_voters(1, 123, mock_channel)

        # No non-voters should be tracked (member has no valid ID)
        count, ids = await get_non_voters_for_day("vrijdag", 1, 123)
        self.assertEqual(count, 0)

    async def test_update_non_voters_with_empty_member_id(self):
        """Test handling of members with empty ID"""
        # Create mock member with empty id
        member_empty_id = SimpleNamespace(id="", bot=False)
        mock_channel = SimpleNamespace(members=[member_empty_id])

        # Should not crash
        await update_non_voters(1, 123, mock_channel)

        # No non-voters should be tracked (member has empty ID)
        count, ids = await get_non_voters_for_day("vrijdag", 1, 123)
        self.assertEqual(count, 0)


class TestGetNonVotersForDay(unittest.IsolatedAsyncioTestCase):
    """Test get_non_voters_for_day function"""

    async def asyncSetUp(self):
        await reset_votes_scoped(1, 123)

    async def asyncTearDown(self):
        await reset_votes_scoped(1, 123)

    async def test_get_non_voters_empty(self):
        """Test getting non-voters when there are none"""
        count, ids = await get_non_voters_for_day("vrijdag", 1, 123)
        self.assertEqual(count, 0)
        self.assertEqual(ids, [])

    async def test_get_non_voters_with_data(self):
        """Test getting non-voters when they exist"""
        # Create mock members
        member1 = SimpleNamespace(id=100, bot=False)
        member2 = SimpleNamespace(id=200, bot=False)
        mock_channel = SimpleNamespace(members=[member1, member2])

        # Update non-voters (nobody voted)
        await update_non_voters(1, 123, mock_channel)

        # Get non-voters for vrijdag
        count, ids = await get_non_voters_for_day("vrijdag", 1, 123)
        self.assertEqual(count, 2)
        self.assertIn("100", ids)
        self.assertIn("200", ids)

    async def test_get_non_voters_different_days(self):
        """Test that non-voters are tracked per day"""
        # Create mock members
        member1 = SimpleNamespace(id=100, bot=False)
        member2 = SimpleNamespace(id=200, bot=False)
        mock_channel = SimpleNamespace(members=[member1, member2])

        # Member1 votes for vrijdag, member2 votes for zaterdag
        await toggle_vote(100, "vrijdag", "om 19:00 uur", 1, 123)
        await toggle_vote(200, "zaterdag", "om 20:30 uur", 1, 123)

        # Update non-voters
        await update_non_voters(1, 123, mock_channel)

        # Vrijdag: only member2 is non-voter
        count_vr, ids_vr = await get_non_voters_for_day("vrijdag", 1, 123)
        self.assertEqual(count_vr, 1)
        self.assertIn("200", ids_vr)

        # Zaterdag: only member1 is non-voter
        count_za, ids_za = await get_non_voters_for_day("zaterdag", 1, 123)
        self.assertEqual(count_za, 1)
        self.assertIn("100", ids_za)

    async def test_get_non_voters_handles_none_per_dag(self):
        """Test handling of None in per_dag dictionary"""
        from apps.utils.poll_storage import save_votes_scoped

        # Manually create a non-voter entry with None per_dag (edge case)
        scoped = {
            "_non_voter::100": None,  # Edge case: None instead of dict
            "_non_voter::200": {"vrijdag": ["niet gestemd"]},
        }
        await save_votes_scoped(1, 123, scoped)

        # Should not crash and should only return member 200
        count, ids = await get_non_voters_for_day("vrijdag", 1, 123)
        self.assertEqual(count, 1)
        self.assertIn("200", ids)

    async def test_get_non_voters_handles_non_list_tijden(self):
        """Test handling of non-list tijden values"""
        from apps.utils.poll_storage import save_votes_scoped

        # Manually create a non-voter entry with non-list tijden (edge case)
        scoped = {
            "_non_voter::100": {"vrijdag": "niet gestemd"},  # String instead of list
            "_non_voter::200": {"vrijdag": ["niet gestemd"]},
        }
        await save_votes_scoped(1, 123, scoped)

        # Should not crash and should only return member 200
        count, ids = await get_non_voters_for_day("vrijdag", 1, 123)
        self.assertEqual(count, 1)
        self.assertIn("200", ids)


class TestNonVoterEdgeCases(unittest.IsolatedAsyncioTestCase):
    """Test edge cases and cleanup logic for non-voters"""

    async def asyncSetUp(self):
        await reset_votes_scoped(1, 123)

    async def asyncTearDown(self):
        await reset_votes_scoped(1, 123)

    async def test_update_non_voters_cleanup_when_all_days_removed(self):
        """Test that non-voter entry is fully removed when no days remain"""
        from apps.utils.poll_storage import save_votes_scoped

        # Create mock members
        member1 = SimpleNamespace(id=100, bot=False)
        mock_channel = SimpleNamespace(members=[member1])

        # Manually create a non-voter entry for all days
        scoped = {
            "_non_voter::100": {
                "vrijdag": ["niet gestemd"],
                "zaterdag": ["niet gestemd"],
                "zondag": ["niet gestemd"],
            }
        }
        await save_votes_scoped(1, 123, scoped)

        # Member votes for all days
        await toggle_vote("100", "vrijdag", "om 19:00 uur", 1, 123)
        await toggle_vote("100", "zaterdag", "om 20:30 uur", 1, 123)
        await toggle_vote("100", "zondag", "om 19:00 uur", 1, 123)

        # Update should remove the entire non-voter entry
        await update_non_voters(1, 123, mock_channel)

        # Verify the non-voter entry is completely removed
        votes = await load_votes(1, 123)
        self.assertNotIn("_non_voter::100", votes)

    async def test_update_non_voters_partial_day_cleanup(self):
        """Test that only specific days are removed from non-voter entry"""
        from apps.utils.poll_storage import save_votes_scoped

        # Create mock members
        member1 = SimpleNamespace(id=100, bot=False)
        mock_channel = SimpleNamespace(members=[member1])

        # Manually create a non-voter entry for multiple days
        scoped = {
            "_non_voter::100": {
                "vrijdag": ["niet gestemd"],
                "zaterdag": ["niet gestemd"],
                "zondag": ["niet gestemd"],
            }
        }
        await save_votes_scoped(1, 123, scoped)

        # Member votes only for vrijdag
        await toggle_vote("100", "vrijdag", "om 19:00 uur", 1, 123)

        # Update should remove only vrijdag from non-voter entry
        await update_non_voters(1, 123, mock_channel)

        # Verify vrijdag is removed but others remain
        votes = await load_votes(1, 123)
        self.assertIn("_non_voter::100", votes)
        self.assertNotIn("vrijdag", votes["_non_voter::100"])
        self.assertIn("zaterdag", votes["_non_voter::100"])
        self.assertIn("zondag", votes["_non_voter::100"])

    async def test_update_non_voters_with_existing_non_voter_entries(self):
        """Test that existing non-voter entries are properly updated"""
        from apps.utils.poll_storage import save_votes_scoped

        # Create mock members
        member1 = SimpleNamespace(id=100, bot=False)
        member2 = SimpleNamespace(id=200, bot=False)
        mock_channel = SimpleNamespace(members=[member1, member2])

        # Start with old non-voter data
        scoped = {
            "_non_voter::100": {"vrijdag": ["niet gestemd"]},
            "_non_voter::999": {"vrijdag": ["niet gestemd"]},  # Member no longer in channel
        }
        await save_votes_scoped(1, 123, scoped)

        # Update non-voters
        await update_non_voters(1, 123, mock_channel)

        # Member 999 should be removed, members 100 and 200 should be non-voters
        votes = await load_votes(1, 123)
        self.assertNotIn("_non_voter::999", votes)
        self.assertIn("_non_voter::100", votes)
        self.assertIn("_non_voter::200", votes)


if __name__ == "__main__":
    unittest.main()

# tests/test_decision.py

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from apps.logic.decision import build_decision_line
from apps.utils.poll_settings import set_visibility
from apps.utils.poll_storage import save_votes_scoped
from tests.base import BaseTestCase

AMS = ZoneInfo("Europe/Amsterdam")
FRI = "vrijdag"
T19 = "om 19:00 uur"
T2030 = "om 20:30 uur"


class TestDecision(BaseTestCase):

    async def asyncSetUp(self):
        await super().asyncSetUp()

    async def _set_votes(self, mapping: dict):
        """mapping: dict[str_user_id] -> {"vrijdag": [tijd, ...]}"""
        await save_votes_scoped(1, 12345, mapping)

    def _dt(self, y, m, d, hh=12, mm=0):
        return datetime(y, m, d, hh, mm, tzinfo=AMS)

    async def test_before_deadline_shows_announcement(self):
        set_visibility(12345, FRI, modus="deadline", tijd="18:00")
        now = self._dt(2025, 8, 22, 17, 0)

        await self._set_votes({})
        line = await build_decision_line(1, 12345, FRI, now)
        self.assertIsNotNone(line)
        assert line is not None
        self.assertIn("18:00", line)

    async def test_after_deadline_winner_2030(self):
        set_visibility(12345, FRI, modus="deadline", tijd="18:00")
        now = self._dt(2025, 8, 22, 19, 0)

        # 6 stemmen op 20:30, 5 op 19:00
        votes = {}
        for i in range(1, 7):
            votes[str(i)] = {FRI: [T2030]}
        for i in range(7, 12):
            votes[str(i)] = {FRI: [T19]}

        await self._set_votes(votes)
        line = await build_decision_line(1, 12345, FRI, now)
        self.assertIsNotNone(line)
        assert line is not None
        self.assertIn("20:30", line)
        self.assertIn("6 stemmen", line)

    async def test_after_deadline_winner_19(self):
        set_visibility(12345, FRI, modus="deadline", tijd="18:00")
        now = self._dt(2025, 8, 22, 19, 0)

        # 7 op 19:00, 2 op 20:30
        votes = {}
        for i in range(1, 8):
            votes[str(i)] = {FRI: [T19]}
        for i in range(8, 10):
            votes[str(i)] = {FRI: [T2030]}

        await self._set_votes(votes)
        line = await build_decision_line(1, 12345, FRI, now)
        self.assertIsNotNone(line)
        assert line is not None
        self.assertIn("19:00", line)
        self.assertIn("7 stemmen", line)

    async def test_after_deadline_tie_prefers_2030(self):
        set_visibility(12345, FRI, modus="deadline", tijd="18:00")
        now = self._dt(2025, 8, 22, 19, 0)

        # 6 op 19:00, 6 op 20:30 → 20:30 wint bij gelijk
        votes = {}
        for i in range(1, 7):
            votes[str(i)] = {FRI: [T19]}
        for i in range(7, 13):
            votes[str(i)] = {FRI: [T2030]}

        await self._set_votes(votes)
        line = await build_decision_line(1, 12345, FRI, now)
        self.assertIsNotNone(line)
        assert line is not None
        self.assertIn("20:30", line)
        self.assertIn("6", line)

    async def test_after_deadline_not_enough_votes(self):
        set_visibility(12345, FRI, modus="deadline", tijd="18:00")
        now = self._dt(2025, 8, 22, 19, 0)

        # 5 op 19:00, 4 op 20:30 → drempel niet gehaald
        votes = {}
        for i in range(1, 6):
            votes[str(i)] = {FRI: [T19]}
        for i in range(6, 10):
            votes[str(i)] = {FRI: [T2030]}

        await self._set_votes(votes)
        line = await build_decision_line(1, 12345, FRI, now)
        self.assertIsNotNone(line)
        assert line is not None
        self.assertIn("Gaat niet door", line)

    async def test_other_day_returns_none(self):
        # Donderdag 2025-08-21 → dag is niet vrijdag → None
        set_visibility(12345, FRI, modus="deadline", tijd="18:00")
        now = self._dt(2025, 8, 21, 12, 0)

        await self._set_votes({})
        line = await build_decision_line(1, 12345, FRI, now)
        self.assertIsNone(line)

    async def test_invalid_dag_returns_none(self):
        """Test dat een ongeldige dagnaam None teruggeeft (line 52)"""
        now = self._dt(2025, 8, 22, 19, 0)  # vrijdag

        line = await build_decision_line(1, 12345, "onbekende_dag", now)
        self.assertIsNone(line)

    async def test_with_channel_uses_scoped_counts(self):
        """Test dat channel parameter category-scoped counts gebruikt (lines 63-69)"""
        from unittest.mock import MagicMock, patch, AsyncMock

        set_visibility(12345, FRI, modus="deadline", tijd="18:00")
        now = self._dt(2025, 8, 22, 19, 0)

        # Create mock channel with category containing multiple channels
        mock_channel = MagicMock()
        mock_channel.id = 12345

        # Mock get_vote_scope_channels at its source (poll_settings)
        with patch(
            "apps.utils.poll_settings.get_vote_scope_channels",
            return_value=[12345, 67890],
        ), patch(
            "apps.logic.decision.get_counts_for_day_scoped",
            new=AsyncMock(return_value={T19: 7, T2030: 3}),
        ) as mock_scoped:
            line = await build_decision_line(1, 12345, FRI, now, channel=mock_channel)

        # Should have used scoped counts
        mock_scoped.assert_awaited_once_with(FRI, 1, [12345, 67890])
        self.assertIsNotNone(line)
        assert line is not None
        self.assertIn("19:00", line)

    async def test_with_channel_single_scope_uses_regular_counts(self):
        """Test dat single scope channel reguliere counts gebruikt (line 69)"""
        from unittest.mock import MagicMock, patch, AsyncMock

        set_visibility(12345, FRI, modus="deadline", tijd="18:00")
        now = self._dt(2025, 8, 22, 19, 0)

        mock_channel = MagicMock()
        mock_channel.id = 12345

        # Mock get_vote_scope_channels to return only one channel
        with patch(
            "apps.utils.poll_settings.get_vote_scope_channels",
            return_value=[12345],
        ), patch(
            "apps.logic.decision.get_counts_for_day",
            new=AsyncMock(return_value={T19: 8, T2030: 2}),
        ) as mock_regular:
            line = await build_decision_line(1, 12345, FRI, now, channel=mock_channel)

        # Should have used regular counts (not scoped)
        mock_regular.assert_awaited_once_with(FRI, 1, 12345)
        self.assertIsNotNone(line)
        assert line is not None
        self.assertIn("19:00", line)

    async def test_edge_case_c19_below_threshold_c2030_zero(self):
        """Test edge case waar c19 < MIN maar > c2030 (line 84)"""
        set_visibility(12345, FRI, modus="deadline", tijd="18:00")
        now = self._dt(2025, 8, 22, 19, 0)

        # 5 op 19:00, 0 op 20:30 → geen van beide haalt drempel
        # c2030 (0) >= max(c19=5, MIN=6) → False
        # c19 (5) >= MIN (6) → False
        # → fallback line 84
        votes = {}
        for i in range(1, 6):
            votes[str(i)] = {FRI: [T19]}

        await self._set_votes(votes)
        line = await build_decision_line(1, 12345, FRI, now)
        self.assertIsNotNone(line)
        assert line is not None
        self.assertIn("Gaat niet door", line)


if __name__ == "__main__":
    unittest.main()

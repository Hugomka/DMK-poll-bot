# tests/test_decision.py
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from apps.logic.decision import build_decision_line
from apps.utils.poll_settings import set_visibility
from apps.utils.poll_storage import save_votes
from tests.base import BaseTestCase

AMS = ZoneInfo("Europe/Amsterdam")
FRI = "vrijdag"
T19 = "om 19:00 uur"
T2030 = "om 20:30 uur"


class TestDecision(BaseTestCase):

    async def asyncSetUp(self):
        await super().asyncSetUp()

    async def _set_votes(self, mapping: dict):
        """
        mapping: dict[str_user_id] -> {"vrijdag": [tijd, ...]}
        Voorbeeld:
          {"1": {"vrijdag": ["om 20:30 uur"]}, ...}
        """
        await save_votes(mapping)

    def _dt(self, y, m, d, hh=12, mm=0):
        return datetime(y, m, d, hh, mm, tzinfo=AMS)

    async def test_before_deadline_shows_announcement(self):
        set_visibility(12345, FRI, modus="deadline", tijd="18:00")
        now = self._dt(2025, 8, 22, 17, 0)

        await self._set_votes({})
        line = await build_decision_line(12345, FRI, now)
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
        line = await build_decision_line(12345, FRI, now)
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
        line = await build_decision_line(12345, FRI, now)
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
        line = await build_decision_line(12345, FRI, now)
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
        line = await build_decision_line(12345, FRI, now)
        self.assertIsNotNone(line)
        assert line is not None
        self.assertIn("Gaat niet door", line)

    async def test_other_day_returns_none(self):
        # Donderdag 2025-08-21 → dag is niet vrijdag → None
        set_visibility(12345, FRI, modus="deadline", tijd="18:00")
        now = self._dt(2025, 8, 21, 12, 0)

        await self._set_votes({})
        line = await build_decision_line(12345, FRI, now)
        self.assertIsNone(line)


if __name__ == "__main__":
    unittest.main()

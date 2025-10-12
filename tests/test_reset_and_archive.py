# tests/test_reset_and_archive.py

import csv
import os
from datetime import datetime
from typing import cast
from unittest.mock import patch
from zoneinfo import ZoneInfo

from apps.utils import archive as ar
from apps.utils.poll_storage import get_votes_for_option, reset_votes, toggle_vote
from tests.base import BaseTestCase


class TestResetEnArchiefUitgebreid(BaseTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        # Schoon archief voor elke test
        if os.path.exists(ar.ARCHIVE_CSV):
            os.remove(ar.ARCHIVE_CSV)
        if os.path.isdir(ar.ARCHIVE_DIR):
            try:
                # Probeer lege map; als die nog bestaat is dat oké
                os.rmdir(ar.ARCHIVE_DIR)
            except OSError:
                pass

    async def test_reset_zet_stemmen_op_nul(self):
        user = "999"
        await toggle_vote(user, "vrijdag", "om 19:00 uur", 1, 123)
        await reset_votes()
        aantal = await get_votes_for_option("vrijdag", "om 19:00 uur", 1, 123)
        self.assertEqual(aantal, 0)

    async def test_append_week_snapshot_maakt_csv(self):
        await toggle_vote("abc", "vrijdag", "om 19:00 uur", 1, 123)
        await ar.append_week_snapshot_scoped(
            now=datetime.now(ZoneInfo("Europe/Amsterdam"))
        )
        self.assertTrue(ar.archive_exists_scoped())
        self.assertTrue(os.path.exists(ar.ARCHIVE_CSV))

    async def test_append_leeg_snapshot(self):
        await ar.append_week_snapshot_scoped(
            now=datetime.now(ZoneInfo("Europe/Amsterdam"))
        )
        self.assertTrue(ar.archive_exists_scoped())

    async def test_delete_archive_verwijdert_file(self):
        await ar.append_week_snapshot_scoped(
            now=datetime.now(ZoneInfo("Europe/Amsterdam"))
        )
        ok = ar.delete_archive_scoped()
        self.assertTrue(ok)
        self.assertFalse(os.path.exists(ar.ARCHIVE_CSV))

    async def test_week_dates_eu_localizes_naive_datetime(self):
        """Naive datetime → wordt gelokaliseerd (Europe/Amsterdam) in _week_dates_eu."""
        naive = datetime(2025, 9, 13, 12, 0, 0)  # tzinfo=None
        week, vr, za, zo = ar._week_dates_eu(naive)
        # Basisvorm controleren (strings YYYY-MM-DD en week als int)
        self.assertIsInstance(week, int)
        for d in (vr, za, zo):
            self.assertRegex(d, r"^\d{4}-\d{2}-\d{2}$")

    async def test_build_counts_skips_unknown_day_and_time(self):
        """
        _build_counts_from_votes:
        - onbekende dag → overslaan
        - onbekende tijd binnen geldige dag → overslaan
        """
        # Zorg dat DAGEN/VOLGORDE voorspelbaar zijn
        with patch.object(ar, "DAGEN", ["vrijdag", "zaterdag", "zondag"]), patch.object(
            ar,
            "VOLGORDE",
            ["om 19:00 uur", "om 20:30 uur", "misschien", "niet meedoen"],
        ):
            votes = {
                "u1": {
                    "maandag": ["om 19:00 uur"],  # Dag niet in telling → continue
                    "vrijdag": ["onbekend"],  # Tijd niet in telling[dag] → overslaan
                }
            }
            telling = ar._build_counts_from_votes(votes)
            # Alles 0 gebleven
            for dag in ["vrijdag", "zaterdag", "zondag"]:
                self.assertEqual(telling[dag]["om 19:00 uur"], 0)
                self.assertEqual(telling[dag]["om 20:30 uur"], 0)
                self.assertEqual(telling[dag]["misschien"], 0)
                self.assertEqual(telling[dag]["niet meedoen"], 0)

    async def test_append_twice_writes_header_once(self):
        """Eerste append schrijft header; tweede append schrijft géén header opnieuw."""
        # Eerste snapshot
        await ar.append_week_snapshot_scoped(
            now=datetime.now(ZoneInfo("Europe/Amsterdam"))
        )
        # Tweede snapshot
        await ar.append_week_snapshot_scoped(
            now=datetime.now(ZoneInfo("Europe/Amsterdam"))
        )

        self.assertTrue(os.path.exists(ar.ARCHIVE_CSV))
        with open(ar.ARCHIVE_CSV, "r", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        # Minimaal 3 regels: header + 2 data-rijen
        self.assertGreaterEqual(len(rows), 3)
        header = rows[0]
        self.assertIn("week", header)
        # 2e regel is data en mag niet gelijk zijn aan de header
        self.assertNotEqual(rows[1], header)

    async def test_open_archive_bytes_when_missing(self):
        """open_archive_bytes_scoped → (None, None) als archief ontbreekt."""
        # Zeker weten dat file weg is
        if os.path.exists(ar.ARCHIVE_CSV):
            os.remove(ar.ARCHIVE_CSV)
        name, data = ar.open_archive_bytes_scoped()
        self.assertIsNone(name)
        self.assertIsNone(data)

    async def test_delete_archive_when_missing_returns_false(self):
        """delete_archive_scoped → False als er niets te verwijderen valt."""
        if os.path.exists(ar.ARCHIVE_CSV):
            os.remove(ar.ARCHIVE_CSV)
        ok = ar.delete_archive_scoped()
        self.assertFalse(ok)

    async def test_build_counts_increments_known_time(self):
        """
        _build_counts_from_votes:
        - bekende dag én tijd → telling wordt verhoogd (dekt het inner-loop pad).
        """
        with patch.object(ar, "DAGEN", ["vrijdag"]), patch.object(
            ar,
            "VOLGORDE",
            ["om 19:00 uur", "om 20:30 uur", "misschien", "niet meedoen"],
        ):
            votes = {
                "u1": {"vrijdag": ["om 19:00 uur", "om 19:00 uur"]},
                "u2": {"vrijdag": ["om 19:00 uur"]},
            }
            telling = ar._build_counts_from_votes(votes)
            # 2 + 1 = 3 keer 'om 19:00 uur'
            self.assertEqual(telling["vrijdag"]["om 19:00 uur"], 3)
            # Andere tellers blijven 0
            self.assertEqual(telling["vrijdag"]["om 20:30 uur"], 0)
            self.assertEqual(telling["vrijdag"]["misschien"], 0)
            self.assertEqual(telling["vrijdag"]["niet meedoen"], 0)

    async def test_append_week_snapshot_uses_default_now(self):
        """
        append_week_snapshot_scoped zonder 'now' → gebruikt default Europe/Amsterdam now
        en schrijft het archief (dekt het now is None-pad).
        """
        # Zorg dat archief nog niet bestaat
        if os.path.exists(ar.ARCHIVE_CSV):
            os.remove(ar.ARCHIVE_CSV)

        await ar.append_week_snapshot_scoped()  # now=None → default pad
        self.assertTrue(ar.archive_exists_scoped())
        self.assertTrue(os.path.exists(ar.ARCHIVE_CSV))

    async def test_open_archive_bytes_returns_name_and_bytes(self):
        """
        open_archive_bytes als het archief bestaat → (naam, bytes).
        (dekt het open/read/return-pad)
        """
        # Maak zeker dat er een CSV is
        if not os.path.exists(ar.ARCHIVE_CSV):
            await ar.append_week_snapshot_scoped()

        name, data = ar.open_archive_bytes_scoped()
        self.assertEqual(name, "dmk_archive.csv")
        # Houd Pylance tevreden: assert en cast naar bytes
        self.assertIsNotNone(data)
        data_b = cast(bytes, data)

        self.assertGreater(len(data_b), 0)
        # optioneel: eerste bytes bevatten de header 'week'
        self.assertIn(b"week", data_b.splitlines()[0])

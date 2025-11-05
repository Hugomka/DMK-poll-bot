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
        # Basisvorm controleren (strings YYYY-MM-DD en week als ISO format YYYY-Www)
        self.assertIsInstance(week, str)
        self.assertRegex(week, r"^\d{4}-W\d{2}$")  # ISO week format: 2025-W37
        for d in (vr, za, zo):
            self.assertRegex(d, r"^\d{4}-\d{2}-\d{2}$")

    async def test_week_dates_eu_returns_upcoming_weekend(self):
        """Test dat _week_dates_eu aankomende weekend retourneert, niet vorige."""
        # Dinsdag 5 november 2025
        tuesday = datetime(2025, 11, 5, 14, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
        week, vr, za, zo = ar._week_dates_eu(tuesday)

        # Verwacht aankomend weekend: vrijdag 7, zaterdag 8, zondag 9 november
        self.assertEqual(vr, "2025-11-07")
        self.assertEqual(za, "2025-11-08")
        self.assertEqual(zo, "2025-11-09")
        self.assertEqual(week, "2025-W45")  # Week 45

    async def test_week_dates_eu_on_friday_returns_same_friday(self):
        """Test dat _week_dates_eu op vrijdag diezelfde vrijdag retourneert."""
        # Vrijdag 7 november 2025
        friday = datetime(2025, 11, 7, 10, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
        _, vr, za, zo = ar._week_dates_eu(friday)

        # Verwacht: vrijdag 7 (vandaag), zaterdag 8, zondag 9
        self.assertEqual(vr, "2025-11-07")
        self.assertEqual(za, "2025-11-08")
        self.assertEqual(zo, "2025-11-09")

    async def test_week_dates_eu_on_monday_returns_next_friday(self):
        """Test dat _week_dates_eu op maandag volgende vrijdag retourneert."""
        # Maandag 10 november 2025 (na het weekend)
        monday = datetime(2025, 11, 10, 9, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
        week, vr, za, zo = ar._week_dates_eu(monday)

        # Verwacht: vrijdag 14, zaterdag 15, zondag 16 november
        self.assertEqual(vr, "2025-11-14")
        self.assertEqual(za, "2025-11-15")
        self.assertEqual(zo, "2025-11-16")
        self.assertEqual(week, "2025-W46")

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
            telling = await ar._build_counts_from_votes(votes)
            # Alles 0 gebleven
            for dag in ["vrijdag", "zaterdag", "zondag"]:
                self.assertEqual(telling[dag]["om 19:00 uur"], 0)
                self.assertEqual(telling[dag]["om 20:30 uur"], 0)
                self.assertEqual(telling[dag]["misschien"], 0)
                self.assertEqual(telling[dag]["niet meedoen"], 0)

    async def test_append_twice_writes_header_once(self):
        """Eerste append schrijft header; tweede append van dezelfde week update de rij."""
        # Eerste snapshot
        await ar.append_week_snapshot_scoped(
            now=datetime.now(ZoneInfo("Europe/Amsterdam"))
        )
        # Tweede snapshot (zelfde week → update bestaande rij)
        await ar.append_week_snapshot_scoped(
            now=datetime.now(ZoneInfo("Europe/Amsterdam"))
        )

        self.assertTrue(os.path.exists(ar.ARCHIVE_CSV))
        with open(ar.ARCHIVE_CSV, "r", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        # Precies 2 regels: header + 1 data-rij (tweede append update dezelfde week)
        self.assertEqual(len(rows), 2)
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
            telling = await ar._build_counts_from_votes(votes)
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

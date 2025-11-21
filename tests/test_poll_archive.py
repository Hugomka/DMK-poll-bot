# tests/test_poll_archive.py
"""
Tests voor poll_archive.py om coverage te verhogen van 52% naar 80%+
"""

import os
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

from apps.commands.poll_archive import PollArchive
from tests.base import BaseTestCase


def _mk_interaction(channel: Any = None, guild: Any = None) -> Any:
    """Maakt een interaction-mock met response.defer en followup.send."""
    interaction = MagicMock()
    interaction.channel = channel
    interaction.guild = guild
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    return interaction


class TestPollArchive(BaseTestCase):
    """Tests voor /dmk-poll-archief command"""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bot = MagicMock()
        self.cog = PollArchive(self.bot)

    async def _run(self, cmd, *args, **kwargs):
        """Roept een app_commands.Command aan via .callback(cog, ...)."""
        cb = getattr(cmd, "callback", None)
        if cb is not None:
            owner = getattr(cmd, "binding", None)
            if owner is None:
                owner = getattr(self, "cog", None)
            return await cb(owner, *args, **kwargs)
        return await cast(Any, cmd)(*args, **kwargs)

    def _last_content(self, mock_send) -> str:
        """Haal 'content' op uit kwargs of uit de eerste positionele arg."""
        if not mock_send.called:
            return ""
        args, kwargs = mock_send.call_args
        if "content" in kwargs and kwargs["content"] is not None:
            return kwargs["content"]
        if args and isinstance(args[0], str):
            return args[0]
        return ""

    async def test_archief_no_channel_returns_error(self):
        """Test dat command error geeft als er geen kanaal is"""
        interaction = _mk_interaction(channel=None)

        await self._run(self.cog.archief, interaction)

        interaction.followup.send.assert_awaited_once()
        content = self._last_content(interaction.followup.send)
        assert "Geen kanaal" in content

    async def test_archief_no_archive_exists(self):
        """Test dat melding komt als archief niet bestaat"""
        channel = MagicMock()
        channel.id = 123
        guild = MagicMock()
        guild.id = 456
        interaction = _mk_interaction(channel=channel, guild=guild)

        with patch("apps.commands.poll_archive.archive_exists_scoped", return_value=False):
            await self._run(self.cog.archief, interaction)

        interaction.followup.send.assert_awaited_once()
        content = self._last_content(interaction.followup.send)
        assert "geen archief" in content.lower()

    async def test_archief_success_with_view(self):
        """Test dat archief tonen werkt met ArchiveView (nieuwe methode)"""
        channel = MagicMock()
        channel.id = 123
        guild = MagicMock()
        guild.id = 456
        interaction = _mk_interaction(channel=channel, guild=guild)

        csv_data = b"week,datum\n1,2024-01-01"

        with patch(
            "apps.commands.poll_archive.archive_exists_scoped", return_value=True
        ), patch(
            "apps.commands.poll_archive.ArchiveView"
        ) as mock_view_class, patch(
            "apps.commands.poll_archive.create_archive", return_value=csv_data
        ):
            mock_view = MagicMock()
            mock_view.selected_delimiter = ","
            mock_view_class.return_value = mock_view

            await self._run(self.cog.archief, interaction)

        # View moet zijn aangemaakt met juiste parameters
        mock_view_class.assert_called_once_with(456, 123)

        # Followup moet zijn aangeroepen met file en view
        interaction.followup.send.assert_awaited_once()
        args, kwargs = interaction.followup.send.call_args

        # Check content bevat beschrijvende tekst
        content = kwargs.get("content", "")
        assert "DMK Poll Archief" in content
        assert "CSV-formaat" in content
        assert "Verwijder archief" in content

        # Check file parameter
        assert "file" in kwargs

        # Check view parameter
        assert "view" in kwargs
        assert kwargs["view"] == mock_view

        # Check ephemeral is True
        assert kwargs.get("ephemeral") is True

    async def test_archief_success_without_view(self):
        """Test dat archief tonen werkt zonder ArchiveView (fallback)"""
        channel = MagicMock()
        channel.id = 123
        guild = MagicMock()
        guild.id = 456
        interaction = _mk_interaction(channel=channel, guild=guild)

        archive_data = b"week,ja,nee,misschien\n2024-01,5,2,3\n"

        with patch(
            "apps.commands.poll_archive.archive_exists_scoped", return_value=True
        ), patch(
            "apps.commands.poll_archive.open_archive_bytes_scoped",
            return_value=("archive.csv", archive_data),
        ), patch("apps.commands.poll_archive.ArchiveView", None):
            # ArchiveView is None (not available)

            await self._run(self.cog.archief, interaction)

        # Followup moet zijn aangeroepen met alleen file (geen view)
        interaction.followup.send.assert_awaited_once()
        _, kwargs = interaction.followup.send.call_args

        # Check content
        content = kwargs.get("content", "")
        assert "CSV-archief" in content

        # Check file parameter
        assert "file" in kwargs
        file_obj = kwargs["file"]
        assert file_obj.filename == "archive.csv"

        # Check ephemeral is True
        assert kwargs.get("ephemeral") is True

        # Check view NIET aanwezig
        assert "view" not in kwargs

    async def test_archief_with_channel_without_guild(self):
        """Test dat guild correct wordt bepaald via channel"""
        channel = MagicMock()
        channel.id = 123
        channel.guild = MagicMock()
        channel.guild.id = 789
        interaction = _mk_interaction(channel=channel, guild=None)

        archive_data = b"week,ja,nee,misschien\n2024-01,5,2,3\n"

        with patch(
            "apps.commands.poll_archive.archive_exists_scoped", return_value=True
        ) as mock_exists, patch(
            "apps.commands.poll_archive.open_archive_bytes_scoped",
            return_value=("archive.csv", archive_data),
        ), patch("apps.commands.poll_archive.ArchiveView", None):
            await self._run(self.cog.archief, interaction)

        # archive_exists_scoped moet aangeroepen zijn met guild.id van channel
        mock_exists.assert_called_once_with(789, 123)


class TestPollArchiveSetup(BaseTestCase):
    """Tests voor setup functie"""

    async def test_setup_adds_cog(self):
        """Test dat setup de PollArchive cog toevoegt"""
        bot = MagicMock()
        bot.add_cog = AsyncMock()

        from apps.commands.poll_archive import setup

        await setup(bot)

        bot.add_cog.assert_awaited_once()
        args, _ = bot.add_cog.call_args
        assert isinstance(args[0], PollArchive)


class TestArchiveDelimiterFunctionality(BaseTestCase):
    """Tests voor nieuwe delimiter functionaliteit in archive.py"""

    def setUp(self):
        """Setup test archief"""
        from apps.utils.archive import ARCHIVE_DIR

        import os

        os.makedirs(ARCHIVE_DIR, exist_ok=True)
        self.test_csv_path = os.path.join(ARCHIVE_DIR, "dmk_archive_123_456.csv")

        # Maak test CSV aan
        with open(self.test_csv_path, "w", encoding="utf-8") as f:
            f.write("week,datum_vrijdag,datum_zaterdag,datum_zondag,vr_19,vr_2030\n")
            f.write("1,2024-01-05,2024-01-06,2024-01-07,5,3\n")
            f.write("2,2024-01-12,2024-01-13,2024-01-14,7,2\n")

    def tearDown(self):
        """Cleanup test bestanden"""
        import os

        if os.path.exists(self.test_csv_path):
            os.remove(self.test_csv_path)

    def test_create_archive_with_comma_delimiter(self):
        """Test dat create_archive werkt met comma delimiter"""
        from apps.utils.archive import create_archive

        result = create_archive(123, 456, delimiter=",")

        assert result is not None
        result_str = result.decode("utf-8")

        # Check dat komma's aanwezig zijn
        assert ",2024-01-05," in result_str
        assert "week,datum_vrijdag" in result_str

    def test_create_archive_with_semicolon_delimiter(self):
        """Test dat create_archive werkt met semicolon delimiter"""
        from apps.utils.archive import create_archive

        result = create_archive(123, 456, delimiter=";")

        assert result is not None
        result_str = result.decode("utf-8")

        # Check dat puntkomma's aanwezig zijn
        assert ";2024-01-05;" in result_str
        assert "week;datum_vrijdag" in result_str

        # Check dat GEEN komma's aanwezig zijn (behalve eventueel in data)
        lines = result_str.split("\n")
        for line in lines:
            if line:
                # Elke regel moet semicolons hebben als delimiter
                assert ";" in line

    def test_generate_csv_preview_with_comma(self):
        """Test dat generate_csv_preview werkt met comma delimiter"""
        from apps.utils.archive import generate_csv_preview

        preview = generate_csv_preview(123, 456, delimiter=",", max_lines=2)

        assert "week,datum_vrijdag" in preview
        assert "1,2024-01-05" in preview

        # Moet maximaal 2 regels zijn
        lines = preview.split("\n")
        assert len(lines) == 2

    def test_generate_csv_preview_with_semicolon(self):
        """Test dat generate_csv_preview werkt met semicolon delimiter"""
        from apps.utils.archive import generate_csv_preview

        preview = generate_csv_preview(123, 456, delimiter=";", max_lines=3)

        assert "week;datum_vrijdag" in preview
        assert "1;2024-01-05" in preview

        # Moet maximaal 3 regels zijn
        lines = preview.split("\n")
        assert len(lines) == 3

    def test_generate_csv_preview_nonexistent_archive(self):
        """Test dat generate_csv_preview correct werkt als archief niet bestaat"""
        from apps.utils.archive import generate_csv_preview

        preview = generate_csv_preview(999, 999, delimiter=",")

        assert "Geen archief beschikbaar" in preview

    def test_create_archive_nonexistent_returns_none(self):
        """Test dat create_archive None returned als archief niet bestaat"""
        from apps.utils.archive import create_archive

        result = create_archive(999, 999, delimiter=",")

        assert result is None


class TestArchiveView(BaseTestCase):
    """Tests voor ArchiveView UI componenten"""

    async def test_archive_view_initialization(self):
        """Test dat ArchiveView correct wordt geïnitialiseerd"""
        from apps.ui.archive_view import ArchiveView

        view = ArchiveView(guild_id=123, channel_id=456)

        assert view.guild_id == 123
        assert view.channel_id == 456
        assert view.selected_delimiter == ","  # Default

        # Check dat alle componenten zijn toegevoegd
        assert len(view.children) == 2  # SelectMenu, Delete button (geen Download button)

    async def test_delimiter_select_menu_callback_updates_file(self):
        """Test dat delimiter selectie direct het CSV bestand update"""
        from unittest.mock import PropertyMock
        from apps.ui.archive_view import ArchiveView, DelimiterSelectMenu

        view = ArchiveView(guild_id=123, channel_id=456)
        select_menu = None

        # Vind de SelectMenu
        for child in view.children:
            if isinstance(child, DelimiterSelectMenu):
                select_menu = child
                break

        assert select_menu is not None

        # Mock interaction
        interaction = MagicMock()
        interaction.response.edit_message = AsyncMock()

        csv_data = b"week;datum\n1;2024-01-01"

        # Roep callback aan met gemockte values
        with patch("apps.ui.archive_view.create_archive", return_value=csv_data), \
             patch.object(type(select_menu), "values", new_callable=PropertyMock, return_value=[";"]):
            await select_menu.callback(interaction)

        # Check dat delimiter is gewijzigd
        assert view.selected_delimiter == ";"

        # Check dat message is geüpdatet met nieuw bestand
        interaction.response.edit_message.assert_awaited_once()
        _, kwargs = interaction.response.edit_message.call_args

        # Check content bevat beschrijvende tekst
        content = kwargs.get("content", "")
        assert "DMK Poll Archief" in content
        assert "CSV-formaat" in content

        # Check dat attachments bevat een File
        assert "attachments" in kwargs
        assert len(kwargs["attachments"]) == 1

        # Check view is meegestuurd
        assert "view" in kwargs
        assert kwargs["view"] == view

    async def test_delimiter_select_menu_callback_failure(self):
        """Test dat delimiter selectie foutmelding geeft als genereren faalt"""
        from unittest.mock import PropertyMock
        from apps.ui.archive_view import ArchiveView, DelimiterSelectMenu

        view = ArchiveView(guild_id=123, channel_id=456)
        select_menu = None

        # Vind de SelectMenu
        for child in view.children:
            if isinstance(child, DelimiterSelectMenu):
                select_menu = child
                break

        assert select_menu is not None

        # Mock interaction
        interaction = MagicMock()
        interaction.response.send_message = AsyncMock()

        # Roep callback aan met None return (fout)
        with patch("apps.ui.archive_view.create_archive", return_value=None), \
             patch.object(type(select_menu), "values", new_callable=PropertyMock, return_value=[";"]):
            await select_menu.callback(interaction)

        # Check dat error message is verzonden
        interaction.response.send_message.assert_awaited_once()
        args, kwargs = interaction.response.send_message.call_args

        content = args[0] if args else ""
        assert "Kon archief niet genereren" in content
        assert kwargs["ephemeral"] is True


class TestArchiveWithNonVoters(BaseTestCase):
    """Tests voor niet-stemmers in CSV archief"""

    async def test_append_week_snapshot_includes_non_voters_columns(self):
        """Test dat CSV niet-stemmers kolommen bevat in header"""
        from apps.utils.archive import append_week_snapshot_scoped, get_archive_path_scoped
        import os

        guild_id = 789
        channel_id = 654
        csv_path = get_archive_path_scoped(guild_id, channel_id)

        # Cleanup als bestand al bestaat
        if os.path.exists(csv_path):
            os.remove(csv_path)

        try:
            # Append zonder channel (niet-stemmers zullen 0 zijn)
            await append_week_snapshot_scoped(guild_id, channel_id, channel=None)

            # Lees CSV en check header
            with open(csv_path, "r", encoding="utf-8") as f:
                header = f.readline().strip()

            # Check dat niet-stemmers kolommen aanwezig zijn
            assert "vr_niet_gestemd" in header
            assert "za_niet_gestemd" in header
            assert "zo_niet_gestemd" in header

            # Check volgorde: na elke dag moet niet_gestemd komen
            columns = header.split(",")
            assert "vr_niet_gestemd" in columns
            assert "za_niet_gestemd" in columns
            assert "zo_niet_gestemd" in columns

        finally:
            # Cleanup
            if os.path.exists(csv_path):
                os.remove(csv_path)

    async def test_append_week_snapshot_with_channel_counts_non_voters(self):
        """Test dat niet-stemmers correct worden geteld met channel"""
        from apps.utils.archive import append_week_snapshot_scoped, get_archive_path_scoped
        from types import SimpleNamespace
        import os

        guild_id = 111
        channel_id = 222
        csv_path = get_archive_path_scoped(guild_id, channel_id)

        # Cleanup als bestand al bestaat
        if os.path.exists(csv_path):
            os.remove(csv_path)

        try:
            # Mock channel met 3 leden
            mock_member1 = SimpleNamespace(id=123, bot=False)
            mock_member2 = SimpleNamespace(id=456, bot=False)
            mock_member3 = SimpleNamespace(id=789, bot=False)
            mock_channel = SimpleNamespace(members=[mock_member1, mock_member2, mock_member3])

            # Mock stemmen: alleen lid 123 heeft gestemd voor vrijdag
            with patch("apps.utils.archive.load_votes", return_value={
                "123": {"vrijdag": ["om 19:00 uur"]},
            }):
                await append_week_snapshot_scoped(guild_id, channel_id, channel=mock_channel)

            # Lees CSV en check data row
            with open(csv_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Should have header + 1 data row
            assert len(lines) == 2

            header = lines[0].strip().split(",")
            data = lines[1].strip().split(",")

            # Vind indices van niet_gestemd kolommen
            vr_idx = header.index("vr_niet_gestemd")
            za_idx = header.index("za_niet_gestemd")
            zo_idx = header.index("zo_niet_gestemd")

            # Check waarden: vrijdag heeft 2 niet-stemmers (3 leden - 1 stemmer)
            #                zaterdag en zondag hebben 3 niet-stemmers (niemand heeft gestemd)
            assert data[vr_idx] == "2"
            assert data[za_idx] == "3"
            assert data[zo_idx] == "3"

        finally:
            # Cleanup
            if os.path.exists(csv_path):
                os.remove(csv_path)

    async def test_append_week_snapshot_without_channel_shows_zero_non_voters(self):
        """Test dat niet-stemmers 0 zijn zonder channel"""
        from apps.utils.archive import append_week_snapshot_scoped, get_archive_path_scoped
        import os

        guild_id = 333
        channel_id = 444
        csv_path = get_archive_path_scoped(guild_id, channel_id)

        # Cleanup als bestand al bestaat
        if os.path.exists(csv_path):
            os.remove(csv_path)

        try:
            # Append zonder channel
            await append_week_snapshot_scoped(guild_id, channel_id, channel=None)

            # Lees CSV en check data row
            with open(csv_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            header = lines[0].strip().split(",")
            data = lines[1].strip().split(",")

            # Vind indices van niet_gestemd kolommen
            vr_idx = header.index("vr_niet_gestemd")
            za_idx = header.index("za_niet_gestemd")
            zo_idx = header.index("zo_niet_gestemd")

            # Check dat alle niet-stemmers waarden 0 zijn
            assert data[vr_idx] == "0"
            assert data[za_idx] == "0"
            assert data[zo_idx] == "0"

        finally:
            # Cleanup
            if os.path.exists(csv_path):
                os.remove(csv_path)

    async def test_append_migrates_old_csv_header(self):
        """Test dat oude CSV bestanden automatisch gemigreerd worden naar nieuwe header"""
        from apps.utils.archive import append_week_snapshot_scoped, get_archive_path_scoped
        import os

        guild_id = 555
        channel_id = 666
        csv_path = get_archive_path_scoped(guild_id, channel_id)

        # Cleanup als bestand al bestaat
        if os.path.exists(csv_path):
            os.remove(csv_path)

        try:
            # Maak een oud CSV bestand aan (zonder niet_gestemd kolommen)
            old_header = "week,datum_vrijdag,datum_zaterdag,datum_zondag,vr_19,vr_2030,vr_misschien,vr_niet,za_19,za_2030,za_misschien,za_niet,zo_19,zo_2030,zo_misschien,zo_niet"
            old_data = "41,2025-10-10,2025-10-11,2025-10-12,1,3,0,0,1,3,0,0,2,2,0,0"

            with open(csv_path, "w", encoding="utf-8") as f:
                f.write(old_header + "\n")
                f.write(old_data + "\n")

            # Append nieuwe week (dit zou header moeten migreren)
            await append_week_snapshot_scoped(guild_id, channel_id, channel=None)

            # Lees CSV en check
            with open(csv_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Check dat header is gemigreerd
            new_header = lines[0].strip()
            assert "vr_niet_gestemd" in new_header
            assert "za_niet_gestemd" in new_header
            assert "zo_niet_gestemd" in new_header
            assert "vr_was_misschien" in new_header
            assert "za_was_misschien" in new_header
            assert "zo_was_misschien" in new_header

            # Check dat oude data rij is gemigreerd met nieuwe kolommen (niet_gestemd en was_misschien = empty)
            # Oude: 41,2025-10-10,2025-10-11,2025-10-12,1,3,0,0,1,3,0,0,2,2,0,0 (16 kolommen)
            # Nieuw: 41,2025-10-10,2025-10-11,2025-10-12,1,3,0,,0,,1,3,0,,0,,2,2,0,,0, (22 kolommen)
            migrated_old_row = lines[1].strip().split(",")
            assert len(migrated_old_row) == 22, f"Migrated row should have 22 columns, got {len(migrated_old_row)}"
            assert migrated_old_row[0] == "41"  # week preserved
            assert migrated_old_row[4] == "1"   # vr_19 preserved
            assert migrated_old_row[7] == ""    # vr_was_misschien added (empty = data not tracked)
            assert migrated_old_row[9] == ""    # vr_niet_gestemd added (empty = data not tracked)
            assert migrated_old_row[13] == ""   # za_was_misschien added (empty = data not tracked)
            assert migrated_old_row[15] == ""   # za_niet_gestemd added (empty = data not tracked)
            assert migrated_old_row[19] == ""   # zo_was_misschien added (empty = data not tracked)
            assert migrated_old_row[21] == ""   # zo_niet_gestemd added (empty = data not tracked)

            # Check dat nieuwe rij volledige data heeft (22 kolommen)
            new_data_row = lines[2].strip().split(",")
            assert len(new_data_row) == 22  # 4 datum kolommen + 18 data kolommen (6 per dag)

        finally:
            # Cleanup
            if os.path.exists(csv_path):
                os.remove(csv_path)


class TestWeekdayArchive(BaseTestCase):
    """Tests voor weekday archive functionaliteit (dual archive systeem)"""

    async def test_weekday_archive_created_when_weekday_enabled(self):
        """Test dat weekday archief wordt aangemaakt als weekday polls ingeschakeld zijn"""
        from apps.utils.archive import append_week_snapshot_scoped, get_archive_path_scoped
        from datetime import datetime
        import pytz
        import csv

        # Setup: enable maandag poll
        with patch("apps.utils.poll_settings.get_enabled_poll_days", return_value=["maandag", "vrijdag"]):
            now = datetime(2025, 11, 22, 10, 0, tzinfo=pytz.timezone("Europe/Amsterdam"))

            await append_week_snapshot_scoped(
                guild_id=123,
                channel_id=456,
                now=now,
                channel=None
            )

            # Check dat weekend archief bestaat
            weekend_path = get_archive_path_scoped(123, 456, weekday=False)
            assert os.path.exists(weekend_path), "Weekend archief moet bestaan"

            # Check dat weekday archief bestaat
            weekday_path = get_archive_path_scoped(123, 456, weekday=True)
            assert os.path.exists(weekday_path), "Weekday archief moet bestaan"

            # Verify weekday CSV structure
            with open(weekday_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = list(reader)

            assert len(rows) == 2, "Weekday CSV moet header + 1 data rij hebben"

            header = rows[0]
            assert header[0] == "week"
            assert header[1] == "datum_maandag"
            assert header[2] == "datum_dinsdag"
            assert header[3] == "datum_woensdag"
            assert header[4] == "datum_donderdag"
            assert "ma_19" in header
            assert "di_19" in header
            assert "wo_19" in header
            assert "do_19" in header

            # Cleanup
            if os.path.exists(weekend_path):
                os.remove(weekend_path)
            if os.path.exists(weekday_path):
                os.remove(weekday_path)

    async def test_weekday_archive_not_created_when_weekday_disabled(self):
        """Test dat weekday archief NIET wordt aangemaakt als alleen weekend polls ingeschakeld zijn"""
        from apps.utils.archive import append_week_snapshot_scoped, get_archive_path_scoped
        from datetime import datetime
        import pytz

        # Setup: only weekend days enabled
        with patch("apps.utils.poll_settings.get_enabled_poll_days", return_value=["vrijdag", "zaterdag", "zondag"]):
            now = datetime(2025, 11, 22, 10, 0, tzinfo=pytz.timezone("Europe/Amsterdam"))

            await append_week_snapshot_scoped(
                guild_id=123,
                channel_id=456,
                now=now,
                channel=None
            )

            # Check dat weekend archief bestaat
            weekend_path = get_archive_path_scoped(123, 456, weekday=False)
            assert os.path.exists(weekend_path), "Weekend archief moet bestaan"

            # Check dat weekday archief NIET bestaat
            weekday_path = get_archive_path_scoped(123, 456, weekday=True)
            assert not os.path.exists(weekday_path), "Weekday archief mag niet bestaan"

            # Cleanup
            if os.path.exists(weekend_path):
                os.remove(weekend_path)

    async def test_week_dates_weekdays_calculates_correct_dates(self):
        """Test dat _week_dates_weekdays correct de maandag-donderdag datums berekent"""
        from apps.utils.archive import _week_dates_weekdays
        from datetime import datetime
        import pytz

        # Test: vrijdag 21 november → vorige maandag t/m donderdag (18-21 nov)
        now = datetime(2025, 11, 21, 10, 0, tzinfo=pytz.timezone("Europe/Amsterdam"))
        week, ma, di, wo, do = _week_dates_weekdays(now)

        assert week == "2025-W47"
        assert ma == "2025-11-17"  # Vorige maandag
        assert di == "2025-11-18"
        assert wo == "2025-11-19"
        assert do == "2025-11-20"

    async def test_week_dates_weekdays_on_monday_goes_back_week(self):
        """Test dat op maandag zelf terug wordt gegaan naar vorige maandag"""
        from apps.utils.archive import _week_dates_weekdays
        from datetime import datetime
        import pytz

        # Test: maandag 17 november → vorige maandag (10 nov)
        now = datetime(2025, 11, 17, 10, 0, tzinfo=pytz.timezone("Europe/Amsterdam"))
        week, ma, di, wo, do = _week_dates_weekdays(now)

        assert week == "2025-W46"
        assert ma == "2025-11-10"  # Vorige week maandag
        assert di == "2025-11-11"
        assert wo == "2025-11-12"
        assert do == "2025-11-13"

    async def test_weekday_archive_path_has_suffix(self):
        """Test dat weekday archief pad correct _weekdays suffix heeft"""
        from apps.utils.archive import get_archive_path_scoped

        weekend_path = get_archive_path_scoped(123, 456, weekday=False)
        weekday_path = get_archive_path_scoped(123, 456, weekday=True)

        assert weekend_path.endswith("dmk_archive_123_456.csv")
        assert weekday_path.endswith("dmk_archive_123_456_weekdays.csv")
        assert weekend_path != weekday_path

    async def test_weekday_archive_contains_all_four_days_data(self):
        """Test dat weekday archief data voor alle 4 weekdagen bevat"""
        from apps.utils.archive import append_week_snapshot_scoped, get_archive_path_scoped
        from apps.utils.poll_storage import toggle_vote
        from datetime import datetime
        import pytz
        import csv

        # Setup: vote for maandag
        await toggle_vote("user1", "maandag", "om 19:00 uur", 123, 456)
        await toggle_vote("user2", "dinsdag", "om 20:30 uur", 123, 456)
        await toggle_vote("user3", "woensdag", "misschien", 123, 456)
        await toggle_vote("user4", "donderdag", "niet meedoen", 123, 456)

        with patch("apps.utils.poll_settings.get_enabled_poll_days", return_value=["maandag", "dinsdag", "woensdag", "donderdag"]):
            now = datetime(2025, 11, 22, 10, 0, tzinfo=pytz.timezone("Europe/Amsterdam"))

            await append_week_snapshot_scoped(
                guild_id=123,
                channel_id=456,
                now=now,
                channel=None
            )

            weekday_path = get_archive_path_scoped(123, 456, weekday=True)

            with open(weekday_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = list(reader)

            header = rows[0]
            data_row = rows[1]

            # Find column indices
            ma_19_idx = header.index("ma_19")
            di_2030_idx = header.index("di_2030")
            wo_misschien_idx = header.index("wo_misschien")
            do_niet_idx = header.index("do_niet")

            # Verify data
            assert data_row[ma_19_idx] == "1", "Maandag 19:00 moet 1 stem hebben"
            assert data_row[di_2030_idx] == "1", "Dinsdag 20:30 moet 1 stem hebben"
            assert data_row[wo_misschien_idx] == "1", "Woensdag misschien moet 1 stem hebben"
            assert data_row[do_niet_idx] == "1", "Donderdag niet meedoen moet 1 stem hebben"

            # Cleanup
            if os.path.exists(weekday_path):
                os.remove(weekday_path)
            weekend_path = get_archive_path_scoped(123, 456, weekday=False)
            if os.path.exists(weekend_path):
                os.remove(weekend_path)

    async def test_weekday_archive_updates_existing_week(self):
        """Test dat weekday archief bestaande week update in plaats van nieuwe rij toe te voegen"""
        from apps.utils.archive import append_week_snapshot_scoped, get_archive_path_scoped
        from datetime import datetime
        import pytz
        import csv

        with patch("apps.utils.poll_settings.get_enabled_poll_days", return_value=["maandag"]):
            now = datetime(2025, 11, 22, 10, 0, tzinfo=pytz.timezone("Europe/Amsterdam"))

            # Eerste archivering
            await append_week_snapshot_scoped(123, 456, now, None)

            weekday_path = get_archive_path_scoped(123, 456, weekday=True)

            with open(weekday_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows_before = list(reader)

            assert len(rows_before) == 2, "Moet header + 1 data rij hebben"

            # Tweede archivering (zelfde week)
            await append_week_snapshot_scoped(123, 456, now, None)

            with open(weekday_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows_after = list(reader)

            assert len(rows_after) == 2, "Moet nog steeds header + 1 data rij hebben (geen duplicate)"

            # Cleanup
            if os.path.exists(weekday_path):
                os.remove(weekday_path)
            weekend_path = get_archive_path_scoped(123, 456, weekday=False)
            if os.path.exists(weekend_path):
                os.remove(weekend_path)


if __name__ == "__main__":
    import unittest

    unittest.main()

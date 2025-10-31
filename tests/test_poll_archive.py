# tests/test_poll_archive.py
"""
Tests voor poll_archive.py om coverage te verhogen van 52% naar 80%+
"""

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
        assert "verwijder-knop" in content

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


if __name__ == "__main__":
    import unittest

    unittest.main()

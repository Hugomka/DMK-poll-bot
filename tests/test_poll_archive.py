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


class TestPollArchiveDownload(BaseTestCase):
    """Tests voor /dmk-poll-archief-download command"""

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

    async def test_archief_download_no_channel_returns_error(self):
        """Test dat command error geeft als er geen kanaal is"""
        interaction = _mk_interaction(channel=None)

        await self._run(self.cog.archief_download, interaction)

        interaction.followup.send.assert_awaited_once()
        content = self._last_content(interaction.followup.send)
        assert "Geen kanaal" in content

    async def test_archief_download_no_archive_exists(self):
        """Test dat melding komt als archief niet bestaat"""
        channel = MagicMock()
        channel.id = 123
        guild = MagicMock()
        guild.id = 456
        interaction = _mk_interaction(channel=channel, guild=guild)

        with patch("apps.commands.poll_archive.archive_exists_scoped", return_value=False):
            await self._run(self.cog.archief_download, interaction)

        interaction.followup.send.assert_awaited_once()
        content = self._last_content(interaction.followup.send)
        assert "geen archief" in content.lower()

    async def test_archief_download_empty_data(self):
        """Test dat melding komt als archief niet kan worden gelezen"""
        channel = MagicMock()
        channel.id = 123
        guild = MagicMock()
        guild.id = 456
        interaction = _mk_interaction(channel=channel, guild=guild)

        with patch(
            "apps.commands.poll_archive.archive_exists_scoped", return_value=True
        ), patch(
            "apps.commands.poll_archive.open_archive_bytes_scoped",
            return_value=("archive.csv", b""),
        ):
            await self._run(self.cog.archief_download, interaction)

        interaction.followup.send.assert_awaited_once()
        content = self._last_content(interaction.followup.send)
        assert "kon niet worden gelezen" in content.lower()

    async def test_archief_download_success_with_view(self):
        """Test dat archief downloaden werkt met ArchiveDeleteView"""
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
        ), patch(
            "apps.commands.poll_archive.ArchiveDeleteView"
        ) as mock_view_class:
            # Mock view instance
            mock_view = MagicMock()
            mock_view_class.return_value = mock_view

            await self._run(self.cog.archief_download, interaction)

        # View moet zijn aangemaakt met juiste parameters
        mock_view_class.assert_called_once_with(456, 123)

        # Followup moet zijn aangeroepen met file en view
        interaction.followup.send.assert_awaited_once()
        args, kwargs = interaction.followup.send.call_args

        # Check content
        content = args[0] if args else kwargs.get("content", "")
        assert "CSV-archief" in content
        assert "verwijderen" in content.lower()

        # Check file parameter
        assert "file" in kwargs
        file_obj = kwargs["file"]
        assert file_obj.filename == "archive.csv"

        # Check view parameter
        assert "view" in kwargs
        assert kwargs["view"] == mock_view

    async def test_archief_download_success_without_view(self):
        """Test dat archief downloaden werkt zonder ArchiveDeleteView (fallback)"""
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
        ), patch("apps.commands.poll_archive.ArchiveDeleteView", None):
            # ArchiveDeleteView is None (not available)

            await self._run(self.cog.archief_download, interaction)

        # Followup moet zijn aangeroepen met alleen file (geen view)
        interaction.followup.send.assert_awaited_once()
        args, kwargs = interaction.followup.send.call_args

        # Check content
        content = kwargs.get("content", "")
        assert "CSV-archief" in content
        assert "verwijderen" not in content.lower()  # Geen delete optie

        # Check file parameter
        assert "file" in kwargs
        file_obj = kwargs["file"]
        assert file_obj.filename == "archive.csv"

        # Check view NIET aanwezig
        assert "view" not in kwargs

    async def test_archief_download_with_channel_without_guild(self):
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
        ):
            await self._run(self.cog.archief_download, interaction)

        # archive_exists_scoped moet aangeroepen zijn met guild.id van channel
        mock_exists.assert_called_once_with(789, 123)


class TestPollArchiveVerwijderen(BaseTestCase):
    """Tests voor /dmk-poll-archief-verwijderen command"""

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

    async def test_archief_verwijderen_no_channel_returns_error(self):
        """Test dat command error geeft als er geen kanaal is"""
        interaction = _mk_interaction(channel=None)

        await self._run(self.cog.archief_verwijderen, interaction)

        interaction.followup.send.assert_awaited_once()
        content = self._last_content(interaction.followup.send)
        assert "Geen kanaal" in content

    async def test_archief_verwijderen_success(self):
        """Test dat archief verwijderen werkt en success melding geeft"""
        channel = MagicMock()
        channel.id = 123
        guild = MagicMock()
        guild.id = 456
        interaction = _mk_interaction(channel=channel, guild=guild)

        with patch(
            "apps.commands.poll_archive.delete_archive_scoped", return_value=True
        ) as mock_delete:
            await self._run(self.cog.archief_verwijderen, interaction)

        # delete_archive_scoped moet zijn aangeroepen
        mock_delete.assert_called_once_with(456, 123)

        # Moet success melding geven
        interaction.followup.send.assert_awaited_once()
        content = self._last_content(interaction.followup.send)
        assert "verwijderd" in content.lower()
        assert "✅" in content

    async def test_archief_verwijderen_no_archive(self):
        """Test dat melding komt als er geen archief was om te verwijderen"""
        channel = MagicMock()
        channel.id = 123
        guild = MagicMock()
        guild.id = 456
        interaction = _mk_interaction(channel=channel, guild=guild)

        with patch(
            "apps.commands.poll_archive.delete_archive_scoped", return_value=False
        ):
            await self._run(self.cog.archief_verwijderen, interaction)

        # Moet melding geven dat er geen archief was
        interaction.followup.send.assert_awaited_once()
        content = self._last_content(interaction.followup.send)
        assert "geen archief" in content.lower()
        assert "verwijderen" in content.lower()

    async def test_archief_verwijderen_with_channel_without_guild(self):
        """Test dat guild correct wordt bepaald via channel"""
        channel = MagicMock()
        channel.id = 123
        channel.guild = MagicMock()
        channel.guild.id = 789
        interaction = _mk_interaction(channel=channel, guild=None)

        with patch(
            "apps.commands.poll_archive.delete_archive_scoped", return_value=True
        ) as mock_delete:
            await self._run(self.cog.archief_verwijderen, interaction)

        # delete_archive_scoped moet aangeroepen zijn met guild.id van channel
        mock_delete.assert_called_once_with(789, 123)


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


if __name__ == "__main__":
    import unittest

    unittest.main()

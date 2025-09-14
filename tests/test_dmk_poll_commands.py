# tests/test_dmk_poll_commands.py

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

from apps.commands.dmk_poll import DMKPoll
from tests.base import BaseTestCase


def _mk_interaction(channel: Any = None, admin: bool = True, guild: Any = None):
    """Maakt een interaction-mock met response.defer en followup.send."""
    interaction = MagicMock()
    interaction.channel = channel
    interaction.guild = guild or getattr(channel, "guild", None)
    interaction.user = MagicMock()
    if admin:
        interaction.user.guild_permissions.administrator = True
    else:
        interaction.user.guild_permissions.administrator = False
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    return interaction


class TestDMKPollCommands(BaseTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bot = MagicMock()
        self.cog = DMKPoll(self.bot)

    async def _run(self, cmd, *args, **kwargs):
        """
        Roept een app_commands.Command aan via .callback(self, ...),
        of valt terug op direct aanroepen voor gewone callables.
        """
        cb = getattr(cmd, "callback", None)
        if cb is not None:
            # app_commands.Command: callback verwacht de cog als eerste arg
            return await cb(self.cog, *args, **kwargs)
        # fallback voor echte callables (zou hier niet meer moeten komen)
        return await cast(Any, cmd)(*args, **kwargs)

    def _last_content(self, mock_send) -> str:
        """Haal 'content' op uit kwargs of uit de eerste positionele arg."""
        args, kwargs = mock_send.call_args
        if "content" in kwargs and kwargs["content"] is not None:
            return kwargs["content"]
        if args and isinstance(args[0], str):
            return args[0]
        return ""

    #  /dmk-poll-on
    async def test_on_creates_and_edits_messages_and_button_text(self):
        # Channel/guild mocks
        guild = MagicMock(id=42)
        channel = MagicMock()
        channel.id = 123
        channel.guild = guild

        # Bestaande dag-berichten: vrijdag bestaat (edit), zaterdag/zondag niet (send).
        msg_vr = MagicMock()
        msg_vr.edit = AsyncMock()

        async def fake_fetch(mid):
            return msg_vr if mid == 1111 else None

        channel.fetch_message = AsyncMock(side_effect=fake_fetch)

        sent_msgs = []

        async def fake_send(content=None, view=None):
            m = MagicMock()
            m.id = 2222 if view is None else 3333  # dag vs stemmen-bericht
            sent_msgs.append((content, view))
            return m

        channel.send = AsyncMock(side_effect=fake_send)

        # Patches in dmk_poll namespace
        with patch("apps.commands.dmk_poll.set_channel_disabled"), patch(
            "apps.commands.dmk_poll.get_message_id",
            side_effect=lambda cid, key: 1111 if key == "vrijdag" else None,
        ), patch("apps.commands.dmk_poll.save_message_id") as save_mid, patch(
            "apps.commands.dmk_poll.update_poll_message", new=AsyncMock()
        ), patch(
            "apps.commands.dmk_poll.is_paused", return_value=False
        ), patch(
            "apps.commands.dmk_poll.OneStemButtonView"
        ) as OneStem, patch(
            "apps.commands.dmk_poll.build_poll_message_for_day_async",
            new=AsyncMock(return_value="DAGCONTENT"),
        ):

            OneStem.return_value = MagicMock()

            interaction = _mk_interaction(channel=channel, admin=True, guild=guild)
            await self._run(self.cog.on, interaction)

            # Vrijdag ge-edit, zaterdag/zondag ge-sent + id opgeslagen
            msg_vr.edit.assert_awaited_with(content="DAGCONTENT", view=None)
            # Save_message_id zou 2x aangeroepen moeten zijn (za/zo) en 1x voor 'stemmen'
            assert save_mid.call_count == 3

            # Followup verstuurd
            interaction.followup.send.assert_called()
            assert "ingeschakeld" in self._last_content(interaction.followup.send)

    async def test_on_no_channel_early_return(self):
        interaction = _mk_interaction(channel=None, admin=True)
        await self._run(self.cog.on, interaction)
        interaction.followup.send.assert_called()
        assert "Geen kanaal" in self._last_content(interaction.followup.send)

    #  /dmk-poll-reset
    async def test_reset_updates_existing_day_messages_and_stemmen_button(self):
        guild = MagicMock(id=99)
        channel = MagicMock()
        channel.id = 777
        channel.guild = guild

        # Er zijn twee dag-berichten aanwezig (vr, za), en 'stemmen'-bericht
        msg_vr = MagicMock()
        msg_vr.edit = AsyncMock()
        msg_za = MagicMock()
        msg_za.edit = AsyncMock()
        s_msg = MagicMock()
        s_msg.edit = AsyncMock()

        async def fake_fetch(mid):
            mapping = {111: msg_vr, 222: msg_za, 999: s_msg}
            return mapping.get(mid, None)

        channel.fetch_message = AsyncMock(side_effect=fake_fetch)

        with patch(
            "apps.commands.dmk_poll.append_week_snapshot", new=AsyncMock()
        ), patch("apps.commands.dmk_poll.reset_votes", new=AsyncMock()), patch(
            "apps.commands.dmk_poll.is_name_display_enabled", return_value=True
        ), patch(
            "apps.commands.dmk_poll.toggle_name_display"
        ), patch(
            "apps.commands.dmk_poll.get_message_id",
            side_effect=lambda cid, k: (
                {"vrijdag": 111, "zaterdag": 222}.get(k) if isinstance(k, str) else None
            ),
        ), patch(
            "apps.commands.dmk_poll.is_paused", return_value=False
        ), patch(
            "apps.commands.dmk_poll.should_hide_counts", return_value=False
        ), patch(
            "apps.commands.dmk_poll.build_poll_message_for_day_async",
            new=AsyncMock(return_value="RESETCONTENT"),
        ), patch(
            "apps.commands.dmk_poll.OneStemButtonView"
        ) as OneStem:

            OneStem.return_value = MagicMock()

            # Ook 'stemmen'-bericht aanwezig
            def get_mid(cid, key):
                return (
                    999
                    if key == "stemmen"
                    else {"vrijdag": 111, "zaterdag": 222}.get(key)
                )

            with patch("apps.commands.dmk_poll.get_message_id", side_effect=get_mid):
                interaction = _mk_interaction(channel=channel, admin=True, guild=guild)
                await self._run(self.cog.reset, interaction)

        # Beide dagberichten ge-edit en 'stemmen' aangepast
        msg_vr.edit.assert_awaited()
        msg_za.edit.assert_awaited()
        s_msg.edit.assert_awaited()
        interaction.followup.send.assert_called()

    async def test_reset_when_no_day_messages_found(self):
        guild = MagicMock(id=1)
        channel = MagicMock(id=2, guild=guild)
        channel.fetch_message = AsyncMock(return_value=None)

        with patch(
            "apps.commands.dmk_poll.append_week_snapshot", new=AsyncMock()
        ), patch("apps.commands.dmk_poll.reset_votes", new=AsyncMock()), patch(
            "apps.commands.dmk_poll.is_name_display_enabled", return_value=False
        ), patch(
            "apps.commands.dmk_poll.get_message_id", return_value=None
        ), patch(
            "apps.commands.dmk_poll.is_paused", return_value=True
        ):

            interaction = _mk_interaction(channel=channel, admin=True, guild=guild)
            await self._run(self.cog.reset, interaction)

        interaction.followup.send.assert_called()
        assert "Geen dag-berichten" in self._last_content(interaction.followup.send)

    #  /dmk-poll-pauze
    async def test_pauze_toggles_and_updates_message_existing_and_missing(self):
        guild = MagicMock(id=5)
        channel = MagicMock(id=6, guild=guild)

        s_msg = MagicMock()
        s_msg.edit = AsyncMock()

        async def fake_fetch(mid):
            return s_msg if mid == 999 else None

        channel.fetch_message = AsyncMock(side_effect=fake_fetch)
        channel.send = AsyncMock(return_value=MagicMock(id=1234))

        with patch(
            "apps.commands.dmk_poll.toggle_paused", side_effect=[True, False]
        ), patch(
            "apps.commands.dmk_poll.get_message_id", side_effect=[999, None]
        ), patch(
            "apps.commands.dmk_poll.save_message_id"
        ) as save_mid, patch(
            "apps.commands.dmk_poll.OneStemButtonView"
        ) as OneStem:

            OneStem.return_value = MagicMock()

            # Eerste call: s_mid bestaat → edit
            interaction = _mk_interaction(channel=channel, admin=True, guild=guild)
            await self._run(self.cog.pauze, interaction)
            s_msg.edit.assert_awaited()
            interaction.followup.send.assert_called()
            assert "gepauzeerd" in self._last_content(interaction.followup.send)

            # Tweede call: geen s_mid → send + save id
            interaction2 = _mk_interaction(channel=channel, admin=True, guild=guild)
            await self._run(self.cog.pauze, interaction2)
            channel.send.assert_awaited()
            assert save_mid.called

    #  /dmk-poll-verwijderen
    async def test_verwijderbericht_closes_and_clears_ids_and_disables_channel(self):
        guild = MagicMock(id=10)
        channel = MagicMock(id=20, guild=guild)

        msg_vr = MagicMock()
        msg_vr.edit = AsyncMock()
        msg_za = MagicMock()
        msg_za.edit = AsyncMock()

        async def fake_fetch(mid):
            return {111: msg_vr, 222: msg_za}.get(mid)

        channel.fetch_message = AsyncMock(side_effect=fake_fetch)

        with patch(
            "apps.commands.dmk_poll.get_message_id",
            side_effect=lambda cid, k: {"vrijdag": 111, "zaterdag": 222}.get(k),
        ), patch("apps.commands.dmk_poll.clear_message_id") as clr_mid, patch(
            "apps.commands.dmk_poll.set_channel_disabled"
        ) as set_dis:

            interaction = _mk_interaction(channel=channel, admin=True, guild=guild)
            await self._run(self.cog.verwijderbericht, interaction)

        # Beide dag-berichten ge-edit en keys opgeschoond
        msg_vr.edit.assert_awaited()
        msg_za.edit.assert_awaited()
        assert clr_mid.call_count >= 2
        set_dis.assert_called_with(channel.id, True)
        interaction.followup.send.assert_called()

    async def test_verwijderbericht_also_clears_stemmen_and_falls_back_to_edit_on_delete_error(
        self,
    ):
        guild = MagicMock(id=10)
        channel = MagicMock(id=20, guild=guild)

        s_msg = MagicMock()
        s_msg.delete = AsyncMock(side_effect=Exception("no perms"))
        s_msg.edit = AsyncMock()

        channel.fetch_message = AsyncMock(return_value=s_msg)

        with patch(
            "apps.commands.dmk_poll.get_message_id",
            side_effect=lambda cid, k: 999 if k == "stemmen" else None,
        ), patch("apps.commands.dmk_poll.clear_message_id") as clr_mid, patch(
            "apps.commands.dmk_poll.set_channel_disabled"
        ):

            interaction = _mk_interaction(channel=channel, admin=True, guild=guild)
            await self._run(self.cog.verwijderbericht, interaction)

        s_msg.edit.assert_awaited()
        clr_mid.assert_called_with(channel.id, "stemmen")
        interaction.followup.send.assert_called()

    async def test_verwijderbericht_when_nothing_found(self):
        guild = MagicMock(id=10)
        channel = MagicMock(id=20, guild=guild)
        channel.fetch_message = AsyncMock(return_value=None)

        with patch("apps.commands.dmk_poll.get_message_id", return_value=None), patch(
            "apps.commands.dmk_poll.clear_message_id"
        ), patch("apps.commands.dmk_poll.set_channel_disabled"):

            interaction = _mk_interaction(channel=channel, admin=True, guild=guild)
            await self._run(self.cog.verwijderbericht, interaction)

        interaction.followup.send.assert_called()
        assert "Er stonden geen poll-berichten" in self._last_content(
            interaction.followup.send
        )

    #  /dmk-poll-stemmen
    async def test_stemmen_set_visibility_all_days_and_specific_day(self):
        guild = MagicMock(id=1)
        channel = MagicMock(id=2, guild=guild)

        # Eerst: zichtbaar voor alle dagen
        with patch("apps.commands.dmk_poll.set_visibility") as set_vis, patch(
            "apps.commands.dmk_poll.update_poll_message", new=AsyncMock()
        ):
            interaction = _mk_interaction(channel=channel, admin=True, guild=guild)

            Choice = type(
                "Choice",
                (),
                {"__init__": lambda self, value: setattr(self, "value", value)},
            )
            actie = Choice("zichtbaar")

            await self._run(
                self.cog.stemmen, interaction, actie=actie, dag=None, tijd=None
            )

            # Drie dagen aangeroepen
            assert set_vis.call_count == 3
            interaction.followup.send.assert_called()
            assert "Instellingen voor alle dagen" in self._last_content(
                interaction.followup.send
            )

        # Dan: verborgen met tijd voor één dag
        with patch("apps.commands.dmk_poll.set_visibility") as set_vis, patch(
            "apps.commands.dmk_poll.update_poll_message", new=AsyncMock()
        ):
            interaction = _mk_interaction(channel=channel, admin=True, guild=guild)
            Choice = type(
                "Choice",
                (),
                {"__init__": lambda self, value: setattr(self, "value", value)},
            )
            actie = Choice("verborgen")
            dag = Choice("vrijdag")
            await self._run(
                self.cog.stemmen, interaction, actie=actie, dag=dag, tijd="17:45"
            )

            set_vis.assert_called_with(
                channel.id, "vrijdag", modus="deadline", tijd="17:45"
            )
            interaction.followup.send.assert_called()
            assert "Instelling voor vrijdag" in self._last_content(
                interaction.followup.send
            )

    async def test_stemmen_no_channel(self):
        interaction = _mk_interaction(channel=None, admin=True)
        Choice = type(
            "Choice",
            (),
            {"__init__": lambda self, value: setattr(self, "value", value)},
        )
        await self._run(self.cog.stemmen, interaction, actie=Choice("zichtbaar"))
        interaction.followup.send.assert_called()
        assert "Geen kanaal" in self._last_content(interaction.followup.send)

    #  Archief commands
    async def test_archief_download_no_archive(self):
        channel = MagicMock(id=1)
        interaction = _mk_interaction(channel=channel, admin=True)

        with patch("apps.commands.dmk_poll.archive_exists", return_value=False):
            await self._run(self.cog.archief_download, interaction)

        interaction.followup.send.assert_called()
        assert (
            "nog geen archief" in self._last_content(interaction.followup.send).lower()
        )

    async def test_archief_download_with_data_without_view_and_with_view(self):
        channel = MagicMock(id=1)
        interaction = _mk_interaction(channel=channel, admin=True)

        # 1) ArchiveDeleteView is None
        with patch("apps.commands.dmk_poll.archive_exists", return_value=True), patch(
            "apps.commands.dmk_poll.open_archive_bytes",
            return_value=("arch.csv", b"week,vr,za,zo\n"),
        ), patch("apps.commands.dmk_poll.ArchiveDeleteView", None):

            await self._run(self.cog.archief_download, interaction)
            interaction.followup.send.assert_called()
            # File zou meegaan (we kunnen alleen checken dat 'file' in kwargs zit)
            assert "file" in interaction.followup.send.call_args.kwargs

        # 2) ArchiveDeleteView bestaat
        interaction2 = _mk_interaction(channel=channel, admin=True)
        with patch("apps.commands.dmk_poll.archive_exists", return_value=True), patch(
            "apps.commands.dmk_poll.open_archive_bytes",
            return_value=("arch.csv", b"week,vr,za,zo\n"),
        ), patch("apps.commands.dmk_poll.ArchiveDeleteView") as ViewCls:

            ViewCls.return_value = MagicMock()
            await self._run(self.cog.archief_download, interaction2)
            interaction2.followup.send.assert_called()
            kwargs = interaction2.followup.send.call_args.kwargs
            assert "file" in kwargs and "view" in kwargs

    async def test_archief_verwijderen_true_and_false(self):
        interaction = _mk_interaction(channel=MagicMock(id=1), admin=True)

        with patch("apps.commands.dmk_poll.delete_archive", return_value=True):
            await self._run(self.cog.archief_verwijderen, interaction)
            interaction.followup.send.assert_called()
            assert "verwijderd" in self._last_content(interaction.followup.send).lower()

        interaction2 = _mk_interaction(channel=MagicMock(id=1), admin=True)
        with patch("apps.commands.dmk_poll.delete_archive", return_value=False):
            await self._run(self.cog.archief_verwijderen, interaction2)
            interaction2.followup.send.assert_called()
            assert (
                "geen archief" in self._last_content(interaction2.followup.send).lower()
            )

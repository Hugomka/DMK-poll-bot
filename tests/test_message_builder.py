# tests/test_message_builder.py
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, patch

import pytz

from apps.utils import message_builder as mb
from tests.base import BaseTestCase


def opt(dag: str, tijd: str, emoji: str = "🕒"):
    return SimpleNamespace(dag=dag, tijd=tijd, emoji=emoji)


class GuildAlwaysFail:
    """
    Guild-mock die altijd faalt bij member-lookups.
    - get_member gooit een Exception
    - fetch_member is async en gooit ook een Exception
    Hiermee raken we het except-pad in build_grouped_names_for.
    """

    def get_member(self, _):
        raise RuntimeError("boom")

    async def fetch_member(self, _):
        raise RuntimeError("boom")


class TestMessageBuilder(BaseTestCase):

    # _get_next_weekday_date
    def test_get_next_weekday_date_before_reset(self):
        """Test dat datums stabiel blijven vóór de reset (dinsdag 20:00)."""
        tz = pytz.timezone("Europe/Amsterdam")

        # Zaterdag 9 november 2024, 15:00 (vóór dinsdag 20:00 reset)
        # Poll-periode: di 5 nov 20:00 - di 12 nov 20:00
        # Verwachte datums: vr 8 nov, za 9 nov, zo 10 nov
        test_time = tz.localize(datetime(2024, 11, 9, 15, 0))

        with patch("apps.utils.message_builder.datetime") as mock_dt:
            mock_dt.now.return_value = test_time

            vrijdag_date = mb._get_next_weekday_date("vrijdag")
            zaterdag_date = mb._get_next_weekday_date("zaterdag")
            zondag_date = mb._get_next_weekday_date("zondag")

            assert vrijdag_date == "08-11"  # 8 november (vorige vrijdag)
            assert zaterdag_date == "09-11"  # 9 november (vandaag)
            assert zondag_date == "10-11"   # 10 november (morgen)

    def test_get_next_weekday_date_after_reset(self):
        """Test dat datums updaten ná de reset (dinsdag 20:00)."""
        tz = pytz.timezone("Europe/Amsterdam")

        # Dinsdag 12 november 2024, 20:01 (net na reset)
        # Nieuwe poll-periode: di 12 nov 20:00 - di 19 nov 20:00
        # Verwachte datums: vr 15 nov, za 16 nov, zo 17 nov
        test_time = tz.localize(datetime(2024, 11, 12, 20, 1))

        with patch("apps.utils.message_builder.datetime") as mock_dt:
            mock_dt.now.return_value = test_time

            vrijdag_date = mb._get_next_weekday_date("vrijdag")
            zaterdag_date = mb._get_next_weekday_date("zaterdag")
            zondag_date = mb._get_next_weekday_date("zondag")

            assert vrijdag_date == "15-11"  # 15 november (volgende vrijdag)
            assert zaterdag_date == "16-11"  # 16 november
            assert zondag_date == "17-11"   # 17 november

    def test_get_next_weekday_date_on_tuesday_before_reset(self):
        """Test dat datums stabiel blijven op dinsdag vóór 20:00."""
        tz = pytz.timezone("Europe/Amsterdam")

        # Dinsdag 12 november 2024, 19:59 (net vóór reset)
        # Huidige poll-periode: di 5 nov 20:00 - di 12 nov 20:00
        # Verwachte datums: vr 8 nov, za 9 nov, zo 10 nov (vorig weekend)
        test_time = tz.localize(datetime(2024, 11, 12, 19, 59))

        with patch("apps.utils.message_builder.datetime") as mock_dt:
            mock_dt.now.return_value = test_time

            vrijdag_date = mb._get_next_weekday_date("vrijdag")
            zaterdag_date = mb._get_next_weekday_date("zaterdag")
            zondag_date = mb._get_next_weekday_date("zondag")

            assert vrijdag_date == "08-11"  # 8 november (vorige vrijdag)
            assert zaterdag_date == "09-11"  # 9 november
            assert zondag_date == "10-11"   # 10 november

    # build_poll_message_for_day_async
    async def test_build_message_no_options(self):
        """Geen opties → '(geen opties gevonden)' tekst."""
        with patch("apps.utils.message_builder.get_poll_options", return_value=[]):
            txt = await mb.build_poll_message_for_day_async(
                "vrijdag", guild_id=1, channel_id=2, hide_counts=True
            )
            assert "geen opties gevonden" in txt

    async def test_build_message_with_counts_visible(self):
        """Aantallen zichtbaar (hide_counts=False) → toont getallen."""
        options = [
            opt("vrijdag", "om 19:00 uur", "🟢"),
            opt("vrijdag", "om 20:30 uur", "🔵"),
        ]
        counts = {"om 19:00 uur": 3, "om 20:30 uur": 5}

        with patch(
            "apps.utils.message_builder.get_poll_options", return_value=options
        ), patch("apps.utils.message_builder.get_counts_for_day", return_value=counts):

            txt = await mb.build_poll_message_for_day_async(
                "vrijdag", guild_id=1, channel_id=2, hide_counts=False
            )
            # Check voor Hammertime timestamps met "Om" en "uur"
            assert "🟢 Om <t:" in txt  # Hammertime format voor 19:00
            assert ":t> uur (3 stemmen)" in txt
            assert "🔵 Om <t:" in txt  # Hammertime format voor 20:30
            assert ":t> uur (5 stemmen)" in txt

    async def test_build_message_hides_misschien_in_deadline_mode_counts_hidden(self):
        """Misschien wordt NIET getoond in deadline-modus wanneer counts verborgen zijn."""
        options = [
            opt("vrijdag", "om 19:00 uur", "🟢"),
            opt("vrijdag", "om 20:30 uur", "🔵"),
            opt("vrijdag", "misschien", "Ⓜ️"),
            opt("vrijdag", "niet meedoen", "❌"),
        ]

        with patch("apps.utils.message_builder.get_poll_options", return_value=options), \
             patch("apps.utils.message_builder.get_setting", return_value={"modus": "deadline", "tijd": "18:00"}):
            # Gebruik vrijdag van de huidige week (realistisch voor DMK-poll-bot)
            # Bot werkt met huidige week (maandag t/m zondag), datum kan in verleden/toekomst zijn
            now = datetime.now()
            days_since_monday = now.weekday()  # 0=maandag, 4=vrijdag
            monday_this_week = now - timedelta(days=days_since_monday)
            friday_this_week = monday_this_week + timedelta(days=4)  # Vrijdag = +4 dagen
            friday_date = friday_this_week.strftime("%Y-%m-%d")
            txt = await mb.build_poll_message_for_day_async(
                "vrijdag", guild_id=1, channel_id=2, hide_counts=True, datum_iso=friday_date
            )
            # Normale tijdslots worden wel getoond met Hammertime
            assert "🟢 Om <t:" in txt  # Hammertime voor 19:00
            assert ":t> uur (stemmen verborgen)" in txt
            assert "🔵 Om <t:" in txt  # Hammertime voor 20:30
            # "Misschien" wordt NIET getoond in deadline-modus
            assert "Ⓜ️ Misschien" not in txt
            # "Niet meedoen" wordt wel getoond
            assert "❌ Niet meedoen (stemmen verborgen)" in txt

    async def test_build_message_hides_misschien_in_deadline_mode_counts_visible(self):
        """Misschien wordt NIET getoond in deadline-modus, ook niet wanneer counts zichtbaar zijn (toch altijd 0)."""
        options = [
            opt("vrijdag", "om 19:00 uur", "🟢"),
            opt("vrijdag", "om 20:30 uur", "🔵"),
            opt("vrijdag", "misschien", "Ⓜ️"),
            opt("vrijdag", "niet meedoen", "❌"),
        ]
        counts = {
            "om 19:00 uur": 3,
            "om 20:30 uur": 5,
            "misschien": 0,  # In deadline-modus worden misschien-stemmen omgezet naar "niet meedoen"
            "niet meedoen": 3,
        }

        with patch(
            "apps.utils.message_builder.get_poll_options", return_value=options
        ), patch("apps.utils.message_builder.get_counts_for_day", return_value=counts), \
           patch("apps.utils.message_builder.get_setting", return_value={"modus": "deadline", "tijd": "18:00"}):

            txt = await mb.build_poll_message_for_day_async(
                "vrijdag", guild_id=1, channel_id=2, hide_counts=False
            )
            # Normale opties worden getoond met Hammertime
            assert "🟢 Om <t:" in txt  # Hammertime voor 19:00
            assert ":t> uur (3 stemmen)" in txt
            assert "🔵 Om <t:" in txt  # Hammertime voor 20:30
            assert ":t> uur (5 stemmen)" in txt
            # "Misschien" wordt NIET getoond in deadline-modus
            assert "Ⓜ️ Misschien" not in txt
            # "Niet meedoen" wordt wel getoond
            assert "❌ Niet meedoen (3 stemmen)" in txt

    async def test_build_message_shows_misschien_in_zichtbaar_mode(self):
        """Misschien wordt WEL getoond in zichtbaar-modus (altijd)."""
        options = [
            opt("vrijdag", "om 19:00 uur", "🟢"),
            opt("vrijdag", "om 20:30 uur", "🔵"),
            opt("vrijdag", "misschien", "Ⓜ️"),
            opt("vrijdag", "niet meedoen", "❌"),
        ]
        counts = {
            "om 19:00 uur": 3,
            "om 20:30 uur": 5,
            "misschien": 2,
            "niet meedoen": 1,
        }

        with patch(
            "apps.utils.message_builder.get_poll_options", return_value=options
        ), patch("apps.utils.message_builder.get_counts_for_day", return_value=counts), \
           patch("apps.utils.message_builder.get_setting", return_value={"modus": "altijd", "tijd": "18:00"}):

            txt = await mb.build_poll_message_for_day_async(
                "vrijdag", guild_id=1, channel_id=2, hide_counts=False
            )
            # Alle opties worden getoond inclusief Misschien in zichtbaar-modus
            assert "🟢 Om <t:" in txt  # Hammertime voor 19:00
            assert ":t> uur (3 stemmen)" in txt
            assert "🔵 Om <t:" in txt  # Hammertime voor 20:30
            assert ":t> uur (5 stemmen)" in txt
            assert "Ⓜ️ Misschien (2 stemmen)" in txt
            assert "❌ Niet meedoen (1 stemmen)" in txt

    # build_grouped_names_for
    async def test_grouped_empty_votes(self):
        """Lege stemmen → (0, ''). (dekt het vroege return-pad)"""
        total, text = await mb.build_grouped_names_for(
            "vrijdag", "om 19:00 uur", None, {}
        )
        assert total == 0
        assert text == ""

    async def test_grouped_guest_with_guild_exception(self):
        """
        Gast-stem zonder geldige guild-member lookup:
        - guild.get_member / fetch_member gooien excepties → mention blijft 'Gast'
        - alleen gasten (owner stemt niet) → '({mention}: namen)'
        """
        votes = {"123_guest::Mario": {"vrijdag": ["om 19:00 uur"]}}

        # Pylance tevreden houden: cast onze mock naar het verwachte type
        guild = cast(mb.discord.Guild, GuildAlwaysFail())

        total, text = await mb.build_grouped_names_for(
            "vrijdag", "om 19:00 uur", guild, votes
        )
        assert total == 1
        assert text == "(Gast: Mario)"  # Gasten en owner stemt niet

    async def test_grouped_member_with_guild_exception(self):
        """
        Lid-stem zonder geldige guild-member lookup:
        - guild.get_member / fetch_member gooien excepties → mention valt terug op 'Lid'
        - lid zonder gasten → 'Lid'
        """
        votes = {456: {"vrijdag": ["om 20:30 uur"]}}

        # Pylance tevreden houden: cast onze mock naar het verwachte type
        guild = cast(mb.discord.Guild, GuildAlwaysFail())

        total, text = await mb.build_grouped_names_for(
            "vrijdag", "om 20:30 uur", guild, votes
        )
        assert total == 1
        assert text == "Lid"

    async def test_grouped_outer_exception_continue(self):
        """
        Buitenste try/except: als user_votes geen dict is (bijv. None),
        dan veroorzaakt .get(...) een AttributeError → except → doorgaan.
        Resultaat blijft leeg.
        """
        votes = {"kapot": None}  # Triggert except in de loop

        total, text = await mb.build_grouped_names_for(
            "vrijdag", "om 19:00 uur", None, votes
        )
        assert total == 0
        assert text == ""

    async def test_build_message_shows_non_voters_when_all_voted(self):
        """Toont 🎉 bericht wanneer alle leden hebben gestemd (0 niet-stemmers)."""
        options = [
            opt("vrijdag", "om 19:00 uur", "🟢"),
            opt("vrijdag", "niet meedoen", "❌"),
        ]
        counts = {"om 19:00 uur": 2, "niet meedoen": 1}

        # Mock channel met 3 leden (waarvan allemaal hebben gestemd)
        mock_member1 = SimpleNamespace(id=123, bot=False, display_name="Alice")
        mock_member2 = SimpleNamespace(id=456, bot=False, display_name="Bob")
        mock_member3 = SimpleNamespace(id=789, bot=False, display_name="Carol")
        mock_channel = SimpleNamespace(members=[mock_member1, mock_member2, mock_member3])
        mock_guild = SimpleNamespace(id=1)

        # Alle 3 leden hebben gestemd
        all_votes = {
            "123": {"vrijdag": ["om 19:00 uur"]},
            "456": {"vrijdag": ["om 19:00 uur"]},
            "789": {"vrijdag": ["niet meedoen"]},
        }

        with patch(
            "apps.utils.message_builder.get_poll_options", return_value=options
        ), patch(
            "apps.utils.message_builder.get_counts_for_day", return_value=counts
        ), patch(
            "apps.utils.message_builder.load_votes", return_value=all_votes
        ):
            txt = await mb.build_poll_message_for_day_async(
                "vrijdag",
                guild_id=1,
                channel_id=2,
                hide_counts=False,
                guild=cast(mb.discord.Guild, mock_guild),
                channel=mock_channel,
            )
            assert "🎉 Iedereen heeft gestemd! - *Fantastisch dat jullie allemaal hebben gestemd! Bedankt!*" in txt

    async def test_build_message_shows_non_voters_count(self):
        """Toont 👻 met aantal niet-stemmers wanneer niet iedereen heeft gestemd."""
        options = [
            opt("vrijdag", "om 19:00 uur", "🟢"),
            opt("vrijdag", "niet meedoen", "❌"),
        ]
        counts = {"om 19:00 uur": 1, "niet meedoen": 0}

        # Mock channel met 3 leden (waarvan 1 heeft gestemd)
        mock_member1 = SimpleNamespace(id=123, bot=False, display_name="Alice")
        mock_member2 = SimpleNamespace(id=456, bot=False, display_name="Bob")
        mock_member3 = SimpleNamespace(id=789, bot=False, display_name="Carol")
        mock_channel = SimpleNamespace(id=2, members=[mock_member1, mock_member2, mock_member3])

        # Mock guild with get_member and fetch_member methods
        def mock_get_member(member_id):
            members_map = {123: mock_member1, 456: mock_member2, 789: mock_member3}
            return members_map.get(member_id)

        async def mock_fetch_member(member_id):
            return mock_get_member(member_id)

        mock_guild = SimpleNamespace(
            id=1,
            get_member=mock_get_member,
            fetch_member=mock_fetch_member
        )

        # Alleen lid 123 heeft gestemd (others are non-voters calculated from channel members)
        all_votes = {
            "123": {"vrijdag": ["om 19:00 uur"]},
        }

        with patch(
            "apps.utils.message_builder.get_poll_options", return_value=options
        ), patch(
            "apps.utils.message_builder.get_counts_for_day", return_value=counts
        ), patch(
            "apps.utils.message_builder.load_votes", new=AsyncMock(return_value=all_votes)
        ), patch(
            "apps.utils.poll_storage.load_votes", new=AsyncMock(return_value=all_votes)
        ):
            txt = await mb.build_poll_message_for_day_async(
                "vrijdag",
                guild_id=1,
                channel_id=2,
                hide_counts=False,
                guild=cast(mb.discord.Guild, mock_guild),
                channel=mock_channel,
            )
            assert "👻 Niet gestemd (2 personen)" in txt
            assert "🎉" not in txt

    async def test_build_message_shows_non_voters_when_counts_hidden(self):
        """Niet-stemmers worden WEL getoond wanneer counts verborgen zijn (om te motiveren)."""
        options = [opt("vrijdag", "om 19:00 uur", "🟢")]

        mock_member1 = SimpleNamespace(id=123, bot=False, display_name="Alice")
        mock_channel = SimpleNamespace(id=2, members=[mock_member1])

        # Mock guild with get_member and fetch_member methods
        def mock_get_member(member_id):
            if member_id == 123:
                return mock_member1
            return None

        async def mock_fetch_member(member_id):
            return mock_get_member(member_id)

        mock_guild = SimpleNamespace(
            id=1,
            get_member=mock_get_member,
            fetch_member=mock_fetch_member
        )

        # Niemand heeft gestemd, Alice is non-voter (calculated from channel members)
        all_votes = {}

        with patch(
            "apps.utils.message_builder.get_poll_options", return_value=options
        ), patch(
            "apps.utils.message_builder.load_votes", new=AsyncMock(return_value=all_votes)
        ), patch(
            "apps.utils.poll_storage.load_votes", new=AsyncMock(return_value=all_votes)
        ):
            txt = await mb.build_poll_message_for_day_async(
                "vrijdag",
                guild_id=1,
                channel_id=2,
                hide_counts=True,
                guild=cast(mb.discord.Guild, mock_guild),
                channel=mock_channel,
            )
            # Niet-stemmers worden altijd getoond, ook bij verborgen counts (motivatie!)
            assert "👻 Niet gestemd (1 personen)" in txt

    async def test_build_message_past_date_shows_counts_despite_hide_setting(self):
        """Verleden datum overschrijft hide_counts=True en toont altijd counts."""
        options = [opt("maandag", "om 19:00 uur", "🟥")]
        counts = {"om 19:00 uur": 5}

        # Gebruik een datum ver in het verleden
        past_date = "2024-01-01"

        with patch(
            "apps.utils.message_builder.get_poll_options", return_value=options
        ), patch("apps.utils.message_builder.get_counts_for_day", return_value=counts), \
           patch("apps.utils.poll_settings.get_poll_option_state", return_value=True):
            txt = await mb.build_poll_message_for_day_async(
                "maandag",
                guild_id=1,
                channel_id=2,
                hide_counts=True,  # Verborgen, maar wordt overschreven voor verleden
                datum_iso=past_date,
            )
            # Verleden datum moet counts tonen ondanks hide_counts=True
            assert "(5 stemmen)" in txt
            assert "(stemmen verborgen)" not in txt

    async def test_build_message_invalid_datum_iso_falls_back_safely(self):
        """Invalid datum_iso veroorzaakt exception die wordt afgevangen."""
        options = [opt("vrijdag", "om 19:00 uur", "🔴")]
        counts = {"om 19:00 uur": 3}

        # Invalid datum_iso die parse error veroorzaakt
        invalid_date = "invalid-date-format"

        with patch(
            "apps.utils.message_builder.get_poll_options", return_value=options
        ), patch("apps.utils.message_builder.get_counts_for_day", return_value=counts):
            txt = await mb.build_poll_message_for_day_async(
                "vrijdag",
                guild_id=1,
                channel_id=2,
                hide_counts=True,
                datum_iso=invalid_date,
            )
            # Bij parse error: assume niet-verleden, dus counts verborgen
            assert "(stemmen verborgen)" in txt

    async def test_get_weekday_date_returns_from_rolling_window(self):
        """_get_weekday_date_for_rolling_window gebruikt rolling window voor correcte datum."""
        mock_window = [
            {"dag": "vrijdag", "datum": datetime(2025, 12, 5)},
            {"dag": "zaterdag", "datum": datetime(2025, 12, 6)},
        ]

        with patch(
            "apps.utils.message_builder.get_rolling_window_days", return_value=mock_window
        ):
            result = mb._get_weekday_date_for_rolling_window("vrijdag", dag_als_vandaag=None)
            assert result == "2025-12-05"

    async def test_get_weekday_date_returns_empty_string_when_not_found(self):
        """_get_weekday_date_for_rolling_window returnt lege string als dag niet in window."""
        mock_window = [
            {"dag": "zaterdag", "datum": datetime(2025, 12, 6)},
        ]

        with patch(
            "apps.utils.message_builder.get_rolling_window_days", return_value=mock_window
        ):
            result = mb._get_weekday_date_for_rolling_window("maandag", dag_als_vandaag=None)
            assert result == ""

    async def test_get_non_voters_with_stored_ids_builds_display_names(self):
        """get_non_voters_for_day haalt display names op voor niet-stemmers uit storage."""
        # Mock members met verschillende name attributes
        mock_member1 = SimpleNamespace(
            id=123,
            display_name="Alice",
            global_name="AliceGlobal",
            name="alice_user"
        )
        mock_member2 = SimpleNamespace(
            id=456,
            display_name=None,
            global_name="BobGlobal",
            name="bob_user"
        )

        def mock_get_member(member_id):
            if member_id == 123:
                return mock_member1
            elif member_id == 456:
                return mock_member2
            return None

        async def mock_fetch_member(member_id):
            return mock_get_member(member_id)

        mock_guild = SimpleNamespace(
            id=1,
            get_member=mock_get_member,
            fetch_member=mock_fetch_member
        )
        mock_channel = SimpleNamespace(id=2, members=[])
        all_votes = {}

        # Mock get_non_voters_from_storage om 2 non-voter IDs te returnen
        with patch(
            "apps.utils.message_builder.get_non_voters_from_storage",
            new=AsyncMock(return_value=(2, ["123", "456"]))
        ):
            count, text = await mb.get_non_voters_for_day(
                "vrijdag",
                cast(mb.discord.Guild, mock_guild),
                mock_channel,
                all_votes
            )

            assert count == 2
            assert "@Alice" in text
            assert "@BobGlobal" in text  # display_name is None, gebruikt global_name

    async def test_get_non_voters_handles_member_fetch_exception(self):
        """get_non_voters_for_day skip members die exception gooien bij fetch."""
        def mock_get_member(_):
            return None

        async def mock_fetch_member(_):
            raise RuntimeError("Member not found")

        mock_guild = SimpleNamespace(
            id=1,
            get_member=mock_get_member,
            fetch_member=mock_fetch_member
        )
        mock_channel = SimpleNamespace(id=2, members=[])
        all_votes = {}

        # Mock get_non_voters_from_storage om 2 non-voter IDs te returnen
        with patch(
            "apps.utils.message_builder.get_non_voters_from_storage",
            new=AsyncMock(return_value=(2, ["123", "456"]))
        ):
            count, text = await mb.get_non_voters_for_day(
                "vrijdag",
                cast(mb.discord.Guild, mock_guild),
                mock_channel,
                all_votes
            )

            # Beide members gooien exception, dus 0 non-voters
            assert count == 0
            assert text == ""

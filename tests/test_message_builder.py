# tests/test_message_builder.py
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, patch

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
            assert "🟢 Om 19:00 uur (3 stemmen)" in txt
            assert "🔵 Om 20:30 uur (5 stemmen)" in txt

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
            txt = await mb.build_poll_message_for_day_async(
                "vrijdag", guild_id=1, channel_id=2, hide_counts=True
            )
            # Normale tijdslots worden wel getoond
            assert "🟢 Om 19:00 uur (stemmen verborgen)" in txt
            assert "🔵 Om 20:30 uur (stemmen verborgen)" in txt
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
            # Normale opties worden getoond
            assert "🟢 Om 19:00 uur (3 stemmen)" in txt
            assert "🔵 Om 20:30 uur (5 stemmen)" in txt
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
            assert "🟢 Om 19:00 uur (3 stemmen)" in txt
            assert "🔵 Om 20:30 uur (5 stemmen)" in txt
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

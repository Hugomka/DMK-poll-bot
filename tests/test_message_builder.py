# tests/test_message_builder.py
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

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
            assert "🟢 om 19:00 uur (3 stemmen)" in txt
            assert "🔵 om 20:30 uur (5 stemmen)" in txt

    async def test_build_message_hides_misschien_when_counts_hidden(self):
        """Misschien wordt NIET getoond wanneer counts verborgen zijn."""
        options = [
            opt("vrijdag", "om 19:00 uur", "🟢"),
            opt("vrijdag", "om 20:30 uur", "🔵"),
            opt("vrijdag", "misschien", "Ⓜ️"),
            opt("vrijdag", "niet meedoen", "❌"),
        ]

        with patch("apps.utils.message_builder.get_poll_options", return_value=options):
            txt = await mb.build_poll_message_for_day_async(
                "vrijdag", guild_id=1, channel_id=2, hide_counts=True
            )
            # Normale tijdslots worden wel getoond
            assert "🟢 om 19:00 uur (stemmen verborgen)" in txt
            assert "🔵 om 20:30 uur (stemmen verborgen)" in txt
            # "Misschien" wordt NIET getoond
            assert "Ⓜ️ misschien" not in txt
            # "Niet meedoen" wordt wel getoond
            assert "❌ niet meedoen (stemmen verborgen)" in txt

    async def test_build_message_shows_misschien_when_counts_visible(self):
        """Misschien wordt WEL getoond wanneer counts zichtbaar zijn."""
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
        ), patch("apps.utils.message_builder.get_counts_for_day", return_value=counts):

            txt = await mb.build_poll_message_for_day_async(
                "vrijdag", guild_id=1, channel_id=2, hide_counts=False
            )
            # Alle opties worden getoond inclusief Misschien
            assert "🟢 om 19:00 uur (3 stemmen)" in txt
            assert "🔵 om 20:30 uur (5 stemmen)" in txt
            assert "Ⓜ️ misschien (2 stemmen)" in txt
            assert "❌ niet meedoen (1 stemmen)" in txt

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

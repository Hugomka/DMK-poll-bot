# tests/test_poll_button_view_construction.py

from __future__ import annotations

from datetime import datetime
from importlib import import_module
from typing import Any, cast
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from tests.base import BaseTestCase

_pb = import_module("apps.ui.poll_buttons")
MODULE = _pb.__name__
PollButton = _pb.PollButton
ButtonStyle = _pb.ButtonStyle
PollButtonView = _pb.PollButtonView
create_poll_button_views_per_day = _pb.create_poll_button_views_per_day


# Kleine helperklasse om opties te bouwen (lijkt op echte PollOption)
class SimpleOption:
    def __init__(self, dag: str, tijd: str, emoji: str) -> None:
        self.dag = dag
        self.tijd = tijd
        self.emoji = emoji  # Voeg emoji attribuut toe
        self.label = f"{emoji} {dag.capitalize()} {tijd}"


class TestPollButtonViewConstruction(BaseTestCase):
    """Bouw van views op basis van stemmen + zichtbaarheid."""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        # Vast tijdstip om flakiness te voorkomen
        self.now = datetime(2025, 8, 22, 17, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))

    async def test_selected_and_unselected_buttons_have_correct_styles(self) -> None:
        """
        Geselecteerde opties krijgen success‑stijl en een vinkje in de label.
        Niet‑geselecteerde opties hebben secondary‑stijl en geen vinkje.
        """
        opties = [
            SimpleOption("vrijdag", "om 19:00 uur", "🎮"),
            SimpleOption("vrijdag", "om 20:30 uur", "🎲"),
            SimpleOption("vrijdag", "misschien", "❓"),
        ]
        votes = {"vrijdag": ["om 19:00 uur", "misschien"]}

        with patch(f"{MODULE}.get_poll_options", return_value=opties), patch(
            f"{MODULE}.is_vote_button_visible", return_value=True
        ):
            view = PollButtonView(
                votes=votes, channel_id=123, filter_dag="vrijdag", now=self.now
            )

        self.assertEqual(len(view.children), 3)

        seen_selected: set[str] = set()
        for raw_btn in view.children:
            btn = cast(
                Any, raw_btn
            )  # knoppen zijn generieke discord Items; cast naar Any
            _, tijd = btn.custom_id.split(":", 1)
            if tijd in votes["vrijdag"]:
                seen_selected.add(tijd)
                self.assertEqual(btn.style, ButtonStyle.success)
                self.assertTrue(btn.label.startswith("✅ "))
            else:
                self.assertEqual(btn.style, ButtonStyle.secondary)
                self.assertFalse(btn.label.startswith("✅ "))
        self.assertSetEqual(seen_selected, set(votes["vrijdag"]))

    async def test_visibility_filter_excludes_invisible_options(self) -> None:
        """Onzichtbare opties mogen niet toegevoegd worden aan de view."""
        opties = [
            SimpleOption("zaterdag", "om 19:00 uur", ""),
            SimpleOption("zaterdag", "om 20:30 uur", ""),
            SimpleOption("zaterdag", "misschien", ""),
        ]
        votes = {"zaterdag": []}

        def visible_side_effect(
            channel_id: int, dag: str, tijd: str, now: datetime
        ) -> bool:
            # Alleen 20:30 zichtbaar
            return tijd == "om 20:30 uur"

        with patch(f"{MODULE}.get_poll_options", return_value=opties), patch(
            f"{MODULE}.is_vote_button_visible", side_effect=visible_side_effect
        ):
            view = PollButtonView(
                votes=votes, channel_id=999, filter_dag="zaterdag", now=self.now
            )

        self.assertEqual(len(view.children), 1)
        only_button = cast(Any, view.children[0])
        self.assertIn("om 20:30 uur", only_button.custom_id)

    async def test_create_views_for_each_day(self) -> None:
        """
        ``create_poll_button_views_per_day`` levert per dag een view +
        header op wanneer er zichtbare opties zijn.
        """
        opties = [
            SimpleOption("vrijdag", "om 19:00 uur", "🔴"),
            SimpleOption("vrijdag", "om 20:30 uur", "🟠"),
            SimpleOption("zaterdag", "om 19:00 uur", "🟡"),
            SimpleOption("zaterdag", "om 20:30 uur", "⚪"),
        ]
        votes = {"vrijdag": [], "zaterdag": []}

        # Mock rolling window days met vrijdag en zaterdag als future days
        mock_rolling_window = [
            {"dag": "vrijdag", "datum_iso": "2024-12-06", "is_past": False, "is_today": False, "is_future": True},
            {"dag": "zaterdag", "datum_iso": "2024-12-07", "is_past": False, "is_today": False, "is_future": True},
        ]

        with patch(f"{MODULE}.get_poll_options", return_value=opties), patch(
            "apps.utils.poll_settings.get_enabled_rolling_window_days", return_value=mock_rolling_window
        ), patch(f"{MODULE}.is_vote_button_visible", return_value=True), patch(
            f"{MODULE}.get_user_votes", new_callable=AsyncMock, return_value=votes
        ):
            views = await create_poll_button_views_per_day(
                user_id="abc", guild_id=1, channel_id=2
            )

        self.assertEqual(len(views), 2)
        # Headers bevatten nu ook tijdzone legenda met dag-specifieke emoji's
        for dag, header, view in views:
            self.assertIn(dag, ["vrijdag", "zaterdag"])
            # Check dat header de basis tekst bevat
            self.assertIn(f"📅 **{dag.capitalize()}** — kies jouw tijden 👇", header)
            # Check dat tijdzone legenda aanwezig is (met juiste emoji per dag)
            self.assertIn("19:00 = <t:", header)  # Tijd aanwezig
            self.assertIn(":F>", header)  # Hammertime full format
            # Check dag-specifieke emoji's
            if dag == "vrijdag":
                self.assertIn("🔴", header)
                self.assertIn("🟠", header)
            elif dag == "zaterdag":
                self.assertIn("🟡", header)
                self.assertIn("⚪", header)
            self.assertTrue(view.children)  # niet leeg

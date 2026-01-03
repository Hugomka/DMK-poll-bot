# tests/test_open_stemmen_button.py

from __future__ import annotations

import types as _types
from importlib import import_module
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

from tests.base import BaseTestCase

_pb = import_module("apps.ui.poll_buttons")
MODULE = _pb.__name__
OpenStemmenButton = _pb.OpenStemmenButton
ButtonStyle = _pb.ButtonStyle


class TestOpenStemmenButton(BaseTestCase):
    """Tests voor OpenStemmenButton constructor en callback (regels ~210-246)."""

    def test_constructor_paused_sets_disabled_and_style(self) -> None:
        btn_paused = OpenStemmenButton(paused=True)
        self.assertTrue(btn_paused.disabled)
        self.assertEqual(btn_paused.style, ButtonStyle.secondary)
        self.assertIn("gepauzeerd", btn_paused.label)

        btn_active = OpenStemmenButton(paused=False)
        self.assertFalse(btn_active.disabled)
        self.assertEqual(btn_active.style, ButtonStyle.primary)
        self.assertNotIn("gepauzeerd", btn_active.label)

    async def test_callback_no_channel_early_return(self) -> None:
        class DummyResponse:
            def __init__(self) -> None:
                self._done = False
                self.sent: list[tuple[str, dict[str, Any]]] = []

            def is_done(self) -> bool:
                return self._done

            async def send_message(self, content: str, **kwargs: Any) -> None:
                self.sent.append((content, kwargs))

        class DummyFollowup:
            async def send(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
                raise AssertionError("followup hoort niet gebruikt te worden")

        interaction = _types.SimpleNamespace(
            channel_id=None,
            user=_types.SimpleNamespace(id=1),
            guild_id=0,
            guild=None,
            channel=None,
            response=DummyResponse(),
            followup=DummyFollowup(),
        )

        btn = OpenStemmenButton()
        await btn.callback(cast(Any, interaction))
        self.assertEqual(len(interaction.response.sent), 1)
        msg, kw = interaction.response.sent[0]
        self.assertIn("alleen in een serverkanaal", msg)
        self.assertTrue(kw.get("ephemeral", False))

    async def test_callback_paused_channel(self) -> None:
        class DummyResponse:
            def __init__(self) -> None:
                self.sent: list[tuple[str, dict[str, Any]]] = []

            def is_done(self) -> bool:
                return False

            async def send_message(self, content: str, **kwargs: Any) -> None:
                self.sent.append((content, kwargs))

        interaction = _types.SimpleNamespace(
            channel_id=123,
            user=_types.SimpleNamespace(id=1),
            guild_id=7,
            guild=_types.SimpleNamespace(id=7),
            channel="chan",
            response=DummyResponse(),
            followup=_types.SimpleNamespace(),
        )

        btn = OpenStemmenButton()
        with patch(f"{MODULE}.is_paused", return_value=True):
            await btn.callback(cast(Any, interaction))

        self.assertEqual(len(interaction.response.sent), 1)
        msg, kw = interaction.response.sent[0]
        self.assertIn("⏸️ Stemmen is tijdelijk gepauzeerd", msg)
        self.assertTrue(kw.get("ephemeral", False))

    async def test_callback_no_views_available(self) -> None:
        class DummyResponse:
            def __init__(self) -> None:
                self.sent: list[tuple[str, dict[str, Any]]] = []
                self.edited: list[dict[str, Any]] = []

            def is_done(self) -> bool:
                return False

            async def send_message(self, content: str, **kwargs: Any) -> None:
                self.sent.append((content, kwargs))

        interaction = _types.SimpleNamespace(
            channel_id=123,
            user=_types.SimpleNamespace(id=1),
            guild_id=7,
            guild=_types.SimpleNamespace(id=7),
            channel="chan",
            response=DummyResponse(),
            followup=_types.SimpleNamespace(),
        )

        async def edit_original_response(**kwargs: Any) -> None:
            interaction.response.edited.append(kwargs)

        interaction.edit_original_response = edit_original_response

        btn = OpenStemmenButton()
        with patch(f"{MODULE}.is_paused", return_value=False), patch(
            f"{MODULE}.create_poll_button_views_per_day",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(f"{MODULE}._cleanup_outdated_messages_for_channel", new_callable=AsyncMock):
            await btn.callback(cast(Any, interaction))

        # Eerste response: "Poll wordt bijgewerkt..."
        self.assertEqual(len(interaction.response.sent), 1)
        msg, _ = interaction.response.sent[0]
        self.assertIn("Poll wordt bijgewerkt", msg)

        # Edit response: "Stemmen is gesloten..."
        self.assertEqual(len(interaction.response.edited), 1)
        self.assertIn("Stemmen is gesloten", interaction.response.edited[0]["content"])

    async def test_callback_happy_path_instruction_and_followups(self) -> None:
        # Eén instructiebericht + followup per dag
        class DummyResponse:
            def __init__(self) -> None:
                self.sent: list[tuple[str, dict[str, Any]]] = []
                self.edited: list[dict[str, Any]] = []

            def is_done(self) -> bool:
                return False

            async def send_message(self, content: str, **kwargs: Any) -> None:
                self.sent.append((content, kwargs))

        class DummyFollowup:
            def __init__(self) -> None:
                self.sent: list[tuple[str, Any, dict[str, Any]]] = []

            async def send(self, content: str, **kwargs: Any) -> None:
                view = kwargs.get("view")
                metadata = kwargs.get("metadata", {})
                self.sent.append((content, view, metadata))

        fake_view1 = MagicMock()
        fake_view2 = MagicMock()
        views = [
            ("vrijdag", "📅 **Vrijdag** — kies jouw tijden 👇", fake_view1),
            ("zaterdag", "📅 **Zaterdag** — kies jouw tijden 👇", fake_view2),
        ]

        interaction = _types.SimpleNamespace(
            channel_id=123,
            user=_types.SimpleNamespace(id=1),
            guild_id=7,
            guild=_types.SimpleNamespace(id=7),
            channel="chan",
            response=DummyResponse(),
            followup=DummyFollowup(),
        )

        async def edit_original_response(**kwargs: Any) -> None:
            interaction.response.edited.append(kwargs)

        interaction.edit_original_response = edit_original_response

        btn = OpenStemmenButton()
        with patch(f"{MODULE}.is_paused", return_value=False), patch(
            f"{MODULE}.create_poll_button_views_per_day",
            new_callable=AsyncMock,
            return_value=views,
        ), patch(f"{MODULE}._cleanup_outdated_messages_for_channel", new_callable=AsyncMock):
            await btn.callback(cast(Any, interaction))

        # Eerste response: "Poll wordt bijgewerkt..."
        self.assertEqual(len(interaction.response.sent), 1)
        msg, _ = interaction.response.sent[0]
        self.assertIn("Poll wordt bijgewerkt", msg)

        # Edit response: "Kies jouw tijden hieronder..."
        self.assertEqual(len(interaction.response.edited), 1)
        self.assertIn("Kies jouw tijden hieronder", interaction.response.edited[0]["content"])

        # 2 followups, headers en juiste view object
        self.assertEqual(len(interaction.followup.sent), 2)
        self.assertIn("Vrijdag", interaction.followup.sent[0][0])
        self.assertIs(interaction.followup.sent[0][1], fake_view1)
        self.assertIn("Zaterdag", interaction.followup.sent[1][0])
        self.assertIs(interaction.followup.sent[1][1], fake_view2)

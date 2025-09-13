# tests/test_poll_button_visibility_closed.py

from __future__ import annotations

import types as _types
from importlib import import_module
from typing import Any, cast
from unittest.mock import AsyncMock, patch

from tests.base import BaseTestCase

_pb = import_module("apps.ui.poll_buttons")
MODULE = _pb.__name__
PollButton = _pb.PollButton
ButtonStyle = _pb.ButtonStyle


class TestPollButtonVisibilityClosed(BaseTestCase):
    """Dek het pad waar de stemmogelijkheid gesloten is (regels ~73-86 + 102)."""

    async def test_closed_edits_message_when_message_exists(self) -> None:
        # interaction.message is aanwezig → message.edit(...) wordt gebruikt
        edit_calls: list[tuple[str, Any]] = []

        class DummyMessage:
            async def edit(self, *, content: str, view: Any | None) -> None:
                edit_calls.append((content, view))

        class DummyResponse:
            def is_done(self) -> bool:
                return False

            async def edit_message(self, *args: Any, **kwargs: Any) -> None:
                pass  # eerder geprobeerd; mag falen in app, hier niet relevant

        interaction = _types.SimpleNamespace(
            channel_id=123,
            user=_types.SimpleNamespace(id=1),
            guild_id=7,
            guild=_types.SimpleNamespace(id=7),
            channel="chan",
            response=DummyResponse(),
            followup=_types.SimpleNamespace(),
            message=DummyMessage(),
            edit_original_response=AsyncMock(),
        )

        btn = PollButton("vrijdag", "om 19:00 uur", "Test", ButtonStyle.secondary)

        with patch(f"{MODULE}.is_vote_button_visible", return_value=False), patch(
            f"{MODULE}.toggle_vote", new_callable=AsyncMock
        ) as toggle_mock:
            await btn.callback(cast(Any, interaction))
            toggle_mock.assert_not_called()

        self.assertEqual(len(edit_calls), 1)
        content, view = edit_calls[0]
        self.assertIn("❌ De stemmogelijkheid is gesloten", content)
        self.assertIsNone(view)

    async def test_closed_edits_original_when_no_message(self) -> None:
        # interaction.message is None → edit_original_response(...)
        edit_original = AsyncMock()

        class DummyResponse:
            def is_done(self) -> bool:
                return False

            async def edit_message(self, *args: Any, **kwargs: Any) -> None:
                pass

        interaction = _types.SimpleNamespace(
            channel_id=123,
            user=_types.SimpleNamespace(id=1),
            guild_id=7,
            guild=_types.SimpleNamespace(id=7),
            channel="chan",
            response=DummyResponse(),
            followup=_types.SimpleNamespace(),
            message=None,
            edit_original_response=edit_original,
        )

        btn = PollButton("vrijdag", "om 19:00 uur", "Test", ButtonStyle.secondary)

        with patch(f"{MODULE}.is_vote_button_visible", return_value=False):
            await btn.callback(cast(Any, interaction))

        edit_original.assert_awaited()
        # inhoud controleren is voldoende
        args, kwargs = edit_original.call_args
        self.assertIn("❌ De stemmogelijkheid is gesloten", kwargs.get("content", ""))

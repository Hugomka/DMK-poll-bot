# tests/test_poll_button_exception_path.py

from __future__ import annotations

import types as _types
from importlib import import_module
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

from tests.base import BaseTestCase

_pb = import_module("apps.ui.poll_buttons")
MODULE = _pb.__name__
PollButton = _pb.PollButton
ButtonStyle = _pb.ButtonStyle


class TestPollButtonExceptionPath(BaseTestCase):
    """Dek het except-herstelpad (regels ~125-149)."""

    async def test_toggle_raises_then_recovery_edits_message_with_new_view(
        self,
    ) -> None:
        # Forceer toggle_vote om te falen → except-blok moet nieuwe view tonen
        class DummyMessage:
            def __init__(self) -> None:
                self.edits: list[tuple[str, Any]] = []

            async def edit(self, *, content: str, view: Any | None) -> None:
                self.edits.append((content, view))

        class DummyResponse:
            def is_done(self) -> bool:
                return False

            async def edit_message(self, *args: Any, **kwargs: Any) -> None:
                pass

        interaction = _types.SimpleNamespace(
            channel_id=123,
            user=_types.SimpleNamespace(id=5),
            guild_id=7,
            guild=_types.SimpleNamespace(id=7),
            channel=None,  # maakt niet uit; we willen het except-pad halen
            response=DummyResponse(),
            followup=_types.SimpleNamespace(),
            message=DummyMessage(),
            edit_original_response=AsyncMock(),
        )

        btn = PollButton("vrijdag", "om 19:00 uur", "Test", ButtonStyle.secondary)

        with patch(f"{MODULE}.is_vote_button_visible", return_value=True), patch(
            f"{MODULE}.toggle_vote", side_effect=RuntimeError("kapot")
        ), patch(
            f"{MODULE}.create_poll_button_view",
            new_callable=AsyncMock,
            return_value=MagicMock(),
        ):
            await btn.callback(cast(Any, interaction))

        # Er moet een herstelbericht zijn gezet op interaction.message.edit(...)
        self.assertGreater(len(interaction.message.edits), 0)
        content, view = interaction.message.edits[-1]
        self.assertIn("⚠️ Er ging iets mis, probeer opnieuw", content)
        self.assertIsNotNone(view)

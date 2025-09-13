# tests/test_poll_button_paused_paths.py

from __future__ import annotations

import types as _types
from importlib import import_module
from typing import Any, cast
from unittest.mock import patch

from tests.base import BaseTestCase

_pb = import_module("apps.ui.poll_buttons")
MODULE = _pb.__name__
PollButton = _pb.PollButton
ButtonStyle = _pb.ButtonStyle


class TestPollButtonPausedPaths(BaseTestCase):
    """Dek het 'is_paused' pad (regels rond 61->71 / 66-68)."""

    async def test_paused_response_when_is_done_false_uses_response_send(self) -> None:
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
                raise AssertionError("followup.send hoort niet gebruikt te worden")

        interaction = _types.SimpleNamespace(
            channel_id=123,
            user=_types.SimpleNamespace(id=42),
            guild_id=7,
            guild=_types.SimpleNamespace(id=7),
            channel="chan",
            response=DummyResponse(),
            followup=DummyFollowup(),
        )

        btn = PollButton("vrijdag", "om 19:00 uur", "Test", ButtonStyle.secondary)

        with patch(f"{MODULE}.is_paused", return_value=True):
            await btn.callback(cast(Any, interaction))

        self.assertEqual(len(interaction.response.sent), 1)
        msg, kw = interaction.response.sent[0]
        self.assertIn("⏸️ Stemmen is gepauzeerd", msg)
        self.assertTrue(kw.get("ephemeral", False))

    async def test_paused_response_when_is_done_true_uses_followup(self) -> None:
        class DummyResponse:
            def __init__(self) -> None:
                self._done = True

            def is_done(self) -> bool:
                return self._done

            async def send_message(
                self, *args: Any, **kwargs: Any
            ) -> None:  # pragma: no cover
                raise AssertionError(
                    "response.send_message hoort niet gebruikt te worden"
                )

        class DummyFollowup:
            def __init__(self) -> None:
                self.sent: list[tuple[str, dict[str, Any]]] = []

            async def send(self, content: str, **kwargs: Any) -> None:
                self.sent.append((content, kwargs))

        interaction = _types.SimpleNamespace(
            channel_id=123,
            user=_types.SimpleNamespace(id=42),
            guild_id=7,
            guild=_types.SimpleNamespace(id=7),
            channel="chan",
            response=DummyResponse(),
            followup=DummyFollowup(),
        )

        btn = PollButton("vrijdag", "om 19:00 uur", "Test", ButtonStyle.secondary)

        with patch(f"{MODULE}.is_paused", return_value=True):
            await btn.callback(cast(Any, interaction))

        self.assertEqual(len(interaction.followup.sent), 1)
        msg, kw = interaction.followup.sent[0]
        self.assertIn("⏸️ Stemmen is gepauzeerd", msg)
        self.assertTrue(kw.get("ephemeral", False))

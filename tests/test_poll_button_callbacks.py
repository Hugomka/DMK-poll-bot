# tests/test_poll_button_callbacks.py

from __future__ import annotations

import types as _types
from importlib import import_module
from typing import Any, List, cast
from unittest.mock import AsyncMock, MagicMock, patch

from tests.base import BaseTestCase

_pb = import_module("apps.ui.poll_buttons")
MODULE = _pb.__name__
PollButton = _pb.PollButton
ButtonStyle = _pb.ButtonStyle


class TestPollButtonCallbacks(BaseTestCase):
    """Gedrag van de `PollButton.callback`."""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.button = PollButton(
            dag="vrijdag",
            tijd="om 19:00 uur",
            label="Test",
            stijl=ButtonStyle.secondary,
        )

    async def test_callback_success_flow(self) -> None:
        """
        Blij‑pad: stem toggelen, nieuwe view bouwen en update van publiek
        pollbericht plannen.
        """

        class DummyResponse:
            """Houdt bij of we het bestaande ephemeral bericht bewerken."""

            def __init__(self) -> None:
                self.done = False
                self.edited: List[Any] = []

            def is_done(self) -> bool:
                return self.done

            async def edit_message(
                self, *, content: str | None = None, view: Any | None = None
            ) -> None:
                self.edited.append((content, view))

            async def send_message(self, *args: Any, **kwargs: Any) -> None:
                raise AssertionError(
                    "send_message zou hier niet mogen worden aangeroepen"
                )

        class DummyFollowup:
            """Noteert follow‑up berichten (verwachten we hier niet)."""

            def __init__(self) -> None:
                self.sent: List[Any] = []

            async def send(self, content: str | None = None, **kwargs: Any) -> None:
                self.sent.append((content, kwargs))

        dummy_response = DummyResponse()
        dummy_followup = DummyFollowup()
        edit_original = AsyncMock()
        interaction = _types.SimpleNamespace(
            channel_id=123,
            user=_types.SimpleNamespace(id=42),
            guild_id=7,
            guild=_types.SimpleNamespace(id=7),
            channel="channel",
            response=dummy_response,
            followup=dummy_followup,
            message=None,
            edit_original_response=edit_original,
        )

        created_tasks: list[Any] = []

        def _fake_create_task(coro: Any) -> None:
            created_tasks.append(coro)
            return None

        with patch(f"{MODULE}.is_paused", return_value=False), patch(
            f"{MODULE}.is_vote_button_visible", return_value=True
        ), patch(f"{MODULE}.toggle_vote", new_callable=AsyncMock) as toggle_mock, patch(
            f"{MODULE}.create_poll_button_view",
            new_callable=AsyncMock,
            return_value=MagicMock(),
        ) as create_view_mock, patch(
            f"{MODULE}.update_poll_message", new_callable=AsyncMock
        ) as update_mock:
            await self.button.callback(cast(Any, interaction))
            # geef de event loop een tick zodat de task (update_poll_message) kan afronden
            import asyncio

            await asyncio.sleep(0)

            toggle_mock.assert_awaited_once_with(
                "42", "vrijdag", "om 19:00 uur", 7, 123
            )
            create_view_mock.assert_awaited_once_with("42", 7, 123, dag="vrijdag")
            update_mock.assert_awaited_once_with(interaction.channel, "vrijdag")
            self.assertEqual(len(dummy_response.edited), 1)
            edited_content, _ = dummy_response.edited[0]
            self.assertIn("Je stem wordt verwerkt", edited_content)
            edit_original.assert_awaited()

    async def test_callback_no_channel(self) -> None:
        """
        Geen kanaal → meteen waarschuwing sturen en niet proberen te stemmen.
        """

        class DummyResponse:
            def __init__(self) -> None:
                self.done = False
                self.sent_via_response = False

            def is_done(self) -> bool:
                return self.done

            async def send_message(self, content: str, **kwargs: Any) -> None:
                self.sent_via_response = True

            async def edit_message(
                self, *, content: str | None = None, view: Any | None = None
            ) -> None:
                pass  # niet gebruikt

        class DummyFollowup:
            def __init__(self) -> None:
                self.sent_via_followup = False

            async def send(self, content: str, **kwargs: Any) -> None:
                self.sent_via_followup = True

        dummy_response = DummyResponse()
        dummy_followup = DummyFollowup()
        interaction = _types.SimpleNamespace(
            channel_id=None,
            user=_types.SimpleNamespace(id=1),
            guild_id=0,
            guild=None,
            channel=None,
            response=dummy_response,
            followup=dummy_followup,
            message=None,
            edit_original_response=AsyncMock(),
        )

        with patch(f"{MODULE}.is_paused", return_value=False), patch(
            f"{MODULE}.toggle_vote", new_callable=AsyncMock
        ) as toggle_mock:
            await self.button.callback(cast(Any, interaction))
            toggle_mock.assert_not_called()
            self.assertTrue(dummy_response.sent_via_response)
            self.assertFalse(dummy_followup.sent_via_followup)

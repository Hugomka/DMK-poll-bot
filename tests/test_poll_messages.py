# tests/test_poll_message.py

from __future__ import annotations

import asyncio
import io
import os
from contextlib import redirect_stdout
from types import SimpleNamespace
from typing import Callable, Optional
from unittest.mock import patch

from apps.utils import poll_message
from tests.base import BaseTestCase

# Kleine helpers/mocks


def mk_channel(channel_id: int = 222, guild_id: int = 111):
    """
    Maakt een simpel channel-object met id en guild.
    Methods (fetch_message/send) hangen we per test via monkeypatch op.
    """
    ch = SimpleNamespace()
    ch.id = channel_id
    ch.guild = SimpleNamespace(id=guild_id)
    return ch


def mk_msg(msg_id: int = 999):
    class _Msg:
        def __init__(self, mid: int):
            self.id = mid
            self.edited = []

        async def edit(self, *, content=None, view=None):
            self.edited.append({"content": content, "view": view})

    return _Msg(msg_id)


async def _safe_call_passthrough(fn: Optional[Callable], *args, **kwargs):
    """
    Eenvoudige safe_call vervanger: roept fn aan (async of sync).
    """
    if fn is None:
        return None
    res = fn(*args, **kwargs)
    if asyncio.iscoroutine(res):
        return await res
    return res


# ================================================================
#                     TESTS
# ================================================================
class TestPollMessage(BaseTestCase):
    # _load() except JSONDecodeError → fallback {}
    async def test_load_corrupt_file_uses_empty(self):
        path = os.environ["POLL_MESSAGE_FILE"]
        with open(path, "w", encoding="utf-8") as f:
            f.write("{ this is not valid json")

        # Roep iets dat _load() gebruikt, bv. get_message_id
        mid = poll_message.get_message_id(123, "vrijdag")
        self.assertIsNone(mid)  # data == {}

    # save/get/clear_message_id
    async def test_save_get_clear_message_id(self):
        poll_message.save_message_id(7, "vrijdag", 1010)
        self.assertEqual(poll_message.get_message_id(7, "vrijdag"), 1010)

        poll_message.clear_message_id(7, "vrijdag")
        self.assertIsNone(poll_message.get_message_id(7, "vrijdag"))

    # Set_channel_disabled / is_channel_disabled + early return in update_poll_message
    async def test_update_poll_message_skips_when_channel_disabled(self):
        # Channel disabled → update_poll_message moet direct returnen
        ch = mk_channel(channel_id=333)

        called = {"builder": 0}

        async def fake_builder(*args, **kwargs):
            called["builder"] += 1
            return "CONTENT"

        poll_message.set_channel_disabled(333, True)
        with patch(
            "apps.utils.poll_message.safe_call", side_effect=_safe_call_passthrough
        ), patch(
            "apps.utils.poll_message.build_poll_message_for_day_async",
            side_effect=fake_builder,
        ):
            await poll_message.update_poll_message(ch, dag="vrijdag")

        self.assertEqual(called["builder"], 0)  # niets aangeroepen

        # Weer inschakelen, en dan moet hij bouwen
        poll_message.set_channel_disabled(333, False)
        with patch(
            "apps.utils.poll_message.safe_call", side_effect=_safe_call_passthrough
        ), patch(
            "apps.utils.poll_message.build_poll_message_for_day_async",
            side_effect=fake_builder,
        ), patch(
            "apps.utils.poll_message.get_message_id", return_value=None
        ), patch(
            "apps.utils.poll_message.should_hide_counts", return_value=False
        ), patch(
            "apps.utils.poll_message.build_decision_line", return_value=""
        ):
            # Mock send op channel
            sent = []

            async def fake_send(*, content=None, view=None):
                m = SimpleNamespace(id=12345, content=content)
                sent.append(m)
                return m

            ch.send = fake_send
            await poll_message.update_poll_message(ch, dag="vrijdag")
            self.assertEqual(called["builder"], 1)
            self.assertEqual(len(sent), 1)

    # schedule_poll_update (debounce en key (cid, dag))
    async def test_schedule_poll_update_debounce(self):
        ch = mk_channel(channel_id=444)

        calls = []

        async def fake_update(channel, dag=None):
            calls.append((getattr(channel, "id", 0), dag))

        with patch(
            "apps.utils.poll_message.update_poll_message", side_effect=fake_update
        ):
            # Twee keer snel achter elkaar met delay=0 → eerste wordt gecanceld
            t1 = poll_message.schedule_poll_update(ch, "vrijdag", delay=0)
            t2 = poll_message.schedule_poll_update(ch, "vrijdag", delay=0)
            await asyncio.gather(t1, t2, return_exceptions=True)

        # Slechts 1 call door debounce
        self.assertEqual(calls, [(444, "vrijdag")])

    # schedule_poll_update met delay > 0 en cancel
    async def test_schedule_poll_update_delay_and_cancel(self):
        ch = mk_channel(channel_id=445)

        calls = []

        async def fake_update(channel, dag=None):
            calls.append((getattr(channel, "id", 0), dag))

        # Start met positieve delay zodat _runner gaat slapen
        with patch(
            "apps.utils.poll_message.update_poll_message", side_effect=fake_update
        ):
            t = poll_message.schedule_poll_update(ch, "vrijdag", delay=0.2)

            # Cancel vóór het afgaat → triggert asyncio.CancelledError in _runner
            await asyncio.sleep(0.01)
            t.cancel()

            # Geen exception naar buiten; _runner vangt CancelledError en returnt
            await asyncio.gather(t, return_exceptions=True)

        # Door cancel is update_poll_message niet aangeroepen
        self.assertEqual(calls, [])

    # Update flow – edit-pad (mid aanwezig en message editable)
    async def test_update_flow_edit_existing_message(self):
        ch = mk_channel(channel_id=555)

        # Mid aanwezig
        with patch("apps.utils.poll_message.get_message_id", return_value=777), patch(
            "apps.utils.poll_message.should_hide_counts", return_value=False
        ), patch(
            "apps.utils.poll_message.build_decision_line", return_value="DECISION"
        ), patch(
            "apps.utils.poll_message.build_poll_message_for_day_async",
            return_value="CONTENT",
        ), patch(
            "apps.utils.poll_message.safe_call", side_effect=_safe_call_passthrough
        ):

            # Fetch_message geeft een bericht terug (edit-pad)
            msg = mk_msg(777)

            async def fake_fetch(mid):
                self.assertEqual(mid, 777)
                return msg

            ch.fetch_message = fake_fetch

            edited = []

            async def fake_edit(*, content=None, view=None):
                edited.append({"content": content, "view": view})

            # Hang edit op msg
            msg.edit = fake_edit

            await poll_message.update_poll_message(ch, dag="vrijdag")

            # Edit moet zijn aangeroepen, geen send
            self.assertTrue(len(edited) == 1)

    # Update flow – mid bestaat maar fetch geeft None → clear + create
    async def test_update_flow_fetch_none_then_create(self):
        ch = mk_channel(channel_id=556)

        with patch("apps.utils.poll_message.get_message_id", return_value=888), patch(
            "apps.utils.poll_message.should_hide_counts", return_value=False
        ), patch("apps.utils.poll_message.build_decision_line", return_value=""), patch(
            "apps.utils.poll_message.build_poll_message_for_day_async",
            return_value="CONTENT",
        ), patch(
            "apps.utils.poll_message.safe_call", side_effect=_safe_call_passthrough
        ) as sc, patch(
            "apps.utils.poll_message.clear_message_id"
        ) as clear_id, patch(
            "apps.utils.poll_message.save_message_id"
        ) as save_id:

            async def fake_fetch(mid):
                return None  # Forceer clear + create

            async def fake_send(*, content=None, view=None):
                return SimpleNamespace(id=99999, content=content)

            ch.fetch_message = fake_fetch
            ch.send = fake_send

            await poll_message.update_poll_message(ch, dag="zaterdag")

            clear_id.assert_called_once_with(556, "zaterdag")
            save_id.assert_called_once()  # Aangemaakt

    # Update flow – NotFound → clear + create
    async def test_update_flow_fetch_raises_notfound_then_create(self):
        ch = mk_channel(channel_id=557)

        class DummyNotFound(Exception):
            pass

        # Patch discord.NotFound/HTTPException lokaal in de module
        with patch.object(
            poll_message.discord, "NotFound", DummyNotFound, create=True
        ), patch("apps.utils.poll_message.get_message_id", return_value=999), patch(
            "apps.utils.poll_message.should_hide_counts", return_value=False
        ), patch(
            "apps.utils.poll_message.build_decision_line", return_value=""
        ), patch(
            "apps.utils.poll_message.build_poll_message_for_day_async",
            return_value="CONTENT",
        ), patch(
            "apps.utils.poll_message.safe_call", side_effect=_safe_call_passthrough
        ), patch(
            "apps.utils.poll_message.clear_message_id"
        ) as clear_id, patch(
            "apps.utils.poll_message.save_message_id"
        ) as save_id:

            async def fake_fetch(mid):
                raise DummyNotFound()

            async def fake_send(*, content=None, view=None):
                return SimpleNamespace(id=123456)

            ch.fetch_message = fake_fetch
            ch.send = fake_send

            await poll_message.update_poll_message(ch, dag="zondag")
            clear_id.assert_called_once_with(557, "zondag")
            save_id.assert_called_once()

    # Update flow – HTTPException code 30046 → stil negeren
    async def test_update_flow_http_30046_is_ignored(self):
        ch = mk_channel(channel_id=558)

        class DummyHTTPException(Exception):
            def __init__(self, code=None):
                super().__init__("dummy")
                self.code = code

        with patch.object(
            poll_message.discord, "HTTPException", DummyHTTPException, create=True
        ), patch("apps.utils.poll_message.get_message_id", return_value=111), patch(
            "apps.utils.poll_message.should_hide_counts", return_value=False
        ), patch(
            "apps.utils.poll_message.build_decision_line", return_value=""
        ), patch(
            "apps.utils.poll_message.build_poll_message_for_day_async",
            return_value="CONTENT",
        ), patch(
            "apps.utils.poll_message.safe_call", side_effect=_safe_call_passthrough
        ):

            async def fake_fetch(mid):
                # Simulate edit die HTTP 30046 gooit
                class _Msg:
                    async def edit(self, *, content=None, view=None):
                        raise DummyHTTPException(code=30046)

                return _Msg()

            ch.fetch_message = fake_fetch

            # Geen exception en geen create
            created = []

            async def fake_send(*, content=None, view=None):
                created.append(True)
                return SimpleNamespace(id=42)

            ch.send = fake_send
            await poll_message.update_poll_message(ch, dag="vrijdag")
            self.assertEqual(created, [])  # Niet aangemaakt

    # Update flow – HTTPException andere code → log en continue (geen create)
    async def test_update_flow_http_other_logs_and_skips_create(self):
        ch = mk_channel(channel_id=559)

        class DummyHTTPException(Exception):
            def __init__(self, code=None):
                super().__init__("dummy")
                self.code = code

        with patch.object(
            poll_message.discord, "HTTPException", DummyHTTPException, create=True
        ), patch("apps.utils.poll_message.get_message_id", return_value=112), patch(
            "apps.utils.poll_message.should_hide_counts", return_value=False
        ), patch(
            "apps.utils.poll_message.build_decision_line", return_value=""
        ), patch(
            "apps.utils.poll_message.build_poll_message_for_day_async",
            return_value="CONTENT",
        ), patch(
            "apps.utils.poll_message.safe_call", side_effect=_safe_call_passthrough
        ):

            async def fake_fetch(mid):
                class _Msg:
                    async def edit(self, *, content=None, view=None):
                        raise DummyHTTPException(code=99999)

                return _Msg()

            ch.fetch_message = fake_fetch

            buf = io.StringIO()
            created = []

            async def fake_send(*, content=None, view=None):
                created.append(True)
                return SimpleNamespace(id=77)

            ch.send = fake_send

            # Stdout cap om de print te vangen
            with redirect_stdout(buf):
                await poll_message.update_poll_message(ch, dag="zaterdag")

            out = buf.getvalue()
            self.assertIn("Fout bij updaten voor zaterdag", out)
            self.assertEqual(created, [])  # Geen create na de fout

    # Create-pad – geen mid → send + save
    async def test_update_flow_create_when_no_mid(self):
        ch = mk_channel(channel_id=560)

        with patch("apps.utils.poll_message.get_message_id", return_value=None), patch(
            "apps.utils.poll_message.should_hide_counts", return_value=True
        ), patch(
            "apps.utils.poll_message.build_decision_line", return_value="DEC"
        ), patch(
            "apps.utils.poll_message.build_poll_message_for_day_async",
            return_value="CONTENT",
        ), patch(
            "apps.utils.poll_message.safe_call", side_effect=_safe_call_passthrough
        ), patch(
            "apps.utils.poll_message.save_message_id"
        ) as save_id:

            created = []

            async def fake_send(*, content=None, view=None):
                created.append(content)
                return SimpleNamespace(id=9090)

            ch.send = fake_send
            await poll_message.update_poll_message(ch, dag="vrijdag")

            self.assertEqual(len(created), 1)
            # Decision werd toegevoegd aan content
            self.assertIn("DEC", created[0])
            save_id.assert_called_once_with(560, "vrijdag", 9090)

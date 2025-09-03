# tests/test_poll_message_updates.py

from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from apps.utils.poll_message import update_poll_message
from apps.utils.poll_message import save_message_id as _save_message_id
from tests.base import BaseTestCase

# Helper: fake message met edit
class FakeMsg:
    def __init__(self, mid=1111):
        self.id = mid
        self.edited = False
    async def edit(self, **kwargs):
        self.edited = True

# Helper: fake channel met fetch/send
class FakeChannel:
    def __init__(self):
        self.id = 123 
        self.sent = []
        self.fetched = {}
        self.guild = SimpleNamespace()  # gebruikt door builder

    async def fetch_message(self, mid):
        if mid in self.fetched:
            return self.fetched[mid]
        raise Exception("not found")

    async def send(self, content=None, view=None):
        m = FakeMsg()
        self.sent.append((content, view))
        return m
    
async def _fake_build_poll_message_for_day_async(dag, **kwargs):
    return f"poll for {dag}"

class TestPollMessageUpdates(BaseTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()

    async def test_update_edits_existing_message(self):
        ch = FakeChannel()
        msg = FakeMsg()
        ch.fetched[111] = msg

        with patch("apps.utils.poll_message.get_message_id", return_value=111),\
            patch("apps.utils.poll_message.build_poll_message_for_day_async",\
            side_effect=_fake_build_poll_message_for_day_async):
            await update_poll_message(ch, "vrijdag")

        assert msg.edited is True
        assert ch.sent == []

    async def test_update_creates_message_when_missing(self):
        ch = FakeChannel()

        with patch("apps.utils.poll_message.get_message_id",\
            return_value=None), patch("apps.utils.poll_message.build_poll_message_for_day_async",\
            side_effect=_fake_build_poll_message_for_day_async),\
            patch("apps.utils.poll_message.save_message_id") as save_id:
            await update_poll_message(ch, "zaterdag")

        assert len(ch.sent) == 1
        save_id.assert_called()

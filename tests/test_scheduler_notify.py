# tests/test_scheduler_notify.py

from unittest.mock import patch
from tests.base import BaseTestCase
from apps.scheduler import notify_voters_if_avond_gaat_door

class FakeMember:
    def __init__(self, uid):
        self.id = uid
        self.mention = f"<@{uid}>"

class FakeChannel:
    def __init__(self):
        self.id = 999
        self.sent = []
    async def send(self, content):
        self.sent.append(content)

class FakeGuild:
    def __init__(self, members):
        self.id = 1
        self._members = {m.id: m for m in members}
        self.text_channels = [FakeChannel()]
    def get_member(self, uid):
        return self._members.get(uid)

class FakeBot:
    def __init__(self, guilds):
        self.guilds = guilds

class TestSchedulerNotify(BaseTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()

    async def test_notify_sends_when_6_or_more_votes(self):
        votes = {
            "1": {"vrijdag": ["om 20:30 uur"]},
            "2": {"vrijdag": ["om 20:30 uur"]},
            "3": {"vrijdag": ["om 20:30 uur"]},
            "4": {"vrijdag": ["om 20:30 uur"]},
            "5": {"vrijdag": ["om 20:30 uur"]},
            "6": {"vrijdag": ["om 20:30 uur"]},
        }

        async def fake_load_votes():
            return votes

        with patch("apps.scheduler.get_message_id", return_value=111), \
             patch("apps.scheduler.load_votes", side_effect=fake_load_votes):
            g = FakeGuild([FakeMember(int(i)) for i in votes.keys()])
            bot = FakeBot([g])

            await notify_voters_if_avond_gaat_door(bot, "vrijdag")

            ch = g.text_channels[0]
            assert len(ch.sent) == 1
            assert "20:30" in ch.sent[0]

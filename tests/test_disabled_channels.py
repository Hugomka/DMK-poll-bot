# tests/test_disabled_channels.py

import importlib
import os
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from tests.base import BaseTestCase


class DisabledChannelsTests(BaseTestCase):

    async def asyncSetUp(self):
        await super().asyncSetUp()
        if "apps.utils.poll_message" in sys.modules:
            import apps.utils.poll_message as poll_message

            importlib.reload(poll_message)
        else:
            import apps.utils.poll_message as poll_message

    def setUp(self):
        # Gebruik een tijdelijk JSON-bestand voor poll_message opslag
        self.tmpdir = tempfile.TemporaryDirectory()
        self.json_path = os.path.join(self.tmpdir.name, "poll_message.json")
        os.environ["POLL_MESSAGE_FILE"] = self.json_path

        # Module opnieuw laden zodat hij de env var oppakt
        # (import pas hier doen zodat reload werkt)
        global poll_message
        if "apps.utils.poll_message" in globals():
            import apps.utils.poll_message as poll_message  # noqa: F401

            importlib.reload(poll_message)
        else:
            import apps.utils.poll_message as poll_message  # noqa: F401
        self.pm = poll_message

    def tearDown(self):
        self.tmpdir.cleanup()

    # Helpers voor fake Discord objecten
    class FakeGuild:
        def __init__(self, gid=1234):
            self.id = gid

    class FakeMessage:
        def __init__(self, mid=999):
            self.id = mid

        async def edit(self, **kwargs):
            return None

    class FakeChannel:
        def __init__(self, cid=5678, guild=None):
            self.id = cid
            self.guild = guild or DisabledChannelsTests.FakeGuild()

        async def send(self, **kwargs):
            # In test 2 willen we kunnen detecteren of dit NIET wordt aangeroepen
            return DisabledChannelsTests.FakeMessage()

    # 1) Verwijderen zet kanaal uit (persistent gedrag)
    def test_set_channel_disabled_persists(self):
        ch_id = 111
        # Vooraf: zou False moeten zijn
        self.assertFalse(self.pm.is_channel_disabled(ch_id))

        # Zet uit
        self.pm.set_channel_disabled(ch_id, True)

        # Herlaad module om persistence te simuleren
        importlib.reload(self.pm)

        self.assertTrue(self.pm.is_channel_disabled(ch_id))

    # 2) update_poll_message slaat disabled kanaal over
    async def test_update_poll_message_skips_disabled_channel(self):
        ch = self.FakeChannel(cid=222)

        # Markeer kanaal als disabled
        self.pm.set_channel_disabled(ch.id, True)
        self.assertTrue(self.pm.is_channel_disabled(ch.id))

        # Patch alles wat side-effects kan geven
        # - build_poll_message_for_day_async: simpele string
        # - build_decision_line: geen besluit
        # - save_message_id: mag NIET worden aangeroepen
        # - channel.send: mag NIET worden aangeroepen
        with patch(
            "apps.utils.poll_message.build_poll_message_for_day_async",
            new=AsyncMock(return_value="content"),
        ), patch(
            "apps.utils.poll_message.build_decision_line",
            new=AsyncMock(return_value=""),
        ), patch(
            "apps.utils.poll_message.save_message_id"
        ) as save_mid, patch.object(
            ch, "send", new=AsyncMock()
        ) as send_mock:

            await self.pm.update_poll_message(ch, "vrijdag")

            # Omdat kanaal disabled is: geen nieuwe berichten en geen opslag
            save_mid.assert_not_called()
            send_mock.assert_not_called()

    # 3) Poll-on zet kanaal weer aan (basisgedrag)
    def test_enable_channel_again(self):
        ch_id = 333
        self.pm.set_channel_disabled(ch_id, True)
        self.assertTrue(self.pm.is_channel_disabled(ch_id))

        self.pm.set_channel_disabled(ch_id, False)
        self.assertFalse(self.pm.is_channel_disabled(ch_id))


if __name__ == "__main__":
    unittest.main()

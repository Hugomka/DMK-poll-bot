import os
import unittest

from apps.utils.poll_storage import reset_votes

class BaseTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        os.environ["VOTES_FILE"] = "votes_test.json"
        os.environ["POLL_MESSAGE_FILE"] = "poll_message_test.json"
        os.environ["SETTINGS_FILE"] = "poll_settings_test.json"

    async def asyncTearDown(self):
        for bestand in ["votes_test.json", "poll_message_test.json", "poll_settings_test.json"]:
            if os.path.exists(bestand):
                os.remove(bestand)

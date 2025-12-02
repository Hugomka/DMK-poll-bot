# tests/base.py

import os
import tempfile
import unittest


class BaseTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Create temp files for this test
        self.temp_votes_file = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix="_votes.json", encoding="utf-8"
        )
        self.temp_votes_file.close()

        self.temp_message_file = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix="_poll_message.json", encoding="utf-8"
        )
        self.temp_message_file.close()

        self.temp_settings_file = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix="_poll_settings.json", encoding="utf-8"
        )
        self.temp_settings_file.close()

        # Set environment variables to temp files
        # (poll_storage uses get_votes_path() which reads from env)
        self.original_votes_env = os.environ.get("VOTES_FILE")
        self.original_message_env = os.environ.get("POLL_MESSAGE_FILE")
        self.original_settings_env = os.environ.get("SETTINGS_FILE")

        os.environ["VOTES_FILE"] = self.temp_votes_file.name
        os.environ["POLL_MESSAGE_FILE"] = self.temp_message_file.name
        os.environ["SETTINGS_FILE"] = self.temp_settings_file.name

        # Patch module-level constants (for poll_message and poll_settings)
        from apps.utils import poll_message, poll_settings

        self.original_message_file = poll_message.POLL_MESSAGE_FILE
        self.original_settings_file = poll_settings.SETTINGS_FILE

        poll_message.POLL_MESSAGE_FILE = self.temp_message_file.name
        poll_settings.SETTINGS_FILE = self.temp_settings_file.name

        # Reset votes (uses env var via get_votes_path())
        from apps.utils.poll_storage import reset_votes
        await reset_votes()

    async def asyncTearDown(self):
        # Restore original file paths
        from apps.utils import poll_message, poll_settings

        poll_message.POLL_MESSAGE_FILE = self.original_message_file
        poll_settings.SETTINGS_FILE = self.original_settings_file

        # Restore environment variables
        if self.original_votes_env is not None:
            os.environ["VOTES_FILE"] = self.original_votes_env
        else:
            os.environ.pop("VOTES_FILE", None)

        if self.original_message_env is not None:
            os.environ["POLL_MESSAGE_FILE"] = self.original_message_env
        else:
            os.environ.pop("POLL_MESSAGE_FILE", None)

        if self.original_settings_env is not None:
            os.environ["SETTINGS_FILE"] = self.original_settings_env
        else:
            os.environ.pop("SETTINGS_FILE", None)

        # Clean up temp files
        for temp_file in [
            self.temp_votes_file.name,
            self.temp_message_file.name,
            self.temp_settings_file.name,
        ]:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception:
                pass

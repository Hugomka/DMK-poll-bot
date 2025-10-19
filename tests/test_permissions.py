# tests/test_permissions.py

import unittest

from discord import app_commands

from apps.commands.poll_lifecycle import PollLifecycle
from apps.commands.poll_votes import PollVotes
from apps.commands.poll_archive import PollArchive
from apps.commands.poll_guests import PollGuests
from apps.commands.poll_status import PollStatus


def _get_cmd(cog_class, attr_name):
    """Haalt het app command object op dat op de Cog-attribute is geplakt."""
    cmd = getattr(cog_class, attr_name, None)
    if cmd is None:
        raise AssertionError(
            f"Commando-attribute '{attr_name}' niet gevonden op {cog_class.__name__}"
        )
    if not isinstance(cmd, app_commands.Command):
        raise AssertionError(
            f"Attribute '{attr_name}' is geen app_commands.Command (type={type(cmd)})"
        )
    return cmd


class TestCommandDefaults(unittest.TestCase):
    def test_admin_mod_default_commands(self):
        admin_mod_cmds = {
            # (cog_class, attr_name): expected_slash_name
            (PollLifecycle, "on"): "dmk-poll-on",
            (PollLifecycle, "reset"): "dmk-poll-reset",
            (PollLifecycle, "pauze"): "dmk-poll-pauze",
            (PollLifecycle, "verwijderbericht"): "dmk-poll-verwijderen",
            (PollVotes, "stemmen"): "dmk-poll-stemmen",
            (PollArchive, "archief_download"): "dmk-poll-archief-download",
            (PollArchive, "archief_verwijderen"): "dmk-poll-archief-verwijderen",
            (PollStatus, "status"): "dmk-poll-status",
        }
        for (cog_class, attr), expected_name in admin_mod_cmds.items():
            cmd = _get_cmd(cog_class, attr)
            # Naam
            self.assertEqual(cmd.name, expected_name, f"Naam mismatch bij {attr}")
            # Guild-only
            self.assertTrue(
                getattr(cmd, "guild_only", False), f"{attr} moet guild_only=True zijn"
            )
            # Default permissions moeten admin of moderate_members bevatten
            dp = getattr(cmd, "default_permissions", None)
            self.assertIsNotNone(dp, f"{attr} moet default_permissions hebben")
            has_admin = getattr(dp, "administrator", False)
            has_moderate = getattr(dp, "moderate_members", False)
            self.assertTrue(
                has_admin or has_moderate,
                f"{attr} moet admin of moderate_members default hebben",
            )
            # Description hint: accepteer zowel (standaard: beheerder/moderator) als de losse varianten
            desc = getattr(cmd, "description", "") or ""
            self.assertTrue(
                any(
                    tag in desc
                    for tag in (
                        "(standaard: beheerder/moderator)",
                        "(standaard: beheerder)",
                        "(standaard: moderator)",
                    )
                ),
                f"{attr} description mist '(standaard: beheerder/moderator)' of '(standaard: beheerder)' of '(standaard: moderator)'",
            )

    def test_public_default_commands(self):
        public_cmds = {
            # (cog_class, attr_name): expected_slash_name
            (PollGuests, "gast_add"): "gast-add",
            (PollGuests, "gast_remove"): "gast-remove",
        }
        for (cog_class, attr), expected_name in public_cmds.items():
            cmd = _get_cmd(cog_class, attr)
            self.assertEqual(cmd.name, expected_name, f"Naam mismatch bij {attr}")
            self.assertTrue(
                getattr(cmd, "guild_only", False), f"{attr} moet guild_only=True zijn"
            )
            # Géén default_permissions => iedereen mag standaard
            dp = getattr(cmd, "default_permissions", None)
            self.assertTrue(
                dp is None or getattr(dp, "value", 0) == 0,
                f"{attr} moet géén default_permissions hebben",
            )


if __name__ == "__main__":
    unittest.main()

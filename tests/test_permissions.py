# tests/test_permissions.py

import unittest

from discord import app_commands

from apps.commands.dmk_poll import DMKPoll


def _get_cmd(attr_name):
    """Haalt het app command object op dat op de Cog-attribute is geplakt."""
    cmd = getattr(DMKPoll, attr_name, None)
    if cmd is None:
        raise AssertionError(
            f"Commando-attribute '{attr_name}' niet gevonden op DMKPoll"
        )
    if not isinstance(cmd, app_commands.Command):
        raise AssertionError(
            f"Attribute '{attr_name}' is geen app_commands.Command (type={type(cmd)})"
        )
    return cmd


class TestCommandDefaults(unittest.TestCase):
    def test_admin_mod_default_commands(self):
        admin_mod_cmds = {
            # attr_name: expected_slash_name
            "on": "dmk-poll-on",
            "reset": "dmk-poll-reset",
            "pauze": "dmk-poll-pauze",
            "verwijderbericht": "dmk-poll-verwijderen",
            "stemmen": "dmk-poll-stemmen",
            "archief_download": "dmk-poll-archief-download",
            "archief_verwijderen": "dmk-poll-archief-verwijderen",
        }
        for attr, expected_name in admin_mod_cmds.items():
            cmd = _get_cmd(attr)
            # naam
            self.assertEqual(cmd.name, expected_name, f"Naam mismatch bij {attr}")
            # guild-only
            self.assertTrue(
                getattr(cmd, "guild_only", False), f"{attr} moet guild_only=True zijn"
            )
            # default permissions moeten admin of moderate_members bevatten
            dp = getattr(cmd, "default_permissions", None)
            self.assertIsNotNone(dp, f"{attr} moet default_permissions hebben")
            has_admin = getattr(dp, "administrator", False)
            has_moderate = getattr(dp, "moderate_members", False)
            self.assertTrue(
                has_admin or has_moderate,
                f"{attr} moet admin of moderate_members default hebben",
            )
            # description hint: accepteer zowel (default: admin/mod) als de losse varianten
            desc = getattr(cmd, "description", "") or ""
            self.assertTrue(
                any(
                    tag in desc
                    for tag in (
                        "(default: admin/mod)",
                        "(default: admin)",
                        "(default: moderator)",
                    )
                ),
                f"{attr} description mist '(default: admin/mod)' of '(default: admin)' of '(default: moderator)'",
            )

    def test_public_default_commands(self):
        public_cmds = {
            "status": "dmk-poll-status",
            "gast_add": "gast-add",
            "gast_remove": "gast-remove",
        }
        for attr, expected_name in public_cmds.items():
            cmd = _get_cmd(attr)
            self.assertEqual(cmd.name, expected_name, f"Naam mismatch bij {attr}")
            self.assertTrue(
                getattr(cmd, "guild_only", False), f"{attr} moet guild_only=True zijn"
            )
            # géén default_permissions => iedereen mag standaard
            dp = getattr(cmd, "default_permissions", None)
            self.assertTrue(
                dp is None or getattr(dp, "value", 0) == 0,
                f"{attr} moet géén default_permissions hebben",
            )


if __name__ == "__main__":
    unittest.main()

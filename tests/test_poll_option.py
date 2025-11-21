# tests/test_poll_option.py

import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast
from unittest.mock import patch

from tests.base import BaseTestCase

EXPECTED_DAYS = ["vrijdag", "zaterdag", "zondag"]

# Dummy discord module vóór import van poll_option
# We hebben alleen ButtonStyle.secondary nodig.
discord_mod = cast(Any, ModuleType("discord"))


class _ButtonStyle:
    secondary = object()  # Willekeurige sentinel


discord_mod.ButtonStyle = _ButtonStyle
sys.modules.setdefault("discord", discord_mod)

# Nu pas importeren zodat onze dummy gebruikt wordt
from apps.entities import poll_option as po  # noqa: E402


class TestPollOption(BaseTestCase):
    def setUp(self):
        super().setUp()
        # Maak een temp pad voor poll_options.json per test
        self.tmpfile = Path("poll_options_test.json")
        if self.tmpfile.exists():
            self.tmpfile.unlink()

    def tearDown(self):
        try:
            if self.tmpfile.exists():
                self.tmpfile.unlink()
        finally:
            super().tearDown()

    # _load_raw_options: bestand mist → defaults
    def test_get_options_when_file_missing_uses_defaults(self):
        with patch.object(po, "OPTIONS_FILE", str(self.tmpfile)):
            opts = po.get_poll_options()
        assert isinstance(opts, list) and len(opts) == len(po._DEFAULTS)
        # Check dat type PollOption en default stijl gezet is
        o = opts[0]
        assert hasattr(o, "dag") and hasattr(o, "tijd") and hasattr(o, "emoji")
        assert o.stijl is po.ButtonStyle.secondary
        # Label-format
        assert o.label.startswith(f"{o.emoji} {o.dag.capitalize()} {o.tijd}")

    # _load_raw_options: kapotte JSON → defaults (except-pad)
    def test_get_options_corrupt_json_uses_defaults(self):
        self.tmpfile.write_text("{ not valid json", encoding="utf-8")
        with patch.object(po, "OPTIONS_FILE", str(self.tmpfile)):
            opts = po.get_poll_options()
        assert len(opts) == len(po._DEFAULTS)

    # _load_raw_options: ongeldige schema → defaults
    def test_get_options_invalid_schema_uses_defaults(self):
        # Ontbreekt verplichte sleutel 'tijd' / 'emoji'
        bad = [{"dag": "vrijdag"}]
        self.tmpfile.write_text(json.dumps(bad), encoding="utf-8")
        with patch.object(po, "OPTIONS_FILE", str(self.tmpfile)):
            opts = po.get_poll_options()
        assert len(opts) == len(po._DEFAULTS)

    # Geldige JSON → precies die opties
    def test_get_options_valid_json_returns_custom(self):
        data = [
            {"dag": "maandag", "tijd": "om 19:00 uur", "emoji": "🟢"},
            {"dag": "maandag", "tijd": "misschien", "emoji": "Ⓜ️"},
        ]
        self.tmpfile.write_text(json.dumps(data), encoding="utf-8")
        with patch.object(po, "OPTIONS_FILE", str(self.tmpfile)):
            opts = po.get_poll_options()

        assert [(o.dag, o.tijd, o.emoji) for o in opts] == [
            ("maandag", "om 19:00 uur", "🟢"),
            ("maandag", "misschien", "Ⓜ️"),
        ]
        # ButtonStyle.secondary is default
        for o in opts:
            assert o.stijl is po.ButtonStyle.secondary
            assert o.label == f"{o.emoji} {o.dag.capitalize()} {o.tijd}"

    #  list_days: unieke dagen in JSON-volgorde -
    def test_list_days_unique_and_in_order(self):
        data = [
            {"dag": "vrijdag", "tijd": "om 19:00 uur", "emoji": "🟢"},
            {"dag": "vrijdag", "tijd": "misschien", "emoji": "Ⓜ️"},
            {"dag": "zaterdag", "tijd": "om 20:30 uur", "emoji": "🔵"},
            {"dag": "vrijdag", "tijd": "niet meedoen", "emoji": "❌"},
            {"dag": "zondag", "tijd": "om 19:00 uur", "emoji": "🟡"},
        ]
        self.tmpfile.write_text(json.dumps(data), encoding="utf-8")
        with patch.object(po, "OPTIONS_FILE", str(self.tmpfile)):
            days = po.list_days()
        # Eerste keer dat een dag verschijnt bepaalt de volgorde
        assert days == EXPECTED_DAYS

    #  is_valid_option: True en False paden -
    def test_is_valid_option_true_and_false(self):
        data = [
            {"dag": "vrijdag", "tijd": "om 19:00 uur", "emoji": "🟢"},
            {"dag": "zaterdag", "tijd": "misschien", "emoji": "Ⓜ️"},
        ]
        self.tmpfile.write_text(json.dumps(data), encoding="utf-8")
        with patch.object(po, "OPTIONS_FILE", str(self.tmpfile)):
            assert po.is_valid_option("vrijdag", "om 19:00 uur") is True
            assert po.is_valid_option("zaterdag", "misschien") is True
            # Onbestaande combinatie
            assert po.is_valid_option("zondag", "om 19:00 uur") is False
            assert po.is_valid_option("vrijdag", "niet meedoen") is False

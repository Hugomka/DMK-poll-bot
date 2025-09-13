# tests/test_poll_buttons.py

"""
Uitgebreide tests voor de knop‑UI van de poll.

Deze tests bootsen realistische scenario's na waarin een gebruiker op
knoppen drukt. We testen of views correct worden opgebouwd (zichtbaarheid
+ selectie) en of de callbacks correct werken, zonder echte
Discord- of opslag‑afhankelijkheden.

We plaatsen lichte stubs voor `discord` en de benodigde `apps.*` modules.
Alle tests erven van een minimale `BaseTestCase` die dezelfde env‑vars
zet als in het project en tijdelijke bestanden opruimt.
"""
from __future__ import annotations

import sys
import types as _types
from datetime import datetime
from typing import Any, cast

# ---------------------------------------------------------------------------
# Eenvoudige stub voor het pakket ``discord`` (alleen wat we nodig hebben).
# Hiermee draaien de tests ook als de echte discord-bibliotheek ontbreekt.
if "discord" not in sys.modules:
    # Module ``discord.ui`` met Button en View
    ui_mod: Any = _types.ModuleType("discord.ui")

    class _FakeButtonStyle:
        """Kleine enum met stijlen die we in tests nodig hebben."""

        primary = 1
        secondary = 2
        success = 3

    class _FakeButton:
        def __init__(
            self, *, label: str, style: int, custom_id: str, disabled: bool = False
        ) -> None:
            self.label = label
            self.style = style
            self.custom_id = custom_id
            self.disabled = disabled

        # De app‑klasse voegt de async callback toe; hier niets nodig.

    class _FakeView:
        def __init__(self, *, timeout: int | None = None) -> None:
            self.timeout = timeout
            self.children: list[Any] = []

        def add_item(self, item: Any) -> None:
            self.children.append(item)

    cast(Any, ui_mod).Button = _FakeButton
    cast(Any, ui_mod).View = _FakeView

    discord_mod: Any = _types.ModuleType("discord")
    cast(Any, discord_mod).ButtonStyle = _FakeButtonStyle
    cast(Any, discord_mod).ui = ui_mod
    # Voor type‑compatibiliteit: Interaction bestaat, maar we gebruiken hem niet echt
    cast(Any, discord_mod).Interaction = object

    sys.modules["discord"] = discord_mod
    sys.modules["discord.ui"] = ui_mod

# --- Dynamische import: eerst de echte module, dan (indien nodig) fallback ---
from pathlib import Path

# Zorg dat projectroot op sys.path staat (zodat 'apps.ui.poll_buttons' werkt).
_project_root = str(Path(__file__).resolve().parents[1])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

if "apps" not in sys.modules:
    sys.modules["apps"] = _types.ModuleType("apps")
    sys.modules["apps.entities"] = _types.ModuleType("apps.entities")

    # entities.poll_option
    poll_option_mod: Any = _types.ModuleType("apps.entities.poll_option")

    def _default_get_poll_options() -> list[Any]:
        return []

    def _default_list_days() -> list[str]:
        return []

    poll_option_mod.get_poll_options = _default_get_poll_options  # type: ignore[attr-defined]
    poll_option_mod.list_days = _default_list_days  # type: ignore[attr-defined]
    sys.modules["apps.entities.poll_option"] = poll_option_mod

    # logic.visibility
    sys.modules["apps.logic"] = _types.ModuleType("apps.logic")
    visibility_mod: Any = _types.ModuleType("apps.logic.visibility")

    def _default_is_vote_button_visible(
        channel_id: int, dag: str, tijd: str, now: datetime
    ) -> bool:  # noqa: D401
        return True

    visibility_mod.is_vote_button_visible = _default_is_vote_button_visible  # type: ignore[attr-defined]
    sys.modules["apps.logic.visibility"] = visibility_mod

    # utils.poll_message
    sys.modules["apps.utils"] = _types.ModuleType("apps.utils")
    poll_message_mod: Any = _types.ModuleType("apps.utils.poll_message")

    def _default_update_poll_message(channel: Any, dag: str) -> None:
        return None

    poll_message_mod.update_poll_message = _default_update_poll_message  # type: ignore[attr-defined]
    sys.modules["apps.utils.poll_message"] = poll_message_mod

    # utils.poll_settings
    poll_settings_mod: Any = _types.ModuleType("apps.utils.poll_settings")
    poll_settings_mod.is_paused = lambda channel_id: False  # type: ignore[attr-defined]
    sys.modules["apps.utils.poll_settings"] = poll_settings_mod

    # utils.poll_storage
    poll_storage_mod: Any = _types.ModuleType("apps.utils.poll_storage")

    async def _default_get_user_votes(
        user_id: str, guild_id: int, channel_id: int
    ) -> dict[str, list[str]]:
        return {}

    async def _default_toggle_vote(
        user_id: str, dag: str, tijd: str, guild_id: int, channel_id: int
    ) -> None:
        return None

    poll_storage_mod.get_user_votes = _default_get_user_votes  # type: ignore[attr-defined]
    poll_storage_mod.toggle_vote = _default_toggle_vote  # type: ignore[attr-defined]
    sys.modules["apps.utils.poll_storage"] = poll_storage_mod

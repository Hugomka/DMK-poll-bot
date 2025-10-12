# tests/test_archive_view.py

import sys
from types import ModuleType, SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

from tests.base import BaseTestCase

# ---- Zorg dat 'discord' aanwezig is vóór import van archive_view ----------------
# We maken een minimale dummy-implementatie van discord + discord.ui
discord_mod = cast(Any, ModuleType("discord"))
discord_ui_mod = cast(Any, ModuleType("discord.ui"))


class DummyView:
    def __init__(self, timeout=None):
        self.timeout = timeout
        self.children = []

    def add_item(self, item):
        self.children.append(item)


class DummyButton:
    def __init__(self, *, label=None, style=None, custom_id=None):
        self.label = label
        self.style = style
        self.custom_id = custom_id


class ButtonStyle:
    danger = "danger"


# maak attribuuten aan op de (Any-)module
discord_mod.ui = discord_ui_mod
discord_ui_mod.Button = DummyButton
discord_ui_mod.View = DummyView
discord_mod.ButtonStyle = ButtonStyle

# registreer modules
sys.modules.setdefault("discord", discord_mod)
sys.modules.setdefault("discord.ui", discord_ui_mod)

# Nu pas importeren, zodat archive_view onze dummies gebruikt
from apps.ui import archive_view  # noqa: E402


class TestArchiveView(BaseTestCase):
    async def test_view_initializes_with_button(self):
        """
        ArchiveDeleteView.__init__ zou een DeleteArchiveButton moeten toevoegen.
        """
        view = archive_view.ArchiveDeleteView()
        assert hasattr(view, "children")
        assert len(view.children) == 1
        assert isinstance(view.children[0], archive_view.DeleteArchiveButton)

        # Button eigenschappen aanwezig (label, style, custom_id)
        btn = view.children[0]
        assert btn.label == "🗑️ Verwijder archief"
        assert btn.style == archive_view.discord.ButtonStyle.danger
        assert btn.custom_id == "delete_archive_scoped"

    async def test_button_callback_ok_with_message(self):
        """
        delete_archive_scoped() → True:
        - response.send_message wordt aangeroepen met succes-tekst (ephemeral=True)
        - interaction.message is niet None → message.edit(view=None) wordt gedaan
        """
        sent = []
        edited = []

        class Resp:
            async def send_message(self, content, *, ephemeral=False):
                sent.append({"content": content, "ephemeral": ephemeral})

        class Msg:
            async def edit(self, **kwargs):
                edited.append(kwargs)

        interaction = SimpleNamespace(response=Resp(), message=Msg())

        view = archive_view.ArchiveDeleteView()
        btn = view.children[0]

        with patch("apps.ui.archive_view.delete_archive_scoped", return_value=True):
            # cast naar Any voor Pylance
            await btn.callback(cast(Any, interaction))

        assert sent and "Archief verwijderd" in sent[0]["content"]
        assert sent[0]["ephemeral"] is True
        assert edited and edited[0].get("view") is None

    async def test_button_callback_ok_without_message(self):
        """
        delete_archive_scoped() → True maar interaction.message is None:
        - alleen response.send_message; geen edit
        """
        sent = []

        class Resp:
            async def send_message(self, content, *, ephemeral=False):
                sent.append({"content": content, "ephemeral": ephemeral})

        interaction = SimpleNamespace(response=Resp(), message=None)

        view = archive_view.ArchiveDeleteView()
        btn = view.children[0]

        with patch("apps.ui.archive_view.delete_archive_scoped", return_value=True):
            await btn.callback(cast(Any, interaction))

        assert sent and "Archief verwijderd" in sent[0]["content"]
        assert sent[0]["ephemeral"] is True

    async def test_button_callback_not_ok(self):
        """
        delete_archive_scoped() → False:
        - response.send_message met waarschuwing
        - geen edit
        """
        sent = []
        edited = []

        class Resp:
            async def send_message(self, content, *, ephemeral=False):
                sent.append({"content": content, "ephemeral": ephemeral})

        class Msg:
            async def edit(self, **kwargs):
                edited.append(kwargs)

        interaction = SimpleNamespace(response=Resp(), message=Msg())

        view = archive_view.ArchiveDeleteView()
        btn = view.children[0]

        with patch("apps.ui.archive_view.delete_archive_scoped", return_value=False):
            await btn.callback(cast(Any, interaction))

        assert sent and "geen archief" in sent[0]["content"]
        assert sent[0]["ephemeral"] is True
        assert edited == []  # geen edit in False-pad

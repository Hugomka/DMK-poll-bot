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
    def __init__(self, *, label=None, style=None, custom_id=None, row=None):
        self.label = label
        self.style = style
        self.custom_id = custom_id
        self.row = row


class DummySelect:
    def __init__(self, *, placeholder=None, options=None, custom_id=None, row=None):
        self.placeholder = placeholder
        self.options = options or []
        self.custom_id = custom_id
        self.row = row


class ButtonStyle:
    danger = "danger"
    success = "success"


# maak attribuuten aan op de (Any-)module
discord_mod.ui = discord_ui_mod
discord_ui_mod.Button = DummyButton
discord_ui_mod.Select = DummySelect
discord_ui_mod.View = DummyView
discord_mod.ButtonStyle = ButtonStyle
discord_mod.SelectOption = lambda **kwargs: SimpleNamespace(**kwargs)
discord_mod.File = lambda *args, **kwargs: SimpleNamespace(filename=kwargs.get("filename", ""))

# registreer modules
sys.modules.setdefault("discord", discord_mod)
sys.modules.setdefault("discord.ui", discord_ui_mod)

# Nu pas importeren, zodat archive_view onze dummies gebruikt
from apps.ui import archive_view  # noqa: E402


class TestArchiveView(BaseTestCase):
    async def test_view_initializes_with_button(self):
        """
        ArchiveView.__init__ zou SelectMenu en Delete button moeten toevoegen.
        """
        view = archive_view.ArchiveView()
        assert hasattr(view, "children")
        assert len(view.children) == 2  # SelectMenu, Delete (geen Download button meer)

        # Vind delete button
        delete_btn = None
        for child in view.children:
            if isinstance(child, archive_view.DeleteArchiveButton):
                delete_btn = child
                break

        assert delete_btn is not None
        assert delete_btn.label == "Verwijder archief"
        assert delete_btn.style == archive_view.discord.ButtonStyle.danger
        assert delete_btn.custom_id == "delete_archive_scoped"

    async def test_button_callback_shows_confirmation(self):
        """
        DeleteArchiveButton toont bevestigingsbericht:
        - response.send_message wordt aangeroepen met bevestigingstekst
        - view met Annuleer en Verwijder Archief knoppen
        """
        sent = []

        class Resp:
            async def send_message(self, content, *, view=None, ephemeral=False):
                sent.append({"content": content, "view": view, "ephemeral": ephemeral})

        class Msg:
            pass

        interaction = SimpleNamespace(response=Resp(), message=Msg())

        view = archive_view.ArchiveView()
        # Vind delete button
        btn = None
        for child in view.children:
            if isinstance(child, archive_view.DeleteArchiveButton):
                btn = child
                break
        assert btn is not None

        # cast naar Any voor Pylance
        await btn.callback(cast(Any, interaction))

        assert sent and "Weet je zeker" in sent[0]["content"]
        assert sent[0]["ephemeral"] is True
        assert sent[0]["view"] is not None
        # Check dat view ConfirmDeleteView is
        assert isinstance(sent[0]["view"], archive_view.ConfirmDeleteView)

    async def test_confirm_delete_button_deletes_and_updates(self):
        """
        ConfirmDeleteButton verwijdert archief en update beide berichten:
        - edit_message op bevestigingsbericht
        - edit op origineel bericht
        """
        edited_confirmation = []
        edited_original = []

        class Resp:
            async def edit_message(self, content, *, view=None):
                edited_confirmation.append({"content": content, "view": view})

        class OrigMsg:
            async def edit(self, **kwargs):
                edited_original.append(kwargs)

        interaction = SimpleNamespace(response=Resp())

        # Maak ConfirmDeleteView met origineel bericht (cast naar Any voor type checking)
        confirm_view = archive_view.ConfirmDeleteView(123, 456, cast(Any, OrigMsg()))

        # Vind ConfirmDeleteButton
        confirm_btn = None
        for child in confirm_view.children:
            if isinstance(child, archive_view.ConfirmDeleteButton):
                confirm_btn = child
                break
        assert confirm_btn is not None

        with patch("apps.ui.archive_view.delete_archive_scoped", return_value=True):
            await confirm_btn.callback(cast(Any, interaction))

        # Check bevestigingsbericht is geüpdatet
        assert edited_confirmation and "Archief verwijderd" in edited_confirmation[0]["content"]

        # Check origineel bericht is geüpdatet
        assert edited_original
        assert "Archief verwijderd" in edited_original[0].get("content", "")
        assert edited_original[0].get("attachments") == []
        assert edited_original[0].get("view") is None

    async def test_cancel_button_closes_confirmation(self):
        """
        CancelButton sluit bevestigingsbericht:
        - edit_message met annuleringstekst
        """
        edited = []

        class Resp:
            async def edit_message(self, content, *, view=None):
                edited.append({"content": content, "view": view})

        interaction = SimpleNamespace(response=Resp())

        # Maak ConfirmDeleteView
        confirm_view = archive_view.ConfirmDeleteView(123, 456, None)

        # Vind CancelButton
        cancel_btn = None
        for child in confirm_view.children:
            if isinstance(child, archive_view.CancelButton):
                cancel_btn = child
                break
        assert cancel_btn is not None

        await cancel_btn.callback(cast(Any, interaction))

        # Check dat bericht is geüpdatet met annuleringstekst
        assert edited and "geannuleerd" in edited[0]["content"].lower()
        assert edited[0]["view"] is None

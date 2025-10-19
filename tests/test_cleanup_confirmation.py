# tests/test_cleanup_confirmation.py
#
# Unit tests voor CleanupConfirmationView en knoppen

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from discord.ui import Button

from apps.ui.cleanup_confirmation import (
    CleanupConfirmationView,
    NoButton,
    YesButton,
)
from tests.base import BaseTestCase


class TestCleanupConfirmationView(BaseTestCase):
    """Tests voor CleanupConfirmationView."""

    async def test_view_initializes_with_callbacks_and_buttons(self):
        """View moet on_confirm, on_cancel en message_count opslaan en 2 knoppen toevoegen."""

        on_confirm = MagicMock()
        on_cancel = MagicMock()

        view = CleanupConfirmationView(
            on_confirm=on_confirm, on_cancel=on_cancel, message_count=42
        )

        # Check attributes
        self.assertEqual(view.on_confirm, on_confirm)
        self.assertEqual(view.on_cancel, on_cancel)
        self.assertEqual(view.message_count, 42)
        self.assertEqual(view.timeout, 180)

        # Check buttons toegevoegd
        self.assertEqual(len(view.children), 2)
        self.assertIsInstance(view.children[0], YesButton)
        self.assertIsInstance(view.children[1], NoButton)

    async def test_yes_button_callback_success(self):
        """YesButton.callback moet knoppen disablen, bericht updaten en on_confirm aanroepen."""

        on_confirm_called = False

        async def mock_on_confirm(interaction):
            nonlocal on_confirm_called
            on_confirm_called = True

        on_cancel = AsyncMock()
        view = CleanupConfirmationView(
            on_confirm=mock_on_confirm, on_cancel=on_cancel, message_count=10
        )

        # Mock interaction
        interaction = SimpleNamespace(
            response=SimpleNamespace(edit_message=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()),
        )

        yes_button = view.children[0]
        self.assertIsInstance(yes_button, YesButton)

        # Suppress emoji print errors
        with patch("builtins.print"):
            await yes_button.callback(interaction)

        # Assert: knoppen disabled
        for item in view.children:
            if isinstance(item, Button):
                self.assertTrue(item.disabled)

        # Assert: bericht geüpdatet
        interaction.response.edit_message.assert_awaited_once()
        call_kwargs = interaction.response.edit_message.call_args.kwargs
        self.assertIn("⏳ Bezig met verwijderen", call_kwargs["content"])
        self.assertIn("10", call_kwargs["content"])
        self.assertEqual(call_kwargs["view"], view)

        # Assert: on_confirm aangeroepen
        self.assertTrue(on_confirm_called)

        # Assert: on_cancel NIET aangeroepen
        on_cancel.assert_not_awaited()

    async def test_yes_button_callback_exception_in_edit(self):
        """YesButton.callback moet exception afhandelen bij edit_message failure."""

        on_confirm = AsyncMock()
        on_cancel = AsyncMock()
        view = CleanupConfirmationView(
            on_confirm=on_confirm, on_cancel=on_cancel, message_count=10
        )

        # Mock interaction met fout in edit_message
        interaction = SimpleNamespace(
            response=SimpleNamespace(
                edit_message=AsyncMock(side_effect=RuntimeError("Edit failed"))
            ),
            followup=SimpleNamespace(send=AsyncMock()),
        )

        yes_button = view.children[0]

        # Suppress print output
        with patch("builtins.print") as mock_print:
            await yes_button.callback(interaction)

        # Assert: error geprint
        mock_print.assert_called()
        print_call = str(mock_print.call_args)
        self.assertIn("Fout in YesButton.callback", print_call)

        # Assert: followup.send aangeroepen met error message
        interaction.followup.send.assert_awaited_once()
        call_args = interaction.followup.send.call_args
        # Check args of kwargs
        if call_args.kwargs and "content" in call_args.kwargs:
            self.assertIn("⚠️", call_args.kwargs["content"])
            self.assertTrue(call_args.kwargs.get("ephemeral", False))
        elif call_args.args:
            self.assertIn("⚠️", call_args.args[0])
            self.assertTrue(call_args.kwargs.get("ephemeral", False))

    async def test_yes_button_callback_exception_in_followup(self):
        """YesButton.callback moet gracefully falen als zowel edit als followup falen."""

        on_confirm = AsyncMock()
        on_cancel = AsyncMock()
        view = CleanupConfirmationView(
            on_confirm=on_confirm, on_cancel=on_cancel, message_count=10
        )

        # Mock interaction met fouten in zowel edit als followup
        interaction = SimpleNamespace(
            response=SimpleNamespace(
                edit_message=AsyncMock(side_effect=RuntimeError("Edit failed"))
            ),
            followup=SimpleNamespace(
                send=AsyncMock(side_effect=RuntimeError("Followup failed"))
            ),
        )

        yes_button = view.children[0]

        # Suppress print output
        with patch("builtins.print"):
            # Should not raise
            await yes_button.callback(interaction)

        # Assert: no crash, graceful failure
        # (test passes if geen exception gegooid wordt)

    async def test_no_button_callback_success(self):
        """NoButton.callback moet knoppen disablen, bericht updaten en on_cancel aanroepen."""

        on_confirm = AsyncMock()
        on_cancel_called = False

        async def mock_on_cancel(interaction):
            nonlocal on_cancel_called
            on_cancel_called = True

        view = CleanupConfirmationView(
            on_confirm=on_confirm, on_cancel=mock_on_cancel, message_count=10
        )

        # Mock interaction
        interaction = SimpleNamespace(
            response=SimpleNamespace(edit_message=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()),
        )

        no_button = view.children[1]
        self.assertIsInstance(no_button, NoButton)

        # Suppress emoji print errors
        with patch("builtins.print"):
            await no_button.callback(interaction)

        # Assert: knoppen disabled
        for item in view.children:
            if isinstance(item, Button):
                self.assertTrue(item.disabled)

        # Assert: bericht geüpdatet
        interaction.response.edit_message.assert_awaited_once()
        call_kwargs = interaction.response.edit_message.call_args.kwargs
        self.assertIn("ℹ️", call_kwargs["content"])
        self.assertIn("behouden", call_kwargs["content"])
        self.assertEqual(call_kwargs["view"], view)

        # Assert: on_cancel aangeroepen
        self.assertTrue(on_cancel_called)

        # Assert: on_confirm NIET aangeroepen
        on_confirm.assert_not_awaited()

    async def test_no_button_callback_exception_in_edit(self):
        """NoButton.callback moet exception afhandelen bij edit_message failure."""

        on_confirm = AsyncMock()
        on_cancel = AsyncMock()
        view = CleanupConfirmationView(
            on_confirm=on_confirm, on_cancel=on_cancel, message_count=10
        )

        # Mock interaction met fout in edit_message
        interaction = SimpleNamespace(
            response=SimpleNamespace(
                edit_message=AsyncMock(side_effect=RuntimeError("Edit failed"))
            ),
            followup=SimpleNamespace(send=AsyncMock()),
        )

        no_button = view.children[1]

        # Suppress print output
        with patch("builtins.print") as mock_print:
            await no_button.callback(interaction)

        # Assert: error geprint
        mock_print.assert_called()
        print_call = str(mock_print.call_args)
        self.assertIn("Fout in NoButton.callback", print_call)

        # Assert: followup.send aangeroepen met error message
        interaction.followup.send.assert_awaited_once()
        call_args = interaction.followup.send.call_args
        # Check args of kwargs
        if call_args.kwargs and "content" in call_args.kwargs:
            self.assertIn("⚠️", call_args.kwargs["content"])
            self.assertTrue(call_args.kwargs.get("ephemeral", False))
        elif call_args.args:
            self.assertIn("⚠️", call_args.args[0])
            self.assertTrue(call_args.kwargs.get("ephemeral", False))

    async def test_no_button_callback_exception_in_followup(self):
        """NoButton.callback moet gracefully falen als zowel edit als followup falen."""

        on_confirm = AsyncMock()
        on_cancel = AsyncMock()
        view = CleanupConfirmationView(
            on_confirm=on_confirm, on_cancel=on_cancel, message_count=10
        )

        # Mock interaction met fouten in zowel edit als followup
        interaction = SimpleNamespace(
            response=SimpleNamespace(
                edit_message=AsyncMock(side_effect=RuntimeError("Edit failed"))
            ),
            followup=SimpleNamespace(
                send=AsyncMock(side_effect=RuntimeError("Followup failed"))
            ),
        )

        no_button = view.children[1]

        # Suppress print output
        with patch("builtins.print"):
            # Should not raise
            await no_button.callback(interaction)

        # Assert: no crash, graceful failure
        # (test passes if geen exception gegooid wordt)

    async def test_yes_button_properties(self):
        """Test YesButton label, style en custom_id."""
        on_confirm = MagicMock()
        on_cancel = MagicMock()
        view = CleanupConfirmationView(
            on_confirm=on_confirm, on_cancel=on_cancel, message_count=5
        )

        yes_button = view.children[0]
        self.assertIsInstance(yes_button, YesButton)
        self.assertEqual(yes_button.label, "✅ Ja, verwijder")
        self.assertEqual(yes_button.style.value, 4)  # ButtonStyle.danger = 4
        self.assertEqual(yes_button.custom_id, "cleanup_yes")

    async def test_no_button_properties(self):
        """Test NoButton label, style en custom_id."""
        on_confirm = MagicMock()
        on_cancel = MagicMock()
        view = CleanupConfirmationView(
            on_confirm=on_confirm, on_cancel=on_cancel, message_count=5
        )

        no_button = view.children[1]
        self.assertIsInstance(no_button, NoButton)
        self.assertEqual(no_button.label, "❌ Nee, behoud")
        self.assertEqual(no_button.style.value, 2)  # ButtonStyle.secondary = 2
        self.assertEqual(no_button.custom_id, "cleanup_no")

    async def test_both_buttons_disable_all_items(self):
        """Test dat beide knoppen alle items in de view disablen."""
        on_confirm = AsyncMock()
        on_cancel = AsyncMock()
        view = CleanupConfirmationView(
            on_confirm=on_confirm, on_cancel=on_cancel, message_count=10
        )

        interaction = SimpleNamespace(
            response=SimpleNamespace(edit_message=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()),
        )

        # Test Yes button
        yes_button = view.children[0]
        with patch("builtins.print"):
            await yes_button.callback(interaction)

        for item in view.children:
            if isinstance(item, Button):
                self.assertTrue(item.disabled, "Yes button moet alle knoppen disablen")

        # Reset voor No button test
        for item in view.children:
            if isinstance(item, Button):
                item.disabled = False

        # Test No button
        no_button = view.children[1]
        with patch("builtins.print"):
            await no_button.callback(interaction)

        for item in view.children:
            if isinstance(item, Button):
                self.assertTrue(item.disabled, "No button moet alle knoppen disablen")

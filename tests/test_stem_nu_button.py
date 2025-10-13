# tests/test_stem_nu_button.py

"""
Tests voor Stem Nu button functionaliteit (Misschien-bevestiging 17:00-18:00).
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from apps.ui.stem_nu_button import (
    ConfirmationView,
    JaButton,
    NeeButton,
    StemNuButton,
    StemNuView,
    create_stem_nu_view,
)
from tests.test_mention_utils import _consume_coro_task


class StemNuButtonTestCase(unittest.IsolatedAsyncioTestCase):
    """Test StemNuButton callback functionaliteit."""

    def setUp(self):
        """Setup voor elke test."""
        self.mock_interaction = MagicMock()
        self.mock_interaction.user.id = 123456
        self.mock_interaction.guild_id = 789
        self.mock_interaction.guild.id = 789
        self.mock_interaction.channel_id = 456
        self.mock_interaction.channel = MagicMock()
        self.mock_interaction.response.send_message = AsyncMock()
        self.mock_interaction.response.is_done.return_value = False
        self.mock_interaction.delete_original_response = AsyncMock()

    async def test_stem_nu_button_no_channel_id(self):
        """Test dat button een foutmelding toont zonder channel_id."""
        button = StemNuButton()
        self.mock_interaction.channel_id = None

        await button.callback(self.mock_interaction)

        self.mock_interaction.response.send_message.assert_called_once()
        call_args = self.mock_interaction.response.send_message.call_args
        self.assertIn("serverkanaal", call_args[0][0])
        self.assertTrue(call_args[1]["ephemeral"])

    async def test_stem_nu_button_wrong_view_type(self):
        """Test dat button foutmelding toont met verkeerd view type."""
        # Create a mock view that's not a StemNuView
        mock_view = MagicMock()
        button = StemNuButton()
        # Manually set the _view attribute to bypass the setter
        button._view = mock_view

        await button.callback(self.mock_interaction)

        self.mock_interaction.response.send_message.assert_called_once()
        call_args = self.mock_interaction.response.send_message.call_args
        self.assertIn("dag/tijd", call_args[0][0])
        self.assertTrue(call_args[1]["ephemeral"])

    @patch("apps.ui.stem_nu_button.get_user_votes")
    async def test_stem_nu_button_misschien_shows_confirmation(self, mock_get_votes):
        """Test dat button Ja/Nee dialoog toont voor 'misschien' stem."""
        mock_get_votes.return_value = {"vrijdag": ["misschien"]}

        button = StemNuButton()
        view = StemNuView(dag="vrijdag", leading_time="19:00")
        button._view = view

        await button.callback(self.mock_interaction)

        # Verify confirmation dialog was shown
        self.mock_interaction.response.send_message.assert_called_once()
        call_args = self.mock_interaction.response.send_message.call_args
        self.assertIn("19:00", call_args[0][0])
        self.assertIn("meedoen", call_args[0][0])
        self.assertTrue(call_args[1]["ephemeral"])
        # Verify view is ConfirmationView
        self.assertIsInstance(call_args[1]["view"], ConfirmationView)

    @patch("apps.ui.stem_nu_button.get_user_votes")
    @patch("asyncio.sleep")
    async def test_stem_nu_button_niet_meedoen_readonly(
        self, mock_sleep, mock_get_votes
    ):
        """Test dat button readonly bericht toont voor 'niet meedoen'."""
        mock_get_votes.return_value = {"vrijdag": ["niet meedoen"]}
        mock_sleep.return_value = AsyncMock()

        button = StemNuButton()
        view = StemNuView(dag="vrijdag", leading_time="19:00")
        button._view = view

        await button.callback(self.mock_interaction)

        # Verify readonly message was shown
        self.mock_interaction.response.send_message.assert_called_once()
        call_args = self.mock_interaction.response.send_message.call_args
        self.assertIn("niet meedoen", call_args[0][0])
        self.assertTrue(call_args[1]["ephemeral"])

        # Verify auto-delete was scheduled
        mock_sleep.assert_called_once_with(20)

    @patch("apps.ui.stem_nu_button.get_user_votes")
    @patch("asyncio.sleep")
    async def test_stem_nu_button_already_voted_time(self, mock_sleep, mock_get_votes):
        """Test dat button readonly bericht toont als al voor tijd gestemd."""
        mock_get_votes.return_value = {"vrijdag": ["om 19:00 uur"]}
        mock_sleep.return_value = AsyncMock()

        button = StemNuButton()
        view = StemNuView(dag="vrijdag", leading_time="19:00")
        button._view = view

        await button.callback(self.mock_interaction)

        # Verify readonly message was shown
        self.mock_interaction.response.send_message.assert_called_once()
        call_args = self.mock_interaction.response.send_message.call_args
        self.assertIn("19:00", call_args[0][0])
        self.assertTrue(call_args[1]["ephemeral"])

        # Verify auto-delete was scheduled
        mock_sleep.assert_called_once_with(20)

    @patch("apps.ui.stem_nu_button.get_user_votes")
    async def test_stem_nu_button_no_vote(self, mock_get_votes):
        """Test dat button foutmelding toont als niet gestemd."""
        mock_get_votes.return_value = {"vrijdag": []}

        button = StemNuButton()
        view = StemNuView(dag="vrijdag", leading_time="19:00")
        button._view = view

        await button.callback(self.mock_interaction)

        # Verify error message was shown
        self.mock_interaction.response.send_message.assert_called_once()
        call_args = self.mock_interaction.response.send_message.call_args
        self.assertIn("nog niet gestemd", call_args[0][0])
        self.assertTrue(call_args[1]["ephemeral"])

    @patch("builtins.print")
    @patch("apps.ui.stem_nu_button.get_user_votes")
    async def test_stem_nu_button_handles_exception(self, mock_get_votes, mock_print):
        """Test dat button exceptions netjes afhandelt."""
        mock_get_votes.side_effect = Exception("Test error")

        button = StemNuButton()
        view = StemNuView(dag="vrijdag", leading_time="19:00")
        button._view = view

        await button.callback(self.mock_interaction)

        # Verify error message was shown
        self.mock_interaction.response.send_message.assert_called_once()
        call_args = self.mock_interaction.response.send_message.call_args
        self.assertIn("mis", call_args[0][0].lower())


class JaButtonTestCase(unittest.IsolatedAsyncioTestCase):
    """Test JaButton callback functionaliteit."""

    async def asyncSetUp(self):
        """Setup voor elke test."""
        self.mock_interaction = MagicMock()
        self.mock_interaction.user.id = 123456
        self.mock_interaction.channel = MagicMock()
        self.mock_interaction.response.edit_message = AsyncMock()
        self.mock_interaction.response.send_message = AsyncMock()

        self.confirmation_view = ConfirmationView(
            user_id="123456",
            guild_id=789,
            channel_id=456,
            dag="vrijdag",
            leading_time="19:00",
        )

    @patch("apps.ui.stem_nu_button.remove_vote")
    @patch("apps.ui.stem_nu_button.add_vote")
    @patch("asyncio.create_task")
    async def test_ja_button_updates_vote_1900(
        self, mock_create_task, mock_add_vote, mock_remove_vote
    ):
        """Test dat Ja-button stem update naar 19:00."""
        mock_create_task.side_effect = _consume_coro_task()
        mock_remove_vote.return_value = AsyncMock()
        mock_add_vote.return_value = AsyncMock()

        button = JaButton(self.confirmation_view)
        await button.callback(self.mock_interaction)

        # Verify misschien was removed
        mock_remove_vote.assert_called_once_with(
            "123456", "vrijdag", "misschien", 789, 456
        )

        # Verify vote for 19:00 was added
        mock_add_vote.assert_called_once_with(
            "123456", "vrijdag", "om 19:00 uur", 789, 456
        )

        # Verify poll update was scheduled
        mock_create_task.assert_called_once()

        # Verify confirmation message
        self.mock_interaction.response.edit_message.assert_called_once()
        call_args = self.mock_interaction.response.edit_message.call_args
        self.assertIn("19:00", call_args[1]["content"])
        self.assertIsNone(call_args[1]["view"])

    @patch("apps.ui.stem_nu_button.remove_vote")
    @patch("apps.ui.stem_nu_button.add_vote")
    @patch("asyncio.create_task")
    async def test_ja_button_updates_vote_2030(
        self, mock_create_task, mock_add_vote, mock_remove_vote
    ):
        """Test dat Ja-button stem update naar 20:30."""
        mock_create_task.side_effect = _consume_coro_task()
        mock_remove_vote.return_value = AsyncMock()
        mock_add_vote.return_value = AsyncMock()

        # Different leading time
        view = ConfirmationView(
            user_id="123456",
            guild_id=789,
            channel_id=456,
            dag="zaterdag",
            leading_time="20:30",
        )

        button = JaButton(view)
        await button.callback(self.mock_interaction)

        # Verify vote for 20:30 was added
        mock_add_vote.assert_called_once_with(
            "123456", "zaterdag", "om 20:30 uur", 789, 456
        )

    @patch("builtins.print")
    @patch("apps.ui.stem_nu_button.remove_vote")
    async def test_ja_button_handles_exception(self, mock_remove_vote, mock_print):
        """Test dat Ja-button exceptions netjes afhandelt."""
        mock_remove_vote.side_effect = Exception("Test error")

        button = JaButton(self.confirmation_view)
        await button.callback(self.mock_interaction)

        # Verify error message was shown
        self.mock_interaction.response.send_message.assert_called_once()
        call_args = self.mock_interaction.response.send_message.call_args
        self.assertIn("mis", call_args[0][0].lower())


class NeeButtonTestCase(unittest.IsolatedAsyncioTestCase):
    """Test NeeButton callback functionaliteit."""

    async def asyncSetUp(self):
        """Setup voor elke test."""
        self.mock_interaction = MagicMock()
        self.mock_interaction.user.id = 123456
        self.mock_interaction.channel = MagicMock()
        self.mock_interaction.response.edit_message = AsyncMock()
        self.mock_interaction.response.send_message = AsyncMock()

        self.confirmation_view = ConfirmationView(
            user_id="123456",
            guild_id=789,
            channel_id=456,
            dag="vrijdag",
            leading_time="19:00",
        )

    @patch("apps.ui.stem_nu_button.remove_vote")
    @patch("apps.ui.stem_nu_button.add_vote")
    @patch("asyncio.create_task")
    async def test_nee_button_updates_vote_niet_meedoen(
        self, mock_create_task, mock_add_vote, mock_remove_vote
    ):
        """Test dat Nee-button stem update naar 'niet meedoen'."""
        mock_create_task.side_effect = _consume_coro_task()
        mock_remove_vote.return_value = AsyncMock()
        mock_add_vote.return_value = AsyncMock()

        button = NeeButton(self.confirmation_view)
        await button.callback(self.mock_interaction)

        # Verify misschien was removed
        mock_remove_vote.assert_called_once_with(
            "123456", "vrijdag", "misschien", 789, 456
        )

        # Verify vote for 'niet meedoen' was added
        mock_add_vote.assert_called_once_with(
            "123456", "vrijdag", "niet meedoen", 789, 456
        )

        # Verify poll update was scheduled
        mock_create_task.assert_called_once()

        # Verify confirmation message
        self.mock_interaction.response.edit_message.assert_called_once()
        call_args = self.mock_interaction.response.edit_message.call_args
        self.assertIn("niet mee te doen", call_args[1]["content"])
        self.assertIsNone(call_args[1]["view"])

    @patch("builtins.print")
    @patch("apps.ui.stem_nu_button.remove_vote")
    async def test_nee_button_handles_exception(self, mock_remove_vote, mock_print):
        """Test dat Nee-button exceptions netjes afhandelt."""
        mock_remove_vote.side_effect = Exception("Test error")

        button = NeeButton(self.confirmation_view)
        await button.callback(self.mock_interaction)

        # Verify error message was shown
        self.mock_interaction.response.send_message.assert_called_once()
        call_args = self.mock_interaction.response.send_message.call_args
        self.assertIn("mis", call_args[0][0].lower())


class StemNuViewTestCase(unittest.IsolatedAsyncioTestCase):
    """Test StemNuView en factory functie."""

    async def test_stem_nu_view_creation(self):
        """Test dat StemNuView correct wordt aangemaakt."""
        view = StemNuView(dag="vrijdag", leading_time="19:00")

        self.assertEqual(view.dag, "vrijdag")
        self.assertEqual(view.leading_time, "19:00")
        self.assertIsNone(view.timeout)  # Permanent view
        self.assertEqual(len(view.children), 1)  # Heeft 1 button
        self.assertIsInstance(view.children[0], StemNuButton)

    async def test_create_stem_nu_view_factory(self):
        """Test de factory functie voor StemNuView."""
        view = create_stem_nu_view("zaterdag", "20:30")

        self.assertIsInstance(view, StemNuView)
        self.assertEqual(view.dag, "zaterdag")
        self.assertEqual(view.leading_time, "20:30")


class ConfirmationViewTestCase(unittest.IsolatedAsyncioTestCase):
    """Test ConfirmationView."""

    async def test_confirmation_view_creation(self):
        """Test dat ConfirmationView correct wordt aangemaakt."""
        view = ConfirmationView(
            user_id="123",
            guild_id=456,
            channel_id=789,
            dag="zondag",
            leading_time="19:00",
        )

        self.assertEqual(view.user_id, "123")
        self.assertEqual(view.guild_id, 456)
        self.assertEqual(view.channel_id, 789)
        self.assertEqual(view.dag, "zondag")
        self.assertEqual(view.leading_time, "19:00")
        self.assertEqual(view.timeout, 180)  # 3 minutes timeout
        self.assertEqual(len(view.children), 2)  # Heeft 2 buttons (Ja en Nee)

        # Check button types
        button_types = [type(child) for child in view.children]
        self.assertIn(JaButton, button_types)
        self.assertIn(NeeButton, button_types)


if __name__ == "__main__":
    unittest.main()

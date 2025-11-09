# apps/ui/cleanup_confirmation.py
#
# Bevestigingsview voor het opschonen van oude berichten
# Gebruikt door /dmk-poll-on, /dmk-poll-off, en /dmk-poll-verwijderen

from typing import Callable

from discord import ButtonStyle, Interaction
from discord.ui import Button, View


class CleanupConfirmationView(View):
    """View met Ja/Nee knoppen voor bevestiging van kanaalopschoning."""

    def __init__(
        self,
        on_confirm: Callable,
        on_cancel: Callable,
        message_count: int,
    ):
        """
        Args:
            on_confirm: Async functie om aan te roepen bij "Ja"
            on_cancel: Async functie om aan te roepen bij "Nee"
            message_count: Aantal berichten dat verwijderd zou worden
        """
        super().__init__(timeout=180)  # 3 minuten timeout
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.message_count = message_count

        # Voeg knoppen toe
        self.add_item(YesButton(self))
        self.add_item(NoButton(self))


class YesButton(Button):
    """Ja-knop: verwijder alle oude berichten."""

    def __init__(self, parent_view: CleanupConfirmationView):
        super().__init__(
            label="✅ Ja, verwijder",
            style=ButtonStyle.danger,
            custom_id="cleanup_yes",
        )
        self.parent_view = parent_view

    async def callback(self, interaction: Interaction):
        """Handler voor Ja-knop."""
        try:
            # Disable alle knoppen
            for item in self.parent_view.children:
                if isinstance(item, Button):
                    item.disabled = True

            await interaction.response.edit_message(
                content=f"⏳ Bezig met verwijderen van {self.parent_view.message_count} bericht(en)...",
                view=self.parent_view,
            )

            # Roep de confirm handler aan
            await self.parent_view.on_confirm(interaction)

        except Exception as e:  # pragma: no cover
            print(f"⚠️ Fout in YesButton.callback: {e}")
            try:
                await interaction.followup.send(
                    "⚠️ Er ging iets mis bij het verwijderen van berichten.",
                    ephemeral=True,
                )
            except Exception:  # pragma: no cover
                pass


class NoButton(Button):
    """Nee-knop: behoud oude berichten."""

    def __init__(self, parent_view: CleanupConfirmationView):
        super().__init__(
            label="❌ Nee, behoud",
            style=ButtonStyle.secondary,
            custom_id="cleanup_no",
        )
        self.parent_view = parent_view

    async def callback(self, interaction: Interaction):
        """Handler voor Nee-knop."""
        try:
            # Disable alle knoppen
            for item in self.parent_view.children:
                if isinstance(item, Button):
                    item.disabled = True

            await interaction.response.edit_message(
                content="ℹ️ Oude berichten worden behouden. De polls worden nu geplaatst.",
                view=self.parent_view,
            )

            # Roep de cancel handler aan
            await self.parent_view.on_cancel(interaction)

        except Exception as e:  # pragma: no cover
            print(f"⚠️ Fout in NoButton.callback: {e}")
            try:
                await interaction.followup.send(
                    "⚠️ Er ging iets mis.",
                    ephemeral=True,
                )
            except Exception:  # pragma: no cover
                pass

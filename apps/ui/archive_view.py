# apps/ui/archive_view.py

import io

import discord
from discord import File
from discord.ui import Button, Select, View

from apps.utils.archive import create_archive, delete_archive_scoped


class ArchiveView(View):
    """View met dropdown voor CSV formaat selectie en delete knop."""

    def __init__(self, guild_id: int | None = None, channel_id: int | None = None):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.selected_delimiter = ","  # Default

        # Add SelectMenu (row 0)
        self.add_item(DelimiterSelectMenu(self))

        # Add Delete button (row 1, red)
        self.add_item(DeleteArchiveButton(self))


class DelimiterSelectMenu(Select):
    """SelectMenu voor delimiter keuze - update bestand direct bij selectie."""

    def __init__(self, parent_view: "ArchiveView"):
        self.parent_view = parent_view

        options = [
            discord.SelectOption(
                label="🇺🇸 Comma (,)",
                value=",",
                description="Standaard CSV delimiter",
                default=True,
            ),
            discord.SelectOption(
                label="🇳🇱 Semicolon (;)",
                value=";",
                description="Nederlandse Excel delimiter",
            ),
        ]

        super().__init__(
            placeholder="Selecteer CSV Formaat...",
            options=options,
            custom_id="delimiter_select",
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        """Update CSV bestand met geselecteerde delimiter."""
        self.parent_view.selected_delimiter = self.values[0]

        # Update default option
        for option in self.options:
            option.default = option.value == self.values[0]

        # Genereer CSV met gekozen delimiter
        csv_data = create_archive(
            self.parent_view.guild_id,
            self.parent_view.channel_id,
            self.parent_view.selected_delimiter,
        )

        if not csv_data:
            await interaction.response.send_message(
                "❌ Kon archief niet genereren.", ephemeral=True
            )
            return

        # Genereer bestandsnaam
        guild_id = self.parent_view.guild_id or 0
        channel_id = self.parent_view.channel_id or 0
        filename = f"dmk_archive_{guild_id}_{channel_id}.csv"

        # Behoud de originele tekst van het bericht
        message_content = (
            "\n📊 **DMK Poll Archief**\n"
            "Je kunt een **CSV-formaat** tussen NL en US kiezen en download het archiefbestand dat geschikt is voor je spreadsheet.\n\n"
            "⚠️ **Let op**:\n"
            "Op de verwijder-knop klikken verwijdert je het hele archief permanent."
        )

        # Update bericht met nieuw CSV bestand
        await interaction.response.edit_message(
            content=message_content,
            attachments=[File(io.BytesIO(csv_data), filename=filename)],
            view=self.parent_view,
        )


class DeleteArchiveButton(Button):
    """Delete knop om archief te verwijderen."""

    def __init__(self, parent_view: "ArchiveView"):
        super().__init__(
            label="Verwijder archief",
            style=discord.ButtonStyle.danger,  # Red button
            custom_id="delete_archive_scoped",
            row=1,
        )
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        """Toon bevestigingsbericht voordat archief wordt verwijderd."""
        # Maak bevestigingsview met verwijzing naar origineel bericht
        confirmation_view = ConfirmDeleteView(
            self.parent_view.guild_id,
            self.parent_view.channel_id,
            interaction.message,
        )

        # Stuur bevestigingsbericht als ephemeral followup
        await interaction.response.send_message(
            "⚠️ **Weet je zeker dat je het archief permanent wilt verwijderen?**\n"
            "Deze actie kan niet ongedaan worden gemaakt.",
            view=confirmation_view,
            ephemeral=True,
        )


class ConfirmDeleteView(View):
    """Bevestigingsview voor het verwijderen van archief."""

    def __init__(
        self,
        guild_id: int | None,
        channel_id: int | None,
        original_message: discord.Message | None,
    ):
        super().__init__(timeout=60)  # 60 seconden timeout
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.original_message = original_message

        # Voeg knoppen toe
        self.add_item(CancelButton())
        self.add_item(ConfirmDeleteButton(self))


class CancelButton(Button):
    """Annuleer knop - sluit bevestigingsbericht."""

    def __init__(self):
        super().__init__(
            label="Annuleer",
            style=discord.ButtonStyle.success,  # Green button
            custom_id="cancel_delete",
        )

    async def callback(self, interaction: discord.Interaction):
        """Sluit bevestigingsbericht."""
        await interaction.response.edit_message(
            content="❌ Verwijdering geannuleerd.",
            view=None,
        )


class ConfirmDeleteButton(Button):
    """Bevestig verwijdering knop - voert daadwerkelijke verwijdering uit."""

    def __init__(self, parent_view: "ConfirmDeleteView"):
        super().__init__(
            label="Verwijder Archief",
            style=discord.ButtonStyle.danger,  # Red button
            custom_id="confirm_delete_archive",
        )
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        """Verwijder archief en update beide berichten."""
        ok = delete_archive_scoped(
            self.parent_view.guild_id, self.parent_view.channel_id
        )

        if ok:
            # Update bevestigingsbericht
            await interaction.response.edit_message(
                content="🗑️ Archief verwijderd.",
                view=None,
            )

            # Update originele bericht om verwijdering aan te geven
            if self.parent_view.original_message is not None:
                deleted_content = (
                    "❌ **Archief verwijderd**\n"
                    "Er is momenteel geen archief beschikbaar."
                )
                await self.parent_view.original_message.edit(
                    content=deleted_content,
                    attachments=[],
                    view=None,
                )
        else:
            # Als archief niet bestond
            await interaction.response.edit_message(
                content="⚠️ Er was geen archief om te verwijderen.",
                view=None,
            )

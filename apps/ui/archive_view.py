# apps/ui/archive_view.py

import io

import discord
from discord import File
from discord.ui import Button, Select, View

from apps.utils.archive import create_archive, delete_archive_scoped
from apps.utils.i18n import t


class ArchiveView(View):
    """View met dropdown voor CSV formaat selectie en delete knop."""

    def __init__(self, guild_id: int | None = None, channel_id: int | None = None, weekday: bool = False):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.weekday = weekday
        self.selected_delimiter = ","  # Default

        cid = channel_id or 0

        # Add SelectMenu (row 0)
        self.add_item(DelimiterSelectMenu(self, cid))

        # Add Delete button (row 1, red)
        self.add_item(DeleteArchiveButton(self, cid))


class DelimiterSelectMenu(Select):
    """SelectMenu voor delimiter keuze - update bestand direct bij selectie."""

    def __init__(self, parent_view: "ArchiveView", channel_id: int = 0):
        self.parent_view = parent_view
        self._channel_id = channel_id

        options = [
            discord.SelectOption(
                label="🇺🇸 Comma (,)",
                value=",",
                description=t(channel_id, "ARCHIVE.standard_delimiter"),
                default=True,
            ),
            discord.SelectOption(
                label="🇳🇱 Semicolon (;)",
                value=";",
                description=t(channel_id, "ARCHIVE.dutch_delimiter"),
            ),
        ]

        super().__init__(
            placeholder=t(channel_id, "ARCHIVE.select_format"),
            options=options,
            custom_id="delimiter_select",
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        """Update CSV bestand met geselecteerde delimiter."""
        self.parent_view.selected_delimiter = self.values[0]
        cid = self._channel_id

        # Update default option
        for option in self.options:
            option.default = option.value == self.values[0]

        # Genereer CSV met gekozen delimiter
        csv_data = create_archive(
            self.parent_view.guild_id,
            self.parent_view.channel_id,
            self.parent_view.selected_delimiter,
            self.parent_view.weekday,
        )

        if not csv_data:
            await interaction.response.send_message(
                t(cid, "ERRORS.archive_generate_failed"), ephemeral=True
            )
            return

        # Genereer bestandsnaam
        guild_id = self.parent_view.guild_id or 0
        channel_id = self.parent_view.channel_id or 0
        archive_type = "weekday" if self.parent_view.weekday else "weekend"
        filename = f"dmk_archive_{guild_id}_{channel_id}_{archive_type}.csv"

        # Behoud de originele tekst van het bericht
        if self.parent_view.weekday:
            message_content = t(cid, "ARCHIVE.archive_message_weekday")
        else:
            message_content = t(cid, "ARCHIVE.archive_message_weekend")

        # Update bericht met nieuw CSV bestand
        await interaction.response.edit_message(
            content=message_content,
            attachments=[File(io.BytesIO(csv_data), filename=filename)],
            view=self.parent_view,
        )


class DeleteArchiveButton(Button):
    """Delete knop om archief te verwijderen."""

    def __init__(self, parent_view: "ArchiveView", channel_id: int = 0):
        self._channel_id = channel_id
        super().__init__(
            label=t(channel_id, "ARCHIVE.delete_button"),
            style=discord.ButtonStyle.danger,  # Red button
            custom_id="delete_archive_scoped",
            row=1,
        )
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        """Toon bevestigingsbericht voordat archief wordt verwijderd."""
        cid = self._channel_id

        # Maak bevestigingsview met verwijzing naar origineel bericht
        confirmation_view = ConfirmDeleteView(
            self.parent_view.guild_id,
            self.parent_view.channel_id,
            interaction.message,
            cid,
        )

        # Stuur bevestigingsbericht als ephemeral followup
        await interaction.response.send_message(
            t(cid, "ARCHIVE.confirm_delete"),
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
        i18n_channel_id: int = 0,
    ):
        super().__init__(timeout=60)  # 60 seconden timeout
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.original_message = original_message
        self._i18n_channel_id = i18n_channel_id

        # Voeg knoppen toe
        self.add_item(CancelButton(i18n_channel_id))
        self.add_item(ConfirmDeleteButton(self, i18n_channel_id))


class CancelButton(Button):
    """Annuleer knop - sluit bevestigingsbericht."""

    def __init__(self, channel_id: int = 0):
        self._channel_id = channel_id
        super().__init__(
            label=t(channel_id, "UI.cancel_button"),
            style=discord.ButtonStyle.success,  # Green button
            custom_id="cancel_delete",
        )

    async def callback(self, interaction: discord.Interaction):
        """Sluit bevestigingsbericht."""
        await interaction.response.edit_message(
            content=t(self._channel_id, "ARCHIVE.deletion_cancelled"),
            view=None,
        )


class ConfirmDeleteButton(Button):
    """Bevestig verwijdering knop - voert daadwerkelijke verwijdering uit."""

    def __init__(self, parent_view: "ConfirmDeleteView", channel_id: int = 0):
        self._channel_id = channel_id
        super().__init__(
            label=t(channel_id, "ARCHIVE.confirm_delete_button"),
            style=discord.ButtonStyle.danger,  # Red button
            custom_id="confirm_delete_archive",
        )
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        """Verwijder archief en update beide berichten."""
        cid = self._channel_id
        ok = delete_archive_scoped(
            self.parent_view.guild_id, self.parent_view.channel_id
        )

        if ok:
            # Update bevestigingsbericht
            await interaction.response.edit_message(
                content=t(cid, "ARCHIVE.deleted"),
                view=None,
            )

            # Update originele bericht om verwijdering aan te geven
            if self.parent_view.original_message is not None:
                await self.parent_view.original_message.edit(
                    content=t(cid, "ARCHIVE.deleted_no_archive"),
                    attachments=[],
                    view=None,
                )
        else:
            # Als archief niet bestond
            await interaction.response.edit_message(
                content=t(cid, "ARCHIVE.nothing_to_delete"),
                view=None,
            )

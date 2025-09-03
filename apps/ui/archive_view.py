# apps/ui/archive_view.py

import discord
from discord.ui import Button, View

from apps.utils.archive import delete_archive


class ArchiveDeleteView(View):
    """Knop om het archief te verwijderen na downloaden."""

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(DeleteArchiveButton())


class DeleteArchiveButton(Button):
    def __init__(self):
        super().__init__(
            label="🗑️ Verwijder archief",
            style=discord.ButtonStyle.danger,
            custom_id="delete_archive",
        )

    async def callback(self, interaction: discord.Interaction):
        ok = delete_archive()

        if ok:
            # Eerste antwoord op de interaction (ephemeral)
            await interaction.response.send_message(
                "🗑️ Archief verwijderd.", ephemeral=True
            )

            # Knop weghalen uit het originele bericht (alleen als dat bericht bestaat)
            if interaction.message is not None:
                await interaction.message.edit(view=None)
        else:
            # Ook hier: direct response gebruiken, geen followup nodig
            await interaction.response.send_message(
                "⚠️ Er was geen archief om te verwijderen.", ephemeral=True
            )

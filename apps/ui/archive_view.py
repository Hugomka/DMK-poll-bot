# apps/ui/archive_view.py

import discord

from discord.ui import View, Button
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
            custom_id="delete_archive"
        )

    async def callback(self, interaction: discord.Interaction):
        ok = delete_archive()
        if ok:
            await interaction.followup.send(f"🗑️ Archief verwijderd.", ephemeral=True)
            # Verwijder de knop na succesvol wissen
            await interaction.message.edit(view=None)
        else:
            await interaction.followup.send(f"⚠️ Er was geen archief om te verwijderen.", ephemeral=True)

# apps/ui/name_toggle_view.py

import discord
from discord.ui import View, Button
from apps.utils.poll_settings import toggle_name_display
from apps.utils.poll_message import update_poll_message

class NaamToggleView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ToggleNamenButton())

class ToggleNamenButton(Button):
    def __init__(self):
        super().__init__(
            label="🧑‍🤝‍🧑 Wissel namen",
            style=discord.ButtonStyle.primary,
            custom_id="toggle_namen"
        )

    async def callback(self, interaction: discord.Interaction):
        nieuw = toggle_name_display(interaction.channel.id)
        status = "zichtbaar" if nieuw else "anoniem"

        # Herbouw publieke pollberichten
        for dag in ["vrijdag", "zaterdag", "zondag"]:
            await update_poll_message(interaction.channel, dag)

        await interaction.response.edit_message(content=f"✅ Namen zijn nu **{status}**", view=None)

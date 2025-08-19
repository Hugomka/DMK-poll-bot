# apps/ui/name_toggle_view.py

import discord
from discord.ui import View, Button
from apps.utils.poll_settings import is_name_display_enabled, toggle_name_display, is_paused, get_setting
from apps.utils.poll_storage import load_votes
from apps.entities.poll_option import get_poll_options

class NaamToggleView(View):
    def __init__(self, channel_id: int):
        super().__init__(timeout=None)
        namen_aan = is_name_display_enabled(channel_id)
        self.add_item(ToggleNamenButton(namen_aan))

class ToggleNamenButton(Button):
    from apps.ui.name_toggle_view import NaamToggleView  # ← jezelf importeren mag in dit geval

    def __init__(self, namen_aan: bool):
        label = "🙈 Namen verbergen" if namen_aan else "👤 Namen tonen"
        super().__init__(
            label=label,
            style=discord.ButtonStyle.primary,
            custom_id="toggle_namen"
        )
        self.namen_aan = namen_aan  # onthoud huidige status

    async def callback(self, interaction: discord.Interaction):
        nieuw = toggle_name_display(interaction.channel.id)
        namen_txt = "zichtbaar" if nieuw else "anoniem"
        pauze_txt = "Ja" if is_paused(interaction.channel.id) else "Nee"

        # Embed opnieuw opbouwen
        embed = discord.Embed(
            title="📊 DMK-poll status",
            description=f"⏸️ Pauze: **{pauze_txt}**\n👤 Namen: **{namen_txt}**",
            color=discord.Color.blurple()
        )

        all_votes = await load_votes()
        guild = interaction.guild

        for dag in ["vrijdag", "zaterdag", "zondag"]:
            instelling = get_setting(interaction.channel.id, dag)
            zicht_txt = "altijd zichtbaar" if instelling.get("modus") == "altijd" else f"deadline {instelling.get('tijd', '18:00')}"

            regels: list[str] = []

            for opt in get_poll_options():
                if opt.dag != dag:
                    continue

                stemmers = []
                for user_id, user_votes in all_votes.items():
                    if opt.tijd in user_votes.get(dag, []):
                        member = guild.get_member(int(user_id))
                        if member is None:
                            try:
                                member = await guild.fetch_member(int(user_id))
                            except discord.NotFound:
                                member = None
                        if member:
                            stemmers.append(member.mention)

                n = len(stemmers)
                regel = f"{opt.emoji} {opt.tijd} — **{n}** stemmen"
                if nieuw and stemmers:
                    regel += f":  {', '.join(stemmers)}"
                regels.append(regel)

            value = "\n".join(regels) if regels else "_(geen opties gevonden)_"
            embed.add_field(name=f"{dag.capitalize()} ({zicht_txt})", value=value, inline=False)

        # ✨ Vervang de embed en laat de knop staan
        new_view = NaamToggleView(interaction.channel.id)  # nieuwe view met nieuwe label
        await interaction.response.edit_message(embed=embed, view=new_view)

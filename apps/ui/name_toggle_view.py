import discord
from discord.ui import View, Button
from apps.utils.poll_settings import is_name_display_enabled, toggle_name_display, is_paused, get_setting
from apps.utils.poll_storage import load_votes
from apps.entities.poll_option import get_poll_options
from apps.utils.message_builder import build_grouped_names_for

class NaamToggleView(View):
    def __init__(self, channel_id: int):
        super().__init__(timeout=None)
        namen_aan = is_name_display_enabled(channel_id)
        self.add_item(ToggleNamenButton(namen_aan))

class ToggleNamenButton(Button):
    def __init__(self, namen_aan: bool):
        label = "🙈 Namen verbergen" if namen_aan else "👤 Namen tonen"
        super().__init__(label=label, style=discord.ButtonStyle.primary, custom_id="toggle_namen")
        self.namen_aan = namen_aan

    async def callback(self, interaction: discord.Interaction):
        try:
            nieuw = toggle_name_display(interaction.channel.id)
            namen_txt = "zichtbaar" if nieuw else "anoniem"
            pauze_txt = "Ja" if is_paused(interaction.channel.id) else "Nee"

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

                    totaal, groepen_txt = await build_grouped_names_for(dag, opt.tijd, guild, all_votes)

                    regel = f"{opt.emoji} {opt.tijd} — **{totaal}** stemmen"
                    if nieuw and groepen_txt:
                        regel += f":  {groepen_txt}"
                    regels.append(regel)

                value = "\n".join(regels) if regels else "_(geen opties gevonden)_"
                embed.add_field(name=f"{dag.capitalize()} ({zicht_txt})", value=value, inline=False)

            # Belangrijk: bij button-callback direct de message editen (geen defer_update in jouw versie)
            new_view = NaamToggleView(interaction.channel.id)
            await interaction.response.edit_message(embed=embed, view=new_view)

        except Exception as e:
            # Zichtbare en duidelijke foutmelding + console log
            print(f"❌ Toggle-namen fout: {type(e).__name__}: {e}")
            if interaction.response.is_done():
                await interaction.followup.send(
                    f"❌ Kon de status niet bijwerken: **{type(e).__name__}** — {e}",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ Kon de status niet bijwerken: **{type(e).__name__}** — {e}",
                    ephemeral=True
                )

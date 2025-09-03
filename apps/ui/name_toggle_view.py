# apps/ui/name_toggle_view.py

import discord
from discord.ui import View, Button
from typing import Optional
from apps.utils.poll_settings import (
    is_name_display_enabled,
    toggle_name_display,
    is_paused,
    get_setting,
)
from apps.utils.poll_storage import load_votes
from apps.entities.poll_option import get_poll_options
from apps.utils.message_builder import build_grouped_names_for


class NaamToggleView(View):
    """Persistente view met een knop om namen te tonen/verbergen."""
    def __init__(self, channel_id: Optional[int] = None):
        # timeout=None => persistent
        super().__init__(timeout=None)

        # Let op: voor registratie bij startup is channel_id onbekend.
        # We zetten dan voorlopig het label op 'tonen'. Bij echte weergave
        # (edit_message in callback) maken we een nieuwe view met de echte status.
        namen_aan = is_name_display_enabled(channel_id) if channel_id else False
        self.add_item(ToggleNamenButton(namen_aan))

    @classmethod
    def is_persistent(cls) -> bool:
        # Sluit aan bij jouw bestaande stijl (zie OneStemButtonView)
        return True


class ToggleNamenButton(Button):
    def __init__(self, namen_aan: bool):
        label = "🙈 Namen verbergen" if namen_aan else "👤 Namen tonen"
        # custom_id is vereist voor persistente buttons
        super().__init__(label=label, style=discord.ButtonStyle.primary, custom_id="toggle_namen")
        self.namen_aan = namen_aan

    async def callback(self, interaction: discord.Interaction):
        try:
            channel_id = interaction.channel.id

            # 1) Toggle de instelling
            nieuw = toggle_name_display(channel_id)  # True = namen aan
            namen_txt = "zichtbaar" if nieuw else "anoniem"
            pauze_txt = "Ja" if is_paused(channel_id) else "Nee"

            # 2) Basis-embed met status
            embed = discord.Embed(
                title="📊 DMK-poll status",
                description=f"⏸️ Pauze: **{pauze_txt}**\n👤 Namen: **{namen_txt}**",
                color=discord.Color.blurple(),
            )

            # 3) Haal alle stemmen (één keer) en bouw per dag de regels
            all_votes = await load_votes()
            guild = interaction.guild

            for dag in ["vrijdag", "zaterdag", "zondag"]:
                instelling = get_setting(channel_id, dag)
                modus = instelling.get("modus", "altijd")
                tijd_val = instelling.get("tijd", "18:00")
                zicht_txt = "altijd zichtbaar" if modus == "altijd" else f"deadline {tijd_val}"

                regels: list[str] = []

                for opt in get_poll_options():
                    if opt.dag != dag:
                        continue

                    totaal, groepen_txt = await build_grouped_names_for(
                        dag, opt.tijd, guild, all_votes
                    )

                    regel = f"{opt.emoji} {opt.tijd} — **{totaal}** stemmen"
                    # Alleen namen tonen als de nieuwe stand 'aan' is
                    if nieuw and groepen_txt:
                        regel += f":  {groepen_txt}"

                    regels.append(regel)

                value = "\n".join(regels) if regels else "_(geen opties gevonden)_"
                embed.add_field(
                    name=f"{dag.capitalize()} ({zicht_txt})",
                    value=value,
                    inline=False,
                )

            # 4) Vernieuw de view zodat het label klopt met de nieuwe stand
            new_view = NaamToggleView(channel_id)

            # Belangrijk: direct de originele message editen
            await interaction.response.edit_message(embed=embed, view=new_view)

        except Exception as e:
            # Vriendelijke foutmelding voor de gebruiker + log in console
            print(f"❌ Toggle-namen fout: {type(e).__name__}: {e}")
            if interaction.response.is_done():
                await interaction.followup.send(
                    f"❌ Kon de status niet bijwerken: **{type(e).__name__}** — {e}",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    f"❌ Kon de status niet bijwerken: **{type(e).__name__}** — {e}",
                    ephemeral=True,
                )

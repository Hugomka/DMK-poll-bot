# apps/ui/name_toggle_view.py
from typing import Optional

import discord
from discord.ui import Button, View

from apps.entities.poll_option import get_poll_options
from apps.utils.message_builder import build_grouped_names_for
from apps.utils.poll_settings import (
    get_setting,
    is_name_display_enabled,
    is_paused,
    toggle_name_display,
)
from apps.utils.poll_storage import load_votes


class NaamToggleView(View):
    """Persistente view met een knop om namen te tonen/verbergen."""

    def __init__(self, channel_id: Optional[int] = None):
        super().__init__(timeout=None)
        # Als channel_id onbekend is tijdens startup, zet label voorlopig uit
        namen_aan = is_name_display_enabled(channel_id) if channel_id else False
        self.add_item(ToggleNamenButton(namen_aan))

    @classmethod
    def is_persistent(cls) -> bool:
        return True


class ToggleNamenButton(Button):
    def __init__(self, namen_aan: bool):
        label = "🙈 Namen verbergen" if namen_aan else "👤 Namen tonen"
        super().__init__(
            label=label, style=discord.ButtonStyle.primary, custom_id="toggle_namen"
        )
        self.namen_aan = namen_aan

    async def callback(self, interaction: discord.Interaction):
        try:
            # Gebruik de veilige properties; kunnen None zijn
            channel_id = interaction.channel_id
            guild = interaction.guild
            guild_id = int(
                getattr(interaction, "guild_id", 0) or getattr(guild, "id", 0) or 0
            )

            if channel_id is None or guild is None or guild_id == 0:
                # Geen geldige server/kanalencontext -> netjes melden
                if interaction.response.is_done():
                    await interaction.followup.send(
                        "⚠️ Deze knop werkt alleen in een serverkanaal.", ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "⚠️ Deze knop werkt alleen in een serverkanaal.", ephemeral=True
                    )
                return

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

            # 3) Haal ALLEEN gescopeerde stemmen (guild+channel) en bouw per dag de regels
            all_votes = await load_votes(guild_id, channel_id)

            for dag in ["vrijdag", "zaterdag", "zondag"]:
                instelling = get_setting(channel_id, dag)
                modus = instelling.get("modus", "altijd")
                tijd_val = instelling.get("tijd", "18:00")
                zicht_txt = (
                    "altijd zichtbaar" if modus == "altijd" else f"deadline {tijd_val}"
                )

                regels: list[str] = []

                for opt in get_poll_options():
                    if opt.dag != dag:
                        continue

                    totaal, groepen_txt = await build_grouped_names_for(
                        dag, opt.tijd, guild, all_votes
                    )

                    regel = f"{opt.emoji} {opt.tijd} — **{totaal}** stemmen"
                    if nieuw and groepen_txt:
                        regel += f":  {groepen_txt}"

                    regels.append(regel)

                value = "\n".join(regels) if regels else "_(geen opties gevonden)_"
                embed.add_field(
                    name=f"{dag.capitalize()} ({zicht_txt})",
                    value=value,
                    inline=False,
                )

            # 4) View vernieuwen zodat label klopt met nieuwe stand
            new_view = NaamToggleView(channel_id)

            # Originele bericht editen via interaction response
            await interaction.response.edit_message(embed=embed, view=new_view)

        except Exception as e:
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

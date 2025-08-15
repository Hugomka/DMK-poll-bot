# apps\ui\poll_buttons.py

from discord.ui import View, Button
from discord import Interaction, ButtonStyle

from apps.utils.poll_settings import is_paused
from apps.utils.poll_storage import toggle_vote, get_user_votes
from apps.utils.poll_message import update_poll_message
from apps.entities.poll_option import get_poll_options

class PollButtonView(View):
    """Ephemeral knoppen voor ALLE opties; jouw eigen keuzes lichten op."""
    def __init__(self, user_id: str = ""):
        super().__init__(timeout=60)
        votes = get_user_votes(user_id) if user_id else {}

        for option in get_poll_options():
            selected = option.tijd in votes.get(option.dag, [])
            stijl = ButtonStyle.success if selected else ButtonStyle.secondary
            label = f"✅ {option.label}" if selected else option.label
            self.add_item(PollButton(option.dag, option.tijd, label, stijl))

class PollButton(Button):
    def __init__(self, dag, tijd, label, stijl):
        super().__init__(label=label, style=stijl, custom_id=f"{dag}:{tijd}")
        self.dag = dag
        self.tijd = tijd

    async def callback(self, interaction: Interaction):
        try:
            # Blokkeer stemmen tijdens pauze
            if is_paused(interaction.channel.id):
                # Werk het huidige ephemeral NIET bij (er verandert niets), geef melding
                if interaction.response.is_done():
                    await interaction.followup.send("⏸️ Stemmen is gepauzeerd. Probeer later opnieuw.", ephemeral=True)
                else:
                    await interaction.response.send_message("⏸️ Stemmen is gepauzeerd. Probeer later opnieuw.", ephemeral=True)
                return

            user_id = str(interaction.user.id)

            # Toggle stem
            toggle_vote(user_id, self.dag, self.tijd)

            # Zelfde ephemeral direct verversen (kleuren/✅)
            if interaction.response.is_done():
                await interaction.edit_original_response(view=PollButtonView(user_id))
            else:
                await interaction.response.edit_message(view=PollButtonView(user_id))

            # Publieke dagberichten verversen (aantallen)
            await update_poll_message(interaction.channel)

        except Exception as e:
            try:
                await interaction.followup.send(f"❌ Er ging iets mis: {e}", ephemeral=True)
            except:
                pass

# Publieke 1-knop view
class OpenStemmenButton(Button):
    def __init__(self, paused: bool = False):
        label = "🗳️ Stemmen (gepauzeerd)" if paused else "🗳️ Stemmen"
        style = ButtonStyle.secondary if paused else ButtonStyle.primary
        super().__init__(label=label, style=style, custom_id="open_stemmen", disabled=paused)
        self.paused = paused

    async def callback(self, interaction: Interaction):
        # Extra check: als er intussen gepauzeerd is, blokkeer.
        if is_paused(interaction.channel.id):
            await interaction.response.send_message("⏸️ Stemmen is tijdelijk gepauzeerd.", ephemeral=True)
            return

        await interaction.response.send_message(
            "Kies jouw tijden hieronder 👇 (alleen jij ziet dit).",
            view=PollButtonView(str(interaction.user.id)),
            ephemeral=True
        )

class OneStemButtonView(View):
    """Publieke 1-knop-view. Disabled wanneer gepauzeerd."""
    def __init__(self, paused: bool = False):
        super().__init__(timeout=None)
        self.add_item(OpenStemmenButton(paused))


# (optioneel) blijvende compat met jouw /dmk-poll-dagen
class DailyPollView(View):
    def __init__(self, dag: str, tijden: list[str]):
        super().__init__(timeout=None)

        def match_opt(dag: str, tijd: str):
            # zoek dynamisch in de live opties
            for o in get_poll_options():
                if o.dag != dag:
                    continue
                if tijd in ("19:00", "20:30"):
                    if o.tijd.endswith(f"{tijd} uur"):
                        return o
                elif tijd == "misschien" and o.tijd == "misschien":
                    return o
            return None

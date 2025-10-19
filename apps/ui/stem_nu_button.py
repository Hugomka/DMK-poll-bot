# apps/ui/stem_nu_button.py
#
# "Stem Nu" button voor Misschien-bevestiging (17:00-18:00)
#
# Flow:
# 1. Gebruiker klikt "Stem nu"
# 2. Check huidige stem:
#    - Misschien: Toon Ja/Nee dialoog voor leidende tijd
#    - Al gestemd voor tijd: Toon bevestiging (readonly)
#    - ❌ niet meedoen: Toon bevestiging (readonly)
# 3. Na Ja/Nee keuze: update stem, update poll, verwijder uit notificatie

import asyncio

from discord import ButtonStyle, Interaction
from discord.ui import Button, View

from apps.utils.poll_message import update_poll_message
from apps.utils.poll_storage import add_vote, get_user_votes, remove_vote


class StemNuButton(Button):
    """De 'Stem nu' knop onder het notificatiebericht (17:00-18:00)."""

    def __init__(self):
        super().__init__(
            label="🗳️ Stem nu",
            style=ButtonStyle.primary,
            custom_id="stem_nu_confirm",
        )

    async def callback(self, interaction: Interaction):
        """
        Handler voor "Stem nu" knop.

        Controleert de huidige stem van de gebruiker en toont:
        - Misschien: Ja/Nee dialoog
        - Al gestemd: Readonly bevestiging
        - ❌ niet meedoen: Readonly bevestiging
        """
        try:
            channel_id = interaction.channel_id
            if channel_id is None:
                await interaction.response.send_message(
                    "⚠️ Deze knop werkt alleen in een serverkanaal.", ephemeral=True
                )
                return

            user_id = str(interaction.user.id)
            guild_id = int(
                interaction.guild_id or getattr(interaction.guild, "id", 0) or 0
            )

            # Haal custom_id op uit het bericht (format: "stem_nu:dag:tijd")
            # Dit wordt gezet door de scheduler bij het aanmaken van de knop
            # Voor nu, halen we de dag uit de knop metadata (zie create view)
            # Workaround: we moeten de dag en tijd doorgeven via de view
            view = self.view
            if not isinstance(view, StemNuView):
                await interaction.response.send_message(
                    "⚠️ Fout: kon dag/tijd niet bepalen.", ephemeral=True
                )
                return

            dag = view.dag
            leading_time = view.leading_time

            # Haal huidige stemmen op
            votes = await get_user_votes(user_id, guild_id, channel_id)
            current_votes = votes.get(dag, [])

            # Check wat de gebruiker heeft gestemd
            if "misschien" in current_votes:
                # Toon Ja/Nee dialoog
                confirmation_view = ConfirmationView(
                    user_id=user_id,
                    guild_id=guild_id,
                    channel_id=channel_id,
                    dag=dag,
                    leading_time=leading_time,
                )
                await interaction.response.send_message(
                    f"💬 Wil je vanavond om **{leading_time}** meedoen?",
                    view=confirmation_view,
                    ephemeral=True,
                )
            elif "niet meedoen" in current_votes:
                # Al ❌ gestemd
                await interaction.response.send_message(
                    "ℹ️ Je hebt al voor **niet meedoen** gestemd.",
                    ephemeral=True,
                )
                # Auto-delete na 20 seconden
                await asyncio.sleep(20)
                try:
                    await interaction.delete_original_response()
                except Exception:  # pragma: no cover
                    pass
            elif any(
                tijd in current_votes for tijd in ["om 19:00 uur", "om 20:30 uur"]
            ):
                # Al voor een tijd gestemd
                tijden_str = ", ".join(
                    t for t in current_votes if t in ["om 19:00 uur", "om 20:30 uur"]
                )
                await interaction.response.send_message(
                    f"ℹ️ Je hebt al voor **{tijden_str}** gestemd.",
                    ephemeral=True,
                )
                # Auto-delete na 20 seconden
                await asyncio.sleep(20)
                try:
                    await interaction.delete_original_response()
                except Exception:  # pragma: no cover
                    pass
            else:
                # Geen stem? Dit zou niet moeten gebeuren
                await interaction.response.send_message(
                    "⚠️ Je hebt nog niet gestemd voor deze dag.",
                    ephemeral=True,
                )

        except Exception as e:  # pragma: no cover
            print(f"⚠️ Fout in StemNuButton.callback: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "⚠️ Er ging iets mis. Probeer het later opnieuw.",
                        ephemeral=True,
                    )
            except Exception:  # pragma: no cover
                pass


class ConfirmationView(View):
    """Ja/Nee dialoog voor Misschien-bevestiging."""

    def __init__(
        self,
        user_id: str,
        guild_id: int,
        channel_id: int,
        dag: str,
        leading_time: str,
    ):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.dag = dag
        self.leading_time = leading_time

        # Voeg Ja en Nee knoppen toe
        self.add_item(JaButton(self))
        self.add_item(NeeButton(self))


class JaButton(Button):
    """Ja-knop: update stem naar leading_time."""

    def __init__(self, parent_view: ConfirmationView):
        super().__init__(
            label="✅ Ja",
            style=ButtonStyle.success,
            custom_id="ja_confirm",
        )
        self.parent_view = parent_view

    async def callback(self, interaction: Interaction):
        try:
            # Verwijder "misschien" stem
            await remove_vote(
                self.parent_view.user_id,
                self.parent_view.dag,
                "misschien",
                self.parent_view.guild_id,
                self.parent_view.channel_id,
            )

            # Voeg stem toe voor leading time
            tijd_full = (
                "om 19:00 uur"
                if self.parent_view.leading_time == "19:00"
                else "om 20:30 uur"
            )
            await add_vote(
                self.parent_view.user_id,
                self.parent_view.dag,
                tijd_full,
                self.parent_view.guild_id,
                self.parent_view.channel_id,
            )

            # Update poll bericht
            if interaction.channel is not None:
                asyncio.create_task(
                    update_poll_message(interaction.channel, self.parent_view.dag)
                )

            # Bevestiging
            await interaction.response.edit_message(
                content=f"✅ Je stem is geregistreerd voor **{self.parent_view.leading_time}**!",
                view=None,
            )

            # TODO: In toekomst: real-time update notificatiebericht (verwijder mention)

        except Exception as e:  # pragma: no cover
            print(f"⚠️ Fout in JaButton.callback: {e}")
            try:
                await interaction.response.send_message(
                    "⚠️ Er ging iets mis bij het verwerken van je stem.",
                    ephemeral=True,
                )
            except Exception:  # pragma: no cover
                pass


class NeeButton(Button):
    """Nee-knop: update stem naar ❌ niet meedoen."""

    def __init__(self, parent_view: ConfirmationView):
        super().__init__(
            label="❌ Nee",
            style=ButtonStyle.danger,
            custom_id="nee_confirm",
        )
        self.parent_view = parent_view

    async def callback(self, interaction: Interaction):
        try:
            # Verwijder "misschien" stem
            await remove_vote(
                self.parent_view.user_id,
                self.parent_view.dag,
                "misschien",
                self.parent_view.guild_id,
                self.parent_view.channel_id,
            )

            # Voeg ❌ stem toe
            await add_vote(
                self.parent_view.user_id,
                self.parent_view.dag,
                "niet meedoen",
                self.parent_view.guild_id,
                self.parent_view.channel_id,
            )

            # Update poll bericht
            if interaction.channel is not None:
                asyncio.create_task(
                    update_poll_message(interaction.channel, self.parent_view.dag)
                )

            # Bevestiging
            await interaction.response.edit_message(
                content="ℹ️ Je hebt aangegeven **niet mee te doen**.",
                view=None,
            )

            # TODO: In toekomst: real-time update notificatiebericht (verwijder mention)

        except Exception as e:  # pragma: no cover
            print(f"⚠️ Fout in NeeButton.callback: {e}")
            try:
                await interaction.response.send_message(
                    "⚠️ Er ging iets mis bij het verwerken van je stem.",
                    ephemeral=True,
                )
            except Exception:  # pragma: no cover
                pass


class StemNuView(View):
    """View met "Stem nu" knop voor notificatiebericht."""

    def __init__(self, dag: str, leading_time: str):
        super().__init__(timeout=None)  # Permanent (tot 18:00)
        self.dag = dag
        self.leading_time = leading_time
        self.add_item(StemNuButton())


def create_stem_nu_view(dag: str, leading_time: str) -> StemNuView:
    """Factory functie voor het maken van een Stem Nu view."""
    return StemNuView(dag=dag, leading_time=leading_time)

# apps/ui/poll_options_settings.py
#
# UI voor poll-opties instellingen met toggle buttons

from datetime import datetime

import discord

from apps.utils.discord_client import fetch_message_or_none, safe_call
from apps.utils.poll_message import (
    clear_message_id,
    get_message_id,
    is_channel_disabled,
    save_message_id,
    schedule_poll_update,
)
from apps.utils.poll_settings import (
    DAYS_INDEX,
    WEEK_DAYS,
    get_all_poll_options_state,
    is_day_completely_disabled,
    toggle_poll_option,
)
from apps.utils.poll_storage import get_votes_for_option


async def _heeft_poll_stemmen(
    channel_id: int, guild_id: int, dag: str, tijd: str
) -> bool:
    """
    Check of een poll-optie al stemmen heeft.

    Args:
        channel_id: Het kanaal ID
        guild_id: Het guild ID
        dag: 'maandag' t/m 'zondag'
        tijd: '19:00' | '20:30'

    Returns:
        True als er al stemmen zijn, anders False
    """
    # Converteer tijd naar poll_option format
    tijd_key = "om 19:00 uur" if tijd == "19:00" else "om 20:30 uur"

    try:
        stemmen = await get_votes_for_option(dag, tijd_key, guild_id, channel_id)
        return stemmen > 0
    except Exception:  # pragma: no cover
        return False


def _is_poll_in_verleden(dag: str, tijd: str, now: datetime | None = None) -> bool:
    """
    Check of een poll-optie in het verleden ligt.

    Args:
        dag: 'maandag' t/m 'zondag'
        tijd: '19:00' | '20:30'
        now: Huidige datetime (optioneel, voor testing)

    Returns:
        True als poll in verleden, anders False
    """
    if now is None:
        now = datetime.now()

    target_weekday = DAYS_INDEX.get(dag)
    if target_weekday is None:
        return False

    current_weekday = now.weekday()

    # Dag is in het verleden
    if current_weekday > target_weekday:
        return True

    # Dag is in de toekomst
    if current_weekday < target_weekday:
        return False

    # Zelfde dag - check tijd
    uur = 19 if tijd == "19:00" else 20
    minuut = 0 if tijd == "19:00" else 30

    poll_tijd = now.replace(hour=uur, minute=minuut, second=0, microsecond=0)
    return now >= poll_tijd


class PollOptionsSettingsView(discord.ui.View):
    """View met 14 toggle buttons voor poll-opties (7 dagen × 2 tijden)."""

    def __init__(
        self,
        channel_id: int,
        channel: discord.TextChannel,
        guild_id: int,
        votes_per_option: dict[str, int] | None = None,
    ):
        super().__init__(timeout=None)  # Persistent view
        self.channel_id = channel_id
        self.channel = channel
        self.guild_id = guild_id

        # Haal huidige status op
        states = get_all_poll_options_state(channel_id)

        # Voeg buttons toe in logische volgorde (alle weekdagen)
        for dag in WEEK_DAYS:
            for tijd in ["19:00", "20:30"]:
                key = f"{dag}_{tijd}"
                enabled = states.get(key, True)

                # Bepaal of deze optie al stemmen heeft (uit cache of default False)
                heeft_stemmen = False
                if votes_per_option:
                    tijd_key = "om 19:00 uur" if tijd == "19:00" else "om 20:30 uur"
                    optie_key = f"{dag}_{tijd_key}"
                    heeft_stemmen = votes_per_option.get(optie_key, 0) > 0

                self.add_item(
                    PollOptionButton(dag, tijd, enabled, heeft_stemmen, guild_id)
                )


class PollOptionButton(discord.ui.Button):
    """Toggle button voor een specifieke poll optie."""

    def __init__(
        self, dag: str, tijd: str, enabled: bool, heeft_stemmen: bool, guild_id: int
    ):
        self.dag = dag
        self.tijd = tijd
        self.enabled = enabled
        self.heeft_stemmen = heeft_stemmen
        self.guild_id = guild_id

        # Label en emoji - consistent met poll_options.json
        emoji_map = {
            "maandag_19:00": "🟥",
            "maandag_20:30": "🟧",
            "dinsdag_19:00": "🟨",
            "dinsdag_20:30": "⬜",
            "woensdag_19:00": "🟩",
            "woensdag_20:30": "🟦",
            "donderdag_19:00": "🟪",
            "donderdag_20:30": "🟫",
            "vrijdag_19:00": "🔴",
            "vrijdag_20:30": "🟠",
            "zaterdag_19:00": "🟡",
            "zaterdag_20:30": "⚪",
            "zondag_19:00": "🟢",
            "zondag_20:30": "🔵",
        }
        emoji = emoji_map.get(f"{dag}_{tijd}", "⚪")
        label = f"{dag.capitalize()} {tijd}"

        # Bepaal button style op basis van logica:
        # 1. Disabled (uit) -> grijs
        # 2. Enabled + (toekomst OF heeft stemmen) -> groen
        # 3. Enabled + verleden + geen stemmen -> blauw
        if not enabled:
            style = discord.ButtonStyle.secondary  # Grijs
        else:
            in_verleden = _is_poll_in_verleden(dag, tijd)
            if in_verleden and not heeft_stemmen:
                style = discord.ButtonStyle.primary  # Blauw
            else:
                style = discord.ButtonStyle.success  # Groen

        super().__init__(
            style=style,
            label=label,
            emoji=emoji,
            custom_id=f"poll_option_{dag}_{tijd}",
        )

    async def callback(self, interaction: discord.Interaction):
        """Toggle de poll optie en refresh de poll messages."""
        channel_id = interaction.channel_id
        if not channel_id:  # pragma: no cover
            await interaction.response.send_message(
                "❌ Kan channel ID niet bepalen.", ephemeral=True
            )
            return

        try:
            # Toggle de optie
            nieuwe_status = toggle_poll_option(channel_id, self.dag, self.tijd)

            # Update button status
            self.enabled = nieuwe_status

            # Check of deze poll al stemmen heeft (alleen relevant als we aanzetten)
            if nieuwe_status:
                self.heeft_stemmen = await _heeft_poll_stemmen(
                    channel_id, self.guild_id, self.dag, self.tijd
                )
            else:
                # Disabled - stemmen zijn niet relevant
                self.heeft_stemmen = False

            # Bepaal nieuwe button style op basis van logica:
            # 1. Disabled (uit) -> grijs
            # 2. Enabled + (toekomst OF heeft stemmen) -> groen
            # 3. Enabled + verleden + geen stemmen -> blauw (primary)
            if not nieuwe_status:
                self.style = discord.ButtonStyle.secondary  # Grijs
            else:
                in_verleden = _is_poll_in_verleden(self.dag, self.tijd)
                if in_verleden and not self.heeft_stemmen:
                    self.style = discord.ButtonStyle.primary  # Blauw
                else:
                    self.style = discord.ButtonStyle.success  # Groen

            # Update de settings message met nieuwe button states (EERST, voor response)
            await interaction.response.edit_message(view=self.view)

            # Check of bot actief is
            bot_actief = not is_channel_disabled(channel_id)

            if bot_actief:
                # Refresh poll messages (silent - geen followup message!)
                await self._refresh_poll_messages(interaction.channel)
            else:
                # Bot is niet actief - toon waarschuwing
                await interaction.followup.send(
                    "⚠️ De poll is momenteel niet actief. "
                    "Wijzigingen worden toegepast bij de volgende activatie.",
                    ephemeral=True,
                )

        except discord.NotFound:  # pragma: no cover
            # Message bestaat niet meer, negeer
            pass
        except Exception as e:  # pragma: no cover
            # Alleen errors tonen
            await interaction.followup.send(
                f"❌ Fout bij togglen poll-optie: {e}", ephemeral=True
            )

    async def _refresh_poll_messages(self, channel):
        """
        Refresh poll messages na toggle.

        Logic (efficiënt):
        - Als dag volledig disabled → verwijder message
        - Als dag message bestaat → edit de message (voeg/verwijder tijd-regel)
        - Als dag nieuw enabled (was volledig disabled) → hermaak alles voor juiste volgorde
        """
        # Guard: check of view bestaat
        if not self.view or not isinstance(
            self.view, PollOptionsSettingsView
        ):  # pragma: no cover
            return

        # BELANGRIJK: Check of poll-berichten aanwezig zijn
        # Als er geen poll-berichten zijn, betekent dit dat de poll gesloten is (sluitingsbericht actief)
        # Dan NIETS doen - geen poll-berichten aanmaken tijdens sluitingsperiode
        vrijdag_msg = get_message_id(self.view.channel_id, "vrijdag")
        zaterdag_msg = get_message_id(self.view.channel_id, "zaterdag")
        zondag_msg = get_message_id(self.view.channel_id, "zondag")

        # Als er geen enkele poll-message is, dan is de poll gesloten
        if (
            vrijdag_msg is None and zaterdag_msg is None and zondag_msg is None
        ):  # pragma: no cover
            return

        import asyncio

        # Check huidige status van alle dagen
        vrijdag_disabled = is_day_completely_disabled(self.view.channel_id, "vrijdag")
        zaterdag_disabled = is_day_completely_disabled(self.view.channel_id, "zaterdag")
        zondag_disabled = is_day_completely_disabled(self.view.channel_id, "zondag")

        # Check of messages bestaan
        vrijdag_exists = get_message_id(self.view.channel_id, "vrijdag") is not None
        zaterdag_exists = get_message_id(self.view.channel_id, "zaterdag") is not None
        zondag_exists = get_message_id(self.view.channel_id, "zondag") is not None

        # Detecteer of een dag nieuw enabled wordt (was disabled, nu enabled, maar message bestaat nog niet)
        nieuwe_dag_aanmaken = (
            (not vrijdag_disabled and not vrijdag_exists)
            or (not zaterdag_disabled and not zaterdag_exists)
            or (not zondag_disabled and not zondag_exists)
        )

        if nieuwe_dag_aanmaken:
            # Een nieuwe dag moet aangemaakt worden → verwijder alles en hermaak in juiste volgorde
            await self._recreate_all_poll_messages(channel)
        else:
            # Geen nieuwe dag → efficiënt updaten/verwijderen
            update_tasks = []

            # Voor elke dag: verwijder als volledig disabled, anders edit
            if vrijdag_disabled and vrijdag_exists:  # pragma: no cover
                update_tasks.append(self._delete_day_message(channel, "vrijdag"))
            elif not vrijdag_disabled and vrijdag_exists:  # pragma: no cover
                # Edit bestaande message (tijd toegevoegd/verwijderd)
                update_tasks.append(schedule_poll_update(channel, "vrijdag", delay=0))

            if zaterdag_disabled and zaterdag_exists:  # pragma: no cover
                update_tasks.append(self._delete_day_message(channel, "zaterdag"))
            elif not zaterdag_disabled and zaterdag_exists:  # pragma: no cover
                # Edit bestaande message (tijd toegevoegd/verwijderd)
                update_tasks.append(schedule_poll_update(channel, "zaterdag", delay=0))

            if zondag_disabled and zondag_exists:  # pragma: no cover
                update_tasks.append(self._delete_day_message(channel, "zondag"))
            elif not zondag_disabled and zondag_exists:  # pragma: no cover
                # Edit bestaande message (tijd toegevoegd/verwijderd)
                update_tasks.append(schedule_poll_update(channel, "zondag", delay=0))

            if update_tasks:  # pragma: no cover
                await asyncio.gather(*update_tasks, return_exceptions=True)

    async def _recreate_all_poll_messages(self, channel):
        """
        Verwijder en hermaak alle poll messages in de juiste volgorde.
        Wordt alleen gebruikt als een nieuwe dag enabled wordt.
        """
        # Guard: check of view bestaat
        if not self.view or not isinstance(
            self.view, PollOptionsSettingsView
        ):  # pragma: no cover
            return

        # BELANGRIJK: Check of poll-berichten aanwezig zijn
        # Als er geen poll-berichten zijn, betekent dit dat de poll gesloten is (sluitingsbericht actief)
        # Dan NIETS doen - geen poll-berichten aanmaken tijdens sluitingsperiode
        vrijdag_msg = get_message_id(self.view.channel_id, "vrijdag")
        zaterdag_msg = get_message_id(self.view.channel_id, "zaterdag")
        zondag_msg = get_message_id(self.view.channel_id, "zondag")

        # Als er geen enkele poll-message is, dan is de poll gesloten
        if (
            vrijdag_msg is None and zaterdag_msg is None and zondag_msg is None
        ):  # pragma: no cover
            return

        import asyncio

        # Stap 1: Verwijder ALLE bestaande poll messages
        all_days = WEEK_DAYS
        delete_tasks = [self._delete_day_message(channel, dag) for dag in all_days]
        await asyncio.gather(*delete_tasks, return_exceptions=True)

        # Stap 2: Check welke dagen enabled zijn
        vrijdag_disabled = is_day_completely_disabled(
            self.view.channel_id, "vrijdag"
        )  # pragma: no cover
        zaterdag_disabled = is_day_completely_disabled(
            self.view.channel_id, "zaterdag"
        )  # pragma: no cover
        zondag_disabled = is_day_completely_disabled(
            self.view.channel_id, "zondag"
        )  # pragma: no cover

        # Stap 3: Hermaak poll messages in de juiste volgorde (alleen enabled dagen)
        update_tasks = []  # pragma: no cover
        if not vrijdag_disabled:  # pragma: no cover
            update_tasks.append(schedule_poll_update(channel, "vrijdag", delay=0.1))
        if not zaterdag_disabled:  # pragma: no cover
            update_tasks.append(schedule_poll_update(channel, "zaterdag", delay=0.2))
        if not zondag_disabled:  # pragma: no cover
            update_tasks.append(schedule_poll_update(channel, "zondag", delay=0.3))

        if update_tasks:  # pragma: no cover
            await asyncio.gather(*update_tasks, return_exceptions=True)

        # Stap 4: Hermaak buttons en notificatie messages
        await self._recreate_ui_messages(channel)  # pragma: no cover

    async def _recreate_ui_messages(self, channel):
        """
        Verwijder en hermaak buttons en notificatie messages om volgorde te garanderen.

        Volgorde moet zijn:
        1. Poll messages (vrijdag, zaterdag, zondag)
        2. Buttons message (🗳️ Stemmen)
        3. Notificatie message (als die er is)
        """
        # Guard: check of view bestaat
        if not self.view or not isinstance(
            self.view, PollOptionsSettingsView
        ):  # pragma: no cover
            return

        from apps.ui.poll_buttons import OneStemButtonView  # pragma: no cover
        from apps.utils.poll_settings import is_paused  # pragma: no cover

        # 1. Verwijder oude stemmen button message
        buttons_id = get_message_id(self.view.channel_id, "stemmen")  # pragma: no cover
        if buttons_id:  # pragma: no cover
            msg = await fetch_message_or_none(channel, buttons_id)
            if msg:  # pragma: no cover
                await safe_call(msg.delete)
            clear_message_id(self.view.channel_id, "stemmen")

        # 2. Verwijder oude notificatie message
        notif_id = get_message_id(
            self.view.channel_id, "notification_persistent"
        )  # pragma: no cover
        if notif_id:  # pragma: no cover
            msg = await fetch_message_or_none(channel, notif_id)
            if msg:  # pragma: no cover
                await safe_call(msg.delete)
            clear_message_id(self.view.channel_id, "notification_persistent")

        # 3. Hermaak stemmen button message
        paused = is_paused(self.view.channel_id)  # pragma: no cover
        view = OneStemButtonView(paused=paused)  # pragma: no cover
        tekst = (  # pragma: no cover
            "⏸️ Stemmen is tijdelijk gepauzeerd."
            if paused
            else "Klik op **🗳️ Stemmen** om je keuzes te maken."
        )
        new_buttons = await safe_call(
            channel.send, content=tekst, view=view
        )  # pragma: no cover
        if new_buttons:  # pragma: no cover
            save_message_id(self.view.channel_id, "stemmen", new_buttons.id)

        # 4. Hermaak notificatie message (als die er was)
        if notif_id:  # pragma: no cover
            content = ":mega: Notificatie:\nDe DMK-poll-bot is zojuist aangezet. Veel plezier met de stemmen! 🎮"
            new_notif = await safe_call(channel.send, content=content, view=None)
            if new_notif:  # pragma: no cover
                save_message_id(
                    self.view.channel_id, "notification_persistent", new_notif.id
                )

    async def _delete_day_message(self, channel, dag: str):
        """Verwijder poll message voor een specifieke dag."""
        # Guard: check of view bestaat
        if not self.view or not isinstance(
            self.view, PollOptionsSettingsView
        ):  # pragma: no cover
            return

        try:
            message_id = get_message_id(self.view.channel_id, dag)
            if not message_id:
                return

            msg = await fetch_message_or_none(channel, message_id)
            if msg:
                await safe_call(msg.delete)

            # Clear de message ID
            clear_message_id(self.view.channel_id, dag)
        except Exception:  # pragma: no cover
            # Negeer errors (message bestaat niet meer, etc.)
            pass


def create_poll_options_settings_embed() -> discord.Embed:
    """Maak embed voor poll-opties settings."""
    embed = discord.Embed(
        title="⚙️ Instellingen Poll-opties",
        description=(
            "Activeer of deactiveer de poll-optie voor de huidige poll. "
            "Het heeft een direct effect op de huidige kanaal met de poll.\n\n"
            "⚠️ **Let op:** Bij activeren van maandag en dinsdag kunnen problemen "
            "ontstaan met de gesloten periode (default: maandag 00:00 t/m dinsdag 20:00). "
            "Pas deze periode aan via `/dmk-poll-on` zodat leden kunnen stemmen.\n\n"
            "**Status:**\n"
            "🟢 Groen = Actief (poll wordt gegenereerd)\n"
            "🔵 Blauw = Actief na reset (poll in verleden, geen stemmen)\n"
            "⚪ Grijs = Uitgeschakeld"
        ),
        color=discord.Color.blue(),
    )

    embed.set_footer(text="Klik op een knop om de status te togglen")

    return embed

# apps\commands\dmk_poll.py

import io
import discord

from datetime import datetime
from zoneinfo import ZoneInfo
from discord import app_commands, File
from discord.ext import commands
from apps.ui.name_toggle_view import NaamToggleView

from apps.entities.poll_option import get_poll_options
from apps.utils.poll_message import (
    save_message_id,
    get_message_id,
    clear_message_id,
    update_poll_message,
)
from apps.ui.poll_buttons import OneStemButtonView, PollButtonView
from apps.utils.poll_storage import get_votes_for_option, load_votes, reset_votes
from apps.utils.message_builder import build_poll_message_for_day_async
from apps.utils.poll_settings import get_setting, is_name_display_enabled, is_paused, set_visibility, should_hide_counts, toggle_paused
from apps.utils.archive import append_week_snapshot, archive_exists, open_archive_bytes, delete_archive
from apps.utils.poll_settings import toggle_name_display

try:
    from apps.ui.archive_view import ArchiveDeleteView
except Exception:
    ArchiveDeleteView = None

class DMKPoll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "🚫 Sorry, je bent geen beheerder. Je kunt deze commando niet gebruiken.",
                ephemeral=True
            )
        else:
            raise error  # laat andere fouten gewoon door

    @app_commands.default_permissions(administrator=True)
    @app_commands.command(name="dmk-poll-on", description="Plaats of update de polls per avond")
    @app_commands.checks.has_permissions(administrator=True)
    async def on(self, interaction):
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        dagen = ["vrijdag", "zaterdag", "zondag"]

        try:
            # 1) Eerste 3 berichten: ALLEEN TEKST, GEEN KNOPPEN
            for dag in dagen:
                content = await build_poll_message_for_day_async(dag, guild=channel.guild)
                mid = get_message_id(channel.id, dag)

                if mid:
                    try:
                        msg = await channel.fetch_message(mid)
                        await msg.edit(content=content, view=None)
                    except Exception:
                        msg = await channel.send(content=content, view=None)
                        save_message_id(channel.id, dag, msg.id)
                else:
                    msg = await channel.send(content=content, view=None)
                    save_message_id(channel.id, dag, msg.id)

            # 2) Vierde bericht: één knop “🗳️ Stemmen”
            key = "stemmen"
            tekst = "Klik op **🗳️ Stemmen** om je keuzes te maken."
            mid = get_message_id(channel.id, key)
            if mid:
                try:
                    msg = await channel.fetch_message(mid)
                    await msg.edit(content=tekst, view=OneStemButtonView())
                except Exception:
                    msg = await channel.send(content=tekst, view=OneStemButtonView())
                    save_message_id(channel.id, key, msg.id)
            else:
                msg = await channel.send(content=tekst, view=OneStemButtonView())
                save_message_id(channel.id, key, msg.id)

            await interaction.followup.send("✅ De polls zijn geplaatst of bijgewerkt.", ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"❌ Fout bij plaatsen: {e}", ephemeral=True)
            
    @app_commands.default_permissions(administrator=True)
    @app_commands.command(name="dmk-poll-reset", description="Reset de polls naar een nieuwe week.")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        dagen = ["vrijdag", "zaterdag", "zondag"]

        try:
            # 1) Archief bijwerken (mag mislukken zonder het command te breken)
            try:
                await append_week_snapshot()
            except Exception as e:
                print(f"⚠️ append_week_snapshot mislukte: {e}")

            # 2) Alle stemmen wissen (async!)
            await reset_votes()

            # 3) Namen direct uitschakelen
            from apps.utils.poll_settings import set_name_display
            set_name_display(channel.id, False)

            # 4) Dag-berichten updaten (zonder knoppen), met huidige zichtbaarheid/pauze
            now = datetime.now(ZoneInfo("Europe/Amsterdam"))
            paused = is_paused(channel.id)
            gevonden = False

            for dag in dagen:
                mid = get_message_id(channel.id, dag)
                if not mid:
                    continue
                gevonden = True
                try:
                    msg = await channel.fetch_message(mid)
                    hide = should_hide_counts(channel.id, dag, now)
                    content = await build_poll_message_for_day_async(dag, hide_counts=hide, pauze=paused, guild=channel.guild)
                    await msg.edit(content=content, view=None)  # ← knoppen worden niet opnieuw getoond
                except Exception as e:
                    print(f"Fout bij resetten van poll voor {dag}: {e}")

            if gevonden:
                await interaction.followup.send("🔄 De stemmen zijn gereset voor een nieuwe week.", ephemeral=True)
            else:
                await interaction.followup.send("⚠️ Geen dag-berichten gevonden om te resetten.", ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"❌ Reset mislukt: {e}", ephemeral=True)

    @app_commands.default_permissions(administrator=True)
    @app_commands.command(name="dmk-poll-pauze", description="Pauzeer of hervat alle polls")
    @app_commands.checks.has_permissions(administrator=True)
    async def pauze(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel

        try:
            # 1) Toggle pauze-status
            paused = toggle_paused(channel.id)  # True = nu gepauzeerd

            # 2) Stemmen-bericht updaten (knop disabled + tekst)
            key = "stemmen"
            mid = get_message_id(channel.id, key)
            tekst = "⏸️ Stemmen is tijdelijk gepauzeerd." if paused else "Klik op **🗳️ Stemmen** om je keuzes te maken."
            view = OneStemButtonView(paused=paused)

            if mid:
                try:
                    msg = await channel.fetch_message(mid)
                    await msg.edit(content=tekst, view=view)
                except Exception:
                    newmsg = await channel.send(content=tekst, view=view)
                    save_message_id(channel.id, key, newmsg.id)
            else:
                newmsg = await channel.send(content=tekst, view=view)
                save_message_id(channel.id, key, newmsg.id)

            status_txt = "gepauzeerd" if paused else "hervat"
            await interaction.followup.send(f"⏯️ Stemmen is {status_txt}.", ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"❌ Er ging iets mis: {e}", ephemeral=True)

    @app_commands.default_permissions(administrator=True)
    @app_commands.command(name="dmk-poll-verwijderen", description="Verwijder alle pollberichten uit het kanaal en uit het systeem.")
    @app_commands.checks.has_permissions(administrator=True)
    async def verwijderbericht(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        dagen = ["vrijdag", "zaterdag", "zondag"]

        try:
            gevonden = False

            # 1) Dag-berichten afsluiten (knop-vrij) en keys wissen
            for dag in dagen:
                mid = get_message_id(channel.id, dag)
                if not mid:
                    continue
                gevonden = True
                try:
                    msg = await channel.fetch_message(mid)
                    afsluit_tekst = "📴 Deze poll is gesloten. Dank voor je deelname."
                    await msg.edit(content=afsluit_tekst, view=None)
                except Exception as e:
                    print(f"❌ Fout bij verwijderen poll ({dag}): {e}")
                finally:
                    # key altijd opschonen
                    clear_message_id(channel.id, dag)

            # 2) Losse “Stemmen”-bericht ook opruimen
            s_mid = get_message_id(channel.id, "stemmen")
            if s_mid:
                try:
                    s_msg = await channel.fetch_message(s_mid)
                    try:
                        await s_msg.delete()
                    except Exception:
                        # als delete niet mag, dan in elk geval neutraliseren
                        await s_msg.edit(content="📴 Stemmen gesloten.", view=None)
                except Exception as e:
                    print(f"❌ Fout bij opruimen stemmen-bericht: {e}")
                finally:
                    clear_message_id(channel.id, "stemmen")

            # 3) Terugkoppeling
            if gevonden:
                await interaction.followup.send("✅ De polls zijn verwijderd en afgesloten.", ephemeral=True)
            else:
                await interaction.followup.send("⚠️ Geen polls gevonden om te verwijderen.", ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"❌ Er ging iets mis: {e}", ephemeral=True)

    @app_commands.default_permissions(administrator=True)
    @app_commands.command(
        name="dmk-poll-stemmen",
        description="Stel in of stemmenaantallen zichtbaar zijn of verborgen blijven tot de deadline."
    )
    @app_commands.choices(
        actie=[
            app_commands.Choice(name="Zichtbaar maken", value="zichtbaar"),
            app_commands.Choice(name="Verbergen tot deadline", value="verborgen"),
        ],
        dag=[
            app_commands.Choice(name="Vrijdag", value="vrijdag"),
            app_commands.Choice(name="Zaterdag", value="zaterdag"),
            app_commands.Choice(name="Zondag", value="zondag"),
        ],
    )
    @app_commands.describe(
        tijd="Tijdstip in uu:mm (alleen nodig bij verborgen modus)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def stemmen(
        self,
        interaction: discord.Interaction,
        actie: app_commands.Choice[str],
        dag: app_commands.Choice[str] | None = None,
        tijd: str | None = None,
    ):
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel

        try:

            if dag.value:
                doel_dagen = [dag.value]
            else:
                doel_dagen = ["vrijdag", "zaterdag", "zondag"]

            laatste = None
            for d in doel_dagen:
                if actie.value == "zichtbaar":
                    laatste = set_visibility(channel.id, d, modus="altijd")
                else:
                    laatste = set_visibility(channel.id, d, modus="deadline", tijd=(tijd or "18:00"))
                await update_poll_message(channel, d)

            tijd_txt = laatste["tijd"]
            modus_txt = "altijd zichtbaar" if laatste["modus"] == "altijd" else f"verborgen tot {tijd_txt}"

            if dag.value:
                await interaction.followup.send(
                    f"⚙️ Instelling voor {dag.value} gewijzigd naar: **{modus_txt}**.\n📌 Kijk hierboven bij de pollberichten om het resultaat te zien.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"⚙️ Instellingen voor alle dagen gewijzigd naar: **{modus_txt}**.\n📌 Kijk hierboven bij de pollberichten om het resultaat te zien.",
                    ephemeral=True
                )

        except Exception as e:
            await interaction.followup.send(f"❌ Er ging iets mis: {e}", ephemeral=True)

    @app_commands.default_permissions(administrator=True)
    @app_commands.command(
        name="dmk-poll-archief-download",
        description="(Admin) Download het CSV-archief met weekresultaten."
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def archief_download(self, interaction: discord.Interaction):
        # NIET-ephemeral defer, want we willen de file publiek kunnen sturen
        await interaction.response.defer(ephemeral=False)

        try:
            if not archive_exists():
                # Korte privé melding als er niets is
                await interaction.followup.send("Er is nog geen archief.", ephemeral=True)
                return

            filename, data = open_archive_bytes()
            if not data:
                await interaction.followup.send("Archief kon niet worden gelezen.", ephemeral=True)
                return

            if ArchiveDeleteView is None:
                await interaction.followup.send(
                    content="CSV-archief met weekresultaten.",
                    file=File(io.BytesIO(data), filename=filename),
                )
                return

            view = ArchiveDeleteView()
            await interaction.followup.send(
                "CSV-archief met weekresultaten. Wil je het hierna verwijderen?",
                file=File(io.BytesIO(data), filename=filename),
                view=view
            )
        except Exception as e:
            # Altijd afronden met feedback
            await interaction.followup.send(f"❌ Er ging iets mis: {e}", ephemeral=True)

    @app_commands.default_permissions(administrator=True)
    @app_commands.command(
        name="dmk-poll-archief-verwijderen",
        description="(Admin) Verwijder het volledige archief."
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def archief_verwijderen(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            ok = delete_archive()
            msg = "Archief verwijderd. ✅" if ok else "Er was geen archief om te verwijderen."
            await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Er ging iets mis: {e}", ephemeral=True)
    
    @app_commands.command(
        name="dmk-poll-status",
        description="Toon pauze, zichtbaarheid en alle stemmen per dag (ephemeral embed)."
    )
    async def status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        guild = channel.guild

        try:
            pauze_txt = "Ja" if is_paused(channel.id) else "Nee"
            namen_aan = is_name_display_enabled(channel.id)
            namen_txt = "zichtbaar" if namen_aan else "anoniem"

            embed = discord.Embed(
                title="📊 DMK-poll status",
                description=f"⏸️ Pauze: **{pauze_txt}**\n👤 Namen: **{namen_txt}**",
                color=discord.Color.blurple()
            )

            all_votes = await load_votes()

            for dag in ["vrijdag", "zaterdag", "zondag"]:
                instelling = get_setting(channel.id, dag)
                zicht_txt = "altijd zichtbaar" if instelling.get("modus") == "altijd" else f"deadline {instelling.get('tijd', '18:00')}"

                regels: list[str] = []

                for opt in get_poll_options():
                    if opt.dag != dag:
                        continue

                    # aantal stemmers tellen
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
                    if namen_aan and stemmers:
                        regel += f":  {', '.join(stemmers)}"
                    regels.append(regel)

                value = "\n".join(regels) if regels else "_(geen opties gevonden)_"
                embed.add_field(name=f"{dag.capitalize()} ({zicht_txt})", value=value, inline=False)

            # ➕ View alleen voor beheerders
            view = NaamToggleView() if interaction.user.guild_permissions.administrator else None

            await interaction.followup.send(embed=embed, ephemeral=True, view=view)

        except Exception as e:
            await interaction.followup.send(f"❌ Er ging iets mis: {e}", ephemeral=True)

async def setup(bot):
    c = DMKPoll(bot)
    bot.tree.on_error = c.on_app_command_error
    await bot.add_cog(c)

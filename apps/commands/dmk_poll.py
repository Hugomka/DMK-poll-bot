# apps\commands\dmk_poll.py

import io
import discord
import re

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
from apps.utils.poll_storage import add_guest_votes, get_votes_for_option, load_votes, remove_guest_votes, reset_votes
from apps.utils.message_builder import build_grouped_names_for, build_poll_message_for_day_async
from apps.utils.poll_settings import get_setting, is_name_display_enabled, is_paused, set_visibility, should_hide_counts, toggle_paused
from apps.utils.archive import append_week_snapshot, archive_exists, open_archive_bytes, delete_archive
from apps.utils.poll_settings import toggle_name_display

try:
    from apps.ui.archive_view import ArchiveDeleteView
except Exception:
    ArchiveDeleteView = None

async def is_admin_of_moderator(interaction: discord.Interaction) -> bool:
    perms = interaction.user.guild_permissions
    return perms.administrator or perms.moderate_members

class DMKPoll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, (app_commands.MissingPermissions, app_commands.CheckFailure)):
            await interaction.response.send_message(
                "🚫 Sorry, je bent geen beheerder of moderator. Je kunt deze commando niet gebruiken.",
                ephemeral=True
            )
        else:
            raise error

    @app_commands.default_permissions(administrator=True, moderate_members=True)
    @app_commands.command(name="dmk-poll-on", description="Plaats of update de polls per avond")
    @app_commands.check(is_admin_of_moderator)
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
            
    @app_commands.default_permissions(administrator=True, moderate_members=True)
    @app_commands.command(name="dmk-poll-reset", description="Reset de polls naar een nieuwe week.")
    @app_commands.check(is_admin_of_moderator)
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

    @app_commands.default_permissions(administrator=True, moderate_members=True)
    @app_commands.command(name="dmk-poll-pauze", description="Pauzeer of hervat alle polls")
    @app_commands.check(is_admin_of_moderator)
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

    @app_commands.default_permissions(administrator=True, moderate_members=True)
    @app_commands.command(name="dmk-poll-verwijderen", description="Verwijder alle pollberichten uit het kanaal en uit het systeem.")
    @app_commands.check(is_admin_of_moderator)
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

    @app_commands.default_permissions(administrator=True, moderate_members=True)
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
    @app_commands.check(is_admin_of_moderator)
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

    @app_commands.default_permissions(administrator=True, moderate_members=True)
    @app_commands.command(
        name="dmk-poll-archief-download",
        description="(Admin) Download het CSV-archief met weekresultaten."
    )
    @app_commands.check(is_admin_of_moderator)
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

    @app_commands.default_permissions(administrator=True, moderate_members=True)
    @app_commands.command(
        name="dmk-poll-archief-verwijderen",
        description="(Admin) Verwijder het volledige archief."
    )
    @app_commands.check(is_admin_of_moderator)
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

                    # Bouw groepen: owner_id -> {"voted": bool, "guests": [namen], "mention": "@Owner"}
                    groepen = {}
                    for raw_id, user_votes in all_votes.items():
                        if opt.tijd not in user_votes.get(dag, []):
                            continue

                        try:
                            if "_guest::" in raw_id:
                                owner_id, guest_name = raw_id.split("_guest::", 1)
                                owner_member = guild.get_member(int(owner_id)) or await guild.fetch_member(int(owner_id))
                                key = owner_id
                                g = groepen.setdefault(key, {"voted": False, "guests": [], "mention": owner_member.mention if owner_member else "Gast"})
                                g["guests"].append(guest_name.strip() or "Gast")
                            else:
                                member = guild.get_member(int(raw_id)) or await guild.fetch_member(int(raw_id))
                                if member:
                                    key = raw_id
                                    g = groepen.setdefault(key, {"voted": False, "guests": [], "mention": member.mention})
                                    g["voted"] = True
                        except Exception as ex:
                            print(f"⚠️ status: kon ID '{raw_id}' niet verwerken: {ex}")

                    # totaal = owners die zelf stemmen + alle gasten
                    n = sum(1 for g in groepen.values() if g["voted"]) + sum(len(g["guests"]) for g in groepen.values())

                    def format_groep(g):
                        if g["guests"] and g["voted"]:
                            return f"{g['mention']} ({g['mention']}: {', '.join(g['guests'])})"
                        elif g["guests"]:
                            return f"({g['mention']}: {', '.join(g['guests'])})"
                        else:
                            return f"{g['mention']}"

                    totaal, groepen_txt = await build_grouped_names_for(dag, opt.tijd, guild, all_votes)

                    regel = f"{opt.emoji} {opt.tijd} — **{totaal}** stemmen"
                    if namen_aan and groepen_txt:
                        regel += f":  {groepen_txt}"
                    regels.append(regel)

                value = "\n".join(regels) if regels else "_(geen opties gevonden)_"
                embed.add_field(name=f"{dag.capitalize()} ({zicht_txt})", value=value, inline=False)

            # ➕ View alleen voor beheerders
            view = NaamToggleView(channel.id) if interaction.user.guild_permissions.administrator else None

            await interaction.followup.send(embed=embed, ephemeral=True, view=view)

        except Exception as e:
            await interaction.followup.send(f"❌ Er ging iets mis: {e}", ephemeral=True)

    @app_commands.default_permissions(administrator=False)  # iedereen mag gasten toevoegen
    @app_commands.command(
        name="gast-add",
        description="Voeg gaststemmen toe voor een dag+tijd. Meerdere namen scheiden met , of ;"
    )
    @app_commands.choices(
        slot=[
            app_commands.Choice(name="Vrijdag 19:00",  value="vrijdag|om 19:00 uur"),
            app_commands.Choice(name="Vrijdag 20:30",  value="vrijdag|om 20:30 uur"),
            app_commands.Choice(name="Zaterdag 19:00", value="zaterdag|om 19:00 uur"),
            app_commands.Choice(name="Zaterdag 20:30", value="zaterdag|om 20:30 uur"),
            app_commands.Choice(name="Zondag 19:00",   value="zondag|om 19:00 uur"),
            app_commands.Choice(name="Zondag 20:30",   value="zondag|om 20:30 uur"),
        ],
    )
    @app_commands.describe(namen="Meerdere namen met komma, bv: Mario, Luigi, Peach")
    async def gast_add(
        self,
        interaction: discord.Interaction,
        slot: app_commands.Choice[str],
        namen: str
    ):
        """Voorbeeld: /gast-add slot:'Vrijdag 20:30' namen:'Mario, Luigi, Peach'"""
        await interaction.response.defer(ephemeral=True)

        try:
            dag, tijd = slot.value.split("|", 1)

            # split op komma of puntkomma
            ruwe = [p.strip() for p in re.split(r"[;,]", namen or "") if p.strip()]
            if not ruwe:
                await interaction.followup.send("⚠️ Geen geldige namen opgegeven.", ephemeral=True)
                return

            toegevoegd, overgeslagen = await add_guest_votes(interaction.user.id, dag, tijd, ruwe)

            # Publieke pollbericht voor díe dag even updaten
            await update_poll_message(interaction.channel, dag)

            parts = []
            if toegevoegd:
                parts.append(f"✅ Toegevoegd: {', '.join(toegevoegd)}")
            if overgeslagen:
                parts.append(f"ℹ️ Overgeslagen (bestond al): {', '.join(overgeslagen)}")
            if not parts:
                parts = ["(niets gewijzigd)"]

            await interaction.followup.send(
                f"👥 Gaststemmen voor **{dag} {tijd}**\n" + "\n".join(parts),
                ephemeral=True
            )

        except Exception as e:
            await interaction.followup.send(f"❌ Er ging iets mis: {e}", ephemeral=True)

    @app_commands.command(
        name="gast-remove",
        description="Verwijder gaststemmen voor een dag+tijd. Meerdere namen scheiden met , of ;"
    )
    @app_commands.choices(
        slot=[
            app_commands.Choice(name="Vrijdag 19:00",  value="vrijdag|om 19:00 uur"),
            app_commands.Choice(name="Vrijdag 20:30",  value="vrijdag|om 20:30 uur"),
            app_commands.Choice(name="Zaterdag 19:00", value="zaterdag|om 19:00 uur"),
            app_commands.Choice(name="Zaterdag 20:30", value="zaterdag|om 20:30 uur"),
            app_commands.Choice(name="Zondag 19:00",   value="zondag|om 19:00 uur"),
            app_commands.Choice(name="Zondag 20:30",   value="zondag|om 20:30 uur"),
        ],
    )
    @app_commands.describe(namen="Meerdere namen met komma, bv: Mario, Luigi, Peach")
    async def gast_remove(
        self,
        interaction: discord.Interaction,
        slot: app_commands.Choice[str],
        namen: str
    ):
        """Voorbeeld: /gast-remove slot:'Vrijdag 20:30' namen:'Mario, Luigi'"""
        await interaction.response.defer(ephemeral=True)

        try:
            dag, tijd = slot.value.split("|", 1)
            ruwe = [p.strip() for p in re.split(r"[;,]", namen or "") if p.strip()]
            if not ruwe:
                await interaction.followup.send("⚠️ Geen geldige namen opgegeven.", ephemeral=True)
                return

            verwijderd, nietgevonden = await remove_guest_votes(interaction.user.id, dag, tijd, ruwe)

            # Publieke pollbericht voor díe dag updaten
            await update_poll_message(interaction.channel, dag)

            parts = []
            if verwijderd:
                parts.append(f"✅ Verwijderd: {', '.join(verwijderd)}")
            if nietgevonden:
                parts.append(f"ℹ️ Niet gevonden: {', '.join(nietgevonden)}")
            if not parts:
                parts = ["(niets gewijzigd)"]

            await interaction.followup.send(
                f"👥 Gaststemmen verwijderd voor **{dag} {tijd}**\n" + "\n".join(parts),
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Er ging iets mis: {e}", ephemeral=True)


async def setup(bot):
    c = DMKPoll(bot)
    bot.tree.on_error = c.on_app_command_error
    await bot.add_cog(c)

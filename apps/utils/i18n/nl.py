# apps/utils/i18n/nl.py
"""Dutch translations for DMK-poll-bot (default language)."""

# Day names (internal key -> display name)
DAY_NAMES = {
    "monday": "maandag",
    "tuesday": "dinsdag",
    "wednesday": "woensdag",
    "thursday": "donderdag",
    "friday": "vrijdag",
    "saturday": "zaterdag",
    "sunday": "zondag",
}

# Time labels
TIME_LABELS = {
    "19:00": "om 19:00 uur",
    "20:30": "om 20:30 uur",
    "maybe": "misschien",
    "not_joining": "niet meedoen",
}

# Common words for pluralization
COMMON = {
    "member": "lid",
    "members": "leden",
    "has": "heeft",
    "have": "hebben",
    "person": "persoon",
    "persons": "personen",
    "vote": "stem",
    "votes": "stemmen",
    "for": "voor",
    "and": "en",
    "guest": "gast",
    "at_time": "Om {tijd} uur",
}

# UI text (buttons, status messages, headers)
UI = {
    # Vote button
    "vote_button": "Stemmen",
    "vote_button_paused": "Stemmen (gepauzeerd)",
    "vote_processing": "Je stem wordt verwerkt…",
    "vote_success": "Je stem is verwerkt.",
    "vote_closed": "De stemmogelijkheid is gesloten.",
    "vote_error": "Er ging iets mis, probeer opnieuw.",
    # Headers
    "choose_times_header": "📅 **{dag}** — kies jouw tijden 👇",
    "poll_title": "**DMK-poll voor {dag} ({datum}):**",
    "poll_title_paused": "**- _(Gepauzeerd)_**",
    # Status
    "votes_hidden": "stemmen verborgen",
    "votes_count": "{n} stemmen",
    "vote_count_singular": "{n} stem",
    "no_options": "_(geen opties gevonden)_",
    "everyone_voted": "🎉 Iedereen heeft gestemd!",
    "everyone_voted_thanks": "Fantastisch dat jullie allemaal hebben gestemd! Bedankt!",
    "not_voted_count": "👻 Niet gestemd ({count} personen)",
    "not_voted_singular": "👻 Niet gestemd ({count} persoon)",
    # Paused
    "paused": "Gepauzeerd",
    "paused_message": "Stemmen is tijdelijk gepauzeerd.",
    "voting_paused": "Stemmen is gepauzeerd.",
    # Poll messages
    "poll_updating": "Poll wordt bijgewerkt... een moment geduld.",
    "voting_closed_all_days": "Stemmen is gesloten voor alle dagen. Kom later terug.",
    "choose_times_instruction": "Kies jouw tijden hieronder 👇 per dag (alleen jij ziet dit).",
    "click_vote_button": "Klik op **🗳️ Stemmen** om je keuzes te maken.",
    # Errors
    "error_channel_only": "Deze knop werkt alleen in een serverkanaal.",
    "error_no_channel": "Kan channel ID niet bepalen.",
    "error_generic": "Er ging iets mis: {error}",
    # Settings
    "language_changed": "✅ Taal is gewijzigd naar Nederlands.",
    # Stem nu button (vote now confirmation)
    "vote_now_button": "🗳️ Stem nu",
    "confirm_join_tonight": "💬 Wil je vanavond om **{time}** meedoen?",
    "already_voted_not_joining": "ℹ️ Je hebt al voor **niet meedoen** gestemd.",
    "already_voted_for_time": "ℹ️ Je hebt al voor **{times}** gestemd.",
    "vote_registered_for_time": "✅ Je stem is geregistreerd voor **{time}**!",
    "indicated_not_joining": "ℹ️ Je hebt aangegeven **niet mee te doen**.",
    "yes_button": "✅ Ja",
    "no_button": "❌ Nee",
    # Cleanup confirmation
    "yes_delete_button": "✅ Ja, verwijder",
    "no_keep_button": "❌ Nee, behoud",
    "cancel_button": "Annuleer",
    "deleting_messages": "⏳ Bezig met verwijderen van {count} bericht(en)...",
    "messages_kept_posting": "ℹ️ Oude berichten worden behouden. De polls worden nu geplaatst.",
}

# Notification texts
NOTIFICATIONS = {
    "poll_opened": "De DMK-poll-bot is zojuist aangezet. Veel plezier met de stemmen! 🎮",
    "poll_opened_at": "De DMK-poll-bot is zojuist aangezet om {tijd}. Veel plezier met de stemmen! 🎮",
    "poll_reset": "De poll is zojuist gereset voor het nieuwe weekend. Je kunt weer stemmen. Veel plezier!",
    "poll_closed": "Deze poll is gesloten en gaat pas **{opening_time}** weer open. Dank voor je deelname.",
    # Reminders
    "reminder_day": "📣 DMK-poll – **{dag}**\n{count_text}Als je nog niet gestemd hebt voor **{dag}**, doe dat dan a.u.b. zo snel mogelijk.",
    "reminder_weekend": "📣 DMK-poll – herinnering\n{count_text}Als je nog niet gestemd hebt voor dit weekend, doe dat dan a.u.b. zo snel mogelijk.",
    "not_voted_yet": "nog niet gestemd.",
    # Celebration
    "celebration_title": "🎉 Geweldig! Iedereen heeft gestemd!",
    "celebration_description": "Bedankt voor jullie inzet dit weekend!",
    # Doorgaan
    "event_proceeding": "De DMK-avond van {dag} om {tijd} gaat door! Veel plezier!",
    "event_proceeding_with_count": "Totaal {totaal} deelnemers: {participants}\nDe DMK-avond van {dag} om {tijd} gaat door! Veel plezier!",
    # Maybe reminder
    "maybe_reminder": "Je hebt 'misschien' gestemd voor {dag}. Bevestig a.u.b. je deelname.",
    "maybe_voted": "op :m: **Misschien** gestemd.",
    "maybe_confirm": "Als je op **Misschien** hebt gestemd: wil je vanavond meedoen?\nKlik op **Stem nu** om je stem te bevestigen.",
    # Notification heading
    "notification_heading": ":mega: Notificatie:",
    # Decision lines
    "decision_pending": "⏳ Beslissing komt **om 18:00**.",
    "decision_not_happening": "🚫 **Gaat niet door** (te weinig stemmen).",
    "decision_happening_1900": "🏁 **Vanavond om 19:00 gaat door!** ({count} stemmen)",
    "decision_happening_2030": "🏁 **Vanavond om 20:30 gaat door!** ({count} stemmen)",
}

# Error messages
ERRORS = {
    "no_channel": "Geen kanaal gevonden.",
    "paused": "Stemmen is tijdelijk gepauzeerd.",
    "channel_only": "Deze knop werkt alleen in een serverkanaal.",
    "toggle_notification": "Fout bij togglen notificatie: {error}",
    "toggle_poll_option": "Fout bij togglen poll-optie: {error}",
    "invalid_time": "Tijd moet in HH:mm formaat zijn (bijv. 20:00).",
    "invalid_date": "Datum moet in DD-MM-YYYY formaat zijn (bijv. 31-12-2025).",
    "time_required": "De parameter 'tijd' is verplicht samen met 'dag' of 'datum'.",
    "dag_datum_conflict": "Je kunt niet zowel 'dag' als 'datum' opgeven. Kies één van beide.",
    "time_without_dag_datum": "De parameter 'tijd' kan niet zonder 'dag' of 'datum'.",
    "frequentie_eenmalig_requires_datum": "Frequentie 'eenmalig' vereist een 'datum' parameter.",
    "frequentie_wekelijks_requires_dag": "Frequentie 'wekelijks' vereist een 'dag' parameter.",
    "reset_failed": "Reset mislukt: {error}",
    "generic_error": "Er ging iets mis: {error}",
    "place_error": "Fout bij plaatsen: {error}",
    "delete_error": "Fout bij verwijderen: {error}",
    # Stem nu button errors
    "could_not_determine_day_time": "Fout: kon dag/tijd niet bepalen.",
    "not_voted_yet_day": "Je hebt nog niet gestemd voor deze dag.",
    "generic_try_again": "Er ging iets mis. Probeer het later opnieuw.",
    "vote_processing_error": "Er ging iets mis bij het verwerken van je stem.",
    "delete_messages_failed": "Er ging iets mis bij het verwijderen van berichten.",
    # Archive errors
    "archive_generate_failed": "Kon archief niet genereren.",
}

# Command feedback messages
COMMANDS = {
    # Poll lifecycle
    "polls_enabled": "✅ Polls zijn weer ingeschakeld en geplaatst/bijgewerkt.",
    "polls_scheduled": "⏰ Poll is ingepland voor activatie op {schedule}.",
    "reset_complete": "🔄 De stemmen zijn gereset voor een nieuwe week.",
    "no_day_messages": "⚠️ Geen dag-berichten gevonden om te resetten.",
    "poll_paused": "⏸️ De poll is gepauzeerd.",
    "poll_resumed": "▶️ De poll is hervat.",
    "poll_deleted": "🗑️ Alle poll-berichten zijn verwijderd.",
    # Guest commands
    "guest_added": "👥 Gaststemmen voor **{dag} {tijd}**",
    "guest_skipped": "ℹ️ Overgeslagen (bestond al): {skipped}",
    "guest_removed": "👥 Gaststemmen verwijderd voor **{dag} {tijd}**",
    "no_valid_names": "Geen geldige namen opgegeven.",
    "nothing_changed": "(niets gewijzigd)",
    "guest_added_list": "✅ Toegevoegd: {names}",
    "guest_removed_list": "✅ Verwijderd: {names}",
    "guest_not_found": "ℹ️ Niet gevonden: {names}",
    # Settings
    "setting_changed": "⚙️ Instelling voor {dag} gewijzigd naar: **{mode}**.\n📌 Kijk hierboven bij de pollberichten om het resultaat te zien.",
    "settings_all_changed": "⚙️ Instellingen voor alle dagen gewijzigd naar: **{mode}**.\n📌 Kijk hierboven bij de pollberichten om het resultaat te zien.",
    "poll_not_active_warning": "⚠️ De poll is momenteel niet actief. Wijzigingen worden toegepast bij de volgende activatie.",
}

# Settings UI text
SETTINGS = {
    # Notification settings
    "notification_settings_title": "🔔 Instellingen Notificaties",
    "notification_settings_description": "Schakel automatische notificaties in of uit. Deze instellingen bepalen welke notificaties de bot automatisch verstuurt.",
    "notification_legend": "Legenda",
    "notification_status": "Status",
    "status_active": "🟢 Groen = Actief",
    "status_inactive": "⚪ Grijs = Uitgeschakeld",
    "click_to_toggle": "Klik op een knop om de status te togglen",
    # Poll options settings
    "poll_options_title": "⚙️ Instellingen Poll-opties",
    "poll_options_description": "Activeer of deactiveer de poll-optie voor de huidige poll. Het heeft een direct effect op de huidige kanaal met de poll.",
    "poll_options_warning": "⚠️ **Let op:** Bij activeren van maandag en dinsdag kunnen problemen ontstaan met de gesloten periode (default: maandag 00:00 t/m dinsdag 20:00). Pas deze periode aan via `/dmk-poll-on` zodat leden kunnen stemmen.",
    "times_your_timezone": "Tijden (jouw tijdzone)",
    "status_active_generated": "🟢 Groen = Actief (poll wordt gegenereerd)",
    "status_active_after_reset": "🔵 Blauw = Actief na reset (poll in verleden, geen stemmen)",
    # Notification types
    "notif_poll_opened": "Poll geopend",
    "notif_poll_reset": "Poll gereset",
    "notif_poll_closed": "Poll gesloten",
    "notif_reminders": "Herinnering stemmen",
    "notif_thursday_reminder": "Herinnering weekend",
    "notif_misschien": "Herinnering misschien",
    "notif_doorgaan": "Doorgaan",
    "notif_celebration": "Felicitatie",
}

# Status display
STATUS = {
    "status_title": "📊 DMK-poll status",
    "pause_label": "⏸️ Pauze",
    "yes": "Ja",
    "no": "Nee",
    "activation_field": "🗓️ Geplande activatie",
    "deactivation_field": "🗑️ Geplande deactivatie",
    "no_schedule": "Geen",
    "default_label": "(default)",
    "visibility_always": "altijd zichtbaar",
    "visibility_deadline": "verborgen tot {tijd}",
    "visibility_deadline_show_ghosts": "verborgen tot {tijd} (behalve niet gestemd)",
}

# Archive UI text
ARCHIVE = {
    "standard_delimiter": "Standaard CSV delimiter",
    "dutch_delimiter": "Nederlandse Excel delimiter",
    "select_format": "Selecteer CSV Formaat...",
    "delete_button": "Verwijder archief",
    "confirm_delete": "⚠️ **Weet je zeker dat je het archief permanent wilt verwijderen?**\nDeze actie kan niet ongedaan worden gemaakt.",
    "confirm_delete_button": "Verwijder Archief",
    "deletion_cancelled": "❌ Verwijdering geannuleerd.",
    "deleted": "🗑️ Archief verwijderd.",
    "deleted_no_archive": "❌ **Archief verwijderd**\nEr is momenteel geen archief beschikbaar.",
    "nothing_to_delete": "Er was geen archief om te verwijderen.",
    "no_archive": "Er is nog geen archief voor dit kanaal.",
    "read_failed": "Archief kon niet worden gelezen.",
    "description": "CSV-archief met weekresultaten voor dit kanaal.",
    "archive_message_weekend": "📊 **DMK Poll Archief - Weekend (vrijdag-zondag)**\nJe kunt een **CSV-formaat** tussen NL en US kiezen en download het archiefbestand dat geschikt is voor je spreadsheet.\n\n⚠️ **Let op**:\nOp de 'Verwijder archief'-knop klikken verwijdert je het hele archief permanent.",
    "archive_message_weekday": "📊 **DMK Poll Archief - Weekday (maandag-donderdag)**\nJe kunt een **CSV-formaat** tussen NL en US kiezen en download het archiefbestand dat geschikt is voor je spreadsheet.\n\n⚠️ **Let op**:\nOp de 'Verwijder archief'-knop klikken verwijdert je het hele archief permanent.",
}

# Opening message parts
OPENING = {
    "header": "@everyone\n# 🎮 **Welkom bij de DMK-poll!**\n\n",
    "intro": "Elke week organiseren we DMK-avonden op {dagen}. Stem hieronder op de avonden waarop jij mee wilt doen! De stemmen blijven verborgen tot de deadline van {deadline} uur.",
    "reminder_note": "Als je nog niet gestemd hebt, krijg je 2 uur voor de deadline een herinnering.",
    "maybe_note": "Heb je op 'misschien' gestemd? Dan krijg je 1 uur voor de deadline een herinnering om je stem te bevestigen. Als je dan nog niet stemt, wordt je stem automatisch omgezet naar 'niet meedoen'.",
    "notification_cta": "Dus wees op tijd als je graag mee wilt doen, en zet de meldingen voor dit kanaal aan.",
    "vote_info": "ℹ️ **Stem alsjeblieft op elke dag, ook als je denkt niet mee te doen. Zo blijft het overzicht duidelijk.**",
    "how_it_works": "📅 **Hoe werkt het?**",
    "how_click": "Klik op **🗳️ Stemmen** om je keuzes aan te geven",
    "how_multiple": "Je kunt meerdere tijden kiezen",
    "how_change": "Je kunt je stem altijd aanpassen",
    "guests_title": "👥 **Gasten meebrengen?**",
    "guests_instruction": "Gebruik `/gast-add` om gasten toe te voegen aan je stem.",
    "have_fun": "Veel plezier! 🎉",
    "fallback": "Klik op **🗳️ Stemmen** om je keuzes aan te geven.\n\nVeel plezier! 🎉",
}

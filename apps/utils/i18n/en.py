# apps/utils/i18n/en.py
"""English translations for DMK-poll-bot."""

# Day names (internal key -> display name)
DAY_NAMES = {
    "monday": "Monday",
    "tuesday": "Tuesday",
    "wednesday": "Wednesday",
    "thursday": "Thursday",
    "friday": "Friday",
    "saturday": "Saturday",
    "sunday": "Sunday",
}

# Time labels
TIME_LABELS = {
    "19:00": "at 7:00 PM",
    "20:30": "at 8:30 PM",
    "maybe": "maybe",
    "not_joining": "not joining",
}

# Common words for pluralization
COMMON = {
    "member": "member",
    "members": "members",
    "has": "has",
    "have": "have",
    "person": "person",
    "persons": "people",
    "vote": "vote",
    "votes": "votes",
    "for": "for",
    "and": "and",
    "guest": "guest",
    "at_time": "At {tijd}",
}

# UI text (buttons, status messages, headers)
UI = {
    # Vote button
    "vote_button": "Vote",
    "vote_button_paused": "Vote (paused)",
    "vote_processing": "Your vote is being processed…",
    "vote_success": "Your vote has been processed.",
    "vote_closed": "Voting is closed.",
    "vote_error": "Something went wrong, please try again.",
    # Headers
    "choose_times_header": "📅 **{dag}** — choose your times 👇",
    "poll_title": "**DMK poll for {dag} ({datum}):**",
    "poll_title_paused": "**- _(Paused)_**",
    # Status
    "votes_hidden": "votes hidden",
    "votes_count": "{n} votes",
    "vote_count_singular": "{n} vote",
    "no_options": "_(no options found)_",
    "everyone_voted": "🎉 Everyone has voted!",
    "everyone_voted_thanks": "Amazing that everyone voted! Thank you!",
    "not_voted_count": "👻 Not voted ({count} people)",
    "not_voted_singular": "👻 Not voted ({count} person)",
    # Paused
    "paused": "Paused",
    "paused_message": "Voting is temporarily paused.",
    "voting_paused": "Voting is paused.",
    # Poll messages
    "poll_updating": "Poll is being updated... please wait.",
    "voting_closed_all_days": "Voting is closed for all days. Come back later.",
    "choose_times_instruction": "Choose your times below 👇 per day (only you can see this).",
    "click_vote_button": "Click **🗳️ Vote** to make your choices.",
    # Errors
    "error_channel_only": "This button only works in a server channel.",
    "error_no_channel": "Cannot determine channel ID.",
    "error_generic": "Something went wrong: {error}",
    # Settings
    "language_changed": "✅ Language has been changed to English.",
    # Stem nu button (vote now confirmation)
    "vote_now_button": "🗳️ Vote now",
    "confirm_join_tonight": "💬 Do you want to join tonight at **{time}**?",
    "already_voted_not_joining": "ℹ️ You already voted for **not joining**.",
    "already_voted_for_time": "ℹ️ You already voted for **{times}**.",
    "vote_registered_for_time": "✅ Your vote is registered for **{time}**!",
    "indicated_not_joining": "ℹ️ You indicated **not joining**.",
    "yes_button": "✅ Yes",
    "no_button": "❌ No",
    # Cleanup confirmation
    "yes_delete_button": "✅ Yes, delete",
    "no_keep_button": "❌ No, keep",
    "cancel_button": "Cancel",
    "deleting_messages": "⏳ Deleting {count} message(s)...",
    "messages_kept_posting": "ℹ️ Old messages will be kept. The polls are now being posted.",
}

# Notification texts
NOTIFICATIONS = {
    "poll_opened": "The DMK poll bot has just been activated. Have fun voting! 🎮",
    "poll_opened_at": "The DMK poll bot has just been activated at {tijd}. Have fun voting! 🎮",
    "poll_reset": "The poll has been reset for the new weekend. You can vote again. Have fun!",
    "poll_closed": "This poll is closed and will reopen at **{opening_time}**. Thanks for participating.",
    # Reminders
    "reminder_day": "📣 DMK poll – **{dag}**\n{count_text}If you haven't voted for **{dag}** yet, please do so as soon as possible.",
    "reminder_weekend": "📣 DMK poll – reminder\n{count_text}If you haven't voted for this weekend yet, please do so as soon as possible.",
    "not_voted_yet": "not voted yet.",
    # Celebration
    "celebration_title": "🎉 Amazing! Everyone has voted!",
    "celebration_description": "Thank you for your dedication this weekend!",
    # Doorgaan (event proceeding)
    "event_proceeding": "The DMK evening on {dag} at {tijd} is happening! Have fun!",
    "event_proceeding_with_count": "Total {totaal} participants: {participants}\nThe DMK evening on {dag} at {tijd} is happening! Have fun!",
    # Maybe reminder
    "maybe_reminder": "You voted 'maybe' for {dag}. Please confirm your participation.",
    "maybe_voted": "voted :m: **Maybe**.",
    "maybe_confirm": "If you voted **Maybe**: do you want to join tonight?\nClick **Vote now** to confirm your participation.",
}

# Error messages
ERRORS = {
    "no_channel": "No channel found.",
    "paused": "Voting is temporarily paused.",
    "channel_only": "This button only works in a server channel.",
    "toggle_notification": "Error toggling notification: {error}",
    "toggle_poll_option": "Error toggling poll option: {error}",
    "invalid_time": "Time must be in HH:mm format (e.g., 20:00).",
    "invalid_date": "Date must be in DD-MM-YYYY format (e.g., 31-12-2025).",
    "time_required": "The 'time' parameter is required with 'day' or 'date'.",
    "dag_datum_conflict": "You cannot specify both 'day' and 'date'. Choose one.",
    "time_without_dag_datum": "The 'time' parameter requires 'day' or 'date'.",
    "frequentie_eenmalig_requires_datum": "Frequency 'one-time' requires a 'date' parameter.",
    "frequentie_wekelijks_requires_dag": "Frequency 'weekly' requires a 'day' parameter.",
    "reset_failed": "Reset failed: {error}",
    "generic_error": "Something went wrong: {error}",
    "place_error": "Error placing polls: {error}",
    "delete_error": "Error deleting: {error}",
    # Stem nu button errors
    "could_not_determine_day_time": "Error: could not determine day/time.",
    "not_voted_yet_day": "You haven't voted for this day yet.",
    "generic_try_again": "Something went wrong. Please try again later.",
    "vote_processing_error": "Something went wrong processing your vote.",
    "delete_messages_failed": "Something went wrong deleting messages.",
    # Archive errors
    "archive_generate_failed": "Could not generate archive.",
}

# Command feedback messages
COMMANDS = {
    # Poll lifecycle
    "polls_enabled": "✅ Polls have been enabled and posted/updated.",
    "polls_scheduled": "⏰ Poll is scheduled for activation at {schedule}.",
    "reset_complete": "🔄 Votes have been reset for a new week.",
    "no_day_messages": "⚠️ No day messages found to reset.",
    "poll_paused": "⏸️ The poll has been paused.",
    "poll_resumed": "▶️ The poll has been resumed.",
    "poll_deleted": "🗑️ All poll messages have been deleted.",
    # Guest commands
    "guest_added": "👥 Guest votes for **{dag} {tijd}**",
    "guest_skipped": "ℹ️ Skipped (already exists): {skipped}",
    "guest_removed": "👥 Guest votes removed for **{dag} {tijd}**",
    "no_valid_names": "No valid names provided.",
    "nothing_changed": "(nothing changed)",
    "guest_added_list": "✅ Added: {names}",
    "guest_removed_list": "✅ Removed: {names}",
    "guest_not_found": "ℹ️ Not found: {names}",
    # Settings
    "setting_changed": "⚙️ Setting for {dag} changed to: **{mode}**.\n📌 Check the poll messages above to see the result.",
    "settings_all_changed": "⚙️ Settings for all days changed to: **{mode}**.\n📌 Check the poll messages above to see the result.",
    "poll_not_active_warning": "⚠️ The poll is currently not active. Changes will be applied at the next activation.",
}

# Settings UI text
SETTINGS = {
    # Notification settings
    "notification_settings_title": "🔔 Notification Settings",
    "notification_settings_description": "Enable or disable automatic notifications. These settings determine which notifications the bot sends automatically.",
    "notification_legend": "Legend",
    "notification_status": "Status",
    "status_active": "🟢 Green = Active",
    "status_inactive": "⚪ Grey = Disabled",
    "click_to_toggle": "Click a button to toggle the status",
    # Poll options settings
    "poll_options_title": "⚙️ Poll Options Settings",
    "poll_options_description": "Activate or deactivate the poll option for the current poll. This has a direct effect on the current channel with the poll.",
    "poll_options_warning": "⚠️ **Note:** When activating Monday and Tuesday, issues may occur with the closed period (default: Monday 00:00 to Tuesday 20:00). Adjust this period via `/dmk-poll-on` so members can vote.",
    "times_your_timezone": "Times (your timezone)",
    "status_active_generated": "🟢 Green = Active (poll is generated)",
    "status_active_after_reset": "🔵 Blue = Active after reset (poll in past, no votes)",
    # Notification types
    "notif_poll_opened": "Poll opened",
    "notif_poll_reset": "Poll reset",
    "notif_poll_closed": "Poll closed",
    "notif_reminders": "Voting reminder",
    "notif_thursday_reminder": "Weekend reminder",
    "notif_misschien": "Maybe reminder",
    "notif_doorgaan": "Proceeding",
    "notif_celebration": "Celebration",
}

# Status display
STATUS = {
    "status_title": "📊 DMK poll status",
    "pause_label": "⏸️ Pause",
    "yes": "Yes",
    "no": "No",
    "activation_field": "🗓️ Scheduled activation",
    "deactivation_field": "🗑️ Scheduled deactivation",
    "no_schedule": "None",
    "default_label": "(default)",
    "visibility_always": "always visible",
    "visibility_deadline": "deadline {tijd}",
    "visibility_deadline_show_ghosts": "hidden until {tijd} (except not voted)",
}

# Archive UI text
ARCHIVE = {
    "standard_delimiter": "Standard CSV delimiter",
    "dutch_delimiter": "Dutch Excel delimiter",
    "select_format": "Select CSV Format...",
    "delete_button": "Delete archive",
    "confirm_delete": "⚠️ **Are you sure you want to permanently delete the archive?**\nThis action cannot be undone.",
    "confirm_delete_button": "Delete Archive",
    "deletion_cancelled": "❌ Deletion cancelled.",
    "deleted": "🗑️ Archive deleted.",
    "deleted_no_archive": "❌ **Archive deleted**\nNo archive currently available.",
    "nothing_to_delete": "There was no archive to delete.",
    "no_archive": "There is no archive for this channel yet.",
    "read_failed": "Archive could not be read.",
    "description": "CSV archive with weekly results for this channel.",
    "archive_message_weekend": "📊 **DMK Poll Archive - Weekend (Friday-Sunday)**\nYou can choose a **CSV format** between NL and US and download the archive file suitable for your spreadsheet.\n\n⚠️ **Note**:\nClicking 'Delete archive' will permanently delete the entire archive.",
    "archive_message_weekday": "📊 **DMK Poll Archive - Weekday (Monday-Thursday)**\nYou can choose a **CSV format** between NL and US and download the archive file suitable for your spreadsheet.\n\n⚠️ **Note**:\nClicking 'Delete archive' will permanently delete the entire archive.",
}

# Opening message parts
OPENING = {
    "header": "@everyone\n# 🎮 **Welcome to the DMK poll!**\n\n",
    "intro": "Every week we organize DMK evenings on {dagen}. Vote below on the evenings you want to join! Votes remain hidden until the deadline of {deadline}.",
    "reminder_note": "If you haven't voted yet, you'll get a reminder 2 hours before the deadline.",
    "maybe_note": "Did you vote 'maybe'? You'll get a reminder 1 hour before the deadline to confirm your participation. If you don't vote by then, your vote will automatically be changed to 'not joining'.",
    "notification_cta": "So be on time if you want to join, and enable notifications for this channel.",
    "vote_info": "ℹ️ **Please vote on every day, even if you think you won't join. This keeps the overview clear.**",
    "how_it_works": "📅 **How does it work?**",
    "how_click": "Click **🗳️ Vote** to make your choices",
    "how_multiple": "You can choose multiple times",
    "how_change": "You can always change your vote",
    "guests_title": "👥 **Bringing guests?**",
    "guests_instruction": "Use `/gast-add` to add guests to your vote.",
    "have_fun": "Have fun! 🎉",
    "fallback": "Click **🗳️ Vote** to make your choices.\n\nHave fun! 🎉",
}

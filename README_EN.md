[🇳🇱 Nederlands](README.md) | **🇺🇸 English**

# DMK-poll-bot 🇺🇸

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B%20%7C%203.13-blue.svg)
![discord.py 2.3.2](https://img.shields.io/badge/discord.py-2.3.2-blueviolet.svg)
![License](https://img.shields.io/github/license/Hugomka/DMK-poll-bot)
![Last Commit](https://img.shields.io/github/last-commit/Hugomka/DMK-poll-bot)
![Issues](https://img.shields.io/github/issues/Hugomka/DMK-poll-bot)
![Stars](https://img.shields.io/github/stars/Hugomka/DMK-poll-bot?style=social)
[![Coverage](https://img.shields.io/codecov/c/github/Hugomka/DMK-poll-bot?label=Coverage)](https://codecov.io/gh/Hugomka/DMK-poll-bot)

**DMK-poll-bot** is a smart, fully automatic Discord bot for planning weekends for **Deaf Mario Kart (DMK)**.
This bot was specially made for the DMK community, making organizing game nights smooth and fair.
No more puzzling with reactions: the bot handles the poll, collects votes, and clearly communicates the outcome.

---

## 🔰 Introduction

DMK-poll-bot helps the **DMK club** plan races on weekends. Every week the bot starts a new poll for **Friday**, **Saturday**, and **Sunday**.
Members vote with buttons, votes remain hidden until the deadline, and the bot automatically decides if there's enough interest.
There's also support for **guest votes** and a **CSV archive** of results. In short: an accessible, user-friendly poll that fits our Discord community.

**Why this bot?**
Previously we did this with manual polls or reactions. That was unclear and time-consuming.
With DMK-poll-bot this goes **automatically** and **fairly** – everyone can vote with one click, results come exactly on time, and the decision follows fixed DMK rules.

---

## 📦 Features

| Feature | Description |
|---|---|
| **🗳️ Voting per day** | For Monday through Sunday each their own poll with options (default: only weekend active). |
| **✅ Customizable poll options** | Times/options via `poll_options.json` and `/dmk-poll-instelling` (default: 7:00 PM, 8:30 PM for Friday/Saturday/Sunday). |
| **🔒 Safe storage** | Votes in `votes.json` with async lock, keeping everything stable and fast. |
| **⏰ Automatic scheduler** | New week on Tuesday 8:00 PM, day updates at 6:00 PM, reminders at 4:00 PM, notifications when event proceeds. |
| **📅 Poll scheduling** | Schedule polls to automatically activate/deactivate at specific times (configurable per channel). |
| **🏁 Automatic decision** | On the day itself after the deadline: ≥6 votes needed; in case of tie **8:30 PM** wins. |
| **📢 Smart notifications** | Reminders for non-voters (4:00 PM), early Thursday reminder (8:00 PM), Maybe confirmation (5:00 PM), and mentions for proceeding messages. |
| **👁️ Hidden votes** | Until the deadline (default 6:00 PM) counts remain hidden in the channel messages. |
| **🎟️ Guest votes** | Members can add/remove votes **for guests**. |
| **💬 Slash commands** | `/dmk-poll-on/reset/pauze/verwijderen/instelling/stemmen/status/notify`, archive download/delete, and guest commands. |
| **⚙️ Configurable settings** | Via `/dmk-poll-instelling`: toggle poll options (14 day/time combinations: Monday through Sunday, 7:00 PM and 8:30 PM) and notifications (8 types on/off per channel). |
| **📊 Live status** | `/dmk-poll-status` shows per day the counts, optionally names, and scheduling information. |
| **🔄 Maybe conversion** | Those who voted "maybe" at 5:00 PM get a confirmation button; at 6:00 PM remaining "maybe" votes are automatically converted to "not joining". |
| **🔔 Privacy-friendly mentions** | Temporary mentions (5 sec visible for reminders), persistent mentions (5 hours visible for "proceeding" messages). |
| **🌍 Multilingual support** | Full i18n support for Dutch (🇳🇱) and English (🇺🇸). Language configurable per channel via `/dmk-poll-taal`. |
| **📂 Category-based polls** | Channels in the same Discord category share votes. Ideal for multilingual communities with separate language channels. |

---

## 🌍 Multilingual Support & Category Polls

The bot supports **fully multilingual** polls with **shared votes** between channels in the same category.

### How does it work?

1. **Language per channel**: Each channel can have its own language (Dutch or English)
2. **Shared votes**: Channels in the same Discord category automatically share votes
3. **Synchronized settings**: Poll options, notifications, and period settings are synchronized

### Example setup

```
📁 DMK Category
├── #dmk-poll-nl (Dutch)
└── #dmk-poll-en (English)
```

- Votes in `#dmk-poll-nl` are automatically visible in `#dmk-poll-en` (and vice versa)
- Each channel shows the interface in its own language
- Vote settings are synchronized between both channels

### Setting language

Use `/dmk-poll-taal` to change the language of a channel:

| Option | Description |
|--------|-------------|
| 🇳🇱 Nederlands | Dutch interface and notifications |
| 🇺🇸 English | English interface and notifications |

### What gets translated?

- Poll messages and titles
- Vote buttons and time labels
- Notifications and reminders
- Decision messages ("Gaat door!" / "Is happening!")
- Settings UI and error messages

### Synchronized settings

These settings are automatically synchronized between channels in the same category:

| Setting | Description |
|---------|-------------|
| `__poll_options__` | Which day/time combinations are active |
| `__period_settings__` | Open/close times for periods |
| `__reminder_time__` | Minutes before deadline for reminders |
| `__notification_states__` | Which notifications are on/off |
| `__paused__` | Whether the poll is paused |

**Note:** The language setting (`__language__`) is **not** synchronized - this is intentionally different per channel.

---

## 💬 Command Overview

DMK-poll-bot works with **Slash commands** (type `/` in Discord).

| Command | Description |
|---|---|
| **`/dmk-poll-on`** *(default: admin/mod)* | Places or refreshes the 3 day messages, an opening message with `@everyone`, the **🗳️ Vote** button, and a notification message in the current channel. Also supports scheduling parameters for automatic activation. |
| **`/dmk-poll-reset`** *(default: admin/mod)* | Archive (CSV) + **clear all votes** → ready for new week. |
| **`/dmk-poll-pauze`** *(default: admin/mod)* | Pause/resume voting. When paused, the Vote button is disabled. |
| **`/dmk-poll-off`** *(default: admin/mod)* | Close the poll TEMPORARILY: remove all messages but keep automation active. The poll will automatically reopen at the configured time. |
| **`/dmk-poll-stopzetten`** *(default: admin/mod)* | Stop the poll PERMANENTLY: remove all messages and disable automation. The bot must be manually started again with **/dmk-poll-on**. |
| **`/dmk-poll-instelling`** *(default: admin/mod)* | Open settings for the poll. Choose between **Poll options** (toggle 14 day/time combinations: Monday through Sunday, each 7:00 PM and 8:30 PM; default only weekend active) or **Notifications** (toggle 8 automatic notifications: poll opened/reset/closed, reminders, proceeding, celebration). Interactive UI with green/gray buttons per channel. ⚠️ Note: when activating Monday/Tuesday, adjust the closed period via `/dmk-poll-on`. |
| **`/dmk-poll-stemmen`** *(default: admin/mod)* | Setting per day or all days: **always visible** or **hidden until** `HH:mm` (default 6:00 PM). |
| **`/dmk-poll-archief`** *(default: admin/mod)* | View and manage the CSV archive: choose CSV format (🇺🇸 Comma / 🇳🇱 Semicolon), download directly, or delete archive. |
| **`/dmk-poll-status`** *(default: admin/mod)* | Ephemeral embed: pause/names status and per day the counts with names. |
| **`/dmk-poll-notify`** *(default: admin/mod)* | Send a notification manually. Choose from 7 standard notifications or use custom text. Extra option: `ping` to choose between @everyone, @here (only online users), or no ping (silent notification). |
| **`/dmk-poll-taal`** *(default: admin/mod)* | Change the channel's language. Choose between 🇳🇱 Nederlands and 🇺🇸 English. |
| **`/guest-add`** | Add guest votes: `/guest-add slot:"Saturday 8:30 PM" names:"Mario, Luigi"` |
| **`/guest-remove`** | Remove guest votes: `/guest-remove slot:"Saturday 8:30 PM" names:"Mario"` |

**Note:** Most admin commands give **ephemeral** feedback (only visible to you), keeping the channel clean.

---

## 🔐 Setting Permissions per Server

The defaults are set in the bot (some commands *(default: admin/mod)*, others for everyone).
Admins and moderators can **customize** this per server via Discord:

1. Go to **Server Settings → Integrations → [your bot] → Commands**.
2. Choose a command (e.g., `/dmk-poll-on`).
3. Set **Roles and Members**: which role(s) or persons may use it.
4. Optional: restrict per **channel**.
5. Done! This overrides the defaults. You don't need to modify the bot code.

---

## 👥 Voting with Guests

- **Add guest:**
  Example:
```
/guest-add slot:"Saturday 7:00 PM (Zaterdag 19:00)" names:"Pauline, King Boo"
```

You can separate multiple names with commas or `;`. The bot reports which guests were added and which already existed.

- **Remove guest:**
Example:
```
/guest-remove slot:"Saturday 7:00 PM (Zaterdag 19:00)" names:"King Boo"
```
The bot reports which names were removed or not found.

**How does this count?** Each guest counts as an **extra vote** at that time, linked to your account. In the public poll you only see counts. In `/dmk-poll-status` votes are grouped per owner, e.g.:
`@Mario (@Mario: Luigi, Peach), @Toad`

---

## ⚙️ Poll Options (config)

The vote options are in **`poll_options.json`**. Default:

```json
[
  { "dag": "maandag",  "tijd": "om 19:00 uur", "emoji": "🟥" },
  { "dag": "maandag",  "tijd": "om 20:30 uur", "emoji": "🟧" },
  { "dag": "maandag",  "tijd": "misschien",    "emoji": "Ⓜ️" },
  { "dag": "maandag",  "tijd": "niet meedoen", "emoji": "❌" },
  // ... dinsdag (🟨⬜), woensdag (🟩🟦), donderdag (🟪🟫) ...
  { "dag": "vrijdag",  "tijd": "om 19:00 uur", "emoji": "🔴" },
  { "dag": "vrijdag",  "tijd": "om 20:30 uur", "emoji": "🟠" },
  { "dag": "vrijdag",  "tijd": "misschien",    "emoji": "Ⓜ️" },
  { "dag": "vrijdag",  "tijd": "niet meedoen", "emoji": "❌" },
  // ... zaterdag (🟡⚪), zondag (🟢🔵) ...
]
```

* Feel free to adjust times/emojis.
* Keep the structure (`dag`, `tijd`, `emoji`).
* Restart the bot after changes so new polls use the adjustment.
* If the JSON is missing or broken, we fall back to these defaults.

---

## ⚙️ Installation

> Required: **Python 3.10+** and a **Discord Bot Token**.

1. **Clone code**
```bash
git clone https://github.com/Hugomka/DMK-poll-bot.git
cd DMK-poll-bot
```

2. **Virtual environment**
- Linux/macOS:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```
- Windows PowerShell:
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  ```

3. **Dependencies**
- Minimal runtime:
  ```bash
  pip install -r requirements.txt
  ```
- Development (incl. tests/lint/coverage):
  ```bash
  pip install -r dev-requirements.txt
  ```
  > Tip Windows: if `pip` doesn't work, use `python -m pip install -r dev-requirements.txt`.

4. **Create .env**
```env
DISCORD_TOKEN=your_bot_token_here
```

5. **Start bot (test)**
```bash
python main.py
```

---

6. **Run as service (systemd, Linux)**
   Create `/etc/systemd/system/dmk-bot.service`:

```ini
[Unit]
Description=DMK Discord Poll Bot
After=network.target

[Service]
Type=simple
User=<your-username>
WorkingDirectory=/path/to/DMK-poll-bot
ExecStart=/path/to/DMK-poll-bot/venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Activate:

```bash
sudo systemctl daemon-reload
sudo systemctl enable dmk-bot
sudo systemctl start dmk-bot
# logs
journalctl -u dmk-bot -f
```

**Tip:** Make sure the bot has proper permissions (application commands, read/write messages).

---

## 🚀 Deployment

### First deployment (new server)

The bot automatically creates all runtime files on first start:

```bash
# Clone repository
git clone https://github.com/Hugomka/DMK-poll-bot.git
cd DMK-poll-bot

# Setup (see installation instructions above)
python -m venv .venv
source .venv/bin/activate  # or .\.venv\Scripts\Activate.ps1 on Windows
pip install -r requirements.txt

# Create .env with DISCORD_TOKEN
echo "DISCORD_TOKEN=your_token_here" > .env

# Start the bot (automatically creates tenor-links.json and other runtime files)
python main.py
```

### Update deployment (existing server)

During updates, runtime files are **not** overwritten:

```bash
# Pull updates
git pull origin main

# Restart the bot
# (runtime files remain preserved with their current data)
```

### Automatic Tenor GIF Sync

The bot automatically synchronizes `tenor-links.template.json` to `tenor-links.json`:
- **When**: Every Monday at 00:00 (poll closing time)
- **What**: New GIFs are added with count: 0, removed GIFs are deleted
- **Preservation**: Existing GIF counts are preserved
- **Efficiency**: Sync is only performed when there are actually new or removed GIFs (not on count changes only)

**Updating GIF list:**
1. Edit `tenor-links.template.json` on your development machine
2. Commit and push the changes
3. Deploy to production with `git pull`
4. The bot will automatically sync on Monday 00:00 (or on restart via catch-up mechanism)

---

## 🔧 Technical Details

### Directory structure

```
DMK-poll-bot/
├── apps/
│   ├── commands/           # Slash commands (modularized)
│   │   ├── __init__.py             # Command utilities and helpers
│   │   ├── dmk_poll.py             # Main entry point for all commands
│   │   ├── poll_lifecycle.py       # Lifecycle commands (on/reset/pauze/off/stopzetten)
│   │   ├── poll_config.py          # Poll configuration command (instelling)
│   │   ├── poll_votes.py           # Vote visibility commands
│   │   ├── poll_guests.py          # Guest commands (add/remove)
│   │   ├── poll_archive.py         # Archive commands (download/delete)
│   │   └── poll_status.py          # Status command and notify
│   ├── ui/                 # Discord UI components
│   │   ├── poll_buttons.py           # Poll vote buttons and views
│   │   ├── stem_nu_button.py         # "Vote Now" button for Maybe confirmation
│   │   ├── poll_options_settings.py  # Poll options settings view (day/time toggles)
│   │   ├── notification_settings.py  # Notification settings view (8 notification toggles)
│   │   ├── archive_view.py           # Archive download view with delete button
│   │   └── cleanup_confirmation.py   # Cleanup confirmation view for old messages
│   ├── utils/              # Helper functions
│   │   ├── poll_storage.py        # Vote storage (votes.json)
│   │   ├── poll_settings.py       # Poll settings (pause, visibility, scheduling)
│   │   ├── poll_message.py        # Message ID storage and updates
│   │   ├── message_builder.py     # Poll message construction
│   │   ├── archive.py              # CSV archive management
│   │   ├── mention_utils.py       # Temporary/persistent mentions with cleanup
│   │   ├── discord_client.py      # Discord API helpers
│   │   ├── i18n/                   # Internationalization (Dutch/English translations)
│   │   └── logger.py               # Logging utilities
│   ├── logic/              # Business logic
│   │   ├── decision.py             # Decision rules (who wins?)
│   │   └── visibility.py           # Visibility logic (hide/show)
│   ├── entities/           # Data models
│   │   └── poll_option.py          # Poll option dataclass
│   ├── data/               # Data templates (default data files for new channels)
│   │   ├── poll_message.json       # Template for message IDs
│   │   └── votes.json              # Template for vote storage
│   └── scheduler.py        # APScheduler tasks (reset, reminders, notifications, scheduling)
├── tests/                  # Unit tests with high coverage
│   └── ...
├── main.py                 # Bot entry point
├── poll_options.json       # Config of vote options
├── opening_message.txt     # Customizable opening text for polls
├── requirements.txt        # Runtime dependencies
└── dev-requirements.txt    # Development dependencies (pytest, coverage, linting)
```

### Important data files

| File/directory            | Runtime Data | Purpose                                                                          |
| ------------------------- | :----------: | -------------------------------------------------------------------------------- |
| `poll_options.json`       | ❌ | Config of options (times/emojis) per day.                                        |
| `votes.json`              | ✅ | All votes (per user/guest per day). Async lock for safe I/O.                     |
| `poll_settings.json`      | ✅ | Channel settings: pause, visibility (always/deadline), show names, scheduling (activation/deactivation times), poll options (which days/times enabled), notification preferences (8 toggles per channel), language. |
| `poll_message.json`       | ✅ | Storage of message IDs of the channel polls (for updating/deleting).             |
| `archive/`                | ✅ | Weekly CSV archives for weekend and weekday polls per guild and channel.         |
| `opening_message.txt`     | ❌ | Customizable opening message shown above the polls.                              |
| `tenor-links.json`        | ✅ | Celebration GIF URLs with usage counts (automatically synchronized).             |
| `tenor-links.template.json` | ❌ | Template for GIF list (source of truth, IS committed).                         |
| `resources/`              | ❌ | Local images for fallback (thanks-puppies-kitties.jpg).                          |
| `.scheduler_state.json`   | ✅ | State of the scheduler (last execution of jobs).                                 |
| `.scheduler.lock`         | ✅ | File lock for scheduler state to prevent race conditions.                        |

**Runtime data files** (✅) are automatically created and updated by the bot. These are in `.gitignore` and are **not** committed to git.

### Archive

When resetting for a new week, the bot adds 1 line to **both** archives with: ISO week number (e.g., 2025-W44), date per day, and per day the counts for 7:00 PM, 8:30 PM, maybe, was maybe (💤), not joining, and not voted (👻).

**Two separate archives:**
- **Weekend archive** (`_weekend.csv`): Friday, Saturday, Sunday
- **Weekday archive** (`_weekdays.csv`): Monday, Tuesday, Wednesday, Thursday

Download and delete with archive commands. Archive is **per guild and per channel** stored in `archive/dmk_archive_{guild_id}_{channel_id}_{type}.csv`.

### Decision Rules

* Decision only on the **day itself** after the **deadline** (default 6:00 PM).
* **Minimum 6 votes** needed (configurable via `MIN_NOTIFY_VOTES`).
* **Equal votes? → 8:30 PM wins.**
* Otherwise the time slot with the most votes wins.
* Too few votes? → "Not happening."

### Timezone

All times are in **Europe/Amsterdam** (CET/CEST).

---

## ⏰ Automation (scheduler)

The bot uses APScheduler for automatic tasks:

| Time | Day | Task | Description |
|---|---|---|---|
| **00:00** | Monday | Tenor GIF sync | Sync tenor-links.template.json to tenor-links.json (only on changes) |
| **20:00** | Tuesday | Reset polls | Clear votes, archive, send general reset notification |
| **16:00** | Friday, Saturday, Sunday | Non-voter reminder | Send mention to members who haven't voted for that day (temporary, 5 sec) |
| **17:00** | Friday, Saturday, Sunday | Maybe confirmation | Send "Vote Now" button to Maybe voters with leading time |
| **18:00** | Daily | Poll update | Show counts, add decision rule under the poll |
| **18:00** | Friday, Saturday, Sunday | Maybe conversion | Convert remaining "maybe" votes to "not joining" |
| **18:05** | Friday, Saturday, Sunday | Proceeding notification | Mentions of voters on winning time (≥6), persistent mentions (5 hours) |
| **20:00** | Thursday | Early reminder | Mention to members who haven't voted at all (temporary, 5 sec) |
| **Every minute** | Continuous | Scheduled poll activation | Activate scheduled polls based on activation time |
| **Every minute** | Continuous | Scheduled poll deactivation | Deactivate scheduled polls based on deactivation time |

### Notification System

The bot has a smart notification system with privacy in mind:

1. **Temporary mentions** (5 seconds visible):
   - Reminders for non-voters (4:00 PM Friday/Saturday/Sunday)
   - Early reminders (8:00 PM Thursday)
   - Reset notifications (@everyone)
   - Users do get a notification on their device, but the mention disappears quickly from the channel
   - After 1 hour the entire message is automatically deleted

2. **Persistent mentions** (5 hours visible):
   - "Proceeding" messages for participants (6:05 PM Friday/Saturday/Sunday)
   - Remain visible for 5 hours, then the entire message is automatically deleted
   - This ensures participants can see who's joining throughout the day

3. **Maybe confirmation** (5:00 PM):
   - At 5:00 PM voters with "maybe" get a "Vote Now" button with the leading time
   - Can confirm (Yes → winning time) or cancel (No → not joining)
   - At 6:00 PM remaining "maybe" votes are automatically converted to "not joining"

### Catch-up mechanism

On restart, the bot automatically executes **missed jobs** (maximum 1x per job). This prevents duplicate executions on quick restarts. State is tracked in `.scheduler_state.json` with file-locking via `.scheduler.lock`.

The bot must keep running to execute these tasks (resource usage is low).

---

## 📊 Status & Archive

### View status (`/dmk-poll-status`)

* Ephemeral message (only you can see it).
* Shows pause/names status and per day the counts.
* Names can also be shown (grouped with guests), depending on your setting.

### Archive

* **Command:** `/dmk-poll-archief` → shows ephemeral messages with separate archives:
  - 📊 **Weekend archive** (Friday-Sunday): Always available for download
  - 📊 **Weekday archive** (Monday-Thursday): Only visible when weekday polls are active
  - Each archive has its own **dropdown** to choose format: 🇺🇸 Comma (`,`) for international tools or 🇳🇱 Semicolon (`;`) for Dutch Excel
  - On selection the file is directly replaced with the new delimiter
  - Each archive has its own **delete button**, but deleting removes **both** archives permanently
* Archive grows with 1 line per week (after reset).
* Archive is **per guild and per channel**, so multiple Discord servers or multiple channels on the same server have their own archive.

---

## 🧪 Testing and Coverage

The bot has extensive unit tests with high code coverage for all functionality.

Run all unit tests with:
```bash
pytest -v
```

Generate coverage:
```bash
coverage run -m pytest -v
coverage report -m
coverage xml
```

> The coverage badge at the top works once CI has uploaded a `coverage.xml` to Codecov.

---

## ⚙️ Poll Settings

The bot has a unified settings system accessible via `/dmk-poll-instelling` with two configuration panels:

### Poll Options

Toggle which day/time combinations are visible in the poll:
- **Friday** 7:00 PM / 8:30 PM (🔴🟠)
- **Saturday** 7:00 PM / 8:30 PM (🟡⚪)
- **Sunday** 7:00 PM / 8:30 PM (🟢🔵)

**Use:** Handy for temporarily disabling certain days/times without removing the entire poll. For example: make only Friday available, or show only 7:00 PM times.

**Interactive UI:** Green buttons (✅ active) and gray buttons (⚪ disabled). Click to toggle.

### Notifications

Toggle 8 automatic notifications per channel:

| Notification | Time | Default | Description |
|--------------|------|---------|-------------|
| 📂 **Poll opened** | Tue 8:00 PM | ✅ On | When new poll is placed |
| 🔄 **Poll reset** | Tue 8:00 PM | ✅ On | When poll is reset for new week |
| 🔒 **Poll closed** | Mon 00:00 | ✅ On | When poll is closed |
| ⏰ **Vote reminder** | Fri/Sat/Sun 4:00 PM | ❌ Off | Reminder for non-voters (per day) |
| 🕐 **Thursday reminder** | Thu 8:00 PM | ❌ Off | Early reminder for those who haven't voted at all |
| ❓ **Maybe reminder** | 5:00 PM | ❌ Off | Confirmation for maybe-voters with "Vote Now" button |
| ✅ **Proceeding** | 6:00 PM | ✅ On | "Is happening" message with mentions of participants |
| 🎉 **Celebration** | automatic | ✅ On | When everyone has voted (celebration GIF) |

**Per-channel configuration:** Each poll channel can have its own notification preferences. Defaults are set for typical use, but can be adjusted per channel.

**Interactive UI:** Green buttons (🟢 active) and gray buttons (⚪ disabled). Click to toggle.

---

## 📅 Poll Scheduling

The bot supports **automatic activation and deactivation** of polls based on times. This is useful if you want polls only available at certain moments.

### How does it work?

- **Activation time**: Poll is automatically activated (unpaused) at the configured time
- **Deactivation time**: Poll is automatically deactivated (paused) at the configured time
- **Check**: The scheduler checks every minute if polls need to be activated or deactivated
- **Per channel**: Each poll channel can have its own activation/deactivation times

### Configuration

Scheduling is configured in `poll_settings.json` per channel:

```json
{
  "123456789": {
    "activation_time": "09:00",
    "deactivation_time": "23:00"
  }
}
```

### View status

With `/dmk-poll-status` you can view the current scheduling status, including:
- Whether scheduling is active
- When the poll will be activated/deactivated
- Whether the poll is currently active or paused

---

## 🎨 Customizable Opening Message

The opening message above the polls can be customized via `opening_message.txt`. This file can:
- Contain `@everyone` mentions
- Use markdown formatting (bold, italic, headers)
- Contain emojis
- Have multiple lines

If the file doesn't exist or can't be read, the bot uses a fallback message.

---

## 🔮 Future / Tips

* Extra days or other times? Adjust `poll_options.json` (watch out for archive logic).
* Adjust scheduler times? Edit `poll_settings.json` (not documented, see `apps/scheduler.py` for details).
* The bot is tailored for DMK, but can be used elsewhere with small adjustments.
* Feedback/ideas are welcome via GitHub Issues. Have fun racing! 🎮🏁

---

## 📝 Development Tips

### Code style

The bot follows Python best practices:
- **Type hints** for all functions
- **Docstrings** for public APIs
- **Async/await** for all I/O operations
- **Exception handling** with fallbacks and defensive programming
- **Safe API helpers** (discord_client.py) for robust Discord calls
- **Modularized structure** - command modules are split by functionality

### Adding new features

1. First write tests in `tests/`
2. Implement the feature in the appropriate module
3. Update the README with new functionality
4. Test with `python -m unittest discover -v`
5. Check coverage with `coverage report` (aim for high coverage)

### Debugging

The bot logs all scheduler jobs to stdout. For problems:
```bash
# Run locally with logs
python main.py

# View systemd logs
journalctl -u dmk-bot -f

# Check scheduler state
cat .scheduler_state.json
```

---

## 🎉 Recent Improvements

### v2.4 - Dual Language & Category Polls (2026-01)

**Multilingual support:**
- Full i18n (internationalization) support for Dutch (🇳🇱) and English (🇺🇸)
- Per-channel language setting via `/dmk-poll-taal` command
- All UI elements translated: buttons, notifications, decision messages, error messages
- Time notation adapted per language: "om 19:00 uur" (NL) vs "at 7:00 PM" (EN)

**Category-based polls:**
- Channels in the same Discord category automatically share votes
- Ideal for multilingual communities (e.g., NL + EN channels together)
- Votes in one channel are immediately visible in all linked channels
- Settings are automatically synchronized between linked channels

**Synchronized settings:**
- Poll options (day/time combinations)
- Period settings (open/close times)
- Notification preferences
- Reminder time
- Pause status

### v2.3 - Rolling Window Date System (2025-12-02)

**Rolling Window Date System:**
- **7-day rolling window**: Polls always show chronological dates (-1 day, today, +5 days ahead)
- **Automatic date updates**: Poll messages, vote messages, and scheduler notifications use rolling window for correct dates
- **Consistent date display**: All date bugs fixed

### v2.2 - Code Simplification (2025-11-09)

**Simplification of message deletion commands:**
- `/dmk-poll-off` and `/dmk-poll-verwijderen` refactored for better maintainability
- Code reduction from ~135 to ~45-52 lines per function (**62-67% smaller**)
- Same user experience, but much simpler code

### v2.1 - Celebration GIF Randomizer (2025-11-07)

**Celebration GIF Selection with Weighted Randomization:**
- Dynamic selection from 27 Tenor GIF URLs (`tenor-links.json`)
- Weighted ratio: Nintendo URLs are used **3x more often** than non-Nintendo URLs
- Fair distribution: Selects URL with lowest `count` within the chosen group

### v2.0 - Code refactoring & test coverage improvement

**Command restructuring and modularization**:
- New command structure for clear separation between temporary and permanent closing
- Large `dmk_poll.py` (978 lines) split into smaller, focused modules
- Better maintainability and readability

---

## 📄 License

This bot is open source. See [LICENSE](LICENSE) for details.

---

**Made with ❤️ for the Deaf Mario Kart community.**

**DMK-poll-bot was developed with help from [Claude](https://claude.com/claude-code), [Le Chat](https://chat.mistral.ai/chat), and [ChatGPT](https://chatgpt.com/).**

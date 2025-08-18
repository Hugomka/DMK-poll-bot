# DMK-poll-bot 🇳🇱

Een slimme, volledig automatische Discord-bot om weekenden te plannen voor **Deaf Mario Kart (DMK)**.
Ontwikkeld door [ChatGPT](https://openai.com/chatgpt) in samenwerking met **Goldway** (prompter en co-developer).

## ✅ Wat doet deze bot?

* Stuurt elke **maandag om 00:00** een poll voor vrijdag, zaterdag en zondag.
* Laat gebruikers stemmen via knoppen (geen reacties meer nodig).
* Verbergt stemresultaten tot **18:00 op de dag zelf**.
* Geeft automatisch aan **welke tijd doorgaat** (vanaf 6 stemmen).
* Stuurt optioneel een notificatie naar stemmers.
* Admins kunnen polls beheren met `/dmk-poll on/off/reset/status`.

## 📦 Features

| Functie                        | Beschrijving                                                                |
| ------------------------------ | --------------------------------------------------------------------------- |
| **🗳️ Stemmen per dag**        | Vrijdag, zaterdag, zondag — elk met eigen tijden                            |
| **✅ Aanpasbare pollopties**    | Opties configureerbaar via `poll_options.json`                              |
| **🔒 Async bestands-I/O**      | Veilige opslag zonder lag (`votes.json`, met lock)                          |
| **🗕️ Scheduler automatisch**  | Herstart poll elke maandag, toon stemmen om 18:00, enzovoort                |
| **🗸 Tijden doorgaan of niet** | Gaat alleen door bij ≥6 stemmen, 20:30 krijgt voorrang bij gelijkspel       |
| **👁️ Ephemeral stemmen**      | Stemmen gebeurt privé via knop + popup                                      |
| **💬 Slash commands**          | `/dmk-poll on`, `/off`, `/reset`, `/status`, `/pauze`, `/verwijderen`, enz. |
| **📊 Status bekijken**         | `/dmk-poll-status` toont live stemmen in een embed (ephemeral)              |

## 🛠️ Installatie

1. Clone deze repo op je server:

```bash
git clone https://github.com/Hugomka/DMK-poll-bot.git
cd DMK-poll-bot
```

2. Installeer de benodigde packages:

```bash
apt update && apt install -y python3.12-venv
python3 -m venv venv
source venv/bin/activate
pip install discord.py python-dotenv apscheduler pytz
```

3. Maak een `.env` bestand aan met je Discord-token:

```env
DISCORD_TOKEN=jouweigenbottokenhier
```

4. Start de bot handmatig voor test:

```bash
python main.py
```

5. (Optioneel) Maak een systemd-service voor automatisch starten:

```ini
# Bestand: /etc/systemd/system/dmk-bot.service
[Unit]
Description=DMK Discord Poll Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/DMK-poll-bot
ExecStart=/root/DMK-poll-bot/venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Daarna:

```bash
systemctl daemon-reload
systemctl enable dmk-bot
systemctl start dmk-bot
```

## 🧪 Vereisten

* Python 3.10 of hoger
* `discord.py`
* `python-dotenv`
* `apscheduler`
* `pytz`

## 📁 Bestanden

| Bestand                     | Doel                            |
| --------------------------- | ------------------------------- |
| `main.py`                   | Start de bot                    |
| `apps/commands/dmk_poll.py` | Slash commands                  |
| `apps/ui/poll_buttons.py`   | Stemknoppen                     |
| `apps/utils/*`              | Opslag, scheduler, poll-helpers |
| `poll_options.json`         | Configureerbare pollopties      |
| `votes.json`                | Dynamisch bestand met stemmen   |

## ✍️ Over deze bot

De DMK-poll-bot is met zorg ontwikkeld door [ChatGPT](https://openai.com/chatgpt), met prompts en bijdragen van **Goldway**, speciaal voor **Deaf Mario Kart**.
Het doel: een toegankelijke, efficiënte manier om spelavonden te organiseren — zonder gedoe met reacties of aparte bots.

🤝 Jouw stem telt. Jouw tijd ook.

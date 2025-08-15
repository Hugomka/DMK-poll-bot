# DMK-poll-bot 🇳🇱

Een slimme, volledig automatische Discord-bot om weekenden te plannen voor **Deaf Mario Kart (DMK)**.  
Ontwikkeld door [ChatGPT](https://openai.com/chatgpt) in samenwerking met de clubbeheerders.

## ✅ Wat doet deze bot?

- Stuurt elke **maandag om 00:00** een poll voor vrijdag, zaterdag en zondag.
- Laat gebruikers stemmen via knoppen (geen reacties meer nodig).
- Verbergt stemresultaten tot **18:00 op de dag zelf**.
- Geeft automatisch aan **welke tijd doorgaat** (vanaf 6 stemmen).
- Stuurt optioneel een notificatie naar stemmers.
- Admins kunnen polls beheren met `/dmk-poll on/off/reset/status`.

## 📦 Features

| Functie                                      | Beschrijving                                                                 |
|---------------------------------------------|------------------------------------------------------------------------------|
| **🗳️ Stemmen per dag**                        | Vrijdag, zaterdag, zondag — elk met eigen tijden                            |
| **✅ Aanpasbare pollopties**                 | Opties configureerbaar via `poll_options.json`                              |
| **🔒 Async bestands-I/O**                    | Veilige opslag zonder lag (`votes.json`, met lock)                          |
| **📅 Scheduler automatisch**                 | Herstart poll elke maandag, toon stemmen om 18:00, enzovoort                |
| **🟨 Tijden doorgaan of niet**              | Gaat alleen door bij ≥6 stemmen, 20:30 krijgt voorrang bij gelijkspel       |
| **👁️ Ephemeral stemmen**                    | Stemmen gebeurt privé via knop + popup                                      |
| **💬 Slash commands**                       | Alleen 3 admin-commando’s: `/on`, `/off`, `/reset`                          |
| **📊 Status bekijken**                      | `/dmk-poll-status` toont live stemmen in een embed (ephemeral)             |

## 🛠️ Installatie

1. Clone deze repo.
2. Maak een `.env` bestand aan met jouw Discord bot token:

```
DISCORD_TOKEN=jouweigenbottokenhier
```

3. Start de bot:

```bash
python main.py
```

## 🧪 Vereisten

- Python 3.10 of hoger
- `discord.py` v2.3+
- `python-dotenv`
- `apscheduler`

Installeer dependencies:

```bash
pip install -r requirements.txt
```

## 📁 Bestanden

| Bestand                  | Doel                                  |
|--------------------------|---------------------------------------|
| `main.py`               | Start de bot                          |
| `apps/commands/dmk_poll.py` | Slash commands                      |
| `apps/ui/poll_buttons.py`   | Stemknoppen                         |
| `apps/utils/*`              | Opslag, scheduler, poll-helpers     |
| `poll_options.json`         | Configureerbare pollopties         |
| `votes.json`                | Dynamisch bestand met stemmen       |

## ✍️ Over deze bot

De DMK-poll-bot is met zorg ontwikkeld door [ChatGPT](https://openai.com/chatgpt) in samenwerking met het bestuur van **Deaf Mario Kart**.  
Het doel: een toegankelijke, efficiënte manier om spelavonden te organiseren — zonder gedoe met reacties of aparte bots.

🤝 Jouw stem telt. Jouw tijd ook.

# DMK-poll-bot 🇳🇱

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B%20%7C%203.13-blue.svg)
![discord.py 2.3.2](https://img.shields.io/badge/discord.py-2.3.2-blueviolet.svg)
![License](https://img.shields.io/github/license/Hugomka/DMK-poll-bot)
![Last Commit](https://img.shields.io/github/last-commit/Hugomka/DMK-poll-bot)
![Issues](https://img.shields.io/github/issues/Hugomka/DMK-poll-bot)
![Stars](https://img.shields.io/github/stars/Hugomka/DMK-poll-bot?style=social)
[![Coverage](https://img.shields.io/codecov/c/github/Hugomka/DMK-poll-bot?label=Coverage)](https://codecov.io/gh/Hugomka/DMK-poll-bot)

**DMK-poll-bot** is een slimme, volledig automatische Discord-bot om weekenden te plannen voor **Deaf Mario Kart (DMK)**.
Deze bot is speciaal gemaakt voor de DMK-community, zodat het organiseren van game-avonden soepel en eerlijk gaat.
Je hoeft niet langer te puzzelen met reacties: de bot regelt de poll, verzamelt stemmen en communiceert duidelijk de uitkomst.

---

## 🔰 Introductie

DMK-poll-bot helpt de **DMK club** bij het plannen van races in het weekend. Elke week start de bot een nieuwe poll voor **vrijdag**, **zaterdag** en **zondag**.
Leden stemmen met knopjes, de stemmen blijven tot de deadline verborgen, en de bot beslist automatisch of er genoeg animo is.
Ook is er ondersteuning voor **gaststemmen** en een **CSV-archief** van resultaten. Kortom: een toegankelijke, gebruiksvriendelijke poll die past bij onze Discord-community.

**Waarom deze bot?**
Vroeger deden we dit met handmatige polls of reacties. Dat was onoverzichtelijk en kostte tijd.
Met DMK-poll-bot gaat dit **automatisch** en **eerlijk** – iedereen kan met één klik stemmen, resultaten komen precies op tijd, en de beslissing volgt vaste DMK-regels.

---

## 📦 Functies

| Functie | Beschrijving |
|---|---|
| **🗳️ Stemmen per dag** | Voor maandag t/m zondag elk een eigen poll met opties (standaard: alleen weekend actief). |
| **✅ Aanpasbare pollopties** | Tijden/opties via `poll_options.json` en `/dmk-poll-instelling` (standaard: 19:00, 20:30 voor vrijdag/zaterdag/zondag). |
| **🔒 Veilige opslag** | Stemmen in `votes.json` met async lock, zodat alles stabiel en snel blijft. |
| **⏰ Automatische scheduler** | Nieuwe week op dinsdag 20:00, dag-updates om 18:00, herinneringen om 16:00, notificaties bij "gaat door". |
| **📅 Poll scheduling** | Plan polls om automatisch te activeren/deactiveren op specifieke tijden (per kanaal configureerbaar). |
| **🏁 Automatische beslissing** | Op de dag zelf na de deadline: ≥6 stemmen nodig; bij gelijkstand wint **20:30**. |
| **📢 Slimme notificaties** | Herinneringen voor niet-stemmers (16:00), vroege herinnering donderdag (20:00), Misschien-bevestiging (17:00), en mentions bij doorgaan-berichten. |
| **👁️ Verborgen stemmen** | Tot de deadline (standaard 18:00) blijven aantallen verborgen in de kanaalberichten. |
| **🎟️ Gaststemmen** | Leden kunnen stemmen **voor gasten** toevoegen/verwijderen. |
| **💬 Slash commando's** | `/dmk-poll-on/reset/pauze/verwijderen/instelling/stemmen/status/notify`, archief downloaden/verwijderen, en gast-commando's. |
| **⚙️ Configureerbare instellingen** | Via `/dmk-poll-instelling`: toggle poll-opties (14 dag/tijd combinaties: maandag t/m zondag, 19:00 en 20:30) en notificaties (8 types aan/uit per kanaal). |
| **📊 Live status** | `/dmk-poll-status` toont per dag de aantallen, optioneel namen, en scheduling informatie. |
| **🔄 Misschien-conversie** | Wie om 17:00 "misschien" heeft gestemd krijgt een bevestigingsknop; om 18:00 worden resterende "misschien"-stemmen automatisch omgezet naar "niet meedoen". |
| **🔔 Privacy-vriendelijke mentions** | Tijdelijke mentions (5 sec zichtbaar voor herinneringen), persistente mentions (5 uur zichtbaar voor "gaat door"-berichten). |

---

## 💬 Overzicht van commando's

DMK-poll-bot werkt met **Slash commando's** (typ `/` in Discord).

| Commando | Uitleg |
|---|---|
| **`/dmk-poll-on`** *(default: admin/mod)* | Plaatst of vernieuwt de 3 dag-berichten, een openingsbericht met `@everyone`, de **🗳️ Stemmen**-knop en een notificatiebericht in het huidige kanaal. |
| **`/dmk-poll-reset`** *(default: admin/mod)* | Archiveren (CSV) + **alle stemmen wissen** → klaar voor nieuwe week. |
| **`/dmk-poll-pauze`** *(default: admin/mod)* | Pauzeer/hervat stemmen. Bij pauze is de Stemmen-knop uitgeschakeld. |
| **`/dmk-poll-verwijderen`** *(default: admin/mod)* | Sluit en verwijder alle poll-berichten in het kanaal en zet dit kanaal uit voor de scheduler. Polls komen hier niet meer terug, tenzij je later **/dmk-poll-on** gebruikt om het kanaal opnieuw te activeren. |
| **`/dmk-poll-instelling`** *(default: admin/mod)* | Open instellingen voor de poll. Kies tussen **Poll-opties** (toggle 14 dag/tijd combinaties: maandag t/m zondag, elk 19:00 en 20:30; standaard alleen weekend actief) of **Notificaties** (toggle 8 automatische notificaties: poll geopend/gereset/gesloten, herinneringen, doorgaan, felicitatie). Interactieve UI met groene/grijze knoppen per kanaal. ⚠️ Let op: bij activeren van maandag/dinsdag de gesloten periode aanpassen via `/dmk-poll-on`. |
| **`/dmk-poll-stemmen`** *(default: admin/mod)* | Instelling per dag of alle dagen: **altijd zichtbaar** of **verborgen tot** `uu:mm` (standaard 18:00). |
| **`/dmk-poll-archief`** *(default: admin/mod)* | Bekijk en beheer het CSV-archief: kies CSV-formaat (🇺🇸 Comma / 🇳🇱 Semicolon), download direct, of verwijder archief. |
| **`/dmk-poll-status`** *(default: admin/mod)* | Ephemeral embed: pauze/namen-status en per dag de aantallen met namen. |
| **`/dmk-poll-notify`** *(default: admin/mod)* | Stuur handmatig een notificatie. Kies uit 7 standaard notificaties of gebruik een eigen tekst. Extra optie: `ping` om te kiezen tussen @everyone, @here (alleen online users) of geen ping (stille notificatie). |
| **`/gast-add`** | Voeg gaststemmen toe: `/gast-add slot:"Vrijdag 20:30" namen:"Mario, Luigi"` |
| **`/gast-remove`** | Verwijder gaststemmen: `/gast-remove slot:"Vrijdag 20:30" namen:"Mario"` |

**Opmerking:** De meeste admin-commando's geven **ephemeral** feedback (alleen zichtbaar voor jou), zodat het kanaal schoon blijft.

---

## 🔐 Rechten per server instellen

De defaults staan in de bot (sommige commands *(default: admin/mod)*, andere voor iedereen).
Beheerders en moderators kunnen dit per server **aanpassen** via Discord:

1. Ga naar **Server Settings → Integrations → [jouw bot] → Commands**.
2. Kies een command (bijv. `/dmk-poll-on`).
3. Stel **Roles and Members** in: welke rol(len) of personen het mogen gebruiken.
4. Optioneel: beperk per **kanaal**.
5. Klaar! Dit overschrijft de defaults. Je hoeft de bot-code niet te wijzigen.

---

## 👥 Stemmen met gasten

- **Gast toevoegen:**
  Voorbeeld:
```
/gast-add slot:"Zaterdag 19:00" namen:"Pauline, King Boo"
```

Je kunt meerdere namen scheiden met komma's of `;`. De bot meldt welke gasten zijn toegevoegd en welke al bestonden.

- **Gast verwijderen:**
Voorbeeld:
```
/gast-remove slot:"Zaterdag 19:00" namen:"King Boo"
```
De bot meldt welke namen zijn verwijderd of niet gevonden.

**Hoe telt dit mee?** Elke gast telt als een **extra stem** op dat tijdstip, gekoppeld aan jouw account. In de openbare poll zie je alleen aantallen. In `/dmk-poll-status` worden stemmen gegroepeerd per eigenaar, bv.:
`@Mario (@Mario: Luigi, Peach), @Toad`

---

## ⚙️ Poll-opties (config)

De stemopties staan in **`poll_options.json`**. Standaard:

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

* Pas tijden/emoji's gerust aan.
* Hou de structuur aan (`dag`, `tijd`, `emoji`).
* Restart de bot na wijzigen zodat nieuwe polls de aanpassing gebruiken.
* Als het JSON ontbreekt of stuk is, vallen we terug op deze defaults.

---

## ⚙️ Installatie

> Vereist: **Python 3.10+** en een **Discord Bot Token**.

1. **Code klonen**
```bash
git clone https://github.com/Hugomka/DMK-poll-bot.git
cd DMK-poll-bot
```

2. **Virtuele omgeving**
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

3. **Afhankelijkheden**
- Minimale runtime:
  ```bash
  pip install -r requirements.txt
  ```
- Ontwikkeling (incl. tests/lint/coverage):
  ```bash
  pip install -r dev-requirements.txt
  ```
  > Tip Windows: als `pip` niet werkt, gebruik `python -m pip install -r dev-requirements.txt`.

4. **.env maken**
```env
DISCORD_TOKEN=je_bot_token_hier
```

5. **Bot starten (test)**
```bash
python main.py
```

---

6. **Als service draaien (systemd, Linux)**
   Maak `/etc/systemd/system/dmk-bot.service`:

```ini
[Unit]
Description=DMK Discord Poll Bot
After=network.target

[Service]
Type=simple
User=<jouw-usernaam>
WorkingDirectory=/pad/naar/DMK-poll-bot
ExecStart=/pad/naar/DMK-poll-bot/venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Activeer:

```bash
sudo systemctl daemon-reload
sudo systemctl enable dmk-bot
sudo systemctl start dmk-bot
# logs
journalctl -u dmk-bot -f
```

**Tip:** Zorg dat de bot juiste rechten heeft (application commands, berichten lezen/schrijven).

---

## 🚀 Deployment

### Eerste deployment (nieuwe server)

De bot maakt automatisch alle runtime bestanden aan bij de eerste start:

```bash
# Clone repository
git clone https://github.com/Hugomka/DMK-poll-bot.git
cd DMK-poll-bot

# Setup (zie installatie-instructies hierboven)
python -m venv .venv
source .venv/bin/activate  # of .\.venv\Scripts\Activate.ps1 op Windows
pip install -r requirements.txt

# Maak .env met DISCORD_TOKEN
echo "DISCORD_TOKEN=je_token_hier" > .env

# Start de bot (creëert automatisch tenor-links.json en andere runtime bestanden)
python main.py
```

### Update deployment (bestaande server)

Bij updates worden runtime bestanden **niet** overschreven:

```bash
# Pull updates
git pull origin main

# Restart de bot
# (runtime bestanden blijven behouden met hun huidige data)
```

### Automatische Tenor GIF Sync

De bot synchroniseert automatisch `tenor-links.template.json` naar `tenor-links.json`:
- **Wanneer**: Elke maandag om 00:00 (poll sluitingstijd)
- **Wat**: Nieuwe GIFs worden toegevoegd met count: 0, verwijderde GIFs worden verwijderd
- **Behoud**: Bestaande GIF counts blijven behouden
- **Efficiëntie**: Sync wordt alleen uitgevoerd als er daadwerkelijk nieuwe of verwijderde GIFs zijn (niet bij alleen count wijzigingen)

**GIF lijst bijwerken:**
1. Bewerk `tenor-links.template.json` op je development machine
2. Commit en push de wijzigingen
3. Deploy naar productie met `git pull`
4. De bot zal automatisch synchroniseren op maandag 00:00 (of bij herstart via catch-up mechanisme)

---

## 🔧 Technische details

### Map-structuur

```
DMK-poll-bot/
├── apps/
│   ├── commands/           # Slash commando's (gemodulariseerd)
│   │   ├── __init__.py             # Command utilities en helpers
│   │   ├── dmk_poll.py             # Main entry point voor alle commando's
│   │   ├── poll_lifecycle.py       # Lifecycle commando's (on/reset/pauze/verwijderen)
│   │   ├── poll_config.py          # Poll configuratie commando (instelling)
│   │   ├── poll_votes.py           # Stemzichtbaarheid commando's
│   │   ├── poll_guests.py          # Gast-commando's (add/remove)
│   │   ├── poll_archive.py         # Archief commando's (download/verwijderen)
│   │   └── poll_status.py          # Status commando en notify
│   ├── ui/                 # Discord UI componenten
│   │   ├── poll_buttons.py           # Poll stemknoppen en views
│   │   ├── stem_nu_button.py         # "Stem Nu" knop voor Misschien-bevestiging
│   │   ├── poll_options_settings.py  # Poll-opties settings view (dag/tijd toggles)
│   │   ├── notification_settings.py  # Notificatie settings view (8 notificatie toggles)
│   │   ├── archive_view.py           # Archief download view met verwijder-knop
│   │   └── cleanup_confirmation.py   # Cleanup confirmation view voor oude berichten
│   ├── utils/              # Hulpfuncties
│   │   ├── poll_storage.py        # Stem-opslag (votes.json)
│   │   ├── poll_settings.py       # Poll-instellingen (pauze, zichtbaarheid, scheduling)
│   │   ├── poll_message.py        # Bericht-ID opslag en updates
│   │   ├── message_builder.py     # Poll-bericht constructie
│   │   ├── archive.py              # CSV-archief beheer
│   │   ├── mention_utils.py       # Tijdelijke/persistente mentions met cleanup
│   │   ├── discord_client.py      # Discord API helpers
│   │   └── logger.py               # Logging utilities
│   ├── logic/              # Business logic
│   │   ├── decision.py             # Beslissingsregels (wie wint?)
│   │   └── visibility.py           # Zichtbaarheidslogica (verbergen/tonen)
│   ├── entities/           # Data models
│   │   └── poll_option.py          # Poll optie dataclass
│   ├── data/               # Data templates (standaard data-bestanden voor nieuwe kanalen)
│   │   ├── poll_message.json       # Template voor bericht-IDs
│   │   └── votes.json              # Template voor stem-opslag
│   └── scheduler.py        # APScheduler taken (reset, herinneringen, notificaties, scheduling)
├── tests/                  # Unittests met hoge coverage
│   ├── test_poll_lifecycle*.py     # Tests voor lifecycle commando's
│   ├── test_poll_guests.py         # Tests voor gast-commando's
│   ├── test_poll_archive.py        # Tests voor archief commando's
│   ├── test_poll_votes.py          # Tests voor stemzichtbaarheid
│   ├── test_poll_message.py        # Tests voor bericht-opslag
│   ├── test_poll_settings*.py      # Tests voor poll settings en scheduling
│   ├── test_poll_options_settings_*.py  # Tests voor poll-opties settings (logic + UI)
│   ├── test_notification_settings_*.py  # Tests voor notificatie settings (logic + UI)
│   ├── test_status*.py             # Tests voor status commando
│   ├── test_cleanup_confirmation.py # Tests voor cleanup UI
│   ├── test_mention_utils.py       # Tests voor mention utilities
│   ├── test_scheduler_*.py         # Tests voor scheduler functies
│   ├── test_permissions.py         # Tests voor command permissions
│   └── ...                          # Andere test modules
├── main.py                 # Bot entry point
├── poll_options.json       # Config van stemopties
├── opening_message.txt     # Aanpasbare openingstekst voor polls
├── requirements.txt        # Runtime dependencies
└── dev-requirements.txt    # Development dependencies (pytest, coverage, linting)
```

### Belangrijke data-bestanden

| Bestand/map               | Runtime Data | Doel                                                                             |
| ------------------------- | :----------: | -------------------------------------------------------------------------------- |
| `poll_options.json`       | ❌ | Config van opties (tijden/emoji's) per dag.                                      |
| `votes.json`              | ✅ | Alle stemmen (per user/gast per dag). Async lock voor veilige I/O.               |
| `poll_settings.json`      | ✅ | Kanaal-instellingen: pauze, zichtbaarheid (altijd/deadline), namen tonen, scheduling (activatie/deactivatie tijden), poll-opties (welke dagen/tijden enabled), notificatie preferences (8 toggles per kanaal). |
| `poll_message.json`       | ✅ | Opslag van bericht-ID's van de channel-polls (om te kunnen updaten/verwijderen). |
| `archive/dmk_archive_{guild_id}_{channel_id}_weekend.csv` | ✅ | Wekelijks CSV-archief voor weekend polls (vrijdag-zondag) met weeknummer, datums en aantallen per optie/dag. |
| `archive/dmk_archive_{guild_id}_{channel_id}_weekday.csv` | ✅ | Wekelijks CSV-archief voor weekday polls (maandag-donderdag) met weeknummer, datums en aantallen per optie/dag. |
| `opening_message.txt`     | ❌ | Aanpasbaar openingsbericht dat getoond wordt boven de polls.                     |
| `tenor-links.json`        | ✅ | Celebration GIF URLs met gebruikscounts (wordt automatisch gesynchroniseerd).   |
| `tenor-links.template.json` | ❌ | Template voor GIF lijst (bron van waarheid, wordt WEL gecommit).              |
| `resources/`              | ❌ | Lokale afbeeldingen voor fallback (bedankt-puppies-kitties.jpg).                |
| `.scheduler_state.json`   | ✅ | State van de scheduler (laatste uitvoering van jobs).                            |
| `.scheduler.lock`         | ✅ | File lock voor scheduler state om race conditions te voorkomen.                  |

**Runtime data bestanden** (✅) worden automatisch aangemaakt en bijgewerkt door de bot. Deze staan in `.gitignore` en worden **niet** gecommit naar git.

### Archief

Bij resetten voor een nieuwe week voegt de bot 1 regel toe aan **beide** archieven met: ISO weeknummer (bijv. 2025-W44), datum per dag, en per dag de aantallen voor 19:00, 20:30, misschien, was misschien (💤), niet meedoen, en niet gestemd (👻).

**Twee aparte archieven:**
- **Weekend archief** (`_weekend.csv`): Vrijdag, zaterdag, zondag
- **Weekday archief** (`_weekdays.csv`): Maandag, dinsdag, woensdag, donderdag

Downloaden en wissen kan met de archief-commando's. Archief is **per guild en per kanaal** opgeslagen in `archive/dmk_archive_{guild_id}_{channel_id}_{type}.csv`.

#### Archive migratie

Als je oude archive bestanden hebt (zonder de nieuwste kolommen), kun je deze migreren met het migratie-script:

```bash
py migrate_archives.py
```

**CSV Versies:**
- **V1** (16 kolommen): Origineel formaat, zonder niet_gestemd en was_misschien kolommen
- **V2** (19 kolommen): Met niet_gestemd kolommen toegevoegd
- **V3** (22 kolommen): Met was_misschien kolommen toegevoegd - **HUIDIGE VERSIE**
- **V4** (22 kolommen): ISO week formaat (2025-W44 in plaats van alleen 44)

Dit script:
- Vindt automatisch alle archive CSV bestanden
- Voegt de nieuwe kolommen toe: `vr_niet_gestemd`, `za_niet_gestemd`, `zo_niet_gestemd`, `vr_was_misschien`, `za_was_misschien`, `zo_was_misschien`
- Converteert week nummers naar ISO 8601 formaat (YYYY-Www, bijvoorbeeld 2025-W44)
- Behoudt alle bestaande data
- Gebruikt **lege waarden** voor oude data (om aan te geven dat deze metrics niet getrackt werden in die weken)
- Is veilig om meerdere keren uit te voeren (slaat reeds gemigreerde bestanden over)

**Wanneer migreren?** Bij eerste deployment na updates. Nieuwe archives krijgen automatisch het correcte formaat.

**Was Misschien Tracking:**
De bot houdt nu bij hoeveel "misschien" stemmen automatisch worden omgezet naar "niet meedoen" wanneer de deadline (18:00) passeert. Dit geeft inzicht in hoeveel mensen niet op tijd hun stem hebben bevestigd. Deze data wordt getoond in `/dmk-poll-status` met een 💤 emoji en opgeslagen in het CSV-archief.

### Beslissingsregels

* Beslissing alleen op de **dag zelf** na de **deadline** (standaard 18:00).
* **Minimaal 6 stemmen** nodig (configureerbaar via `MIN_NOTIFY_VOTES`).
* **Gelijk aantal? → 20:30 wint.**
* Anders wint het tijdstip met de meeste stemmen.
* Te weinig stemmen? → "Gaat niet door."

### Tijdzone

Alle tijden zijn in **Europe/Amsterdam** (CET/CEST).

---

## ⏰ Automatisering (scheduler)

De bot gebruikt APScheduler voor automatische taken:

| Tijdstip | Dag | Taak | Beschrijving |
|---|---|---|---|
| **00:00** | Maandag | Tenor GIF sync | Sync tenor-links.template.json naar tenor-links.json (alleen bij wijzigingen) |
| **20:00** | Dinsdag | Reset polls | Stemmen leeg maken, archiveren, algemene resetmelding sturen |
| **16:00** | Vrijdag, Zaterdag, Zondag | Herinnering niet-stemmers | Mention sturen naar leden die nog niet gestemd hebben voor die dag (tijdelijk, 5 sec) |
| **17:00** | Vrijdag, Zaterdag, Zondag | Misschien-bevestiging | "Stem Nu" knop sturen naar Misschien-stemmers met leidende tijd |
| **18:00** | Dagelijks | Poll-update | Aantallen tonen, beslissingsregel toevoegen onder de poll |
| **18:00** | Vrijdag, Zaterdag, Zondag | Misschien-conversie | Resterende "misschien"-stemmen omzetten naar "niet meedoen" |
| **18:05** | Vrijdag, Zaterdag, Zondag | Doorgaan-notificatie | Mentions van stemmers op winnende tijd (≥6), persistente mentions (5 uur) |
| **20:00** | Donderdag | Vroege herinnering | Mention naar leden die nog helemaal niet gestemd hebben (tijdelijk, 5 sec) |
| **Elke minuut** | Continu | Scheduled poll activation | Activeer geplande polls op basis van activatietijd |
| **Elke minuut** | Continu | Scheduled poll deactivation | Deactiveer geplande polls op basis van deactivatietijd |

### Notificatiesysteem

De bot heeft een slim notificatiesysteem met privacy in gedachten:

1. **Tijdelijke mentions** (5 seconden zichtbaar):
   - Herinneringen voor niet-stemmers (16:00 vrijdag/zaterdag/zondag)
   - Vroege herinneringen (20:00 donderdag)
   - Reset-meldingen (@everyone)
   - Gebruikers krijgen wel een notificatie op hun apparaat, maar de mention verdwijnt snel uit het kanaal
   - Na 1 uur wordt het hele bericht automatisch verwijderd

2. **Persistente mentions** (5 uur zichtbaar):
   - "Gaat door"-berichten voor deelnemers (18:05 vrijdag/zaterdag/zondag)
   - Blijven zichtbaar voor 5 uur, daarna wordt het hele bericht automatisch verwijderd
   - Dit zorgt ervoor dat deelnemers gedurende de dag kunnen zien wie er meedoet

3. **Misschien-bevestiging** (17:00):
   - Om 17:00 krijgen stemmers met "misschien" een "Stem Nu" knop met de leidende tijd
   - Kunnen bevestigen (Ja → winnende tijd) of afzeggen (Nee → niet meedoen)
   - Om 18:00 worden resterende "misschien"-stemmen automatisch omgezet naar "niet meedoen"

### Catch-up mechanisme

Bij herstart voert de bot automatisch **gemiste jobs** uit (maximaal 1x per job). Dit voorkomt dubbele uitvoeringen bij snelle herstarts. State wordt bijgehouden in `.scheduler_state.json` met file-locking via `.scheduler.lock`.

De bot moet blijven draaien om deze taken uit te voeren (resourceverbruik is laag).

---

## 📊 Status & archief

### Status bekijken (`/dmk-poll-status`)

* Ephemeral bericht (alleen jij ziet het).
* Toont pauze-/namen-status en per dag de aantallen.
* Namen kunnen ook getoond worden (gegroepeerd met gasten), afhankelijk van je instelling.

### Archief

* **Commando:** `/dmk-poll-archief` → toont ephemeral berichten met aparte archieven:
  - 📊 **Weekend archief** (vrijdag-zondag): Altijd beschikbaar voor download
  - 📊 **Weekday archief** (maandag-donderdag): Alleen zichtbaar wanneer weekday polls actief zijn
  - Elk archief heeft eigen **dropdown** om formaat te kiezen: 🇺🇸 Comma (`,`) voor internationale tools of 🇳🇱 Semicolon (`;`) voor Nederlandse Excel
  - Bij selectie wordt het bestand direct vervangen met de nieuwe delimiter
  - Elke archief heeft eigen **verwijder-knop**, maar verwijderen verwijdert **beide** archieven permanent
* Archief groeit met 1 regel per week (na reset).
* Archief is **per guild en per kanaal**, zodat meerdere Discord-servers of meerdere kanalen op dezelfde server hun eigen archief hebben.
* **Bestandsnamen**: `dmk_archive_{guild_id}_{channel_id}_weekend.csv` en `dmk_archive_{guild_id}_{channel_id}_weekday.csv`

---

## 🧪 Testen en dekking

De bot heeft uitgebreide unittests met hoge code coverage voor alle functionaliteit.

Alle unittests draaien met:
```bash
pytest -v
```

Dekking genereren:
```bash
coverage run -m pytest -v
coverage report -m
coverage xml
```

> De coverage-badge bovenaan werkt zodra de CI een `coverage.xml` heeft geüpload naar Codecov.

### Test-overzicht

De tests dekken onder andere:
- **Poll lifecycle** (on/reset/pauze/verwijderen commando's)
- **Poll-opslag** (stemmen toevoegen/verwijderen/resetten, exception handling)
- **Poll-settings** (pauze, zichtbaarheid, namen tonen, scheduling)
- **Poll-opties settings** (logic + UI voor dag/tijd toggles, per-channel state)
- **Notificatie settings** (logic + UI voor 8 notificatie toggles, defaults, persistence)
- **Scheduling** (activatie/deactivatie op tijden, scheduler state, catch-up)
- **Gast-commando's** (toevoegen, verwijderen, groepering, validatie)
- **Archief** (download, verwijderen, per guild/channel)
- **Message builder** (bericht-constructie met verborgen aantallen)
- **Beslissingslogica** (winnaar bepalen, gelijkstand, minimum stemmen)
- **Scheduler** (catch-up, reset venster, gemiste jobs, deadline mode, Misschien-flow, notificatie filtering)
- **UI components** (poll buttons, Stem Nu button, poll-opties view, notificatie view, archief view, cleanup confirmation)
- **Notificaties** (tijdelijk, persistent, Misschien-flow, cleanup)
- **Mention utilities** (tijdelijke/persistente mentions, auto-delete, display names)
- **Discord client** (safe API calls met exception handling)
- **Permissions** (command defaults, admin/mod checks)

### Recente test-verbeteringen

De testdekking is recent significant verbeterd door:
- Comprehensive tests die alle functionaliteit uitgebreid dekken
- Uitgebreide tests voor exception handling in alle modules
- Tests voor edge cases en error scenarios
- Tests voor scheduler deadline mode en Misschien-flow
- Tests voor cleanup confirmation en mention utilities
- Tests voor gemodulariseerde command structuur
- Tests voor permissions en default command settings

---

## ⚙️ Poll Instellingen

De bot heeft een unified settings systeem toegankelijk via `/dmk-poll-instelling` met twee configuratiepanelen:

### Poll-opties

Toggle welke dag/tijd combinaties zichtbaar zijn in de poll:
- **Vrijdag** 19:00 / 20:30 (🔴🟠)
- **Zaterdag** 19:00 / 20:30 (🟡⚪)
- **Zondag** 19:00 / 20:30 (🟢🔵)

**Gebruik:** Handig om bepaalde dagen/tijden tijdelijk uit te schakelen zonder de hele poll te verwijderen. Bijvoorbeeld: alleen vrijdag beschikbaar maken, of alleen 19:00 tijden tonen.

**Interactieve UI:** Groene knoppen (✅ actief) en grijze knoppen (⚪ uitgeschakeld). Klik om te togglen.

### Notificaties

Toggle 8 automatische notificaties per kanaal:

| Notificatie | Tijdstip | Default | Beschrijving |
|-------------|----------|---------|--------------|
| 📂 **Poll geopend** | di 20:00 | ✅ Aan | Wanneer nieuwe poll wordt geplaatst |
| 🔄 **Poll gereset** | di 20:00 | ✅ Aan | Wanneer poll wordt gereset voor nieuwe week |
| 🔒 **Poll gesloten** | ma 00:00 | ✅ Aan | Wanneer poll wordt gesloten |
| ⏰ **Herinnering stemmen** | vr/za/zo 16:00 | ❌ Uit | Herinnering voor niet-stemmers (per dag) |
| 🕐 **Herinnering donderdag** | do 20:00 | ❌ Uit | Vroege herinnering voor wie helemaal niet gestemd heeft |
| ❓ **Herinnering misschien** | 17:00 | ❌ Uit | Bevestiging voor misschien-stemmers met "Stem Nu" knop |
| ✅ **Doorgaan** | 18:00 | ✅ Aan | "Gaat door" bericht met mentions van deelnemers |
| 🎉 **Felicitatie** | automaat | ✅ Aan | Wanneer iedereen heeft gestemd (celebration GIF) |

**Per-channel configuratie:** Elke poll-kanaal kan eigen notificatie voorkeuren hebben. Defaults zijn ingesteld voor typisch gebruik, maar kunnen aangepast worden per kanaal.

**Interactieve UI:** Groene knoppen (🟢 actief) en grijze knoppen (⚪ uitgeschakeld). Klik om te togglen.

---

## 📅 Poll Scheduling

De bot ondersteunt **automatische activering en deactivering** van polls op basis van tijden. Dit is handig als je polls alleen op bepaalde momenten beschikbaar wilt hebben.

### Hoe werkt het?

- **Activatietijd**: Poll wordt automatisch geactiveerd (uit pauze gehaald) op het ingestelde tijdstip
- **Deactivatietijd**: Poll wordt automatisch gedeactiveerd (in pauze gezet) op het ingestelde tijdstip
- **Controle**: De scheduler controleert elke minuut of er polls geactiveerd of gedeactiveerd moeten worden
- **Per kanaal**: Elke poll-kanaal kan zijn eigen activatie/deactivatie tijden hebben

### Configuratie

Scheduling wordt geconfigureerd in `poll_settings.json` per kanaal:

```json
{
  "123456789": {
    "activation_time": "09:00",
    "deactivation_time": "23:00"
  }
}
```

### Status bekijken

Met `/dmk-poll-status` kun je de huidige scheduling-status bekijken, inclusief:
- Of scheduling actief is
- Wanneer de poll geactiveerd/gedeactiveerd wordt
- Of de poll momenteel actief of gepauzeerd is

---

## 🎨 Aanpasbaar openingsbericht

Het openingsbericht boven de polls kan aangepast worden via `opening_message.txt`. Dit bestand kan:
- `@everyone` mentions bevatten
- Markdown opmaak gebruiken (vet, italic, kopjes)
- Emoji's bevatten
- Meerdere regels hebben

**Standaard bericht:**
```
@everyone
# 🎮 **Welkom bij de DMK-poll!**

Elke week organiseren we DMK-avonden op vrijdag, zaterdag en zondag. Stem hieronder op de avonden waarop jij mee wilt doen! De stemmen blijven verborgen tot de deadline van 18:00 uur. Heb je nog niet gestemd of misschien gestemd? Dan krijg je 1 uur voor de deadline een herinnering. Als je dan nog niet stemt, wordt je stem automatisch omgezet naar 'niet meedoen'. Dus wees op tijd als je graag mee wilt doen, en zet de meldingen voor dit kanaal aan.

ℹ️ **Stem alsjeblieft op elke dag, ook als je denkt niet mee te doen. Zo blijft het overzicht duidelijk.**

📅 **Hoe werkt het?**
• Klik op **🗳️ Stemmen** om je keuzes aan te geven
• Je kunt meerdere tijden kiezen
• Je kunt je stem altijd aanpassen

👥 **Gasten meebrengen?**
Gebruik `/gast-add` om gasten toe te voegen aan je stem.

Veel plezier! 🎉
```

Als het bestand niet bestaat of niet gelezen kan worden, gebruikt de bot een fallback-bericht.

---

## 🔮 Toekomst / tips

* Extra dagen of andere tijden? Pas `poll_options.json` aan (let op archieflogica).
* Scheduler-tijden aanpassen? Bewerk `poll_settings.json` (niet-gedocumenteerd, zie `apps/scheduler.py` voor details).
* De bot is op maat voor DMK, maar kan met kleine aanpassingen ook elders gebruikt worden.
* Feedback/ideeën zijn welkom via GitHub Issues. Veel race-plezier! 🎮🏁

---

## 📝 Ontwikkeltips

### Code-stijl

De bot volgt Python best practices:
- **Type hints** voor alle functies
- **Docstrings** voor publieke API's
- **Async/await** voor alle I/O operaties
- **Exception handling** met fallbacks en defensive programming
- **Safe API helpers** (discord_client.py) voor robuuste Discord calls
- **Gemodulariseerde structuur** - command modules zijn opgesplitst naar functionaliteit

### Recente refactoring

De codebase is recent gerefactored voor betere onderhoudbaarheid:
- **Command modularisatie**: `dmk_poll.py` opgesplitst in kleinere modules
  - `poll_lifecycle.py` - Lifecycle commando's (on/reset/pauze/verwijderen)
  - `poll_votes.py` - Stemzichtbaarheid
  - `poll_guests.py` - Gast-functionaliteit
  - `poll_archive.py` - Archief beheer
  - `poll_status.py` - Status en notificaties
- **UI componenten**: Toegevoegd cleanup_confirmation.py voor oude berichten
- **Mention utilities**: Uitgebreid met display names en auto-cleanup functies
- **Test coverage**: Significant verbeterd met uitgebreide tests

### Nieuwe features toevoegen

1. Schrijf eerst tests in `tests/`
2. Implementeer de feature in de juiste module
3. Update de README met nieuwe functionaliteit
4. Test met `python -m unittest discover -v`
5. Check coverage met `coverage report` (streef naar hoge coverage)

### Debugging

De bot logt alle scheduler-jobs naar stdout. Bij problemen:
```bash
# Lokaal draaien met logs
python main.py

# Systemd logs bekijken
journalctl -u dmk-bot -f

# Scheduler state checken
cat .scheduler_state.json
```

---

## 🎉 Recente verbeteringen

### v2.3 - Rolling Window Date System (2025-12-02)

**Rolling Window Datum Systeem:**
- **7-daags rollend venster**: Polls tonen altijd chronologische datums (-1 dag, vandaag, +5 dagen vooruit)
- **Automatische datum updates**: Poll-berichten, stemberichten, en scheduler notificaties gebruiken rolling window voor correcte datums
- **Consistente datum weergave**: Alle datum bugs opgelost - geen 27 november meer wanneer 4 december verwacht wordt
- **Hammertime timestamps**: Discord timestamps tonen correcte datums in gebruiker's tijdzone

**Wat is gefixt:**
- Message builder fallback gebruikt rolling window i.p.v. oude `_get_next_weekday_date_iso` logica
- Vote message legendas (stemberichten) tonen correcte rolling window datums
- Scheduler decision announcements gebruiken rolling window per channel
- Poll options settings UI gebruikt rolling window voor tijdzone legenda
- Automatische cleanup van oude berichten buiten rolling window

**Test resultaten:** 34 nieuwe/aangepaste tests passing ✅
- `test_remaining_date_bugs.py`: Bewijst dat fallback correcte datums gebruikt
- `test_vote_message_dates.py`: Bewijst dat stemberichten correcte datums tonen
- `test_rolling_window_integration.py`: Test integratie met `/dmk-poll-on`
- `test_scheduler_update_all_polls.py`: Rolling window mock updates

**Bestanden aangepast:**
- `apps/utils/message_builder.py`: Rolling window fallback logica
- `apps/ui/poll_buttons.py`: Vote message datums uit rolling window
- `apps/scheduler.py`: Decision announcement + cleanup oude berichten
- `apps/ui/poll_options_settings.py`: Settings embed met channel_id parameter
- `apps/commands/poll_config.py`: Geeft channel_id door aan settings embed
- `apps/commands/poll_lifecycle.py`: Cleanup oude berichten buiten rolling window
- `apps/commands/poll_status.py`: Gebruikt altijd huidige dag (geen opgeslagen waarde)
- `apps/utils/poll_message.py`: Haalt datums uit rolling window

**Belangrijke notitie:**
- `dag_als_vandaag` parameter wordt NIET meer opgeslagen in state
- Rolling window gebruikt altijd de huidige dag bij updates (berekend on-the-fly)
- Oude berichten buiten rolling window worden automatisch verwijderd

### v2.2 - Code Simplification (2025-11-09)

**Vereenvoudiging van message deletion commands:**
- `/dmk-poll-off` en `/dmk-poll-verwijderen` gerefactored voor betere onderhoudbaarheid
- Code reductie van ~135 naar ~45-52 regels per functie (**62-67% kleiner**)
- Verwijderde redundante message-by-ID deletion logic
- Nu simpelweg: scan `channel.history()` en verwijder alle bot-berichten
- Robuuster: werkt automatisch voor alle message types (ook toekomstige)
- Zelfde gebruikerservaring, maar veel eenvoudiger code

**Test resultaten:** 669 tests passing ✅ (geen regressies)

### v2.1 - Celebration GIF Randomizer (2025-11-07)

**Celebration GIF Selectie met Gewogen Randomisatie:**
- Dynamische selectie uit 27 Tenor GIF URLs (`tenor-links.json`)
- Gewogen ratio: Nintendo URLs worden **3x vaker** gebruikt dan non-Nintendo URLs
- Eerlijke distributie: Selecteert URL met laagste `count` binnen de gekozen groep
- Automatische count incrementatie voor natuurlijke variatie per week
- Fallback naar lokale afbeelding (`resources/bedankt-puppies-kitties.jpg`) als Tenor faalt

**Hoe het werkt:**
1. Bereken gemiddelde counts voor Nintendo en non-Nintendo groepen
2. Als Nintendo avg ≤ (non-Nintendo avg × 3): Kies uit Nintendo pool
3. Anders: Kies uit non-Nintendo pool
4. Selecteer URL met laagste count uit de gekozen pool
5. Increment count en sla op naar `tenor-links.json`

**Bestanden:**
- `tenor-links.json`: 27 GIF URLs (16 Nintendo, 11 non-Nintendo) met count tracking
- `resources/bedankt-puppies-kitties.jpg`: Lokale fallback afbeelding
- `apps/utils/celebration_gif.py`: Gewogen selectie algoritme
- `tests/test_celebration_gif.py`: 8 tests voor algoritme en edge cases

**Test resultaten:** 669 tests passing ✅ (was 661, +8 nieuwe tests)

### v2.0 - Code refactoring & test coverage verbetering

**Command modularisatie** (PR #3):
- Grote `dmk_poll.py` (978 regels) opgesplitst in kleinere, gefocuste modules
- Betere onderhoudbaarheid en leesbaarheid
- Duidelijke scheiding van verantwoordelijkheden

**Test coverage uitbreiding**:
- Significant verbeterde code coverage
- Uitgebreide unittests voor robuuste codebase
- Uitgebreide tests voor exception handling en edge cases
- Tests voor alle nieuwe modules en functies
- Tests voor permissions en command defaults

**Scheduling feature**:
- Automatische activatie/deactivatie van polls op ingestelde tijden
- Per-kanaal configureerbaar via poll_settings.json
- Status zichtbaar in `/dmk-poll-status` commando
- Elke minuut controleert de scheduler of polls geactiveerd/gedeactiveerd moeten worden

**Notificatie-verbeteringen**:
- Display names in plaats van user mentions voor betere leesbaarheid
- Tijdelijke mentions (5 sec) voor herinneringen (16:00 voor niet-stemmers)
- Vroege herinnering op donderdag 20:00 voor wie nog helemaal niet gestemd heeft
- Persistente mentions (5 uur) voor "gaat door"-berichten
- Automatische cleanup: tijdelijke berichten na 1 uur, persistente na 5 uur
- Ping-opties in `/dmk-poll-notify`: kies tussen @everyone (iedereen), @here (alleen online), of stille notificaties (geen ping)

**UI verbeteringen**:
- Cleanup confirmation voor oude berichten
- Verbeterde Stem Nu button voor Misschien-bevestiging
- Betere foutafhandeling in alle UI componenten

**Code kwaliteit**:
- Safe API helpers voor robuuste Discord calls
- Betere exception handling in alle modules
- Type hints en docstrings voor alle functies
- Defensive programming principes toegepast

---

## 📄 Licentie

Deze bot is open source. Zie [LICENSE](LICENSE) voor details.

---

**Gemaakt met ❤️ voor de Deaf Mario Kart community.**

**DMK-poll-bot is ontwikkeld met hulp van [Claude](https://claude.com/claude-code), [Le Chat](https://chat.mistral.ai/chat) en [ChatGPT](https://chatgpt.com/).**

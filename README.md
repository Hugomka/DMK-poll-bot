# DMK-poll-bot 🇳🇱

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)
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
| **🗳️ Stemmen per dag** | Voor vrijdag, zaterdag en zondag elk een eigen poll met opties. |
| **✅ Aanpasbare pollopties** | Tijden/opties via `poll_options.json` (standaard 19:00, 20:30, misschien, niet meedoen). |
| **🔒 Veilige opslag** | Stemmen in `votes.json` met async lock, zodat alles stabiel en snel blijft. |
| **⏰ Automatische scheduler** | Nieuwe week op dinsdag 20:00, dag-updates om 18:00, herinneringen om 17:00, notificaties bij "gaat door". |
| **🏁 Automatische beslissing** | Op de dag zelf na de deadline: ≥6 stemmen nodig; bij gelijkstand wint **20:30**. |
| **📢 Slimme notificaties** | Herinneringen voor niet-stemmers, Misschien-bevestiging, en mentions bij doorgaan-berichten. |
| **👁️ Verborgen stemmen** | Tot de deadline (standaard 18:00) blijven aantallen verborgen in de kanaalberichten. |
| **🎟️ Gaststemmen** | Leden kunnen stemmen **voor gasten** toevoegen/verwijderen. |
| **💬 Slash commando's** | `/dmk-poll-on/reset/pauze/verwijderen/stemmen/status/notify`, archief downloaden/verwijderen, en gast-commando's. |
| **📊 Live status** | `/dmk-poll-status` toont per dag de aantallen en optioneel namen. |
| **🔄 Misschien-conversie** | Wie om 17:00 "misschien" heeft gestemd krijgt een bevestigingsknop; om 18:00 worden resterende "misschien"-stemmen automatisch omgezet naar "niet meedoen". |
| **🔔 Privacy-vriendelijke mentions** | Tijdelijke mentions (2 sec zichtbaar voor herinneringen), persistente mentions (tot 23:00 voor "gaat door"-berichten). |

---

## 💬 Overzicht van commando's

DMK-poll-bot werkt met **Slash commando's** (typ `/` in Discord).

| Commando | Uitleg |
|---|---|
| **`/dmk-poll-on`** *(default: admin/mod)* | Plaatst of vernieuwt de 3 dag-berichten, een openingsbericht met `@everyone`, de **🗳️ Stemmen**-knop en een notificatiebericht in het huidige kanaal. |
| **`/dmk-poll-reset`** *(default: admin/mod)* | Archiveren (CSV) + **alle stemmen wissen** → klaar voor nieuwe week. |
| **`/dmk-poll-pauze`** *(default: admin/mod)* | Pauzeer/hervat stemmen. Bij pauze is de Stemmen-knop uitgeschakeld. |
| **`/dmk-poll-verwijderen`** *(default: admin/mod)* | Sluit en verwijder alle poll-berichten in het kanaal en zet dit kanaal uit voor de scheduler. Polls komen hier niet meer terug, tenzij je later **/dmk-poll-on** gebruikt om het kanaal opnieuw te activeren. |
| **`/dmk-poll-stemmen`** *(default: admin/mod)* | Instelling per dag of alle dagen: **altijd zichtbaar** of **verborgen tot** `uu:mm` (standaard 18:00). |
| **`/dmk-poll-archief-download`** *(default: admin/mod)* | Download `archive/dmk_archive.csv` met weekresultaten. |
| **`/dmk-poll-archief-verwijderen`** *(default: admin/mod)* | Verwijder het volledige CSV-archief. |
| **`/dmk-poll-status`** *(default: admin/mod)* | Ephemeral embed: pauze/namen-status en per dag de aantallen met namen. |
| **`/dmk-poll-notify`** *(default: admin/mod)* | Stuur handmatig een notificatie. Zonder dag: algemene resetmelding. Met dag: notificatie voor niet-stemmers van die specifieke dag. |
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
/gast-add slot:"Zaterdag 19:00" namen:"Anna, Piet"
```

Je kunt meerdere namen scheiden met komma's of `;`. De bot meldt welke gasten zijn toegevoegd en welke al bestonden.

- **Gast verwijderen:**
Voorbeeld:
```
/gast-remove slot:"Zaterdag 19:00" namen:"Piet"
```
De bot meldt welke namen zijn verwijderd of niet gevonden.

**Hoe telt dit mee?** Elke gast telt als een **extra stem** op dat tijdstip, gekoppeld aan jouw account. In de openbare poll zie je alleen aantallen. In `/dmk-poll-status` worden stemmen gegroepeerd per eigenaar, bv.:
`@Johan (@Johan: Tim, Kim), @Piet`

---

## ⚙️ Poll-opties (config)

De stemopties staan in **`poll_options.json`**. Standaard:

```json
[
  { "dag": "vrijdag",  "tijd": "om 19:00 uur", "emoji": "🔴" },
  { "dag": "vrijdag",  "tijd": "om 20:30 uur", "emoji": "🟠" },
  { "dag": "vrijdag",  "tijd": "misschien",    "emoji": "Ⓜ️" },
  { "dag": "vrijdag",  "tijd": "niet meedoen", "emoji": "❌" },

  { "dag": "zaterdag", "tijd": "om 19:00 uur", "emoji": "🟡" },
  { "dag": "zaterdag", "tijd": "om 20:30 uur", "emoji": "⚪" },
  { "dag": "zaterdag", "tijd": "misschien",    "emoji": "Ⓜ️" },
  { "dag": "zaterdag", "tijd": "niet meedoen", "emoji": "❌" },

  { "dag": "zondag",   "tijd": "om 19:00 uur", "emoji": "🟢" },
  { "dag": "zondag",   "tijd": "om 20:30 uur", "emoji": "🔵" },
  { "dag": "zondag",   "tijd": "misschien",    "emoji": "Ⓜ️" },
  { "dag": "zondag",   "tijd": "niet meedoen", "emoji": "❌" }
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

## 🔧 Technische details

### Map-structuur

```
DMK-poll-bot/
├── apps/
│   ├── commands/           # Slash commando's (gemodulariseerd)
│   │   ├── dmk_poll.py             # Main entry point voor alle commando's
│   │   ├── poll_lifecycle.py       # Lifecycle commando's (on/reset/pauze/verwijderen)
│   │   ├── poll_votes.py           # Stemzichtbaarheid commando's
│   │   ├── poll_guests.py          # Gast-commando's (add/remove)
│   │   ├── poll_archive.py         # Archief commando's (download/verwijderen)
│   │   └── poll_status.py          # Status commando en notify
│   ├── ui/                 # Discord UI componenten
│   │   ├── poll_buttons.py           # Poll stemknoppen en views
│   │   ├── stem_nu_button.py         # "Stem Nu" knop voor Misschien-bevestiging
│   │   ├── archive_view.py           # Archief download view met verwijder-knop
│   │   └── cleanup_confirmation.py   # Cleanup confirmation view voor oude berichten
│   ├── utils/              # Hulpfuncties
│   │   ├── poll_storage.py        # Stem-opslag (votes.json)
│   │   ├── poll_settings.py       # Poll-instellingen (pauze, zichtbaarheid)
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
│   └── scheduler.py        # APScheduler taken (reset, herinneringen, notificaties)
├── tests/                  # Unittests (150+ tests, ~88% coverage)
│   ├── test_poll_lifecycle.py      # Tests voor lifecycle commando's
│   ├── test_poll_guests.py         # Tests voor gast-commando's
│   ├── test_poll_archive.py        # Tests voor archief commando's
│   ├── test_poll_votes.py          # Tests voor stemzichtbaarheid
│   ├── test_poll_message.py        # Tests voor bericht-opslag
│   ├── test_cleanup_confirmation.py # Tests voor cleanup UI
│   ├── test_mention_utils.py       # Tests voor mention utilities
│   ├── test_scheduler_*.py         # Tests voor scheduler functies
│   └── ...                          # Andere test modules
├── main.py                 # Bot entry point
├── poll_options.json       # Config van stemopties
├── opening_message.txt     # Aanpasbare openingstekst voor polls
├── requirements.txt        # Runtime dependencies
└── dev-requirements.txt    # Development dependencies (tests, linting)
```

### Belangrijke data-bestanden

| Bestand/map               | Doel                                                                             |
| ------------------------- | -------------------------------------------------------------------------------- |
| `poll_options.json`       | Config van opties (tijden/emoji's) per dag.                                      |
| `votes.json`              | Alle stemmen (per user/gast per dag). Async lock voor veilige I/O.               |
| `poll_settings.json`      | Kanaal-instellingen: pauze, zichtbaarheid (altijd/deadline), namen tonen.        |
| `poll_message.json`       | Opslag van bericht-ID's van de channel-polls (om te kunnen updaten/verwijderen). |
| `archive/dmk_archive.csv` | Wekelijks CSV-archief met weeknummer, datums en aantallen per optie/dag.         |
| `opening_message.txt`     | Aanpasbaar openingsbericht dat getoond wordt boven de polls.                     |
| `.scheduler_state.json`   | State van de scheduler (laatste uitvoering van jobs).                            |

### Archief

Bij resetten voor een nieuwe week voegt de bot 1 regel toe aan `dmk_archive.csv` met: weeknummer, datum vr/za/zo, en per dag de aantallen voor 19:00, 20:30, misschien, niet meedoen. Downloaden en wissen kan met de archief-commando's. Archief is **per guild en per kanaal** opgeslagen in `archive/{guild_id}/{channel_id}/dmk_archive.csv`.

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
| **Dinsdag 20:00** | Wekelijks | Reset polls | Stemmen leeg maken, archiveren, algemene resetmelding sturen |
| **17:00** | Vrijdag, Zaterdag, Zondag | Herinnering niet-stemmers | Mention sturen naar leden die nog niet gestemd hebben voor die dag (tijdelijk, 2 sec) |
| **17:05** | Vrijdag, Zaterdag, Zondag | Misschien-bevestiging | "Stem Nu" knop sturen naar Misschien-stemmers met leidende tijd |
| **18:00** | Dagelijks | Poll-update | Aantallen tonen, beslissingsregel toevoegen onder de poll |
| **18:00** | Vrijdag, Zaterdag, Zondag | Misschien-conversie | Resterende "misschien"-stemmen omzetten naar "niet meedoen" |
| **18:05** | Vrijdag, Zaterdag, Zondag | Doorgaan-notificatie | Mentions van stemmers op winnende tijd (≥6), bericht blijft tot 23:00 |
| **20:00** | Donderdag | Vroege herinnering | Mention naar leden die nog helemaal niet gestemd hebben (tijdelijk, 2 sec) |
| **23:00** | Automatisch | Mention cleanup | Verwijder mentions uit "gaat door"-berichten |

### Notificatiesysteem

De bot heeft een slim notificatiesysteem met privacy in gedachten:

1. **Tijdelijke mentions** (2 seconden zichtbaar):
   - Herinneringen voor niet-stemmers
   - Reset-meldingen (@everyone)
   - Gebruikers krijgen wel een notificatie op hun apparaat, maar de mention verdwijnt snel uit het kanaal

2. **Persistente mentions** (tot 23:00):
   - "Gaat door"-berichten voor deelnemers
   - Blijven zichtbaar tot 23:00, daarna worden mentions automatisch verwijderd
   - Dit zorgt ervoor dat deelnemers de hele dag kunnen zien wie er meedoet

3. **Misschien-bevestiging** (17:00-18:00):
   - Stemmers met "misschien" krijgen een "Stem Nu" knop
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

* **Download:** `/dmk-poll-archief-download` → bot uploadt `dmk_archive.csv` voor dit kanaal.
* **Verwijderen:** `/dmk-poll-archief-verwijderen` → wist het CSV-archief voor dit kanaal.
* Archief groeit met 1 regel per week (na reset).
* Archief is **per guild en per kanaal**, zodat meerdere Discord-servers of meerdere kanalen op dezelfde server hun eigen archief hebben.

---

## 🧪 Testen en dekking

De bot heeft **150+ unittests** met **~88% code coverage** voor uitgebreide dekking van alle functionaliteit.

Alle unittests draaien met:
```bash
python -m unittest discover -v
```

Dekking genereren:
```bash
coverage run -m unittest discover -v
coverage report
coverage xml
```

> De coverage-badge bovenaan werkt zodra de CI een `coverage.xml` heeft geüpload naar Codecov.

### Test-overzicht

De tests dekken onder andere:
- **Poll lifecycle** (on/reset/pauze/verwijderen commando's)
- **Poll-opslag** (stemmen toevoegen/verwijderen/resetten, exception handling)
- **Poll-settings** (pauze, zichtbaarheid, namen tonen)
- **Gast-commando's** (toevoegen, verwijderen, groepering, validatie)
- **Archief** (download, verwijderen, per guild/channel)
- **Message builder** (bericht-constructie met verborgen aantallen)
- **Beslissingslogica** (winnaar bepalen, gelijkstand, minimum stemmen)
- **Scheduler** (catch-up, reset venster, gemiste jobs, deadline mode)
- **UI components** (poll buttons, Stem Nu button, archief view, cleanup confirmation)
- **Notificaties** (tijdelijk, persistent, Misschien-flow, cleanup)
- **Mention utilities** (tijdelijke/persistente mentions, auto-delete, display names)
- **Discord client** (safe API calls met exception handling)

### Recente test-verbeteringen

De testdekking is recent significant verbeterd van ~59% naar ~88% door:
- Uitgebreide tests voor exception handling in alle modules
- Tests voor edge cases en error scenarios
- Tests voor scheduler deadline mode en Misschien-flow
- Tests voor cleanup confirmation en mention utilities
- Tests voor gemodulariseerde command structuur

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
- **Test coverage**: Verbeterd van 59% naar 88% met uitgebreide tests

### Nieuwe features toevoegen

1. Schrijf eerst tests in `tests/`
2. Implementeer de feature in de juiste module
3. Update de README met nieuwe functionaliteit
4. Test met `python -m unittest discover -v`
5. Check coverage met `coverage report` (streef naar >85%)

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

### v2.0 - Code refactoring & test coverage verbetering

**Command modularisatie** (PR #3):
- Grote `dmk_poll.py` (978 regels) opgesplitst in kleinere, gefocuste modules
- Betere onderhoudbaarheid en leesbaarheid
- Duidelijke scheiding van verantwoordelijkheden

**Test coverage uitbreiding**:
- Van 59% naar **88% code coverage**
- 150+ unittests voor robuuste codebase
- Uitgebreide tests voor exception handling en edge cases
- Tests voor alle nieuwe modules en functies

**Notificatie-verbeteringen**:
- Display names in plaats van user mentions voor betere leesbaarheid
- Tijdelijke mentions (2 sec) voor herinneringen
- Persistente mentions tot 23:00 voor "gaat door"-berichten
- Automatische cleanup van oude notificatieberichten

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

**Gemaakt met ❤️ voor de Deaf Mario Kart community**

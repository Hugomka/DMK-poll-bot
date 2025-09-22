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
Ook is er ondersteuning voor **gaststemmen** en een **CSV-archief** van resultaten. Kortom: een toegankelijke, gebruiksvriendelijke poll die past bij onze Discord-community 😊.

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
| **⏰ Automatische scheduler** | Nieuwe week op maandag, dag-updates om 18:00, notificaties bij “gaat door”. |
| **🏁 Automatische beslissing** | Op de dag zelf na de deadline: ≥6 stemmen nodig; bij gelijkstand wint **20:30**. |
| **📢 Notificaties naar stemmers** | Als een avond doorgaat, mentiont de bot alle stemmers van het winnende tijdstip. |
| **👁️ Verborgen stemmen** | Tot de deadline (standaard 18:00) blijven aantallen verborgen in de kanaalberichten. |
| **🎟️ Gaststemmen** | Leden kunnen stemmen **voor gasten** toevoegen/verwijderen. |
| **💬 Slash commando's** | `/dmk-poll on/reset/pauze/verwijderen/stemmen/status`, archief downloaden/verwijderen, en gast-commando's. |
| **📊 Live status** | `/dmk-poll-status` toont per dag de aantallen en optioneel namen. |

---

## 💬 Overzicht van commando's

DMK-poll-bot werkt met **Slash commando's** (typ `/` in Discord).

| Commando | Uitleg |
|---|---|
| **`/dmk-poll-on`** *(default: admin/mod)* | Plaatst of vernieuwt de 3 dag-berichten en een 4e bericht met de **🗳️ Stemmen**-knop in het huidige kanaal. |
| **`/dmk-poll-reset`** *(default: admin/mod)* | Archiveren (CSV) + **alle stemmen wissen** → klaar voor nieuwe week. Namen-uit standaard. |
| **`/dmk-poll-pauze`** *(default: admin/mod)* | Pauzeer/hervat stemmen. Bij pauze is de Stemmen-knop uitgeschakeld. |
| **`/dmk-poll-verwijderen`** *(default: admin/mod)* | Sluit en verwijder alle poll-berichten in het kanaal en zet dit kanaal uit voor de scheduler. Polls komen hier niet meer terug, tenzij je later **/dmk-poll-on** gebruikt om het kanaal opnieuw te activeren. |
| **`/dmk-poll-stemmen`** *(default: admin/mod)* | Instelling per dag of alle dagen: **altijd zichtbaar** of **verborgen tot** `uu:mm` (standaard 18:00). |
| **`/dmk-poll-archief-download`** *(default: admin/mod)* | Download `archive/dmk_archive.csv` met weekresultaten. |
| **`/dmk-poll-archief-verwijderen`** *(default: admin/mod)* | Verwijder het volledige CSV-archief. |
| **`/dmk-poll-status`** *(default: admin/mod)* | Ephemeral embed: pauze/namen-status en per dag de aantallen met namen. |
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
```/gast-add slot:"Zaterdag 19:00" namen:"Anna, Piet"```

Je kunt meerdere namen scheiden met komma's of `;`. De bot meldt welke gasten zijn toegevoegd en welke al bestonden.

- **Gast verwijderen:**  
Voorbeeld:  
```/gast-remove slot:"Zaterdag 19:00" namen:"Piet"```
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

**Map-structuur**

* `apps/commands/` – Slash commando's (o.a. `dmk_poll.py`).
* `apps/ui/` – Discord UI: knoppen en views (bv. stemmen, naam-toggle, archief-knop).
* `apps/utils/` – Opslag (`poll_storage.py`, `poll_settings.py`), berichtenbouw (`message_builder.py`), scheduler (`scheduler.py`), archief (`archive.py`).
* `main.py` – Start de bot, registreert scheduler en commando's.

**Belangrijke data-bestanden**

| Bestand/map               | Doel                                                                             |
| ------------------------- | -------------------------------------------------------------------------------- |
| `poll_options.json`       | Config van opties (tijden/emoji's) per dag.                                      |
| `votes.json`              | Alle stemmen (per user/gast per dag). Async lock voor veilige I/O.               |
| `poll_settings.json`      | Kanaal-instellingen: pauze, zichtbaarheid (altijd/deadline), namen tonen.        |
| `poll_message.json`       | Opslag van bericht-ID's van de channel-polls (om te kunnen updaten/verwijderen). |
| `archive/dmk_archive.csv` | Wekelijks CSV-archief met weeknummer, datums en aantallen per optie/dag.         |

**Archief**
Bij resetten voor een nieuwe week voegt de bot 1 regel toe aan `dmk_archive.csv` met: weeknummer, datum vr/za/zo, en per dag de aantallen voor 19:00, 20:30, misschien, niet meedoen. Downloaden en wissen kan met de archief-commando's.

**Beslissingsregels**

* Beslissing alleen op de **dag zelf** na de **deadline**.
* **Minimaal 6 stemmen** nodig.
* **Gelijk aantal? → 20:30 wint.**
* Anders wint het tijdstip met de meeste stemmen.
* Te weinig stemmen? → “Gaat niet door.”

**Tijdzone**
Alle tijden zijn in **Europe/Amsterdam** (CET/CEST).

---

## ⏰ Automatisering (scheduler)

* **Maandag 00:00** – Nieuwe week: stemmen leeg + (optioneel) nieuwe poll klaarzetten.
* **Vrij/Za/Zo 18:00** –

  * Aantallen in kanaal tonen (voorheen verborgen).
  * Beslissingsregel toevoegen onder de poll.
  * **Notificatie** sturen met mentions van stemmers op de winnende tijd (alleen bij ≥6).
* Archiveren gebeurt automatisch bij het resetmoment/nieuwe week.

De bot moet blijven draaien om deze taken uit te voeren (resourceverbruik is laag).

---

## 📊 Status & archief

**Status bekijken** (`/dmk-poll-status`)

* Ephemeral bericht (alleen jij ziet het).
* Toont pauze-/namen-status en per dag de aantallen.
* Namen kunnen ook getoond worden (gegroepeerd met gasten), afhankelijk van je instelling.

**Archief**

* **Download:** `/dmk-poll-archief-download` → bot uploadt `dmk_archive.csv`.
* **Verwijderen:** `/dmk-poll-archief-verwijderen` → wist het CSV-archief.
* Archief groeit met 1 regel per week (na reset).

---

## 🧪 Testen en dekking

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

> De coverage‑badge bovenaan werkt zodra de CI een `coverage.xml` heeft geüpload naar Codecov.

---

## 📁 Technische details

(dit deel blijft zoals in je oorspronkelijke README – mapstructuur, archief, beslissingsregels, tijdzone, enz.)

---

## 🔮 Toekomst / tips

* Extra dagen of andere tijden? Pas `poll_options.json` aan (let op archieflogica).
* Mogelijke uitbreiding: reminders sturen naar niet-stemmers.
* De bot is op maat voor DMK, maar kan met kleine aanpassingen ook elders gebruikt worden.
* Feedback/ideeën zijn welkom. Veel race-plezier! 🎮🏁
import datetime
import json
import os


SETTINGS_FILE = "poll_settings.json"

DAYS_INDEX = {
    "maandag": 0,
    "dinsdag": 1,
    "woensdag": 2,
    "donderdag": 3,
    "vrijdag": 4,
    "zaterdag": 5,
    "zondag": 6,
}

def _load_data():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                pass
    return {}

def _save_data(data):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def get_setting(channel_id: int, dag: str):
    """Geef de instelling voor zichtbaarheid en tijdstip terug.
       Standaard: {'modus': 'altijd', 'tijd': '18:00'}."""
    data = _load_data()
    return (
        data.get(str(channel_id), {})
            .get(dag, {'modus': 'altijd', 'tijd': '18:00'})
    )

def toggle_visibility(channel_id: int, dag: str, tijd: str = '18:00'):
    """Schakel tussen 'altijd' en 'deadline'. Bij omschakeling naar 'deadline'
       wordt het tijdstip opgeslagen."""
    data = _load_data()
    kanaal = data.setdefault(str(channel_id), {})
    instelling = kanaal.get(dag, {'modus': 'altijd', 'tijd': '18:00'})
    if instelling['modus'] == 'altijd':
        instelling = {'modus': 'deadline', 'tijd': tijd}
    else:
        instelling = {'modus': 'altijd', 'tijd': '18:00'}
    kanaal[dag] = instelling
    _save_data(data)
    return instelling

def should_hide_counts(channel_id: int, dag: str, now: datetime.datetime) -> bool:
    instelling = get_setting(channel_id, dag)
    if instelling["modus"] == "altijd":
        return False

    tijd_str = instelling.get("tijd", "18:00")
    try:
        uur, minuut = map(int, tijd_str.split(":"))
    except ValueError:
        uur, minuut = 18, 0

    # bepaal de eerstvolgende datum voor de gevraagde dag
    target_idx = DAYS_INDEX.get(dag, None)
    if target_idx is None:
        return False  # onbekende dag

    huidige_idx = now.weekday()
    delta_dagen = (target_idx - huidige_idx) % 7
    # als het vandaag al die dag is maar we zijn vóór de deadline, dan delta_dagen = 0 is prima
    # anders springt het naar de volgende week

    deadline_datum = now.date() + datetime.timedelta(days=delta_dagen)
    deadline_dt = datetime.datetime.combine(
        deadline_datum,
        datetime.time(uur, minuut),
        tzinfo=now.tzinfo,
    )

    # verberg tot de deadline is bereikt
    return now < deadline_dt

# apps/utils/constants.py
#
# Centrale constanten voor DMK-poll-bot
# DRY principe: definieer constanten op één plek

# Weekdag namen in Nederlandse volgorde (maandag = 0, zondag = 6)
DAG_NAMEN = [
    "maandag",
    "dinsdag",
    "woensdag",
    "donderdag",
    "vrijdag",
    "zaterdag",
    "zondag",
]

# Mapping van dag namen naar weekday indices (0 = maandag, 6 = zondag)
DAG_MAPPING = {
    "maandag": 0,
    "dinsdag": 1,
    "woensdag": 2,
    "donderdag": 3,
    "vrijdag": 4,
    "zaterdag": 5,
    "zondag": 6,
}

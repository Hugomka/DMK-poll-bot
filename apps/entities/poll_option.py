from discord import ButtonStyle

class PollOption:
    def __init__(self, id, dag, tijd, emoji, stijl=ButtonStyle.secondary):
        self.id = id
        self.dag = dag
        self.tijd = tijd
        self.emoji = emoji
        self.stijl = stijl
        self.label = f"{emoji} {dag.capitalize()} {tijd}"

POLL_OPTIONS = [
    PollOption("vrijdag_1900", "vrijdag", "om 19:00 uur", "🔴"),
    PollOption("vrijdag_2030", "vrijdag", "om 20:30 uur", "🟠"),
    PollOption("zaterdag_1900", "zaterdag", "om 19:00 uur", "🟡"),
    PollOption("zaterdag_2030", "zaterdag", "om 20:30 uur", "⚪"),
    PollOption("zondag_1900", "zondag", "om 19:00 uur", "🟢"),
    PollOption("zondag_2030", "zondag", "om 20:30 uur", "🔵"),
    PollOption("misschien", "misschien", "", "Ⓜ️"),
    PollOption("niet_meedoen", "niet meedoen", "", "❌"),
]

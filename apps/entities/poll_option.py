from discord import ButtonStyle

class PollOption:
    def __init__(self, id, dag, tijd, emoji, stijl=ButtonStyle.primary):
        self.id = id
        self.dag = dag
        self.tijd = tijd
        self.emoji = emoji
        self.stijl = stijl
        self.tekst = f"{emoji} {dag.capitalize()} {tijd} uur"

POLL_OPTIONS = [
    PollOption("vrijdag_1900", "vrijdag", "19:00", "🔴"),
    PollOption("vrijdag_2030", "vrijdag", "20:30", "🟠"),
    PollOption("zaterdag_1900", "zaterdag", "19:00", "🟡"),
    PollOption("zaterdag_2030", "zaterdag", "20:30", "⚪"),
    PollOption("zondag_1900", "zondag", "19:00", "🟢"),
    PollOption("zondag_2030", "zondag", "20:30", "🔵"),
    PollOption("misschien", "misschien", "19:00", "Ⓜ️", ButtonStyle.secondary),
    PollOption("niet", "niet", "20:30", "❌", ButtonStyle.danger),
]

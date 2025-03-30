from apps.utils.poll_storage import get_votes_for_option

def build_poll_message():
    dagen = ["vrijdag", "zaterdag", "zondag"]
    tijden = ["19:00", "20:30"]
    message = "**DMK-poll deze week**\n\n"

    for dag in dagen:
        count_19 = get_votes_for_option(dag, "19:00")
        count_20 = get_votes_for_option(dag, "20:30")

        doorgaat = None
        if count_19 >= 6 or count_20 >= 6:
            # Bepaal welke tijd doorgaat
            if count_20 >= count_19:
                doorgaat = "20:30"
            else:
                doorgaat = "19:00"

        message += f"📅 {dag.capitalize()}:\n"
        for tijd in tijden:
            count = get_votes_for_option(dag, tijd)
            markering = " → Gaat door!" if tijd == doorgaat else ""
            if (tijd == "19:00"):
                message += f"🕖 19:00 uur ({count} stemmen){markering}\n"
            else:
                message += f"🕤 20:30 uur ({count} stemmen){markering}\n"
        message += "\n"
    message += f"\nⓂ️ Misschien ({get_votes_for_option("misschien", "misschien")} stemmen)"
    message += f"\n❌ Niet meedoen ({get_votes_for_option("niet", "niet")} stemmen)"
    message += f"\n "

    return message

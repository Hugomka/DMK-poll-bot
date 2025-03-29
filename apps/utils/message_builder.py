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

        message += f"{dag.capitalize()}:\n"
        for tijd in tijden:
            count = get_votes_for_option(dag, tijd)
            markering = " → Gaat door!" if tijd == doorgaat else ""
            message += f"- {tijd} uur ({count} stemmen){markering}\n"
        message += "\n"

    return message

async def update_poll_message(self, channel):
    from apps.utils.poll_message import get_message_id
    message_id = get_message_id(channel.id)
    if not message_id:
        return

    try:
        message = await channel.fetch_message(message_id)
        content = build_poll_message()
        await message.edit(content=content)
    except:
        pass
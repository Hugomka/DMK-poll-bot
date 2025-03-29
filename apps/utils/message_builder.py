def build_poll_message():
    dt = datetime.now(pytz.timezone("Europe/Amsterdam"))
    dagen = ["vrijdag", "zaterdag", "zondag"]
    tijden = ["19:00", "20:30"]
    message = "**DMK-poll deze week**\n\n"
    for dag in dagen:
        message += f"{dag.capitalize()}:\n"
        for tijd in tijden:
            count = get_votes_for_option(dag, tijd)
            message += f"- {tijd} uur ({count} stemmen)\n"
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
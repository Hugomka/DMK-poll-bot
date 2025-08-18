# apps/utils/message_builder.py

import discord
from apps.entities.poll_option import get_poll_options
from apps.utils.poll_storage import get_counts_for_day, load_votes
from apps.utils.poll_settings import is_name_display_enabled

async def build_poll_message_for_day_async(
    dag: str,
    hide_counts: bool = False,
    pauze: bool = False,
    guild: discord.Guild | None = None
) -> str:
    title = f"**DMK-poll voor {dag.capitalize()}**"
    if pauze:
        title += " **- _(Gepauzeerd)_**"
    message = f"{title}\n\n"

    opties = [o for o in get_poll_options() if o.dag == dag]

    if not opties:
        message += "_(geen opties gevonden)_"
        return message

    counts = {} if hide_counts else await get_counts_for_day(dag)
    toon_namen = guild and is_name_display_enabled(guild.id)

    if toon_namen:
        alle_votes = await load_votes()

    for option in opties:
        if hide_counts:
            message += f"{option.label} (stemmen verborgen)\n"
        else:
            n = counts.get(option.tijd, 0)
            regel = f"{option.label} ({n} stemmen)"
            
            if toon_namen and n > 0:
                stemmers = []
                for user_id, dag_votes in alle_votes.items():
                    if option.tijd in dag_votes.get(dag, []):
                        member = guild.get_member(int(user_id))
                        if member is None and guild is not None:
                            try:
                                member = await guild.fetch_member(int(user_id))
                            except discord.NotFound:
                                member = None
                        if member:
                            stemmers.append(member.mention)
                if stemmers:
                    regel += f": {', '.join(stemmers)}"
            
            message += regel + "\n"

    return message

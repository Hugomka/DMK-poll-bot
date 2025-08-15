# apps/utils/message_builder.py

from apps.entities.poll_option import get_poll_options
from apps.utils.poll_storage import get_counts_for_day

async def build_poll_message_for_day_async(dag: str, hide_counts: bool = False, pauze: bool = False) -> str:
    title = f"**DMK-poll voor {dag.capitalize()}**"
    if pauze:
        title += " **- _(Gepauzeerd)_**"
    message = f"{title}\n\n"

    counts = {} if hide_counts else await get_counts_for_day(dag)

    for option in get_poll_options():
        if option.dag != dag:
            continue
        if hide_counts:
            message += f"{option.label} (stemmen verborgen)\n"
        else:
            n = counts.get(option.tijd, 0)
            message += f"{option.label} ({n} stemmen)\n"
    return message

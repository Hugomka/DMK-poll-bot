from apps.entities.poll_option import POLL_OPTIONS
from apps.utils.poll_storage import get_votes_for_option

def build_poll_message_for_day(dag, hide_counts=False, pauze=False):
    title = f"**DMK‑poll voor {dag.capitalize()}**"
    if pauze:
        title += " **- _(Gepauzeerd)_**"
    message = f"{title}\n\n"
    for option in POLL_OPTIONS:
        if option.dag != dag:
            continue
        if hide_counts:
            message += f"{option.label} (stemmen verborgen)\n"
        else:
            stemmen = get_votes_for_option(dag, option.tijd)
            message += f"{option.label} ({stemmen} stemmen)\n"
    return message

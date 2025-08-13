from apps.entities.poll_option import POLL_OPTIONS
from apps.utils.poll_storage import get_votes_for_option

def build_poll_message_for_day(dag, pauze=False):
    title = f"**DMK‑poll voor {dag.capitalize()}**"
    if pauze:
        title += " **- _(Gepauzeerd)_**"
    message = f"{title}\n\n"
    for option in POLL_OPTIONS:
        # Opties voor deze dag, de algemene 'niet_meedoen' of de juiste 'misschien_*'
        if not (
            option.dag == dag
            or option.id == "niet_meedoen"
            or (option.id.startswith("misschien") and option.id.endswith(dag))
        ):
            continue
        stemmen = get_votes_for_option(dag, option.tijd)
        message += f"{option.label} ({stemmen} stemmen)\n"
    return message

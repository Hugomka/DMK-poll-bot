from apps.utils.poll_storage import get_votes_for_option
from apps.entities.poll_option import POLL_OPTIONS

def build_poll_message():
    message = "**DMK-poll deze week**\n\n"

    # Doorloop alle opties in POLL_OPTIONS
    for option in POLL_OPTIONS:
        stemmen = get_votes_for_option(option.dag, option.tijd)
        message += f"{option.label} ({stemmen} stemmen)\n"
    return message

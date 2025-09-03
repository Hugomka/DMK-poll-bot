# apps/utils/discord_client.py

from __future__ import annotations

from typing import Any, Awaitable, Callable, Iterable, TypeVar

T = TypeVar("T")


def get_guilds(bot: Any) -> Iterable[Any]:
    """
    Geeft de guilds van een bot terug.
    Werkt met echte discord.Client, maar ook met FakeBot in tests (duck-typing).
    """
    return getattr(bot, "guilds", []) or []


def get_channels(guild: Any) -> Iterable[Any]:
    """
    Geef tekstkanalen terug. Duck-typed:
    - Als channel.type == 'text' (Fake) of hasattr(channel, 'send') (discord.TextChannel) → meenemen.
    """
    channels = getattr(guild, "channels", []) or []
    result = []
    for ch in channels:
        ch_type = getattr(ch, "type", None)
        if ch_type == "text" or hasattr(ch, "send"):
            result.append(ch)
    return result


async def safe_call(
    func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any
) -> T | None:
    """
    Roept een async Discord-call veilig aan; geeft None bij NotFound/Forbidden.
    """
    try:
        return await func(*args, **kwargs)
    except Exception:
        # Bewust stil zijn; hoger niveau logt vaak al.
        return None

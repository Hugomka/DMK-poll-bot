# apps/utils/discord_client.py

import asyncio, random, time
from typing import Callable, Any, Dict
import discord

_CACHE_TTL_SECONDS = 300  # 5 minuten
_guild_cache: Dict[str, Any] = {}
_channel_cache: Dict[int, Any] = {}

async def safe_call(func, *args, retries=3, base_delay=0.5, jitter=0.1, **kwargs):
    """
    Roep een async func aan met retries. Ondersteunt zowel args als kwargs.
    Retries bij HTTP 429 of netwerkfouten (TimeoutError/OSError).
    """
    attempt = 0
    while True:
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            status = getattr(e, "status", None)
            # 429 of netwerkfouten: retry met exponentiële backoff + jitter
            if status == 429 or isinstance(e, (OSError, TimeoutError)):
                attempt += 1
                if attempt > retries:
                    raise
                delay = base_delay * (2 ** (attempt - 1))
                if jitter:
                    delay += random.uniform(0, jitter)
                await asyncio.sleep(delay)
            else:
                raise

def get_guilds(bot: discord.Client):
    """Cache de lijst van guilds (servers) zodat we niet telkens bot.guilds hoeven te lopen."""
    now = time.time()
    entry = _guild_cache.get("guilds")
    if entry is None or (now - entry["time"]) > _CACHE_TTL_SECONDS:
        _guild_cache["guilds"] = {"time": now, "value": list(bot.guilds)}
    return _guild_cache["guilds"]["value"]

def get_channels(guild: discord.Guild):
    """Cache de tekstkanalen per guild."""
    now = time.time()
    entry = _channel_cache.get(guild.id)
    if entry is None or (now - entry["time"]) > _CACHE_TTL_SECONDS:
        _channel_cache[guild.id] = {"time": now, "value": list(guild.text_channels)}
    return _channel_cache[guild.id]["value"]

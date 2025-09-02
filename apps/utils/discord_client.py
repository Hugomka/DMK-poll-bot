# apps/utils/discord_client.py

import asyncio, random, time
from typing import Callable, Any, Dict
import discord

_CACHE_TTL_SECONDS = 300  # 5 minuten
_guild_cache: Dict[str, Any] = {}
_channel_cache: Dict[int, Any] = {}

async def safe_call(func: Callable, *args, retries: int = 5, base_delay: float = 1.0, jitter: float = 0.3):
    """
    Roep een Discord‑API functie aan met exponential backoff bij 429 (rate limit) of netwerkfouten.
    """
    delay = base_delay
    for _ in range(retries):
        try:
            return await func(*args)
        except discord.HTTPException as e:
            if e.status == 429:
                await asyncio.sleep(delay + random.uniform(0, jitter))
                delay *= 2
                continue
            raise
        except Exception:
            await asyncio.sleep(delay + random.uniform(0, jitter))
            delay *= 2
            continue
    raise Exception("safe_call: maximum retries exceeded")

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

# apps/utils/discord_client.py
from __future__ import annotations

import asyncio
import random
import time
from typing import Any, Awaitable, Callable, Iterable, Optional, TypeVar, cast

try:
    import discord  # type: ignore

    HTTPExc = discord.HTTPException  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - tests use fakes / no discord
    discord = None  # type: ignore

    class HTTPExc(Exception):
        status: Optional[int] = None
        code: Optional[int] = None
        retry_after: Optional[float] = None


T = TypeVar("T")

# ----------
# Caching (with simple TTL so tests can simulate refresh by patching time.time)
# ----------

_GUILDS_CACHE: Optional[list[Any]] = None
_GUILDS_TS: float | None = None

_CHANNELS_CACHE: dict[int, list[Any]] = {}
_CHANNELS_TS: dict[int, float] = {}
_CHANNELS_FP: dict[int, tuple[int, int]] = (
    {}
)  # fingerprint of source container id & len

# 5 minuten TTL: tests gebruiken 100.0 -> 500.0 om vervallen te simuleren
_TTL_SECONDS = 300.0


def clear_client_caches() -> None:
    """Maak alle caches leeg (handig in tests)."""
    global _GUILDS_CACHE, _GUILDS_TS, _CHANNELS_CACHE, _CHANNELS_TS, _CHANNELS_FP
    _GUILDS_CACHE = None
    _GUILDS_TS = None
    _CHANNELS_CACHE = {}
    _CHANNELS_TS = {}
    _CHANNELS_FP = {}


def _now() -> float:
    # Losse helper zodat tests time.time kunnen patchen
    return time.time()


def get_guilds(bot: Any) -> list[Any]:
    """
    Haal guilds met een TTL-cache.
    Geeft dezelfde objecten terug (geen wrappers/kopieën) in de list.
    """
    global _GUILDS_CACHE, _GUILDS_TS
    if _GUILDS_CACHE is not None and _GUILDS_TS is not None:
        if (_now() - _GUILDS_TS) <= _TTL_SECONDS:
            return _GUILDS_CACHE

    guilds_raw = getattr(bot, "guilds", None)
    iterable: Iterable[Any] = cast(Iterable[Any], guilds_raw or [])
    _GUILDS_CACHE = list(iterable)
    _GUILDS_TS = _now()
    return _GUILDS_CACHE


def get_channels(guild: Any) -> list[Any]:
    """
    Haal kanalen met per-guild TTL-cache.
    Returned exact dezelfde channel-objecten als op de guild (geen kopieën).
    De list-container wordt vernieuwd als de bronlijst verandert of TTL verloopt.
    """
    gid = getattr(guild, "id", None)

    # Vind lijst met text channels (val terug op 'channels' indien aanwezig)
    chans_raw = (
        getattr(guild, "text_channels", None) or getattr(guild, "channels", None) or []
    )
    iterable: Iterable[Any] = cast(Iterable[Any], chans_raw)
    cur_list = list(iterable)

    # Fingerprint: (id van broncontainer, lengte)
    fp: tuple[int, int] = (id(chans_raw), len(cur_list))

    if isinstance(gid, int) and gid in _CHANNELS_CACHE:
        ts = _CHANNELS_TS.get(gid, 0.0)
        same_fp = _CHANNELS_FP.get(gid) == fp
        fresh = (_now() - ts) <= _TTL_SECONDS
        if same_fp and fresh:
            return _CHANNELS_CACHE[gid]

    # TTL verlopen of bron veranderd → nieuwe list container opslaan
    if isinstance(gid, int):
        _CHANNELS_CACHE[gid] = cur_list
        _CHANNELS_TS[gid] = _now()
        _CHANNELS_FP[gid] = fp

    return cur_list


# ----------
# safe_call
# ----------


async def _maybe_await(value: Any) -> Any:
    """Await op Awaitables/coroutines, anders return direct."""
    if asyncio.iscoroutine(value) or isinstance(value, Awaitable):
        return await value  # type: ignore[misc]
    return value


async def safe_call(
    func: Callable[..., Any],
    *args: Any,
    retries: int = 3,
    base_delay: float = 0.25,
    jitter: float = 0.25,
    **call_kwargs: Any,
) -> Any:
    """
    Voer een (a)sync call uit met retry op 429/ratelimit & transient fouten.
    Let op: 'retries', 'base_delay', 'jitter' gaan NIET door naar func().
    """
    attempt = 0

    def _compute_delay(exp_attempt: int, retry_after: float | None) -> float:
        if retry_after is not None:
            return float(retry_after)
        # Exponentieel met jitter
        base = max(0.0, base_delay)
        j = random.uniform(0.0, max(0.0, jitter))
        return base * (2**exp_attempt) + j

    while True:
        try:
            return await _maybe_await(func(*args, **call_kwargs))
        except HTTPExc as e:
            status = getattr(e, "status", None)
            code = getattr(e, "code", None)
            retry_after = getattr(e, "retry_after", None)
            transient = status in (429, 500, 502, 503, 504) or code in (110000, 200000)
            if not transient or attempt >= retries:
                raise
            delay = _compute_delay(attempt, retry_after)
            if delay > 0:
                await asyncio.sleep(delay)
            attempt += 1
        except (OSError, asyncio.TimeoutError):
            if attempt >= retries:
                raise
            delay = _compute_delay(attempt, None)
            if delay > 0:
                await asyncio.sleep(delay)
            attempt += 1
        except Exception as e:
            # Ondersteun test-FakeHTTPException met attribuut 'status'
            status = getattr(e, "status", None)
            retry_after = getattr(e, "retry_after", None)
            if status in (429, 500, 502, 503, 504):
                if attempt >= retries:
                    raise
                delay = _compute_delay(attempt, retry_after)
                if delay > 0:
                    await asyncio.sleep(delay)
                attempt += 1
                continue
            raise

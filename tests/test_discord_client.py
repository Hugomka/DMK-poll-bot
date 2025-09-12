# tests/test_discord_client.py

from unittest.mock import patch

from apps.utils.discord_client import get_channels, get_guilds, safe_call
from tests.base import BaseTestCase


class FakeHTTPException(Exception):
    """Simuleer een HTTP-exception met een statuscode, bv. 429."""

    def __init__(self, status):
        super().__init__(f"http {status}")
        self.status = status


async def _fails_twice_then_ok(counter: dict):
    """
    Eerste 2 keer: raise 429 -> triggert retry in safe_call.
    Daarna: return 'OK'.
    """
    c = counter.get("n", 0)
    if c < 2:
        counter["n"] = c + 1
        raise FakeHTTPException(429)
    return "OK"


class TestDiscordClient(BaseTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()

    async def test_safe_call_retries_on_429_without_sleep_waits(self):
        # Voorkom echte vertraging in tests
        async def fast_sleep(_):
            return None

        with patch("asyncio.sleep", new=fast_sleep):
            counter = {"n": 0}

            # base_delay=0 en jitter=0: direct opnieuw proberen
            res = await safe_call(
                lambda: _fails_twice_then_ok(counter), retries=5, base_delay=0, jitter=0
            )

            assert res == "OK"
            assert counter["n"] == 2  # Precies 2 keer gefaald -> 2 retries gedaan

    def test_get_guilds_and_channels_cache(self):
        class FakeGuild:
            def __init__(self, gid, chans):
                self.id = gid
                self.text_channels = chans

        class FakeBot:
            def __init__(self, guilds):
                self.guilds = guilds

        # Simuleer tijd:
        # - eerst 100.0s (cache vullen)
        # - nogmaals 100.0s (cache hit)
        # - later 500.0s (TTL verlopen -> cache miss)
        current = {"t": 100.0}

        def fake_time():
            return current["t"]

        with patch("time.time", new=fake_time):
            g1 = FakeGuild(1, ["c1"])
            bot = FakeBot([g1])

            # Eerste call -> cache fill
            v1 = get_guilds(bot)
            v1_id = id(v1)
            ch1 = get_channels(g1)
            ch1_id = id(ch1)

            # Zelfde tijd -> cache hit (object-id blijft gelijk)
            v2 = get_guilds(bot)
            ch2 = get_channels(g1)
            assert id(v2) == v1_id
            assert id(ch2) == ch1_id

            # TTL laten verlopen
            current["t"] = 500.0

            v3 = get_guilds(bot)
            ch3 = get_channels(g1)
            assert id(v3) != v1_id  # Nieuw gecachte lijst
            assert id(ch3) != ch1_id  # Nieuw gecachte kanalen

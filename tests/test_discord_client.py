# tests/test_discord_client.py

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from apps.utils import discord_client as dc
from tests.base import BaseTestCase


class TestDiscordClient(BaseTestCase):
    # -----------------------------
    # safe_call: 429 zonder retry_after → retry zonder sleep
    # -----------------------------
    async def test_safe_call_retries_on_429_without_sleep_waits(self):
        """
        429 zonder retry_after → directe retries (base_delay=0, jitter=0) en daarna succes.
        We mocken asyncio.sleep zodat er sowieso niet echt gewacht wordt.
        """

        # Lokale exception met alleen 'status' (429) en zonder 'retry_after'
        class _E(Exception):
            def __init__(self):
                super().__init__("rate limited")
                self.status = 429
                self.retry_after = None

        # Tel alleen het aantal falingen (zoals de oude helper deed)
        fails = {"n": 0}

        def flaky():
            # Faalt precies 2 keer met 429, daarna "OK"
            if fails["n"] < 2:
                fails["n"] += 1
                raise _E()
            return "OK"

        async def fast_sleep(_):
            # Geen echte vertraging in tests
            return None

        # Patch HTTPExc naar onze lokale _E en voorkom echte sleeps
        with patch.object(dc, "HTTPExc", _E), patch("asyncio.sleep", new=fast_sleep):
            res = await dc.safe_call(flaky, retries=5, base_delay=0, jitter=0)
            assert res == "OK"
            assert fails["n"] == 2  # Precies 2 keer gefaald → 2 retries uitgevoerd

    # -----------------------------
    # Caching: get_guilds
    # -----------------------------
    async def test_get_guilds_cache_and_ttl(self):
        dc.clear_client_caches()

        bot = SimpleNamespace()
        g1 = SimpleNamespace(id=1)
        g2 = SimpleNamespace(id=2)
        bot.guilds = [g1, g2]

        # Starttijd vastzetten
        with patch.object(dc, "_TTL_SECONDS", 300.0), patch.object(
            dc, "time", wraps=dc.time
        ) as tmod:
            # t0
            tmod.time.return_value = 100.0
            first = dc.get_guilds(bot)
            assert first == [g1, g2]

            # Binnen TTL: cache hit (geen nieuwe list)
            tmod.time.return_value = 200.0
            second = dc.get_guilds(bot)
            assert second is first  # exact dezelfde list-container

            # Na TTL: refresh (nieuwe container, huidige bot.guilds)
            bot.guilds = [g1]  # verander bron
            tmod.time.return_value = 100.0 + 301.0
            third = dc.get_guilds(bot)
            assert third == [g1]
            assert third is not first

    # -----------------------------
    # Caching: get_channels
    # -----------------------------
    async def test_get_channels_cache_ttl_and_fingerprint(self):
        dc.clear_client_caches()

        # Guild mock met text_channels
        ch1 = SimpleNamespace(id=11)
        ch2 = SimpleNamespace(id=12)
        chans = [ch1, ch2]

        guild = SimpleNamespace(id=123, text_channels=chans)

        with patch.object(dc, "_TTL_SECONDS", 300.0), patch.object(
            dc, "time", wraps=dc.time
        ) as tmod:
            # t0
            tmod.time.return_value = 100.0
            first = dc.get_channels(guild)
            assert first == [ch1, ch2]
            # Container wordt gecached
            assert dc._CHANNELS_CACHE[guild.id] is first

            # Binnen TTL + zelfde fingerprint: cache hit (zelfde container)
            tmod.time.return_value = 200.0
            second = dc.get_channels(guild)
            assert second is first

            # Bronlijst verandert → fingerprint anders → nieuwe container
            guild.text_channels = [ch1]
            tmod.time.return_value = 210.0
            third = dc.get_channels(guild)
            assert third == [ch1]
            assert third is not first

            # TTL verlopen → ook refresh (zelfs als fingerprint gelijk blijft)
            # maak fingerprint weer gelijk: zelfde object + zelfde lengte
            guild.text_channels = [ch1]
            tmod.time.return_value = 100.0 + 301.0
            fourth = dc.get_channels(guild)
            assert fourth == [ch1]
            assert fourth is not third

    # -----------------------------
    # safe_call: helpers
    # -----------------------------
    class FakeHTTPException(Exception):
        def __init__(self, status=None, code=None, retry_after=None):
            super().__init__("fake")
            self.status = status
            self.code = code
            self.retry_after = retry_after

    async def _no_sleep(self, delay):
        # Vervanger voor asyncio.sleep om tests snel te houden
        self.slept.append(delay)

    # -----------------------------
    # safe_call: succesvolle paden
    # -----------------------------
    async def test_safe_call_success_sync_and_async(self):
        async def a_success(x):
            return x * 2

        def s_success(x, y=1):
            return x + y

        with patch.object(dc, "HTTPExc", self.FakeHTTPException):
            # Async
            res1 = await dc.safe_call(a_success, 4)
            assert res1 == 8
            # Sync
            res2 = await dc.safe_call(s_success, 5, y=7)
            assert res2 == 12

    # -----------------------------
    # safe_call: HTTP 429 met retry_after → retry en succeed
    # -----------------------------
    async def test_safe_call_http_429_retry_after(self):
        calls = {"n": 0}

        def sometimes_fail():
            calls["n"] += 1
            if calls["n"] == 1:
                raise self.FakeHTTPException(status=429, retry_after=0.05)
            return "ok"

        self.slept = []

        with patch.object(dc, "HTTPExc", self.FakeHTTPException), patch(
            "asyncio.sleep", side_effect=self._no_sleep
        ):
            res = await dc.safe_call(
                sometimes_fail, retries=3, base_delay=0.01, jitter=0.0
            )
            assert res == "ok"
            # We hebben exact 1 keer geslapen met retry_after
            assert len(self.slept) == 1
            assert abs(self.slept[0] - 0.05) < 1e-6

    # -----------------------------
    # safe_call: HTTP transient code (500) → retry en succeed
    # -----------------------------
    async def test_safe_call_http_500_retry(self):
        calls = {"n": 0}

        def sometimes_fail():
            calls["n"] += 1
            if calls["n"] < 3:
                raise self.FakeHTTPException(status=500)
            return "ok"

        self.slept = []
        # Jitter deterministisch maken
        with patch.object(dc, "HTTPExc", self.FakeHTTPException), patch(
            "random.uniform", return_value=0.0
        ), patch("asyncio.sleep", side_effect=self._no_sleep):
            res = await dc.safe_call(
                sometimes_fail, retries=5, base_delay=0.01, jitter=0.0
            )
            assert res == "ok"
            # 2 retries → 2 sleeps (exponentieel 0.01, 0.02 zonder jitter)
            assert self.slept == [0.01, 0.02]

    # -----------------------------
    # safe_call: HTTP niet-transient → raise
    # -----------------------------
    async def test_safe_call_http_non_transient_raises(self):
        def always_fail():
            raise self.FakeHTTPException(status=418)  # I'm a teapot (niet-transient)

        with patch.object(dc, "HTTPExc", self.FakeHTTPException):
            try:
                await dc.safe_call(always_fail, retries=2)
            except self.FakeHTTPException as e:
                assert e.status == 418
            else:
                assert False, "expected exception"

    # -----------------------------
    # safe_call: HTTP transient via code-veld (bijv. 110000) → retry
    # -----------------------------
    async def test_safe_call_http_transient_via_code(self):
        calls = {"n": 0}

        def sometimes_fail():
            calls["n"] += 1
            if calls["n"] == 1:
                raise self.FakeHTTPException(code=110000)
            return "ok"

        self.slept = []
        with patch.object(dc, "HTTPExc", self.FakeHTTPException), patch(
            "random.uniform", return_value=0.0
        ), patch("asyncio.sleep", side_effect=self._no_sleep):
            res = await dc.safe_call(
                sometimes_fail, retries=3, base_delay=0.01, jitter=0.0
            )
            assert res == "ok"
            assert self.slept == [0.01]

    # -----------------------------
    # safe_call: OSError/TimeoutError → retry
    # -----------------------------
    async def test_safe_call_oserror_and_timeout_retry(self):
        seq = iter([OSError("ephemeral"), asyncio.TimeoutError(), "ok"])

        def sometimes_fail():
            val = next(seq)
            if isinstance(val, Exception):
                raise val
            return val

        self.slept = []
        with patch("random.uniform", return_value=0.0), patch(
            "asyncio.sleep", side_effect=self._no_sleep
        ):
            res = await dc.safe_call(
                sometimes_fail, retries=5, base_delay=0.01, jitter=0.0
            )
            assert res == "ok"
            # 2 retries → 2 sleeps
            assert self.slept == [0.01, 0.02]

    # -----------------------------
    # safe_call: generic Exception met status 503 → retry
    # -----------------------------
    async def test_safe_call_generic_with_status_transient(self):
        calls = {"n": 0}

        class WeirdError(Exception):
            def __init__(self, status=None, retry_after=None):
                super().__init__("weird")
                self.status = status
                self.retry_after = retry_after

        def sometimes_fail():
            calls["n"] += 1
            if calls["n"] == 1:
                raise WeirdError(status=503, retry_after=0.02)
            return "ok"

        self.slept = []
        with patch("asyncio.sleep", side_effect=self._no_sleep):
            res = await dc.safe_call(
                sometimes_fail, retries=3, base_delay=0.01, jitter=0.0
            )
            assert res == "ok"
            assert len(self.slept) == 1
            assert abs(self.slept[0] - 0.02) < 1e-6

    # -----------------------------
    # safe_call: generic Exception zonder status → raise
    # -----------------------------
    async def test_safe_call_generic_without_status_raises(self):
        def always_fail():
            raise RuntimeError("boom")

        try:
            await dc.safe_call(always_fail, retries=2)
        except RuntimeError as e:
            assert str(e) == "boom"
        else:
            assert False, "expected exception"

    # -----------------------------
    # safe_call: retries uitgeput → raise
    # -----------------------------
    async def test_safe_call_retries_exhausted_raises(self):
        calls = {"n": 0}

        def fail_three_times():
            calls["n"] += 1
            raise self.FakeHTTPException(status=500)

        self.slept = []
        with patch.object(dc, "HTTPExc", self.FakeHTTPException), patch(
            "random.uniform", return_value=0.0
        ), patch("asyncio.sleep", side_effect=self._no_sleep):
            try:
                await dc.safe_call(
                    fail_three_times, retries=2, base_delay=0.01, jitter=0.0
                )
            except self.FakeHTTPException as e:
                assert e.status == 500
                # 2 retries geprobeerd → 2 sleeps
                assert self.slept == [0.01, 0.02]
            else:
                assert False, "expected exception"

    # -----------------------------
    # HTTPExc via code (transient) met delay==0 → géén sleep
    # -----------------------------
    async def test_safe_call_http_transient_code_no_sleep(self):
        """
        HTTP-exception via 'code' (110000) moet als transient gelden.
        We patchen dc.HTTPExc naar een lichte dummy zodat we geen echte
        discord.HTTPException hoeven te construeren. Met base_delay=0 en
        jitter=0 hoort er géén sleep plaats te vinden.
        """
        calls = {"n": 0}

        class DummyHTTPExc(Exception):
            def __init__(self, code=None):
                super().__init__("dummy")
                self.code = code
                self.status = None
                self.retry_after = None

        def flaky():
            calls["n"] += 1
            if calls["n"] == 1:
                # transient via code-veld
                raise DummyHTTPExc(code=110000)
            return "ok"

        slept = []

        async def no_sleep(_):  # mag niet aangeroepen worden
            slept.append(_)

        # Patch het type waar safe_call tegen checkt
        with patch.object(dc, "HTTPExc", DummyHTTPExc), patch(
            "asyncio.sleep", new=no_sleep
        ):
            res = await dc.safe_call(flaky, retries=3, base_delay=0.0, jitter=0.0)
            assert res == "ok"
            assert slept == []  # geen sleep bij delay==0

    # -----------------------------
    # Generieke Exception met status transient (503) en delay==0 → géén sleep
    # -----------------------------
    async def test_safe_call_generic_status_transient_no_sleep(self):
        calls = {"n": 0}

        class Weird(Exception):
            def __init__(self, status=None, retry_after=None):
                super().__init__("w")
                self.status = status
                self.retry_after = retry_after

        def flaky():
            calls["n"] += 1
            if calls["n"] == 1:
                raise Weird(status=503)  # transient via status
            return "ok"

        slept = []

        async def no_sleep(_):  # wordt niet aangeroepen
            slept.append(_)

        with patch("asyncio.sleep", new=no_sleep):
            res = await dc.safe_call(flaky, retries=2, base_delay=0.0, jitter=0.0)
            assert res == "ok"
            assert slept == []  # delay==0 → geen sleep

    # -----------------------------
    # OSError-pad met delay==0 → géén sleep
    # -----------------------------
    async def test_safe_call_oserror_no_sleep(self):
        seq = iter([OSError("temp"), "ok"])

        def flaky():
            v = next(seq)
            if isinstance(v, Exception):
                raise v
            return v

        slept = []

        async def no_sleep(_):  # wordt niet aangeroepen
            slept.append(_)

        with patch("asyncio.sleep", new=no_sleep):
            res = await dc.safe_call(flaky, retries=2, base_delay=0.0, jitter=0.0)
            assert res == "ok"
            assert slept == []  # delay==0 → geen sleep

    # -----------------------------
    # Generieke Exception met status transient, maar retries uitgeput → raise
    # -----------------------------
    async def test_safe_call_generic_status_transient_exhausted_raises(self):
        class Weird(Exception):
            def __init__(self, status=None, retry_after=None):
                super().__init__("w")
                self.status = status
                self.retry_after = None

        def always():
            raise Weird(status=503)

        # retries=0 → meteen raise in generieke except-branch
        try:
            await dc.safe_call(always, retries=0, base_delay=0.0, jitter=0.0)
        except Weird as e:
            assert e.status == 503
        else:
            assert False, "expected exception"

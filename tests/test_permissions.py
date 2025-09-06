# tests/test_permissions.py

import inspect
from tests.base import BaseTestCase
from apps.commands.dmk_poll import is_admin_of_moderator


class Perms:
    def __init__(self, admin=False, mod=False):
        self.administrator = admin
        self.moderate_members = mod


class FakeUser:
    def __init__(self, admin=False, mod=False):
        self.guild_permissions = Perms(admin, mod)


class FakeInteraction:
    def __init__(self, admin=False, mod=False):
        self.user = FakeUser(admin, mod)


class TestPermission(BaseTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()

    async def _call_check(self, itx):
        if inspect.iscoroutinefunction(is_admin_of_moderator):
            return await is_admin_of_moderator(itx)
        return is_admin_of_moderator(itx)

    async def test_is_admin_true(self):
        itx = FakeInteraction(admin=True, mod=False)
        assert await self._call_check(itx)

    async def test_is_moderator_true(self):
        itx = FakeInteraction(admin=False, mod=True)
        assert await self._call_check(itx)

    async def test_is_none_false(self):
        itx = FakeInteraction(admin=False, mod=False)
        assert not await self._call_check(itx)

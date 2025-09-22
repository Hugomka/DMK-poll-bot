# tests/test_ui_views.py

import discord

from apps.ui.poll_buttons import OneStemButtonView
from tests.base import BaseTestCase


class TestUIViews(BaseTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()

    async def test_one_stem_button_view_enabled_disabled(self):
        v1 = OneStemButtonView(paused=False)
        v2 = OneStemButtonView(paused=True)

        assert len(v1.children) >= 1
        assert isinstance(v1.children[0], discord.ui.Button)
        assert v1.children[0].disabled is False

        assert len(v2.children) >= 1
        assert isinstance(v2.children[0], discord.ui.Button)
        assert v2.children[0].disabled is True

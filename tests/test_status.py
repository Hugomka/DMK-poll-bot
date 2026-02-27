# tests/test_status.py

from unittest.mock import AsyncMock, MagicMock, patch

from apps.commands.poll_status import PollStatus
from apps.utils.poll_storage import toggle_vote
from tests.base import BaseTestCase


class TestStatusCommand(BaseTestCase):

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.mock_bot = MagicMock()
        self.cog = PollStatus(self.mock_bot)

    async def test_status_embed_toon_namen(self):
        # Zet naamweergave aan
        kanaal_id = 123456

        # Simuleer stem
        await toggle_vote("111", "vrijdag", "om 19:00 uur", kanaal_id, kanaal_id)

        # Maak nep-interaction met guild en user
        mock_guild = MagicMock()
        mock_guild.id = 0
        mock_member = MagicMock()
        mock_member.display_name = "Goldway"
        mock_member.global_name = None
        mock_member.name = "Goldway"
        mock_guild.get_member.return_value = mock_member
        mock_guild.fetch_member = AsyncMock(return_value=mock_member)
        mock_guild.id = kanaal_id

        mock_channel = MagicMock()
        mock_channel.id = kanaal_id
        mock_channel.guild = mock_guild

        mock_user = MagicMock()
        mock_user.guild_permissions.administrator = True

        interaction = MagicMock()
        interaction.guild = mock_guild
        interaction.channel = mock_channel
        interaction.user = mock_user
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        # ⏯️ Aanroepen van status
        await self.cog._status_impl(interaction)

        # 🔍 Controleer dat een embed is gestuurd
        interaction.followup.send.assert_called()
        args, kwargs = interaction.followup.send.call_args
        self.assertEqual(args, (), "Expected no positional args in followup.send")
        embed = kwargs.get("embed")
        self.assertIsNotNone(embed)
        self.assertIn("@Goldway", str(embed.description) + str(embed.fields))

    async def test_status_embed_toon_niet_stemmers(self):
        """Test dat niet-stemmers worden getoond in het statusbericht"""
        kanaal_id = 123456

        # Simuleer één stem voor vrijdag
        await toggle_vote("111", "vrijdag", "om 19:00 uur", kanaal_id, kanaal_id)

        # Maak nep-interaction met guild, channel en members
        mock_guild = MagicMock()
        mock_guild.id = kanaal_id

        # Lid dat wel heeft gestemd
        mock_member_voted = MagicMock()
        mock_member_voted.id = 111
        mock_member_voted.display_name = "StemmerJan"
        mock_member_voted.global_name = None
        mock_member_voted.name = "StemmerJan"
        mock_member_voted.bot = False

        # Leden die NIET hebben gestemd
        mock_member_not_voted_1 = MagicMock()
        mock_member_not_voted_1.id = 222
        mock_member_not_voted_1.display_name = "NietStemmerKingBoo"
        mock_member_not_voted_1.global_name = None
        mock_member_not_voted_1.name = "NietStemmerKingBoo"
        mock_member_not_voted_1.bot = False

        mock_member_not_voted_2 = MagicMock()
        mock_member_not_voted_2.id = 333
        mock_member_not_voted_2.display_name = "NietStemmerYoshi"
        mock_member_not_voted_2.global_name = None
        mock_member_not_voted_2.name = "NietStemmerYoshi"
        mock_member_not_voted_2.bot = False

        # Bot (moet worden uitgefilterd)
        mock_bot_member = MagicMock()
        mock_bot_member.id = 999
        mock_bot_member.bot = True

        mock_channel = MagicMock()
        mock_channel.id = kanaal_id
        mock_channel.guild = mock_guild
        # Simuleer channel.members - lijst van alle leden in het kanaal
        mock_channel.members = [
            mock_member_voted,
            mock_member_not_voted_1,
            mock_member_not_voted_2,
            mock_bot_member,
        ]

        # Setup guild.get_member en fetch_member
        def get_member_side_effect(member_id):
            members_dict = {
                111: mock_member_voted,
                222: mock_member_not_voted_1,
                333: mock_member_not_voted_2,
                999: mock_bot_member,
            }
            return members_dict.get(member_id)

        mock_guild.get_member.side_effect = get_member_side_effect
        mock_guild.fetch_member = AsyncMock(side_effect=get_member_side_effect)

        mock_user = MagicMock()
        mock_user.guild_permissions.administrator = True

        interaction = MagicMock()
        interaction.guild = mock_guild
        interaction.channel = mock_channel
        interaction.user = mock_user
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        # ⏯️ Aanroepen van status
        await self.cog._status_impl(interaction)

        # 🔍 Controleer dat een embed is gestuurd
        interaction.followup.send.assert_called()
        args, kwargs = interaction.followup.send.call_args
        embed = kwargs.get("embed")
        self.assertIsNotNone(embed)

        # Converteer embed fields naar string voor inspectie
        embed_text = str(embed.description) + "".join(
            str(field.name) + str(field.value) for field in embed.fields
        )

        # Controleer dat de stemmer wordt getoond bij vrijdag
        self.assertIn("@StemmerJan", embed_text)

        # Controleer dat niet-stemmers worden getoond voor vrijdag
        self.assertIn("👻 niet gestemd — **2** stemmen", embed_text)
        self.assertIn("@NietStemmerKingBoo", embed_text)
        self.assertIn("@NietStemmerYoshi", embed_text)

        # Controleer dat de bot NIET wordt getoond
        self.assertNotIn("999", embed_text)

    async def test_status_geen_niet_stemmers_als_iedereen_gestemd_heeft(self):
        """Test dat niet-stemmers NIET worden getoond als iedereen heeft gestemd"""
        kanaal_id = 123456

        # Simuleer stemmen voor beide leden
        await toggle_vote("111", "vrijdag", "om 19:00 uur", kanaal_id, kanaal_id)
        await toggle_vote("222", "vrijdag", "om 20:30 uur", kanaal_id, kanaal_id)

        # Maak nep-interaction met guild, channel en members
        mock_guild = MagicMock()
        mock_guild.id = kanaal_id

        # Beide leden hebben gestemd
        mock_member_1 = MagicMock()
        mock_member_1.id = 111
        mock_member_1.display_name = "StemmerJan"
        mock_member_1.global_name = None
        mock_member_1.name = "StemmerJan"
        mock_member_1.bot = False

        mock_member_2 = MagicMock()
        mock_member_2.id = 222
        mock_member_2.display_name = "StemmerKing Boo"
        mock_member_2.global_name = None
        mock_member_2.name = "StemmerKing Boo"
        mock_member_2.bot = False

        mock_channel = MagicMock()
        mock_channel.id = kanaal_id
        mock_channel.guild = mock_guild
        mock_channel.members = [mock_member_1, mock_member_2]

        def get_member_side_effect(member_id):
            members_dict = {111: mock_member_1, 222: mock_member_2}
            return members_dict.get(member_id)

        mock_guild.get_member.side_effect = get_member_side_effect
        mock_guild.fetch_member = AsyncMock(side_effect=get_member_side_effect)

        mock_user = MagicMock()
        mock_user.guild_permissions.administrator = True

        interaction = MagicMock()
        interaction.guild = mock_guild
        interaction.channel = mock_channel
        interaction.user = mock_user
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        # ⏯️ Aanroepen van status
        await self.cog._status_impl(interaction)

        # 🔍 Controleer dat een embed is gestuurd
        interaction.followup.send.assert_called()
        args, kwargs = interaction.followup.send.call_args
        embed = kwargs.get("embed")
        self.assertIsNotNone(embed)

        # Converteer embed fields naar string
        embed_text = str(embed.description) + "".join(
            str(field.name) + str(field.value) for field in embed.fields
        )

        # Controleer dat beide stemmers worden getoond
        self.assertIn("@StemmerJan", embed_text)
        self.assertIn("@StemmerKing Boo", embed_text)

        # Controleer dat "Niet-stemmers" NIET voorkomt voor vrijdag
        # (er zijn geen niet-stemmers)
        vrijdag_text = ""
        for field in embed.fields:
            if "Vrijdag" in str(field.name):
                vrijdag_text = str(field.value)
                break

        self.assertTrue(len(vrijdag_text) > 0, "Vrijdag field should exist")
        self.assertNotIn("Niet-stemmers", vrijdag_text)

    async def test_status_gast_stem_telt_voor_owner(self):
        """Test dat als een gast van een lid stemt, het lid niet als niet-stemmer wordt getoond"""
        kanaal_id = 123456

        # Simuleer gast-stem voor lid 111
        await toggle_vote(
            "111_guest::Bowser", "vrijdag", "om 19:00 uur", kanaal_id, kanaal_id
        )

        # Maak nep-interaction met guild, channel en members
        mock_guild = MagicMock()
        mock_guild.id = kanaal_id

        # Lid 111 heeft niet zelf gestemd, maar hun gast wel
        mock_member_with_guest = MagicMock()
        mock_member_with_guest.id = 111
        mock_member_with_guest.display_name = "Mario"
        mock_member_with_guest.global_name = None
        mock_member_with_guest.name = "Mario"
        mock_member_with_guest.bot = False

        # Lid 222 heeft helemaal niet gestemd
        mock_member_not_voted = MagicMock()
        mock_member_not_voted.id = 222
        mock_member_not_voted.display_name = "Luigi"
        mock_member_not_voted.global_name = None
        mock_member_not_voted.name = "Luigi"
        mock_member_not_voted.bot = False

        mock_channel = MagicMock()
        mock_channel.id = kanaal_id
        mock_channel.guild = mock_guild
        mock_channel.members = [mock_member_with_guest, mock_member_not_voted]

        def get_member_side_effect(member_id):
            members_dict = {111: mock_member_with_guest, 222: mock_member_not_voted}
            return members_dict.get(member_id)

        mock_guild.get_member.side_effect = get_member_side_effect
        mock_guild.fetch_member = AsyncMock(side_effect=get_member_side_effect)

        mock_user = MagicMock()
        mock_user.guild_permissions.administrator = True

        interaction = MagicMock()
        interaction.guild = mock_guild
        interaction.channel = mock_channel
        interaction.user = mock_user
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        # ⏯️ Aanroepen van status
        await self.cog._status_impl(interaction)

        # 🔍 Controleer dat een embed is gestuurd
        interaction.followup.send.assert_called()
        kwargs = interaction.followup.send.call_args[1]
        embed = kwargs.get("embed")
        self.assertIsNotNone(embed)

        # Converteer embed fields naar string
        embed_text = str(embed.description) + "".join(
            str(field.name) + str(field.value) for field in embed.fields
        )

        # Controleer dat Mario (owner van gast) wordt getoond bij de stemmers
        self.assertIn("@Mario", embed_text)
        self.assertIn("Bowser", embed_text)  # De gast

        # Controleer dat alleen Luigi als niet-stemmer wordt getoond
        self.assertIn("👻 niet gestemd — **1** stemmen", embed_text)
        self.assertIn("@Luigi", embed_text)

        # Mario mag NIET bij niet-stemmers staan (want hun gast heeft gestemd)
        vrijdag_text = ""
        for field in embed.fields:
            if "Vrijdag" in str(field.name):
                vrijdag_text = str(field.value)
                break

        # Zoek de niet-stemmers regel
        niet_stemmers_line = ""
        for line in vrijdag_text.split("\n"):
            if "Niet-stemmers" in line:
                niet_stemmers_line = line
                break

        # Mario mag niet in de niet-stemmers regel staan
        if niet_stemmers_line:
            self.assertNotIn("@Mario", niet_stemmers_line)

    async def test_status_toont_period_schedules(self):
        """Test dat beide periodes met open/close tijden worden getoond in het statusbericht"""
        from apps.utils.poll_settings import set_period_settings

        kanaal_id = 123456

        # Stel period settings in voor dit kanaal
        set_period_settings(kanaal_id, "vr-zo", enabled=True, open_day="dinsdag", open_time="20:00", close_day="maandag", close_time="00:00")
        set_period_settings(kanaal_id, "ma-do", enabled=True, open_day="vrijdag", open_time="20:00", close_day="vrijdag", close_time="00:00")

        # Maak nep-interaction
        mock_guild = MagicMock()
        mock_guild.id = kanaal_id

        mock_channel = MagicMock()
        mock_channel.id = kanaal_id
        mock_channel.guild = mock_guild
        mock_channel.members = []

        mock_user = MagicMock()
        mock_user.guild_permissions.administrator = True

        interaction = MagicMock()
        interaction.guild = mock_guild
        interaction.channel = mock_channel
        interaction.user = mock_user
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        # ⏯️ Aanroepen van status
        await self.cog._status_impl(interaction)

        # 🔍 Controleer dat een embed is gestuurd
        interaction.followup.send.assert_called()
        kwargs = interaction.followup.send.call_args[1]
        embed = kwargs.get("embed")
        self.assertIsNotNone(embed)

        # Converteer embed fields naar string
        embed_text = str(embed.description) + "".join(
            str(field.name) + str(field.value) for field in embed.fields
        )

        # Controleer dat beide periodes aanwezig zijn
        self.assertIn("Periode: vr-zo", embed_text)
        self.assertIn("Periode: ma-do", embed_text)

        # Controleer dat open/close tijden getoond worden
        self.assertIn("Ingeschakeld", embed_text)
        self.assertIn("dinsdag", embed_text)
        self.assertIn("20:00", embed_text)

    async def test_status_toont_disabled_period(self):
        """Test dat een uitgeschakelde periode als 'Uitgeschakeld' wordt getoond"""
        from apps.utils.poll_settings import set_period_settings

        kanaal_id = 654321

        # ma-do is disabled by default
        set_period_settings(kanaal_id, "vr-zo", enabled=True, open_day="dinsdag", open_time="20:00", close_day="maandag", close_time="00:00")
        set_period_settings(kanaal_id, "ma-do", enabled=False)

        # Maak nep-interaction
        mock_guild = MagicMock()
        mock_guild.id = kanaal_id

        mock_channel = MagicMock()
        mock_channel.id = kanaal_id
        mock_channel.guild = mock_guild
        mock_channel.members = []

        mock_user = MagicMock()
        mock_user.guild_permissions.administrator = True

        interaction = MagicMock()
        interaction.guild = mock_guild
        interaction.channel = mock_channel
        interaction.user = mock_user
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        # ⏯️ Aanroepen van status
        await self.cog._status_impl(interaction)

        # 🔍 Controleer dat een embed is gestuurd
        interaction.followup.send.assert_called()
        kwargs = interaction.followup.send.call_args[1]
        embed = kwargs.get("embed")
        self.assertIsNotNone(embed)

        # Zoek de ma-do period field
        mado_field = None
        for field in embed.fields:
            if "ma-do" in str(field.name):
                mado_field = field
                break

        self.assertIsNotNone(mado_field)
        assert mado_field is not None
        self.assertIn("Uitgeschakeld", str(mado_field.value))

    async def test_status_only_shows_enabled_days(self):
        """Test dat status alleen enabled dagen toont op basis van poll-opties instelling"""
        from apps.utils.poll_settings import set_poll_option_state
        from apps.entities.poll_option import get_poll_options

        kanaal_id = 789012

        # Stel alle opties in op disabled, behalve vrijdag, zaterdag en zondag
        for opt in get_poll_options():
            if opt.dag in ["vrijdag", "zaterdag", "zondag"]:
                set_poll_option_state(kanaal_id, opt.dag, opt.tijd, True)
            else:
                set_poll_option_state(kanaal_id, opt.dag, opt.tijd, False)

        # Maak nep-interaction
        mock_guild = MagicMock()
        mock_guild.id = kanaal_id

        mock_channel = MagicMock()
        mock_channel.id = kanaal_id
        mock_channel.guild = mock_guild
        mock_channel.members = []

        mock_user = MagicMock()
        mock_user.guild_permissions.administrator = True

        interaction = MagicMock()
        interaction.guild = mock_guild
        interaction.channel = mock_channel
        interaction.user = mock_user
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        # ⏯️ Aanroepen van status
        await self.cog._status_impl(interaction)

        # 🔍 Controleer dat een embed is gestuurd
        interaction.followup.send.assert_called()
        kwargs = interaction.followup.send.call_args[1]
        embed = kwargs.get("embed")
        self.assertIsNotNone(embed)

        # Verzamel alle field namen
        field_names = [str(field.name) for field in embed.fields]

        # Controleer dat alleen de enabled dagen aanwezig zijn
        self.assertTrue(
            any("Vrijdag" in name for name in field_names),
            "Vrijdag should be shown (enabled)",
        )
        self.assertTrue(
            any("Zaterdag" in name for name in field_names),
            "Zaterdag should be shown (enabled)",
        )
        self.assertTrue(
            any("Zondag" in name for name in field_names),
            "Zondag should be shown (enabled)",
        )

        # Controleer dat de disabled dagen NIET aanwezig zijn
        self.assertFalse(
            any("Maandag" in name for name in field_names),
            "Maandag should NOT be shown (disabled)",
        )
        self.assertFalse(
            any("Dinsdag" in name for name in field_names),
            "Dinsdag should NOT be shown (disabled)",
        )
        self.assertFalse(
            any("Woensdag" in name for name in field_names),
            "Woensdag should NOT be shown (disabled)",
        )
        self.assertFalse(
            any("Donderdag" in name for name in field_names),
            "Donderdag should NOT be shown (disabled)",
        )

    async def test_status_shows_all_days_when_all_enabled(self):
        """Test dat status alle 7 dagen toont als ze allemaal enabled zijn"""
        from apps.utils.poll_settings import set_poll_option_state, set_period_settings
        from apps.entities.poll_option import get_poll_options

        kanaal_id = 890123

        # Enable both periods
        set_period_settings(kanaal_id, "vr-zo", enabled=True)
        set_period_settings(kanaal_id, "ma-do", enabled=True)

        # Stel alle opties in als enabled
        for opt in get_poll_options():
            set_poll_option_state(kanaal_id, opt.dag, opt.tijd, True)

        # Maak nep-interaction
        mock_guild = MagicMock()
        mock_guild.id = kanaal_id

        mock_channel = MagicMock()
        mock_channel.id = kanaal_id
        mock_channel.guild = mock_guild
        mock_channel.members = []

        mock_user = MagicMock()
        mock_user.guild_permissions.administrator = True

        interaction = MagicMock()
        interaction.guild = mock_guild
        interaction.channel = mock_channel
        interaction.user = mock_user
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        # ⏯️ Aanroepen van status — mock is_period_currently_open zodat beide periodes altijd open zijn
        with patch("apps.utils.poll_settings.is_period_currently_open", return_value=True):
            await self.cog._status_impl(interaction)

        # 🔍 Controleer dat een embed is gestuurd
        interaction.followup.send.assert_called()
        kwargs = interaction.followup.send.call_args[1]
        embed = kwargs.get("embed")
        self.assertIsNotNone(embed)

        # Verzamel alle field namen
        field_names = [str(field.name) for field in embed.fields]

        # Controleer dat alle 7 dagen aanwezig zijn
        all_days = [
            "Maandag",
            "Dinsdag",
            "Woensdag",
            "Donderdag",
            "Vrijdag",
            "Zaterdag",
            "Zondag",
        ]
        for dag in all_days:
            self.assertTrue(
                any(dag.lower() in name.lower() for name in field_names),
                f"{dag} should be shown (enabled). Found fields: {field_names}",
            )

    async def test_status_shows_only_weekdays_when_enabled(self):
        """Test dat status alleen weekdagen toont als alleen die zijn enabled"""
        from apps.utils.poll_settings import set_poll_option_state, set_period_settings
        from apps.entities.poll_option import get_poll_options

        kanaal_id = 901234

        # Enable ma-do period, disable vr-zo
        set_period_settings(kanaal_id, "ma-do", enabled=True)
        set_period_settings(kanaal_id, "vr-zo", enabled=False)

        # Stel alleen weekdagen in als enabled
        for opt in get_poll_options():
            if opt.dag in ["maandag", "dinsdag", "woensdag", "donderdag"]:
                set_poll_option_state(kanaal_id, opt.dag, opt.tijd, True)
            else:
                set_poll_option_state(kanaal_id, opt.dag, opt.tijd, False)

        # Maak nep-interaction
        mock_guild = MagicMock()
        mock_guild.id = kanaal_id

        mock_channel = MagicMock()
        mock_channel.id = kanaal_id
        mock_channel.guild = mock_guild
        mock_channel.members = []

        mock_user = MagicMock()
        mock_user.guild_permissions.administrator = True

        interaction = MagicMock()
        interaction.guild = mock_guild
        interaction.channel = mock_channel
        interaction.user = mock_user
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        # ⏯️ Aanroepen van status — mock is_period_currently_open zodat ma-do open is
        with patch("apps.utils.poll_settings.is_period_currently_open", return_value=True):
            await self.cog._status_impl(interaction)

        # 🔍 Controleer dat een embed is gestuurd
        interaction.followup.send.assert_called()
        kwargs = interaction.followup.send.call_args[1]
        embed = kwargs.get("embed")
        self.assertIsNotNone(embed)

        # Verzamel alle field namen
        field_names = [str(field.name) for field in embed.fields]

        # Controleer dat alleen de weekdagen aanwezig zijn
        self.assertTrue(
            any("Maandag" in name for name in field_names),
            "Maandag should be shown (enabled)",
        )
        self.assertTrue(
            any("Dinsdag" in name for name in field_names),
            "Dinsdag should be shown (enabled)",
        )
        self.assertTrue(
            any("Woensdag" in name for name in field_names),
            "Woensdag should be shown (enabled)",
        )
        self.assertTrue(
            any("Donderdag" in name for name in field_names),
            "Donderdag should be shown (enabled)",
        )

        # Controleer dat weekend dagen NIET aanwezig zijn
        self.assertFalse(
            any("Vrijdag" in name for name in field_names),
            "Vrijdag should NOT be shown (disabled)",
        )
        self.assertFalse(
            any("Zaterdag" in name for name in field_names),
            "Zaterdag should NOT be shown (disabled)",
        )
        self.assertFalse(
            any("Zondag" in name for name in field_names),
            "Zondag should NOT be shown (disabled)",
        )


    async def test_status_shows_day_with_only_1900_enabled(self):
        """Test dat een dag wordt getoond als alleen 19:00 enabled is"""
        from apps.utils.poll_settings import set_poll_option_state

        kanaal_id = 111222

        # Stel vrijdag in: alleen 19:00 enabled, 20:30 disabled
        set_poll_option_state(kanaal_id, "vrijdag", "om 19:00 uur", True)
        set_poll_option_state(kanaal_id, "vrijdag", "om 20:30 uur", False)

        # Maak nep-interaction
        mock_guild = MagicMock()
        mock_guild.id = kanaal_id

        mock_channel = MagicMock()
        mock_channel.id = kanaal_id
        mock_channel.guild = mock_guild
        mock_channel.members = []

        mock_user = MagicMock()
        mock_user.guild_permissions.administrator = True

        interaction = MagicMock()
        interaction.guild = mock_guild
        interaction.channel = mock_channel
        interaction.user = mock_user
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        # Aanroepen van status
        await self.cog._status_impl(interaction)

        # Controleer dat vrijdag wordt getoond
        interaction.followup.send.assert_called()
        kwargs = interaction.followup.send.call_args[1]
        embed = kwargs.get("embed")
        self.assertIsNotNone(embed)

        field_names = [str(field.name) for field in embed.fields]
        self.assertTrue(
            any("vrijdag" in name.lower() for name in field_names),
            "Vrijdag should be shown when only 19:00 is enabled",
        )

    async def test_status_shows_day_with_only_2030_enabled(self):
        """Test dat een dag wordt getoond als alleen 20:30 enabled is"""
        from apps.utils.poll_settings import set_poll_option_state

        kanaal_id = 222333

        # Stel zaterdag in: 19:00 disabled, alleen 20:30 enabled
        set_poll_option_state(kanaal_id, "zaterdag", "om 19:00 uur", False)
        set_poll_option_state(kanaal_id, "zaterdag", "om 20:30 uur", True)

        # Maak nep-interaction
        mock_guild = MagicMock()
        mock_guild.id = kanaal_id

        mock_channel = MagicMock()
        mock_channel.id = kanaal_id
        mock_channel.guild = mock_guild
        mock_channel.members = []

        mock_user = MagicMock()
        mock_user.guild_permissions.administrator = True

        interaction = MagicMock()
        interaction.guild = mock_guild
        interaction.channel = mock_channel
        interaction.user = mock_user
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        # Aanroepen van status
        await self.cog._status_impl(interaction)

        # Controleer dat zaterdag wordt getoond
        interaction.followup.send.assert_called()
        kwargs = interaction.followup.send.call_args[1]
        embed = kwargs.get("embed")
        self.assertIsNotNone(embed)

        field_names = [str(field.name) for field in embed.fields]
        self.assertTrue(
            any("zaterdag" in name.lower() for name in field_names),
            "Zaterdag should be shown when only 20:30 is enabled",
        )

    async def test_status_hides_day_with_both_times_disabled(self):
        """Test dat een dag NIET wordt getoond als beide tijden disabled zijn"""
        from apps.utils.poll_settings import set_poll_option_state

        kanaal_id = 333444

        # Stel zondag in: beide tijden disabled
        set_poll_option_state(kanaal_id, "zondag", "om 19:00 uur", False)
        set_poll_option_state(kanaal_id, "zondag", "om 20:30 uur", False)

        # Maak nep-interaction
        mock_guild = MagicMock()
        mock_guild.id = kanaal_id

        mock_channel = MagicMock()
        mock_channel.id = kanaal_id
        mock_channel.guild = mock_guild
        mock_channel.members = []

        mock_user = MagicMock()
        mock_user.guild_permissions.administrator = True

        interaction = MagicMock()
        interaction.guild = mock_guild
        interaction.channel = mock_channel
        interaction.user = mock_user
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        # Aanroepen van status
        await self.cog._status_impl(interaction)

        # Controleer dat zondag NIET wordt getoond
        interaction.followup.send.assert_called()
        kwargs = interaction.followup.send.call_args[1]
        embed = kwargs.get("embed")
        self.assertIsNotNone(embed)

        field_names = [str(field.name) for field in embed.fields]
        self.assertFalse(
            any("zondag" in name.lower() for name in field_names),
            "Zondag should NOT be shown when both times are disabled",
        )

    async def test_status_shows_day_with_both_times_enabled(self):
        """Test dat een dag wordt getoond als beide tijden enabled zijn"""
        from apps.utils.poll_settings import set_poll_option_state

        kanaal_id = 444555

        # Stel vrijdag in: beide tijden enabled
        set_poll_option_state(kanaal_id, "vrijdag", "om 19:00 uur", True)
        set_poll_option_state(kanaal_id, "vrijdag", "om 20:30 uur", True)

        # Maak nep-interaction
        mock_guild = MagicMock()
        mock_guild.id = kanaal_id

        mock_channel = MagicMock()
        mock_channel.id = kanaal_id
        mock_channel.guild = mock_guild
        mock_channel.members = []

        mock_user = MagicMock()
        mock_user.guild_permissions.administrator = True

        interaction = MagicMock()
        interaction.guild = mock_guild
        interaction.channel = mock_channel
        interaction.user = mock_user
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        # Aanroepen van status
        await self.cog._status_impl(interaction)

        # Controleer dat vrijdag wordt getoond
        interaction.followup.send.assert_called()
        kwargs = interaction.followup.send.call_args[1]
        embed = kwargs.get("embed")
        self.assertIsNotNone(embed)

        field_names = [str(field.name) for field in embed.fields]
        self.assertTrue(
            any("vrijdag" in name.lower() for name in field_names),
            "Vrijdag should be shown when both times are enabled",
        )


class TestNotifyCommandEdgeCases(BaseTestCase):
    """Tests voor notify command edge cases en missing coverage"""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        from typing import Any, cast

        self.mock_bot = MagicMock()
        self.cog = PollStatus(self.mock_bot)

        # Helper om command aan te roepen
        async def _invoke_notify(*args, **kwargs):
            cb = self.cog.notify_fallback.callback
            return await cast(Any, cb)(self.cog, *args, **kwargs)

        self._invoke_notify = _invoke_notify

    def _mk_interaction(self, channel=None, admin=True):
        """Maakt een interaction-mock met response.defer en followup.send."""
        interaction = MagicMock()
        interaction.channel = channel
        interaction.guild = getattr(channel, "guild", None) if channel else None
        interaction.user = MagicMock()
        if admin:
            interaction.user.guild_permissions.administrator = True
        else:
            interaction.user.guild_permissions.administrator = False
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        return interaction

    async def test_notify_no_channel(self):
        """Test dat notify een error geeft als er geen kanaal is"""
        interaction = self._mk_interaction(channel=None, admin=True)

        await self._invoke_notify(interaction, "Herinnering vrijdag")

        interaction.followup.send.assert_awaited_once()
        args, kwargs = interaction.followup.send.call_args
        content = str(args[0]) if args else kwargs.get("content", "")
        self.assertIn("Geen kanaal", content)

    async def test_notify_herinnering_vrijdag(self):
        """Test dat notify Herinnering vrijdag correct afhandelt"""
        from unittest.mock import patch

        channel = MagicMock()
        channel.id = 123
        interaction = self._mk_interaction(channel=channel, admin=True)

        with patch("apps.commands.poll_status.is_channel_disabled", return_value=False), \
             patch("apps.commands.poll_status._is_denied_channel", return_value=False), \
             patch("apps.utils.poll_message.set_channel_disabled"), \
             patch("apps.scheduler.notify_non_or_maybe_voters", new=AsyncMock(return_value=True)) as mock_notify:

            await self._invoke_notify(interaction, "Herinnering vrijdag")

            # notify_non_or_maybe_voters moet zijn aangeroepen met dag="vrijdag"
            mock_notify.assert_called_once()
            call_kwargs = mock_notify.call_args
            self.assertEqual(call_kwargs.kwargs.get("dag"), "vrijdag")

    async def test_notify_herinnering_zaterdag(self):
        """Test dat notify Herinnering zaterdag correct afhandelt"""
        from unittest.mock import patch

        channel = MagicMock()
        channel.id = 123
        interaction = self._mk_interaction(channel=channel, admin=True)

        with patch("apps.commands.poll_status.is_channel_disabled", return_value=False), \
             patch("apps.commands.poll_status._is_denied_channel", return_value=False), \
             patch("apps.utils.poll_message.set_channel_disabled"), \
             patch("apps.scheduler.notify_non_or_maybe_voters", new=AsyncMock(return_value=True)) as mock_notify:

            await self._invoke_notify(interaction, "Herinnering zaterdag")

            # notify_non_or_maybe_voters moet zijn aangeroepen met dag="zaterdag"
            mock_notify.assert_called_once()
            call_kwargs = mock_notify.call_args
            self.assertEqual(call_kwargs.kwargs.get("dag"), "zaterdag")

    async def test_notify_herinnering_zondag(self):
        """Test dat notify Herinnering zondag correct afhandelt"""
        from unittest.mock import patch

        channel = MagicMock()
        channel.id = 123
        interaction = self._mk_interaction(channel=channel, admin=True)

        with patch("apps.commands.poll_status.is_channel_disabled", return_value=False), \
             patch("apps.commands.poll_status._is_denied_channel", return_value=False), \
             patch("apps.utils.poll_message.set_channel_disabled"), \
             patch("apps.scheduler.notify_non_or_maybe_voters", new=AsyncMock(return_value=True)) as mock_notify:

            await self._invoke_notify(interaction, "Herinnering zondag")

            # notify_non_or_maybe_voters moet zijn aangeroepen met dag="zondag"
            mock_notify.assert_called_once()
            call_kwargs = mock_notify.call_args
            self.assertEqual(call_kwargs.kwargs.get("dag"), "zondag")


# tests/test_status.py

from unittest.mock import AsyncMock, MagicMock

from apps.commands.poll_status import PollStatus
from apps.utils.poll_settings import set_scheduled_activation, set_scheduled_deactivation
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
        self.assertIn("Niet-stemmers (2)", embed_text)
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
        self.assertIn("Niet-stemmers (1)", embed_text)
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

    async def test_status_toont_schedules(self):
        """Test dat geplande activatie en deactivatie worden getoond in het statusbericht"""
        kanaal_id = 123456

        # Stel schedules in voor dit kanaal
        set_scheduled_activation(kanaal_id, "wekelijks", "10:00", dag="maandag")
        set_scheduled_deactivation(kanaal_id, "datum", "15:30", datum="2025-11-03")

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

        # Controleer dat de schedule velden aanwezig zijn
        self.assertIn("🗓️ Geplande activatie", embed_text)
        self.assertIn("🗑️ Geplande deactivatie", embed_text)

        # Controleer dat de formatted schedules correct zijn (dates displayed as DD-MM-YYYY)
        self.assertIn("elke maandag om 10:00", embed_text)
        self.assertIn("maandag 03-11-2025 om 15:30", embed_text)

    async def test_status_geen_schedules(self):
        """Test dat 'Geen' wordt getoond als er geen schedules zijn"""
        kanaal_id = 654321

        # Geen schedules instellen - gewoon een leeg kanaal

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

        # Controleer dat de schedule velden aanwezig zijn
        self.assertIn("🗓️ Geplande activatie", embed_text)
        self.assertIn("🗑️ Geplande deactivatie", embed_text)

        # Controleer dat beide velden "Geen" tonen
        # We zoeken de velden op en controleren de waarde
        activatie_field = None
        deactivatie_field = None
        for field in embed.fields:
            if "🗓️ Geplande activatie" in str(field.name):
                activatie_field = field
            if "🗑️ Geplande deactivatie" in str(field.name):
                deactivatie_field = field

        self.assertIsNotNone(activatie_field)
        self.assertIsNotNone(deactivatie_field)
        assert activatie_field is not None  # Type narrowing for Pylance
        assert deactivatie_field is not None  # Type narrowing for Pylance
        self.assertEqual(str(activatie_field.value), "Geen")
        self.assertEqual(str(deactivatie_field.value), "Geen")

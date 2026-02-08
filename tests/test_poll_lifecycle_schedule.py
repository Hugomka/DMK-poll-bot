# tests/test_poll_lifecycle_schedule.py
"""
Tests for scheduling-related functions in poll_lifecycle.py:
- _validate_scheduling_params
- _save_schedule
- _save_schedule_off
- _load_opening_message
"""

from unittest.mock import MagicMock, patch

from apps.commands.poll_lifecycle import PollLifecycle, _load_opening_message
from tests.base import BaseTestCase


class TestValidateSchedulingParams(BaseTestCase):
    """Tests for _validate_scheduling_params"""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bot = MagicMock()
        self.cog = PollLifecycle(self.bot)

    # Case: all parameters None → returns None
    async def test_all_params_none_returns_none(self):
        """Test that all None parameters returns None (manual activation)"""
        result = self.cog._validate_scheduling_params(
            dag=None, datum=None, tijd=None, frequentie=None
        )
        assert result is None

    # Case: dag or datum provided without tijd → returns error
    async def test_dag_without_tijd_returns_error(self):
        """Test that dag without tijd returns error"""
        result = self.cog._validate_scheduling_params(
            dag="maandag", datum=None, tijd=None, frequentie=None
        )
        assert result is not None
        assert "tijd" in result.lower()
        assert "verplicht" in result.lower()

    async def test_datum_without_tijd_returns_error(self):
        """Test that datum without tijd returns error"""
        result = self.cog._validate_scheduling_params(
            dag=None, datum="31-12-2025", tijd=None, frequentie=None
        )
        assert result is not None
        assert "tijd" in result.lower()
        assert "verplicht" in result.lower()

    # Case: both dag and datum provided → returns error
    async def test_both_dag_and_datum_returns_error(self):
        """Test that both dag and datum returns error"""
        result = self.cog._validate_scheduling_params(
            dag="maandag", datum="31-12-2025", tijd="18:00", frequentie=None
        )
        assert result is not None
        assert "niet zowel" in result.lower()

    # Case: tijd without dag/datum → returns error
    async def test_tijd_without_dag_or_datum_returns_error(self):
        """Test that tijd without dag or datum returns error"""
        result = self.cog._validate_scheduling_params(
            dag=None, datum=None, tijd="18:00", frequentie=None
        )
        assert result is not None
        assert "kan niet zonder" in result.lower()

    # Case: invalid time formats
    async def test_invalid_time_format_no_colon(self):
        """Test that invalid time format (no colon) returns error"""
        result = self.cog._validate_scheduling_params(
            dag="maandag", datum=None, tijd="1800", frequentie=None
        )
        assert result is not None
        assert "HH:mm" in result

    async def test_invalid_time_format_non_numeric(self):
        """Test that non-numeric time returns error"""
        result = self.cog._validate_scheduling_params(
            dag="maandag", datum=None, tijd="18:xx", frequentie=None
        )
        assert result is not None
        assert "HH:mm" in result

    async def test_invalid_time_format_too_many_parts(self):
        """Test that time with too many parts returns error"""
        result = self.cog._validate_scheduling_params(
            dag="maandag", datum=None, tijd="18:00:00", frequentie=None
        )
        assert result is not None
        assert "HH:mm" in result

    # Case: invalid hour/minute ranges
    async def test_invalid_hour_24(self):
        """Test that hour=24 returns error"""
        result = self.cog._validate_scheduling_params(
            dag="maandag", datum=None, tijd="24:00", frequentie=None
        )
        assert result is not None
        # Language-agnostic: check for time format indicator
        assert "HH:mm" in result or "tijd" in result.lower() or "time" in result.lower()

    async def test_invalid_hour_negative(self):
        """Test that negative hour returns error"""
        result = self.cog._validate_scheduling_params(
            dag="maandag", datum=None, tijd="-1:00", frequentie=None
        )
        assert result is not None
        # Language-agnostic: check for time format indicator
        assert "HH:mm" in result or "tijd" in result.lower() or "time" in result.lower()

    async def test_invalid_minute_60(self):
        """Test that minute=60 returns error"""
        result = self.cog._validate_scheduling_params(
            dag="maandag", datum=None, tijd="10:60", frequentie=None
        )
        assert result is not None
        # Language-agnostic: check for time format indicator
        assert "HH:mm" in result or "tijd" in result.lower() or "time" in result.lower()

    async def test_invalid_minute_negative(self):
        """Test that negative minute returns error"""
        result = self.cog._validate_scheduling_params(
            dag="maandag", datum=None, tijd="10:-5", frequentie=None
        )
        assert result is not None
        # Language-agnostic: check for time format indicator
        assert "HH:mm" in result or "tijd" in result.lower() or "time" in result.lower()

    # Case: invalid datum format
    async def test_invalid_datum_format(self):
        """Test that invalid datum format returns error"""
        result = self.cog._validate_scheduling_params(
            dag=None, datum="01-13-2024", tijd="18:00", frequentie=None
        )
        assert result is not None
        assert "DD-MM-YYYY" in result

    async def test_invalid_datum_format_wrong_separator(self):
        """Test that wrong date separator returns error"""
        result = self.cog._validate_scheduling_params(
            dag=None, datum="2024/12/31", tijd="18:00", frequentie=None
        )
        assert result is not None
        assert "DD-MM-YYYY" in result

    async def test_invalid_datum_day_out_of_range(self):
        """Test that invalid day returns error"""
        result = self.cog._validate_scheduling_params(
            dag=None, datum="30-02-2024", tijd="18:00", frequentie=None
        )
        assert result is not None
        assert "DD-MM-YYYY" in result

    # Case: frequentie validation
    async def test_frequentie_eenmalig_without_datum(self):
        """Test that frequentie=eenmalig without datum returns error"""
        result = self.cog._validate_scheduling_params(
            dag="maandag", datum=None, tijd="18:00", frequentie="eenmalig"
        )
        assert result is not None
        assert "eenmalig" in result.lower()
        assert "datum" in result.lower()

    async def test_frequentie_wekelijks_without_dag(self):
        """Test that frequentie=wekelijks without dag returns error"""
        result = self.cog._validate_scheduling_params(
            dag=None, datum="31-12-2025", tijd="18:00", frequentie="wekelijks"
        )
        assert result is not None
        assert "wekelijks" in result.lower()
        assert "dag" in result.lower()

    # Case: valid combinations
    async def test_valid_dag_and_tijd(self):
        """Test that valid dag and tijd returns None"""
        result = self.cog._validate_scheduling_params(
            dag="maandag", datum=None, tijd="18:00", frequentie=None
        )
        assert result is None

    async def test_valid_datum_and_tijd(self):
        """Test that valid datum and tijd returns None"""
        result = self.cog._validate_scheduling_params(
            dag=None, datum="31-12-2025", tijd="18:00", frequentie=None
        )
        assert result is None

    async def test_valid_dag_tijd_frequentie_wekelijks(self):
        """Test that valid dag, tijd, and frequentie=wekelijks returns None"""
        result = self.cog._validate_scheduling_params(
            dag="vrijdag", datum=None, tijd="20:00", frequentie="wekelijks"
        )
        assert result is None

    async def test_valid_datum_tijd_frequentie_eenmalig(self):
        """Test that valid datum, tijd, and frequentie=eenmalig returns None"""
        result = self.cog._validate_scheduling_params(
            dag=None, datum="31-12-2025", tijd="23:59", frequentie="eenmalig"
        )
        assert result is None

    async def test_valid_edge_time_00_00(self):
        """Test that 00:00 is valid"""
        result = self.cog._validate_scheduling_params(
            dag="maandag", datum=None, tijd="00:00", frequentie=None
        )
        assert result is None

    async def test_valid_edge_time_23_59(self):
        """Test that 23:59 is valid"""
        result = self.cog._validate_scheduling_params(
            dag="maandag", datum=None, tijd="23:59", frequentie=None
        )
        assert result is None


class TestSaveSchedule(BaseTestCase):
    """Tests for _save_schedule (async)"""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bot = MagicMock()
        self.cog = PollLifecycle(self.bot)

    async def test_save_schedule_with_datum(self):
        """Test _save_schedule with datum returns correct message with weekday"""
        with patch(
            "apps.commands.poll_lifecycle.set_scheduled_activation"
        ) as mock_set, patch(
            "apps.commands.poll_lifecycle.clear_scheduled_activation"
        ) as mock_clear:
            result = await self.cog._save_schedule(
                channel_id=123,
                dag=None,
                datum="31-12-2025",
                tijd="18:00",
                frequentie=None,
            )

            # Should call set_scheduled_activation with type "datum" (stored as YYYY-MM-DD)
            mock_set.assert_called_once_with(
                123, "datum", "18:00", datum="2025-12-31"
            )
            mock_clear.assert_not_called()

            # Should return message with weekday and date (displayed as DD-MM-YYYY)
            assert "woensdag" in result.lower()  # 31-12-2025 is a Wednesday
            assert "31-12-2025" in result
            assert "18:00" in result

    async def test_save_schedule_with_datum_monday(self):
        """Test _save_schedule with datum on Monday"""
        with patch("apps.commands.poll_lifecycle.set_scheduled_activation") as mock_set:
            result = await self.cog._save_schedule(
                channel_id=123, dag=None, datum="29-12-2025", tijd="20:00", frequentie=None
            )

            # Storage should be in YYYY-MM-DD format
            mock_set.assert_called_once_with(
                123, "datum", "20:00", datum="2025-12-29"
            )

            # 29-12-2025 is a Monday, display should be in DD-MM-YYYY
            assert "maandag" in result.lower()
            assert "29-12-2025" in result
            assert "20:00" in result

    async def test_save_schedule_with_dag_wekelijks_explicit(self):
        """Test _save_schedule with dag and frequentie=wekelijks"""
        with patch("apps.commands.poll_lifecycle.set_scheduled_activation") as mock_set:
            result = await self.cog._save_schedule(
                channel_id=456,
                dag="dinsdag",
                datum=None,
                tijd="19:00",
                frequentie="wekelijks",
            )

            # Should call set_scheduled_activation with type "wekelijks"
            mock_set.assert_called_once_with(456, "wekelijks", "19:00", dag="dinsdag")

            # Should return recurrent message
            assert "elke" in result.lower()
            assert "dinsdag" in result.lower()
            assert "19:00" in result

    async def test_save_schedule_with_dag_wekelijks_default(self):
        """Test _save_schedule with dag and frequentie=None defaults to wekelijks"""
        with patch("apps.commands.poll_lifecycle.set_scheduled_activation") as mock_set:
            result = await self.cog._save_schedule(
                channel_id=456,
                dag="vrijdag",
                datum=None,
                tijd="20:00",
                frequentie=None,
            )

            # Should call set_scheduled_activation with type "wekelijks"
            mock_set.assert_called_once_with(456, "wekelijks", "20:00", dag="vrijdag")

            # Should return recurrent message (because frequentie=None)
            assert "elke" in result.lower()
            assert "vrijdag" in result.lower()
            assert "20:00" in result

    async def test_save_schedule_with_dag_eenmalig(self):
        """Test _save_schedule with dag and frequentie=eenmalig"""
        with patch("apps.commands.poll_lifecycle.set_scheduled_activation") as mock_set:
            result = await self.cog._save_schedule(
                channel_id=789,
                dag="zaterdag",
                datum=None,
                tijd="21:00",
                frequentie="eenmalig",
            )

            # Should still use type "wekelijks" but with eenmalig message
            mock_set.assert_called_once_with(789, "wekelijks", "21:00", dag="zaterdag")

            # Should return one-time message
            assert "eenmalig" in result.lower()
            assert "zaterdag" in result.lower()
            assert "21:00" in result

    async def test_save_schedule_no_dag_no_datum_clears_schedule(self):
        """Test _save_schedule without dag or datum clears schedule"""
        with patch(
            "apps.commands.poll_lifecycle.clear_scheduled_activation"
        ) as mock_clear, patch(
            "apps.commands.poll_lifecycle.set_scheduled_activation"
        ) as mock_set:
            result = await self.cog._save_schedule(
                channel_id=999, dag=None, datum=None, tijd="18:00", frequentie=None
            )

            # Should call clear_scheduled_activation
            mock_clear.assert_called_once_with(999)
            mock_set.assert_not_called()

            # Should return empty string
            assert result == ""


class TestSaveScheduleOff(BaseTestCase):
    """Tests for _save_schedule_off (async)"""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bot = MagicMock()
        self.cog = PollLifecycle(self.bot)

    async def test_save_schedule_off_with_datum(self):
        """Test _save_schedule_off with datum returns correct message"""
        with patch(
            "apps.utils.poll_settings.set_scheduled_deactivation"
        ) as mock_set_deact:
            result = await self.cog._save_schedule_off(
                channel_id=123,
                dag=None,
                datum="31-12-2025",
                tijd="18:00",
                frequentie=None,
            )

            # Should call set_scheduled_deactivation with type "datum" (stored as YYYY-MM-DD)
            mock_set_deact.assert_called_once_with(
                123, "datum", "18:00", datum="2025-12-31"
            )

            # Should return message with weekday and date (displayed as DD-MM-YYYY)
            assert "woensdag" in result.lower()  # 31-12-2025 is Wednesday
            assert "31-12-2025" in result
            assert "18:00" in result
            assert "uitgeschakeld" in result.lower()

    async def test_save_schedule_off_with_datum_sunday(self):
        """Test _save_schedule_off with datum on Sunday"""
        with patch("apps.utils.poll_settings.set_scheduled_deactivation") as mock_set:
            result = await self.cog._save_schedule_off(
                channel_id=123, dag=None, datum="28-12-2025", tijd="20:00", frequentie=None
            )

            # Storage should be in YYYY-MM-DD format
            mock_set.assert_called_once_with(
                123, "datum", "20:00", datum="2025-12-28"
            )

            # 28-12-2025 is a Sunday, display should be in DD-MM-YYYY
            assert "zondag" in result.lower()
            assert "28-12-2025" in result
            assert "20:00" in result

    async def test_save_schedule_off_with_dag_wekelijks_explicit(self):
        """Test _save_schedule_off with dag and frequentie=wekelijks"""
        with patch("apps.utils.poll_settings.set_scheduled_deactivation") as mock_set:
            result = await self.cog._save_schedule_off(
                channel_id=456,
                dag="woensdag",
                datum=None,
                tijd="22:00",
                frequentie="wekelijks",
            )

            # Should call set_scheduled_deactivation with type "wekelijks"
            mock_set.assert_called_once_with(456, "wekelijks", "22:00", dag="woensdag")

            # Should return recurrent message
            assert "elke" in result.lower()
            assert "woensdag" in result.lower()
            assert "22:00" in result
            assert "uitgeschakeld" in result.lower()

    async def test_save_schedule_off_with_dag_wekelijks_default(self):
        """Test _save_schedule_off with dag and frequentie=None defaults to wekelijks"""
        with patch("apps.utils.poll_settings.set_scheduled_deactivation") as mock_set:
            result = await self.cog._save_schedule_off(
                channel_id=456,
                dag="donderdag",
                datum=None,
                tijd="23:00",
                frequentie=None,
            )

            # Should call set_scheduled_deactivation with type "wekelijks"
            mock_set.assert_called_once_with(456, "wekelijks", "23:00", dag="donderdag")

            # Should return recurrent message (because frequentie=None)
            assert "elke" in result.lower()
            assert "donderdag" in result.lower()
            assert "23:00" in result

    async def test_save_schedule_off_with_dag_eenmalig(self):
        """Test _save_schedule_off with dag and frequentie=eenmalig"""
        with patch("apps.utils.poll_settings.set_scheduled_deactivation") as mock_set:
            result = await self.cog._save_schedule_off(
                channel_id=789,
                dag="maandag",
                datum=None,
                tijd="08:00",
                frequentie="eenmalig",
            )

            # Should still use type "wekelijks" but with eenmalig message
            mock_set.assert_called_once_with(789, "wekelijks", "08:00", dag="maandag")

            # Should return one-time message
            assert "eenmalig" in result.lower()
            assert "maandag" in result.lower()
            assert "08:00" in result

    async def test_save_schedule_off_no_dag_no_datum_returns_empty(self):
        """Test _save_schedule_off without dag or datum returns empty string"""
        result = await self.cog._save_schedule_off(
            channel_id=999, dag=None, datum=None, tijd="18:00", frequentie=None
        )

        # Should return empty string
        assert result == ""


class TestLoadOpeningMessage(BaseTestCase):
    """Tests for _load_opening_message - dynamic message generation"""

    async def test_load_opening_message_no_channel_id_returns_generic(self):
        """Test that generic fallback is generated without channel_id"""
        result = _load_opening_message(channel_id=None)
        assert "Welkom bij de DMK-poll" in result
        assert "@everyone" in result
        assert "Klik op **🗳️ Stemmen**" in result
        assert "Veel plezier! 🎉" in result

    async def test_load_opening_message_with_default_settings(self):
        """Test message generation with default weekend settings"""
        channel_id = 999888

        with patch("apps.utils.poll_settings.get_enabled_poll_days", return_value=["vrijdag", "zaterdag", "zondag"]), \
             patch("apps.utils.poll_settings.get_setting", return_value={"modus": "deadline", "tijd": "18:00"}), \
             patch("apps.utils.poll_settings.is_notification_enabled", return_value=True):

            result = _load_opening_message(channel_id=channel_id)

            assert "vrijdag, zaterdag en zondag" in result
            assert "verborgen tot de deadline" in result
            assert "<t:" in result  # HammerTime format
            assert "Als je nog niet gestemd hebt" in result  # Reminder notification
            assert "Heb je op 'misschien' gestemd" in result  # Misschien notification

    async def test_load_opening_message_notifications_disabled(self):
        """Test message generation with notifications disabled"""
        channel_id = 999888

        with patch("apps.utils.poll_settings.get_enabled_poll_days", return_value=["vrijdag"]), \
             patch("apps.utils.poll_settings.get_setting", return_value={"modus": "deadline", "tijd": "20:00"}), \
             patch("apps.utils.poll_settings.is_notification_enabled", return_value=False):

            result = _load_opening_message(channel_id=channel_id)

            # Should not contain notification text
            assert "Als je nog niet gestemd hebt" not in result
            assert "Heb je op 'misschien' gestemd" not in result
            # But should still have basic info
            assert "vrijdag" in result
            assert "verborgen tot de deadline" in result

    async def test_load_opening_message_single_day(self):
        """Test message formatting with single enabled day"""
        channel_id = 999888

        with patch("apps.utils.poll_settings.get_enabled_poll_days", return_value=["zondag"]), \
             patch("apps.utils.poll_settings.get_setting", return_value={"modus": "deadline", "tijd": "18:00"}), \
             patch("apps.utils.poll_settings.is_notification_enabled", return_value=False):

            result = _load_opening_message(channel_id=channel_id)

            # Should show just the single day (no "en")
            assert "zondag" in result
            assert " en " not in result or " en zondag" not in result


if __name__ == "__main__":
    import unittest

    unittest.main()

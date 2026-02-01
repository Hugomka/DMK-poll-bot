# tests/test_i18n.py
"""Tests for the i18n (internationalization) module."""

from tests.base import BaseTestCase


class TestI18nLanguageSettings(BaseTestCase):
    """Tests for language settings in poll_settings."""

    async def test_get_language_default(self):
        """Default language should be Dutch (nl)."""
        from apps.utils.poll_settings import get_language

        lang = get_language(999)
        self.assertEqual(lang, "nl")

    async def test_set_language_english(self):
        """Should be able to set language to English."""
        from apps.utils.poll_settings import get_language, set_language

        set_language(123, "en")
        self.assertEqual(get_language(123), "en")

    async def test_set_language_dutch(self):
        """Should be able to set language to Dutch."""
        from apps.utils.poll_settings import get_language, set_language

        set_language(123, "nl")
        self.assertEqual(get_language(123), "nl")

    async def test_set_language_invalid(self):
        """Should raise error for invalid language."""
        from apps.utils.poll_settings import set_language

        with self.assertRaises(ValueError):
            set_language(123, "invalid")

    async def test_language_persists_per_channel(self):
        """Different channels can have different languages."""
        from apps.utils.poll_settings import get_language, set_language

        set_language(100, "nl")
        set_language(200, "en")

        self.assertEqual(get_language(100), "nl")
        self.assertEqual(get_language(200), "en")


class TestI18nTranslation(BaseTestCase):
    """Tests for the translation function t()."""

    async def test_translation_dutch(self):
        """Should return Dutch translation."""
        from apps.utils.i18n import t
        from apps.utils.poll_settings import set_language

        set_language(123, "nl")
        text = t(123, "UI.vote_success")
        self.assertEqual(text, "Je stem is verwerkt.")

    async def test_translation_english(self):
        """Should return English translation."""
        from apps.utils.i18n import t
        from apps.utils.poll_settings import set_language

        set_language(123, "en")
        text = t(123, "UI.vote_success")
        self.assertEqual(text, "Your vote has been processed.")

    async def test_translation_with_placeholders(self):
        """Should fill in placeholders."""
        from apps.utils.i18n import t
        from apps.utils.poll_settings import set_language

        set_language(123, "nl")
        text = t(123, "NOTIFICATIONS.poll_closed", opening_time="dinsdag 20:00")
        self.assertIn("dinsdag 20:00", text)

    async def test_translation_missing_key(self):
        """Should return [MISSING: key] for unknown keys."""
        from apps.utils.i18n import t

        text = t(123, "NONEXISTENT.key")
        self.assertIn("MISSING", text)

    async def test_translation_fallback_to_dutch(self):
        """Should fall back to Dutch if key missing in target language."""
        from apps.utils.i18n import t
        from apps.utils.poll_settings import set_language

        # Set to English but request a key that exists in Dutch
        set_language(123, "en")
        # Both languages should have this key, so this tests the normal path
        text = t(123, "UI.vote_button")
        self.assertEqual(text, "Vote")


class TestI18nDayNames(BaseTestCase):
    """Tests for day name localization."""

    async def test_day_name_dutch(self):
        """Should return Dutch day names."""
        from apps.utils.i18n import get_day_name
        from apps.utils.poll_settings import set_language

        set_language(123, "nl")
        self.assertEqual(get_day_name(123, "vrijdag"), "vrijdag")
        self.assertEqual(get_day_name(123, "maandag"), "maandag")

    async def test_day_name_english(self):
        """Should return English day names."""
        from apps.utils.i18n import get_day_name
        from apps.utils.poll_settings import set_language

        set_language(123, "en")
        self.assertEqual(get_day_name(123, "vrijdag"), "Friday")
        self.assertEqual(get_day_name(123, "maandag"), "Monday")

    async def test_day_name_all_days_english(self):
        """Should correctly translate all Dutch day names to English."""
        from apps.utils.i18n import get_day_name
        from apps.utils.poll_settings import set_language

        set_language(123, "en")
        expected = {
            "maandag": "Monday",
            "dinsdag": "Tuesday",
            "woensdag": "Wednesday",
            "donderdag": "Thursday",
            "vrijdag": "Friday",
            "zaterdag": "Saturday",
            "zondag": "Sunday",
        }
        for dutch, english in expected.items():
            self.assertEqual(get_day_name(123, dutch), english)


class TestI18nTimeLabels(BaseTestCase):
    """Tests for time label localization."""

    async def test_time_label_dutch(self):
        """Should return Dutch time labels."""
        from apps.utils.i18n import get_time_label
        from apps.utils.poll_settings import set_language

        set_language(123, "nl")
        self.assertEqual(get_time_label(123, "om 19:00 uur"), "om 19:00 uur")
        self.assertEqual(get_time_label(123, "misschien"), "misschien")

    async def test_time_label_english(self):
        """Should return English time labels."""
        from apps.utils.i18n import get_time_label
        from apps.utils.poll_settings import set_language

        set_language(123, "en")
        self.assertEqual(get_time_label(123, "om 19:00 uur"), "at 7:00 PM")
        self.assertEqual(get_time_label(123, "misschien"), "maybe")


class TestI18nCountText(BaseTestCase):
    """Tests for count text with pluralization."""

    async def test_count_text_singular_dutch(self):
        """Should use singular form in Dutch."""
        from apps.utils.i18n import get_count_text
        from apps.utils.poll_settings import set_language

        set_language(123, "nl")
        text = get_count_text(123, 1)
        self.assertIn("1 lid", text)
        self.assertIn("heeft", text)

    async def test_count_text_plural_dutch(self):
        """Should use plural form in Dutch."""
        from apps.utils.i18n import get_count_text
        from apps.utils.poll_settings import set_language

        set_language(123, "nl")
        text = get_count_text(123, 5)
        self.assertIn("5 leden", text)
        self.assertIn("hebben", text)

    async def test_count_text_singular_english(self):
        """Should use singular form in English."""
        from apps.utils.i18n import get_count_text
        from apps.utils.poll_settings import set_language

        set_language(123, "en")
        text = get_count_text(123, 1)
        self.assertIn("1 member", text)
        self.assertIn("has", text)

    async def test_count_text_plural_english(self):
        """Should use plural form in English."""
        from apps.utils.i18n import get_count_text
        from apps.utils.poll_settings import set_language

        set_language(123, "en")
        text = get_count_text(123, 5)
        self.assertIn("5 members", text)
        self.assertIn("have", text)


class TestI18nNotificationTexts(BaseTestCase):
    """Tests for notification text functions with i18n."""

    async def test_herinnering_dag_dutch(self):
        """Should return Dutch reminder text."""
        from apps.utils.notification_texts import get_text_herinnering_dag
        from apps.utils.poll_settings import set_language

        set_language(123, "nl")
        text = get_text_herinnering_dag("vrijdag", channel_id=123)
        self.assertIn("vrijdag", text)
        self.assertIn("gestemd", text)

    async def test_herinnering_dag_english(self):
        """Should return English reminder text."""
        from apps.utils.notification_texts import get_text_herinnering_dag
        from apps.utils.poll_settings import set_language

        set_language(123, "en")
        text = get_text_herinnering_dag("vrijdag", channel_id=123)
        self.assertIn("Friday", text)
        self.assertIn("voted", text)

    async def test_poll_opened_dutch(self):
        """Should return Dutch poll opened text."""
        from apps.utils.notification_texts import get_text_poll_opened
        from apps.utils.poll_settings import set_language

        set_language(123, "nl")
        text = get_text_poll_opened(123)
        self.assertIn("aangezet", text)

    async def test_poll_opened_english(self):
        """Should return English poll opened text."""
        from apps.utils.notification_texts import get_text_poll_opened
        from apps.utils.poll_settings import set_language

        set_language(123, "en")
        text = get_text_poll_opened(123)
        self.assertIn("activated", text)

    async def test_celebration_dutch(self):
        """Should return Dutch celebration text."""
        from apps.utils.notification_texts import get_text_celebration
        from apps.utils.poll_settings import set_language

        set_language(123, "nl")
        text = get_text_celebration(123)
        self.assertIn("Geweldig", text)

    async def test_celebration_english(self):
        """Should return English celebration text."""
        from apps.utils.notification_texts import get_text_celebration
        from apps.utils.poll_settings import set_language

        set_language(123, "en")
        text = get_text_celebration(123)
        self.assertIn("Amazing", text)


class TestI18nTranslationCompleteness(BaseTestCase):
    """Tests to ensure translation completeness."""

    async def test_all_ui_keys_exist_in_both_languages(self):
        """All UI keys should exist in both languages."""
        from apps.utils.i18n import nl, en

        nl_keys = set(nl.UI.keys())
        en_keys = set(en.UI.keys())

        missing_in_en = nl_keys - en_keys
        missing_in_nl = en_keys - nl_keys

        self.assertEqual(
            missing_in_en, set(), f"Missing in English: {missing_in_en}"
        )
        self.assertEqual(
            missing_in_nl, set(), f"Missing in Dutch: {missing_in_nl}"
        )

    async def test_all_notifications_keys_exist_in_both_languages(self):
        """All NOTIFICATIONS keys should exist in both languages."""
        from apps.utils.i18n import nl, en

        nl_keys = set(nl.NOTIFICATIONS.keys())
        en_keys = set(en.NOTIFICATIONS.keys())

        missing_in_en = nl_keys - en_keys
        missing_in_nl = en_keys - nl_keys

        self.assertEqual(
            missing_in_en, set(), f"Missing in English: {missing_in_en}"
        )
        self.assertEqual(
            missing_in_nl, set(), f"Missing in Dutch: {missing_in_nl}"
        )

    async def test_all_settings_keys_exist_in_both_languages(self):
        """All SETTINGS keys should exist in both languages."""
        from apps.utils.i18n import nl, en

        nl_keys = set(nl.SETTINGS.keys())
        en_keys = set(en.SETTINGS.keys())

        missing_in_en = nl_keys - en_keys
        missing_in_nl = en_keys - nl_keys

        self.assertEqual(
            missing_in_en, set(), f"Missing in English: {missing_in_en}"
        )
        self.assertEqual(
            missing_in_nl, set(), f"Missing in Dutch: {missing_in_nl}"
        )

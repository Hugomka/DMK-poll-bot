# tests/test_notification_texts.py

import unittest

from apps.utils.notification_texts import (
    NOTIFICATION_TEXTS,
    NotificationText,
    format_notification_text,
    format_opening_time_from_schedule,
    get_all_notification_names,
    get_notification_by_name,
    get_text_herinnering_dag,
    get_text_herinnering_weekend,
    get_text_poll_gesloten,
)


class TestNotificationTextHelpers(unittest.TestCase):
    """Test helper functies voor notificatieteksten."""

    def test_get_text_herinnering_dag_without_non_voters(self):
        """Test herinnering voor dag zonder niet-stemmers."""
        result = get_text_herinnering_dag("vrijdag")
        self.assertIn("DMK-poll - **vrijdag**", result)
        self.assertIn("Als je nog niet gestemd hebt voor **vrijdag**", result)
        # Geen count_text
        self.assertNotIn("lid", result.lower())
        self.assertNotIn("leden", result.lower())

    def test_get_text_herinnering_dag_with_one_non_voter(self):
        """Test herinnering voor dag met 1 niet-stemmer (enkelvoud)."""
        non_voters = ["Alice"]
        result = get_text_herinnering_dag("zaterdag", non_voters)
        self.assertIn("**1 lid** heeft nog niet gestemd", result)
        self.assertIn("DMK-poll - **zaterdag**", result)

    def test_get_text_herinnering_dag_with_multiple_non_voters(self):
        """Test herinnering voor dag met meerdere niet-stemmers (meervoud)."""
        non_voters = ["Alice", "Bob", "Charlie"]
        result = get_text_herinnering_dag("zondag", non_voters)
        self.assertIn("**3 leden** hebben nog niet gestemd", result)
        self.assertIn("DMK-poll - **zondag**", result)

    def test_get_text_herinnering_dag_with_empty_list(self):
        """Test herinnering met lege lijst (moet zelfde zijn als None)."""
        result = get_text_herinnering_dag("vrijdag", [])
        self.assertNotIn("lid", result.lower())
        self.assertNotIn("leden", result.lower())

    def test_get_text_herinnering_weekend_without_non_voters(self):
        """Test weekend herinnering zonder niet-stemmers."""
        result = get_text_herinnering_weekend()
        self.assertIn("DMK-poll - herinnering", result)
        self.assertIn("Als je nog niet gestemd hebt voor dit weekend", result)
        # Geen count_text
        self.assertNotIn("lid", result.lower())
        self.assertNotIn("leden", result.lower())

    def test_get_text_herinnering_weekend_with_one_non_voter(self):
        """Test weekend herinnering met 1 niet-stemmer (enkelvoud)."""
        non_voters = ["Alice"]
        result = get_text_herinnering_weekend(non_voters)
        self.assertIn("**1 lid** heeft nog niet gestemd", result)
        self.assertIn("DMK-poll - herinnering", result)

    def test_get_text_herinnering_weekend_with_multiple_non_voters(self):
        """Test weekend herinnering met meerdere niet-stemmers (meervoud)."""
        non_voters = ["Alice", "Bob"]
        result = get_text_herinnering_weekend(non_voters)
        self.assertIn("**2 leden** hebben nog niet gestemd", result)

    def test_get_text_poll_gesloten_default(self):
        """Test poll gesloten tekst met default opening tijd."""
        result = get_text_poll_gesloten()
        self.assertIn("Deze poll is gesloten", result)
        self.assertIn("Dank voor je deelname", result)

    def test_get_text_poll_gesloten_custom_time(self):
        """Test poll gesloten tekst met custom opening tijd (kan Hammertime zijn)."""
        result = get_text_poll_gesloten("vrijdag om 19:30 uur")
        self.assertIn("Deze poll is gesloten", result)
        self.assertIn("**vrijdag om 19:30 uur** weer open", result)

    def test_get_text_poll_gesloten_with_hammertime(self):
        """Test poll gesloten tekst met Hammertime format."""
        result = get_text_poll_gesloten("<t:1234567890:F>")
        self.assertIn("Deze poll is gesloten", result)
        self.assertIn("**<t:1234567890:F>** weer open", result)


class TestFormatOpeningTimeFromSchedule(unittest.TestCase):
    """Test DRY functie voor formatteren van opening tijd met Hammertime."""

    def test_format_none_schedule_returns_hammertime(self):
        """Test dat None schedule Hammertime teruggeeft voor volgende dinsdag 20:00."""
        result = format_opening_time_from_schedule(None)
        # Moet Hammertime format zijn
        self.assertTrue(result.startswith("<t:"))
        self.assertTrue(result.endswith(":F>"))

    def test_format_wekelijks_schedule_with_default_day(self):
        """Test wekelijks schema zonder expliciete dag (default dinsdag) geeft Hammertime."""
        schedule = {"type": "wekelijks", "tijd": "20:00"}
        result = format_opening_time_from_schedule(schedule)
        # Moet Hammertime format zijn
        self.assertTrue(result.startswith("<t:"))
        self.assertTrue(result.endswith(":F>"))

    def test_format_wekelijks_schedule_with_custom_day(self):
        """Test wekelijks schema met custom dag en tijd geeft Hammertime."""
        schedule = {"type": "wekelijks", "dag": "vrijdag", "tijd": "19:30"}
        result = format_opening_time_from_schedule(schedule)
        # Moet Hammertime format zijn
        self.assertTrue(result.startswith("<t:"))
        self.assertTrue(result.endswith(":F>"))

    def test_format_wekelijks_all_days(self):
        """Test wekelijks schema voor alle dagen geeft Hammertime."""
        dagen = [
            "maandag",
            "dinsdag",
            "woensdag",
            "donderdag",
            "vrijdag",
            "zaterdag",
            "zondag",
        ]
        for dag in dagen:
            schedule = {"type": "wekelijks", "dag": dag, "tijd": "18:00"}
            result = format_opening_time_from_schedule(schedule)
            # Moet Hammertime format zijn voor elke dag
            self.assertTrue(result.startswith("<t:"), f"Failed for {dag}")
            self.assertTrue(result.endswith(":F>"), f"Failed for {dag}")

    def test_format_datum_schedule_valid_date(self):
        """Test datum schema met geldige datum geeft Hammertime."""
        schedule = {"type": "datum", "datum": "2025-11-15", "tijd": "19:30"}
        result = format_opening_time_from_schedule(schedule)
        # Moet Hammertime format zijn
        self.assertTrue(result.startswith("<t:"))
        self.assertTrue(result.endswith(":F>"))

    def test_format_datum_schedule_monday(self):
        """Test datum schema voor maandag geeft Hammertime."""
        schedule = {"type": "datum", "datum": "2025-11-03", "tijd": "12:00"}
        result = format_opening_time_from_schedule(schedule)
        # Moet Hammertime format zijn
        self.assertTrue(result.startswith("<t:"))
        self.assertTrue(result.endswith(":F>"))

    def test_format_datum_schedule_sunday(self):
        """Test datum schema voor zondag geeft Hammertime."""
        schedule = {"type": "datum", "datum": "2025-11-09", "tijd": "14:00"}
        result = format_opening_time_from_schedule(schedule)
        # Moet Hammertime format zijn
        self.assertTrue(result.startswith("<t:"))
        self.assertTrue(result.endswith(":F>"))

    def test_format_datum_schedule_invalid_date(self):
        """Test datum schema met ongeldige datum (fallback naar text)."""
        schedule = {"type": "datum", "datum": "invalid-date", "tijd": "19:30"}
        result = format_opening_time_from_schedule(schedule)
        # Bij fout: datum as-is met tijd (fallback)
        self.assertEqual(result, "invalid-date om 19:30")

    def test_format_datum_schedule_missing_datum(self):
        """Test datum schema zonder datum veld (fallback naar text)."""
        schedule = {"type": "datum", "tijd": "19:30"}
        result = format_opening_time_from_schedule(schedule)
        # Leeg datum veld (fallback)
        self.assertEqual(result, " om 19:30")

    def test_format_datum_schedule_default_tijd(self):
        """Test datum schema zonder tijd (default 20:00) geeft Hammertime."""
        schedule = {"type": "datum", "datum": "2025-11-15"}
        result = format_opening_time_from_schedule(schedule)
        # Moet Hammertime format zijn
        self.assertTrue(result.startswith("<t:"))
        self.assertTrue(result.endswith(":F>"))

    def test_format_unknown_schedule_type_returns_hammertime(self):
        """Test onbekend schema type geeft Hammertime terug voor default dinsdag."""
        schedule = {"type": "unknown", "tijd": "12:00"}
        result = format_opening_time_from_schedule(schedule)
        # Moet Hammertime format zijn
        self.assertTrue(result.startswith("<t:"))
        self.assertTrue(result.endswith(":F>"))

    def test_format_empty_schedule_returns_hammertime(self):
        """Test leeg schema dict geeft Hammertime terug voor default dinsdag."""
        schedule = {}
        result = format_opening_time_from_schedule(schedule)
        # Moet Hammertime format zijn
        self.assertTrue(result.startswith("<t:"))
        self.assertTrue(result.endswith(":F>"))


class TestNotificationTextsList(unittest.TestCase):
    """Test NOTIFICATION_TEXTS lijst en gerelateerde functies."""

    def test_notification_texts_has_expected_count(self):
        """Test dat NOTIFICATION_TEXTS 8 items heeft."""
        self.assertEqual(len(NOTIFICATION_TEXTS), 8)

    def test_all_notification_texts_are_namedtuples(self):
        """Test dat alle items NotificationText namedtuples zijn."""
        for notif in NOTIFICATION_TEXTS:
            self.assertIsInstance(notif, NotificationText)
            self.assertTrue(hasattr(notif, "name"))
            self.assertTrue(hasattr(notif, "content"))

    def test_notification_names_are_unique(self):
        """Test dat alle notificatie namen uniek zijn."""
        names = [notif.name for notif in NOTIFICATION_TEXTS]
        self.assertEqual(len(names), len(set(names)))

    def test_get_all_notification_names_returns_list(self):
        """Test dat get_all_notification_names lijst teruggeeft."""
        names = get_all_notification_names()
        self.assertIsInstance(names, list)
        self.assertEqual(len(names), 8)

    def test_get_all_notification_names_contains_expected_names(self):
        """Test dat alle verwachte namen aanwezig zijn."""
        names = get_all_notification_names()
        expected = [
            "Poll geopend",
            "Poll gereset",
            "Poll gesloten",
            "Herinnering vrijdag",
            "Herinnering zaterdag",
            "Herinnering zondag",
            "Herinnering weekend",
            "Felicitatie (iedereen gestemd)",
        ]
        self.assertEqual(names, expected)

    def test_get_notification_by_name_existing(self):
        """Test get_notification_by_name met bestaande naam."""
        notif = get_notification_by_name("Poll geopend")
        self.assertIsNotNone(notif)
        assert notif is not None  # Type narrowing voor Pylance
        self.assertEqual(notif.name, "Poll geopend")
        self.assertIn("aangezet", notif.content)

    def test_get_notification_by_name_all_notifications(self):
        """Test get_notification_by_name voor alle notificaties."""
        for name in get_all_notification_names():
            notif = get_notification_by_name(name)
            self.assertIsNotNone(notif)
            assert notif is not None  # Type narrowing voor Pylance
            self.assertEqual(notif.name, name)

    def test_get_notification_by_name_non_existing(self):
        """Test get_notification_by_name met niet-bestaande naam."""
        notif = get_notification_by_name("Niet bestaand")
        self.assertIsNone(notif)

    def test_notification_poll_geopend_content(self):
        """Test content van Poll geopend notificatie."""
        notif = get_notification_by_name("Poll geopend")
        self.assertIsNotNone(notif)
        assert notif is not None  # Type narrowing voor Pylance
        self.assertIn("DMK-poll-bot is zojuist aangezet", notif.content)
        self.assertIn("🎮", notif.content)

    def test_notification_poll_gereset_content(self):
        """Test content van Poll gereset notificatie."""
        notif = get_notification_by_name("Poll gereset")
        self.assertIsNotNone(notif)
        assert notif is not None  # Type narrowing voor Pylance
        self.assertIn("gereset voor het nieuwe weekend", notif.content)

    def test_notification_poll_gesloten_has_hammertime(self):
        """Test dat Poll gesloten Hammertime format gebruikt."""
        notif = get_notification_by_name("Poll gesloten")
        self.assertIsNotNone(notif)
        assert notif is not None  # Type narrowing voor Pylance
        # Moet Hammertime format bevatten
        self.assertIn("<t:", notif.content)
        self.assertIn(":F>", notif.content)


class TestFormatNotificationText(unittest.TestCase):
    """Test format_notification_text functie voor placeholder vervanging."""

    def test_format_with_valid_placeholders(self):
        """Test formatteren met geldige placeholders."""
        text = "Hallo {naam}, welkom bij {plaats}!"
        result = format_notification_text(text, naam="Alice", plaats="Discord")
        self.assertEqual(result, "Hallo Alice, welkom bij Discord!")

    def test_format_with_missing_placeholder(self):
        """Test formatteren met ontbrekende placeholder (moet origineel teruggeven)."""
        text = "Hallo {naam}, welkom bij {plaats}!"
        result = format_notification_text(text, naam="Alice")
        # KeyError → return origineel
        self.assertEqual(result, "Hallo {naam}, welkom bij {plaats}!")

    def test_format_without_placeholders(self):
        """Test formatteren zonder placeholders."""
        text = "Gewone tekst zonder placeholders"
        result = format_notification_text(text)
        self.assertEqual(result, "Gewone tekst zonder placeholders")

    def test_format_with_empty_text(self):
        """Test formatteren met lege string."""
        result = format_notification_text("")
        self.assertEqual(result, "")

    def test_format_with_extra_kwargs(self):
        """Test formatteren met extra kwargs die niet gebruikt worden."""
        text = "Hallo {naam}!"
        result = format_notification_text(text, naam="Alice", extra="ignored")
        self.assertEqual(result, "Hallo Alice!")


if __name__ == "__main__":
    unittest.main()

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
        self.assertIn("**dinsdag om 20:00 uur** weer open", result)
        self.assertIn("Dank voor je deelname", result)

    def test_get_text_poll_gesloten_custom_time(self):
        """Test poll gesloten tekst met custom opening tijd."""
        result = get_text_poll_gesloten("vrijdag om 19:30 uur")
        self.assertIn("Deze poll is gesloten", result)
        self.assertIn("**vrijdag om 19:30 uur** weer open", result)


class TestFormatOpeningTimeFromSchedule(unittest.TestCase):
    """Test DRY functie voor formatteren van opening tijd."""

    def test_format_none_schedule_returns_default(self):
        """Test dat None schedule default tijd teruggeeft."""
        result = format_opening_time_from_schedule(None)
        self.assertEqual(result, "dinsdag om 20:00 uur")

    def test_format_wekelijks_schedule_with_default_day(self):
        """Test wekelijks schema zonder expliciete dag (default dinsdag)."""
        schedule = {"type": "wekelijks", "tijd": "20:00"}
        result = format_opening_time_from_schedule(schedule)
        self.assertEqual(result, "dinsdag om 20:00")

    def test_format_wekelijks_schedule_with_custom_day(self):
        """Test wekelijks schema met custom dag en tijd."""
        schedule = {"type": "wekelijks", "dag": "vrijdag", "tijd": "19:30"}
        result = format_opening_time_from_schedule(schedule)
        self.assertEqual(result, "vrijdag om 19:30")

    def test_format_wekelijks_all_days(self):
        """Test wekelijks schema voor alle dagen van de week."""
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
            self.assertEqual(result, f"{dag} om 18:00")

    def test_format_datum_schedule_valid_date(self):
        """Test datum schema met geldige datum."""
        schedule = {"type": "datum", "datum": "2025-11-15", "tijd": "19:30"}
        result = format_opening_time_from_schedule(schedule)
        # 2025-11-15 is een zaterdag
        self.assertEqual(result, "zaterdag 15-11-2025 om 19:30")

    def test_format_datum_schedule_monday(self):
        """Test datum schema voor maandag."""
        schedule = {"type": "datum", "datum": "2025-11-03", "tijd": "12:00"}
        result = format_opening_time_from_schedule(schedule)
        # 2025-11-03 is een maandag
        self.assertEqual(result, "maandag 03-11-2025 om 12:00")

    def test_format_datum_schedule_sunday(self):
        """Test datum schema voor zondag."""
        schedule = {"type": "datum", "datum": "2025-11-09", "tijd": "14:00"}
        result = format_opening_time_from_schedule(schedule)
        # 2025-11-09 is een zondag
        self.assertEqual(result, "zondag 09-11-2025 om 14:00")

    def test_format_datum_schedule_invalid_date(self):
        """Test datum schema met ongeldige datum (fallback)."""
        schedule = {"type": "datum", "datum": "invalid-date", "tijd": "19:30"}
        result = format_opening_time_from_schedule(schedule)
        # Bij fout: datum as-is met tijd
        self.assertEqual(result, "invalid-date om 19:30")

    def test_format_datum_schedule_missing_datum(self):
        """Test datum schema zonder datum veld."""
        schedule = {"type": "datum", "tijd": "19:30"}
        result = format_opening_time_from_schedule(schedule)
        # Leeg datum veld
        self.assertEqual(result, " om 19:30")

    def test_format_datum_schedule_default_tijd(self):
        """Test datum schema zonder tijd (default 20:00)."""
        schedule = {"type": "datum", "datum": "2025-11-15"}
        result = format_opening_time_from_schedule(schedule)
        self.assertEqual(result, "zaterdag 15-11-2025 om 20:00")

    def test_format_unknown_schedule_type_returns_default(self):
        """Test onbekend schema type geeft default terug."""
        schedule = {"type": "unknown", "tijd": "12:00"}
        result = format_opening_time_from_schedule(schedule)
        self.assertEqual(result, "dinsdag om 20:00 uur")

    def test_format_empty_schedule_returns_default(self):
        """Test leeg schema dict geeft default terug."""
        schedule = {}
        result = format_opening_time_from_schedule(schedule)
        self.assertEqual(result, "dinsdag om 20:00 uur")


class TestNotificationTextsList(unittest.TestCase):
    """Test NOTIFICATION_TEXTS lijst en gerelateerde functies."""

    def test_notification_texts_has_expected_count(self):
        """Test dat NOTIFICATION_TEXTS 7 items heeft."""
        self.assertEqual(len(NOTIFICATION_TEXTS), 7)

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
        self.assertEqual(len(names), 7)

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
        ]
        self.assertEqual(names, expected)

    def test_get_notification_by_name_existing(self):
        """Test get_notification_by_name met bestaande naam."""
        notif = get_notification_by_name("Poll geopend")
        self.assertIsNotNone(notif)
        self.assertEqual(notif.name, "Poll geopend")
        self.assertIn("aangezet", notif.content)

    def test_get_notification_by_name_all_notifications(self):
        """Test get_notification_by_name voor alle notificaties."""
        for name in get_all_notification_names():
            notif = get_notification_by_name(name)
            self.assertIsNotNone(notif)
            self.assertEqual(notif.name, name)

    def test_get_notification_by_name_non_existing(self):
        """Test get_notification_by_name met niet-bestaande naam."""
        notif = get_notification_by_name("Niet bestaand")
        self.assertIsNone(notif)

    def test_notification_poll_geopend_content(self):
        """Test content van Poll geopend notificatie."""
        notif = get_notification_by_name("Poll geopend")
        self.assertIn("DMK-poll-bot is zojuist aangezet", notif.content)
        self.assertIn("🎮", notif.content)

    def test_notification_poll_gereset_content(self):
        """Test content van Poll gereset notificatie."""
        notif = get_notification_by_name("Poll gereset")
        self.assertIn("gereset voor het nieuwe weekend", notif.content)

    def test_notification_poll_gesloten_has_default_time(self):
        """Test dat Poll gesloten default tijd gebruikt."""
        notif = get_notification_by_name("Poll gesloten")
        self.assertIn("dinsdag om 20:00 uur", notif.content)


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

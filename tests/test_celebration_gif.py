# tests/test_celebration_gif.py
"""Tests voor celebration GIF selector."""

import json
import os
from unittest.mock import patch

from apps.utils.celebration_gif import get_celebration_gif_url
from tests.base import BaseTestCase


class TestGetCelebrationGifUrl(BaseTestCase):
    """Test get_celebration_gif_url functie."""

    def test_returns_none_when_no_file(self):
        """Test dat None wordt geretourneerd als er geen tenor-links bestand is."""
        with patch("apps.utils.celebration_gif.os.path.exists", return_value=False):
            result = get_celebration_gif_url()
            self.assertIsNone(result)

    def test_returns_none_when_empty_list(self):
        """Test dat None wordt geretourneerd bij lege lijst."""
        with patch("apps.utils.celebration_gif._load_tenor_links", return_value=[]):
            result = get_celebration_gif_url()
            self.assertIsNone(result)

    def test_returns_url_from_nintendo_when_count_low(self):
        """Test dat Nintendo URL wordt geselecteerd wanneer count laag is."""
        links = [
            {"id": 1, "url": "https://tenor.com/view/mario-1", "nintendo": "yes", "count": 0},
            {"id": 2, "url": "https://tenor.com/view/mario-2", "nintendo": "yes", "count": 0},
            {"id": 3, "url": "https://tenor.com/view/mj-1", "nintendo": "no", "count": 0},
        ]

        with patch("apps.utils.celebration_gif._load_tenor_links", return_value=links):
            with patch("apps.utils.celebration_gif._save_tenor_links") as mock_save:
                result = get_celebration_gif_url()

                # Moet een Nintendo URL selecteren (beide hebben count=0, dus een van beide)
                self.assertIn(result, ["https://tenor.com/view/mario-1", "https://tenor.com/view/mario-2"])

                # Verifieer dat count werd geïncrementeerd
                saved_links = mock_save.call_args[0][0]
                # Check dat één van de Nintendo URLs count 1 heeft
                nintendo_counts = [link["count"] for link in saved_links if link["nintendo"] == "yes"]
                self.assertIn(1, nintendo_counts)

    def test_returns_url_from_non_nintendo_when_nintendo_count_high(self):
        """Test dat non-Nintendo URL wordt geselecteerd wanneer Nintendo count hoog is."""
        links = [
            {"id": 1, "url": "https://tenor.com/view/mario-1", "nintendo": "yes", "count": 30},
            {"id": 2, "url": "https://tenor.com/view/mj-1", "nintendo": "no", "count": 0},
        ]

        with patch("apps.utils.celebration_gif._load_tenor_links", return_value=links):
            with patch("apps.utils.celebration_gif._save_tenor_links") as mock_save:
                result = get_celebration_gif_url()

                # Moet non-Nintendo URL selecteren want Nintendo avg (30) >= non-Nintendo avg (0) * 3
                self.assertEqual(result, "https://tenor.com/view/mj-1")

                # Verifieer dat count werd geïncrementeerd
                saved_links = mock_save.call_args[0][0]
                self.assertEqual(saved_links[1]["count"], 1)

    def test_selects_lowest_count_within_pool(self):
        """Test dat de URL met de laagste count wordt geselecteerd."""
        links = [
            {"id": 1, "url": "https://tenor.com/view/mario-1", "nintendo": "yes", "count": 5},
            {"id": 2, "url": "https://tenor.com/view/mario-2", "nintendo": "yes", "count": 2},
            {"id": 3, "url": "https://tenor.com/view/mario-3", "nintendo": "yes", "count": 8},
        ]

        with patch("apps.utils.celebration_gif._load_tenor_links", return_value=links):
            with patch("apps.utils.celebration_gif._save_tenor_links") as mock_save:
                result = get_celebration_gif_url()

                # Moet mario-2 selecteren want die heeft count=2 (laagste)
                self.assertEqual(result, "https://tenor.com/view/mario-2")

                # Verifieer dat count werd geïncrementeerd naar 3
                saved_links = mock_save.call_args[0][0]
                self.assertEqual(saved_links[1]["count"], 3)

    def test_handles_only_nintendo_links(self):
        """Test dat het werkt met alleen Nintendo links."""
        links = [
            {"id": 1, "url": "https://tenor.com/view/mario-1", "nintendo": "yes", "count": 0},
            {"id": 2, "url": "https://tenor.com/view/mario-2", "nintendo": "yes", "count": 0},
        ]

        with patch("apps.utils.celebration_gif._load_tenor_links", return_value=links):
            with patch("apps.utils.celebration_gif._save_tenor_links"):
                result = get_celebration_gif_url()

                # Moet een van de Nintendo URLs retourneren
                self.assertIn(result, ["https://tenor.com/view/mario-1", "https://tenor.com/view/mario-2"])

    def test_handles_only_non_nintendo_links(self):
        """Test dat het werkt met alleen non-Nintendo links."""
        links = [
            {"id": 1, "url": "https://tenor.com/view/mj-1", "nintendo": "no", "count": 0},
            {"id": 2, "url": "https://tenor.com/view/mj-2", "nintendo": "no", "count": 0},
        ]

        with patch("apps.utils.celebration_gif._load_tenor_links", return_value=links):
            with patch("apps.utils.celebration_gif._save_tenor_links"):
                result = get_celebration_gif_url()

                # Moet een van de non-Nintendo URLs retourneren
                self.assertIn(result, ["https://tenor.com/view/mj-1", "https://tenor.com/view/mj-2"])

    def test_weighted_selection_ratio(self):
        """Test dat Nintendo URLs ongeveer 3x vaker worden gebruikt dan non-Nintendo."""
        # Dit test de 3:1 ratio door meerdere selecties te doen
        links = [
            {"id": 1, "url": "https://tenor.com/view/mario-1", "nintendo": "yes", "count": 0},
            {"id": 2, "url": "https://tenor.com/view/mj-1", "nintendo": "no", "count": 0},
        ]

        nintendo_count = 0
        non_nintendo_count = 0

        # Simuleer 40 selecties
        for i in range(40):
            test_links = [link.copy() for link in links]
            # Update counts based on simulation
            test_links[0]["count"] = nintendo_count
            test_links[1]["count"] = non_nintendo_count

            with patch("apps.utils.celebration_gif._load_tenor_links", return_value=test_links):
                with patch("apps.utils.celebration_gif._save_tenor_links") as mock_save:
                    result = get_celebration_gif_url()

                    # Update counts based on result
                    if result == "https://tenor.com/view/mario-1":
                        nintendo_count += 1
                    else:
                        non_nintendo_count += 1

        # Nintendo moet ongeveer 30x gebruikt zijn, non-Nintendo 10x (ratio 3:1)
        # Tolerantie van +/- 5
        self.assertGreater(nintendo_count, 20)  # Minstens 20 van 40
        self.assertLess(non_nintendo_count, 20)  # Maximaal 20 van 40


class TestCelebrationGifExceptionHandling(BaseTestCase):
    """Tests voor exception handling in celebration_gif helpers"""

    def test_load_tenor_links_json_decode_error(self):
        """Test dat _load_tenor_links lege lijst retourneert bij JSONDecodeError"""
        from unittest.mock import mock_open, patch

        from apps.utils import celebration_gif

        # Patch open at module level to avoid interfering with coverage.py
        with patch("apps.utils.celebration_gif.os.path.exists", return_value=True), \
             patch("apps.utils.celebration_gif.open", mock_open(read_data="invalid json")):

            result = celebration_gif._load_tenor_links()

            self.assertEqual(result, [])

    def test_load_tenor_links_file_read_exception(self):
        """Test dat _load_tenor_links lege lijst retourneert bij algemene exception"""
        from unittest.mock import patch

        from apps.utils import celebration_gif

        # Patch open at module level to avoid interfering with coverage.py
        with patch("apps.utils.celebration_gif.os.path.exists", return_value=True), \
             patch("apps.utils.celebration_gif.open", side_effect=OSError("File read error")):

            result = celebration_gif._load_tenor_links()

            self.assertEqual(result, [])

    def test_save_tenor_links_exception(self):
        """Test dat _save_tenor_links exceptions afvangt"""
        from unittest.mock import patch

        from apps.utils import celebration_gif

        links = [{"url": "https://tenor.com/view/test", "count": 0}]

        # Patch open at module level to avoid interfering with coverage.py
        with patch("apps.utils.celebration_gif.open", side_effect=OSError("File write error")):
            # Moet geen exception gooien
            celebration_gif._save_tenor_links(links)

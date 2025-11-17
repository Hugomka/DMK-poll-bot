# tests/test_tenor_sync.py
"""
Tests voor tenor sync functionaliteit (apps/utils/tenor_sync.py).

Test coverage:
- needs_sync() - detecteert of sync nodig is
- sync_tenor_links() - synchroniseert template naar runtime
- get_tenor_links() - haalt tenor links op
- increment_gif_count() - verhoogt count voor specifieke GIF
- Automatische creatie van tenor-links.json bij eerste run
- Behoud van counts bij sync
- Nieuwe GIFs toevoegen met count: 0
- Verwijderde GIFs verwijderen uit runtime
"""

import json
import os
import shutil
import tempfile

from apps.utils.tenor_sync import (
    get_tenor_links,
    increment_gif_count,
    needs_sync,
    sync_tenor_links,
)
from tests.base import BaseTestCase


class TestTenorSync(BaseTestCase):
    """Tests voor tenor sync functionaliteit."""

    def setUp(self):
        """Set up temporary directory voor elke test."""
        super().setUp()

        # Create temp directory
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()

        # Change to temp dir (zodat de functies onze test files vinden)
        os.chdir(self.temp_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        # Change back to original directory
        os.chdir(self.original_cwd)

        # Remove temp directory
        try:
            shutil.rmtree(self.temp_dir)
        except Exception:
            pass

        super().tearDown()

    def _write_template(self, links):
        """Helper: schrijf template bestand."""
        with open("tenor-links.template.json", "w", encoding="utf-8") as f:
            json.dump(links, f)

    def _write_runtime(self, links):
        """Helper: schrijf runtime bestand."""
        with open("tenor-links.json", "w", encoding="utf-8") as f:
            json.dump(links, f)

    def _read_runtime(self):
        """Helper: lees runtime bestand."""
        with open("tenor-links.json", "r", encoding="utf-8") as f:
            return json.load(f)

    # ========================================================================
    # Tests for needs_sync()
    # ========================================================================

    def test_needs_sync_runtime_not_exists(self):
        """Test needs_sync() retourneert True als runtime niet bestaat."""
        template_links = [
            {"url": "https://tenor.com/1", "nintendo": "yes", "count": 0},
        ]
        self._write_template(template_links)
        # Runtime bestaat niet

        result = needs_sync()
        self.assertTrue(result)

    def test_needs_sync_template_not_exists(self):
        """Test needs_sync() retourneert False als template niet bestaat."""
        runtime_links = [
            {"url": "https://tenor.com/1", "nintendo": "yes", "count": 5},
        ]
        self._write_runtime(runtime_links)
        # Template bestaat niet

        result = needs_sync()
        self.assertFalse(result)

    def test_needs_sync_same_urls(self):
        """Test needs_sync() retourneert False als URLs gelijk zijn (alleen counts verschillen)."""
        template_links = [
            {"url": "https://tenor.com/1", "nintendo": "yes", "count": 0},
            {"url": "https://tenor.com/2", "nintendo": "no", "count": 0},
        ]
        runtime_links = [
            {"url": "https://tenor.com/1", "nintendo": "yes", "count": 5},
            {"url": "https://tenor.com/2", "nintendo": "no", "count": 3},
        ]

        self._write_template(template_links)
        self._write_runtime(runtime_links)

        result = needs_sync()
        self.assertFalse(result)

    def test_needs_sync_different_urls(self):
        """Test needs_sync() retourneert True als URLs verschillen."""
        template_links = [
            {"url": "https://tenor.com/1", "nintendo": "yes", "count": 0},
            {"url": "https://tenor.com/3", "nintendo": "yes", "count": 0},  # Nieuw
        ]
        runtime_links = [
            {"url": "https://tenor.com/1", "nintendo": "yes", "count": 5},
            {"url": "https://tenor.com/2", "nintendo": "no", "count": 3},  # Oud
        ]

        self._write_template(template_links)
        self._write_runtime(runtime_links)

        result = needs_sync()
        self.assertTrue(result)

    # ========================================================================
    # Tests for sync_tenor_links()
    # ========================================================================

    def test_sync_creates_runtime_from_template(self):
        """Test dat sync_tenor_links() runtime bestand aanmaakt als het niet bestaat."""
        template_links = [
            {"url": "https://tenor.com/1", "nintendo": "yes", "count": 0},
            {"url": "https://tenor.com/2", "nintendo": "no", "count": 0},
        ]

        self._write_template(template_links)
        # Runtime bestaat niet

        sync_tenor_links()

        # Check dat runtime is aangemaakt met count: 0
        result = self._read_runtime()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["url"], "https://tenor.com/1")
        self.assertEqual(result[0]["count"], 0)
        self.assertEqual(result[1]["url"], "https://tenor.com/2")
        self.assertEqual(result[1]["count"], 0)

    def test_sync_preserves_counts(self):
        """Test dat sync_tenor_links() counts behoudt voor bestaande GIFs."""
        template_links = [
            {"url": "https://tenor.com/1", "nintendo": "yes", "count": 0},
            {"url": "https://tenor.com/2", "nintendo": "no", "count": 0},
        ]
        runtime_links = [
            {"url": "https://tenor.com/1", "nintendo": "yes", "count": 5},
            {"url": "https://tenor.com/2", "nintendo": "no", "count": 3},
        ]

        self._write_template(template_links)
        self._write_runtime(runtime_links)

        sync_tenor_links()

        # Check dat counts behouden zijn
        result = self._read_runtime()
        self.assertEqual(result[0]["count"], 5)
        self.assertEqual(result[1]["count"], 3)

    def test_sync_adds_new_gifs_with_zero_count(self):
        """Test dat sync_tenor_links() nieuwe GIFs toevoegt met count: 0."""
        template_links = [
            {"url": "https://tenor.com/1", "nintendo": "yes", "count": 0},
            {"url": "https://tenor.com/2", "nintendo": "no", "count": 0},
            {"url": "https://tenor.com/3", "nintendo": "yes", "count": 0},  # Nieuw
        ]
        runtime_links = [
            {"url": "https://tenor.com/1", "nintendo": "yes", "count": 5},
            {"url": "https://tenor.com/2", "nintendo": "no", "count": 3},
        ]

        self._write_template(template_links)
        self._write_runtime(runtime_links)

        sync_tenor_links()

        # Check dat nieuwe GIF toegevoegd is met count: 0
        result = self._read_runtime()
        self.assertEqual(len(result), 3)
        self.assertEqual(result[2]["url"], "https://tenor.com/3")
        self.assertEqual(result[2]["count"], 0)
        # Oude counts behouden
        self.assertEqual(result[0]["count"], 5)
        self.assertEqual(result[1]["count"], 3)

    def test_sync_removes_deleted_gifs(self):
        """Test dat sync_tenor_links() verwijderde GIFs verwijdert."""
        template_links = [
            {"url": "https://tenor.com/1", "nintendo": "yes", "count": 0},
            # GIF 2 is verwijderd uit template
        ]
        runtime_links = [
            {"url": "https://tenor.com/1", "nintendo": "yes", "count": 5},
            {"url": "https://tenor.com/2", "nintendo": "no", "count": 3},  # Verwijderen
        ]

        self._write_template(template_links)
        self._write_runtime(runtime_links)

        sync_tenor_links()

        # Check dat GIF 2 verwijderd is
        result = self._read_runtime()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["url"], "https://tenor.com/1")
        self.assertEqual(result[0]["count"], 5)

    def test_sync_template_not_found(self):
        """Test dat sync_tenor_links() netjes afhandelt als template niet bestaat."""
        # Template bestaat niet

        # Should not raise, just log warning
        sync_tenor_links()

        # Runtime should not be created
        self.assertFalse(os.path.exists("tenor-links.json"))

    def test_sync_invalid_template_json(self):
        """Test dat sync_tenor_links() netjes afhandelt bij invalide JSON in template."""
        # Schrijf invalide JSON
        with open("tenor-links.template.json", "w", encoding="utf-8") as f:
            f.write("invalid json {")

        # Should not raise, just log error
        sync_tenor_links()

    # ========================================================================
    # Tests for get_tenor_links()
    # ========================================================================

    def test_get_tenor_links_returns_runtime_data(self):
        """Test dat get_tenor_links() runtime data retourneert."""
        runtime_links = [
            {"url": "https://tenor.com/1", "nintendo": "yes", "count": 5},
            {"url": "https://tenor.com/2", "nintendo": "no", "count": 3},
        ]

        self._write_runtime(runtime_links)

        result = get_tenor_links()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["count"], 5)
        self.assertEqual(result[1]["count"], 3)

    def test_get_tenor_links_triggers_sync_if_not_exists(self):
        """Test dat get_tenor_links() sync triggert als runtime niet bestaat."""
        template_links = [
            {"url": "https://tenor.com/1", "nintendo": "yes", "count": 0},
        ]
        self._write_template(template_links)
        # Runtime bestaat niet

        result = get_tenor_links()

        # Sync should have created runtime
        self.assertTrue(os.path.exists("tenor-links.json"))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["url"], "https://tenor.com/1")

    def test_get_tenor_links_handles_invalid_json(self):
        """Test dat get_tenor_links() lege lijst retourneert bij invalide JSON."""
        # Schrijf invalide JSON
        with open("tenor-links.json", "w", encoding="utf-8") as f:
            f.write("invalid json {")

        result = get_tenor_links()

        # Should return empty list
        self.assertEqual(result, [])

    # ========================================================================
    # Tests for increment_gif_count()
    # ========================================================================

    def test_increment_gif_count_increases_count(self):
        """Test dat increment_gif_count() count verhoogt."""
        runtime_links = [
            {"url": "https://tenor.com/1", "nintendo": "yes", "count": 5},
            {"url": "https://tenor.com/2", "nintendo": "no", "count": 3},
        ]

        self._write_runtime(runtime_links)

        increment_gif_count("https://tenor.com/1")

        # Check dat count verhoogd is
        result = self._read_runtime()
        self.assertEqual(result[0]["count"], 6)
        self.assertEqual(result[1]["count"], 3)  # Onveranderd

    def test_increment_gif_count_url_not_found(self):
        """Test dat increment_gif_count() netjes afhandelt als URL niet gevonden."""
        runtime_links = [
            {"url": "https://tenor.com/1", "nintendo": "yes", "count": 5},
        ]

        self._write_runtime(runtime_links)

        # Should not raise, just log warning
        increment_gif_count("https://tenor.com/999")

        # Check dat niets veranderd is
        result = self._read_runtime()
        self.assertEqual(result[0]["count"], 5)

"""Unit tests for demo markdown content resolution."""

import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from medcat_service.config import Settings
from medcat_service.demo import demo_content


class TestResolveDemoMarkdown(unittest.TestCase):
    def test_unset_path_uses_bundled_footer(self):
        settings = Settings()
        self.assertIsNone(settings.demo_ui_custom_markdown_path)
        self.assertEqual(
            demo_content.resolve_demo_markdown(settings),
            demo_content.default_footer,
        )

    def test_empty_path_raises_validation_error(self):
        with self.assertRaises(ValidationError) as ctx:
            Settings(demo_ui_custom_markdown_path="")
        self.assertIn("APP_DEMO_UI_CUSTOM_MARKDOWN_PATH", str(ctx.exception))

    def test_whitespace_path_raises_validation_error(self):
        with self.assertRaises(ValidationError) as ctx:
            Settings(demo_ui_custom_markdown_path="   ")
        self.assertIn("APP_DEMO_UI_CUSTOM_MARKDOWN_PATH", str(ctx.exception))

    def test_valid_file_returns_file_contents(self):
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".md", delete=False) as handle:
            handle.write("# Custom Footer\n\nHello from mount.")
            path = handle.name

        try:
            settings = Settings(demo_ui_custom_markdown_path=path)
            self.assertEqual(
                demo_content.resolve_demo_markdown(settings),
                "# Custom Footer\n\nHello from mount.",
            )
        finally:
            Path(path).unlink(missing_ok=True)

    def test_missing_file_raises_validation_error(self):
        with self.assertRaises(ValidationError) as ctx:
            Settings(demo_ui_custom_markdown_path="/tmp/medcat-demo-footer-missing.md")
        self.assertIn("APP_DEMO_UI_CUSTOM_MARKDOWN_PATH", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

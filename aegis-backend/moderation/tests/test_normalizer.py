"""
Tests for the text normalizer (ml_pipeline/models_pkg/normalizer.py).

These are pure function tests -- no Django, no database needed.
"""
import pytest
from ml_pipeline.models_pkg.normalizer import normalize_text


class TestNormalizer:
    """Tests for normalize_text() function."""

    def test_normalize_strips_urls_and_mentions(self):
        """URLs and @mentions should be removed entirely."""
        text = "check this https://evil.com @badguy"
        result = normalize_text(text)
        assert "https://evil.com" not in result
        assert "@badguy" not in result
        assert result == "check this"

    def test_normalize_collapses_whitespace_and_html(self):
        """HTML entities should be decoded, whitespace collapsed, <user> stripped."""
        text = "hello &amp; world &lt;user&gt; rt  foo"
        result = normalize_text(text)
        assert "&amp;" not in result
        assert "&lt;" not in result
        assert "<user>" not in result
        assert "rt" not in result.split()  # rt prefix removed
        assert result == "hello & world foo"

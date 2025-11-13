import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hype.hype import Hype
from tests.test_seen_status import DummyConfig, status_data


def test_language_detection_fallback_for_english(tmp_path):
    """When Mastodon doesn't provide language, detect English content and allow it"""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.languages_allowlist = ["en"]
    hype = Hype(cfg)
    
    # Create a status with English content but no language metadata
    s = status_data("1", "https://a/1")
    s["language"] = None  # Mastodon didn't detect language
    s["content"] = "<p>This is a test post in English language. Hello world!</p>"
    
    # Should NOT skip because we detect it's English
    assert hype._should_skip_status(s) is False


def test_language_detection_fallback_for_dutch(tmp_path):
    """When Mastodon doesn't provide language, detect Dutch content and skip it"""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.languages_allowlist = ["en"]
    hype = Hype(cfg)
    
    # Create a status with Dutch content but no language metadata
    s = status_data("1", "https://a/1")
    s["language"] = None  # Mastodon didn't detect language
    s["content"] = "<p>Dit is een testbericht in het Nederlands. Hallo wereld!</p>"
    
    # Should skip because we detect it's Dutch, not English
    assert hype._should_skip_status(s) is True


def test_language_detection_fallback_for_french(tmp_path):
    """When Mastodon doesn't provide language, detect French content and skip it"""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.languages_allowlist = ["en"]
    hype = Hype(cfg)
    
    # Create a status with French content but no language metadata
    s = status_data("1", "https://a/1")
    s["language"] = None  # Mastodon didn't detect language
    s["content"] = "<p>Ceci est un message de test en français. Bonjour le monde!</p>"
    
    # Should skip because we detect it's French, not English
    assert hype._should_skip_status(s) is True


def test_language_detection_with_html_content(tmp_path):
    """Language detection should work with HTML-formatted content"""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.languages_allowlist = ["en"]
    hype = Hype(cfg)
    
    # Create a status with HTML content
    s = status_data("1", "https://a/1")
    s["language"] = ""  # Empty language
    s["content"] = """
        <p>This is an <strong>important</strong> announcement about our new features.</p>
        <p>We are excited to share these updates with everyone!</p>
    """
    
    # Should NOT skip because content is English
    assert hype._should_skip_status(s) is False


def test_language_detection_with_mentions_and_hashtags(tmp_path):
    """Language detection should ignore mentions and hashtags"""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.languages_allowlist = ["en"]
    hype = Hype(cfg)
    
    # Create a status with mentions and hashtags
    s = status_data("1", "https://a/1")
    s["language"] = None
    s["content"] = """
        <p>@someone This is a great article about technology and innovation.
        Check it out! #programming #tech #innovation</p>
    """
    
    # Should NOT skip because content is English
    assert hype._should_skip_status(s) is False


def test_language_detection_overrides_mastodon_language(tmp_path):
    """Bot always detects language from content, ignoring Mastodon's potentially incorrect detection"""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.languages_allowlist = ["en"]
    hype = Hype(cfg)
    
    # Create a status where Mastodon incorrectly detected English for Dutch content
    s = status_data("1", "https://a/1")
    s["language"] = "en"  # Mastodon incorrectly detected as English
    s["content"] = "<p>Dit is een langere Nederlandse tekst die Mastodon verkeerd heeft gedetecteerd als Engels.</p>"
    
    # Should skip because our detection finds it's Dutch, not English (override Mastodon)
    assert hype._should_skip_status(s) is True


def test_language_detection_with_empty_content(tmp_path):
    """When content is empty, should skip if allowlist is configured"""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.languages_allowlist = ["en"]
    hype = Hype(cfg)
    
    # Create a status with no content and no language
    s = status_data("1", "https://a/1")
    s["language"] = None
    s["content"] = ""
    
    # Should skip because we can't detect language and it's not in allowlist
    assert hype._should_skip_status(s) is True


def test_language_detection_with_very_short_content(tmp_path):
    """When content is very short, detection might fail, so skip if no language"""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.languages_allowlist = ["en"]
    hype = Hype(cfg)
    
    # Create a status with very short content
    s = status_data("1", "https://a/1")
    s["language"] = None
    s["content"] = "Hi"
    
    # Should skip because content is too short for reliable detection
    assert hype._should_skip_status(s) is True


def test_language_detection_disabled_when_no_allowlist(tmp_path):
    """When allowlist is empty, language detection should not run"""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.languages_allowlist = []  # No language filtering
    hype = Hype(cfg)
    
    # Create a status with Dutch content
    s = status_data("1", "https://a/1")
    s["language"] = None
    s["content"] = "Dit is een testbericht in het Nederlands"
    
    # Should NOT skip because language filtering is disabled
    assert hype._should_skip_status(s) is False


def test_detect_language_from_content_helper(tmp_path):
    """Test the _detect_language_from_content helper method directly"""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    hype = Hype(cfg)
    
    # Test English detection
    status_en = {"content": "<p>This is a longer piece of English text to ensure proper detection.</p>"}
    lang = hype._detect_language_from_content(status_en)
    assert lang == "en"
    
    # Test Dutch detection
    status_nl = {"content": "<p>Dit is een langere Nederlandse tekst om goede detectie te garanderen.</p>"}
    lang = hype._detect_language_from_content(status_nl)
    assert lang == "nl"
    
    # Test French detection
    status_fr = {"content": "<p>Ceci est un texte français plus long pour assurer une bonne détection.</p>"}
    lang = hype._detect_language_from_content(status_fr)
    assert lang == "fr"
    
    # Test empty content
    status_empty = {"content": ""}
    lang = hype._detect_language_from_content(status_empty)
    assert lang == ""
    
    # Test very short content
    status_short = {"content": "Hi"}
    lang = hype._detect_language_from_content(status_short)
    assert lang == ""  # Too short to detect reliably


def test_use_mastodon_language_detection_enabled(tmp_path):
    """When use_mastodon_language_detection is True, trust Mastodon's language field"""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.languages_allowlist = ["en"]
    cfg.use_mastodon_language_detection = True
    hype = Hype(cfg)
    
    # Mastodon says English, even though content is Dutch
    s = status_data("1", "https://a/1")
    s["language"] = "en"  # Mastodon says English
    s["content"] = "<p>Dit is een langere Nederlandse tekst die Mastodon verkeerd heeft gedetecteerd.</p>"
    
    # Should NOT skip because we trust Mastodon's "en" (even though it's wrong)
    assert hype._should_skip_status(s) is False


def test_use_mastodon_language_detection_disabled_default(tmp_path):
    """By default (use_mastodon_language_detection=False), detect from content"""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.languages_allowlist = ["en"]
    # use_mastodon_language_detection defaults to False
    hype = Hype(cfg)
    
    # Mastodon says English, but content is Dutch
    s = status_data("1", "https://a/1")
    s["language"] = "en"  # Mastodon says English (incorrect)
    s["content"] = "<p>Dit is een langere Nederlandse tekst die Mastodon verkeerd heeft gedetecteerd.</p>"
    
    # Should skip because we detect it's Dutch (override Mastodon)
    assert hype._should_skip_status(s) is True


def test_use_mastodon_language_detection_with_french(tmp_path):
    """When use_mastodon_language_detection is True, trust Mastodon even if wrong"""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.languages_allowlist = ["en"]
    cfg.use_mastodon_language_detection = True
    hype = Hype(cfg)
    
    # Mastodon says French, even though content is English
    s = status_data("1", "https://a/1")
    s["language"] = "fr"  # Mastodon says French
    s["content"] = "<p>This is actually English content that Mastodon incorrectly detected.</p>"
    
    # Should skip because we trust Mastodon's "fr" (even though it's wrong)
    assert hype._should_skip_status(s) is True


def test_use_mastodon_language_detection_disabled_correct_english(tmp_path):
    """With langdetect mode, correctly allow English content"""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.languages_allowlist = ["en"]
    cfg.use_mastodon_language_detection = False
    hype = Hype(cfg)
    
    # Mastodon says French, but content is actually English
    s = status_data("1", "https://a/1")
    s["language"] = "fr"  # Mastodon says French (incorrect)
    s["content"] = "<p>This is actually English content that we should allow based on detection.</p>"
    
    # Should NOT skip because we detect it's English (override Mastodon's "fr")
    assert hype._should_skip_status(s) is False

import sys
import types
import math
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hype.hype import Hype
from tests.test_seen_status import DummyConfig, status_data


def test_min_replies_in_scoring(tmp_path):
    """Test that replies_count is included in scoring calculation."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    hype = Hype(cfg)
    s = status_data("1", "https://a/1")
    s["replies_count"] = 5
    s["reblogs_count"] = 0
    s["favourites_count"] = 0
    expected = math.log1p(5) * 1.5  # replies weight is 1.5
    assert hype.score_status(s) == pytest.approx(expected)


def test_replies_score_weight(tmp_path):
    """Test that replies have the correct weight relative to other engagement."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    hype = Hype(cfg)
    
    # Test that replies are weighted between favorites (1.0) and reblogs (2.0)
    s = status_data("1", "https://a/1")
    s["replies_count"] = 10
    s["reblogs_count"] = 0
    s["favourites_count"] = 0
    replies_score = hype.score_status(s)
    
    s["replies_count"] = 0
    s["favourites_count"] = 10
    favourites_score = hype.score_status(s)
    
    s["favourites_count"] = 0
    s["reblogs_count"] = 10
    reblogs_score = hype.score_status(s)
    
    # Verify that replies score is between favourites and reblogs
    assert favourites_score < replies_score < reblogs_score


def test_min_replies_filtering(tmp_path):
    """Test that posts with insufficient replies are filtered out."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.min_replies = 3
    hype = Hype(cfg)
    
    # Should skip posts with fewer replies than minimum
    s_low = status_data("1", "https://a/1")
    s_low["replies_count"] = 2
    assert hype._should_skip_status(s_low) == True
    
    # Should not skip posts with sufficient replies
    s_high = status_data("2", "https://a/2")
    s_high["replies_count"] = 5
    assert hype._should_skip_status(s_high) == False


def test_min_replies_threshold_blocks_low_reply_posts(tmp_path):
    """Posts below the replies threshold are filtered out."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.min_replies = 2
    hype = Hype(cfg)

    s = status_data("1", "https://a/1")
    s["replies_count"] = 1
    assert hype._should_skip_status(s) is True

    s["replies_count"] = 2
    assert hype._should_skip_status(s) is False


def test_combined_engagement_filtering(tmp_path):
    """Test that replies filtering works alongside other engagement filters."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.min_replies = 2
    cfg.min_favourites = 3
    cfg.min_reblogs = 1
    hype = Hype(cfg)
    
    # Should skip if any engagement metric is below threshold
    s = status_data("1", "https://a/1")
    s["replies_count"] = 5  # Above threshold
    s["favourites_count"] = 1  # Below threshold
    s["reblogs_count"] = 2  # Above threshold
    assert hype._should_skip_status(s) == True
    
    # Should not skip if all engagement metrics meet thresholds
    s["favourites_count"] = 4  # Now above threshold
    assert hype._should_skip_status(s) == False


def test_missing_replies_count_defaults_to_zero(tmp_path):
    """Test that missing replies_count field defaults to 0."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.min_replies = 1
    hype = Hype(cfg)

    s = status_data("1", "https://a/1")
    s.pop("replies_count", None)
    assert hype._should_skip_status(s) == True

    score = hype.score_status(s)
    assert score >= 0


def test_none_replies_count_treated_as_zero(tmp_path):
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.min_replies = 2
    hype = Hype(cfg)

    s = status_data("1", "https://a/1")
    s["replies_count"] = None
    assert hype._should_skip_status(s) is True

    s["replies_count"] = "5"
    assert hype._should_skip_status(s) is False


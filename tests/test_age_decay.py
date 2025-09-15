import sys
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hype.hype import Hype
from tests.test_seen_status import DummyConfig, status_data


def test_age_decay_disabled_by_default(tmp_path):
    """Test that age decay is disabled by default."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.hashtag_scores = {"test": 10}
    hype = Hype(cfg)
    
    # Create an old status
    old_time = datetime.now(timezone.utc) - timedelta(hours=48)
    s = status_data("1", "https://a/1")
    s["tags"] = [{"name": "test"}]
    s["created_at"] = old_time.isoformat()
    
    # Score should not be affected by age when disabled
    score = hype.score_status(s)
    assert score == 10  # Just the hashtag score, no decay


def test_age_decay_applies_penalty_to_old_posts(tmp_path):
    """Test that age decay reduces scores for old posts."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.age_decay_enabled = True
    cfg.age_decay_half_life_hours = 24.0
    cfg.hashtag_scores = {"test": 10}
    hype = Hype(cfg)
    
    # Create a status that's 48 hours old (2 half-lives)
    old_time = datetime.now(timezone.utc) - timedelta(hours=48)
    s = status_data("1", "https://a/1")
    s["tags"] = [{"name": "test"}]
    s["created_at"] = old_time.isoformat()
    
    score = hype.score_status(s)
    
    # After 2 half-lives, score should be reduced by 75%
    # decay_factor = 0.5^(48/24) = 0.5^2 = 0.25
    # penalty = 10 * (1 - 0.25) = 7.5
    # final_score = 10 - 7.5 = 2.5
    expected_score = 10 * (0.5 ** (48 / 24))  # 2.5
    assert score == pytest.approx(expected_score, rel=1e-9)


def test_age_decay_no_penalty_for_new_posts(tmp_path):
    """Test that very recent posts get no age penalty."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.age_decay_enabled = True
    cfg.age_decay_half_life_hours = 24.0
    cfg.hashtag_scores = {"test": 10}
    hype = Hype(cfg)
    
    # Create a very recent status (1 minute old)
    recent_time = datetime.now(timezone.utc) - timedelta(minutes=1)
    s = status_data("1", "https://a/1")
    s["tags"] = [{"name": "test"}]
    s["created_at"] = recent_time.isoformat()
    
    score = hype.score_status(s)
    
    # For very recent posts, decay should be minimal
    # After 1/60 hours, decay_factor = 0.5^(1/60/24) ≈ 0.9997
    # So penalty is tiny and score is almost the full 10
    assert score > 9.9  # Should be very close to 10


def test_age_decay_with_different_half_life(tmp_path):
    """Test age decay with different half-life settings."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.age_decay_enabled = True
    cfg.age_decay_half_life_hours = 12.0  # Faster decay
    cfg.hashtag_scores = {"test": 10}
    hype = Hype(cfg)
    
    # Create a status that's 24 hours old (2 half-lives with 12h half-life)
    old_time = datetime.now(timezone.utc) - timedelta(hours=24)
    s = status_data("1", "https://a/1")
    s["tags"] = [{"name": "test"}]
    s["created_at"] = old_time.isoformat()
    
    score = hype.score_status(s)
    
    # After 2 half-lives (24h / 12h), score should be reduced by 75%
    expected_score = 10 * (0.5 ** (24 / 12))  # 2.5
    assert score == pytest.approx(expected_score, rel=1e-9)


def test_age_decay_combined_with_engagement(tmp_path):
    """Test that age decay applies to the total score including engagement."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.age_decay_enabled = True
    cfg.age_decay_half_life_hours = 24.0
    hype = Hype(cfg)
    
    # Create an old status with engagement
    old_time = datetime.now(timezone.utc) - timedelta(hours=24)  # 1 half-life
    s = status_data("1", "https://a/1")
    s["reblogs_count"] = 3
    s["favourites_count"] = 8
    s["created_at"] = old_time.isoformat()
    
    score = hype.score_status(s)
    
    # Calculate expected score
    base_score = math.log1p(3) * 2 + math.log1p(8)  # engagement only
    # After 1 half-life, decay_factor = 0.5
    expected_score = base_score * 0.5
    assert score == pytest.approx(expected_score, rel=1e-9)


def test_age_decay_handles_missing_created_at(tmp_path):
    """Test that missing created_at doesn't crash the system."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.age_decay_enabled = True
    cfg.age_decay_half_life_hours = 24.0
    cfg.hashtag_scores = {"test": 10}
    hype = Hype(cfg)
    
    s = status_data("1", "https://a/1")
    s["tags"] = [{"name": "test"}]
    # Remove created_at to simulate missing timestamp
    if "created_at" in s:
        del s["created_at"]
    
    # Should not crash and should treat as epoch time (very old)
    score = hype.score_status(s)
    # Should be heavily penalized as it's treated as epoch time
    assert score < 1  # Should be close to 0 due to extreme age


def test_age_decay_with_negative_hashtag_scores(tmp_path):
    """Test that age decay works correctly with negative hashtag scores."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.age_decay_enabled = True
    cfg.age_decay_half_life_hours = 24.0
    cfg.hashtag_scores = {"bad": -5}
    hype = Hype(cfg)
    
    # Create an old status with negative hashtag
    old_time = datetime.now(timezone.utc) - timedelta(hours=24)  # 1 half-life
    s = status_data("1", "https://a/1")
    s["tags"] = [{"name": "bad"}]
    s["created_at"] = old_time.isoformat()
    
    score = hype.score_status(s)
    
    # Base score is -5, decay factor is 0.5
    # penalty = -5 * (1 - 0.5) = -2.5 (negative penalty is actually a bonus)
    # final score = -5 - (-2.5) = -2.5
    expected_score = -5 * 0.5
    assert score == pytest.approx(expected_score, rel=1e-9)
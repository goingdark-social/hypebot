import sys
import math
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hype.hype import Hype
from tests.test_seen_status import DummyConfig, status_data


def test_negative_hashtag_weights_reduce_score(tmp_path):
    """Test that negative hashtag weights reduce the total score."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.hashtag_scores = {"bad": -5, "good": 10}
    hype = Hype(cfg)
    
    # Status with negative hashtag
    s = status_data("1", "https://a/1")
    s["tags"] = [{"name": "bad"}]
    s["reblogs_count"] = 3
    s["favourites_count"] = 8
    
    score = hype.score_status(s)
    
    # Expected: -5 (hashtag) + log1p(3)*2 + log1p(8)
    expected = -5 + math.log1p(3) * 2 + math.log1p(8)
    assert score == pytest.approx(expected)
    assert score < math.log1p(3) * 2 + math.log1p(8)  # Less than without negative hashtag


def test_negative_hashtag_weights_can_make_score_negative(tmp_path):
    """Test that negative hashtag weights can make the total score negative."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.hashtag_scores = {"terrible": -20}
    hype = Hype(cfg)
    
    # Status with very negative hashtag and minimal engagement
    s = status_data("1", "https://a/1")
    s["tags"] = [{"name": "terrible"}]
    s["reblogs_count"] = 1
    s["favourites_count"] = 1
    
    score = hype.score_status(s)
    
    # Expected: -20 + log1p(1)*2 + log1p(1) ≈ -20 + 1.386 + 0.693 ≈ -17.92
    expected = -20 + math.log1p(1) * 2 + math.log1p(1)
    assert score == pytest.approx(expected)
    assert score < 0  # Score should be negative


def test_mixed_positive_negative_hashtags(tmp_path):
    """Test scoring with both positive and negative hashtags in same post."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.hashtag_scores = {"good": 15, "bad": -10, "neutral": 0}
    hype = Hype(cfg)
    
    # Status with mixed hashtags
    s = status_data("1", "https://a/1")
    s["tags"] = [{"name": "good"}, {"name": "bad"}, {"name": "neutral"}]
    s["reblogs_count"] = 2
    s["favourites_count"] = 5
    
    score = hype.score_status(s)
    
    # Expected: (15 - 10 + 0) + log1p(2)*2 + log1p(5) = 5 + engagement
    hashtag_sum = 15 - 10 + 0  # 5
    engagement = math.log1p(2) * 2 + math.log1p(5)
    expected = hashtag_sum + engagement
    assert score == pytest.approx(expected)


def test_negative_hashtag_weights_support_float_values(tmp_path):
    """Test that negative hashtag weights support decimal values."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.hashtag_scores = {"slightly_bad": -2.5, "very_bad": -10.75}
    hype = Hype(cfg)
    
    # Status with decimal negative weight
    s1 = status_data("1", "https://a/1")
    s1["tags"] = [{"name": "slightly_bad"}]
    
    s2 = status_data("2", "https://a/2")
    s2["tags"] = [{"name": "very_bad"}]
    
    score1 = hype.score_status(s1)
    score2 = hype.score_status(s2)
    
    assert score1 == pytest.approx(-2.5)
    assert score2 == pytest.approx(-10.75)
    assert score1 > score2  # Less negative is better


def test_negative_hashtag_weights_case_insensitive(tmp_path):
    """Test that negative hashtag weights are case insensitive."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.hashtag_scores = {"spam": -8}
    hype = Hype(cfg)
    
    # Test different cases
    s1 = status_data("1", "https://a/1")
    s1["tags"] = [{"name": "SPAM"}]
    
    s2 = status_data("2", "https://a/2")
    s2["tags"] = [{"name": "Spam"}]
    
    s3 = status_data("3", "https://a/3")
    s3["tags"] = [{"name": "spam"}]
    
    # All should get the same negative score
    score1 = hype.score_status(s1)
    score2 = hype.score_status(s2)
    score3 = hype.score_status(s3)
    
    assert score1 == score2 == score3 == -8


def test_unknown_hashtags_get_zero_score(tmp_path):
    """Test that unknown hashtags get zero score (no error)."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.hashtag_scores = {"known": 5}
    hype = Hype(cfg)
    
    # Status with unknown hashtag
    s = status_data("1", "https://a/1")
    s["tags"] = [{"name": "unknown"}]
    s["reblogs_count"] = 3
    
    score = hype.score_status(s)
    
    # Should only get engagement score, no hashtag penalty or bonus
    expected = math.log1p(3) * 2
    assert score == pytest.approx(expected)


def test_negative_hashtag_combined_with_age_decay(tmp_path):
    """Test negative hashtag weights work correctly with age decay."""
    from datetime import datetime, timezone, timedelta
    
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.hashtag_scores = {"bad": -10}
    cfg.age_decay_enabled = True
    cfg.age_decay_half_life_hours = 24.0
    hype = Hype(cfg)
    
    # Create an old status with negative hashtag
    old_time = datetime.now(timezone.utc) - timedelta(hours=24)  # 1 half-life
    s = status_data("1", "https://a/1")
    s["tags"] = [{"name": "bad"}]
    s["created_at"] = old_time.isoformat()
    
    score = hype.score_status(s)
    
    # Base score is -10, after 1 half-life decay factor is 0.5
    # So final score should be -10 * 0.5 = -5
    expected_score = -10 * 0.5
    assert score == pytest.approx(expected_score, rel=1e-9)


def test_zero_hashtag_score_unchanged(tmp_path):
    """Test that hashtags with zero score work correctly."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.hashtag_scores = {"neutral": 0}
    hype = Hype(cfg)
    
    s = status_data("1", "https://a/1")
    s["tags"] = [{"name": "neutral"}]
    s["reblogs_count"] = 2
    
    score = hype.score_status(s)
    
    # Should only get engagement score
    expected = math.log1p(2) * 2
    assert score == pytest.approx(expected)


def test_extreme_negative_hashtag_weights(tmp_path):
    """Test extremely negative hashtag weights."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.hashtag_scores = {"extremely_bad": -1000}
    hype = Hype(cfg)
    
    # Status with extreme negative hashtag but high engagement
    s = status_data("1", "https://a/1")
    s["tags"] = [{"name": "extremely_bad"}]
    s["reblogs_count"] = 100
    s["favourites_count"] = 500
    
    score = hype.score_status(s)
    
    # Even with high engagement, should still be very negative
    engagement = math.log1p(100) * 2 + math.log1p(500)  # ~15.5
    expected = -1000 + engagement
    assert score == pytest.approx(expected)
    assert score < -980  # Should still be very negative
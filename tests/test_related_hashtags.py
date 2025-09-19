import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hype.hype import Hype
from tests.test_seen_status import DummyConfig, status_data


def test_related_hashtag_scoring_disabled_by_default(tmp_path):
    """Test that related hashtag scoring is disabled when no config is provided."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    # Default should be empty dict (disabled)
    assert cfg.related_hashtags == {}
    
    hype = Hype(cfg)
    
    # Create a status with content that would match if related hashtags were configured
    status = status_data("1", "https://example.com/1")
    status["content"] = "I love self-hosting my homelab setup!"
    status["tags"] = []
    status["reblogs_count"] = 5
    status["favourites_count"] = 3
    
    score = hype.score_status(status)
    # Should only get base engagement score, no hashtag bonuses
    assert score > 0  # Base score from engagement
    
    # Test the related hashtag calculation directly
    related_score = hype._calculate_related_hashtag_score(status)
    assert related_score == 0


def test_related_hashtag_scoring_basic_functionality(tmp_path):
    """Test basic related hashtag scoring with simple configuration."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.hashtag_scores = {"homelab": 10.0}
    cfg.related_hashtags = {
        "homelab": {
            "self-hosting": 0.5,  # 50% of the homelab score
            "selfhosting": 0.5,
        }
    }
    
    hype = Hype(cfg)
    
    # Status with related content but no homelab hashtag
    status = status_data("1", "https://example.com/1")
    status["content"] = "I love self-hosting my applications"
    status["tags"] = []
    status["reblogs_count"] = 0
    status["favourites_count"] = 0
    
    related_score = hype._calculate_related_hashtag_score(status)
    # Should get 50% of homelab score (10.0 * 0.5 = 5.0)
    assert related_score == 5.0


def test_related_hashtag_scoring_ignores_existing_hashtags(tmp_path):
    """Test that related scoring doesn't apply when the main hashtag is already present."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.hashtag_scores = {"homelab": 10.0}
    cfg.related_hashtags = {
        "homelab": {
            "self-hosting": 0.5,
        }
    }
    
    hype = Hype(cfg)
    
    # Status already has the homelab hashtag
    status = status_data("1", "https://example.com/1")
    status["content"] = "I love self-hosting my applications"
    status["tags"] = [{"name": "homelab"}]
    
    related_score = hype._calculate_related_hashtag_score(status)
    # Should not get related bonus because main hashtag is already present
    assert related_score == 0


def test_related_hashtag_scoring_case_insensitive(tmp_path):
    """Test that related hashtag scoring is case insensitive."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.hashtag_scores = {"homelab": 10.0}
    cfg.related_hashtags = {
        "homelab": {
            "self-hosting": 0.5,
        }
    }
    
    hype = Hype(cfg)
    
    # Test with different case combinations
    test_cases = [
        "I love Self-Hosting",
        "I love SELF-HOSTING",
        "I love self-hosting",
        "self-hosting is great",
    ]
    
    for content in test_cases:
        status = status_data("1", "https://example.com/1")
        status["content"] = content
        status["tags"] = []
        
        related_score = hype._calculate_related_hashtag_score(status)
        assert related_score == 5.0, f"Failed for content: {content}"


def test_related_hashtag_scoring_multiple_terms(tmp_path):
    """Test related hashtag scoring with multiple related terms."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.hashtag_scores = {"homelab": 10.0, "docker": 8.0}
    cfg.related_hashtags = {
        "homelab": {
            "self-hosting": 0.5,
            "self-hosted": 0.3,
        },
        "docker": {
            "container": 0.6,
            "containerization": 0.4,
        }
    }
    
    hype = Hype(cfg)
    
    # Status with multiple related terms
    status = status_data("1", "https://example.com/1")
    status["content"] = "I use containers for self-hosting in my setup"
    status["tags"] = []
    
    related_score = hype._calculate_related_hashtag_score(status)
    # Should get homelab bonus (10.0 * 0.5 = 5.0) and docker bonus (8.0 * 0.6 = 4.8) = 9.8
    assert related_score == 9.8


def test_related_hashtag_scoring_only_one_bonus_per_hashtag(tmp_path):
    """Test that only one bonus is applied per main hashtag even if multiple terms match."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.hashtag_scores = {"homelab": 10.0}
    cfg.related_hashtags = {
        "homelab": {
            "self-hosting": 0.5,
            "self-hosted": 0.3,
        }
    }
    
    hype = Hype(cfg)
    
    # Status with multiple related terms for the same hashtag
    status = status_data("1", "https://example.com/1")
    status["content"] = "I love self-hosting and self-hosted applications"
    status["tags"] = []
    
    related_score = hype._calculate_related_hashtag_score(status)
    # Should only get one bonus (the first match: 10.0 * 0.5 = 5.0)
    assert related_score == 5.0


def test_related_hashtag_scoring_no_bonus_for_negative_base_scores(tmp_path):
    """Test that related bonuses are not applied for negative base hashtag scores."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.hashtag_scores = {"spam": -10.0}  # Negative score
    cfg.related_hashtags = {
        "spam": {
            "advertisement": 0.5,
        }
    }
    
    hype = Hype(cfg)
    
    status = status_data("1", "https://example.com/1")
    status["content"] = "This is an advertisement"
    status["tags"] = []
    
    related_score = hype._calculate_related_hashtag_score(status)
    # Should not get bonus for negative base scores
    assert related_score == 0


def test_related_hashtag_scoring_checks_hashtag_content_too(tmp_path):
    """Test that related scoring checks both content and existing hashtag names."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.hashtag_scores = {"homelab": 10.0}
    cfg.related_hashtags = {
        "homelab": {
            "selfhosted": 0.5,  # No hyphen
        }
    }
    
    hype = Hype(cfg)
    
    # Status has the related term as a hashtag, not in content
    status = status_data("1", "https://example.com/1")
    status["content"] = "Check out my setup"
    status["tags"] = [{"name": "selfhosted"}]
    
    related_score = hype._calculate_related_hashtag_score(status)
    # Should get bonus because hashtag matches related term
    assert related_score == 5.0


def test_related_hashtag_scoring_integration_with_main_scoring(tmp_path):
    """Test that related hashtag scoring integrates properly with main score_status method."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.hashtag_scores = {"python": 15.0}
    cfg.related_hashtags = {
        "python": {
            "programming": 0.4,
        }
    }
    
    hype = Hype(cfg)
    
    # Status with related content
    status = status_data("1", "https://example.com/1")
    status["content"] = "I love programming"
    status["tags"] = []
    status["reblogs_count"] = 5
    status["favourites_count"] = 3
    
    total_score = hype.score_status(status)
    
    # Calculate expected score
    import math
    reblogs_score = math.log1p(5) * 2  # ~3.58
    favorites_score = math.log1p(3)    # ~1.39
    related_bonus = 15.0 * 0.4         # 6.0
    expected = reblogs_score + favorites_score + related_bonus
    
    assert abs(total_score - expected) < 0.01  # Allow small floating point differences
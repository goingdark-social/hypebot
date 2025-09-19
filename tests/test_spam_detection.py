import sys
import math
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hype.hype import Hype
from tests.test_seen_status import DummyConfig, status_data


def test_emoji_count_detection():
    """Test emoji counting function works correctly."""
    cfg = DummyConfig("/tmp/state.json")
    hype = Hype(cfg)
    
    # Test with no emojis
    assert hype._count_emojis("") == 0
    assert hype._count_emojis("Hello world") == 0
    
    # Test with single emoji
    assert hype._count_emojis("Hello 😀") == 1
    assert hype._count_emojis("😀 Hello") == 1
    
    # Test with multiple emojis
    assert hype._count_emojis("😀😁😂") == 3
    assert hype._count_emojis("Hello 😀 world 😁 test 😂") == 3
    
    # Test with mixed content
    assert hype._count_emojis("Check this out! 🎉🎊🚀 Amazing!") == 3


def test_link_detection():
    """Test link detection function works correctly."""
    cfg = DummyConfig("/tmp/state.json")
    hype = Hype(cfg)
    
    # Test with no links
    assert not hype._has_links("")
    assert not hype._has_links("Hello world")
    
    # Test with HTTP links
    assert hype._has_links("Check out https://example.com")
    assert hype._has_links("Visit https://www.example.com/path")
    
    # Test with HTTPS links
    assert hype._has_links("Go to http://example.com")
    
    # Test with www links
    assert hype._has_links("Visit www.example.com")
    
    # Test with multiple links
    assert hype._has_links("Visit https://example.com and www.test.com")


def test_no_spam_penalty_by_default(tmp_path):
    """Test that spam penalties are disabled by default."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    # Default spam penalties should be 0
    assert cfg.spam_emoji_penalty == 0
    assert cfg.spam_link_penalty == 0
    assert cfg.spam_emoji_threshold == 2
    
    hype = Hype(cfg)
    s = status_data("1", "https://a/1")
    s["content"] = "😀😁😂😃😄 Check out https://example.com"  # 5 emojis + link
    
    # Should score normally since penalties are 0
    base_score = hype.score_status(s)
    assert base_score == 0  # No hashtags, reblogs, favourites, etc.


def test_emoji_spam_penalty(tmp_path):
    """Test emoji spam penalty reduces score."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.spam_emoji_penalty = 1.0  # 1 point penalty per excess emoji
    cfg.spam_emoji_threshold = 2  # Penalty starts after 2 emojis
    hype = Hype(cfg)
    
    # Test no penalty for 2 emojis or less
    s1 = status_data("1", "https://a/1")
    s1["content"] = "😀😁"  # 2 emojis - no penalty
    score1 = hype.score_status(s1)
    
    s2 = status_data("2", "https://a/2") 
    s2["content"] = "😀"  # 1 emoji - no penalty
    score2 = hype.score_status(s2)
    
    assert score1 == score2 == 0  # No penalty
    
    # Test penalty for excess emojis
    s3 = status_data("3", "https://a/3")
    s3["content"] = "😀😁😂"  # 3 emojis - 1 excess, penalty = 1
    score3 = hype.score_status(s3)
    assert score3 == -1.0
    
    s4 = status_data("4", "https://a/4")
    s4["content"] = "😀😁😂😃😄"  # 5 emojis - 3 excess, penalty = 3
    score4 = hype.score_status(s4)
    assert score4 == -3.0


def test_link_penalty(tmp_path):
    """Test link penalty reduces score."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.spam_link_penalty = 0.5  # 0.5 point penalty for links
    hype = Hype(cfg)
    
    # Test no penalty without links
    s1 = status_data("1", "https://a/1")
    s1["content"] = "Hello world"
    score1 = hype.score_status(s1)
    assert score1 == 0
    
    # Test penalty with links
    s2 = status_data("2", "https://a/2")
    s2["content"] = "Check out https://example.com"
    score2 = hype.score_status(s2)
    assert score2 == -0.5


def test_combined_spam_penalties(tmp_path):
    """Test that emoji and link penalties combine."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.spam_emoji_penalty = 1.0
    cfg.spam_emoji_threshold = 2
    cfg.spam_link_penalty = 0.5
    hype = Hype(cfg)
    
    s = status_data("1", "https://a/1")
    s["content"] = "😀😁😂😃 Check this out! https://example.com"  # 4 emojis (2 excess) + link
    score = hype.score_status(s)
    
    # Expected: -(2 * 1.0) - 0.5 = -2.5
    assert score == -2.5


def test_spam_penalty_with_positive_score(tmp_path):
    """Test spam penalties work with positive base scores."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.spam_emoji_penalty = 1.0
    cfg.spam_emoji_threshold = 2
    cfg.spam_link_penalty = 0.5
    cfg.hashtag_scores = {"python": 10}
    hype = Hype(cfg)
    
    s = status_data("1", "https://a/1")
    s["tags"] = [{"name": "python"}]
    s["content"] = "😀😁😂 Python is awesome! https://python.org"  # 3 emojis (1 excess) + link
    s["reblogs_count"] = 3
    s["favourites_count"] = 8
    
    # Base score: hashtag(10) + reblogs(log1p(3)*2) + favourites(log1p(8)) - emoji_penalty(1) - link_penalty(0.5)
    expected_base = 10 + math.log1p(3) * 2 + math.log1p(8) - 1.0 - 0.5
    score = hype.score_status(s)
    assert score == pytest.approx(expected_base)


def test_configurable_emoji_threshold(tmp_path):
    """Test that emoji threshold is configurable."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.spam_emoji_penalty = 1.0
    cfg.spam_emoji_threshold = 1  # Penalty starts after 1 emoji
    hype = Hype(cfg)
    
    # Test no penalty for 1 emoji
    s1 = status_data("1", "https://a/1")
    s1["content"] = "😀"
    score1 = hype.score_status(s1)
    assert score1 == 0
    
    # Test penalty for 2 emojis (1 excess)
    s2 = status_data("2", "https://a/2")
    s2["content"] = "😀😁"
    score2 = hype.score_status(s2)
    assert score2 == -1.0


def test_spam_detection_handles_missing_content(tmp_path):
    """Test spam detection handles missing or None content gracefully."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.spam_emoji_penalty = 1.0
    cfg.spam_link_penalty = 0.5
    hype = Hype(cfg)
    
    # Test with None content
    s1 = status_data("1", "https://a/1")
    s1["content"] = None
    score1 = hype.score_status(s1)
    assert score1 == 0
    
    # Test with missing content key
    s2 = status_data("2", "https://a/2")
    if "content" in s2:
        del s2["content"]
    score2 = hype.score_status(s2)
    assert score2 == 0
    
    # Test with empty content
    s3 = status_data("3", "https://a/3")
    s3["content"] = ""
    score3 = hype.score_status(s3)
    assert score3 == 0
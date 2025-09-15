import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hype.hype import Hype
from tests.test_seen_status import DummyConfig, status_data


def test_hashtag_diversity_disabled_by_default(tmp_path):
    """Test that hashtag diversity enforcement is disabled by default."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    hype = Hype(cfg)
    
    # Create multiple statuses with the same hashtag
    s1 = status_data("1", "https://a/1")
    s1["tags"] = [{"name": "python"}]
    s2 = status_data("2", "https://a/2")
    s2["tags"] = [{"name": "python"}]
    
    # Should not be seen as duplicate when diversity is disabled
    assert not hype._hashtag_diversity_hit(s1)
    hype._remember_status(s1)
    assert not hype._hashtag_diversity_hit(s2)


def test_hashtag_diversity_prevents_duplicate_hashtags_in_run(tmp_path):
    """Test that hashtag diversity prevents boosting multiple posts with same hashtag."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.hashtag_diversity_enforced = True
    cfg.max_boosts_per_hashtag_per_run = 1
    hype = Hype(cfg)
    
    # Create multiple statuses with the same hashtag
    s1 = status_data("1", "https://a/1")
    s1["tags"] = [{"name": "python"}]
    s2 = status_data("2", "https://a/2")
    s2["tags"] = [{"name": "python"}]
    
    # First status should be fine
    assert not hype._hashtag_diversity_hit(s1)
    hype._remember_status(s1)
    
    # Second status with same hashtag should be blocked
    assert hype._hashtag_diversity_hit(s2)


def test_hashtag_diversity_allows_different_hashtags(tmp_path):
    """Test that hashtag diversity allows different hashtags."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.hashtag_diversity_enforced = True
    cfg.max_boosts_per_hashtag_per_run = 1
    hype = Hype(cfg)
    
    # Create statuses with different hashtags
    s1 = status_data("1", "https://a/1")
    s1["tags"] = [{"name": "python"}]
    s2 = status_data("2", "https://a/2")
    s2["tags"] = [{"name": "rust"}]
    
    # Both should be fine since they have different hashtags
    assert not hype._hashtag_diversity_hit(s1)
    hype._remember_status(s1)
    assert not hype._hashtag_diversity_hit(s2)


def test_hashtag_diversity_with_multiple_hashtags_per_post(tmp_path):
    """Test hashtag diversity with posts that have multiple hashtags."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.hashtag_diversity_enforced = True
    cfg.max_boosts_per_hashtag_per_run = 1
    hype = Hype(cfg)
    
    # First status with multiple hashtags
    s1 = status_data("1", "https://a/1")
    s1["tags"] = [{"name": "python"}, {"name": "programming"}]
    
    # Second status shares one hashtag
    s2 = status_data("2", "https://a/2")
    s2["tags"] = [{"name": "python"}, {"name": "webdev"}]
    
    # Third status shares the other hashtag
    s3 = status_data("3", "https://a/3")
    s3["tags"] = [{"name": "javascript"}, {"name": "programming"}]
    
    # First should be fine
    assert not hype._hashtag_diversity_hit(s1)
    hype._remember_status(s1)
    
    # Second should be blocked due to shared "python" hashtag
    assert hype._hashtag_diversity_hit(s2)
    
    # Third should be blocked due to shared "programming" hashtag
    assert hype._hashtag_diversity_hit(s3)


def test_hashtag_diversity_respects_limit_setting(tmp_path):
    """Test that hashtag diversity respects the max_boosts_per_hashtag_per_run setting."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.hashtag_diversity_enforced = True
    cfg.max_boosts_per_hashtag_per_run = 2  # Allow 2 per hashtag
    hype = Hype(cfg)
    
    # Create three statuses with the same hashtag
    s1 = status_data("1", "https://a/1")
    s1["tags"] = [{"name": "python"}]
    s2 = status_data("2", "https://a/2")
    s2["tags"] = [{"name": "python"}]
    s3 = status_data("3", "https://a/3")
    s3["tags"] = [{"name": "python"}]
    
    # First two should be fine
    assert not hype._hashtag_diversity_hit(s1)
    hype._remember_status(s1)
    assert not hype._hashtag_diversity_hit(s2)
    hype._remember_status(s2)
    
    # Third should be blocked
    assert hype._hashtag_diversity_hit(s3)


def test_hashtag_diversity_case_insensitive(tmp_path):
    """Test that hashtag diversity is case insensitive."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.hashtag_diversity_enforced = True
    cfg.max_boosts_per_hashtag_per_run = 1
    hype = Hype(cfg)
    
    # Create statuses with same hashtag in different cases
    s1 = status_data("1", "https://a/1")
    s1["tags"] = [{"name": "Python"}]
    s2 = status_data("2", "https://a/2")
    s2["tags"] = [{"name": "python"}]
    
    # First should be fine
    assert not hype._hashtag_diversity_hit(s1)
    hype._remember_status(s1)
    
    # Second should be blocked (case insensitive match)
    assert hype._hashtag_diversity_hit(s2)


def test_hashtag_diversity_resets_between_runs(tmp_path):
    """Test that hashtag diversity tracking resets between boost runs."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.hashtag_diversity_enforced = True
    cfg.max_boosts_per_hashtag_per_run = 1
    inst = types.SimpleNamespace(name="test", limit=1)
    cfg.subscribed_instances = [inst]
    hype = Hype(cfg)
    
    # Setup mocks for first run
    hype.client = MagicMock()
    m = MagicMock()
    m.trending_statuses.return_value = [{"uri": "https://a/1", "tags": [{"name": "python"}]}]
    hype.init_client = MagicMock(return_value=m)
    
    # Create status with hashtags for search result
    s1 = status_data("1", "https://a/1")
    s1["tags"] = [{"name": "python"}]
    hype.client.search_v2.return_value = {"statuses": [s1]}
    
    # First boost run
    hype.boost()
    
    # Verify hashtag was tracked
    assert "python" in hype._hashtags_boosted_this_run
    
    # Setup for second run with same hashtag
    m.trending_statuses.return_value = [{"uri": "https://a/2", "tags": [{"name": "python"}]}]
    s2 = status_data("2", "https://a/2")
    s2["tags"] = [{"name": "python"}]
    hype.client.search_v2.return_value = {"statuses": [s2]}
    
    # Second boost run should reset hashtag tracking
    hype.boost()
    
    # Should have been boosted again because tracking resets
    assert hype.client.status_reblog.call_count == 2


def test_hashtag_diversity_integration_with_seen_status(tmp_path):
    """Test that hashtag diversity integrates properly with _seen_status method."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.hashtag_diversity_enforced = True
    cfg.max_boosts_per_hashtag_per_run = 1
    hype = Hype(cfg)
    
    # Create two statuses with same hashtag
    s1 = status_data("1", "https://a/1")
    s1["tags"] = [{"name": "python"}]
    s2 = status_data("2", "https://a/2")
    s2["tags"] = [{"name": "python"}]
    
    # First should not be seen
    assert not hype._seen_status(s1)
    hype._remember_status(s1)
    
    # Second should be seen due to hashtag diversity
    assert hype._seen_status(s2)


def test_hashtag_diversity_with_no_hashtags(tmp_path):
    """Test that posts with no hashtags are not affected by hashtag diversity."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.hashtag_diversity_enforced = True
    cfg.max_boosts_per_hashtag_per_run = 1
    hype = Hype(cfg)
    
    # Create statuses with no hashtags
    s1 = status_data("1", "https://a/1")
    s1["tags"] = []
    s2 = status_data("2", "https://a/2")
    s2["tags"] = []
    
    # Both should be fine since no hashtags to conflict
    assert not hype._hashtag_diversity_hit(s1)
    hype._remember_status(s1)
    assert not hype._hashtag_diversity_hit(s2)
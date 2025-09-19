import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hype.hype import Hype
from tests.test_seen_status import DummyConfig, status_data


def test_complete_quality_and_related_hashtag_integration(tmp_path):
    """Test the complete integration of quality threshold and related hashtag features."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    
    # Configure quality threshold and related hashtags
    cfg.min_score_threshold = 8  # Higher threshold to filter out post #3
    cfg.hashtag_scores = {
        "homelab": 10.0,
        "python": 8.0,
    }
    cfg.related_hashtags = {
        "homelab": {
            "self-hosting": 0.5,  # 5 points bonus
            "server": 0.3,        # 3 points bonus
        },
        "python": {
            "programming": 0.4,   # 3.2 points bonus
        }
    }
    
    inst = types.SimpleNamespace(name="test_instance", limit=5)
    cfg.subscribed_instances = [inst]
    
    hype = Hype(cfg)
    
    # Create a variety of posts to test the complete functionality
    trending = [
        # High engagement post with homelab hashtag - should definitely pass
        {
            "uri": "https://example.com/1",
            "reblogs_count": 20,
            "favourites_count": 10,
            "created_at": "2024-01-01T00:00:00Z",
            "content": "Check out my new homelab setup!",
            "tags": [{"name": "homelab"}],
        },
        
        # Medium engagement post with related content - should pass with bonus
        {
            "uri": "https://example.com/2", 
            "reblogs_count": 5,
            "favourites_count": 3,
            "created_at": "2024-01-01T00:00:00Z",
            "content": "I love self-hosting my applications at home",
            "tags": [],
        },
        
        # Low engagement post with related content - should fail threshold
        {
            "uri": "https://example.com/3",
            "reblogs_count": 1,
            "favourites_count": 1, 
            "created_at": "2024-01-01T00:00:00Z",
            "content": "Just started self-hosting, any tips?",
            "tags": [],
        },
        
        # High engagement post with Python content - should pass
        {
            "uri": "https://example.com/4",
            "reblogs_count": 15,
            "favourites_count": 8,
            "created_at": "2024-01-01T00:00:00Z",
            "content": "Love programming in different languages",
            "tags": [],
        },
        
        # Low engagement post with no relevant content - should fail  
        {
            "uri": "https://example.com/5",
            "reblogs_count": 2,
            "favourites_count": 1,
            "created_at": "2024-01-01T00:00:00Z", 
            "content": "Random post about nothing special",
            "tags": [],
        },
    ]
    
    m = MagicMock()
    m.trending_statuses.return_value = trending
    hype.init_client = MagicMock(return_value=m)
    
    client = MagicMock()
    # Only posts 1, 2, and 4 should pass the quality threshold
    client.search_v2.side_effect = [
        {"statuses": [status_data("1", "https://example.com/1")]},
        {"statuses": [status_data("2", "https://example.com/2")]},
        {"statuses": [status_data("4", "https://example.com/4")]},
    ]
    hype.client = client
    
    hype.boost()
    
    # Verify only the qualifying posts were boosted
    assert client.status_reblog.call_count == 3
    assert client.search_v2.call_count == 3
    
    # Verify the search calls were for the expected URIs (in score-sorted order)
    search_calls = [call[0][0] for call in client.search_v2.call_args_list]
    expected_uris = ["https://example.com/1", "https://example.com/4", "https://example.com/2"]  # Sorted by score
    assert search_calls == expected_uris


def test_quality_threshold_with_all_posts_failing(tmp_path):
    """Test that boost cycle is skipped when all posts fail quality threshold."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.min_score_threshold = 10  # High threshold
    cfg.hashtag_scores = {"test": 5.0}
    cfg.related_hashtags = {
        "test": {
            "example": 0.5,
        }
    }
    
    inst = types.SimpleNamespace(name="test_instance", limit=3)
    cfg.subscribed_instances = [inst]
    
    hype = Hype(cfg)
    
    # All posts have low scores even with related bonuses
    trending = [
        {
            "uri": "https://example.com/1",
            "reblogs_count": 1,
            "favourites_count": 1,
            "created_at": "2024-01-01T00:00:00Z",
            "content": "This is an example post",  # Gets related bonus but still low
            "tags": [],
        },
        {
            "uri": "https://example.com/2",
            "reblogs_count": 2,
            "favourites_count": 1,
            "created_at": "2024-01-01T00:00:00Z",
            "content": "Another low engagement post",
            "tags": [],
        },
    ]
    
    m = MagicMock()
    m.trending_statuses.return_value = trending
    hype.init_client = MagicMock(return_value=m)
    
    client = MagicMock()
    hype.client = client
    
    hype.boost()
    
    # No posts should be boosted since all fail threshold
    assert client.status_reblog.call_count == 0
    assert client.search_v2.call_count == 0


def test_related_hashtag_scoring_affects_quality_threshold(tmp_path):
    """Test that related hashtag bonuses can help posts pass quality threshold."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.min_score_threshold = 6  # Moderate threshold
    cfg.hashtag_scores = {"homelab": 10.0}
    cfg.related_hashtags = {
        "homelab": {
            "self-hosting": 0.5,  # 5 points bonus
        }
    }
    
    inst = types.SimpleNamespace(name="test_instance", limit=2)
    cfg.subscribed_instances = [inst]
    
    hype = Hype(cfg)
    
    trending = [
        # This post would fail without the related hashtag bonus
        {
            "uri": "https://example.com/1",
            "reblogs_count": 3,     # ~2.8 points engagement
            "favourites_count": 2,  # ~1.1 points engagement  
            "created_at": "2024-01-01T00:00:00Z",
            "content": "I love self-hosting apps",  # +5 points related bonus = ~8.9 total
            "tags": [],
        },
        # This post fails even with related content (if any)
        {
            "uri": "https://example.com/2",
            "reblogs_count": 1,     # ~1.4 points engagement
            "favourites_count": 1,  # ~0.7 points engagement
            "created_at": "2024-01-01T00:00:00Z", 
            "content": "Just a random post",  # No bonus = ~2.1 total
            "tags": [],
        },
    ]
    
    m = MagicMock()
    m.trending_statuses.return_value = trending
    hype.init_client = MagicMock(return_value=m)
    
    client = MagicMock()
    client.search_v2.return_value = {"statuses": [status_data("1", "https://example.com/1")]}
    hype.client = client
    
    hype.boost()
    
    # Only the first post should pass thanks to the related hashtag bonus
    assert client.status_reblog.call_count == 1
    assert client.search_v2.call_count == 1
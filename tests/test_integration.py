import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

from mastodon.errors import MastodonNotFoundError

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hype.hype import Hype
from tests.test_seen_status import DummyConfig, status_data


def test_complete_quality_and_related_hashtag_integration(tmp_path):
    """Test the complete integration of quality threshold and related hashtag features."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.min_replies = 2
    
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
            "id": "remote-1",
            "uri": "https://example.com/1",
            "reblogs_count": 20,
            "favourites_count": 10,
            "created_at": "2024-01-01T00:00:00Z",
            "content": "Check out my new homelab setup!",
            "tags": [{"name": "homelab"}],
            "replies_count": 2,
        },
        
        # Medium engagement post with related content - should pass with bonus
        {
            "id": "remote-2",
            "uri": "https://example.com/2",
            "reblogs_count": 5,
            "favourites_count": 3,
            "created_at": "2024-01-01T00:00:00Z",
            "content": "I love self-hosting my applications at home",
            "tags": [],
            "replies_count": 2,
        },
        
        # Low engagement post with related content - should fail threshold
        {
            "id": "remote-3",
            "uri": "https://example.com/3",
            "reblogs_count": 0,
            "favourites_count": 0,
            "created_at": "2024-01-01T00:00:00Z",
            "content": "Just started self-hosting, any tips?",
            "tags": [],
            "replies_count": 2,
        },
        
        # High engagement post with Python content - should pass
        {
            "id": "remote-4",
            "uri": "https://example.com/4",
            "reblogs_count": 15,
            "favourites_count": 8,
            "created_at": "2024-01-01T00:00:00Z",
            "content": "Love programming in different languages",
            "tags": [],
            "replies_count": 2,
        },
        
        # Low engagement post with no relevant content - should fail  
        {
            "id": "remote-5",
            "uri": "https://example.com/5",
            "reblogs_count": 0,
            "favourites_count": 0,
            "created_at": "2024-01-01T00:00:00Z",
            "content": "Random post about nothing special",
            "tags": [],
            "replies_count": 2,
        },
    ]
    
    m = MagicMock()
    m.trending_statuses.return_value = trending
    hype.init_client = MagicMock(return_value=m)
    
    client = MagicMock()
    client.status_reblog.side_effect = [
        MastodonNotFoundError("Not found"), None,
        MastodonNotFoundError("Not found"), None,
        MastodonNotFoundError("Not found"), None,
    ]

    def search_side_effect(uri, result_type=None, resolve=None):
        responses = {
            "https://example.com/1": {"statuses": [{**status_data("1", "https://example.com/1"), "replies_count": 2}]},
            "https://example.com/2": {"statuses": [{**status_data("2", "https://example.com/2"), "replies_count": 2}]},
            "https://example.com/4": {"statuses": [{**status_data("4", "https://example.com/4"), "replies_count": 2}]},
        }
        return responses.get(uri, {"statuses": []})

    client.search_v2.side_effect = search_side_effect
    hype.client = client
    
    hype.boost()
    
    # Verify only the qualifying posts were boosted
    assert client.status_reblog.call_count == 6
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
    client.status_reblog.side_effect = [
        MastodonNotFoundError("Not found"), None
    ]
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
    cfg.min_replies = 2
    
    inst = types.SimpleNamespace(name="test_instance", limit=2)
    cfg.subscribed_instances = [inst]
    
    hype = Hype(cfg)
    
    trending = [
        # This post would fail without the related hashtag bonus
        {
            "id": "remote-related-1",
            "uri": "https://example.com/1",
            "reblogs_count": 3,     # ~2.8 points engagement
            "favourites_count": 2,  # ~1.1 points engagement
            "created_at": "2024-01-01T00:00:00Z",
            "content": "I love self-hosting apps",  # +5 points related bonus = ~8.9 total
            "tags": [],
            "replies_count": 2,
        },
        # This post fails even with related content (if any)
        {
            "id": "remote-related-2",
            "uri": "https://example.com/2",
            "reblogs_count": 1,     # ~1.4 points engagement
            "favourites_count": 1,  # ~0.7 points engagement
            "created_at": "2024-01-01T00:00:00Z",
            "content": "Just a random post",  # No bonus = ~2.1 total
            "tags": [],
            "replies_count": 2,
        },
    ]
    
    m = MagicMock()
    m.trending_statuses.return_value = trending
    hype.init_client = MagicMock(return_value=m)
    
    client = MagicMock()
    def single_search_side_effect(uri, result_type=None, resolve=None):
        if uri == "https://example.com/1":
            return {"statuses": [{**status_data("1", "https://example.com/1"), "replies_count": 2}]}
        return {"statuses": []}

    client.search_v2.side_effect = single_search_side_effect
    client.status_reblog.side_effect = [
        MastodonNotFoundError("Not found"), None
    ]
    client.status_reblog.side_effect = [
        MastodonNotFoundError("Not found"), None
    ]
    hype.client = client
    
    hype.boost()
    
    # Only the first post should pass thanks to the related hashtag bonus
    assert client.status_reblog.call_count == 2
    assert client.search_v2.call_count == 1

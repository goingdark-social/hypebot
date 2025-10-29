import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mastodon.errors import MastodonNotFoundError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hype.hype import Hype
from tests.test_seen_status import DummyConfig, status_data


def test_quality_threshold_filters_low_scoring_posts(tmp_path):
    """Test that posts below the quality threshold are filtered out."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.min_score_threshold = 5  # Set threshold at 5 (raw score)
    cfg.min_replies = 2
    inst = types.SimpleNamespace(name="i1", limit=3)
    cfg.subscribed_instances = [inst]
    
    hype = Hype(cfg)
    
    # Create posts with different scores
    trending = [
        {
            "id": "remote-1",
            "uri": "https://a/1",
            "reblogs_count": 100,
            "favourites_count": 50,
            "created_at": "2024-01-01T00:00:00Z",
            "replies_count": 2,
        },
        {
            "id": "remote-2",
            "uri": "https://a/2",
            "reblogs_count": 1,
            "favourites_count": 1,
            "created_at": "2024-01-01T00:00:00Z",
            "replies_count": 2,
        },
        {
            "id": "remote-3",
            "uri": "https://a/3",
            "reblogs_count": 10,
            "favourites_count": 5,
            "created_at": "2024-01-01T00:00:00Z",
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
    ]
    # Only the high and medium scoring posts should be searched for
    client.search_v2.side_effect = [
        {"statuses": [{**status_data("1", "https://a/1"), "replies_count": 2}]},
        {"statuses": [{**status_data("3", "https://a/3"), "replies_count": 2}]},
    ]
    hype.client = client
    
    hype.boost()
    
    # Should boost 2 posts (the ones above threshold)
    assert client.status_reblog.call_count == 4
    # Should search for 2 posts (the ones that met the threshold)
    assert client.search_v2.call_count == 2


def test_quality_threshold_disabled_by_default(tmp_path):
    """Test that quality threshold is disabled by default (min_score_threshold = 0)."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    # Default value should be 0 (disabled)
    assert cfg.min_score_threshold == 0
    cfg.min_replies = 2
    
    inst = types.SimpleNamespace(name="i1", limit=2)
    cfg.subscribed_instances = [inst]
    
    hype = Hype(cfg)
    
    trending = [
        {
            "id": "remote-default-1",
            "uri": "https://a/1",
            "reblogs_count": 1,
            "favourites_count": 1,
            "created_at": "2024-01-01T00:00:00Z",
            "replies_count": 2,
        },
        {
            "id": "remote-default-2",
            "uri": "https://a/2",
            "reblogs_count": 1,
            "favourites_count": 1,
            "created_at": "2024-01-01T00:00:00Z",
            "replies_count": 2,
        },
    ]
    
    m = MagicMock()
    m.trending_statuses.return_value = trending
    hype.init_client = MagicMock(return_value=m)
    
    client = MagicMock()
    client.search_v2.side_effect = [
        {"statuses": [{**status_data("1", "https://a/1"), "replies_count": 2}]},
        {"statuses": [{**status_data("2", "https://a/2"), "replies_count": 2}]},
    ]
    client.status_reblog.side_effect = [
        MastodonNotFoundError("Not found"), None,
        MastodonNotFoundError("Not found"), None,
    ]
    hype.client = client
    
    hype.boost()
    
    # Should boost both posts when threshold is 0
    assert client.status_reblog.call_count == 4


def test_quality_threshold_skips_boost_cycle_when_no_qualifying_content(tmp_path):
    """Test that entire boost cycle is skipped when no content meets threshold."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.min_score_threshold = 10  # Higher than typical low-engagement scores (~2)
    cfg.min_replies = 2
    inst = types.SimpleNamespace(name="i1", limit=2)
    cfg.subscribed_instances = [inst]
    
    hype = Hype(cfg)
    
    # All posts have low scores
    trending = [
        {
            "id": "remote-skip-1",
            "uri": "https://a/1",
            "reblogs_count": 1,
            "favourites_count": 1,
            "created_at": "2024-01-01T00:00:00Z",
            "replies_count": 2,
        },
        {
            "id": "remote-skip-2",
            "uri": "https://a/2",
            "reblogs_count": 1,
            "favourites_count": 1,
            "created_at": "2024-01-01T00:00:00Z",
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
    ]
    hype.client = client
    
    hype.boost()
    
    # No posts should be boosted or even searched for
    assert client.status_reblog.call_count == 0
    assert client.search_v2.call_count == 0


def test_quality_threshold_respects_raw_scores(tmp_path):
    """Test that quality threshold works with raw scores before normalization."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.min_score_threshold = 8  # Only posts with raw score >= 8
    cfg.min_replies = 2
    inst = types.SimpleNamespace(name="i1", limit=4)
    cfg.subscribed_instances = [inst]
    
    hype = Hype(cfg)
    
    # Create posts with varied engagement levels
    trending = [
        {
            "id": "remote-raw-1",
            "uri": "https://a/1",
            "reblogs_count": 100,
            "favourites_count": 100,
            "created_at": "2024-01-01T00:00:00Z",
            "replies_count": 2,
        },
        {
            "id": "remote-raw-2",
            "uri": "https://a/2",
            "reblogs_count": 25,
            "favourites_count": 15,
            "created_at": "2024-01-01T00:00:00Z",
            "replies_count": 2,
        },
        {
            "id": "remote-raw-3",
            "uri": "https://a/3",
            "reblogs_count": 5,
            "favourites_count": 3,
            "created_at": "2024-01-01T00:00:00Z",
            "replies_count": 2,
        },
        {
            "id": "remote-raw-4",
            "uri": "https://a/4",
            "reblogs_count": 1,
            "favourites_count": 1,
            "created_at": "2024-01-01T00:00:00Z",
            "replies_count": 2,
        },
    ]
    
    m = MagicMock()
    m.trending_statuses.return_value = trending
    hype.init_client = MagicMock(return_value=m)
    
    client = MagicMock()
    # Only the top 2 posts should qualify (raw scores >= 8)
    client.search_v2.side_effect = [
        {"statuses": [{**status_data("1", "https://a/1"), "replies_count": 2}]},
        {"statuses": [{**status_data("2", "https://a/2"), "replies_count": 2}]},
    ]
    client.status_reblog.side_effect = [
        MastodonNotFoundError("Not found"), None,
        MastodonNotFoundError("Not found"), None,
    ]
    hype.client = client

    hype.boost()

    # Should boost 2 posts (the ones above threshold)
    assert client.status_reblog.call_count == 4
    assert client.search_v2.call_count == 2


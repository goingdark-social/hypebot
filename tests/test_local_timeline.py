import sys
from pathlib import Path
import types
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hype.hype import Hype
from tests.test_seen_status import DummyConfig


def test_local_timeline_enabled_by_default(tmp_path):
    """Test that local timeline is enabled by default"""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    inst = types.SimpleNamespace(name="remote.social", fetch_limit=20, boost_limit=2)
    cfg.subscribed_instances = [inst]
    hype = Hype(cfg)
    
    # Mock remote instance
    remote_mock = MagicMock()
    remote_mock.trending_statuses.return_value = []
    hype.init_client = MagicMock(return_value=remote_mock)
    
    # Mock bot client
    bot_client = MagicMock()
    bot_client.timeline_local = MagicMock(return_value=[])
    hype.client = bot_client
    
    hype.boost()
    
    # timeline_local should be called when enabled (default)
    assert bot_client.timeline_local.call_count == 1


def test_local_timeline_can_be_disabled(tmp_path):
    """Test that local timeline can be explicitly disabled"""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.local_timeline_enabled = False  # Explicitly disable
    inst = types.SimpleNamespace(name="remote.social", fetch_limit=20, boost_limit=2)
    cfg.subscribed_instances = [inst]
    hype = Hype(cfg)
    
    # Mock remote instance
    remote_mock = MagicMock()
    remote_mock.trending_statuses.return_value = []
    hype.init_client = MagicMock(return_value=remote_mock)
    
    # Mock bot client
    bot_client = MagicMock()
    bot_client.timeline_local = MagicMock(return_value=[])
    hype.client = bot_client
    
    hype.boost()
    
    # timeline_local should not be called when disabled
    assert bot_client.timeline_local.call_count == 0


def test_local_timeline_fetches_when_enabled(tmp_path):
    """Test that local timeline is fetched when enabled"""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.local_timeline_enabled = True
    cfg.local_timeline_fetch_limit = 10
    hype = Hype(cfg)
    
    # Mock bot client with local timeline
    bot_client = MagicMock()
    bot_client.timeline_local = MagicMock(return_value=[])
    hype.client = bot_client
    
    hype.boost()
    
    # timeline_local should be called with the right limit
    bot_client.timeline_local.assert_called_once_with(limit=10)


def test_local_timeline_filters_old_posts(tmp_path):
    """Test that posts older than today are filtered out"""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.local_timeline_enabled = True
    cfg.local_timeline_fetch_limit = 20
    cfg.local_timeline_boost_limit = 5
    hype = Hype(cfg)
    
    # Create posts from different days
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    
    local_posts = [
        {
            "id": "1",
            "uri": "https://local/1",
            "url": "https://local/1",
            "created_at": today,
            "reblogs_count": 5,
            "favourites_count": 3,
            "replies_count": 1,
            "account": {"acct": "user1@local"},
            "tags": [],
            "content": "Today's post"
        },
        {
            "id": "2",
            "uri": "https://local/2",
            "url": "https://local/2",
            "created_at": yesterday,
            "reblogs_count": 10,
            "favourites_count": 10,
            "replies_count": 5,
            "account": {"acct": "user2@local"},
            "tags": [],
            "content": "Yesterday's post"
        }
    ]
    
    # Mock bot client
    bot_client = MagicMock()
    bot_client.timeline_local = MagicMock(return_value=local_posts)
    bot_client.status_reblog = MagicMock()
    hype.client = bot_client
    
    hype.boost()
    
    # Only today's post should be boosted
    assert bot_client.status_reblog.call_count == 1
    # Verify it's the correct post (status object is passed, check its ID)
    boosted_status = bot_client.status_reblog.call_args[0][0]
    assert boosted_status["id"] == "1"


def test_local_timeline_filters_low_engagement(tmp_path):
    """Test that posts without minimum engagement are filtered"""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.local_timeline_enabled = True
    cfg.local_timeline_fetch_limit = 20
    cfg.local_timeline_boost_limit = 5
    cfg.local_timeline_min_engagement = 3  # Require at least 3 total interactions
    hype = Hype(cfg)
    
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    
    local_posts = [
        {
            "id": "1",
            "uri": "https://local/1",
            "url": "https://local/1",
            "created_at": today,
            "reblogs_count": 1,
            "favourites_count": 1,
            "replies_count": 0,  # Total: 2 (below threshold)
            "account": {"acct": "user1@local"},
            "tags": [],
            "content": "Low engagement post"
        },
        {
            "id": "2",
            "uri": "https://local/2",
            "url": "https://local/2",
            "created_at": today,
            "reblogs_count": 1,
            "favourites_count": 1,
            "replies_count": 1,  # Total: 3 (meets threshold)
            "account": {"acct": "user2@local"},
            "tags": [],
            "content": "Good engagement post"
        }
    ]
    
    # Mock bot client
    bot_client = MagicMock()
    bot_client.timeline_local = MagicMock(return_value=local_posts)
    bot_client.status_reblog = MagicMock()
    hype.client = bot_client
    
    hype.boost()
    
    # Only the post with enough engagement should be boosted
    assert bot_client.status_reblog.call_count == 1
    boosted_status = bot_client.status_reblog.call_args[0][0]
    assert boosted_status["id"] == "2"


def test_local_timeline_respects_boost_limit(tmp_path):
    """Test that local timeline respects its boost limit"""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.local_timeline_enabled = True
    cfg.local_timeline_fetch_limit = 20
    cfg.local_timeline_boost_limit = 2  # Only boost 2 from local
    hype = Hype(cfg)
    
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    
    # Create 4 qualifying posts from local timeline
    local_posts = []
    for i in range(1, 5):
        local_posts.append({
            "id": str(i),
            "uri": f"https://local/{i}",
            "url": f"https://local/{i}",
            "created_at": today,
            "reblogs_count": 5,
            "favourites_count": 5,
            "replies_count": 1,
            "account": {"acct": f"user{i}@local"},
            "tags": [],
            "content": f"Post {i}"
        })
    
    # Mock bot client
    bot_client = MagicMock()
    bot_client.timeline_local = MagicMock(return_value=local_posts)
    bot_client.status_reblog = MagicMock()
    hype.client = bot_client
    
    hype.boost()
    
    # Should only boost 2 posts (the limit)
    assert bot_client.status_reblog.call_count == 2


def test_local_timeline_with_remote_instances(tmp_path):
    """Test that local timeline works alongside remote instances"""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.local_timeline_enabled = True
    cfg.local_timeline_fetch_limit = 20
    cfg.local_timeline_boost_limit = 1
    
    # Add a remote instance
    inst = types.SimpleNamespace(name="remote.social", fetch_limit=20, boost_limit=1)
    cfg.subscribed_instances = [inst]
    
    hype = Hype(cfg)
    
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    
    # Local timeline post
    local_posts = [{
        "id": "local1",
        "uri": "https://local/1",
        "url": "https://local/1",
        "created_at": today,
        "reblogs_count": 5,
        "favourites_count": 5,
        "replies_count": 1,
        "account": {"acct": "localuser@local"},
        "tags": [],
        "content": "Local post"
    }]
    
    # Remote trending post
    remote_posts = [{
        "id": "remote1",
        "uri": "https://remote/1",
        "url": "https://remote/1",
        "created_at": today,
        "reblogs_count": 10,
        "favourites_count": 10,
        "replies_count": 1,
        "account": {"acct": "remoteuser@remote.social"},
        "tags": [],
        "content": "Remote post"
    }]
    
    # Mock remote instance client
    remote_mock = MagicMock()
    remote_mock.trending_statuses.return_value = remote_posts
    hype.init_client = MagicMock(return_value=remote_mock)
    
    # Mock bot client
    bot_client = MagicMock()
    bot_client.timeline_local = MagicMock(return_value=local_posts)
    bot_client.status_reblog = MagicMock()
    hype.client = bot_client
    
    hype.boost()
    
    # Should boost both (1 from local, 1 from remote)
    assert bot_client.status_reblog.call_count == 2

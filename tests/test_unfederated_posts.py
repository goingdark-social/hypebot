import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hype.hype import Hype
from tests.test_seen_status import DummyConfig, status_data


def test_fetches_unfederated_posts_with_resolve_true(tmp_path):
    """Test that the bot can fetch and boost unfederated posts by using resolve=True."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    inst = types.SimpleNamespace(name="test_instance", limit=1)
    cfg.subscribed_instances = [inst]
    hype = Hype(cfg)
    
    # Mock trending status from remote instance (unfederated)
    trending = [
        {
            "uri": "https://remote.instance/status/12345",
            "reblogs_count": 10,
            "favourites_count": 20,
            "created_at": "2024-01-01T00:00:00Z",
        },
    ]
    
    # Mock the remote instance client that fetches trending statuses
    remote_client = MagicMock()
    remote_client.trending_statuses.return_value = trending
    hype.init_client = MagicMock(return_value=remote_client)
    
    # Mock the bot's own client
    bot_client = MagicMock()
    
    # The search_v2 call with resolve=True should successfully fetch the unfederated status
    fetched_status = status_data("12345", "https://remote.instance/status/12345")
    bot_client.search_v2.return_value = {"statuses": [fetched_status]}
    
    hype.client = bot_client
    
    # The boost cycle should complete and boost the unfederated status
    hype.boost()
    
    # Verify that search_v2 was called with resolve=True
    assert bot_client.search_v2.call_count == 1
    search_call_kwargs = bot_client.search_v2.call_args[1]
    assert search_call_kwargs.get("resolve") == True, "search_v2 should be called with resolve=True"
    
    # Verify the status was boosted
    assert bot_client.status_reblog.call_count == 1
    boosted_status = bot_client.status_reblog.call_args[0][0]
    assert boosted_status["uri"] == "https://remote.instance/status/12345"


def test_handles_empty_search_result_gracefully(tmp_path):
    """Test that the bot handles empty search results (even with resolve=True) gracefully."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    inst = types.SimpleNamespace(name="test_instance", limit=1)
    cfg.subscribed_instances = [inst]
    hype = Hype(cfg)
    
    # Mock trending status from remote instance
    trending = [
        {
            "uri": "https://remote.instance/status/99999",
            "reblogs_count": 5,
            "favourites_count": 10,
            "created_at": "2024-01-01T00:00:00Z",
        },
    ]
    
    # Mock the remote instance client
    remote_client = MagicMock()
    remote_client.trending_statuses.return_value = trending
    hype.init_client = MagicMock(return_value=remote_client)
    
    # Mock the bot's own client - return empty result (e.g., deleted status)
    bot_client = MagicMock()
    bot_client.search_v2.return_value = {"statuses": []}
    
    hype.client = bot_client
    
    # The boost cycle should complete without crashing
    hype.boost()
    
    # Verify that search_v2 was called
    assert bot_client.search_v2.call_count == 1
    
    # Verify that no status was boosted (empty result)
    assert bot_client.status_reblog.call_count == 0

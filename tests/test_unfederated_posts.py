import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hype.hype import Hype
from tests.test_seen_status import DummyConfig, status_data


def test_fetches_unfederated_posts_with_resolve_true(tmp_path):
    """Test that the bot can fetch and boost unfederated posts when federation is enabled."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    inst = types.SimpleNamespace(name="test_instance", limit=1)
    cfg.subscribed_instances = [inst]
    cfg.federate_missing_statuses = True  # Enable proactive federation
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
    
    # First search with resolve=False returns empty (not in local DB)
    # Second search with resolve=True successfully fetches the unfederated status
    fetched_status = status_data("12345", "https://remote.instance/status/12345")
    bot_client.search_v2.side_effect = [
        {"statuses": []},  # resolve=False: not found locally
        {"statuses": [fetched_status]},  # resolve=True: fetched from remote
    ]
    
    hype.client = bot_client
    
    # The boost cycle should complete and boost the unfederated status
    hype.boost()
    
    # Verify that search_v2 was called twice (once with resolve=False, once with resolve=True)
    assert bot_client.search_v2.call_count == 2
    first_call_kwargs = bot_client.search_v2.call_args_list[0][1]
    second_call_kwargs = bot_client.search_v2.call_args_list[1][1]
    assert first_call_kwargs.get("resolve") == False, "First search should use resolve=False"
    assert second_call_kwargs.get("resolve") == True, "Second search should use resolve=True for federation"
    
    # Verify the status was boosted
    assert bot_client.status_reblog.call_count == 1
    boosted_status = bot_client.status_reblog.call_args[0][0]
    assert boosted_status["uri"] == "https://remote.instance/status/12345"


def test_handles_empty_search_result_gracefully(tmp_path):
    """Test that the bot handles empty search results (even with resolve=True) gracefully."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    inst = types.SimpleNamespace(name="test_instance", limit=1)
    cfg.subscribed_instances = [inst]
    cfg.federate_missing_statuses = True  # Enable federation
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
    
    # Mock the bot's own client - return empty result (e.g., deleted status or resolve failed)
    bot_client = MagicMock()
    bot_client.search_v2.return_value = {"statuses": []}
    
    hype.client = bot_client
    
    # The boost cycle should complete without crashing
    hype.boost()
    
    # Verify that search_v2 was called twice (resolve=False, then resolve=True)
    assert bot_client.search_v2.call_count == 2
    
    # Verify that no status was boosted (empty result)
    assert bot_client.status_reblog.call_count == 0


def test_skips_unfederated_posts_when_federation_disabled(tmp_path):
    """Test that unfederated posts are skipped when federate_missing_statuses=False."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    inst = types.SimpleNamespace(name="test_instance", limit=1)
    cfg.subscribed_instances = [inst]
    cfg.federate_missing_statuses = False  # Federation disabled (default)
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
    
    # Mock the remote instance client
    remote_client = MagicMock()
    remote_client.trending_statuses.return_value = trending
    hype.init_client = MagicMock(return_value=remote_client)
    
    # Mock the bot's own client
    bot_client = MagicMock()
    
    # First search with resolve=False returns empty (not in local DB)
    bot_client.search_v2.return_value = {"statuses": []}
    
    hype.client = bot_client
    
    # The boost cycle should complete without attempting federation
    hype.boost()
    
    # Verify that search_v2 was called only once (with resolve=False)
    # It should NOT call with resolve=True since federation is disabled
    assert bot_client.search_v2.call_count == 1
    call_kwargs = bot_client.search_v2.call_args[1]
    assert call_kwargs.get("resolve") == False
    
    # Verify that no status was boosted
    assert bot_client.status_reblog.call_count == 0


def test_federation_handles_api_errors_gracefully(tmp_path):
    """Test that federation handles API errors gracefully with proper error logging."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    inst = types.SimpleNamespace(name="test_instance", limit=1)
    cfg.subscribed_instances = [inst]
    cfg.federate_missing_statuses = True
    hype = Hype(cfg)
    
    from mastodon.errors import MastodonAPIError
    
    # Mock trending status
    trending = [
        {
            "uri": "https://remote.instance/status/12345",
            "reblogs_count": 10,
            "favourites_count": 20,
            "created_at": "2024-01-01T00:00:00Z",
        },
    ]
    
    # Mock the remote instance client
    remote_client = MagicMock()
    remote_client.trending_statuses.return_value = trending
    hype.init_client = MagicMock(return_value=remote_client)
    
    # Mock the bot's own client to raise an error on the second search
    bot_client = MagicMock()
    bot_client.search_v2.side_effect = [
        {"statuses": []},  # First call: not found locally
        MastodonAPIError("Unauthorized", 401, "Unauthorized", None),  # Second call: federation fails
    ]
    
    hype.client = bot_client
    
    # The boost cycle should complete without crashing
    hype.boost()
    
    # Verify that search_v2 was called twice
    assert bot_client.search_v2.call_count == 2
    
    # Verify that no status was boosted
    assert bot_client.status_reblog.call_count == 0

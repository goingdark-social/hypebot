import sys
from pathlib import Path
import types
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hype.hype import Hype
from tests.test_seen_status import DummyConfig, status_data
from mastodon.errors import MastodonInternalServerError, MastodonAPIError


def test_handles_mastodon_internal_server_error_during_search(tmp_path):
    """Test that MastodonInternalServerError during search_v2 is handled gracefully."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    inst = types.SimpleNamespace(name="test_instance", limit=2)
    cfg.subscribed_instances = [inst]
    hype = Hype(cfg)
    
    # Mock trending statuses from remote instance
    trending = [
        {
            "uri": "https://remote.instance/status/1",
            "reblogs_count": 5,
            "favourites_count": 10,
            "created_at": "2024-01-01T00:00:00Z",
        },
        {
            "uri": "https://remote.instance/status/2", 
            "reblogs_count": 3,
            "favourites_count": 8,
            "created_at": "2024-01-02T00:00:00Z",
        },
    ]
    
    # Mock the remote instance client that fetches trending statuses
    remote_client = MagicMock()
    remote_client.trending_statuses.return_value = trending
    hype.init_client = MagicMock(return_value=remote_client)
    
    # Mock the bot's own client where search_v2 will fail
    bot_client = MagicMock()
    
    # First search_v2 call raises MastodonInternalServerError (500 error)
    # Second search_v2 call succeeds with a status  
    s2 = status_data("2", "https://remote.instance/status/2")
    bot_client.search_v2.side_effect = [
        MastodonInternalServerError("Mastodon API returned error", 500, "Internal Server Error", None),
        {"statuses": [s2]}
    ]
    
    hype.client = bot_client
    
    # The boost cycle should complete without crashing
    # It should skip the first status that caused the 500 error
    # and successfully boost the second status
    hype.boost()
    
    # Verify that search_v2 was called twice (once for each status)
    assert bot_client.search_v2.call_count == 2
    
    # Verify that only one status was boosted (the second one that didn't error)
    assert bot_client.status_reblog.call_count == 1
    
    # Verify the boosted status was the second one
    boosted_status = bot_client.status_reblog.call_args[0][0]
    assert boosted_status["uri"] == "https://remote.instance/status/2"


def test_handles_other_mastodon_api_errors_during_search(tmp_path):
    """Test that other MastodonAPIError subclasses are also handled gracefully."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    inst = types.SimpleNamespace(name="test_instance", limit=1)
    cfg.subscribed_instances = [inst]
    hype = Hype(cfg)
    
    # Mock trending statuses from remote instance
    trending = [
        {
            "uri": "https://remote.instance/status/1",
            "reblogs_count": 5,
            "favourites_count": 10,
            "created_at": "2024-01-01T00:00:00Z",
        },
    ]
    
    # Mock the remote instance client that fetches trending statuses
    remote_client = MagicMock()
    remote_client.trending_statuses.return_value = trending
    hype.init_client = MagicMock(return_value=remote_client)
    
    # Mock the bot's own client where search_v2 will fail with a generic MastodonAPIError
    bot_client = MagicMock()
    bot_client.search_v2.side_effect = MastodonAPIError("Generic API error")
    
    hype.client = bot_client
    
    # The boost cycle should complete without crashing  
    hype.boost()
    
    # Verify that search_v2 was called once
    assert bot_client.search_v2.call_count == 1
    
    # Verify that no status was boosted due to the API error
    assert bot_client.status_reblog.call_count == 0


def test_continues_after_api_error_with_multiple_statuses(tmp_path):
    """Test that the bot continues processing other statuses after an API error."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    inst = types.SimpleNamespace(name="test_instance", limit=3)
    cfg.subscribed_instances = [inst]
    hype = Hype(cfg)
    
    # Mock trending statuses from remote instance
    trending = [
        {
            "uri": "https://remote.instance/status/1",
            "reblogs_count": 5,
            "favourites_count": 10,
            "created_at": "2024-01-01T00:00:00Z",
        },
        {
            "uri": "https://remote.instance/status/2", 
            "reblogs_count": 3,
            "favourites_count": 8,
            "created_at": "2024-01-02T00:00:00Z",
        },
        {
            "uri": "https://remote.instance/status/3",
            "reblogs_count": 7,
            "favourites_count": 12,
            "created_at": "2024-01-03T00:00:00Z",
        },
    ]
    
    # Mock the remote instance client that fetches trending statuses
    remote_client = MagicMock()
    remote_client.trending_statuses.return_value = trending
    hype.init_client = MagicMock(return_value=remote_client)
    
    # Mock the bot's own client
    bot_client = MagicMock()
    
    # Create mock statuses for successful responses
    s1 = status_data("1", "https://remote.instance/status/1")  
    s3 = status_data("3", "https://remote.instance/status/3")
    
    # First call succeeds, second fails with 500 error, third succeeds
    bot_client.search_v2.side_effect = [
        {"statuses": [s1]},
        MastodonInternalServerError("Mastodon API returned error", 500, "Internal Server Error", None),
        {"statuses": [s3]}
    ]
    
    hype.client = bot_client
    
    # The boost cycle should complete without crashing
    hype.boost()
    
    # Verify that search_v2 was called three times (once for each status)
    assert bot_client.search_v2.call_count == 3
    
    # Verify that two statuses were boosted (first and third, skipping the second due to error)
    assert bot_client.status_reblog.call_count == 2
    
    # Verify the boosted statuses were the first and third ones
    boosted_calls = bot_client.status_reblog.call_args_list
    assert boosted_calls[0][0][0]["uri"] == "https://remote.instance/status/1"
    assert boosted_calls[1][0][0]["uri"] == "https://remote.instance/status/3"


def test_handles_401_unauthorized_search_error(tmp_path):
    """Test that 401 Unauthorized errors during search_v2 are handled gracefully."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    inst = types.SimpleNamespace(name="test_instance", limit=1)
    cfg.subscribed_instances = [inst]
    hype = Hype(cfg)
    
    # Mock trending statuses from remote instance
    trending = [
        {
            "uri": "https://remote.instance/status/1",
            "reblogs_count": 5,
            "favourites_count": 10,
            "created_at": "2024-01-01T00:00:00Z",
        },
    ]
    
    # Mock the remote instance client that fetches trending statuses
    remote_client = MagicMock()
    remote_client.trending_statuses.return_value = trending
    hype.init_client = MagicMock(return_value=remote_client)
    
    # Mock the bot's own client where search_v2 will fail with 401 Unauthorized
    bot_client = MagicMock()
    bot_client.search_v2.side_effect = MastodonAPIError(
        "Mastodon API returned error", 401, "Unauthorized", 
        "Search queries that resolve remote resources are not supported without authentication"
    )
    
    hype.client = bot_client
    
    # The boost cycle should complete without crashing  
    hype.boost()
    
    # Verify that search_v2 was called once
    assert bot_client.search_v2.call_count == 1
    
    # Verify that no status was boosted due to the 401 error
    assert bot_client.status_reblog.call_count == 0
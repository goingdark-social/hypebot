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
    from mastodon.errors import MastodonNotFoundError
    
    cfg = DummyConfig(str(tmp_path / "state.json"))
    inst = types.SimpleNamespace(name="test_instance", limit=1)
    cfg.subscribed_instances = [inst]
    cfg.federate_missing_statuses = True  # Enable proactive federation
    hype = Hype(cfg)
    
    # Trending returns full status object
    trending_status = status_data("12345", "https://remote.instance/status/12345")
    trending = [trending_status]
    
    # Mock the remote instance client that fetches trending statuses
    remote_client = MagicMock()
    remote_client.trending_statuses.return_value = trending
    hype.init_client = MagicMock(return_value=remote_client)
    
    # Mock the bot's own client
    bot_client = MagicMock()
    
    # First reblog attempt fails (404 - not in local DB)
    # Then search with resolve=True successfully fetches the unfederated status
    # Finally, reblog succeeds
    federated_status = status_data("12345", "https://remote.instance/status/12345")
    bot_client.status_reblog.side_effect = [
        MastodonNotFoundError(),  # First reblog: not in local DB
        None,  # Second reblog: succeeds after federation
    ]
    bot_client.search_v2.return_value = {"statuses": [federated_status]}
    
    hype.client = bot_client
    
    # The boost cycle should complete and boost the unfederated status
    hype.boost()
    
    # Verify that reblog was tried twice (before and after federation)
    assert bot_client.status_reblog.call_count == 2
    
    # Verify that search_v2 was called once with resolve=True for federation
    assert bot_client.search_v2.call_count == 1
    search_call_kwargs = bot_client.search_v2.call_args[1]
    assert search_call_kwargs.get("resolve") == True, "Search should use resolve=True for federation"


def test_handles_empty_search_result_gracefully(tmp_path):
    """Test that the bot handles empty search results (even with resolve=True) gracefully."""
    from mastodon.errors import MastodonNotFoundError
    
    cfg = DummyConfig(str(tmp_path / "state.json"))
    inst = types.SimpleNamespace(name="test_instance", limit=1)
    cfg.subscribed_instances = [inst]
    cfg.federate_missing_statuses = True  # Enable federation
    hype = Hype(cfg)
    
    # Trending returns full status object
    trending_status = status_data("99999", "https://remote.instance/status/99999")
    trending = [trending_status]
    
    # Mock the remote instance client
    remote_client = MagicMock()
    remote_client.trending_statuses.return_value = trending
    hype.init_client = MagicMock(return_value=remote_client)
    
    # Mock the bot's own client
    bot_client = MagicMock()
    
    # Reblog fails (not in local DB), then search returns empty (federation failed)
    bot_client.status_reblog.side_effect = MastodonNotFoundError()
    bot_client.search_v2.return_value = {"statuses": []}
    
    hype.client = bot_client
    
    # The boost cycle should complete without crashing
    hype.boost()
    
    # Verify that reblog was attempted once (before federation)
    assert bot_client.status_reblog.call_count == 1
    
    # Verify that search_v2 was called once with resolve=True (federation attempt)
    assert bot_client.search_v2.call_count == 1
    search_call_kwargs = bot_client.search_v2.call_args[1]
    assert search_call_kwargs.get("resolve") == True


def test_skips_unfederated_posts_when_federation_disabled(tmp_path):
    """Test that unfederated posts are skipped when federate_missing_statuses=False."""
    from mastodon.errors import MastodonNotFoundError
    
    cfg = DummyConfig(str(tmp_path / "state.json"))
    inst = types.SimpleNamespace(name="test_instance", limit=1)
    cfg.subscribed_instances = [inst]
    cfg.federate_missing_statuses = False  # Federation disabled (default)
    hype = Hype(cfg)
    
    # Trending returns full status object
    trending_status = status_data("12345", "https://remote.instance/status/12345")
    trending = [trending_status]
    
    # Mock the remote instance client
    remote_client = MagicMock()
    remote_client.trending_statuses.return_value = trending
    hype.init_client = MagicMock(return_value=remote_client)
    
    # Mock the bot's own client
    bot_client = MagicMock()
    
    # Reblog fails (not in local DB)
    bot_client.status_reblog.side_effect = MastodonNotFoundError()
    
    hype.client = bot_client
    
    # The boost cycle should complete without attempting federation
    hype.boost()
    
    # Verify that reblog was attempted once
    assert bot_client.status_reblog.call_count == 1
    
    # Verify that search_v2 was NOT called (federation disabled)
    assert bot_client.search_v2.call_count == 0


def test_federation_handles_api_errors_gracefully(tmp_path):
    """Test that federation handles API errors gracefully with proper error logging."""
    from mastodon.errors import MastodonAPIError, MastodonNotFoundError
    
    cfg = DummyConfig(str(tmp_path / "state.json"))
    inst = types.SimpleNamespace(name="test_instance", limit=1)
    cfg.subscribed_instances = [inst]
    cfg.federate_missing_statuses = True
    hype = Hype(cfg)
    
    # Trending returns full status object
    trending_status = status_data("12345", "https://remote.instance/status/12345")
    trending = [trending_status]
    
    # Mock the remote instance client
    remote_client = MagicMock()
    remote_client.trending_statuses.return_value = trending
    hype.init_client = MagicMock(return_value=remote_client)
    
    # Mock the bot's own client
    bot_client = MagicMock()
    
    # Reblog fails (not in local DB), then search fails with 401
    bot_client.status_reblog.side_effect = MastodonNotFoundError()
    bot_client.search_v2.side_effect = MastodonAPIError("Unauthorized", 401, "Unauthorized", None)
    
    hype.client = bot_client
    
    # The boost cycle should complete without crashing
    hype.boost()
    
    # Verify that reblog was attempted once
    assert bot_client.status_reblog.call_count == 1
    
    # Verify that search_v2 was called once (federation attempt that failed)
    assert bot_client.search_v2.call_count == 1

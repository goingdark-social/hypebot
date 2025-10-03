import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hype.hype import Hype
from hype.config import Instance
from tests.test_seen_status import DummyConfig, status_data


def test_fetch_limit_requests_from_api(tmp_path):
    """Test that fetch_limit is passed to the Mastodon API."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    inst = Instance(name="test.instance", fetch_limit=15, boost_limit=4)
    cfg.subscribed_instances = [inst]
    
    hype = Hype(cfg)
    
    # Mock the Mastodon client
    mock_client = MagicMock()
    mock_client.trending_statuses.return_value = []
    hype.init_client = MagicMock(return_value=mock_client)
    
    # Call fetch
    hype._fetch_trending_statuses(inst)
    
    # Verify trending_statuses was called with the fetch_limit
    mock_client.trending_statuses.assert_called_once_with(limit=15)


def test_boost_limit_restricts_per_instance(tmp_path):
    """Test that boost_limit restricts how many posts are boosted per instance."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    # Instance configured to fetch 10 but only boost 2
    inst = Instance(name="test.instance", fetch_limit=10, boost_limit=2)
    cfg.subscribed_instances = [inst]
    cfg.max_boosts_per_run = 10  # High enough to not interfere
    
    hype = Hype(cfg)
    
    # Create 5 trending posts
    trending = [
        status_data(f"{i}", f"https://a/{i}")
        for i in range(1, 6)
    ]
    
    m = MagicMock()
    m.trending_statuses.return_value = trending
    hype.init_client = MagicMock(return_value=m)
    hype.client = MagicMock()
    
    hype.boost()
    
    # Should only boost 2 posts (the boost_limit), not all 5
    assert hype.client.status_reblog.call_count == 2


def test_legacy_limit_works_as_before(tmp_path):
    """Test that legacy single limit parameter still works."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    # Using legacy format with single limit
    inst = Instance(name="test.instance", limit=3)
    cfg.subscribed_instances = [inst]
    
    hype = Hype(cfg)
    
    # Create 5 trending posts
    trending = [
        status_data(f"{i}", f"https://a/{i}")
        for i in range(1, 6)
    ]
    
    m = MagicMock()
    m.trending_statuses.return_value = trending
    hype.init_client = MagicMock(return_value=m)
    hype.client = MagicMock()
    
    hype.boost()
    
    # Legacy mode: limit=3 means fetch 3 and boost up to 3
    # Should boost all 3 posts
    assert hype.client.status_reblog.call_count == 3


def test_multiple_instances_respect_individual_limits(tmp_path):
    """Test that each instance's boost_limit is respected independently."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    inst1 = Instance(name="i1", fetch_limit=10, boost_limit=2)
    inst2 = Instance(name="i2", fetch_limit=10, boost_limit=3)
    cfg.subscribed_instances = [inst1, inst2]
    cfg.max_boosts_per_run = 10  # High enough to not interfere
    
    hype = Hype(cfg)
    
    # Create trending posts for each instance
    trending_i1 = [status_data(f"1{i}", f"https://i1/{i}") for i in range(1, 6)]
    trending_i2 = [status_data(f"2{i}", f"https://i2/{i}") for i in range(1, 6)]
    
    m1 = MagicMock()
    m1.trending_statuses.return_value = trending_i1
    m2 = MagicMock()
    m2.trending_statuses.return_value = trending_i2
    
    hype.init_client = MagicMock(side_effect=[m1, m2])
    hype.client = MagicMock()
    
    hype.boost()
    
    # Should boost 2 from i1 + 3 from i2 = 5 total
    assert hype.client.status_reblog.call_count == 5


def test_instance_defaults_fetch_20_boost_4(tmp_path):
    """Test that Instance defaults to fetch_limit=20 and boost_limit=4 when using new format."""
    # New format without explicit limits
    inst = Instance(name="test.instance")
    
    assert inst.fetch_limit == 20
    assert inst.boost_limit == 4


def test_instance_legacy_property_works(tmp_path):
    """Test that Instance.limit property works for backward compatibility."""
    inst = Instance(name="test.instance", limit=5)
    
    # Legacy property should return fetch_limit
    assert inst.limit == 5
    assert inst.fetch_limit == 5
    assert inst.boost_limit == 5


def test_instance_respects_api_maximum(tmp_path):
    """Test that fetch_limit is capped at 20 (Mastodon API maximum)."""
    # Try to set fetch_limit above 20
    inst = Instance(name="test.instance", fetch_limit=50, boost_limit=10)
    
    # Should be capped at 20
    assert inst.fetch_limit == 20
    # boost_limit can be anything
    assert inst.boost_limit == 10


def test_backward_compatibility_with_simplenamespacee(tmp_path):
    """Test that SimpleNamespace instances (used in tests) still work."""
    cfg = DummyConfig(str(tmp_path / "state.json"))
    # This is how tests create instances
    inst = types.SimpleNamespace(name="i1", limit=2)
    cfg.subscribed_instances = [inst]
    
    hype = Hype(cfg)
    
    # Create 3 trending posts
    trending = [
        status_data(f"{i}", f"https://a/{i}")
        for i in range(1, 4)
    ]
    
    m = MagicMock()
    m.trending_statuses.return_value = trending
    hype.init_client = MagicMock(return_value=m)
    hype.client = MagicMock()
    
    hype.boost()
    
    # Should boost 2 (the limit)
    assert hype.client.status_reblog.call_count == 2

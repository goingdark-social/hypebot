import os
import sys
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, mock_open

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hype.config import Config, ConfigException


def test_environment_variable_override_simple():
    """Test that environment variables override defaults using mocking."""
    
    # Mock file system calls
    auth_content = """
bot_account:
  server: "https://test.example"
  access_token: "test_token"
"""
    
    config_content = """
interval: 60
subscribed_instances:
  test.instance:
    limit: 5
"""
    
    # Mock the file operations
    mock_files = {
        "/app/config/auth.yaml": auth_content,
        "/app/config/config.yaml": config_content
    }
    
    def mock_open_func(filename, mode='r'):
        if filename in mock_files:
            from io import StringIO
            return StringIO(mock_files[filename])
        else:
            raise FileNotFoundError(f"No such file: {filename}")
    
    with patch('builtins.open', side_effect=mock_open_func):
        with patch.dict(os.environ, {'HYPE_MIN_REPLIES': '5', 'HYPE_INTERVAL': '120'}):
            config = Config()
            assert config.min_replies == 5
            assert config.interval == 120


def test_config_file_values_without_environment():
    """Test that config file values are used when no environment variables are set."""
    
    auth_content = """
bot_account:
  server: "https://test.example"
  access_token: "test_token"
"""
    
    config_content = """
interval: 90
min_replies: 3
daily_public_cap: 30
"""
    
    mock_files = {
        "/app/config/auth.yaml": auth_content,
        "/app/config/config.yaml": config_content
    }
    
    def mock_open_func(filename, mode='r'):
        if filename in mock_files:
            from io import StringIO
            return StringIO(mock_files[filename])
        else:
            raise FileNotFoundError(f"No such file: {filename}")
    
    with patch('builtins.open', side_effect=mock_open_func):
        # Clear any existing environment variables
        env_vars_to_clear = ['HYPE_MIN_REPLIES', 'HYPE_INTERVAL', 'HYPE_DAILY_PUBLIC_CAP']
        env_patch = {var: None for var in env_vars_to_clear if var in os.environ}
        
        with patch.dict(os.environ, env_patch, clear=False):
            config = Config()
            assert config.interval == 90
            assert config.min_replies == 3
            assert config.daily_public_cap == 30


def test_default_values_when_no_config():
    """Test that defaults are used when neither env vars nor config file values are set."""
    
    auth_content = """
bot_account:
  server: "https://test.example"
  access_token: "test_token"
"""
    
    config_content = """
subscribed_instances:
  test.instance:
    limit: 5
"""
    
    mock_files = {
        "/app/config/auth.yaml": auth_content,
        "/app/config/config.yaml": config_content
    }
    
    def mock_open_func(filename, mode='r'):
        if filename in mock_files:
            from io import StringIO
            return StringIO(mock_files[filename])
        else:
            raise FileNotFoundError(f"No such file: {filename}")
    
    with patch('builtins.open', side_effect=mock_open_func):
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            # Should use default values (updated to production defaults)
            assert config.min_replies == 2
            assert config.interval == 15
            assert config.daily_public_cap == 96
            assert config.per_hour_public_cap == 5
            assert config.log_level == "DEBUG"
            assert config.debug_decisions == True
            assert config.require_media == False
            assert config.min_reblogs == 10
            assert config.min_favourites == 10
            assert config.languages_allowlist == ["en"]
            assert config.filtered_instances == ["example.com"]
            assert "goingdark.social" in config.profile_prefix
            assert config.fields["instance"] == "https://goingdark.social"
            assert config.hashtag_scores["homelab"] == 20
            assert config.hashtag_scores["kubernetes"] == 15


def test_invalid_environment_variable_fallback():
    """Test that invalid environment variable values fall back gracefully."""
    
    auth_content = """
bot_account:
  server: "https://test.example"
  access_token: "test_token"
"""
    
    config_content = """
min_replies: 2
interval: 60
"""
    
    mock_files = {
        "/app/config/auth.yaml": auth_content,
        "/app/config/config.yaml": config_content
    }
    
    def mock_open_func(filename, mode='r'):
        if filename in mock_files:
            from io import StringIO
            return StringIO(mock_files[filename])
        else:
            raise FileNotFoundError(f"No such file: {filename}")
    
    with patch('builtins.open', side_effect=mock_open_func):
        with patch.dict(os.environ, {'HYPE_MIN_REPLIES': 'invalid_number'}):
            config = Config()
            # Should fall back to config file value when env var is invalid
            assert config.min_replies == 2


def test_boolean_environment_variables():
    """Test that boolean environment variables are properly parsed."""
    
    auth_content = """
bot_account:
  server: "https://test.example"
  access_token: "test_token"
"""
    
    config_content = """
require_media: true
debug_decisions: false
"""
    
    mock_files = {
        "/app/config/auth.yaml": auth_content,
        "/app/config/config.yaml": config_content
    }
    
    def mock_open_func(filename, mode='r'):
        if filename in mock_files:
            from io import StringIO
            return StringIO(mock_files[filename])
        else:
            raise FileNotFoundError(f"No such file: {filename}")
    
    with patch('builtins.open', side_effect=mock_open_func):
        with patch.dict(os.environ, {
            'HYPE_REQUIRE_MEDIA': 'false',
            'HYPE_DEBUG_DECISIONS': '0'
        }):
            config = Config()
            assert config.require_media == False
            assert config.debug_decisions == False


def test_default_subscribed_instances():
    """Test that default subscribed instances are used when none are configured."""
    
    auth_content = """
bot_account:
  server: "https://test.example"
  access_token: "test_token"
"""
    
    # Config file with no subscribed_instances
    config_content = """
interval: 15
"""
    
    mock_files = {
        "/app/config/auth.yaml": auth_content,
        "/app/config/config.yaml": config_content
    }
    
    def mock_open_func(filename, mode='r'):
        if filename in mock_files:
            from io import StringIO
            return StringIO(mock_files[filename])
        else:
            raise FileNotFoundError(f"No such file: {filename}")
    
    with patch('builtins.open', side_effect=mock_open_func):
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            # Should use default goingdark.social instances
            assert len(config.subscribed_instances) == 7
            
            # Check for expected instances
            instance_names = [inst.name for inst in config.subscribed_instances]
            assert "infosec.exchange" in instance_names
            assert "mastodon.social" in instance_names
            assert "mas.to" in instance_names
            assert "fosstodon.org" in instance_names
            assert "floss.social" in instance_names
            assert "ioc.exchange" in instance_names
            assert "mstdn.social" in instance_names
            
            # Check that all instances have fetch_limit=20 and varying boost_limits
            for inst in config.subscribed_instances:
                assert inst.fetch_limit == 20
                assert inst.boost_limit > 0
            
            # Check specific boost limits
            infosec = next((i for i in config.subscribed_instances if i.name == "infosec.exchange"), None)
            assert infosec is not None
            assert infosec.boost_limit == 5


def test_config_file_instances_override_defaults():
    """Test that config file instances override the defaults."""
    
    auth_content = """
bot_account:
  server: "https://test.example"
  access_token: "test_token"
"""
    
    config_content = """
subscribed_instances:
  custom.instance:
    fetch_limit: 10
    boost_limit: 3
"""
    
    mock_files = {
        "/app/config/auth.yaml": auth_content,
        "/app/config/config.yaml": config_content
    }
    
    def mock_open_func(filename, mode='r'):
        if filename in mock_files:
            from io import StringIO
            return StringIO(mock_files[filename])
        else:
            raise FileNotFoundError(f"No such file: {filename}")
    
    with patch('builtins.open', side_effect=mock_open_func):
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            # Should use config file instances, not defaults
            assert len(config.subscribed_instances) == 1
            assert config.subscribed_instances[0].name == "custom.instance"
            assert config.subscribed_instances[0].fetch_limit == 10
            assert config.subscribed_instances[0].boost_limit == 3
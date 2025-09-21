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
            # Should use default values
            assert config.min_replies == 0
            assert config.interval == 60
            assert config.daily_public_cap == 48


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
require_media: false
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
            'HYPE_REQUIRE_MEDIA': 'true',
            'HYPE_DEBUG_DECISIONS': '1'
        }):
            config = Config()
            assert config.require_media == True
            assert config.debug_decisions == True
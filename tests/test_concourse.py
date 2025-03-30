import os
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
import yaml

from voyager.concourse import ConcourseClient, get_token_from_flyrc


def test_get_token_from_flyrc():
    """Test extraction of token from flyrc file."""
    # Create sample flyrc content
    flyrc_content = {
        'targets': {
            'example': {
                'api': 'https://concourse.example.com',
                'team': 'main',
                'token': {
                    'type': 'bearer',
                    'value': 'sample-token-main'
                }
            },
            'another': {
                'api': 'https://concourse.example.com',
                'team': 'development',
                'token': {
                    'type': 'bearer',
                    'value': 'sample-token-dev'
                }
            },
            'no-token': {
                'api': 'https://concourse.example.com',
                'team': 'test'
                # No token section
            }
        }
    }

    flyrc_yaml = yaml.dump(flyrc_content)

    # Mock the home directory and file open
    with patch('voyager.concourse.Path.home') as mock_home, \
         patch('voyager.concourse.Path.exists', return_value=True), \
         patch('builtins.open', mock_open(read_data=flyrc_yaml)):

        mock_home.return_value = Path('/mock/home')

        # Test with existing team
        token = get_token_from_flyrc('main')
        assert token == 'sample-token-main'

        # Test with another team
        token = get_token_from_flyrc('development')
        assert token == 'sample-token-dev'

        # Test with team that exists but has no token
        token = get_token_from_flyrc('test')
        assert token is None

        # Test with non-existent team
        token = get_token_from_flyrc('non-existent')
        assert token is None


def test_get_token_from_flyrc_file_not_exists():
    """Test when flyrc file doesn't exist."""
    with patch('voyager.concourse.Path.exists', return_value=False):
        token = get_token_from_flyrc('main')
        assert token is None


def test_get_token_from_flyrc_yaml_error():
    """Test handling of YAML parsing errors."""
    with patch('voyager.concourse.Path.home') as mock_home, \
         patch('voyager.concourse.Path.exists', return_value=True), \
         patch('builtins.open', mock_open(read_data='invalid: yaml: content:')), \
         patch('yaml.safe_load', side_effect=yaml.YAMLError("YAML error")), \
         patch('click.echo') as mock_echo:

        mock_home.return_value = Path('/mock/home')

        token = get_token_from_flyrc('main')
        assert token is None
        mock_echo.assert_called_once()
        assert "Error reading flyrc file" in mock_echo.call_args[0][0]


def test_concourse_client_with_flyrc_token():
    """Test ConcourseClient initialization using flyrc token."""
    # Create a test environment without CONCOURSE_TOKEN
    with patch.dict(os.environ, {}, clear=True), \
         patch('voyager.concourse.get_token_from_flyrc', return_value='flyrc-token'):

        client = ConcourseClient('https://concourse.example.com', 'main')

        # Verify the client is using the token from flyrc
        assert client.token == 'flyrc-token'
        assert client.headers['Authorization'] == 'Bearer flyrc-token'


def test_concourse_client_token_priority():
    """Test ConcourseClient token priority (explicit > env > flyrc)."""
    # Test with all token sources available
    with patch.dict(os.environ, {'CONCOURSE_TOKEN': 'env-token'}, clear=True), \
         patch('voyager.concourse.get_token_from_flyrc', return_value='flyrc-token'):

        # 1. Explicit token should take priority
        client = ConcourseClient('https://concourse.example.com', 'main', token='explicit-token')
        assert client.token == 'explicit-token'

        # 2. Env var should take priority over flyrc
        client = ConcourseClient('https://concourse.example.com', 'main')
        assert client.token == 'env-token'

        # 3. With env var removed, should fall back to flyrc
        with patch.dict(os.environ, {}, clear=True):
            client = ConcourseClient('https://concourse.example.com', 'main')
            assert client.token == 'flyrc-token'


def test_concourse_client_no_token():
    """Test ConcourseClient with no token available."""
    with patch.dict(os.environ, {}, clear=True), \
         patch('voyager.concourse.get_token_from_flyrc', return_value=None):

        # Should raise ValueError when no token is available
        with pytest.raises(ValueError) as excinfo:
            ConcourseClient('https://concourse.example.com', 'main')

        # Check error message
        assert "Concourse token not found" in str(excinfo.value)
        assert "team \"main\"" in str(excinfo.value)

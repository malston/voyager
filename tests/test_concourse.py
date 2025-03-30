import os
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
import yaml

from voyager.concourse import (
    ConcourseClient,
    get_api_url_from_flyrc,
    get_concourse_data_from_flyrc,
    get_flyrc_data,
    get_team_from_flyrc,
    get_token_from_flyrc,
)


def create_sample_flyrc_content():
    """Create sample flyrc content for testing."""
    return {
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
                'api': 'https://concourse.another.com',
                'team': 'development',
                'token': {
                    'type': 'bearer',
                    'value': 'sample-token-dev'
                }
            },
            'no-token': {
                'api': 'https://concourse.test.com',
                'team': 'test'
                # No token section
            }
        }
    }


def test_get_flyrc_data():
    """Test reading and filtering flyrc data."""
    flyrc_content = create_sample_flyrc_content()
    flyrc_yaml = yaml.dump(flyrc_content)

    # Mock the home directory and file open
    with patch('voyager.concourse.Path.home') as mock_home, \
         patch('voyager.concourse.Path.exists', return_value=True), \
         patch('builtins.open', mock_open(read_data=flyrc_yaml)):

        mock_home.return_value = Path('/mock/home')

        # Test getting all data
        data = get_flyrc_data()
        assert data == flyrc_content

        # Test filtering by target
        data = get_flyrc_data('example')
        assert 'targets' in data
        assert 'example' in data['targets']
        assert len(data['targets']) == 1

        # Test with non-existent target
        data = get_flyrc_data('non-existent')
        assert data is None


def test_get_concourse_data_from_flyrc():
    """Test extraction of Concourse data from flyrc file."""
    flyrc_content = create_sample_flyrc_content()
    flyrc_yaml = yaml.dump(flyrc_content)

    # Mock the home directory and file open
    with patch('voyager.concourse.Path.home') as mock_home, \
         patch('voyager.concourse.Path.exists', return_value=True), \
         patch('builtins.open', mock_open(read_data=flyrc_yaml)):

        mock_home.return_value = Path('/mock/home')

        # Test with existing target
        data = get_concourse_data_from_flyrc('example')
        assert data['team'] == 'main'
        assert data['api_url'] == 'https://concourse.example.com'
        assert data['token'] == 'sample-token-main'

        # Test with another target
        data = get_concourse_data_from_flyrc('another')
        assert data['team'] == 'development'
        assert data['api_url'] == 'https://concourse.another.com'
        assert data['token'] == 'sample-token-dev'

        # Test with target that exists but has no token
        data = get_concourse_data_from_flyrc('no-token')
        assert data['team'] == 'test'
        assert data['api_url'] == 'https://concourse.test.com'
        assert data['token'] is None

        # Test with non-existent target
        data = get_concourse_data_from_flyrc('non-existent')
        assert data is None


def test_get_token_from_flyrc():
    """Test extraction of token from flyrc file."""
    flyrc_content = create_sample_flyrc_content()
    flyrc_yaml = yaml.dump(flyrc_content)

    # Mock the home directory and file open
    with patch('voyager.concourse.Path.home') as mock_home, \
         patch('voyager.concourse.Path.exists', return_value=True), \
         patch('builtins.open', mock_open(read_data=flyrc_yaml)):

        mock_home.return_value = Path('/mock/home')

        # Test with existing target
        token = get_token_from_flyrc('example')
        assert token == 'sample-token-main'

        # Test with another target
        token = get_token_from_flyrc('another')
        assert token == 'sample-token-dev'

        # Test with target that exists but has no token
        token = get_token_from_flyrc('no-token')
        assert token is None

        # Test with non-existent target
        token = get_token_from_flyrc('non-existent')
        assert token is None


def test_get_api_url_from_flyrc():
    """Test extraction of API URL from flyrc file."""
    flyrc_content = create_sample_flyrc_content()
    flyrc_yaml = yaml.dump(flyrc_content)

    # Mock the home directory and file open
    with patch('voyager.concourse.Path.home') as mock_home, \
         patch('voyager.concourse.Path.exists', return_value=True), \
         patch('builtins.open', mock_open(read_data=flyrc_yaml)):

        mock_home.return_value = Path('/mock/home')

        # Test with existing target
        url = get_api_url_from_flyrc('example')
        assert url == 'https://concourse.example.com'

        # Test with another target
        url = get_api_url_from_flyrc('another')
        assert url == 'https://concourse.another.com'

        # Test with target that has no token but has URL
        url = get_api_url_from_flyrc('no-token')
        assert url == 'https://concourse.test.com'

        # Test with non-existent target
        url = get_api_url_from_flyrc('non-existent')
        assert url is None


def test_get_team_from_flyrc():
    """Test extraction of team name from flyrc file."""
    flyrc_content = create_sample_flyrc_content()
    flyrc_yaml = yaml.dump(flyrc_content)

    # Mock the home directory and file open
    with patch('voyager.concourse.Path.home') as mock_home, \
         patch('voyager.concourse.Path.exists', return_value=True), \
         patch('builtins.open', mock_open(read_data=flyrc_yaml)):

        mock_home.return_value = Path('/mock/home')

        # Test with existing target
        team = get_team_from_flyrc('example')
        assert team == 'main'

        # Test with another target
        team = get_team_from_flyrc('another')
        assert team == 'development'

        # Test with target that has a team but no token
        team = get_team_from_flyrc('no-token')
        assert team == 'test'

        # Test with non-existent target
        team = get_team_from_flyrc('non-existent')
        assert team is None


def test_get_token_from_flyrc_file_not_exists():
    """Test when flyrc file doesn't exist."""
    with patch('voyager.concourse.Path.exists', return_value=False):
        token = get_token_from_flyrc('example')
        assert token is None


def test_get_token_from_flyrc_yaml_error():
    """Test handling of YAML parsing errors."""
    with patch('voyager.concourse.Path.home') as mock_home, \
         patch('voyager.concourse.Path.exists', return_value=True), \
         patch('builtins.open', mock_open(read_data='invalid: yaml: content:')), \
         patch('yaml.safe_load', side_effect=yaml.YAMLError("YAML error")), \
         patch('click.echo') as mock_echo:

        mock_home.return_value = Path('/mock/home')

        token = get_token_from_flyrc('example')
        assert token is None
        mock_echo.assert_called_once()
        assert "Error reading flyrc file" in mock_echo.call_args[0][0]


def test_concourse_client_with_target():
    """Test ConcourseClient initialization using flyrc target."""
    # Create a test environment without CONCOURSE_TOKEN
    with patch.dict(os.environ, {}, clear=True), \
         patch('voyager.concourse.get_api_url_from_flyrc',
               return_value='https://concourse.flyrc.com'), \
         patch('voyager.concourse.get_team_from_flyrc', return_value='main-team'), \
         patch('voyager.concourse.get_token_from_flyrc', return_value='flyrc-token'):

        client = ConcourseClient(target='example')

        # Verify the client is using the values from flyrc
        assert client.api_url == 'https://concourse.flyrc.com'
        assert client.team == 'main-team'
        assert client.token == 'flyrc-token'
        assert client.headers['Authorization'] == 'Bearer flyrc-token'


def test_concourse_client_explicit_params():
    """Test ConcourseClient initialization using explicit parameters."""
    with patch.dict(os.environ, {}, clear=True):
        # Initialize with all parameters explicitly provided
        client = ConcourseClient(api_url='https://concourse.explicit.com',
                                team='explicit-team',
                                token='explicit-token')

        # Verify the client is using the explicit values
        assert client.api_url == 'https://concourse.explicit.com'
        assert client.team == 'explicit-team'
        assert client.token == 'explicit-token'


def test_concourse_client_parameter_priority():
    """Test ConcourseClient parameter priority (explicit > target)."""
    with patch.dict(os.environ, {}, clear=True), \
         patch('voyager.concourse.get_api_url_from_flyrc',
               return_value='https://concourse.flyrc.com'), \
         patch('voyager.concourse.get_team_from_flyrc', return_value='flyrc-team'), \
         patch('voyager.concourse.get_token_from_flyrc', return_value='flyrc-token'):

        # Explicit parameters should take priority over target values
        client = ConcourseClient(
            api_url='https://concourse.explicit.com',
            team='explicit-team',
            token='explicit-token',
            target='example'
        )

        assert client.api_url == 'https://concourse.explicit.com'
        assert client.team == 'explicit-team'
        assert client.token == 'explicit-token'


def test_concourse_client_no_url():
    """Test ConcourseClient with no URL available."""
    with patch.dict(os.environ, {}, clear=True), \
         patch('voyager.concourse.get_api_url_from_flyrc', return_value=None), \
         patch('voyager.concourse.get_team_from_flyrc', return_value='team'), \
         patch('voyager.concourse.get_token_from_flyrc', return_value='token'):

        # Should raise ValueError when no URL is available
        with pytest.raises(ValueError) as excinfo:
            ConcourseClient(target='example')

        # Check error message
        assert "Concourse API URL not found" in str(excinfo.value)
        assert "flyrc" in str(excinfo.value)


def test_concourse_client_env_token_priority():
    """Test ConcourseClient token priority with environment variable."""
    # Test with environment variable token available
    with patch.dict(os.environ, {'CONCOURSE_TOKEN': 'env-token'}, clear=True), \
         patch('voyager.concourse.get_token_from_flyrc', return_value='flyrc-token'):

        # Explicit token should take priority over env var and flyrc
        client = ConcourseClient(
            api_url='https://concourse.example.com',
            team='main',
            token='explicit-token'
        )
        assert client.token == 'explicit-token'

        # Env var should take priority over flyrc
        client = ConcourseClient(
            api_url='https://concourse.example.com',
            team='main'
        )
        assert client.token == 'env-token'


def test_concourse_client_no_token():
    """Test ConcourseClient with no token available."""
    with patch.dict(os.environ, {}, clear=True), \
         patch('voyager.concourse.get_token_from_flyrc', return_value=None), \
         patch('voyager.concourse.get_api_url_from_flyrc',
               return_value='https://concourse.example.com'), \
         patch('voyager.concourse.get_team_from_flyrc', return_value='main'):

        # Should raise ValueError when no token is available
        with pytest.raises(ValueError) as excinfo:
            ConcourseClient(target='example')

        # Check error message
        assert "Concourse token not found" in str(excinfo.value)
        assert "environment variable" in str(excinfo.value)


def test_concourse_client_no_team():
    """Test ConcourseClient with no team available."""
    with patch.dict(os.environ, {}, clear=True), \
         patch('voyager.concourse.get_token_from_flyrc', return_value='token'), \
         patch('voyager.concourse.get_api_url_from_flyrc',
               return_value='https://concourse.example.com'), \
         patch('voyager.concourse.get_team_from_flyrc', return_value=None):

        # Should raise ValueError when no team is available
        with pytest.raises(ValueError) as excinfo:
            ConcourseClient(target='example')

        # Check error message
        assert "Concourse team not found" in str(excinfo.value)
        assert "flyrc" in str(excinfo.value)

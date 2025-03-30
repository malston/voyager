from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from voyager.commands.pipelines import list_pipelines


@pytest.fixture
def mock_concourse_setup():
    """Mock Concourse client with builds."""
    with patch('voyager.commands.pipelines.check_git_repo', return_value=True), \
         patch('voyager.commands.pipelines.get_repo_info', return_value=('test-owner', 'test-repo')), \
         patch('voyager.commands.pipelines.ConcourseClient') as mock_concourse:
        
        # Setup Concourse client
        concourse_instance = mock_concourse.return_value
        
        # Create mock builds
        mock_builds = [
            {
                'name': '42',
                'job_name': 'build-and-release',
                'status': 'succeeded',
                'start_time': '2023-03-01T10:00:00Z',
                'end_time': '2023-03-01T10:05:00Z',
            },
            {
                'name': '41',
                'job_name': 'build-and-release',
                'status': 'failed',
                'start_time': '2023-02-28T15:00:00Z',
                'end_time': '2023-02-28T15:03:00Z',
            }
        ]
        concourse_instance.get_pipeline_builds.return_value = mock_builds
        
        yield {
            'concourse': concourse_instance,
            'builds': mock_builds
        }


def test_list_pipelines_command(mock_concourse_setup):
    """Test listing pipeline builds."""
    runner = CliRunner()
    
    with runner.isolated_filesystem():
        # Concourse options are required
        result = runner.invoke(list_pipelines, [
            '--concourse-url', 'https://concourse.example.com',
            '--concourse-team', 'main',
            '--pipeline', 'release-pipeline'
        ])
        
        # Check the command executed successfully
        assert result.exit_code == 0
        
        # Verify Concourse client was created and called correctly
        mock_concourse_setup['concourse'].get_pipeline_builds.assert_called_once_with(
            'release-pipeline', limit=5
        )
        
        # Check for table headers and content in the output
        assert 'Build #' in result.output
        assert 'Job' in result.output
        assert 'Status' in result.output
        assert 'Started' in result.output
        assert 'Duration' in result.output
        
        # Check that the build numbers and job names are displayed
        assert '42' in result.output
        assert '41' in result.output
        assert 'build-and-release' in result.output
        
        # Check that the status is displayed (normally with color)
        assert 'succeeded' in result.output.lower()
        assert 'failed' in result.output.lower()
        
        # Check that the total count is displayed
        assert 'Total builds: 2' in result.output
        
        # Check that the pipeline URL is displayed
        assert 'Pipeline URL:' in result.output
        assert 'https://concourse.example.com/teams/main/pipelines/release-pipeline' in result.output


def test_list_pipelines_json_format(mock_concourse_setup):
    """Test listing pipeline builds in JSON format."""
    runner = CliRunner()
    
    with runner.isolated_filesystem():
        result = runner.invoke(list_pipelines, [
            '--concourse-url', 'https://concourse.example.com',
            '--concourse-team', 'main',
            '--pipeline', 'release-pipeline',
            '--format', 'json'
        ])
        
        # Check the command executed successfully
        assert result.exit_code == 0
        
        # Verify JSON format - we'll check for some key elements
        assert '"name": "42"' in result.output
        assert '"name": "41"' in result.output
        assert '"job_name": "build-and-release"' in result.output
        assert '"status": "succeeded"' in result.output
        assert '"status": "failed"' in result.output
        
        # JSON format should not include the table headers
        assert 'Build #' not in result.output
        assert 'Job' not in result.output
        
        # No total count in JSON output
        assert 'Total builds:' not in result.output


def test_list_pipelines_with_limit(mock_concourse_setup):
    """Test listing pipelines with a custom limit."""
    runner = CliRunner()
    
    with runner.isolated_filesystem():
        result = runner.invoke(list_pipelines, [
            '--concourse-url', 'https://concourse.example.com',
            '--concourse-team', 'main',
            '--pipeline', 'release-pipeline',
            '--limit', '10'
        ])
        
        # Check the command executed successfully
        assert result.exit_code == 0
        
        # Verify Concourse client was called with the custom limit
        mock_concourse_setup['concourse'].get_pipeline_builds.assert_called_once_with(
            'release-pipeline', limit=10
        )


def test_list_pipelines_no_builds(mock_concourse_setup):
    """Test listing pipelines when no builds are found."""
    runner = CliRunner()
    
    # Set up mock to return empty list
    mock_concourse_setup['concourse'].get_pipeline_builds.return_value = []
    
    with runner.isolated_filesystem():
        result = runner.invoke(list_pipelines, [
            '--concourse-url', 'https://concourse.example.com',
            '--concourse-team', 'main',
            '--pipeline', 'release-pipeline'
        ])
        
        # Check the command executed successfully
        assert result.exit_code == 0
        
        # Should display a message about no builds
        assert 'No builds found for this pipeline.' in result.output


def test_list_pipelines_non_git_repo():
    """Test listing pipelines in a non-git repository."""
    runner = CliRunner()
    
    # Mock check_git_repo to return False
    with patch('voyager.commands.pipelines.check_git_repo', return_value=False):
        with runner.isolated_filesystem():
            result = runner.invoke(list_pipelines, [
                '--concourse-url', 'https://concourse.example.com',
                '--concourse-team', 'main',
                '--pipeline', 'release-pipeline'
            ])
            
            # Check for error message
            assert result.exit_code == 1
            assert 'Error: Current directory is not a git repository' in result.output
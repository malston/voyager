import os
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from voyager.commands.init import init_repo


@pytest.fixture
def mock_env_setup():
    """Set up mocks for init command."""
    with patch('voyager.commands.init.check_git_repo', return_value=True), patch(
        'voyager.commands.init.get_repo_info', return_value=('test-owner', 'test-repo')
    ):
        yield


def test_init_basic(mock_env_setup):
    """Test basic initialization without Concourse options."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        # Run the init command
        result = runner.invoke(init_repo, [])

        # Check the command executed successfully
        assert result.exit_code == 0

        # Check for creation messages
        assert 'Initializing Voyager for test-owner/test-repo' in result.output

        # Verify expected files were created
        assert Path('.github/workflows/voyager.yml').exists()
        assert Path('voyager.yml').exists()
        assert Path('.env.example').exists()

        # Check .env.example content
        with open('.env.example', 'r') as f:
            env_content = f.read()
            assert 'GITHUB_TOKEN' in env_content
            # Should not include Concourse token without Concourse options
            assert 'CONCOURSE_TOKEN' not in env_content

        # Check voyager.yml content
        with open('voyager.yml', 'r') as f:
            config_content = f.read()
            assert 'repository:' in config_content
            assert 'owner: test-owner' in config_content
            assert 'name: test-repo' in config_content
            # Should not include Concourse config without Concourse options
            assert 'concourse:' not in config_content


def test_init_with_concourse(mock_env_setup):
    """Test initialization with Concourse options."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        # Run the init command with Concourse options
        result = runner.invoke(
            init_repo,
            [
                '--concourse-url',
                'https://concourse.example.com',
                '--concourse-team',
                'main',
                '--pipeline',
                'release-pipeline',
            ],
        )

        # Check the command executed successfully
        assert result.exit_code == 0

        # Verify expected files were created
        assert Path('.github/workflows/voyager.yml').exists()
        assert Path('voyager.yml').exists()
        assert Path('.env.example').exists()
        assert Path('ci/pipeline.yml').exists()
        assert Path('ci/set-pipeline.sh').exists()

        # Check executable permission on set-pipeline.sh
        assert os.access('ci/set-pipeline.sh', os.X_OK)

        # Check .env.example content
        with open('.env.example', 'r') as f:
            env_content = f.read()
            assert 'GITHUB_TOKEN' in env_content
            # Should include Concourse token with Concourse options
            assert 'CONCOURSE_TOKEN' in env_content

        # Check voyager.yml content
        with open('voyager.yml', 'r') as f:
            config_content = f.read()
            assert 'repository:' in config_content
            assert 'owner: test-owner' in config_content
            assert 'name: test-repo' in config_content
            # Should include Concourse config with Concourse options
            assert 'concourse:' in config_content
            assert 'url: https://concourse.example.com' in config_content
            assert 'team: main' in config_content
            assert 'pipeline: release-pipeline' in config_content


def test_init_existing_files(mock_env_setup):
    """Test initialization when files already exist."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        # Create some existing files
        os.makedirs('.github/workflows', exist_ok=True)
        with open('.github/workflows/voyager.yml', 'w') as f:
            f.write('# Existing workflow file')

        os.makedirs('ci', exist_ok=True)
        with open('ci/pipeline.yml', 'w') as f:
            f.write('# Existing pipeline file')

        # Run the init command with prompts to not overwrite
        result = runner.invoke(
            init_repo,
            ['--concourse-url', 'https://concourse.example.com', '--concourse-team', 'main'],
            input='n\nn\nn\nn\n',
        )  # Answer no to all overwrites

        # Check the command executed successfully
        assert result.exit_code == 0

        # Check that files were not overwritten
        with open('.github/workflows/voyager.yml', 'r') as f:
            content = f.read()
            assert content == '# Existing workflow file'

        with open('ci/pipeline.yml', 'r') as f:
            content = f.read()
            assert content == '# Existing pipeline file'


def test_init_gitignore_update(mock_env_setup):
    """Test .gitignore is updated with .env entry."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        # Create an existing .gitignore without .env
        with open('.gitignore', 'w') as f:
            f.write('# Ignore node modules\nnode_modules/\n')

        # Run the init command
        result = runner.invoke(init_repo, [])

        # Check the command executed successfully
        assert result.exit_code == 0

        # Verify .gitignore was updated
        with open('.gitignore', 'r') as f:
            content = f.read()
            assert '.env' in content
            # Original content should still be there
            assert 'node_modules/' in content


def test_init_non_git_repo():
    """Test initialization in a non-git repository."""
    runner = CliRunner()

    # Mock check_git_repo to return False
    with patch('voyager.commands.init.check_git_repo', return_value=False):
        with runner.isolated_filesystem():
            # Run the init command
            result = runner.invoke(init_repo, [])

            # Check for error message
            assert result.exit_code == 1
            assert 'Error: Current directory is not a git repository' in result.output

            # Verify no files were created
            assert not Path('.github').exists()
            assert not Path('voyager.yml').exists()
            assert not Path('.env.example').exists()

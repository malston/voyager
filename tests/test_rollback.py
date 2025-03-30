from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from voyager.commands.rollback import rollback


@pytest.fixture
def mock_env_setup():
    """Mock environment setup including Git operations."""
    with patch('git.Repo') as mock_git_repo, patch(
        'voyager.commands.rollback.check_git_repo', return_value=True
    ), patch(
        'voyager.commands.rollback.get_repo_info', return_value=('test-owner', 'test-repo')
    ), patch('voyager.commands.rollback.GitHubClient') as mock_github_client, patch(
        'voyager.commands.rollback.find_version_file'
    ) as mock_find_version, patch(
        'voyager.commands.rollback.extract_version'
    ) as mock_extract_version, patch(
        'voyager.commands.rollback.VersionUpdater'
    ) as mock_version_updater, patch(
        'voyager.commands.rollback.update_version_in_init'
    ) as mock_update_init:
        # Set up mock repo
        mock_repo_instance = mock_git_repo.return_value
        mock_branch = MagicMock()
        mock_branch.name = 'main'
        mock_repo_instance.active_branch = mock_branch
        mock_repo_instance.working_dir = '/fake/path'

        # Mock tags - create a proper mock for the tags collection
        mock_tags = MagicMock()
        mock_tag = MagicMock()
        mock_tag.commit = MagicMock()

        # Configure mock_tags to return mock_tag for any tag key
        mock_tags.__getitem__.return_value = mock_tag
        mock_tags.__contains__.return_value = True

        # Set tags on the repo instance
        mock_repo_instance.tags = mock_tags

        # Mock refs and similar properties for branch existence check
        mock_ref1 = MagicMock()
        mock_ref1.name = 'main'
        mock_ref2 = MagicMock()
        mock_ref2.name = 'develop'
        mock_repo_instance.refs = [mock_ref1, mock_ref2]

        # Mock git operations
        mock_repo_instance.git = MagicMock()
        mock_repo_instance.git.checkout = MagicMock()
        mock_repo_instance.git.branch = MagicMock()
        mock_repo_instance.git.add = MagicMock()
        mock_repo_instance.git.commit = MagicMock()
        mock_repo_instance.git.push = MagicMock()
        mock_repo_instance.create_tag = MagicMock()

        # Make Repo() always return our mocked repo when called with any arguments
        mock_git_repo.side_effect = lambda *args, **kwargs: mock_repo_instance

        # Mock GitHubClient with is_authenticated property
        github_instance = mock_github_client.return_value
        github_instance.is_authenticated = True
        github_instance.get_releases.return_value = [
            {'tag_name': 'v1.0.0', 'name': 'Version 1.0.0', 'published_at': '2023-01-01T12:00:00Z'},
            {'tag_name': 'v0.9.0', 'name': 'Version 0.9.0', 'published_at': '2022-12-01T12:00:00Z'},
        ]
        github_instance.create_release.return_value = {
            'html_url': 'https://github.com/test/test/releases/rollback-v1.0.0'
        }

        # Mock version file finding and extraction
        mock_find_version.return_value = (
            '/fake/path/pyproject.toml',
            r'version\s*=\s*[\'"](?P<version>[^\'"]*)[\'"]',
        )
        mock_extract_version.return_value = '0.9.0'

        # Mock VersionUpdater
        updater_instance = mock_version_updater.return_value
        updater_instance.update_version.return_value = False

        # Mock update_version_in_init so it doesn't try to access real files
        mock_update_init.return_value = None

        yield {
            'git_repo': mock_git_repo,
            'repo_instance': mock_repo_instance,
            'github_client': mock_github_client,
            'find_version': mock_find_version,
            'extract_version': mock_extract_version,
            'version_updater': mock_version_updater,
            'update_init': mock_update_init,
        }


def test_rollback_with_version_file(mock_env_setup):
    """Test rollback handles version files correctly."""
    runner = CliRunner()

    # Setup standard mocks so it finds a version file
    mock_env_setup['find_version'].return_value = (
        '/fake/path/pyproject.toml',
        r'version="([^"]*)"',
    )
    mock_env_setup['extract_version'].return_value = '1.0.0'

    with runner.isolated_filesystem():
        # Mock click.confirm to return True for any confirmations
        with patch('click.confirm', return_value=True):
            # Run rollback with a specified version file and version branch
            result = runner.invoke(
                rollback,
                [
                    '--tag',
                    'v0.9.0',
                    '--version-file',
                    'pyproject.toml',
                    '--version-branch',
                    'version',
                ],
                catch_exceptions=True,
            )

        # Verify VersionUpdater was created with the right parameters
        mock_env_setup['version_updater'].assert_called_once()
        args, kwargs = mock_env_setup['version_updater'].call_args
        assert kwargs['file_path'] == '/fake/path/pyproject.toml'
        assert kwargs['old_version'] == '1.0.0'
        assert kwargs['new_version'] == '0.9.0'
        assert kwargs['branch'] == 'version'

        # Verify update_version was called
        mock_env_setup['version_updater'].return_value.update_version.assert_called_once()

        # Check for version file update messages in output
        assert 'Updating version in' in result.output
        assert 'pyproject.toml' in result.output


def test_rollback_with_version_branch_update(mock_env_setup):
    """Test rollback properly updates version files on separate branches."""
    runner = CliRunner()

    # Make version updater return True to simulate committed changes on separate branch
    updater_instance = mock_env_setup['version_updater'].return_value
    updater_instance.update_version.return_value = True

    with runner.isolated_filesystem():
        # Mock click.confirm to return True for the confirmation prompts
        with patch('click.confirm', return_value=True):
            # Run rollback with version branch
            # Note: We don't need to check the result, just the side effects
            runner.invoke(
                rollback, ['--tag', 'v0.9.0', '--version-branch', 'version'], catch_exceptions=True
            )

            # Verify VersionUpdater was used with the right branch
            args, kwargs = mock_env_setup['version_updater'].call_args
            assert kwargs['branch'] == 'version'

            # Since updater returned True (changes committed),
            # git.add should not be called for version file
            # But it should be called for other things like __init__.py
            mock_env_setup['repo_instance'].git.add.assert_not_called()


def test_rollback_version_file_not_found(mock_env_setup):
    """Test rollback falls back to __init__.py when version file not found."""
    runner = CliRunner()

    # Setup to simulate version file not found
    mock_env_setup['find_version'].return_value = (None, None)

    # Create a patch for the fallback function
    with patch('voyager.commands.rollback.update_version_in_init') as mock_update_init:
        with runner.isolated_filesystem():
            # Run rollback with a non-existent version file
            # The 'y' is for confirming the rollback prompt
            result = runner.invoke(
                rollback,
                ['--tag', 'v0.9.0', '--version-file', 'nonexistent.toml'],
                input='y\n',
                catch_exceptions=True,
            )
            assert 'Warning: Specified version file' in result.output

            # Verify it fell back to the init file
            mock_update_init.assert_called_once()

            # Should try to add __init__.py since no version file was found
            mock_env_setup['repo_instance'].git.add.assert_called_with('src/voyager/__init__.py')


def test_rollback_without_github_auth(mock_env_setup):
    """Test rollback works without GitHub authentication."""
    runner = CliRunner()

    # Simulate GitHub client without authentication
    github_instance = mock_env_setup['github_client'].return_value
    github_instance.is_authenticated = False

    with runner.isolated_filesystem():
        # Run rollback command with catch_exceptions and confirm the rollback
        result = runner.invoke(rollback, ['--tag', 'v0.9.0'], input='y\n', catch_exceptions=True)

        # Check it warns about GitHub authentication
        assert 'Skipping GitHub release creation (not authenticated)' in result.output

        # Should still have created local tag and branch
        mock_env_setup['repo_instance'].create_tag.assert_called_once()
        mock_env_setup['repo_instance'].git.checkout.assert_called()


def test_rollback_select_tag_from_list(mock_env_setup):
    """Test selecting a tag from an interactive list."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        # Provide '1' as input to select the first tag in the list and mock confirmations
        with patch('click.confirm', return_value=True):
            result = runner.invoke(rollback, input='1\n', catch_exceptions=True)

        # It should have shown a list of releases
        assert 'Available releases for rollback:' in result.output

        # Verify the selected tag was used
        assert mock_env_setup['repo_instance'].git.checkout.called


def test_rollback_dry_run(mock_env_setup):
    """Test dry run mode skips actual changes."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        # Run in dry run mode
        result = runner.invoke(rollback, ['--tag', 'v0.9.0', '--dry-run'], catch_exceptions=True)

        # Check for dry run message
        assert 'DRY RUN MODE - No changes will be made' in result.output

        # No Git operations should be performed
        mock_env_setup['repo_instance'].git.checkout.assert_not_called()
        mock_env_setup['repo_instance'].git.commit.assert_not_called()
        mock_env_setup['repo_instance'].git.push.assert_not_called()
        mock_env_setup['repo_instance'].create_tag.assert_not_called()

        # VersionUpdater should not be created either
        mock_env_setup['version_updater'].assert_not_called()

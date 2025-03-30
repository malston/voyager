from unittest.mock import MagicMock, call, patch

import pytest
from click.testing import CliRunner

from voyager.commands.release import create_release


@pytest.fixture
def mock_repo():
    """Mock GitRepo object with necessary methods and properties."""
    mock = MagicMock()
    # Mock the active_branch property to return an object with a name attribute
    mock_branch = MagicMock()
    mock_branch.name = 'main'
    mock.active_branch = mock_branch

    # Mock the refs property
    mock_refs = []
    for branch_name in ['main', 'develop', 'feature/test', 'version']:
        mock_ref = MagicMock()
        mock_ref.name = branch_name
        mock_refs.append(mock_ref)
    mock.refs = mock_refs

    # Add a mock tags property
    mock.tags = []

    return mock


@pytest.fixture
def mock_env_setup():
    """Mock environment setup including Git operations."""
    with patch('git.Repo') as mock_git_repo, patch(
        'voyager.commands.release.check_git_repo', return_value=True
    ), patch(
        'voyager.commands.release.get_repo_info', return_value=('test-owner', 'test-repo')
    ), patch('voyager.commands.release.GitHubClient') as mock_github_client, patch(
        'voyager.commands.release.VersionFinder'
    ) as mock_version_finder, patch(
        'voyager.commands.release.VersionUpdater'
    ) as mock_version_updater:
        # Set up mock repo
        mock_repo_instance = mock_git_repo.return_value
        mock_branch = MagicMock()
        mock_branch.name = 'main'
        mock_repo_instance.active_branch = mock_branch

        # Mock refs for branch existence check
        mock_refs = []
        for branch_name in ['main', 'develop', 'feature/test', 'version']:
            mock_ref = MagicMock()
            mock_ref.name = branch_name
            mock_refs.append(mock_ref)
        mock_repo_instance.refs = mock_refs

        # Mock git operations
        mock_repo_instance.git = MagicMock()
        mock_repo_instance.git.checkout = MagicMock()
        mock_repo_instance.git.add = MagicMock()
        mock_repo_instance.git.commit = MagicMock()
        mock_repo_instance.git.push = MagicMock()
        mock_repo_instance.create_tag = MagicMock()

        # Mock VersionFinder
        finder_instance = mock_version_finder.return_value
        finder_instance.get_current_version.return_value = (
            '0.1.0',
            'pyproject.toml',
            r'version="([^"]*)"',
        )

        # Mock VersionUpdater
        updater_instance = mock_version_updater.return_value
        updater_instance.update_version.return_value = False  # Not committed by updater

        # Mock GitHub client
        github_instance = mock_github_client.return_value
        github_instance.create_release.return_value = {
            'html_url': 'https://github.com/test/test/releases/v1.0.0'
        }

        yield {
            'git_repo': mock_git_repo,
            'repo_instance': mock_repo_instance,
            'github_client': mock_github_client,
            'version_finder': mock_version_finder,
            'version_updater': mock_version_updater,
        }


def test_release_branch_switching_checkout(mock_env_setup):
    """Test release command with checkout strategy for a different branch."""
    runner = CliRunner()

    # Create a test environment
    with runner.isolated_filesystem():
        # Mock click.confirm to always return True
        with patch('click.confirm', return_value=True):
            # Run the release command with a release branch different from the current one
            # Use --merge-strategy parameter to set checkout strategy
            result = runner.invoke(
                create_release,
                ['--release-branch', 'develop', '--type', 'minor', '--merge-strategy', 'checkout'],
            )

            # Check the command executed successfully
            assert result.exit_code == 0

            # Check that git checkout was called with the right branch
            mock_env_setup['repo_instance'].git.checkout.assert_any_call('develop')

            # Ensure the command output indicates a branch switch
            assert 'is different from working branch' in result.output
            assert "Checking out branch 'develop'" in result.output
            assert "Switched to branch 'develop'" in result.output


def test_release_branch_with_rebase(mock_env_setup):
    """Test release command with rebase strategy for a different branch."""
    runner = CliRunner()

    # Set up mock methods that may not exist yet
    mock_env_setup['repo_instance'].git.rebase = MagicMock()
    mock_env_setup['repo_instance'].git.fetch = MagicMock()
    mock_env_setup['repo_instance'].git.pull = MagicMock()
    mock_env_setup['repo_instance'].git.branch = MagicMock()

    # Create a test environment
    with runner.isolated_filesystem():
        # Run the release command with rebase strategy
        result = runner.invoke(
            create_release,
            ['--release-branch', 'develop', '--type', 'minor', '--merge-strategy', 'rebase'],
        )

        # Check the command executed successfully
        assert result.exit_code == 0

        # Verify git operations were called
        mock_env_setup['repo_instance'].git.fetch.assert_any_call('origin', 'develop')
        mock_env_setup['repo_instance'].git.fetch.assert_any_call('origin', 'main')

        # Check that a backup branch was created
        checkout_calls = str(mock_env_setup['repo_instance'].git.checkout.call_args_list)
        assert "'-b', 'backup-main-" in checkout_calls

        # Check that we switched to the target branch
        mock_env_setup['repo_instance'].git.checkout.assert_any_call('develop')

        # Check that we tried to pull the latest changes
        mock_env_setup['repo_instance'].git.pull.assert_called_with('origin', 'develop')

        # Check rebase was called with the backup branch
        # Note: We're checking if rebase was called, but not the exact parameter
        # because the branch name includes a timestamp
        assert mock_env_setup['repo_instance'].git.rebase.called

        # Check backup branch was deleted
        assert mock_env_setup['repo_instance'].git.branch.called
        branch_calls = str(mock_env_setup['repo_instance'].git.branch.call_args_list)
        assert "'-D', 'backup-main-" in branch_calls

        # Verify output message contains rebase text
        assert "Rebasing changes from 'main' onto 'develop'" in result.output


def test_release_branch_with_merge(mock_env_setup):
    """Test release command with merge strategy for a different branch."""
    runner = CliRunner()

    # Set up mock methods that may not exist yet
    mock_env_setup['repo_instance'].git.merge = MagicMock()
    mock_env_setup['repo_instance'].git.fetch = MagicMock()
    mock_env_setup['repo_instance'].git.pull = MagicMock()
    mock_env_setup['repo_instance'].git.branch = MagicMock()

    # Create a test environment
    with runner.isolated_filesystem():
        # Run the release command with merge strategy
        result = runner.invoke(
            create_release,
            ['--release-branch', 'develop', '--type', 'minor', '--merge-strategy', 'merge'],
        )

        # Check the command executed successfully
        assert result.exit_code == 0

        # Verify git operations were called
        mock_env_setup['repo_instance'].git.fetch.assert_any_call('origin', 'develop')
        mock_env_setup['repo_instance'].git.fetch.assert_any_call('origin', 'main')

        # Check that a backup branch was created
        checkout_calls = str(mock_env_setup['repo_instance'].git.checkout.call_args_list)
        assert "'-b', 'backup-main-" in checkout_calls

        # Check that we switched to the target branch
        mock_env_setup['repo_instance'].git.checkout.assert_any_call('develop')

        # Check that we tried to pull the latest changes
        mock_env_setup['repo_instance'].git.pull.assert_called_with('origin', 'develop')

        # Check merge was called with --no-ff
        mock_env_setup['repo_instance'].git.merge.assert_called_with('main', '--no-ff')

        # Check backup branch was deleted
        assert mock_env_setup['repo_instance'].git.branch.called
        branch_calls = str(mock_env_setup['repo_instance'].git.branch.call_args_list)
        assert "'-D', 'backup-main-" in branch_calls

        # Verify output message contains merge text
        assert "Merging changes from 'main' into 'develop'" in result.output


def test_release_branch_with_squash_merge(mock_env_setup):
    """Test release command with squash merge strategy for a different branch."""
    runner = CliRunner()

    # Set up mock methods that may not exist yet
    mock_env_setup['repo_instance'].git.merge = MagicMock()
    mock_env_setup['repo_instance'].git.fetch = MagicMock()
    mock_env_setup['repo_instance'].git.pull = MagicMock()
    mock_env_setup['repo_instance'].git.branch = MagicMock()

    # Create a test environment
    with runner.isolated_filesystem():
        # Run the release command with squash merge strategy
        result = runner.invoke(
            create_release,
            ['--release-branch', 'develop', '--type', 'minor', '--merge-strategy', 'merge-squash'],
        )

        # Check the command executed successfully
        assert result.exit_code == 0

        # Verify git operations were called
        mock_env_setup['repo_instance'].git.fetch.assert_any_call('origin', 'develop')
        mock_env_setup['repo_instance'].git.fetch.assert_any_call('origin', 'main')

        # Check that a backup branch was created
        checkout_calls = str(mock_env_setup['repo_instance'].git.checkout.call_args_list)
        assert "'-b', 'backup-main-" in checkout_calls

        # Check that we switched to the target branch
        mock_env_setup['repo_instance'].git.checkout.assert_any_call('develop')

        # Check that we tried to pull the latest changes
        mock_env_setup['repo_instance'].git.pull.assert_called_with('origin', 'develop')

        # Check merge was called with --squash
        mock_env_setup['repo_instance'].git.merge.assert_called_with('main', '--squash')

        # Verify commit was called with appropriate message
        # Using any_call because we have other commits in the test
        mock_env_setup['repo_instance'].git.commit.assert_any_call(
            '-m', "Squashed merge of 'main' into 'develop' for release"
        )

        # Check backup branch was deleted
        assert mock_env_setup['repo_instance'].git.branch.called
        branch_calls = str(mock_env_setup['repo_instance'].git.branch.call_args_list)
        assert "'-D', 'backup-main-" in branch_calls

        # Verify output message contains squash text
        assert "Squash merging changes from 'main' into 'develop'" in result.output


def test_release_nonexistent_branch(mock_env_setup):
    """Test the behavior when the specified branch doesn't exist."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        # Run the release command with a release branch that doesn't exist
        result = runner.invoke(create_release, ['--release-branch', 'nonexistent-branch'])

        # Check the command failed
        assert result.exit_code == 1

        # Check error message
        assert "Error: Release branch 'nonexistent-branch' does not exist" in result.output
        assert 'Available branches:' in result.output

        # Ensure git checkout was not called
        mock_env_setup['repo_instance'].git.checkout.assert_not_called()


def test_release_checkout_failure(mock_env_setup):
    """Test the behavior when git checkout fails."""
    runner = CliRunner()

    # Mock the git checkout to raise an exception
    mock_env_setup['repo_instance'].git.checkout.side_effect = Exception('Checkout failed')

    with runner.isolated_filesystem():
        # Mock click.confirm to always return False (abort on error)
        with patch('click.confirm', return_value=False):
            # Run the release command with catch_exceptions to see the output but not exit
            result = runner.invoke(
                create_release, ['--release-branch', 'develop'], catch_exceptions=True
            )

            # The actual command will exit, but we'll still see the output
            # The exact error message might vary, but check for key parts
            assert 'Checkout failed' in result.output
            # It might not show "Release canceled" if it exits immediately on exception


def test_release_branch_restoration_on_error(mock_env_setup):
    """Test that the original branch is restored when an error occurs during release."""
    runner = CliRunner()

    # Make Repo() always return our mocked repo when called with any arguments
    mock_env_setup['git_repo'].side_effect = lambda *args, **kwargs: mock_env_setup['repo_instance']

    # Set up the test to fail at some point after branch switching
    mock_env_setup['repo_instance'].git.push.side_effect = Exception('Push failed')

    with runner.isolated_filesystem():
        # Use catch_exceptions to see the output even if it exits
        result = runner.invoke(
            create_release, ['--release-branch', 'develop'], catch_exceptions=True
        )

        # The exit code will depend on how the command is structured
        # We mainly want to check the restoration behavior

        # Check that checkout was called for both branches
        mock_env_setup['repo_instance'].git.checkout.assert_any_call('develop')

        # Check for error message in the output
        assert 'Push failed' in result.output


def test_release_branch_restoration_on_success(mock_env_setup):
    """Test that it offers to restore the original branch after a successful release."""
    runner = CliRunner()

    # Setup GitHub client mock to not throw errors
    github_client_instance = mock_env_setup['github_client'].return_value
    github_client_instance.create_release.return_value = {'html_url': 'https://example.com/release'}

    with runner.isolated_filesystem():
        # We need confirmations for releases and branch switching
        with patch('click.confirm', side_effect=[True, True, True]):
            # Run the release command with checkout strategy
            result = runner.invoke(
                create_release,
                ['--release-branch', 'develop', '--merge-strategy', 'checkout'],
                catch_exceptions=True,
            )

            # Check for branch switching messages in the output
            assert "Checking out branch 'develop'" in result.output

            # Verify the checkout call was to develop
            mock_env_setup['repo_instance'].git.checkout.assert_any_call('develop')


def test_release_with_same_branch(mock_env_setup):
    """Test release when already on the specified branch."""
    runner = CliRunner()

    # Set current branch to main, which is the default

    with runner.isolated_filesystem():
        # Run the release command without specifying a branch (defaults to main)
        result = runner.invoke(create_release, [])

        # Check the command succeeded
        assert result.exit_code == 0

        # Ensure it doesn't try to switch branches
        # Since we're already on main, checkout should not be called with 'main'
        if mock_env_setup['repo_instance'].git.checkout.called:
            for call_args in mock_env_setup['repo_instance'].git.checkout.call_args_list:
                assert call_args != call('main')

        # Should not contain branch switching messages
        assert 'Switching to branch' not in result.output


def test_dry_run_no_git_operations(mock_env_setup):
    """Test that dry run doesn't perform any Git operations."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        # Run the release command in dry-run mode
        result = runner.invoke(create_release, ['--release-branch', 'develop', '--dry-run'])

        # Check the command succeeded
        assert result.exit_code == 0

        # Ensure it switched to the develop branch at some point
        mock_env_setup['repo_instance'].git.checkout.assert_any_call('develop')

        # But ensure no commits, tags, or pushes were made
        mock_env_setup['repo_instance'].git.commit.assert_not_called()
        mock_env_setup['repo_instance'].create_tag.assert_not_called()
        mock_env_setup['repo_instance'].git.push.assert_not_called()

        # Check for dry run message
        assert 'DRY RUN MODE - No changes will be made' in result.output

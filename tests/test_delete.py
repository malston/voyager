from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from voyager.commands.delete import delete_release


@pytest.fixture
def mock_github_setup():
    """Mock GitHub client with releases."""
    with patch("voyager.commands.delete.check_git_repo", return_value=True), patch(
        "voyager.commands.delete.get_repo_info", return_value=("test-owner", "test-repo")
    ), patch("voyager.commands.delete.GitHubClient") as mock_github, patch(
        "git.Repo"
    ) as mock_git_repo:
        # Setup GitHub client
        github_instance = mock_github.return_value

        # Create mock releases
        mock_releases = [
            {
                "id": 1,
                "tag_name": "v1.0.0",
                "name": "Release 1.0.0",
                "published_at": "2023-01-01T00:00:00Z",
                "author": {"login": "testuser"},
                "html_url": "https://github.com/test-owner/test-repo/releases/tag/v1.0.0",
            },
            {
                "id": 2,
                "tag_name": "v1.1.0",
                "name": "Release 1.1.0",
                "published_at": "2023-02-01T00:00:00Z",
                "author": {"login": "testuser"},
                "html_url": "https://github.com/test-owner/test-repo/releases/tag/v1.1.0",
            },
        ]
        github_instance.get_releases.return_value = mock_releases
        github_instance.delete_release.return_value = True

        # Setup Git repo
        repo_instance = mock_git_repo.return_value
        repo_instance.git = MagicMock()
        repo_instance.git.tag = MagicMock()
        repo_instance.git.push = MagicMock()

        yield {"github": github_instance, "repo": repo_instance, "releases": mock_releases}


def test_delete_release_specified_tag(mock_github_setup):
    """Test deleting a release with a specified tag."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        # Force deletion to avoid confirmation prompt
        result = runner.invoke(delete_release, ["-t", "v1.0.0", "-f"])

        # Check the command executed successfully
        assert result.exit_code == 0

        # Check that GitHub delete was called with the right parameters
        mock_github_setup["github"].delete_release.assert_called_once_with(
            "test-owner", "test-repo", 1
        )

        # Verify output message
        assert "Successfully deleted release: v1.0.0" in result.output


def test_delete_release_interactive_selection(mock_github_setup):
    """Test deleting a release by selecting it interactively."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        # Simulate user selecting the first release (input="1") and confirming (input="y")
        result = runner.invoke(delete_release, [], input="1\ny\n")

        # Check the command executed successfully
        assert result.exit_code == 0

        # Check that GitHub delete was called with the right parameters
        mock_github_setup["github"].delete_release.assert_called_once_with(
            "test-owner", "test-repo", 1
        )

        # Verify output shows the list of releases
        assert "Available releases for deletion:" in result.output
        assert "v1.0.0 - Release 1.0.0" in result.output
        assert "v1.1.0 - Release 1.1.0" in result.output

        # Verify deletion message
        assert "Successfully deleted release: v1.0.0" in result.output


def test_delete_release_cancel_confirmation(mock_github_setup):
    """Test canceling a release deletion during confirmation."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        # Simulate user selecting the first release but canceling (input="n")
        result = runner.invoke(delete_release, ["-t", "v1.0.0"], input="n\n")

        # Check the command exited cleanly
        assert result.exit_code == 0

        # Check that GitHub delete was not called
        mock_github_setup["github"].delete_release.assert_not_called()

        # Verify cancellation message
        assert "Deletion canceled" in result.output


def test_delete_release_tag_not_found(mock_github_setup):
    """Test trying to delete a non-existent tag."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        # Try to delete a non-existent tag
        result = runner.invoke(delete_release, ["-t", "v9.9.9"])

        # Check for appropriate error message
        assert "Release with tag 'v9.9.9' not found" in result.output

        # Check that GitHub delete was not called
        mock_github_setup["github"].delete_release.assert_not_called()


def test_delete_release_local_tag_error(mock_github_setup):
    """Test scenario where GitHub release is deleted but local tag deletion fails."""
    runner = CliRunner()

    # Setup Git to raise an error when trying to delete the tag
    from git import GitCommandError

    mock_github_setup["repo"].git.tag.side_effect = GitCommandError("tag -d v1.0.0", 1)

    with runner.isolated_filesystem():
        # Force deletion to avoid confirmation prompt
        result = runner.invoke(delete_release, ["-t", "v1.0.0", "-f"])

        # Check the command executed successfully (the GitHub release is still deleted)
        assert result.exit_code == 0

        # Check that GitHub delete was called
        mock_github_setup["github"].delete_release.assert_called_once()

        # Verify warning message about local tag
        assert "Warning: Could not delete local tag" in result.output

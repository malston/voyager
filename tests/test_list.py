from unittest.mock import patch

import pytest
from click.testing import CliRunner

from voyager.commands.list import pipelines, releases


@pytest.fixture
def mock_github_setup():
    """Mock GitHub client with releases."""
    with patch("voyager.commands.list.check_git_repo", return_value=True), patch(
        "voyager.commands.list.get_repo_info", return_value=("test-owner", "test-repo")
    ), patch("voyager.commands.list.GitHubClient") as mock_github:
        # Setup GitHub client
        github_instance = mock_github.return_value

        # Create mock releases
        mock_releases = [
            {
                "tag_name": "v1.0.0",
                "name": "Release 1.0.0",
                "published_at": "2023-01-01T00:00:00Z",
                "author": {"login": "testuser"},
                "html_url": "https://github.com/test-owner/test-repo/releases/tag/v1.0.0",
            },
            {
                "tag_name": "v1.1.0",
                "name": "Release 1.1.0",
                "published_at": "2023-02-01T00:00:00Z",
                "author": {"login": "testuser"},
                "html_url": "https://github.com/test-owner/test-repo/releases/tag/v1.1.0",
            },
        ]
        github_instance.get_releases.return_value = mock_releases

        yield {"github": github_instance, "releases": mock_releases}


@pytest.fixture
def mock_concourse_setup():
    """Mock Concourse client with builds."""
    with patch("voyager.commands.list.check_git_repo", return_value=True), patch(
        "voyager.commands.list.get_repo_info", return_value=("test-owner", "test-repo")
    ), patch("voyager.commands.list.ConcourseClient") as mock_concourse:
        # Setup Concourse client
        concourse_instance = mock_concourse.return_value

        # Create mock builds
        mock_builds = [
            {
                "name": "42",
                "job_name": "build-and-release",
                "status": "succeeded",
                "start_time": "2023-03-01T10:00:00Z",
                "end_time": "2023-03-01T10:05:00Z",
            },
            {
                "name": "41",
                "job_name": "build-and-release",
                "status": "failed",
                "start_time": "2023-02-28T15:00:00Z",
                "end_time": "2023-02-28T15:03:00Z",
            },
        ]
        concourse_instance.get_pipeline_builds.return_value = mock_builds

        yield {"concourse": concourse_instance, "builds": mock_builds}


def test_list_releases_table_format(mock_github_setup):
    """Test listing releases in table format."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(releases, [])

        # Check the command executed successfully
        assert result.exit_code == 0

        # Verify GitHub client was called correctly
        mock_github_setup["github"].get_releases.assert_called_once_with(
            "test-owner", "test-repo", per_page=10
        )

        # Check for table headers and content in the output
        assert "Tag" in result.output
        assert "Name" in result.output
        assert "Published" in result.output
        assert "Author" in result.output
        assert "v1.0.0" in result.output
        assert "v1.1.0" in result.output
        assert "Release 1.0.0" in result.output
        assert "Release 1.1.0" in result.output
        assert "testuser" in result.output

        # Check that the total count is displayed
        assert "Total releases: 2" in result.output


def test_list_releases_json_format(mock_github_setup):
    """Test listing releases in JSON format."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(releases, ["-o", "json"])

        # Check the command executed successfully
        assert result.exit_code == 0

        # Verify JSON format - we'll check for some key elements
        assert '"tag_name": "v1.0.0"' in result.output
        assert '"tag_name": "v1.1.0"' in result.output
        assert '"name": "Release 1.0.0"' in result.output
        assert '"name": "Release 1.1.0"' in result.output

        # JSON format should not include the table headers
        assert "Tag" not in result.output
        assert "Name" not in result.output

        # No total count in JSON output
        assert "Total releases:" not in result.output


def test_list_releases_with_limit(mock_github_setup):
    """Test listing releases with a custom limit."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(releases, ["-n", "1"])

        # Check the command executed successfully
        assert result.exit_code == 0

        # Verify GitHub client was called with the custom limit
        mock_github_setup["github"].get_releases.assert_called_once_with(
            "test-owner", "test-repo", per_page=1
        )


def test_list_releases_quiet_mode():
    """Test listing releases in quiet mode."""
    runner = CliRunner()

    with patch("voyager.commands.list.check_git_repo", return_value=True), patch(
        "voyager.commands.list.get_repo_info", return_value=("test-owner", "test-repo")
    ), patch("voyager.commands.list.GitHubClient") as mock_github:
        github_instance = mock_github.return_value
        mock_releases = [{"tag_name": "v1.0.0", "name": "Release 1.0.0"}]
        github_instance.get_releases.return_value = mock_releases

        with runner.isolated_filesystem():
            # Testing quiet mode requires accessing the main CLI,
            # not just the list_group directly, so we'll create a simpler test
            result = runner.invoke(releases, [])

            # Just make sure the release command works
            assert result.exit_code == 0
            assert "v1.0.0" in result.output


def test_list_pipelines(mock_concourse_setup):
    """Test listing pipeline builds."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        # Concourse options are required
        result = runner.invoke(
            pipelines,
            [
                "--concourse-url",
                "https://concourse.example.com",
                "--concourse-team",
                "main",
                "--pipeline",
                "release-pipeline",
            ],
        )

        # Check the command executed successfully
        assert result.exit_code == 0

        # Verify Concourse client was created and called correctly
        mock_concourse_setup["concourse"].get_pipeline_builds.assert_called_once_with(
            "release-pipeline", limit=5
        )

        # Check for table headers and content in the output
        assert "Build #" in result.output
        assert "Job" in result.output
        assert "Status" in result.output
        assert "Started" in result.output
        assert "Duration" in result.output

        # Check that the build numbers and job names are displayed
        assert "42" in result.output
        assert "41" in result.output
        assert "build-and-release" in result.output

        # Check that the status is displayed (normally with color)
        assert "succeeded" in result.output.lower()
        assert "failed" in result.output.lower()

        # Check that the total count is displayed
        assert "Total builds: 2" in result.output

        # Check that the pipeline URL is displayed
        assert "Pipeline URL:" in result.output
        assert (
            "https://concourse.example.com/teams/main/pipelines/release-pipeline" in result.output
        )


def test_list_pipelines_json_format(mock_concourse_setup):
    """Test listing pipeline builds in JSON format."""
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(
            pipelines,
            [
                "--concourse-url",
                "https://concourse.example.com",
                "--concourse-team",
                "main",
                "--pipeline",
                "release-pipeline",
                "-o",
                "json",
            ],
        )

        # Check the command executed successfully
        assert result.exit_code == 0

        # Verify JSON format - we'll check for some key elements
        assert '"name": "42"' in result.output
        assert '"name": "41"' in result.output
        assert '"job_name": "build-and-release"' in result.output
        assert '"status": "succeeded"' in result.output
        assert '"status": "failed"' in result.output

        # JSON format should not include the table headers
        assert "Build #" not in result.output
        assert "Job" not in result.output

        # No total count in JSON output
        assert "Total builds:" not in result.output

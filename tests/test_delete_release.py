import pytest
import sys
from unittest.mock import patch, MagicMock
from scripts.delete_release import parse_args, main
from scripts.release_helper import ReleaseHelper
from scripts.git_helper import GitHelper


def test_parse_args():
    # Test required argument
    with patch("sys.argv", ["delete_release.py"]):
        with pytest.raises(SystemExit):
            parse_args()

    # Test with valid arguments
    with patch("sys.argv", ["delete_release.py", "-r", "v1.0.0"]):
        args = parse_args()
        assert args.release_tag == "v1.0.0"
        assert args.owner == "Utilities-tkgieng"
        assert not args.no_tag_deletion
        assert not args.non_interactive

    # Test with custom owner
    with patch("sys.argv", ["delete_release.py", "-r", "v1.0.0", "-o", "custom-owner"]):
        args = parse_args()
        assert args.owner == "custom-owner"

    # Test with no tag deletion
    with patch("sys.argv", ["delete_release.py", "-r", "v1.0.0", "-x"]):
        args = parse_args()
        assert args.no_tag_deletion

    # Test non-interactive mode
    with patch("sys.argv", ["delete_release.py", "-r", "v1.0.0", "-n"]):
        args = parse_args()
        assert args.non_interactive


@pytest.mark.parametrize(
    "input_args,expected_repo",
    [
        (["-r", "v1.0.0"], "ns-mgmt"),
        (["-r", "v1.0.0", "-o", "custom-owner"], "ns-mgmt-custom-owner"),
    ],
)
def test_repo_name_construction(input_args, expected_repo):
    with patch("scripts.delete_release.GitHelper") as mock_git_helper:
        with patch("scripts.delete_release.ReleaseHelper") as mock_release_helper:
            mock_git_helper.return_value.check_git_repo.return_value = True
            mock_release_helper.return_value.get_github_release_by_tag.return_value = {
                "tag_name": "v1.0.0"
            }
            mock_release_helper.return_value.delete_github_release.return_value = True

            with patch("sys.argv", ["delete_release.py"] + input_args), patch(
                "builtins.input", return_value="y"
            ):
                args = parse_args()
                main()

                mock_git_helper.assert_called_once_with(repo=expected_repo)


def test_release_not_found():
    with patch("scripts.delete_release.GitHelper") as mock_git_helper:
        with patch("scripts.delete_release.ReleaseHelper") as mock_release_helper:
            mock_git_helper.return_value.check_git_repo.return_value = True
            mock_release_helper.return_value.get_github_release_by_tag.return_value = None
            mock_release_helper.return_value.get_releases.return_value = [
                {"tag_name": "v1.0.0", "name": "Release 1.0.0"},
                {"tag_name": "v2.0.0", "name": "Release 2.0.0"},
            ]

            with patch("sys.argv", ["delete_release.py", "-r", "v3.0.0"]), patch(
                "builtins.input", return_value="y"
            ):
                args = parse_args()
                main()

                mock_git_helper.return_value.error.assert_called_once_with(
                    "Release v3.0.0 not found"
                )


def test_successful_deletion():
    with patch("scripts.delete_release.GitHelper") as mock_git_helper:
        with patch("scripts.delete_release.ReleaseHelper") as mock_release_helper:
            mock_git_helper.return_value.check_git_repo.return_value = True
            mock_release_helper.return_value.get_github_release_by_tag.return_value = {
                "tag_name": "v1.0.0"
            }
            mock_release_helper.return_value.delete_github_release.return_value = True

            with patch("sys.argv", ["delete_release.py", "-r", "v1.0.0"]), patch(
                "builtins.input", return_value="y"
            ):
                args = parse_args()
                main()

                mock_release_helper.return_value.delete_github_release.assert_called_once_with(
                    "v1.0.0", True
                )


def test_deletion_cancelled():
    with patch("scripts.delete_release.GitHelper") as mock_git_helper:
        with patch("scripts.delete_release.ReleaseHelper") as mock_release_helper:
            mock_git_helper.return_value.check_git_repo.return_value = True
            mock_release_helper.return_value.get_github_release_by_tag.return_value = {
                "tag_name": "v1.0.0"
            }

            with patch("sys.argv", ["delete_release.py", "-r", "v1.0.0"]), patch(
                "builtins.input", return_value="n"
            ):
                args = parse_args()
                main()

                mock_release_helper.return_value.delete_github_release.assert_not_called()

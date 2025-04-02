import pytest
import sys
import os
from unittest.mock import patch, MagicMock
from scripts.delete_release import parse_args, main, delete_git_tag, print_available_releases
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


def test_print_available_releases(capsys):
    releases = [
        {"tag_name": "v1.0.0", "name": "Release 1.0.0"},
        {"tag_name": "v2.0.0", "name": "Release 2.0.0"},
    ]
    print_available_releases(releases)
    captured = capsys.readouterr()
    assert (
        captured.out
        == "Available Github Releases:\nv1.0.0 - Release 1.0.0\nv2.0.0 - Release 2.0.0\n"
    )


def test_delete_git_tag():
    mock_git_helper = MagicMock()
    mock_git_helper.tag_exists = MagicMock()
    mock_release_helper = MagicMock(spec=ReleaseHelper)
    mock_args = MagicMock()
    mock_args.non_interactive = False
    mock_args.no_tag_deletion = False
    tag = "v1.0.0"

    # Test when tag exists and user confirms
    mock_git_helper.tag_exists.return_value = True
    with patch("builtins.input", return_value="y"):
        delete_git_tag(mock_git_helper, mock_release_helper, tag, mock_args)
        mock_release_helper.delete_release_tag.assert_called_once_with(tag)

    # Test when tag exists but user cancels
    mock_release_helper.reset_mock()
    with patch("builtins.input", return_value="n"):
        delete_git_tag(mock_git_helper, mock_release_helper, tag, mock_args)
        mock_release_helper.delete_release_tag.assert_not_called()

    # Test when tag doesn't exist
    mock_git_helper.tag_exists.return_value = False
    delete_git_tag(mock_git_helper, mock_release_helper, tag, mock_args)
    mock_release_helper.delete_release_tag.assert_not_called()
    mock_git_helper.error.assert_called_once_with(f"Git tag {tag} not found in repository")

    # Test in non-interactive mode
    mock_args.non_interactive = True
    mock_git_helper.tag_exists.return_value = True
    mock_git_helper.reset_mock()
    mock_release_helper.reset_mock()
    delete_git_tag(mock_git_helper, mock_release_helper, tag, mock_args)
    mock_release_helper.delete_release_tag.assert_called_once_with(tag)


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
            with patch("os.path.isdir", return_value=True):
                mock_git_helper.return_value.check_git_repo.return_value = True
                mock_release_helper.return_value.get_github_release_by_tag.return_value = {
                    "tag_name": "v1.0.0"
                }
                mock_release_helper.return_value.delete_github_release.return_value = True
                mock_git_helper.return_value.tag_exists.return_value = True

                with patch("sys.argv", ["delete_release.py"] + input_args), patch(
                    "builtins.input", return_value="y"
                ):
                    args = parse_args()
                    main()

                    mock_git_helper.assert_called_once_with(
                        repo="ns-mgmt", repo_dir=f"/Users/malston/git/{expected_repo}"
                    )


def test_release_not_found():
    with patch("scripts.delete_release.GitHelper") as mock_git_helper:
        with patch("scripts.delete_release.ReleaseHelper") as mock_release_helper:
            with patch("os.path.isdir", return_value=True):
                mock_git_helper.return_value.check_git_repo.return_value = True
                mock_release_helper.return_value.get_github_release_by_tag.return_value = None
                mock_release_helper.return_value.get_releases.return_value = [
                    {"tag_name": "v1.0.0", "name": "Release 1.0.0"},
                    {"tag_name": "v2.0.0", "name": "Release 2.0.0"},
                ]
                mock_git_helper.return_value.tag_exists.return_value = True

                with patch("sys.argv", ["delete_release.py", "-r", "v3.0.0"]), patch(
                    "builtins.input", return_value="y"
                ):
                    args = parse_args()
                    main()

                    mock_git_helper.return_value.error.assert_called_once_with(
                        "Release v3.0.0 not found"
                    )


def test_no_releases_found():
    with patch("scripts.delete_release.GitHelper") as mock_git_helper:
        with patch("scripts.delete_release.ReleaseHelper") as mock_release_helper:
            with patch("os.path.isdir", return_value=True):
                mock_git_helper.return_value.check_git_repo.return_value = True
                mock_release_helper.return_value.get_github_release_by_tag.return_value = None
                mock_release_helper.return_value.get_releases.return_value = []
                mock_git_helper.return_value.tag_exists.return_value = True

                with patch("sys.argv", ["delete_release.py", "-r", "v1.0.0"]), patch(
                    "builtins.input", return_value="y"
                ):
                    args = parse_args()
                    main()

                    # Check that error was called with "No releases found"
                    mock_git_helper.return_value.error.assert_any_call("No releases found")
                    mock_release_helper.return_value.delete_release_tag.assert_called_once_with(
                        "v1.0.0"
                    )


def test_successful_deletion():
    with patch("scripts.delete_release.GitHelper") as mock_git_helper:
        with patch("scripts.delete_release.ReleaseHelper") as mock_release_helper:
            with patch("os.path.isdir", return_value=True):
                mock_git_helper.return_value.check_git_repo.return_value = True
                mock_release_helper.return_value.get_github_release_by_tag.return_value = {
                    "tag_name": "v1.0.0"
                }
                mock_release_helper.return_value.delete_github_release.return_value = True
                mock_git_helper.return_value.tag_exists.return_value = True

                with patch("sys.argv", ["delete_release.py", "-r", "v1.0.0"]), patch(
                    "builtins.input", return_value="y"
                ):
                    args = parse_args()
                    main()

                    mock_release_helper.return_value.delete_github_release.assert_called_once_with(
                        "v1.0.0", True
                    )
                    mock_release_helper.return_value.delete_release_tag.assert_called_once_with(
                        "v1.0.0"
                    )


def test_deletion_cancelled():
    with patch("scripts.delete_release.GitHelper") as mock_git_helper:
        with patch("scripts.delete_release.ReleaseHelper") as mock_release_helper:
            with patch("os.path.isdir", return_value=True):
                mock_git_helper.return_value.check_git_repo.return_value = True
                mock_release_helper.return_value.get_github_release_by_tag.return_value = {
                    "tag_name": "v1.0.0"
                }
                mock_git_helper.return_value.tag_exists.return_value = True

                with patch("sys.argv", ["delete_release.py", "-r", "v1.0.0"]), patch(
                    "builtins.input", return_value="n"
                ):
                    args = parse_args()
                    main()

                    mock_release_helper.return_value.delete_github_release.assert_not_called()
                    mock_release_helper.return_value.delete_release_tag.assert_not_called()

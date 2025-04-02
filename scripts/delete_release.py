#!/usr/bin/env python3

# Delete a GitHub release.
# This script deletes a GitHub release and optionally the associated git tag.
# Usage:
#     delete_release.py -r release_tag [-o owner] [-x] [-n] [-h]
# Options:
#     -r release_tag   the release tag
#     -o owner         the github owner (default: Utilities-tkgieng)
#     -x               do not delete the git tag
#     -n               non-interactive
#     -h               display usage

import argparse
import os
import sys
from pathlib import Path
from tabulate import tabulate

# Add the project root to the Python path
PROJECT_ROOT = str(Path(__file__).parent.parent)
sys.path.insert(0, PROJECT_ROOT)

from scripts.release_helper import ReleaseHelper
from scripts.git_helper import GitHelper


class CustomHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Custom help formatter to modify the help output."""

    def format_help(self):
        help_text = super().format_help()
        # Remove the default options section
        help_text = help_text.split("\n\n")[0] + "\n\n" + help_text.split("\n\n")[-1]
        # Change "usage:" to "Usage:"
        help_text = help_text.replace("usage:", "Usage:")
        return help_text


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="delete_release.py",
        description="Delete a GitHub release",
        formatter_class=CustomHelpFormatter,
        add_help=False,
        usage="%(prog)s -r release_tag [-o owner] [-x] [-n] [-h]",
        epilog="""
Options:
  -r release_tag   the release tag
  -o owner         the github owner (default: Utilities-tkgieng)
  -x               do not delete the git tag
  -n               non-interactive
  -h               display usage
""",
    )
    parser.add_argument(
        "-r",
        "--release-tag",
        required=True,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "-o",
        "--owner",
        default="Utilities-tkgieng",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "-x",
        "--no-tag-deletion",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "-n",
        "--non-interactive",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "-h",
        "--help",
        action="help",
        help="display usage",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo = "ns-mgmt"

    git_dir = os.path.expanduser("~/git")
    repo_dir = os.path.join(git_dir, repo)

    # Check if repo ends with the owner
    if args.owner != "Utilities-tkgieng":
        repo_dir = os.path.join(git_dir, f"{repo}-{args.owner}")
    if not os.path.isdir(repo_dir):
        raise ValueError(f"Could not find repo directory: {repo_dir}")

    # Initialize helpers
    release_helper = ReleaseHelper(repo=repo, repo_dir=repo_dir, owner=args.owner)
    git_helper = GitHelper(repo=repo, repo_dir=repo_dir)
    if not git_helper.check_git_repo():
        git_helper.error(f"{repo} is not a git repository")
        return

    release = release_helper.get_github_release_by_tag(args.release_tag)
    if not release:
        git_helper.error(f"Release {args.release_tag} not found")
        releases = release_helper.get_releases()
        if not releases:
            git_helper.error("No releases found")
            return
        # print(tabulate(releases, headers="keys", tablefmt="grid"))
        print(f"Available Github Releases:")
        for release in releases:
            print(f"{release['tag_name']} - {release['name']}")
        return

    try:
        if not args.non_interactive:
            user_input = input(
                f"Are you sure you want to delete github release: {args.release_tag}? [yN] "
            )
            if not user_input.lower().startswith("y"):
                return

        if not release_helper.delete_github_release(args.release_tag, not args.no_tag_deletion):
            git_helper.error("Failed to delete GitHub release")
            return

    except (ConnectionError, ValueError, ImportError, FileNotFoundError, PermissionError) as e:
        git_helper.error(f"Unexpected error: {e}")
        return


if __name__ == "__main__":
    main()

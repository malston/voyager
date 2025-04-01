#!/usr/bin/env python3

import argparse
import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)

from scripts.release_helper import ReleaseHelper
from scripts.git_helper import GitHelper


class CustomHelpFormatter(argparse.RawDescriptionHelpFormatter):
    def format_help(self):
        help_text = super().format_help()
        # Remove the default options section
        help_text = help_text.split("\n\n")[0] + "\n\n" + help_text.split("\n\n")[-1]
        # Change "usage:" to "Usage:"
        help_text = help_text.replace("usage:", "Usage:")
        return help_text


def parse_args() -> argparse.Namespace:
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

    # Initialize helpers
    git_helper = GitHelper()
    release_helper = ReleaseHelper(repo=repo, owner=args.owner)

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

    except Exception as e:
        git_helper.error(f"Unexpected error: {e}")
        return


if __name__ == "__main__":
    main()

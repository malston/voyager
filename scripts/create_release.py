#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Add the project root to the Python path
PROJECT_ROOT = str(Path(__file__).parent.parent)
sys.path.insert(0, PROJECT_ROOT)

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
        prog="create_release.py",
        description="Create a new release",
        formatter_class=CustomHelpFormatter,
        add_help=False,
        usage="%(prog)s -f foundation [-m release_body] [-o owner] [-p params_repo] [-h]",
        epilog="""
Options:
   -f foundation    the foundation name for ops manager (e.g. cml-k8s-n-01)
   -m release_body  the message to apply to the release that is created (optional)
   -o owner         the github owner (default: Utilities-tkgieng)
   -p params_repo   the params repo name always located under ~/git (default: params)
   -h               display usage
""",
    )
    parser.add_argument(
        "-f",
        "--foundation",
        required=True,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "-m",
        "--message",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "-o",
        "--owner",
        default="Utilities-tkgieng",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "-p",
        "--params-repo",
        default="params",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--dry-run",
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
    release_pipeline = f"tkgi-{repo}-release"
    params_repo = args.params_repo

    if args.owner != "Utilities-tkgieng":
        repo = f"{repo}-{args.owner}"
        params_repo = f"{args.params_repo}-{args.owner}"
        release_pipeline = f"tkgi-{repo}-release"

    # Initialize helpers
    git_helper = GitHelper(repo=repo)
    if not git_helper.check_git_repo():
        git_helper.error("Git is not installed or not in PATH")
        return
    release_helper = ReleaseHelper(repo=repo, owner=args.owner, params_repo=params_repo)

    try:
        # Change to the repo's ci directory
        ci_dir = os.path.expanduser(f"~/git/{repo}/ci")
        if not os.path.exists(ci_dir):
            git_helper.error(f"CI directory not found at {ci_dir}")
            return

        if args.dry_run:
            git_helper.info("DRY RUN MODE - No changes will be made")
            git_helper.info(f"Would change to directory: {ci_dir}")
        else:
            os.chdir(ci_dir)

        # Run release pipeline
        if args.dry_run:
            git_helper.info(f"Would run release pipeline: {release_pipeline}")
            git_helper.info(f"Foundation: {args.foundation}")
            if args.message:
                git_helper.info(f"Release message: {args.message}")
        else:
            if not release_helper.run_release_pipeline(args.foundation, args.message):
                git_helper.error("Failed to run release pipeline")
                return

        # Update git release tag
        if args.dry_run:
            git_helper.info("Would update git release tag")
        else:
            if not release_helper.update_params_git_release_tag():
                git_helper.error("Failed to update git release tag")
                return

        # Run set pipeline
        if args.dry_run:
            git_helper.info(f"Would run set pipeline for foundation: {args.foundation}")
        else:
            if not release_helper.run_set_pipeline(args.foundation):
                git_helper.error("Failed to run set pipeline")
                return

        # Ask if user wants to run the prepare-kustomizations job
        if not args.dry_run:
            user_input = input(
                f"Do you want to run the tkgi-{repo}-{args.foundation} pipeline? [yN] "
            )
            if user_input.lower().startswith("y"):
                subprocess.run(
                    [
                        "fly",
                        "-t",
                        args.foundation,
                        "trigger-job",
                        "-j",
                        f"tkgi-{repo}-{args.foundation}/prepare-kustomizations",
                        "-w",
                    ],
                    check=True,
                )
        else:
            git_helper.info(f"Would prompt to run tkgi-{repo}-{args.foundation} pipeline")

        # Get current branch
        branch = git_helper.get_current_branch()

        # Ask if user wants to refly the pipeline
        if not args.dry_run:
            user_input = input(
                f"Do you want to refly the tkgi-{repo}-{args.foundation} pipeline back to latest code on branch: {branch}? [yN] "
            )
            if user_input.lower().startswith("y"):
                subprocess.run(
                    ["./fly.sh", "-f", args.foundation, "-b", branch],
                    input=b"y\n",
                    check=True,
                )
        else:
            git_helper.info(f"Would prompt to refly pipeline on branch: {branch}")

    except subprocess.CalledProcessError as e:
        git_helper.error(f"Command failed with exit code {e.returncode}: {e}")
        return
    except Exception as e:
        git_helper.error(f"Unexpected error: {e}")
        return


if __name__ == "__main__":
    main()

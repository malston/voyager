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
        help_text = help_text.split('\n\n')[0] + '\n\n' + help_text.split('\n\n')[-1]
        # Change "usage:" to "Usage:"
        help_text = help_text.replace('usage:', 'Usage:')
        return help_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog='rollback_release.py',
        description='Rollback a release',
        formatter_class=CustomHelpFormatter,
        add_help=False,
        usage='%(prog)s -f foundation -r release_tag [-p params_repo] [-h]',
        epilog="""
Options:
   -f foundation    the foundation name for ops manager (e.g. cml-k8s-n-01)
   -r release_tag   the release tag
   -p params_repo   the params repo name always located under ~/git (default: params)
   -h               display usage
""",
    )
    parser.add_argument(
        '-f',
        '--foundation',
        required=True,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        '-r',
        '--release',
        required=True,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        '-p',
        '--params-repo',
        default='params',
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        '-h',
        '--help',
        action='help',
        help='display usage',
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo = 'ns-mgmt'

    # Initialize helpers
    git_helper = GitHelper()
    release_helper = ReleaseHelper(repo=repo, params_repo=args.params_repo)

    try:
        # Change to the repo's ci directory
        ci_dir = os.path.expanduser(f'~/git/{repo}/ci')
        if not os.path.exists(ci_dir):
            git_helper.error(f'CI directory not found at {ci_dir}')
            return

        os.chdir(ci_dir)

        # Validate release tag
        release_tag = f"{repo}-{args.release}"
        if not release_helper.validate_params_release_tag(release_tag):
            git_helper.error(f'Release [-r {args.release}] must be a valid release tagged on the params repo')
            git_helper.info('Valid tags are:')
            release_helper.print_valid_params_release_tags()
            return

        # Run set pipeline
        if not release_helper.run_set_pipeline(args.foundation):
            git_helper.error('Failed to run set pipeline')
            return

        # Ask user if they want to run the pipeline
        user_input = input(f'Do you want to run the tkgi-{repo}-{args.foundation} pipeline? [yN] ')
        if user_input.lower().startswith('y'):
            try:
                subprocess.run(
                    [
                        'fly',
                        '-t',
                        args.foundation,
                        'trigger-job',
                        f'tkgi-{repo}-{args.foundation}/prepare-kustomizations',
                        '-w',
                    ],
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                git_helper.error(f'Failed to trigger pipeline job: {e}')
                return

    except Exception as e:
        git_helper.error(f'Unexpected error: {e}')
        return


if __name__ == '__main__':
    main() 
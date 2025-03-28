#!/usr/bin/env python3

import sys
import click

from ..github import GitHubClient
from ..utils import check_git_repo, get_repo_info


@click.command('list')
@click.option('--limit', '-l', default=10, help='Limit the number of releases shown')
def list_releases(limit):
    """List all releases for the repository."""
    if not check_git_repo():
        click.echo('Error: Current directory is not a git repository', err=True)
        sys.exit(1)

    try:
        owner, repo = get_repo_info()
        click.echo(f'Fetching releases for {owner}/{repo}...')

        # Full implementation would go here
        click.echo('List command not fully implemented yet.')

    except Exception as e:
        click.echo(f'Error listing releases: {str(e)}', err=True)
        sys.exit(1)

#!/usr/bin/env python3

import sys
import click
from datetime import datetime
from tabulate import tabulate

from ..github import GitHubClient
from ..utils import check_git_repo, get_repo_info
from ..click_utils import CONTEXT_SETTINGS


@click.command('list', context_settings=CONTEXT_SETTINGS)
@click.option('--limit', '-l', default=10, help='Limit the number of releases shown')
@click.option(
    '--format', '-f', type=click.Choice(['table', 'json']), default='table', help='Output format'
)
def list_releases(limit, format):
    """List all releases for the repository."""
    if not check_git_repo():
        click.echo('Error: Current directory is not a git repository', err=True)
        sys.exit(1)

    try:
        owner, repo = get_repo_info()
        click.echo(f'Fetching releases for {owner}/{repo}...')

        # Fetch releases from GitHub
        github_client = GitHubClient()
        releases = github_client.get_releases(owner, repo, per_page=limit)

        if not releases:
            click.echo('No releases found for this repository.')
            return

        if format == 'json':
            # Output as JSON
            import json

            click.echo(json.dumps(releases, indent=2))
        else:
            # Format releases as a table
            table_data = []
            headers = ['Tag', 'Name', 'Published', 'Author', 'URL']

            for release in releases:
                # Parse and format the date
                published_at = release.get('published_at')
                if published_at:
                    date_obj = datetime.strptime(published_at, '%Y-%m-%dT%H:%M:%SZ')
                    formatted_date = date_obj.strftime('%Y-%m-%d %H:%M')
                else:
                    formatted_date = 'N/A'

                # Get the author login
                author = release.get('author', {}).get('login', 'Unknown')

                # Add the row
                table_data.append(
                    [
                        release.get('tag_name', 'No tag'),
                        release.get('name', 'Unnamed'),
                        formatted_date,
                        author,
                        release.get('html_url', ''),
                    ]
                )

            # Print the table
            click.echo(tabulate(table_data, headers=headers, tablefmt='simple'))
            click.echo(f'\nTotal releases: {len(releases)}')

    except Exception as e:
        click.echo(f'Error listing releases: {str(e)}', err=True)
        sys.exit(1)

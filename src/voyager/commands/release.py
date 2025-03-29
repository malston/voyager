#!/usr/bin/env python3

import os
import sys
import click
import git
import semver
from datetime import datetime

from ..github import GitHubClient
from ..concourse import ConcourseClient
from ..utils import check_git_repo, get_repo_info


@click.command('release')
@click.option(
    '--type',
    '-t',
    type=click.Choice(['major', 'minor', 'patch']),
    default='patch',
    help='Release type (major, minor, patch)',
)
@click.option('--message', '-m', help='Release message')
@click.option('--branch', '-b', default='main', help='Branch to release from')
@click.option(
    '--dry-run', '-d', is_flag=True, help='Perform a dry run without creating actual release'
)
@click.option('--concourse-url', help='Concourse CI API URL')
@click.option('--concourse-team', help='Concourse CI team name')
@click.option('--pipeline', help='Concourse pipeline name to trigger')
@click.option('--job', default='build-and-release', help='Concourse job name to trigger')
def create_release(type, message, branch, dry_run, concourse_url, concourse_team, pipeline, job):
    """Create a new release from the current branch."""
    if not check_git_repo():
        click.echo('Error: Current directory is not a git repository', err=True)
        sys.exit(1)

    try:
        owner, repo = get_repo_info()
        click.echo(f'Preparing release for {owner}/{repo}...')

        # Get the git repo
        git_repo = git.Repo(os.getcwd())

        # Ensure we're on the specified branch
        current_branch = git_repo.active_branch.name
        if current_branch != branch:
            click.echo(f"Warning: You are on branch '{current_branch}', not '{branch}'")
            if not click.confirm(f"Continue release from branch '{current_branch}'?"):
                click.echo('Release canceled.')
                sys.exit(0)

        # Determine current version
        current_version = get_current_version(git_repo)
        click.echo(f'Current version: {current_version}')

        # Calculate new version
        if current_version:
            if type == 'major':
                new_version = str(semver.VersionInfo.parse(current_version).bump_major())
            elif type == 'minor':
                new_version = str(semver.VersionInfo.parse(current_version).bump_minor())
            else:  # patch
                new_version = str(semver.VersionInfo.parse(current_version).bump_patch())
        else:
            # Default to 0.1.0 if no version found
            new_version = '0.1.0'
            click.echo('No previous version found. Starting with 0.1.0')

        click.echo(f'New version will be: {new_version}')

        # Prepare release message
        if not message:
            message = f'Release {new_version}'

        title = f'v{new_version}'
        release_body = f"""
# Release v{new_version}

{message}

Released on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

        if dry_run:
            click.echo('DRY RUN MODE - No changes will be made')
            click.echo(f'Would create release: {title}')
            click.echo(f'With message: {release_body}')
            return

        # Update version in code
        update_version_in_code(new_version)

        # Commit changes
        commit_message = f'Bump version to {new_version}'
        click.echo(f'Committing version change: {commit_message}')
        git_repo.git.add('voyager/__init__.py')
        git_repo.git.commit('-m', commit_message)

        # Create tag
        tag_name = f'v{new_version}'
        click.echo(f'Creating tag: {tag_name}')
        git_repo.create_tag(tag_name)

        # Push changes and tag
        click.echo('Pushing changes and tag to remote...')
        git_repo.git.push('origin', branch)
        git_repo.git.push('origin', tag_name)

        # Create GitHub release
        click.echo('Creating GitHub release...')
        github_client = GitHubClient()
        release = github_client.create_release(
            owner=owner,
            repo=repo,
            tag_name=tag_name,
            name=title,
            body=release_body,
        )

        click.echo(f'✓ GitHub release created: {release.get("html_url")}')

        # Trigger Concourse pipeline if requested
        if concourse_url and concourse_team and pipeline:
            click.echo('Triggering Concourse CI pipeline...')

            try:
                concourse_client = ConcourseClient(api_url=concourse_url, team=concourse_team)

                variables = {'version': new_version, 'is_rollback': 'false'}

                pipeline_triggered = concourse_client.trigger_pipeline(
                    pipeline_name=pipeline, job_name=job, variables=variables
                )

                if pipeline_triggered:
                    click.echo('✓ Concourse pipeline triggered successfully')
                else:
                    click.echo('⚠ Failed to trigger Concourse pipeline', err=True)

            except Exception as e:
                click.echo(f'⚠ Concourse error: {str(e)}', err=True)
                click.echo('Release created successfully, but pipeline trigger failed.')

        click.echo(f'✓ Release v{new_version} completed successfully!')

    except Exception as e:
        click.echo(f'Error creating release: {str(e)}', err=True)
        sys.exit(1)


def get_current_version(git_repo):
    """Get the current version from the package."""
    try:
        with open(os.path.join(git_repo.working_dir, 'voyager', '__init__.py'), 'r') as f:
            content = f.read()
            version_match = re.search(r'__version__\s*=\s*[\'"]([^\'"]*)[\'"]', content)
            if version_match:
                return version_match.group(1)

        # Try to get the latest tag if no version in code
        tags = sorted(git_repo.tags, key=lambda t: t.commit.committed_datetime)
        if tags:
            latest_tag = str(tags[-1])
            if latest_tag.startswith('v'):
                return latest_tag[1:]  # Remove 'v' prefix

        return None
    except Exception as e:
        click.echo(f'Warning: Could not determine current version: {str(e)}', err=True)
        return None


def update_version_in_code(new_version):
    """Update the version in the package __init__.py file."""
    try:
        init_file = os.path.join('voyager', '__init__.py')

        with open(init_file, 'r') as f:
            content = f.read()

        new_content = re.sub(
            r'__version__\s*=\s*[\'"]([^\'"]*)[\'"]', f"__version__ = '{new_version}'", content
        )

        with open(init_file, 'w') as f:
            f.write(new_content)

        click.echo(f'Updated version in {init_file}')

    except Exception as e:
        raise Exception(f'Failed to update version in code: {str(e)}')

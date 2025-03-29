#!/usr/bin/env python3

import os
import sys
import click
import git
import re
from datetime import datetime

from ..github import GitHubClient
from ..concourse import ConcourseClient
from ..utils import check_git_repo, get_repo_info


@click.command('rollback')
@click.option('--tag', '-t', help='Specific tag to rollback to')
@click.option('--dry-run', '-d', is_flag=True, help='Perform a dry run without actual rollback')
@click.option('--concourse-url', help='Concourse CI API URL')
@click.option('--concourse-team', help='Concourse CI team name')
@click.option('--pipeline', help='Concourse pipeline name to trigger')
@click.option('--job', default='rollback', help='Concourse job name to trigger')
def rollback(tag, dry_run, concourse_url, concourse_team, pipeline, job):
    """Rollback to a previous release."""
    if not check_git_repo():
        click.echo('Error: Current directory is not a git repository', err=True)
        sys.exit(1)

    try:
        owner, repo = get_repo_info()
        git_repo = git.Repo(os.getcwd())

        # Fetch releases to display options
        github_client = GitHubClient()
        releases = github_client.get_releases(owner, repo, per_page=20)

        if not releases:
            click.echo('No releases found to roll back to.')
            sys.exit(1)

        # If tag is not specified, ask the user to select a release
        if not tag:
            click.echo('Available releases for rollback:')

            for idx, release in enumerate(releases, 1):
                published_at = release.get('published_at', 'N/A')
                if published_at != 'N/A':
                    date_obj = datetime.strptime(published_at, '%Y-%m-%dT%H:%M:%SZ')
                    formatted_date = date_obj.strftime('%Y-%m-%d %H:%M')
                else:
                    formatted_date = 'N/A'

                click.echo(
                    f'{idx}. {release.get("tag_name")} - {release.get("name")} ({formatted_date})'
                )

            while True:
                choice = click.prompt('Enter the number of the release to roll back to', type=int)
                if 1 <= choice <= len(releases):
                    selected_release = releases[choice - 1]
                    tag = selected_release.get('tag_name')
                    break
                else:
                    click.echo(
                        f'Invalid choice. Please enter a number between 1 and {len(releases)}'
                    )

        # Validate the tag exists
        try:
            tag_commit = git_repo.tags[tag].commit
        except (IndexError, ValueError):
            click.echo(f"Error: Tag '{tag}' does not exist in the repository")
            sys.exit(1)

        click.echo(f'Rolling back to release: {tag}')

        # Get the version number (remove 'v' prefix if present)
        version = tag[1:] if tag.startswith('v') else tag

        # Verify with the user before proceeding
        if not dry_run and not click.confirm(f'Are you sure you want to roll back to {tag}?'):
            click.echo('Rollback cancelled.')
            sys.exit(0)

        if dry_run:
            click.echo('DRY RUN MODE - No changes will be made')
            click.echo(f'Would roll back to: {tag}')
            if concourse_url and concourse_team and pipeline:
                click.echo(f'Would trigger Concourse pipeline: {pipeline}, job: {job}')
            return

        # Create a new 'rollback' branch from the tag
        rollback_branch = f'rollback-to-{tag}'
        click.echo(f'Creating rollback branch: {rollback_branch}')

        # Check if the branch already exists and delete it if it does
        try:
            git_repo.git.branch('-D', rollback_branch)
            click.echo(f'Deleted existing branch: {rollback_branch}')
        except git.GitCommandError:
            # Branch doesn't exist, which is fine
            pass

        # Create the new branch
        git_repo.git.checkout('-b', rollback_branch, tag)

        # Update version in code
        update_version_in_code(git_repo, version)

        # Commit changes
        commit_message = f'Rollback to {tag}'
        click.echo(f'Committing version change: {commit_message}')
        git_repo.git.add('voyager/__init__.py')
        git_repo.git.commit('-m', commit_message)

        # Push the rollback branch
        click.echo('Pushing rollback branch to remote...')
        git_repo.git.push('-f', 'origin', rollback_branch)

        # Create rollback tag
        rollback_tag = f'rollback-{tag}-{datetime.now().strftime("%Y%m%d%H%M%S")}'
        click.echo(f'Creating rollback tag: {rollback_tag}')
        git_repo.create_tag(rollback_tag)
        git_repo.git.push('origin', rollback_tag)

        # Create GitHub release for the rollback
        click.echo('Creating GitHub release for rollback...')
        rollback_message = f"""
# Rollback to {tag}

This is a rollback to the previous release {tag}.

Rolled back on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        rollback_release = github_client.create_release(
            owner=owner,
            repo=repo,
            tag_name=rollback_tag,
            name=f'Rollback to {tag}',
            body=rollback_message,
        )

        click.echo(f'✓ GitHub rollback release created: {rollback_release.get("html_url")}')

        # Trigger Concourse pipeline if requested
        if concourse_url and concourse_team and pipeline:
            click.echo('Triggering Concourse CI rollback pipeline...')

            try:
                concourse_client = ConcourseClient(api_url=concourse_url, team=concourse_team)

                variables = {'version': version, 'is_rollback': 'true'}

                pipeline_triggered = concourse_client.trigger_pipeline(
                    pipeline_name=pipeline, job_name=job, variables=variables
                )

                if pipeline_triggered:
                    click.echo('✓ Concourse rollback pipeline triggered successfully')
                else:
                    click.echo('⚠ Failed to trigger Concourse pipeline', err=True)

            except Exception as e:
                click.echo(f'⚠ Concourse error: {str(e)}', err=True)
                click.echo('Rollback created successfully, but pipeline trigger failed.')

        # Advice on how to proceed
        click.echo('\nRollback branch created successfully.')
        click.echo(
            f"If you want to complete the rollback, merge the '{rollback_branch}' branch to your main branch:"
        )
        click.echo(f'  git checkout main')
        click.echo(f'  git merge {rollback_branch}')
        click.echo(f'  git push origin main')

    except Exception as e:
        click.echo(f'Error during rollback: {str(e)}', err=True)
        sys.exit(1)


def update_version_in_code(git_repo, version):
    """Update the version in the package __init__.py file."""
    try:
        init_file = os.path.join(git_repo.working_dir, 'voyager', '__init__.py')

        with open(init_file, 'r') as f:
            content = f.read()

        new_content = re.sub(
            r'__version__\s*=\s*[\'"]([^\'"]*)[\'"]', f"__version__ = '{version}'", content
        )

        with open(init_file, 'w') as f:
            f.write(new_content)

        click.echo(f'Updated version in {init_file}')

    except Exception as e:
        raise Exception(f'Failed to update version in code: {str(e)}')

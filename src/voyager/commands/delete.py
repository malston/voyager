#!/usr/bin/env python3

import os
import sys
from datetime import datetime

import click

from ..click_utils import CONTEXT_SETTINGS
from ..github import GitHubClient
from ..utils import check_git_repo, get_repo_info


@click.command("delete", context_settings=CONTEXT_SETTINGS)
@click.option("-t", "--tag", metavar="TAG", help="Specific tag to delete")
@click.option("-f", "--force", is_flag=True, help="Force deletion without confirmation")
@click.pass_context
def delete_release(ctx, tag, force):
    """Delete a release and its tag."""
    if not check_git_repo():
        click.echo("Error: Current directory is not a git repository", err=True)
        sys.exit(1)

    try:
        owner, repo = get_repo_info()

        # Initialize GitHub client
        github_client = GitHubClient()

        # Fetch releases
        releases = github_client.get_releases(owner, repo, per_page=20)

        if not releases:
            click.echo("No releases found to delete.")
            sys.exit(1)

        # If tag is not specified, ask the user to select a release
        selected_release = None
        if not tag:
            click.echo("Available releases for deletion:")

            for idx, release in enumerate(releases, 1):
                published_at = release.get("published_at", "N/A")
                if published_at != "N/A":
                    date_obj = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ")
                    formatted_date = date_obj.strftime("%Y-%m-%d %H:%M")
                else:
                    formatted_date = "N/A"

                click.echo(
                    f'{idx}. {release.get("tag_name")} - {release.get("name")} ({formatted_date})'
                )

            while True:
                choice = click.prompt("Enter the number of the release to delete", type=int)
                if 1 <= choice <= len(releases):
                    selected_release = releases[choice - 1]
                    tag = selected_release.get("tag_name")
                    break
                else:
                    click.echo(
                        f"Invalid choice. Please enter a number between 1 and {len(releases)}"
                    )
        else:
            # Find the release by tag name
            for release in releases:
                if release.get("tag_name") == tag:
                    selected_release = release
                    break

        if not selected_release:
            click.echo(f"Release with tag '{tag}' not found.")
            sys.exit(1)

        # Get the release ID
        release_id = selected_release.get("id")

        # Confirm deletion unless force flag is set
        if not force:
            release_name = selected_release.get("name", "Unnamed")
            click.echo(f"Preparing to delete release: {tag} - {release_name}")
            if not click.confirm(
                "Are you sure you want to delete this release? This action cannot be undone."
            ):
                click.echo("Deletion canceled.")
                sys.exit(0)

        # Delete the release
        click.echo(f"Deleting GitHub release: {tag}")
        success = github_client.delete_release(owner, repo, release_id)

        if success:
            click.echo(f"✓ Successfully deleted release: {tag}")

            # Delete the associated tag
            try:
                # Use Git API to delete the tag
                import git

                local_repo = git.Repo(os.getcwd())

                # Try to delete the tag locally
                try:
                    local_repo.git.tag("-d", tag)
                    click.echo(f"✓ Deleted local tag: {tag}")
                except git.GitCommandError as e:
                    click.echo(f"Warning: Could not delete local tag: {e}")

                # Try to delete the tag remotely
                try:
                    local_repo.git.push("origin", f":refs/tags/{tag}")
                    click.echo(f"✓ Deleted remote tag: {tag}")
                except git.GitCommandError as e:
                    click.echo(f"Warning: Could not delete remote tag: {e}")

            except Exception as e:
                click.echo(f"Warning: Could not delete associated Git tag: {e}")
                click.echo("You may need to delete the Git tag manually.")
        else:
            click.echo(f"Failed to delete release: {tag}", err=True)

    except Exception as e:
        click.echo(f"Error deleting release: {str(e)}", err=True)
        sys.exit(1)

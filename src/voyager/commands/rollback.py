#!/usr/bin/env python3

import os
import re
import sys
from datetime import datetime

import click
import git

from ..click_utils import CONTEXT_SETTINGS
from ..concourse import ConcourseClient
from ..github import GitHubClient
from ..utils import check_git_repo, get_repo_info


@click.command('rollback', context_settings=CONTEXT_SETTINGS)
@click.option('-t', '--tag', metavar='TAG', help='Specific tag to rollback to')
@click.option('-d', '--dry-run', is_flag=True, help='Perform a dry run without actual rollback')
@click.option('--concourse-url', help='Concourse CI API URL')
@click.option('--concourse-team', help='Concourse CI team name')
@click.option('--concourse-target', help='Concourse target name from ~/.flyrc')
@click.option('--pipeline', help='Concourse pipeline name to trigger')
@click.option('--job', default='rollback', help='Concourse job name to trigger')
@click.option('--version-file', help='Path to the file containing version information')
@click.option(
    '--version-pattern',
    help='Regex pattern to extract version (with named capture group "version")',
)
@click.option(
    '--version-branch',
    default='version',
    help='Branch to check for version information',
)
@click.pass_context
def rollback(
    ctx,
    tag,
    dry_run,
    concourse_url,
    concourse_team,
    concourse_target,
    pipeline,
    job,
    version_file,
    version_pattern,
    version_branch,
):
    """Rollback to a previous release.

    This command creates a rollback branch from the specified tag, updates version
    files (including those on separate branches if required), creates a new rollback tag,
    and optionally creates a GitHub release and triggers a Concourse pipeline.

    If --version-file is specified, that file will be updated with the rolled-back version.
    If --version-branch is specified, the version file in that branch will be updated.
    """
    if not check_git_repo():
        click.echo('Error: Current directory is not a git repository', err=True)
        sys.exit(1)

    try:
        owner, repo = get_repo_info()
        git_repo = git.Repo(os.getcwd())

        # Check for GitHub authentication - make it optional
        github_authenticated = False
        try:
            # Create GitHub client with authentication required=False
            github_client = GitHubClient(required=False)
            github_authenticated = github_client.is_authenticated

            # Only fetch releases if we're authenticated
            releases = []
            if github_authenticated:
                releases = github_client.get_releases(owner, repo, per_page=20)
        except Exception as e:
            click.echo(f'Warning: Unable to access GitHub API: {str(e)}', err=True)
            click.echo('Continuing with local rollback only.')
            releases = []
            github_authenticated = False

        # If tag is not specified, we'll need to provide options
        if not tag:
            # If authenticated with GitHub, use releases list
            if releases:
                click.echo('Available releases for rollback:')

                for idx, release in enumerate(releases, 1):
                    published_at = release.get('published_at', 'N/A')
                    if published_at != 'N/A':
                        date_obj = datetime.strptime(published_at, '%Y-%m-%dT%H:%M:%SZ')
                        formatted_date = date_obj.strftime('%Y-%m-%d %H:%M')
                    else:
                        formatted_date = 'N/A'

                    click.echo(
                        f'{idx}. {release.get("tag_name")} - '
                        f'{release.get("name")} ({formatted_date})'
                    )

                while True:
                    choice = click.prompt(
                        'Enter the number of the release to roll back to', type=int
                    )
                    if 1 <= choice <= len(releases):
                        selected_release = releases[choice - 1]
                        tag = selected_release.get('tag_name')
                        break
                    else:
                        click.echo(
                            f'Invalid choice. Please enter a number between 1 and {len(releases)}'
                        )
            else:
                # Not authenticated or no releases found, list local tags instead
                tags = sorted([t.name for t in git_repo.tags], reverse=True)
                if not tags:
                    click.echo('No tags found in the repository for rollback.')
                    sys.exit(1)

                click.echo('Available tags for rollback:')
                for idx, t in enumerate(tags, 1):
                    click.echo(f'{idx}. {t}')

                while True:
                    choice = click.prompt('Enter the number of the tag to roll back to', type=int)
                    if 1 <= choice <= len(tags):
                        tag = tags[choice - 1]
                        break
                    else:
                        click.echo(
                            f'Invalid choice. Please enter a number between 1 and {len(tags)}'
                        )

        # Validate the tag exists
        try:
            # Verify tag exists
            git_repo.tags[tag]
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

        # Find and update version in code
        # If a specific version file was provided, use it
        version_file_path = None
        pattern_used = None

        if version_file:
            version_file_path = os.path.join(git_repo.working_dir, version_file)
            if os.path.exists(version_file_path):
                click.echo(f'Using specified version file: {version_file_path}')
                if version_pattern:
                    pattern_used = version_pattern
                else:
                    pattern_used = guess_version_pattern(version_file_path)
            else:
                click.echo(f'Warning: Specified version file {version_file_path} not found')
                version_file_path = None

        # If no version file path found yet, check common locations
        if not version_file_path:
            # Try to find in common locations like __init__.py, pyproject.toml, etc.
            version_file_path, pattern_used = find_version_file(git_repo.working_dir)

        # Update the version
        changes_committed = False
        if version_file_path:
            click.echo(f'Updating version in {version_file_path} to {version}')

            # Get current version
            current_version = extract_version(version_file_path, pattern_used)
            if not current_version:
                click.echo(f'Warning: Could not extract current version from {version_file_path}')
                current_version = '0.0.0'  # Default if nothing found

            # Create version updater
            version_updater = VersionUpdater(
                file_path=version_file_path,
                pattern=pattern_used,
                old_version=current_version,
                new_version=version,
                git_repo=git_repo,
                branch=version_branch,
            )

            # Update the version (this will handle branch switching if needed)
            changes_committed = version_updater.update_version()

            # If the changes were not committed by the updater (if it wasn't on a different branch)
            if not changes_committed:
                click.echo(f'Updating version to {version} in rollback branch')
                # Path might be different if we're not on the original branch
                local_path = os.path.join(
                    git_repo.working_dir, os.path.relpath(version_file_path, git_repo.working_dir)
                )
                git_repo.git.add(local_path)
        else:
            # Fallback to updating version in __init__.py
            update_version_in_init(git_repo, version)

        # Commit changes
        commit_message = f'Rollback to {tag}'
        click.echo(f'Committing version change: {commit_message}')

        # We don't always need to add __init__.py if we've updated a different file
        # The version_updater would have already added changes if it was on a different branch
        if not version_file_path and not changes_committed:
            # Fall back to init.py if nothing else was found
            git_repo.git.add('src/voyager/__init__.py')

        # Commit all changes
        git_repo.git.commit('-m', commit_message)

        # Push the rollback branch
        click.echo('Pushing rollback branch to remote...')
        git_repo.git.push('-f', 'origin', rollback_branch)

        # Create rollback tag
        rollback_tag = f'rollback-{tag}-{datetime.now().strftime("%Y%m%d%H%M%S")}'
        click.echo(f'Creating rollback tag: {rollback_tag}')
        git_repo.create_tag(rollback_tag)
        git_repo.git.push('origin', rollback_tag)

        # Create GitHub release for the rollback (if authenticated)
        if github_authenticated:
            click.echo('Creating GitHub release for rollback...')
            rollback_message = f"""
# Rollback to {tag}

This is a rollback to the previous release {tag}.

Rolled back on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            try:
                rollback_release = github_client.create_release(
                    owner=owner,
                    repo=repo,
                    tag_name=rollback_tag,
                    name=f'Rollback to {tag}',
                    body=rollback_message,
                )
                click.echo(f'✓ GitHub rollback release created: {rollback_release.get("html_url")}')
            except Exception as e:
                click.echo(f'Warning: Could not create GitHub release: {str(e)}', err=True)
                click.echo('Continuing with local rollback only.')
        else:
            click.echo('Skipping GitHub release creation (not authenticated).')
            click.echo(
                'To create a GitHub release later, set GITHUB_TOKEN and use the GitHub '
                'web interface.'
            )

        # Trigger Concourse pipeline if requested
        # Can use either (concourse_url and concourse_team) or concourse_target
        if ((concourse_url and concourse_team) or concourse_target) and pipeline:
            click.echo('Triggering Concourse CI rollback pipeline...')

            try:
                concourse_client = ConcourseClient(
                    api_url=concourse_url, team=concourse_team, target=concourse_target
                )

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
            f"If you want to complete the rollback, merge the '{rollback_branch}' "
            f'branch to your main branch:'
        )
        click.echo('  git checkout main')
        click.echo(f'  git merge {rollback_branch}')
        click.echo('  git push origin main')

    except Exception as e:
        click.echo(f'Error during rollback: {str(e)}', err=True)
        sys.exit(1)


def find_version_file(repo_root):
    """Find a file containing version information in common locations."""
    # Define common patterns for different file types
    patterns = {
        'python_init': r'__version__\s*=\s*[\'"](?P<version>[^\'"]*)[\'"]',
        'pyproject_toml': r'version\s*=\s*[\'"](?P<version>[^\'"]*)[\'"]',
        'package_json': r'"version"\s*:\s*"(?P<version>[^"]*)"',
        'gradle': r'version\s*=\s*[\'"](?P<version>[^\'"]*)[\'"]',
        'cargo_toml': r'version\s*=\s*[\'"](?P<version>[^\'"]*)[\'"]',
        'gemspec': r'\.version\s*=\s*[\'"](?P<version>[^\'"]*)[\'"]',
        'version_txt': r'(?P<version>[\d\.]+)',
    }

    # Check for common version files
    common_files = [
        ('pyproject.toml', patterns['pyproject_toml']),
        ('package.json', patterns['package_json']),
        ('setup.py', r'version\s*=\s*[\'"](?P<version>[^\'"]*)[\'"]'),
        ('VERSION', patterns['version_txt']),
        ('version.txt', patterns['version_txt']),
        ('build.gradle', patterns['gradle']),
        ('build.gradle.kts', patterns['gradle']),
        ('Cargo.toml', patterns['cargo_toml']),
    ]

    # Check for __init__.py in src/package directories
    for root, dirs, files in os.walk(repo_root):
        if '__init__.py' in files:
            rel_path = os.path.relpath(os.path.join(root, '__init__.py'), repo_root)
            common_files.append((rel_path, patterns['python_init']))

        # Limit to top-level directories to avoid deep search
        if root != repo_root:
            dirs.clear()

    # Try each potential version file
    for file_path, pattern in common_files:
        full_path = os.path.join(repo_root, file_path)
        if os.path.exists(full_path):
            version = extract_version(full_path, pattern)
            if version:
                return full_path, pattern

    # Default to the package __init__.py if it exists
    default_init = os.path.join(repo_root, 'src', 'voyager', '__init__.py')
    if os.path.exists(default_init):
        return default_init, patterns['python_init']

    return None, None


def extract_version(file_path, pattern):
    """Extract version from a file using the given pattern."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()

        # Use the provided pattern to find the version
        match = re.search(pattern, content)
        if match and 'version' in match.groupdict():
            return match.group('version')
    except Exception:
        pass

    return None


def guess_version_pattern(file_path):
    """Guess the version pattern based on the file extension."""
    file_name = os.path.basename(file_path)
    file_ext = os.path.splitext(file_name)[1].lower()

    patterns = {
        'python_init': r'__version__\s*=\s*[\'"](?P<version>[^\'"]*)[\'"]',
        'pyproject_toml': r'version\s*=\s*[\'"](?P<version>[^\'"]*)[\'"]',
        'package_json': r'"version"\s*:\s*"(?P<version>[^"]*)"',
        'gradle': r'version\s*=\s*[\'"](?P<version>[^\'"]*)[\'"]',
        'cargo_toml': r'version\s*=\s*[\'"](?P<version>[^\'"]*)[\'"]',
        'gemspec': r'\.version\s*=\s*[\'"](?P<version>[^\'"]*)[\'"]',
        'version_txt': r'(?P<version>[\d\.]+)',
    }

    if file_name == 'pyproject.toml' or file_ext == '.toml':
        return patterns['pyproject_toml']
    elif file_name == 'package.json':
        return patterns['package_json']
    elif file_ext == '.py':
        return patterns['python_init']
    elif file_name in ('VERSION', 'version.txt') or file_ext == '.txt':
        return patterns['version_txt']
    elif file_ext == '.gradle' or file_ext == '.kts':
        return patterns['gradle']
    elif file_name == 'Cargo.toml':
        return patterns['cargo_toml']
    elif file_ext == '.gemspec':
        return patterns['gemspec']

    # Default to a generic pattern
    return r'(?P<version>[\d\.]+)'


def update_version_in_init(git_repo, version):
    """Update the version in the package __init__.py file."""
    try:
        init_file = os.path.join(git_repo.working_dir, 'src', 'voyager', '__init__.py')

        with open(init_file, 'r') as f:
            content = f.read()

        new_content = re.sub(
            r'__version__\s*=\s*[\'"]([^\'"]*)[\'"]', f"__version__ = '{version}'", content
        )

        with open(init_file, 'w') as f:
            f.write(new_content)

        click.echo(f'Updated version in {init_file}')

    except Exception as e:
        raise Exception(f'Failed to update version in code: {str(e)}') from e


class VersionUpdater:
    """Helper class to update version information in different file formats."""

    def __init__(self, file_path, pattern, old_version, new_version, git_repo=None, branch=None):
        self.file_path = file_path
        self.pattern = pattern
        self.old_version = old_version
        self.new_version = new_version
        self.git_repo = git_repo
        self.branch = branch
        self.original_branch = None

    def checkout_branch(self):
        """Checkout the target branch if specified."""
        if self.git_repo and self.branch:
            try:
                self.original_branch = self.git_repo.active_branch.name

                # Check if the branch exists
                branch_exists = False
                for ref in self.git_repo.refs:
                    if ref.name == self.branch or ref.name == f'origin/{self.branch}':
                        branch_exists = True
                        break

                if not branch_exists:
                    click.echo(
                        f"Warning: Branch '{self.branch}' does not exist, "
                        f'staying on current branch.'
                    )
                    return False

                if self.original_branch != self.branch:
                    click.echo(
                        f"Checking out branch '{self.branch}' to update version information..."
                    )
                    self.git_repo.git.checkout(self.branch)
                    return True
            except Exception as e:
                click.echo(f"Warning: Failed to checkout branch '{self.branch}': {str(e)}")
                click.echo('Staying on current branch for version update.')
        return False

    def restore_branch(self):
        """Restore the original branch if we switched branches."""
        if self.git_repo and self.original_branch and self.original_branch != self.branch:
            try:
                click.echo(f"Restoring original branch '{self.original_branch}'...")
                self.git_repo.git.checkout(self.original_branch)
            except Exception as e:
                click.echo(f'Warning: Failed to restore original branch: {str(e)}')

    def update_version(self):
        """Update the version in the file."""
        switched_branch = False
        changes_committed = False
        try:
            # Switch to the specified branch if needed
            switched_branch = self.checkout_branch()

            # Read the file content
            with open(self.file_path, 'r') as f:
                content = f.read()

            # Handle special cases based on file type
            file_name = os.path.basename(self.file_path)
            file_ext = os.path.splitext(file_name)[1].lower()

            if file_name == 'pyproject.toml' or file_ext == '.toml':
                new_content = self._update_toml(content)
            elif file_name == 'package.json':
                new_content = self._update_json(content)
            elif file_ext == '.py':
                new_content = self._update_generic(content)
            else:
                # Generic update using regex pattern
                new_content = self._update_generic(content)

            # Write the updated content back to the file
            with open(self.file_path, 'w') as f:
                f.write(new_content)

            # If we're on a different branch, commit the changes before switching back
            if switched_branch and self.git_repo:
                try:
                    # Commit the version change on the version branch
                    commit_message = f'Update version to {self.new_version} for rollback'
                    click.echo(
                        f'Committing version change on {self.branch} branch: {commit_message}'
                    )
                    self.git_repo.git.add(self.file_path)
                    self.git_repo.git.commit('-m', commit_message)
                    changes_committed = True

                    # Push the change to remote if the user confirms
                    if click.confirm(f"Push version change to remote '{self.branch}' branch?"):
                        click.echo(f"Pushing changes to remote '{self.branch}' branch...")
                        self.git_repo.git.push('origin', self.branch)
                except Exception as e:
                    click.echo(f'Warning: Failed to commit version change: {str(e)}')
                    click.echo('You may need to manually commit and push the changes.')

            return changes_committed
        except Exception as e:
            raise Exception(f'Failed to update version in {self.file_path}: {str(e)}') from e
        finally:
            # Make sure we restore the original branch if we switched
            if switched_branch:
                self.restore_branch()

    def _update_toml(self, content):
        """Update version in TOML files with proper formatting."""
        # For simplicity, use regex replacement but preserve formatting
        return re.sub(
            self.pattern, lambda m: m.group().replace(self.old_version, self.new_version), content
        )

    def _update_json(self, content):
        """Update version in JSON files with proper formatting."""
        # For simplicity, use regex replacement but preserve formatting
        return re.sub(
            self.pattern, lambda m: m.group().replace(self.old_version, self.new_version), content
        )

    def _update_generic(self, content):
        """Update version using a generic pattern replacement."""
        return re.sub(
            self.pattern, lambda m: m.group().replace(self.old_version, self.new_version), content
        )

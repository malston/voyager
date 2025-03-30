#!/usr/bin/env python3

import os
import re
import sys
from datetime import datetime

import click
import git
import semver

from ..click_utils import CONTEXT_SETTINGS
from ..concourse import ConcourseClient
from ..github import GitHubClient
from ..utils import check_git_repo, get_repo_info


@click.command('release', context_settings=CONTEXT_SETTINGS)
@click.option(
    '-t',
    '--type',
    type=click.Choice(['major', 'minor', 'patch']),
    default='patch',
    help='Release type (major, minor, patch)',
)
@click.option('-m', '--message', metavar='MSG', help='Release message')
@click.option(
    '--release-branch',
    '--target',
    '-r',
    default='main',
    metavar='BRANCH',
    help='Target branch to create the release from (defaults to main)',
)
@click.option(
    '--working-branch',
    '-w',
    metavar='BRANCH',
    help='Source branch containing your changes (defaults to current branch)',
)
@click.option(
    '-d', '--dry-run', is_flag=True, help='Perform a dry run without creating actual release'
)
@click.option('--concourse-url', help='Concourse CI API URL')
@click.option('--concourse-team', help='Concourse CI team name')
@click.option('--pipeline', help='Concourse pipeline name to trigger')
@click.option('--job', default='build-and-release', help='Concourse job name to trigger')
@click.option('--version-file', help='Path to the file containing version information')
@click.option(
    '--version-pattern',
    help='Regex pattern to extract version (with named capture group "version")',
)
@click.option(
    '--version-branch',
    default='version',
    help='Branch to check for version information (defaults to "version")',
)
@click.option(
    '--merge-strategy',
    '-s',
    type=click.Choice(['checkout', 'rebase', 'merge', 'merge-squash']),
    default='rebase',
    help="""Strategy to use when target and source branches differ:
    checkout: Simply switch to the target branch (abandons working branch changes)
    rebase: (default) Apply source branch commits on top of the target branch
    merge: Create a merge commit to bring source changes into target (--no-ff)
    merge-squash: Squash all source changes into a single commit on target""",
)
@click.pass_context
def create_release(
    ctx,
    type,
    message,
    release_branch,
    working_branch,
    dry_run,
    concourse_url,
    concourse_team,
    pipeline,
    job,
    version_file,
    version_pattern,
    version_branch,
    merge_strategy,
):
    """Create a new release from the current branch."""
    if not check_git_repo():
        click.echo('Error: Current directory is not a git repository', err=True)
        sys.exit(1)

    try:
        owner, repo = get_repo_info()
        quiet = ctx.obj.get('quiet', False) if ctx.obj else False
        if not quiet:
            click.echo(f'Preparing release for {owner}/{repo}...')

        # Get the git repo
        git_repo = git.Repo(os.getcwd())

        # Get the current branch
        current_branch = git_repo.active_branch.name

        # If no working branch specified, use current branch
        if not working_branch:
            working_branch = current_branch
            click.echo(f"Using current branch '{working_branch}' as the source of changes")

        # Check if release branch exists
        release_branch_exists = False
        for ref in git_repo.refs:
            if ref.name == release_branch or ref.name == f'origin/{release_branch}':
                release_branch_exists = True
                break

        if not release_branch_exists:
            click.echo(f"Error: Release branch '{release_branch}' does not exist")
            click.echo('Available branches:')
            for ref in git_repo.refs:
                if not ref.name.startswith('origin/'):
                    click.echo(f'  {ref.name}')
            sys.exit(1)

        # Check if working branch exists (if different from current)
        if working_branch != current_branch:
            working_branch_exists = False
            for ref in git_repo.refs:
                if ref.name == working_branch or ref.name == f'origin/{working_branch}':
                    working_branch_exists = True
                    break

            if not working_branch_exists:
                click.echo(f"Error: Working branch '{working_branch}' does not exist")
                click.echo('Available branches:')
                for ref in git_repo.refs:
                    if not ref.name.startswith('origin/'):
                        click.echo(f'  {ref.name}')
                sys.exit(1)

            # Switch to the specified working branch
            click.echo(f"Switching to working branch '{working_branch}'...")
            try:
                git_repo.git.checkout(working_branch)
                click.echo(f"Switched to branch '{working_branch}'")
            except git.GitCommandError as e:
                click.echo(f"Error switching to branch '{working_branch}': {str(e)}")
                if not click.confirm(f"Continue release from current branch '{current_branch}'?"):
                    click.echo('Release canceled.')
                    sys.exit(0)
                working_branch = current_branch

        # If release and working branch are different, handle merge strategy
        if working_branch != release_branch:
            msg = (
                f"Release branch '{release_branch}' is different from "
                f"working branch '{working_branch}'."
            )
            click.echo(msg)

            # Use provided merge strategy or prompt if not specified
            if not merge_strategy:
                merge_strategy = click.prompt(
                    'Choose merge strategy',
                    type=click.Choice(['checkout', 'rebase', 'merge', 'merge-squash']),
                    default='rebase',
                )
            else:
                click.echo(f"Using specified merge strategy: '{merge_strategy}'.")

            try:
                if merge_strategy == 'checkout':
                    # Warn the user that checkout won't merge their changes
                    if working_branch != current_branch:
                        click.echo(
                            "⚠️ WARNING: Using 'checkout' strategy with a specified working branch"
                        )
                        click.echo(
                            f"Your commits from '{working_branch}' will NOT be merged into '{release_branch}'"
                        )
                        if not click.confirm('Continue with checkout strategy?', default=False):
                            click.echo('Release canceled.')
                            sys.exit(0)

                    # Simple checkout
                    click.echo(f"Checking out branch '{release_branch}' for release...")
                    git_repo.git.checkout(release_branch)
                    click.echo(f"Switched to branch '{release_branch}'")
                elif merge_strategy == 'rebase':
                    # Rebase the changes from the working branch onto the target branch
                    msg = f"Rebasing changes from '{working_branch}' onto '{release_branch}'..."
                    click.echo(msg)
                    # First ensure we have latest of both branches
                    git_repo.git.fetch('origin', release_branch)
                    git_repo.git.fetch('origin', working_branch)

                    # First, create a backup of the current branch in case something goes wrong
                    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                    backup_branch = f'backup-{working_branch}-{timestamp}'
                    click.echo(f"Creating backup branch '{backup_branch}' of your current work")
                    git_repo.git.checkout('-b', backup_branch)
                    git_repo.git.checkout(working_branch)

                    # Now check out the target branch and update it
                    click.echo(f"Checking out release branch '{release_branch}'")
                    git_repo.git.checkout(release_branch)

                    # Pull latest from remote to make sure we're up to date
                    try:
                        git_repo.git.pull('origin', release_branch)
                    except git.GitCommandError:
                        msg = (
                            f"Could not pull latest changes for '{release_branch}', "
                            f'continuing with local version'
                        )
                    click.echo(msg)

                    # Rebase the target branch onto the working branch
                    # This takes commits from the working branch and applies them
                    # on top of the release branch
                    git_repo.git.rebase(backup_branch)
                    msg = (
                        f"Successfully rebased changes from '{working_branch}' "
                        f"onto '{release_branch}'"
                    )
                    click.echo(msg)

                    # Clean up the backup branch if the rebase was successful
                    git_repo.git.branch('-D', backup_branch)
                    click.echo(f"Removed backup branch '{backup_branch}'")

                elif merge_strategy == 'merge':
                    # Merge changes from working branch into the target branch
                    click.echo(
                        f"Merging changes from '{working_branch}' into '{release_branch}'..."
                    )
                    # First ensure we have latest of both branches
                    git_repo.git.fetch('origin', release_branch)
                    git_repo.git.fetch('origin', working_branch)

                    # First, create a backup of the current branch in case something goes wrong
                    backup_branch = (
                        f'backup-{working_branch}-{datetime.now().strftime("%Y%m%d%H%M%S")}'
                    )
                    click.echo(f"Creating backup branch '{backup_branch}' of your current work")
                    git_repo.git.checkout('-b', backup_branch)
                    git_repo.git.checkout(working_branch)

                    # Now check out the target branch and update it
                    click.echo(f"Checking out release branch '{release_branch}'")
                    git_repo.git.checkout(release_branch)

                    # Pull latest from remote to make sure we're up to date
                    try:
                        git_repo.git.pull('origin', release_branch)
                    except git.GitCommandError:
                        msg = (
                            f"Could not pull latest changes for '{release_branch}', "
                            f'continuing with local version'
                        )
                    click.echo(msg)

                    # Merge the working branch into the release branch
                    git_repo.git.merge(working_branch, '--no-ff')
                    msg = (
                        f"Successfully merged changes from '{working_branch}' "
                        f"into '{release_branch}'"
                    )
                    click.echo(msg)

                    # Clean up the backup branch if the merge was successful
                    git_repo.git.branch('-D', backup_branch)
                    click.echo(f"Removed backup branch '{backup_branch}'")

                elif merge_strategy == 'merge-squash':
                    # Squash merge changes from working branch into the target branch
                    click.echo(
                        f"Squash merging changes from '{working_branch}' into '{release_branch}'..."
                    )
                    # First ensure we have latest of both branches
                    git_repo.git.fetch('origin', release_branch)
                    git_repo.git.fetch('origin', working_branch)

                    # First, create a backup of the current branch in case something goes wrong
                    backup_branch = (
                        f'backup-{working_branch}-{datetime.now().strftime("%Y%m%d%H%M%S")}'
                    )
                    click.echo(f"Creating backup branch '{backup_branch}' of your current work")
                    git_repo.git.checkout('-b', backup_branch)
                    git_repo.git.checkout(working_branch)

                    # Now check out the target branch and update it
                    click.echo(f"Checking out release branch '{release_branch}'")
                    git_repo.git.checkout(release_branch)

                    # Pull latest from remote to make sure we're up to date
                    try:
                        git_repo.git.pull('origin', release_branch)
                    except git.GitCommandError:
                        msg = (
                            f"Could not pull latest changes for '{release_branch}', "
                            f'continuing with local version'
                        )
                    click.echo(msg)

                    # Squash merge the working branch into the release branch
                    git_repo.git.merge(working_branch, '--squash')
                    commit_msg = (
                        f"Squashed merge of '{working_branch}' into '{release_branch}' for release"
                    )
                    git_repo.git.commit('-m', commit_msg)
                    msg = (
                        f"Successfully squash merged changes from '{working_branch}' "
                        f"into '{release_branch}'"
                    )
                    click.echo(msg)

                    # Clean up the backup branch if the squash merge was successful
                    git_repo.git.branch('-D', backup_branch)
                    click.echo(f"Removed backup branch '{backup_branch}'")

                # Record the branch we're on after merge strategy
                current_branch = git_repo.active_branch.name
                click.echo(f"Proceeding with release from branch '{current_branch}'")
            except git.GitCommandError as e:
                click.echo(f"Error with merge strategy '{merge_strategy}': {str(e)}")
                if not click.confirm(f"Continue release from current branch '{working_branch}'?"):
                    click.echo('Release canceled.')
                    sys.exit(0)

        # Determine current version
        version_finder = VersionFinder(git_repo, version_file, version_pattern, version_branch)
        current_version, version_file_path, pattern_used = version_finder.get_current_version()

        if current_version:
            click.echo(f'Current version: {current_version}')
            click.echo(f'Version found in: {version_file_path}')
        else:
            click.echo('No version information found in the repository.')
            if click.confirm('Would you like to start with version 0.1.0?'):
                current_version = '0.1.0'
                if not version_file_path:
                    # Prompt for version file if not found
                    default_file = 'pyproject.toml'
                    if os.path.exists(default_file):
                        version_file_path = default_file
                    else:
                        version_file_path = click.prompt(
                            'Enter the path to the file where version should be stored',
                            default='__init__.py',
                        )
            else:
                current_version = click.prompt('Enter the current version', default='0.1.0')

        # Calculate new version
        if current_version:
            try:
                if type == 'major':
                    new_version = str(semver.VersionInfo.parse(current_version).bump_major())
                elif type == 'minor':
                    new_version = str(semver.VersionInfo.parse(current_version).bump_minor())
                else:  # patch
                    new_version = str(semver.VersionInfo.parse(current_version).bump_patch())
            except ValueError:
                click.echo(f'Warning: Version {current_version} is not a valid semver format.')
                if click.confirm('Would you like to use 0.1.0 as a starting version?'):
                    new_version = '0.1.0'
                else:
                    new_version = click.prompt('Enter the new version')
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
            if version_file_path:
                click.echo(f'Would update version in: {version_file_path}')
            return

        # Update version in code if version file path was found
        if version_file_path:
            version_updater = VersionUpdater(
                file_path=version_file_path,
                pattern=pattern_used,
                old_version=current_version,
                new_version=new_version,
                git_repo=git_repo,
                branch=version_branch,
            )
            # The update_version method will return True if it committed the changes
            changes_committed = version_updater.update_version()
            click.echo(f'Updated version in {version_file_path}')

            # Skip committing if the version updater already committed the changes
            # (which happens when updating on a different branch)
            if not changes_committed:
                # Commit changes
                commit_message = f'Bump version to {new_version}'
                click.echo(f'Committing version change: {commit_message}')
                git_repo.git.add(version_file_path)
                git_repo.git.commit('-m', commit_message)

        # Create tag
        tag_name = f'v{new_version}'
        click.echo(f'Creating tag: {tag_name}')
        git_repo.create_tag(tag_name)

        # Push changes and tag
        click.echo('Pushing changes and tag to remote...')
        # Get current branch again as it might have changed
        current_branch = git_repo.active_branch.name
        git_repo.git.push('origin', current_branch)
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

        # Ask the user if they want to switch back to the original branch
        if working_branch != git_repo.active_branch.name:
            if click.confirm(f"Switch back to working branch '{working_branch}'?"):
                try:
                    git_repo.git.checkout(working_branch)
                    click.echo(f"Switched back to branch '{working_branch}'")
                except git.GitCommandError as e:
                    click.echo(f"Error switching back to branch '{working_branch}': {str(e)}")

    except Exception as e:
        click.echo(f'Error creating release: {str(e)}', err=True)

        # Always try to restore the working branch in case of error
        if 'working_branch' in locals() and working_branch != git_repo.active_branch.name:
            try:
                git_repo.git.checkout(working_branch)
                click.echo(f"Restored working branch '{working_branch}' after error")
            except Exception:
                pass  # Don't add more errors to the output

        sys.exit(1)


class VersionFinder:
    """Helper class to find version information in different project structures."""

    def __init__(self, git_repo, version_file=None, version_pattern=None, branch=None):
        self.git_repo = git_repo
        self.repo_root = git_repo.working_dir
        self.custom_version_file = version_file
        self.custom_version_pattern = version_pattern
        self.branch = branch
        self.original_branch = None

        # Default patterns for version detection
        self.patterns = {
            'python_init': r'__version__\s*=\s*[\'"](?P<version>[^\'"]*)[\'"]',
            'pyproject_toml': r'version\s*=\s*[\'"](?P<version>[^\'"]*)[\'"]',
            'package_json': r'"version"\s*:\s*"(?P<version>[^"]*)"',
            'gradle': r'version\s*=\s*[\'"](?P<version>[^\'"]*)[\'"]',
            'cargo_toml': r'version\s*=\s*[\'"](?P<version>[^\'"]*)[\'"]',
            'gemspec': r'\.version\s*=\s*[\'"](?P<version>[^\'"]*)[\'"]',
            'version_txt': r'(?P<version>[\d\.]+)',
        }

    def checkout_branch(self):
        """Checkout the target branch if specified."""
        if self.branch:
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
                        f"Checking out branch '{self.branch}' to find version information..."
                    )
                    self.git_repo.git.checkout(self.branch)
                    return True
            except Exception as e:
                click.echo(f"Warning: Failed to checkout branch '{self.branch}': {str(e)}")
                click.echo('Staying on current branch for version detection.')
        return False

    def restore_branch(self):
        """Restore the original branch if we switched branches."""
        if self.original_branch and self.original_branch != self.branch:
            try:
                click.echo(f"Restoring original branch '{self.original_branch}'...")
                self.git_repo.git.checkout(self.original_branch)
            except Exception as e:
                click.echo(f'Warning: Failed to restore original branch: {str(e)}')

    def get_current_version(self):
        """Find the current version in the repository."""
        switched_branch = False
        try:
            # Switch to the specified branch if needed
            switched_branch = self.checkout_branch()

            # If a specific version file is provided, check it first
            if self.custom_version_file:
                version_file_path = os.path.join(self.repo_root, self.custom_version_file)
                if os.path.exists(version_file_path):
                    pattern = self.custom_version_pattern or self._guess_pattern(version_file_path)
                    version = self._extract_version(version_file_path, pattern)
                    if version:
                        return version, version_file_path, pattern

            # Check common version file locations
            version_locations = self._get_common_version_locations()

            for file_path, pattern in version_locations:
                full_path = os.path.join(self.repo_root, file_path)
                if os.path.exists(full_path):
                    version = self._extract_version(full_path, pattern)
                    if version:
                        return version, full_path, pattern

            # Try to find the latest tag
            try:
                tags = sorted(self.git_repo.tags, key=lambda t: t.commit.committed_datetime)
                if tags:
                    latest_tag = str(tags[-1])
                    if latest_tag.startswith('v'):
                        return latest_tag[1:], None, None  # version from tag, no file
                    return latest_tag, None, None
            except Exception:
                pass

            # If no version is found, return None
            return None, None, None

        finally:
            # Make sure we restore the original branch if we switched
            if switched_branch:
                self.restore_branch()

    def _get_common_version_locations(self):
        """Return a list of tuples with (file_path, pattern) for common version file locations."""
        locations = []

        # Try to find the package name if it's a Python project
        package_name = self._guess_package_name()

        # Add common version file locations
        if package_name:
            locations.append((f'{package_name}/__init__.py', self.patterns['python_init']))

        # Common version file locations by language/framework
        common_locations = [
            ('pyproject.toml', self.patterns['pyproject_toml']),
            ('setup.py', r'version\s*=\s*[\'"](?P<version>[^\'"]*)[\'"]'),
            ('package.json', self.patterns['package_json']),
            ('VERSION', self.patterns['version_txt']),
            ('version.txt', self.patterns['version_txt']),
            ('build.gradle', self.patterns['gradle']),
            ('build.gradle.kts', self.patterns['gradle']),
            ('Cargo.toml', self.patterns['cargo_toml']),
            ('*.gemspec', self.patterns['gemspec']),
        ]

        # Add all common locations
        locations.extend(common_locations)

        # Check for any __init__.py files in the root directories
        for root, dirs, files in os.walk(self.repo_root):
            if '__init__.py' in files and root != self.repo_root:
                rel_path = os.path.relpath(os.path.join(root, '__init__.py'), self.repo_root)
                locations.append((rel_path, self.patterns['python_init']))

            # Only look at the top level directories
            if root != self.repo_root:
                dirs.clear()

        return locations

    def _guess_package_name(self):
        """Try to guess the Python package name."""
        # Check for standard Python project structure
        setup_py = os.path.join(self.repo_root, 'setup.py')
        if os.path.exists(setup_py):
            try:
                with open(setup_py, 'r') as f:
                    content = f.read()
                    name_match = re.search(r'name\s*=\s*[\'"]([^\'"]*)[\'"]', content)
                    if name_match:
                        return name_match.group(1)
            except Exception:
                pass

        # Check pyproject.toml
        pyproject_toml = os.path.join(self.repo_root, 'pyproject.toml')
        if os.path.exists(pyproject_toml):
            try:
                with open(pyproject_toml, 'r') as f:
                    content = f.read()
                    name_match = re.search(r'name\s*=\s*[\'"]([^\'"]*)[\'"]', content)
                    if name_match:
                        return name_match.group(1)
            except Exception:
                pass

        # Look for directories that might be Python packages
        for item in os.listdir(self.repo_root):
            if os.path.isdir(os.path.join(self.repo_root, item)):
                if os.path.exists(os.path.join(self.repo_root, item, '__init__.py')):
                    return item

        return None

    def _guess_pattern(self, file_path):
        """Guess the version pattern based on the file extension."""
        file_name = os.path.basename(file_path)
        file_ext = os.path.splitext(file_name)[1].lower()

        if file_name == 'pyproject.toml' or file_ext == '.toml':
            return self.patterns['pyproject_toml']
        elif file_name == 'package.json':
            return self.patterns['package_json']
        elif file_ext == '.py':
            return self.patterns['python_init']
        elif file_name in ('VERSION', 'version.txt') or file_ext == '.txt':
            return self.patterns['version_txt']
        elif file_ext == '.gradle' or file_ext == '.kts':
            return self.patterns['gradle']
        elif file_name == 'Cargo.toml':
            return self.patterns['cargo_toml']
        elif file_ext == '.gemspec':
            return self.patterns['gemspec']

        # Default to a generic pattern
        return r'(?P<version>[\d\.]+)'

    def _extract_version(self, file_path, pattern):
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
                    commit_message = f'Bump version to {self.new_version}'
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

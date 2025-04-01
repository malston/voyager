#!/usr/bin/env python3

import os
import subprocess
from typing import List, Optional


class GitHelper:
    """Client for Git operations."""

    # ANSI color codes
    GREEN = '\033[0;32m'
    CYAN = '\033[0;36m'
    RED = '\033[0;31m'
    YELLOW = '\033[0;33m'
    NOCOLOR = '\033[0m'

    def info(self, message: str) -> None:
        """Print info message in cyan color."""
        print(f'{self.CYAN}{message}{self.NOCOLOR}')

    def warn(self, message: str) -> None:
        """Print warning message in yellow color."""
        print(f'{self.YELLOW}{message}{self.NOCOLOR}')

    def error(self, message: str) -> None:
        """Print error message in red color."""
        print(f'{self.RED}{message}{self.NOCOLOR}')

    def completed(self, message: str) -> None:
        """Print completed message in green color."""
        print(f'{self.GREEN}{message}{self.NOCOLOR}')

    def get_latest_release_tag(self, cwd: Optional[str] = None) -> str:
        """Get the latest release tag from git."""
        try:
            # Pull all branches and tags
            subprocess.run(['git', 'pull', '-q', '--all'], check=True, cwd=cwd)

            # Get latest tag
            result = subprocess.run(
                ['git', 'describe', '--tags', '$(git rev-list --tags --max-count=1)'],
                check=True,
                shell=True,
                text=True,
                capture_output=True,
                cwd=cwd,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as err:
            self.error('No release tags found. Make sure to fly the release pipeline.')
            raise RuntimeError('No release tags found') from err

    def get_latest_release(self, cwd: Optional[str] = None) -> str:
        """Get the latest release version (without release-v prefix)."""
        tag = self.get_latest_release_tag(cwd)
        # Extract version number from release-v format
        if 'release-v' in tag:
            return tag.split('release-v')[-1]
        return tag

    def get_params_release_tags(self, params_repo: str) -> List[str]:
        """Get the release tags from the params repository."""
        try:
            git_dir = os.path.expanduser(f'~/git/{params_repo}')
            if not os.path.exists(git_dir):
                self.error(f'Params repository not found at {git_dir}')
                return []

            result = subprocess.run(
                ['git', 'tag', '-l'], check=True, text=True, capture_output=True, cwd=git_dir
            )
            return result.stdout.strip().split('\n')
        except subprocess.CalledProcessError as e:
            self.error(f'Failed to get params release tags: {e}')
            return []

    def validate_params_release_tag(self, release_tag: str, params_repo: str = 'params') -> bool:
        """Validate if the release tag exists in the params repository."""
        params_tags = self.get_params_release_tags(params_repo)
        return release_tag in params_tags

    def print_valid_params_release_tags(self, repo: str, params_repo: str = 'params') -> None:
        """Print all valid release tags for a repository in the params repo."""
        params_tags = self.get_params_release_tags(params_repo)

        # Filter tags that start with the repo name
        for tag in params_tags:
            if tag.startswith(repo):
                # Extract the version from the tag
                version = tag.split(f'{repo}-', 1)[-1] if f'{repo}-' in tag else tag
                self.info(f'> {version}')

    def update_git_release_tag(
        self,
        owner: str,
        repo: str,
        params_repo: str = 'params',
    ) -> bool:
        """Update git release tags in the params repository."""

        try:
            # Change to the repo's ci directory
            repo_ci_dir = os.path.expanduser(f'~/git/{repo}/ci')
            if not os.path.exists(repo_ci_dir):
                self.error(f'Repository CI directory not found at {repo_ci_dir}')
                return False

            # Pull latest changes
            subprocess.run(['git', 'pull', '-q'], check=True, cwd=repo_ci_dir)

            # Remove owner from repo name if needed
            repo_name = repo.split(f'-{owner}')[0] if f'-{owner}' in repo else repo

            # Get last two release tags
            result = subprocess.run(
                'git tag -l | grep release-v | sort -V | tail -2 | head -1',
                check=True,
                shell=True,
                text=True,
                capture_output=True,
                cwd=repo_ci_dir,
            )
            last_release = result.stdout.strip()
            last_version = last_release.split('release-v')[-1] if last_release else ''

            result = subprocess.run(
                'git tag -l | grep release-v | sort -V | tail -1',
                check=True,
                shell=True,
                text=True,
                capture_output=True,
                cwd=repo_ci_dir,
            )
            current_release = result.stdout.strip()
            current_version = current_release.split('release-v')[-1] if current_release else ''

            if not last_version or not current_version:
                self.error('Could not determine release versions')
                return False

            # Print info about the update
            self.info(
                f'Updating the params for the tkgi-{repo_name} pipeline '
                f'from {last_version} to {current_version}'
            )

            # Interactive confirmation
            user_input = input('Do you want to continue? (y/N): ')
            if not user_input.lower().startswith('y'):
                return False

            # Change to params repo
            params_dir = os.path.expanduser(f'~/git/{params_repo}')
            if not os.path.exists(params_dir):
                self.error(f'Params repository not found at {params_dir}')
                return False

            # Check for uncommitted changes
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                check=True,
                text=True,
                capture_output=True,
                cwd=params_dir,
            )

            if result.stdout.strip():
                input('Please commit or stash your changes to params, then hit return to continue')

                # Check again
                result = subprocess.run(
                    ['git', 'status', '--porcelain'],
                    check=True,
                    text=True,
                    capture_output=True,
                    cwd=params_dir,
                )

                if result.stdout.strip():
                    self.error(
                        'You must commit or stash your changes to params in order to continue'
                    )
                    return False

            # Pull latest changes
            subprocess.run(['git', 'pull', '-q'], check=True, cwd=params_dir)

            # Format versions
            from_version = f'v{last_version}'
            to_version = f'v{current_version}'

            # Update git_release_tag values
            find_cmd = (
                f'find {params_dir} -type f \\( -name "*-{repo_name}.yml" -o '
                f'-name "*.{repo_name}.yaml" \\) -exec grep -l '
                f'"git_release_tag: release-{from_version}" {{}} \\;'
            )

            result = subprocess.run(
                find_cmd, check=True, shell=True, text=True, capture_output=True
            )

            files_to_update = result.stdout.strip().split('\n')

            for file_path in files_to_update:
                if not file_path:
                    continue

                sed_cmd = (
                    f'sed -i "s/git_release_tag: release-{from_version}/'
                    f'git_release_tag: release-{to_version}/g" {file_path}'
                )

                subprocess.run(sed_cmd, check=True, shell=True)

            # Show changes
            subprocess.run(['git', 'status'], check=True, cwd=params_dir)
            subprocess.run(['git', 'diff'], check=True, cwd=params_dir)

            # Confirm changes
            user_input = input('Do you want to continue with these commits? (y/n): ')
            if not user_input.lower().startswith('y'):
                subprocess.run(['git', 'checkout', '.'], check=True, cwd=params_dir)
                return False

            # Commit changes to a branch
            branch_name = f'{repo_name}-release-{to_version}'
            subprocess.run(['git', 'checkout', '-b', branch_name], check=True, cwd=params_dir)
            subprocess.run(['git', 'add', '.'], check=True, cwd=params_dir)

            commit_msg = (
                f'Update git_release_tag from release-{from_version} '
                f'to release-{to_version}\n\nNOTICKET'
            )

            subprocess.run(['git', 'commit', '-m', commit_msg], check=True, cwd=params_dir)

            # Merge into master
            subprocess.run(['git', 'checkout', 'master'], check=True, cwd=params_dir)
            subprocess.run(['git', 'pull', 'origin', 'master'], check=True, cwd=params_dir)
            subprocess.run(['git', 'rebase', branch_name], check=True, cwd=params_dir)
            subprocess.run(['git', 'push', 'origin', 'master'], check=True, cwd=params_dir)
            subprocess.run(['git', 'branch', '-D', branch_name], check=True, cwd=params_dir)

            # Create and push tag
            tag_cmd = [
                'git',
                'tag',
                '-a',
                f'{repo_name}-release-{to_version}',
                '-m',
                f'Version {repo_name}-release-{to_version}',
            ]
            subprocess.run(tag_cmd, check=True, cwd=params_dir)

            subprocess.run(
                ['git', 'push', 'origin', f'{repo_name}-release-{to_version}'],
                check=True,
                cwd=params_dir,
            )

            return True

        except subprocess.CalledProcessError as e:
            self.error(f'Error updating git release tag: {e}')
            return False
        except Exception as e:
            self.error(f'Unexpected error during update: {e}')
            return False

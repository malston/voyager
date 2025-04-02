#!/usr/bin/env python3

import os
import subprocess
import re
from typing import List, Optional
from typing import Tuple

import git


class GitHelper:
    """Helper class for git operations used in release pipeline scripts."""

    def __init__(self, repo_dir: Optional[str] = None, repo: Optional[str] = None):
        self.home = os.path.expanduser("~")
        self.repo = repo
        self.repo_dir = repo_dir if repo_dir else os.path.join(self.home, "git", self.repo)

    def info(self, message: str) -> None:
        """Print an info message."""
        print(f"\033[0;36m{message}\033[0m")

    def error(self, message: str) -> None:
        """Print an error message."""
        print(f"\033[0;31m{message}\033[0m")

    def warn(self, message: str) -> None:
        """Print a warning message."""
        print(f"\033[0;33m{message}\033[0m")

    def success(self, message: str) -> None:
        """Print a success message."""
        print(f"\033[0;32m{message}\033[0m")

    def get_repo_info(self, repo: Optional[str] = None) -> Tuple[str, str]:
        """Extract owner and repo name from git remote URL."""
        repo_dir = self.repo_dir if repo is None else os.path.join(self.home, "git", repo)
        try:
            repo = git.Repo(repo_dir)
            for remote in repo.remotes:
                if remote.name == "origin":
                    url = next(remote.urls)
                    # Handle SSH or HTTPS URL formats
                    match = re.search(r"github\.com[:/]([^/]+)/([^/.]+)", url)
                    if match:
                        return match.group(1), match.group(2)

            raise ValueError("Not a GitHub repository or missing origin remote")
        except (git.InvalidGitRepositoryError, git.NoSuchPathError) as err:
            raise ValueError("Current directory is not a git repository") from err

    def check_git_repo(self, repo: Optional[str] = None) -> bool:
        """Check if repo is a git repository."""
        repo_dir = self.repo_dir if repo is None else os.path.join(self.home, "git", repo)
        try:
            git.Repo(repo_dir)
            return True
        except (git.InvalidGitRepositoryError, git.NoSuchPathError):
            return False

    def pull_all(self, repo: Optional[str] = None) -> None:
        """Pull all changes from all remotes."""
        repo_dir = self.repo_dir if repo is None else os.path.join(self.home, "git", repo)
        try:
            subprocess.run(["git", "pull", "--all", "-q"], cwd=repo_dir, check=True)
        except subprocess.CalledProcessError as e:
            self.error(f"Failed to pull changes: {e}")

    def get_current_branch(self, repo: Optional[str] = None) -> str:
        """Get the current branch name."""
        repo_dir = self.repo_dir if repo is None else os.path.join(self.home, "git", repo)
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
                cwd=repo_dir,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            self.error(f"Failed to get current branch: {e}")
            return ""

    def get_tags(self, repo: Optional[str] = None) -> List[str]:
        """Get all git tags."""
        repo_dir = self.repo_dir if repo is None else os.path.join(self.home, "git", repo)
        try:
            result = subprocess.run(
                ["git", "tag", "-l"], capture_output=True, text=True, check=True, cwd=repo_dir
            )
            return result.stdout.strip().split("\n")
        except subprocess.CalledProcessError as e:
            self.error(f"Failed to get tags: {e}")
            return []

    def delete_tag(self, tag: str, repo: Optional[str] = None) -> bool:
        """Delete a git tag locally and remotely."""
        repo_dir = self.repo_dir if repo is None else os.path.join(self.home, "git", repo)
        try:
            subprocess.run(["git", "tag", "--delete", tag], cwd=repo_dir, check=True)
            subprocess.run(["git", "push", "--delete", "origin", tag], cwd=repo_dir, check=True)
            return True
        except subprocess.CalledProcessError as e:
            self.error(f"Failed to delete tag: {e}")
            return False

    def has_uncommitted_changes(self, repo: Optional[str] = None) -> bool:
        """Check if there are any uncommitted changes."""
        repo_dir = self.repo_dir if repo is None else os.path.join(self.home, "git", repo)
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=True,
                cwd=repo_dir,
            )
            return bool(result.stdout.strip())
        except subprocess.CalledProcessError as e:
            self.error(f"Failed to check git status: {e}")
            return True

    def reset_changes(self, repo: Optional[str] = None) -> None:
        """Reset all changes in the working directory."""
        repo_dir = self.repo_dir if repo is None else os.path.join(self.home, "git", repo)
        try:
            subprocess.run(["git", "reset", "--hard"], cwd=repo_dir, check=True)
        except subprocess.CalledProcessError as e:
            self.error(f"Failed to reset changes: {e}")

    def update_release_tag_in_params(
        self, params_repo: str, repo: str, from_version: str, to_version: str
    ) -> None:
        """Update the release tag in params files."""
        params_dir = os.path.join(self.home, "git", params_repo)
        try:
            # Find and update files
            for root, _, files in os.walk(params_dir):
                for file in files:
                    if file.endswith(f"-{repo}.yml") or file.endswith(f".{repo}.yaml"):
                        file_path = os.path.join(root, file)
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()
                        if f"git_release_tag: release-{from_version}" in content:
                            new_content = content.replace(
                                f"git_release_tag: release-{from_version}",
                                f"git_release_tag: release-{to_version}",
                            )
                            with open(file_path, "w", encoding="utf-8") as f:
                                f.write(new_content)
        except (IOError, OSError, PermissionError) as e:
            self.error(f"Failed to update release tag in params: {e}")

    def create_and_merge_branch(self, repo: str, branch_name: str, commit_message: str) -> bool:
        """Create a new branch, commit changes, and merge it into master."""
        repo_dir = os.path.join(self.home, "git", repo)
        try:
            # Create and switch to new branch
            subprocess.run(["git", "checkout", "-b", branch_name], cwd=repo_dir, check=True)

            # Add and commit changes
            subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
            subprocess.run(["git", "commit", "-m", commit_message], cwd=repo_dir, check=True)

            # Switch to master and merge
            subprocess.run(["git", "checkout", "master"], cwd=repo_dir, check=True)
            subprocess.run(["git", "pull", "origin", "master"], cwd=repo_dir, check=True)
            subprocess.run(["git", "rebase", branch_name], cwd=repo_dir, check=True)
            subprocess.run(["git", "push", "origin", "master"], cwd=repo_dir, check=True)

            # Clean up branch
            subprocess.run(["git", "branch", "-D", branch_name], cwd=repo_dir, check=True)
            return True
        except subprocess.CalledProcessError as e:
            self.error(f"Failed to create and merge branch: {e}")
            return False

    def create_and_push_tag(self, repo: str, tag_name: str, tag_message: str) -> bool:
        """Create and push a git tag."""
        repo_dir = os.path.join(self.home, "git", repo)
        try:
            subprocess.run(
                ["git", "tag", "-a", tag_name, "-m", tag_message], cwd=repo_dir, check=True
            )
            subprocess.run(["git", "push", "origin", tag_name], cwd=repo_dir, check=True)
            return True
        except subprocess.CalledProcessError as e:
            self.error(f"Failed to create and push tag: {e}")
            return False

    def confirm(self, message: str) -> bool:
        """Ask for user confirmation."""
        response = input(f"{message} (y/N): ")
        return response.lower().startswith("y")

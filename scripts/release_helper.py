#!/usr/bin/env python3

from typing import List, Union, Optional
from pathlib import Path
import os
import sys
import subprocess
import argparse
import requests
from git_helper import GitHelper
from voyager.github import GitHubClient


class ReleaseHelper:
    """Helper class for managing releases.

    This class provides functionality for managing releases, including getting release tags,
    validating release parameters, and interacting with Git repositories.

    Attributes:
        repo (str): The name of the main repository
        owner (str): The owner/organization of the repository (default: "Utilities-tkgieng")
        params_repo (str): The name of the params repository (default: "params")
        git_helper (GitHelper): Helper instance for Git operations
        github_client (GitHubClient): Client for GitHub API interactions
        home (str): User's home directory path
        repo_dir (str): Full path to the main repository
        params_dir (str): Full path to the params repository
    """

    def __init__(
        self,
        repo: str,
        owner: str = "Utilities-tkgieng",
        params_repo: str = "params",
        repo_dir: str = None,
        params_dir: str = None,
        token: str = None,
    ) -> None:
        self.repo = repo
        self.owner = owner
        self.params_repo = params_repo
        self.git_helper = GitHelper(repo=repo)
        self.github_token = token = os.getenv("GITHUB_TOKEN")
        self.github_client = GitHubClient()
        self.home = str(Path.home())
        self.repo_dir = repo_dir if repo_dir else os.path.join(self.home, "git", self.repo)
        self.params_dir = (
            params_dir if params_dir else os.path.join(self.home, "git", self.params_repo)
        )

        if not self.git_helper.check_git_repo():
            raise ValueError("Repository is not a git repository")

    def get_latest_release_tag(self) -> str:
        """Get the latest release tag from git."""
        self.git_helper.pull_all()
        try:
            result = subprocess.run(
                ["git", "describe", "--tags", "$(git rev-list --tags --max-count=1)"],
                capture_output=True,
                text=True,
                check=True,
                cwd=self.repo_dir,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            self.git_helper.error("No release tags found. Make sure to fly the release pipeline.")
            sys.exit(1)

    def get_latest_release(self) -> str:
        """Get the latest release version without the 'release-v' prefix."""
        tag = self.get_latest_release_tag()
        return tag.replace("release-v", "")

    def get_releases(self) -> Optional[List[str]]:
        """Get all releases for the repository."""
        try:
            return self.github_client.get_releases(self.owner, self.repo)
        except requests.exceptions.RequestException as e:
            self.git_helper.error(f"Error fetching releases: {str(e)}")
            return None

    def validate_release_param(self, param: str) -> bool:
        """Validate a release parameter format."""
        if not param:
            self.git_helper.error("Error: Parameter is required")
            self.git_helper.info("Example: release-v1.0.0")
            return False

        if not param.startswith("release-v"):
            self.git_helper.error("Error: Parameter must start with 'release-v'")
            self.git_helper.info("Example: release-v1.0.0")
            return False

        version_part = param.replace("release-v", "")
        parts = version_part.split(".")
        if len(parts) != 3:
            self.git_helper.error("Error: Invalid semantic version format after 'release-v'")
            self.git_helper.error("The version must follow the MAJOR.MINOR.PATCH format")
            self.git_helper.info("Example: release-v1.0.0")
            return False

        try:
            major, minor, patch = map(int, parts)
        except ValueError:
            self.git_helper.error("Error: Version components must be numbers")
            return False

        return True

    def compare_versions(self, v1: str, v2: str) -> int:
        """Compare two semantic versions. Returns 1 if v1 > v2, -1 if v1 < v2, 0 if equal."""
        v1_parts = list(map(int, v1.split(".")))
        v2_parts = list(map(int, v2.split(".")))

        for i in range(max(len(v1_parts), len(v2_parts))):
            v1_val = v1_parts[i] if i < len(v1_parts) else 0
            v2_val = v2_parts[i] if i < len(v2_parts) else 0
            if v1_val > v2_val:
                return 1
            elif v1_val < v2_val:
                return -1
        return 0

    def get_github_release_by_tag(self, release_tag: str) -> Optional[dict]:
        """Get a GitHub release by tag."""
        try:
            return self.github_client.find_release_by_tag(self.owner, self.repo, release_tag)
        except requests.exceptions.RequestException as e:
            self.git_helper.error(f"Failed to get release by tag: {e}")
            return None

    def delete_github_release(self, release_tag: str, delete_tag: bool = True) -> bool:
        """Delete a GitHub release and optionally its tag."""
        # Get the release ID from the tag name
        release_id = None
        try:
            release = self.get_github_release_by_tag(release_tag)
            release_id = release.get("id") if release else None
        except requests.exceptions.RequestException as e:
            self.git_helper.warn(f"Failed to find release: {e}")
        if not release_id:
            self.git_helper.warn(
                f"Release for {self.owner}/{self.repo} with tag {release_tag} not found"
            )
            try:
                if delete_tag:
                    self.git_helper.pull()
                    self.git_helper.delete_tag(release_tag)
                return True
            except requests.exceptions.RequestException as e:
                self.git_helper.error(f"Failed to delete tag {release_tag}: {e}")
                return False
        try:
            self.github_client.delete_release(self.owner, self.repo, release_id)
            if delete_tag:
                self.git_helper.pull()
                self.git_helper.delete_tag(release_tag)
            return True
        except requests.exceptions.RequestException as e:
            self.git_helper.error(f"Failed to delete release: {e}")
            return False

    def get_params_release_tags(self) -> List[str]:
        """Get all release tags from the params repo."""
        try:
            self.git_helper.pull_all(repo=self.params_repo)
            result = subprocess.run(
                ["git", "tag", "-l"],
                capture_output=True,
                text=True,
                check=True,
                cwd=self.params_dir,
            )
            return result.stdout.strip().split("\n")
        except subprocess.CalledProcessError as e:
            self.git_helper.error(f"Failed to get params release tags: {e}")
            return []

    def validate_params_release_tag(self, release_tag: str) -> bool:
        """Validate if a release tag exists in the params repo."""
        return release_tag in self.get_params_release_tags()

    def print_valid_params_release_tags(self) -> None:
        """Print all valid release tags for the current repo from params."""
        tags = self.get_params_release_tags()
        for tag in tags:
            if tag.startswith(self.repo):
                self.git_helper.info(f'> {tag.replace(f"{self.repo}-", "")}')

    def update_params_git_release_tag(self) -> bool:
        """Update the git release tag in params repo."""
        try:
            self.git_helper.pull_all()
            tags = self.git_helper.get_tags()
            release_tags = [t for t in tags if t.startswith("release-v")]
            if not release_tags:
                self.git_helper.error("No release tags found")
                return False

            last_release = sorted(release_tags)[-2] if len(release_tags) > 1 else release_tags[0]
            current_release = sorted(release_tags)[-1]
            last_version = last_release.replace("release-v", "")
            current_version = current_release.replace("release-v", "")

            self.git_helper.info(
                f"Updating the params for the tkgi-{self.repo} pipeline from {last_version} to {current_version}"
            )
            if not self.git_helper.confirm("Do you want to continue?"):
                return False

            # Update params repo
            self.git_helper.pull_all(repo=self.params_repo)
            if self.git_helper.has_uncommitted_changes(repo=self.params_repo):
                self.git_helper.error("Please commit or stash your changes to params")
                return False

            from_version = f"v{last_version}"
            to_version = f"v{current_version}"

            # Update files
            try:
                self.git_helper.update_release_tag_in_params(
                    self.params_repo, self.repo, from_version, to_version
                )
            except (IOError, OSError, subprocess.SubprocessError) as e:
                self.git_helper.error(f"Failed to update release tag in params: {e}")
                return False

            if not self.git_helper.confirm("Do you want to continue with these commits?"):
                self.git_helper.reset_changes(repo=self.params_repo)
                return False

            try:
                subprocess.run(
                    ["git", "status"],
                    check=True,
                    cwd=self.params_repo,
                )
                subprocess.run(
                    ["git", "diff"],
                    check=True,
                    cwd=self.params_repo,
                )
            except subprocess.CalledProcessError as e:
                self.git_helper.error(f"Failed to run git status/diff: {e}")
                return False

            # Create and merge branch
            branch_name = f"{self.repo}-release-{to_version}"
            self.git_helper.create_and_merge_branch(
                self.params_repo,
                branch_name,
                f"Update git_release_tag from release-{from_version} to release-{to_version}\n\nNOTICKET",
            )

            # Create and push tag
            self.git_helper.create_and_push_tag(
                self.params_repo,
                f"{self.repo}-release-{to_version}",
                f"Version {self.repo}-release-{to_version}",
            )

            return True
        except (subprocess.SubprocessError, IOError, OSError, ValueError) as e:
            self.git_helper.error(f"Failed to update git release tag: {e}")
            return False

    def run_release_pipeline(self, foundation: str, message_body: str = "") -> bool:
        """Run the release pipeline."""
        pipeline = f"tkgi-{self.repo}-release"
        if self.owner != "Utilities-tkgieng":
            pipeline = f"tkgi-{self.repo}-{self.owner}-release"
        self.git_helper.info(f"Running {pipeline} pipeline...")

        if not self.git_helper.confirm("Do you want to continue?"):
            return False

        try:
            # Run fly.sh script
            self.run_fly_script(
                ["-f", foundation, "-r", message_body, "-o", self.owner, "-p", pipeline]
            )

            # Unpause and trigger pipeline
            subprocess.run(
                ["fly", "-t", "tkgi-pipeline-upgrade", "unpause-pipeline", "-p", pipeline],
                check=True,
            )
            subprocess.run(
                [
                    "fly",
                    "-t",
                    "tkgi-pipeline-upgrade",
                    "trigger-job",
                    "-j",
                    f"{pipeline}/create-final-release",
                ],
                check=True,
            )
            subprocess.run(
                [
                    "fly",
                    "-t",
                    "tkgi-pipeline-upgrade",
                    "watch",
                    "-j",
                    f"{pipeline}/create-final-release",
                ],
                check=True,
            )

            input("Press enter to continue")
            self.git_helper.pull_all()
            return True
        except Exception as e:
            self.git_helper.error(f"Failed to run release pipeline: {e}")
            return False

    def run_set_pipeline(self, foundation: str) -> bool:
        """Run the set release pipeline."""
        pipeline = f"tkgi-{self.repo}-{foundation}-set-release-pipeline"
        if self.owner != "Utilities-tkgieng":
            pipeline = f"tkgi-{self.repo}-{self.owner}-{foundation}-set-release-pipeline"
        self.git_helper.info(f"Running {pipeline} pipeline...")

        if not self.git_helper.confirm("Do you want to continue?"):
            return False

        try:
            # Run fly.sh script
            self.run_fly_script(
                [
                    "-f",
                    foundation,
                    "-s",
                    pipeline,
                    "-b",
                    self.git_helper.get_current_branch(),
                    "-d",
                    self.git_helper.get_current_branch(repo=self.params_repo),
                    "-o",
                    self.owner,
                    "-p",
                    f"tkgi-{self.repo}-{foundation}",
                ]
            )

            # Unpause and trigger pipeline
            subprocess.run(
                ["fly", "-t", foundation, "unpause-pipeline", "-p", pipeline], check=True
            )
            subprocess.run(
                [
                    "fly",
                    "-t",
                    foundation,
                    "trigger-job",
                    "-j",
                    f"{pipeline}/set-release-pipeline",
                    "-w",
                ],
                check=True,
            )

            input("Press enter to continue")
            return True
        except Exception as e:
            self.git_helper.error(f"Failed to run set pipeline: {e}")
            return False

    def run_fly_script(self, args: list) -> None:
        """Run the fly.sh script in the repo's ci directory.

        Args:
            args: List of arguments to pass to fly.sh
        """
        ci_dir = os.path.join(self.repo_dir, "ci")
        if not os.path.isdir(ci_dir):
            self.git_helper.error(f"CI directory not found at {ci_dir}")
            return

        # Check for FLY_SCRIPT environment variable first
        fly_script = os.getenv("FLY_SCRIPT")
        if fly_script:
            if not os.path.isabs(fly_script):
                fly_script = os.path.join(ci_dir, fly_script)
        else:
            # Look for any script that starts with 'fly'
            fly_scripts = []
            for item in os.listdir(ci_dir):
                if item.startswith("fly"):
                    script_path = os.path.join(ci_dir, item)
                    if os.path.isfile(script_path):
                        fly_scripts.append(script_path)

            if not fly_scripts:
                self.git_helper.error(f"No fly script found in {ci_dir}")
                return

            if len(fly_scripts) == 1:
                fly_script = fly_scripts[0]
            else:
                self.git_helper.info("Multiple fly scripts found. Please choose one:")
                for i, script in enumerate(fly_scripts, 1):
                    self.git_helper.info(f"{i}. {os.path.basename(script)}")

                while True:
                    try:
                        choice = int(input("Enter the number of the script to use: "))
                        if 1 <= choice <= len(fly_scripts):
                            fly_script = fly_scripts[choice - 1]
                            break
                        self.git_helper.error(
                            f"Please enter a number between 1 and {len(fly_scripts)}"
                        )
                    except ValueError:
                        self.git_helper.error("Please enter a valid number")

        if not os.access(fly_script, os.X_OK):
            self.git_helper.error(f"Fly script at {fly_script} is not executable")
            return

        try:
            subprocess.run([fly_script] + args, cwd=ci_dir, check=True)
        except subprocess.CalledProcessError as e:
            self.git_helper.error(f"Fly script failed: {e.cmd}")
            self.git_helper.error(f"Exit code: {e.returncode}")
            if e.output:
                self.git_helper.error(f"Output: {e.output.decode()}")
            raise


def main():
    parser = argparse.ArgumentParser(description="Release management helper script")
    parser.add_argument("-f", "--foundation", required=True, help="Foundation name for ops manager")
    parser.add_argument("-m", "--message", help="Message to apply to the release")
    parser.add_argument("-o", "--owner", default="Utilities-tkgieng", help="GitHub owner")
    parser.add_argument("-p", "--params-repo", default="params", help="Params repo name")
    parser.add_argument("--repo", default="ns-mgmt", help="Repository name")
    args = parser.parse_args()

    helper = ReleaseHelper(repo=args.repo, owner=args.owner, params_repo=args.params_repo)

    # Run release pipeline
    if helper.run_release_pipeline(args.foundation, args.message):
        # Update git release tag
        helper.update_params_git_release_tag()
        # Run set pipeline
        helper.run_set_pipeline(args.foundation)


if __name__ == "__main__":
    main()

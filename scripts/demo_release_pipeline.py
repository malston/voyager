#!/usr/bin/env python3

import argparse
import os
import re
import subprocess
from typing import Optional, Tuple

from voyager.git import GitHelper
from voyager.github import GitHubClient


class DemoReleasePipeline:
   def __init__(
       self,
       foundation: str,
       repo: str,
       owner: str,
       branch: str,
       params_repo: str,
       params_branch: str,
       release_tag: str,
       release_body: str,
       dry_run: bool = False,
       git_dir: str = None
   ):
       self.foundation = foundation
       self.branch = branch
       self.params_branch = params_branch
       self.release_tag = release_tag
       self.release_body = release_body
       self.dry_run = dry_run
       self.owner = owner
       self.repo = repo
       self.params_repo = params_repo
       self.github_token = os.getenv('GITHUB_TOKEN')
       self.git_helper = GitHelper()
       self.github_client = GitHubClient(token=self.github_token)

       if not self.github_token:
           raise ValueError("GITHUB_TOKEN env must be set before executing this script")
           
       # Store the repo directory path
       if git_dir is None:
           git_dir = os.path.expanduser("~/git")
       self.repo_dir = os.path.join(git_dir, self.repo)
       if not os.path.isdir(self.repo_dir):
           raise ValueError(f"Could not find repo directory: {self.repo_dir}")

   def is_semantic_version(self, version: str) -> bool:
       """Check if a string is a valid semantic version number.

       Args:
           version: The version string to validate

       Returns:
           bool: True if the version is a valid semantic version, False otherwise
       """
       pattern = r'^\d+\.\d+\.\d+$'
       return bool(re.match(pattern, version))

   def run_git_command(self, command: list, **kwargs) -> subprocess.CompletedProcess:
       """Run a git command in the repo directory.
       
       Args:
           command: List of command arguments
           **kwargs: Additional arguments to pass to subprocess.run
           
       Returns:
           subprocess.CompletedProcess: The result of running the command
       """
       if self.dry_run:
           self.git_helper.info(f"[DRY RUN] Would run git command: {' '.join(command)}")
           return None
           
       return subprocess.run(command, cwd=self.repo_dir, **kwargs)

   def validate_git_tag(self, version: str) -> bool:
       """Check if a git tag exists for the given version."""
       try:
           # Check if the tag exists
           result = self.run_git_command(
               ['git', 'tag', '-l', f'release-v{version}'],
               check=True,
               capture_output=True,
               text=True
           )
           return bool(result.stdout.strip())
       except subprocess.CalledProcessError:
           return False

   def get_valid_version_input(self) -> Optional[str]:
       """Get and validate version input from the user.

       Returns:
           Optional[str]: The validated version number or None if validation fails
       """
       while True:
           version = input("Enter the version you want to revert to: ").strip()

           if not self.is_semantic_version(version):
               self.git_helper.error(f"Invalid version format: {version}")
               self.git_helper.info("Version must be in semantic version format (e.g., 1.2.3)")
               retry = input("Would you like to try again? [yN] ")
               if not retry.lower().startswith('y'):
                   return None
               continue

           if not self.validate_git_tag(version):
               self.git_helper.error(f"No git tag found for version: release-v{version}")
               self.git_helper.info("Available release tags:")
               # Show available tags for reference
               subprocess.run(['git', 'tag', '-l', 'release-v*'], check=True)
               retry = input("Would you like to try again? [yN] ")
               if not retry.lower().startswith('y'):
                   return None
               continue

           return version

   def delete_github_release(self, repo: str, owner: str, tag: str, non_interactive: bool = True) -> None:
       """Delete a GitHub release."""
       if not non_interactive:
           response = input(f"Do you want to delete github release: {tag}? [yN] ")
           if not response.lower().startswith('y'):
               return

       try:
           # Get all releases to find the one with matching tag
           releases = self.github_client.get_releases(owner, repo)
           release_id = None

           for release in releases:
               if release['tag_name'] == tag:
                   release_id = release['id']
                   break

           if not release_id:
               self.git_helper.error(f"Release with tag {tag} not found")
               return

           if self.dry_run:
               self.git_helper.info(f"[DRY RUN] Would delete GitHub release {tag} for {owner}/{repo} (release_id: {release_id})")
               return

           # Delete the release
           if self.github_client.delete_release(owner, repo, release_id):
               self.git_helper.info(f"Successfully deleted GitHub release {tag} for {owner}/{repo}")
           else:
               self.git_helper.error(f"Failed to delete GitHub release {tag}")

       except Exception as e:
           self.git_helper.error(f"Error deleting GitHub release: {str(e)}")

   def revert_version(self, previous_version: str) -> None:
       """Revert to a previous version."""
       self.git_helper.info(f"Reverting to version: {previous_version}")
       
       if self.dry_run:
           self.git_helper.info(f"[DRY RUN] Would perform the following actions:")
           self.git_helper.info(f"1. Checkout and pull version branch")
           self.git_helper.info(f"2. Update version file to {previous_version}")
           self.git_helper.info(f"3. Commit and push changes")
           self.git_helper.info(f"4. Recreate release branch")
           return
       
       try:
           # Change to version branch
           self.run_git_command(['git', 'checkout', 'version'], check=True)
           self.run_git_command(['git', 'pull', '-q', 'origin', 'version'], check=True)
           
           # Update version file
           version_file = os.path.join(self.repo_dir, 'version')
           with open(version_file, 'w') as f:
               f.write(previous_version)
           
           # Commit changes
           self.run_git_command(['git', 'add', '.'], check=True)
           self.run_git_command(['git', 'commit', '-m', f"Revert version back to {previous_version} NOTICKET"], check=True)
           self.run_git_command(['git', 'push', 'origin', 'version'], check=True)
           
           # Recreate release branch
           self.run_git_command(['git', 'checkout', 'master'], check=True)
           self.run_git_command(['git', 'pull', '-q', 'origin', 'version'], check=True)
           self.run_git_command(['git', 'branch', '-D', 'release'], check=True)
           self.run_git_command(['git', 'push', '--delete', 'origin', 'release'], check=True)
           self.run_git_command(['git', 'checkout', '-b', 'release'], check=True)
           self.run_git_command(['git', 'push', '-u', 'origin', 'release'], check=True)
           
       except subprocess.CalledProcessError as e:
           self.git_helper.error(f"Git operation failed: {e.cmd}")
           self.git_helper.error(f"Exit code: {e.returncode}")
           if e.output:
               self.git_helper.error(f"Output: {e.output.decode()}")
           self.git_helper.error("Version reversion failed. Please check the git status and resolve any issues.")
           return
       except Exception as e:
           self.git_helper.error(f"Unexpected error during version reversion: {str(e)}")
           return

   def run_fly_script(self, args: list) -> None:
       """Run the fly.sh script in the repo's ci directory.
       
       Args:
           args: List of arguments to pass to fly.sh
       """
       if self.dry_run:
           self.git_helper.info(f"[DRY RUN] Would run fly.sh with args: {' '.join(args)}")
           return
            
       ci_dir = os.path.join(self.repo_dir, 'ci')
       if not os.path.isdir(ci_dir):
           self.git_helper.error(f"CI directory not found at {ci_dir}")
           return
            
       # Check for FLY_SCRIPT environment variable first
       fly_script = os.getenv('FLY_SCRIPT')
       if fly_script:
           if not os.path.isabs(fly_script):
               fly_script = os.path.join(ci_dir, fly_script)
       else:
           # Look for any script that starts with 'fly'
           fly_scripts = []
           for item in os.listdir(ci_dir):
               if item.startswith('fly'):
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
                       self.git_helper.error(f"Please enter a number between 1 and {len(fly_scripts)}")
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

   def run_release_pipeline(self) -> None:
       """Run the release pipeline."""
       release_pipeline = f"tkgi-{self.repo}-release"

       if self.dry_run:
           self.git_helper.info(f"[DRY RUN] Would perform the following actions:")
           self.git_helper.info(f"1. Ask to recreate release pipeline: {release_pipeline}")
           self.git_helper.info(f"2. Run fly.sh with parameters:")
           self.git_helper.info(f"   - foundation: {self.foundation}")
           self.git_helper.info(f"   - release body: {self.release_body}")
           self.git_helper.info(f"   - owner: {self.owner}")
           self.git_helper.info(f"   - pipeline: {release_pipeline}")
           self.git_helper.info(f"3. Ask to run pipeline: {release_pipeline}")
           self.git_helper.info(f"4. Update git release tag")
           return

       # Recreate release pipeline if needed
       response = input("Do you want to recreate the release pipeline? [yN] ")
       if response.lower().startswith('y'):
           subprocess.run(['fly', '-t', 'tkgi-pipeline-upgrade', 'dp', '-p', release_pipeline, '-n'], check=True)

       # Run fly.sh script
       self.run_fly_script([
           '-f', self.foundation,
           '-r', self.release_body,
           '-o', self.owner,
           '-p', release_pipeline
       ])

       # Run pipeline if requested
       response = input(f"Do you want to run the {release_pipeline} pipeline? [yN] ")
       if response.lower().startswith('y'):
           subprocess.run(['fly', '-t', 'tkgi-pipeline-upgrade', 'unpause-pipeline', '-p', release_pipeline], check=True)
           subprocess.run(['fly', '-t', 'tkgi-pipeline-upgrade', 'trigger-job', '-j', f"{release_pipeline}/create-final-release"], check=True)
           subprocess.run(['fly', '-t', 'tkgi-pipeline-upgrade', 'watch', '-j', f"{release_pipeline}/create-final-release"], check=True)
           input("Press enter to continue")

           if not self.git_helper.update_git_release_tag(self.owner, self.repo, self.params_repo):
               self.git_helper.error("Failed to update git release tag")

   def run_set_release_pipeline(self) -> None:
       """Run the set release pipeline."""
       mgmt_pipeline = f"tkgi-{self.repo}-{self.foundation}"
       set_release_pipeline = f"{mgmt_pipeline}-set-release-pipeline"

       if self.dry_run:
           self.git_helper.info(f"[DRY RUN] Would perform the following actions:")
           self.git_helper.info(f"1. Ask to run pipeline: {set_release_pipeline}")
           self.git_helper.info(f"2. Run fly.sh with parameters:")
           self.git_helper.info(f"   - foundation: {self.foundation}")
           self.git_helper.info(f"   - set pipeline: {set_release_pipeline}")
           self.git_helper.info(f"   - branch: {self.branch}")
           self.git_helper.info(f"   - params branch: {self.params_branch}")
           self.git_helper.info(f"   - owner: {self.owner}")
           self.git_helper.info(f"   - pipeline: {mgmt_pipeline}")
           self.git_helper.info(f"3. Unpause and trigger set-release-pipeline job")
           self.git_helper.info(f"4. Ask to run pipeline: {mgmt_pipeline}")
           self.git_helper.info(f"5. Unpause and trigger prepare-kustomizations job")
           return

       response = input(f"Do you want to run the {set_release_pipeline} pipeline? [yN] ")
       if response.lower().startswith('y'):
           self.run_fly_script([
               '-f', self.foundation,
               '-s', set_release_pipeline,
               '-b', self.branch,
               '-d', self.params_branch,
               '-o', self.owner,
               '-p', mgmt_pipeline
           ])

           subprocess.run(['fly', '-t', self.foundation, 'unpause-pipeline', '-p', set_release_pipeline], check=True)
           subprocess.run(['fly', '-t', self.foundation, 'trigger-job', '-j', f"{set_release_pipeline}/set-release-pipeline", '-w'], check=True)

           response = input(f"Do you want to run the {mgmt_pipeline} pipeline? [yN] ")
           if response.lower().startswith('y'):
               subprocess.run(['fly', '-t', self.foundation, 'unpause-pipeline', '-p', mgmt_pipeline], check=True)
               subprocess.run(['fly', '-t', self.foundation, 'trigger-job', '-j', f"{mgmt_pipeline}/prepare-kustomizations", '-w'], check=True)

   def refly_pipeline(self) -> None:
       """Refly the pipeline back to latest code."""
       mgmt_pipeline = f"tkgi-{self.repo}-{self.foundation}"

       response = input(f"Do you want to refly the {self.repo} pipeline back to latest code on branch: {self.branch}? [yN] ")
       if response.lower().startswith('y'):
           self.run_fly_script([
               '-f', self.foundation,
               '-b', self.branch,
               '-p', mgmt_pipeline
           ])

           response = input(f"Do you want to rerun the {mgmt_pipeline} pipeline? [yN] ")
           if response.lower().startswith('y'):
               subprocess.run(['fly', '-t', self.foundation, 'unpause-pipeline', '-p', mgmt_pipeline], check=True)
               subprocess.run(['fly', '-t', self.foundation, 'trigger-job', '-j', f"{mgmt_pipeline}/prepare-kustomizations", '-w'], check=True)

   def handle_version_reversion(self) -> None:
       """Handle checking current version and potential reversion to an older version."""
       if self.dry_run:
           self.git_helper.info("[DRY RUN] Would perform the following actions:")
           self.git_helper.info("1. Checkout and pull version branch")
           self.git_helper.info("2. Read current version from version file")
           self.git_helper.info("3. Ask if you want to revert to an older version")
           self.git_helper.info("4. If yes, validate and prompt for previous version")
           self.git_helper.info("5. If valid, revert to the specified version")
           return
            
       try:
           # Check current version
           self.run_git_command(['git', 'checkout', 'version'], check=True)
           self.run_git_command(['git', 'pull', '-q', 'origin', 'version'], check=True)
       except subprocess.CalledProcessError as e:
           self.git_helper.error(f"Git operation failed: {e.cmd}")
           self.git_helper.error(f"Exit code: {e.returncode}")
           if e.output:
               self.git_helper.error(f"Output: {e.output.decode()}")
           return
        
       version_file = os.path.join(self.repo_dir, 'version')
       if not os.path.exists(version_file):
           self.git_helper.error(f"Version file not found at {version_file}")
           return

       try:
           with open(version_file, 'r') as f:
               current_version = f.read().strip()
       except Exception as e:
           self.git_helper.error(f"Error reading version file: {str(e)}")
           return

       self.git_helper.info(f"The current version is: {current_version}")
        
       # Handle version reversion if requested
       response = input("Do you want to revert to an older version? [yN] ")
       if response.lower().startswith('y'):
           previous_version = self.get_valid_version_input()
           if previous_version:
               self.revert_version(previous_version)
           else:
               self.git_helper.info("Version reversion cancelled")

   def run(self) -> None:
       """Run the complete demo release pipeline."""
       # Check for uncommitted changes
       # result = subprocess.run(['git', 'status', '--porcelain'], check=True, capture_output=True, text=True)
       # if result.stdout.strip():
       #     self.git_helper.error("Please commit or stash your changes before running this script")
       #     return

       # Delete GitHub release if requested
       self.delete_github_release(self.repo, self.owner, self.release_tag)

       # Handle version checking and potential reversion
       self.handle_version_reversion()

       # Run the pipeline steps
       self.run_release_pipeline()
       self.run_set_release_pipeline()
       self.refly_pipeline()


def main():
   parser = argparse.ArgumentParser(description='Demo release pipeline script')
   parser.add_argument('-f', '--foundation', required=True, help='the foundation name for ops manager (e.g. cml-k8s-n-01)')
   parser.add_argument('-r', '--repo', required=True, help='the repo to use')
   parser.add_argument('-o', '--owner', default=os.getenv('USER'), help='the repo owner to use')
   parser.add_argument('-b', '--branch', default=None, help='the branch to use')
   parser.add_argument('-p', '--params-repo', default='params', help='the params repo to use')
   parser.add_argument('-d', '--params-branch', default='master', help='the params branch to use')
   parser.add_argument('-t', '--tag', default=None, help='the release tag')
   parser.add_argument('-m', '--message', default='', help='the message to apply to the release that is created')
   parser.add_argument('--dry-run', action='store_true', help='run in dry-run mode (no actual changes will be made)')
   parser.add_argument('--git-dir', default=None, help='the base directory containing git repositories (default: ~/git)')

   args = parser.parse_args()

   # Get current branch if not specified
   if not args.branch:
       result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], check=True, capture_output=True, text=True)
       args.branch = result.stdout.strip()

   # Get latest release tag if not specified
   git_helper = GitHelper()
   if not args.tag:
       args.tag = git_helper.get_latest_release_tag()

   pipeline = DemoReleasePipeline(
       foundation=args.foundation,
       repo=args.repo,
       owner=args.owner,
       branch=args.branch,
       params_repo=args.params_repo,
       params_branch=args.params_branch,
       release_tag=args.tag,
       release_body=args.message,
       dry_run=args.dry_run,
       git_dir=args.git_dir
   )

   pipeline.run()


if __name__ == '__main__':
   main()

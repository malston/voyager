#!/usr/bin/env python3

import os
import subprocess


class PipelineRunner:
    """Client for running Concourse pipelines."""

    # ANSI color codes
    GREEN = "\033[0;32m"
    CYAN = "\033[0;36m"
    RED = "\033[0;31m"
    YELLOW = "\033[0;33m"
    NOCOLOR = "\033[0m"

    def __init__(self, foundation: str, repo: str, pipeline: str):
        """Initialize the PipelineRunner with foundation and repo information.

        Args:
            foundation: Foundation name (e.g., tkgi-pipeline-upgrade)
            repo: Repository name or path to repository CI directory
            pipeline: Name of the pipeline to run
        """
        self.foundation = foundation
        self.repo = repo
        self.pipeline = pipeline

        # If repo is a path, use it directly, otherwise try to find the CI directory
        if os.path.exists(repo):
            self.repo_ci_dir = repo
        else:
            # Try common CI directory locations
            possible_paths = [
                os.path.expanduser(f"~/git/{repo}/ci"),
                os.path.join(repo, "ci"),
                os.path.join(os.getcwd(), "ci"),
            ]

            # Find the first existing CI directory
            for path in possible_paths:
                if os.path.exists(path):
                    self.repo_ci_dir = path
                    break
            else:
                raise ValueError(f"Could not find CI directory for repository: {repo}")

        # Validate that the CI directory exists
        if not os.path.exists(self.repo_ci_dir):
            raise ValueError(f"CI directory does not exist: {self.repo_ci_dir}")

        # Check for any fly script in the CI directory
        fly_scripts = [
            f
            for f in os.listdir(self.repo_ci_dir)
            if f.startswith("fly")
            and os.path.isfile(os.path.join(self.repo_ci_dir, f))
            and os.access(os.path.join(self.repo_ci_dir, f), os.X_OK)
        ]

        if not fly_scripts:
            raise ValueError(f"No executable fly script found in CI directory: {self.repo_ci_dir}")

        # Store the first fly script we found
        self.fly_script = os.path.join(self.repo_ci_dir, fly_scripts[0])

    def info(self, message: str) -> None:
        """Print info message in cyan color."""
        print(f"{self.CYAN}{message}{self.NOCOLOR}")

    def warn(self, message: str) -> None:
        """Print warning message in yellow color."""
        print(f"{self.YELLOW}{message}{self.NOCOLOR}")

    def error(self, message: str) -> None:
        """Print error message in red color."""
        print(f"{self.RED}{message}{self.NOCOLOR}")

    def completed(self, message: str) -> None:
        """Print completed message in green color."""
        print(f"{self.GREEN}{message}{self.NOCOLOR}")

    def _verify_ci_directory(self) -> bool:
        """Verify that the CI directory exists."""
        if not os.path.exists(self.repo_ci_dir):
            self.error(f"Repository CI directory not found at {self.repo_ci_dir}")
            return False
        return True

    def _get_user_confirmation(self, message: str, default: str = "n") -> bool:
        """Get user confirmation for an action."""
        prompt = (
            f"Do you want to continue? (y/{default}): "
            if default == "n"
            else "Do you want to continue? (y/n): "
        )
        user_input = input(prompt)
        return user_input.lower().startswith("y")

    def _run_fly_script(self, command: str) -> bool:
        """Run the fly script with the provided command.

        Args:
            command: The command to run with the fly script (e.g., '-f "foundation" -r "message"')

        Returns:
            bool: True if the command executed successfully, False otherwise
        """
        try:
            # Construct and run the command
            fly_cmd = f'echo "y" | {self.fly_script} {command}'
            subprocess.run(fly_cmd, check=True, shell=True, cwd=self.repo_ci_dir)
            return True
        except subprocess.CalledProcessError as e:
            self.error(f"Error running fly script: {e}")
            return False

    def _unpause_pipeline(self) -> bool:
        """Unpause the pipeline."""
        try:
            subprocess.run(
                ["fly", "-t", self.foundation, "unpause-pipeline", "-p", self.pipeline],
                check=True,
                cwd=self.repo_ci_dir,
            )
            return True
        except subprocess.CalledProcessError as e:
            self.error(f"Error unpausing pipeline: {e}")
            return False

    def _trigger_job(self, job_name: str, watch: bool = False) -> bool:
        """Trigger a job and optionally watch it."""
        try:
            job_cmd = [
                "fly",
                "-t",
                self.foundation,
                "trigger-job",
                "-j",
                f"{self.pipeline}/{job_name}",
            ]
            if watch:
                job_cmd.append("-w")

            subprocess.run(job_cmd, check=True, cwd=self.repo_ci_dir)
            return True
        except subprocess.CalledProcessError as e:
            self.error(f"Error triggering job: {e}")
            return False

    def _watch_job(self, job_name: str) -> bool:
        """Watch a job's execution."""
        try:
            subprocess.run(
                [
                    "fly",
                    "-t",
                    self.foundation,
                    "watch",
                    "-j",
                    f"{self.pipeline}/{job_name}",
                ],
                check=True,
                cwd=self.repo_ci_dir,
            )
            return True
        except subprocess.CalledProcessError as e:
            self.error(f"Error watching job: {e}")
            return False

    def _pull_latest_changes(self) -> bool:
        """Pull latest changes from git."""
        try:
            subprocess.run(["git", "pull", "-q"], check=True, cwd=self.repo_ci_dir)
            return True
        except subprocess.CalledProcessError as e:
            self.error(f"Error pulling latest changes: {e}")
            return False

    def run_pipeline(self, pipeline_type: str, message_body: str = None) -> bool:
        """Run a pipeline for a repository.

        Args:
            pipeline_type: Type of pipeline to run ('release' or 'set')
            message_body: Optional message body for release pipeline

        Returns:
            bool: True if pipeline ran successfully, False otherwise
        """
        try:
            # Print info and get confirmation
            self.info(f"Running {self.pipeline} pipeline...")
            if not self._get_user_confirmation(f"Continue with {pipeline_type} pipeline?"):
                return False

            # Verify CI directory exists
            if not self._verify_ci_directory():
                return False

            # Define pipeline steps based on type
            if pipeline_type == "release":
                steps = [
                    self._run_fly_script(f'-f "{self.foundation}" -r "{message_body}"'),
                    self._unpause_pipeline(),
                    self._trigger_job("create-final-release"),
                    self._watch_job("create-final-release"),
                ]
            elif pipeline_type == "set":
                steps = [
                    self._run_fly_script(f'-f "{self.foundation}" -s'),
                    self._unpause_pipeline(),
                    self._trigger_job("set-release-pipeline", watch=True),
                ]
            else:
                self.error(f"Invalid pipeline type: {pipeline_type}")
                return False

            # Run pipeline steps
            if not all(steps):
                return False

            # Wait for user confirmation
            input("Press enter to continue")

            # Pull latest changes for release pipeline
            if pipeline_type == "release":
                if not self._pull_latest_changes():
                    return False

            return True

        except Exception as e:
            self.error(f"Unexpected error: {e}")
            return False

    # For backward compatibility
    def run_release_pipeline(self, message_body: str) -> bool:
        """Run the release pipeline for a repository."""
        return self.run_pipeline("release", message_body)

    def run_set_pipeline(self) -> bool:
        """Run the set pipeline for a repository."""
        return self.run_pipeline("set")

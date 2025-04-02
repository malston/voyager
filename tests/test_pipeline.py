#!/usr/bin/env python3

# Standard library imports
import os
import subprocess
import unittest
from unittest.mock import MagicMock, patch

# Local application imports
from voyager.pipeline import PipelineRunner


class TestPipelineRunner(unittest.TestCase):
    """Test cases for the PipelineRunner class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.foundation = "test-foundation"
        self.repo = "test-repo"
        self.pipeline = "test-pipeline"

        # Mock file system operations
        patcher = patch("os.path.exists")
        self.mock_exists = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch("os.listdir")
        self.mock_listdir = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch("os.path.isfile")
        self.mock_isfile = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = patch("os.access")
        self.mock_access = patcher.start()
        self.addCleanup(patcher.stop)

        # Set up default mock behavior
        self.mock_exists.side_effect = lambda path: path == os.path.expanduser(
            f"~/git/{self.repo}/ci"
        )
        self.mock_listdir.return_value = ["fly.sh"]
        self.mock_isfile.return_value = True
        self.mock_access.return_value = True

        self.expected_ci_dir = os.path.expanduser(f"~/git/{self.repo}/ci")
        self.pipeline_runner = PipelineRunner(self.foundation, self.repo, self.pipeline)

    def test_initialization(self):
        """Test that the PipelineRunner is initialized correctly."""
        self.assertEqual(self.pipeline_runner.foundation, self.foundation)
        self.assertEqual(self.pipeline_runner.repo, self.repo)
        self.assertEqual(self.pipeline_runner.pipeline, self.pipeline)
        self.assertEqual(self.pipeline_runner.repo_ci_dir, self.expected_ci_dir)

    def test_initialization_with_existing_path(self):
        """Test initialization when repo is a path."""
        test_path = "/path/to/ci"
        self.mock_exists.side_effect = lambda path: True
        self.mock_listdir.return_value = ["fly.sh"]
        self.mock_isfile.return_value = True
        self.mock_access.return_value = True

        runner = PipelineRunner(self.foundation, test_path, self.pipeline)
        self.assertEqual(runner.repo_ci_dir, test_path)

    def test_initialization_no_fly_script(self):
        """Test initialization when no fly script is found."""
        self.mock_exists.side_effect = lambda path: True
        self.mock_listdir.return_value = []

        with self.assertRaises(ValueError) as cm:
            PipelineRunner(self.foundation, self.repo, self.pipeline)
        self.assertIn("No executable fly script found", str(cm.exception))

    def test_run_fly_script(self):
        """Test running fly script with a command."""
        command = '-f "test" -r "message"'
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            self.assertTrue(self.pipeline_runner._run_fly_script(command))
            mock_run.assert_called_once_with(
                f'echo "y" | {self.pipeline_runner.fly_script} {command}',
                check=True,
                shell=True,
                cwd=self.expected_ci_dir,
            )

    def test_run_fly_script_error(self):
        """Test running fly script when it fails."""
        command = '-f "test"'
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "fly.sh")
            with patch("builtins.print") as mock_print:
                self.assertFalse(self.pipeline_runner._run_fly_script(command))
                mock_print.assert_called_once()

    def test_run_pipeline_release_success(self):
        """Test successful release pipeline run."""
        message_body = "test message"
        with patch.object(
            self.pipeline_runner, "_verify_ci_directory"
        ) as mock_verify, patch.object(
            self.pipeline_runner, "_get_user_confirmation"
        ) as mock_confirm, patch.object(
            self.pipeline_runner, "_run_fly_script"
        ) as mock_fly, patch.object(
            self.pipeline_runner, "_unpause_pipeline"
        ) as mock_unpause, patch.object(
            self.pipeline_runner, "_trigger_job"
        ) as mock_trigger, patch.object(
            self.pipeline_runner, "_watch_job"
        ) as mock_watch, patch(
            "builtins.input"
        ) as mock_input, patch.object(
            self.pipeline_runner, "_pull_latest_changes"
        ) as mock_pull:
            # Set up all mocks to return True
            mock_verify.return_value = True
            mock_confirm.return_value = True
            mock_fly.return_value = True
            mock_unpause.return_value = True
            mock_trigger.return_value = True
            mock_watch.return_value = True
            mock_input.return_value = ""
            mock_pull.return_value = True

            self.assertTrue(self.pipeline_runner.run_pipeline("release", message_body))
            mock_fly.assert_called_once_with(f'-f "{self.foundation}" -r "{message_body}"')

    def test_run_pipeline_set_success(self):
        """Test successful set pipeline run."""
        with patch.object(
            self.pipeline_runner, "_verify_ci_directory"
        ) as mock_verify, patch.object(
            self.pipeline_runner, "_get_user_confirmation"
        ) as mock_confirm, patch.object(
            self.pipeline_runner, "_run_fly_script"
        ) as mock_fly, patch.object(
            self.pipeline_runner, "_unpause_pipeline"
        ) as mock_unpause, patch.object(
            self.pipeline_runner, "_trigger_job"
        ) as mock_trigger, patch(
            "builtins.input"
        ) as mock_input:
            # Set up all mocks to return True
            mock_verify.return_value = True
            mock_confirm.return_value = True
            mock_fly.return_value = True
            mock_unpause.return_value = True
            mock_trigger.return_value = True
            mock_input.return_value = ""

            self.assertTrue(self.pipeline_runner.run_pipeline("set"))
            mock_fly.assert_called_once_with(f'-f "{self.foundation}" -s')

    def test_info_message(self):
        """Test that info messages are printed with cyan color."""
        with patch("builtins.print") as mock_print:
            self.pipeline_runner.info("Test message")
            mock_print.assert_called_once_with(
                f"{self.pipeline_runner.CYAN}Test message{self.pipeline_runner.NOCOLOR}"
            )

    def test_warn_message(self):
        """Test that warning messages are printed with yellow color."""
        with patch("builtins.print") as mock_print:
            self.pipeline_runner.warn("Test message")
            mock_print.assert_called_once_with(
                f"{self.pipeline_runner.YELLOW}Test message{self.pipeline_runner.NOCOLOR}"
            )

    def test_error_message(self):
        """Test that error messages are printed with red color."""
        with patch("builtins.print") as mock_print:
            self.pipeline_runner.error("Test message")
            mock_print.assert_called_once_with(
                f"{self.pipeline_runner.RED}Test message{self.pipeline_runner.NOCOLOR}"
            )

    def test_completed_message(self):
        """Test that completed messages are printed with green color."""
        with patch("builtins.print") as mock_print:
            self.pipeline_runner.completed("Test message")
            mock_print.assert_called_once_with(
                f"{self.pipeline_runner.GREEN}Test message{self.pipeline_runner.NOCOLOR}"
            )

    def test_verify_ci_directory_exists(self):
        """Test CI directory verification when directory exists."""
        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = True
            self.assertTrue(self.pipeline_runner._verify_ci_directory())

    def test_verify_ci_directory_missing(self):
        """Test CI directory verification when directory doesn't exist."""
        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = False
            with patch("builtins.print") as mock_print:
                self.assertFalse(self.pipeline_runner._verify_ci_directory())
                mock_print.assert_called_once()

    def test_get_user_confirmation_yes(self):
        """Test user confirmation when user inputs 'yes'."""
        with patch("builtins.input") as mock_input:
            mock_input.return_value = "yes"
            self.assertTrue(self.pipeline_runner._get_user_confirmation("Test"))

    def test_get_user_confirmation_no(self):
        """Test user confirmation when user inputs 'no'."""
        with patch("builtins.input") as mock_input:
            mock_input.return_value = "no"
            self.assertFalse(self.pipeline_runner._get_user_confirmation("Test"))

    def test_unpause_pipeline(self):
        """Test unpausing the pipeline."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            self.assertTrue(self.pipeline_runner._unpause_pipeline())
            mock_run.assert_called_once_with(
                ["fly", "-t", self.foundation, "unpause-pipeline", "-p", self.pipeline],
                check=True,
                cwd=self.expected_ci_dir,
            )

    def test_trigger_job_without_watch(self):
        """Test triggering a job without watching."""
        job_name = "test-job"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            self.assertTrue(self.pipeline_runner._trigger_job(job_name))
            mock_run.assert_called_once_with(
                ["fly", "-t", self.foundation, "trigger-job", "-j", f"{self.pipeline}/{job_name}"],
                check=True,
                cwd=self.expected_ci_dir,
            )

    def test_trigger_job_with_watch(self):
        """Test triggering a job with watching."""
        job_name = "test-job"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            self.assertTrue(self.pipeline_runner._trigger_job(job_name, watch=True))
            mock_run.assert_called_once_with(
                [
                    "fly",
                    "-t",
                    self.foundation,
                    "trigger-job",
                    "-j",
                    f"{self.pipeline}/{job_name}",
                    "-w",
                ],
                check=True,
                cwd=self.expected_ci_dir,
            )

    def test_watch_job(self):
        """Test watching a job."""
        job_name = "test-job"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            self.assertTrue(self.pipeline_runner._watch_job(job_name))
            mock_run.assert_called_once_with(
                ["fly", "-t", self.foundation, "watch", "-j", f"{self.pipeline}/{job_name}"],
                check=True,
                cwd=self.expected_ci_dir,
            )

    def test_pull_latest_changes(self):
        """Test pulling latest git changes."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            self.assertTrue(self.pipeline_runner._pull_latest_changes())
            mock_run.assert_called_once_with(
                ["git", "pull", "-q"], check=True, cwd=self.expected_ci_dir
            )

    def test_run_pipeline_invalid_type(self):
        """Test running pipeline with invalid type."""
        with patch.object(self.pipeline_runner, "_get_user_confirmation") as mock_confirm, patch(
            "builtins.print"
        ) as mock_print:
            mock_confirm.return_value = True
            self.assertFalse(self.pipeline_runner.run_pipeline("invalid"))
            mock_print.assert_called_with(
                f"{self.pipeline_runner.RED}Invalid pipeline type: invalid"
                f"{self.pipeline_runner.NOCOLOR}"
            )

    def test_run_pipeline_user_cancels(self):
        """Test pipeline run when user cancels."""
        with patch.object(self.pipeline_runner, "_get_user_confirmation") as mock_confirm:
            mock_confirm.return_value = False
            self.assertFalse(self.pipeline_runner.run_pipeline("release"))

    def test_run_pipeline_ci_directory_missing(self):
        """Test pipeline run when CI directory is missing."""
        with patch.object(
            self.pipeline_runner, "_verify_ci_directory"
        ) as mock_verify, patch.object(
            self.pipeline_runner, "_get_user_confirmation"
        ) as mock_confirm:
            mock_verify.return_value = False
            mock_confirm.return_value = True
            self.assertFalse(self.pipeline_runner.run_pipeline("release"))

    def test_run_pipeline_step_failure(self):
        """Test pipeline run when a step fails."""
        with patch.object(
            self.pipeline_runner, "_verify_ci_directory"
        ) as mock_verify, patch.object(
            self.pipeline_runner, "_get_user_confirmation"
        ) as mock_confirm, patch.object(
            self.pipeline_runner, "_run_fly_script"
        ) as mock_fly:
            mock_verify.return_value = True
            mock_confirm.return_value = True
            mock_fly.return_value = False
            self.assertFalse(self.pipeline_runner.run_pipeline("release"))

    def test_backward_compatibility_release_pipeline(self):
        """Test backward compatibility of run_release_pipeline."""
        message_body = "test message"
        with patch.object(self.pipeline_runner, "run_pipeline") as mock_run_pipeline:
            mock_run_pipeline.return_value = True
            self.assertTrue(self.pipeline_runner.run_release_pipeline(message_body))
            mock_run_pipeline.assert_called_once_with("release", message_body)

    def test_backward_compatibility_set_pipeline(self):
        """Test backward compatibility of run_set_pipeline."""
        with patch.object(self.pipeline_runner, "run_pipeline") as mock_run_pipeline:
            mock_run_pipeline.return_value = True
            self.assertTrue(self.pipeline_runner.run_set_pipeline())
            mock_run_pipeline.assert_called_once_with("set")


if __name__ == "__main__":
    unittest.main()

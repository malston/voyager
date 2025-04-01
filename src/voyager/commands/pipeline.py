#!/usr/bin/env python3

import sys

import click

from ..click_utils import CONTEXT_SETTINGS
from ..pipeline import PipelineRunner
from ..utils import check_git_repo


@click.group("pipeline", context_settings=CONTEXT_SETTINGS)
def pipeline_group():
    """Manage Concourse CI pipelines."""
    pass


@pipeline_group.command("release", context_settings=CONTEXT_SETTINGS)
@click.option("--foundation", required=True, help="Foundation name (e.g., cml-k8s-n-01)")
@click.option("--repo", required=True, help="Repository name or path to repository CI directory")
@click.option("--message", "-m", help="Release message describing the changes in this release")
@click.pass_context
def run_release_pipeline(ctx, foundation, repo, message):
    """Run the release pipeline for a repository."""
    if not check_git_repo():
        click.echo("Error: Current directory is not a git repository", err=True)
        sys.exit(1)

    try:
        # Create pipeline runner
        runner = PipelineRunner(foundation, repo)

        # Run the pipeline
        if runner.run_release_pipeline(message):
            click.echo("✓ Release pipeline completed successfully")
        else:
            click.echo("⚠ Release pipeline failed", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error running release pipeline: {str(e)}", err=True)
        sys.exit(1)


@pipeline_group.command("set", context_settings=CONTEXT_SETTINGS)
@click.option("--foundation", required=True, help="Foundation name (e.g., cml-k8s-n-01)")
@click.option("--repo", required=True, help="Repository name or path to repository CI directory")
@click.pass_context
def run_set_pipeline(ctx, foundation, repo):
    """Run the set pipeline for a repository."""
    if not check_git_repo():
        click.echo("Error: Current directory is not a git repository", err=True)
        sys.exit(1)

    try:
        # Create pipeline runner
        runner = PipelineRunner(foundation, repo)

        # Run the pipeline
        if runner.run_set_pipeline():
            click.echo("✓ Set pipeline completed successfully")
        else:
            click.echo("⚠ Set pipeline failed", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error running set pipeline: {str(e)}", err=True)
        sys.exit(1)

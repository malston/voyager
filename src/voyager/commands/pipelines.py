#!/usr/bin/env python3

import sys
from datetime import datetime

import click
from tabulate import tabulate

from ..click_utils import CONTEXT_SETTINGS
from ..concourse import ConcourseClient
from ..utils import check_git_repo, get_repo_info


@click.command("pipelines", context_settings=CONTEXT_SETTINGS)
@click.option("--limit", "-l", default=5, help="Limit the number of pipelines shown")
@click.option("--concourse-url", help="Concourse CI API URL")
@click.option("--concourse-team", help="Concourse CI team name")
@click.option("--concourse-target", help="Concourse target name from ~/.flyrc")
@click.option("--pipeline", required=True, help="Concourse pipeline name")
@click.option(
    "--format", "-f", type=click.Choice(["table", "json"]), default="table", help="Output format"
)
def list_pipelines(limit, concourse_url, concourse_team, concourse_target, pipeline, format):
    """List recent release pipelines/builds."""
    if not check_git_repo():
        click.echo("Error: Current directory is not a git repository", err=True)
        sys.exit(1)

    try:
        owner, repo = get_repo_info()
        click.echo(f"Fetching recent builds for {owner}/{repo}...")

        # Initialize Concourse client
        concourse_client = ConcourseClient(
            api_url=concourse_url, team=concourse_team, target=concourse_target
        )

        # Fetch pipeline builds
        builds = concourse_client.get_pipeline_builds(pipeline, limit=limit)

        if not builds:
            click.echo("No builds found for this pipeline.")
            return

        if format == "json":
            # Output as JSON
            import json

            click.echo(json.dumps(builds, indent=2))
        else:
            # Format builds as a table
            table_data = []
            headers = ["Build #", "Job", "Status", "Started", "Duration", "URL"]

            for build in builds:
                # Parse and format dates
                started_at = build.get("start_time")
                if started_at:
                    # Convert from Unix timestamp if necessary
                    if isinstance(started_at, (int, float)):
                        date_obj = datetime.fromtimestamp(started_at)
                    else:
                        try:
                            date_obj = datetime.strptime(started_at, "%Y-%m-%dT%H:%M:%S.%fZ")
                        except ValueError:
                            date_obj = datetime.strptime(started_at, "%Y-%m-%dT%H:%M:%SZ")
                    formatted_date = date_obj.strftime("%Y-%m-%d %H:%M")
                else:
                    formatted_date = "N/A"

                # Calculate duration if end time is available
                duration = "In progress"
                if build.get("end_time") and build.get("start_time"):
                    end_time = build.get("end_time")
                    start_time = build.get("start_time")

                    # Convert from Unix timestamp if necessary
                    if isinstance(end_time, (int, float)) and isinstance(start_time, (int, float)):
                        duration_seconds = end_time - start_time
                    else:
                        try:
                            end_date = datetime.strptime(end_time, "%Y-%m-%dT%H:%M:%S.%fZ")
                            start_date = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%S.%fZ")
                        except ValueError:
                            end_date = datetime.strptime(end_time, "%Y-%m-%dT%H:%M:%SZ")
                            start_date = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%SZ")
                        duration_seconds = (end_date - start_date).total_seconds()

                    # Format duration
                    minutes, seconds = divmod(duration_seconds, 60)
                    hours, minutes = divmod(minutes, 60)

                    if hours > 0:
                        duration = f"{int(hours)}h {int(minutes)}m"
                    else:
                        duration = f"{int(minutes)}m {int(seconds)}s"

                # Format status with color
                status = build.get("status", "unknown")
                if status == "succeeded":
                    status_display = click.style(status, fg="green")
                elif status == "failed":
                    status_display = click.style(status, fg="red")
                elif status == "started":
                    status_display = click.style(status, fg="yellow")
                else:
                    status_display = status

                # Build URL
                url = (
                    f"{concourse_url}/teams/{concourse_team}/pipelines/{pipeline}/jobs/"
                    f'{build.get("job_name")}/builds/{build.get("name")}'
                )

                # Add the row
                table_data.append(
                    [
                        build.get("name", "N/A"),
                        build.get("job_name", "N/A"),
                        status_display,
                        formatted_date,
                        duration,
                        url,
                    ]
                )

            # Print the table
            click.echo(tabulate(table_data, headers=headers, tablefmt="simple"))
            click.echo(f"\nTotal builds: {len(builds)}")
            click.echo(f"Pipeline URL: {concourse_url}/teams/{concourse_team}/pipelines/{pipeline}")

    except Exception as e:
        click.echo(f"Error listing pipelines: {str(e)}", err=True)
        sys.exit(1)

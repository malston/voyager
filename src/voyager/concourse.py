#!/usr/bin/env python3

import os
from pathlib import Path
from typing import Dict, List, Optional

import click
import requests
import yaml


def get_flyrc_data(target: str = None) -> Optional[Dict]:
    """
    Read and parse the flyrc file.

    Args:
        target: Optional target name to filter data

    Returns:
        Dict containing the flyrc data, or None if file doesn't exist or can't be parsed
    """
    flyrc_path = Path.home() / '.flyrc'
    if not flyrc_path.exists():
        return None

    try:
        with open(flyrc_path, 'r') as f:
            flyrc_data = yaml.safe_load(f)

        if not flyrc_data or 'targets' not in flyrc_data:
            return None

        if target:
            # Get the specified target data if it exists
            if target in flyrc_data.get('targets', {}):
                return {'targets': {target: flyrc_data['targets'][target]}}
            return None

        return flyrc_data
    except (yaml.YAMLError, IOError) as e:
        click.echo(f'Error reading flyrc file: {e}', err=True)
        return None


def get_concourse_data_from_flyrc(target: str) -> Optional[Dict]:
    """
    Extract Concourse data for a specific target from ~/.flyrc file.

    Args:
        target: The Concourse target name

    Returns:
        Dict containing team, api_url, and token if found, None otherwise
    """
    flyrc_data = get_flyrc_data(target)
    if not flyrc_data or 'targets' not in flyrc_data or target not in flyrc_data['targets']:
        return None

    target_data = flyrc_data['targets'][target]

    # Extract relevant information
    result = {
        'team': target_data.get('team'),
        'api_url': target_data.get('api'),
        'token': target_data.get('token', {}).get('value'),
    }

    # Ensure we have the minimum required information
    if not result['team'] or not result['api_url']:
        return None

    return result


def get_token_from_flyrc(target: str) -> Optional[str]:
    """
    Extract Concourse token for a specific target from ~/.flyrc file.

    Args:
        target: The Concourse target name

    Returns:
        The token string if found, None otherwise
    """
    concourse_data = get_concourse_data_from_flyrc(target)
    if not concourse_data:
        return None

    return concourse_data.get('token')


def get_api_url_from_flyrc(target: str) -> Optional[str]:
    """
    Extract Concourse API URL for a specific target from ~/.flyrc file.

    Args:
        target: The Concourse target name

    Returns:
        The API URL string if found, None otherwise
    """
    concourse_data = get_concourse_data_from_flyrc(target)
    if not concourse_data:
        return None

    return concourse_data.get('api_url')


def get_team_from_flyrc(target: str) -> Optional[str]:
    """
    Extract Concourse team name for a specific target from ~/.flyrc file.

    Args:
        target: The Concourse target name

    Returns:
        The team name if found, None otherwise
    """
    concourse_data = get_concourse_data_from_flyrc(target)
    if not concourse_data:
        return None

    return concourse_data.get('team')


class ConcourseClient:
    """Client for interacting with Concourse CI."""

    def __init__(
        self,
        api_url: Optional[str] = None,
        team: Optional[str] = None,
        token: Optional[str] = None,
        target: Optional[str] = None,
    ):
        """
        Initialize a Concourse client.

        Args:
            api_url: URL of the Concourse API (optional if target is provided)
            team: Concourse team name (optional if target is provided)
            token: Authentication token (optional if CONCOURSE_TOKEN env var or target is provided)
            target: Name of the target in ~/.flyrc to use for authentication (optional)
        """
        # First, try to get info from target in ~/.flyrc if provided
        target_team = None
        if target:
            target_api_url = get_api_url_from_flyrc(target)
            target_team = get_team_from_flyrc(target)
            target_token = get_token_from_flyrc(target)

            # Use values from target if not explicitly provided
            if not api_url and target_api_url:
                api_url = target_api_url
            if not team and target_team:
                team = target_team
            if not token and target_token:
                token = target_token

        # Validate API URL
        self.api_url = api_url.rstrip('/') if api_url else None
        if not self.api_url:
            raise ValueError(
                'Concourse API URL not found. Please provide it explicitly via --concourse-url'
                ' or ensure your ~/.flyrc file contains a valid target with --concourse-target.'
            )

        # Validate team
        self.team = team
        if not self.team:
            raise ValueError(
                'Concourse team not found. Please provide it explicitly via --concourse-team'
                ' or ensure your ~/.flyrc file contains a valid target with --concourse-target.'
            )

        # Try to get token in priority order:
        # 1. Explicitly provided token
        # 2. CONCOURSE_TOKEN environment variable
        # 3. Token from ~/.flyrc file for the specified target
        self.token = token or os.environ.get('CONCOURSE_TOKEN')

        if not self.token:
            raise ValueError(
                'Concourse token not found. Please set CONCOURSE_TOKEN environment variable, '
                'provide it explicitly, or ensure your ~/.flyrc file contains credentials '
                'for the target specified with --concourse-target.'
            )

        self.headers = {'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json'}

    def trigger_pipeline(
        self, pipeline_name: str, job_name: str, variables: Dict[str, str] = None
    ) -> bool:
        """Trigger a job in a Concourse pipeline with optional variables."""
        url = (
            f'{self.api_url}/api/v1/teams/{self.team}/pipelines/{pipeline_name}/'
            f'jobs/{job_name}/builds'
        )

        payload = {}
        if variables:
            payload = {'vars': variables}

        response = requests.post(url, headers=self.headers, json=payload)

        if response.status_code in (200, 201):
            build_data = response.json()
            click.echo(f'Pipeline triggered: Build #{build_data.get("id", "Unknown")}')
            click.echo(
                f'URL: {self.api_url}/teams/{self.team}/pipelines/{pipeline_name}/jobs/{job_name}/'
                f'builds/{build_data.get("name", "latest")}'
            )
            return True
        else:
            click.echo(
                f'Failed to trigger pipeline: {response.status_code} - {response.text}', err=True
            )
            return False

    def get_pipeline_builds(self, pipeline_name: str, limit: int = 5) -> List[Dict]:
        """Get recent builds for a pipeline."""
        url = f'{self.api_url}/api/v1/teams/{self.team}/pipelines/{pipeline_name}/builds'
        params = {'limit': limit}

        response = requests.get(url, headers=self.headers, params=params)

        if response.status_code == 200:
            return response.json()
        else:
            click.echo(
                f'Failed to get pipeline builds: {response.status_code} - {response.text}', err=True
            )
            return []

#!/usr/bin/env python3

import os
from pathlib import Path
from typing import Dict, List, Optional

import click
import requests
import yaml


def get_flyrc_data(team: str = None) -> Optional[Dict]:
    """
    Read and parse the flyrc file.

    Args:
        team: Optional team name to filter targets

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

        if team:
            # Filter to targets matching the team
            matching_targets = {}
            for target_name, target_data in flyrc_data.get('targets', {}).items():
                if target_data.get('team') == team:
                    matching_targets[target_name] = target_data

            if matching_targets:
                return {'targets': matching_targets}
            return None

        return flyrc_data
    except (yaml.YAMLError, IOError) as e:
        click.echo(f"Error reading flyrc file: {e}", err=True)
        return None


def get_token_from_flyrc(team: str) -> Optional[str]:
    """
    Extract Concourse token for a specific team from ~/.flyrc file.

    Args:
        team: The Concourse team name

    Returns:
        The token string if found, None otherwise
    """
    flyrc_data = get_flyrc_data(team)
    if not flyrc_data:
        return None

    # Look for the token in any matching target
    for _target, target_data in flyrc_data.get('targets', {}).items():
        token = target_data.get('token', {}).get('value')
        if token:
            return token

    return None


def get_api_url_from_flyrc(team: str) -> Optional[str]:
    """
    Extract Concourse API URL for a specific team from ~/.flyrc file.

    Args:
        team: The Concourse team name

    Returns:
        The API URL string if found, None otherwise
    """
    flyrc_data = get_flyrc_data(team)
    if not flyrc_data:
        return None

    # Look for the API URL in any matching target
    for _target, target_data in flyrc_data.get('targets', {}).items():
        api_url = target_data.get('api')
        if api_url:
            return api_url

    return None


class ConcourseClient:
    """Client for interacting with Concourse CI."""

    def __init__(self, api_url: Optional[str], team: str, token: Optional[str] = None):
        # Get the API URL in priority order:
        # 1. Explicitly provided API URL
        # 2. URL from ~/.flyrc file for the specified team
        self.api_url = None
        if api_url:
            self.api_url = api_url.rstrip('/')
        elif team:
            flyrc_api_url = get_api_url_from_flyrc(team)
            if flyrc_api_url:
                self.api_url = flyrc_api_url.rstrip('/')

        if not self.api_url:
            raise ValueError(
                'Concourse API URL not found. Please provide it explicitly or ensure '
                f'your ~/.flyrc file contains an API URL for the team "{team}".'
            )

        self.team = team

        # Try to get token in priority order:
        # 1. Explicitly provided token
        # 2. CONCOURSE_TOKEN environment variable
        # 3. Token from ~/.flyrc file for the specified team
        self.token = token or os.environ.get('CONCOURSE_TOKEN')

        if not self.token and team:
            self.token = get_token_from_flyrc(team)
        if not self.token:
            raise ValueError(
                'Concourse token not found. Please set CONCOURSE_TOKEN environment variable, '
                'provide it explicitly, or ensure your ~/.flyrc file contains credentials '
                f'for the team "{team}".'
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

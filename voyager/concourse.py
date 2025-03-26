#!/usr/bin/env python3

import os
import requests
import click
from typing import Dict, List, Optional

class ConcourseClient:
    """Client for interacting with Concourse CI."""
    
    def __init__(self, api_url: str, team: str, token: Optional[str] = None):
        self.api_url = api_url.rstrip('/')
        self.team = team
        self.token = token or os.environ.get('CONCOURSE_TOKEN')
        
        if not self.token:
            raise ValueError("Concourse token not found. Please set CONCOURSE_TOKEN environment variable or provide it explicitly.")
            
        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
    
    def trigger_pipeline(self, pipeline_name: str, job_name: str, variables: Dict[str, str] = None) -> bool:
        """Trigger a job in a Concourse pipeline with optional variables."""
        url = f"{self.api_url}/api/v1/teams/{self.team}/pipelines/{pipeline_name}/jobs/{job_name}/builds"
        
        payload = {}
        if variables:
            payload = {"vars": variables}
            
        response = requests.post(url, headers=self.headers, json=payload)
        
        if response.status_code in (200, 201):
            build_data = response.json()
            click.echo(f"Pipeline triggered: Build #{build_data.get('id', 'Unknown')}")
            click.echo(f"URL: {self.api_url}/teams/{self.team}/pipelines/{pipeline_name}/jobs/{job_name}/builds/{build_data.get('name', 'latest')}")
            return True
        else:
            click.echo(f"Failed to trigger pipeline: {response.status_code} - {response.text}", err=True)
            return False
    
    def get_pipeline_builds(self, pipeline_name: str, limit: int = 5) -> List[Dict]:
        """Get recent builds for a pipeline."""
        url = f"{self.api_url}/api/v1/teams/{self.team}/pipelines/{pipeline_name}/builds"
        params = {"limit": limit}
        
        response = requests.get(url, headers=self.headers, params=params)
        
        if response.status_code == 200:
            return response.json()
        else:
            click.echo(f"Failed to get pipeline builds: {response.status_code} - {response.text}", err=True)
            return []

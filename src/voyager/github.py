#!/usr/bin/env python3

import os
from typing import Dict, List, Optional

import requests


class GitHubClient:
    """Client for interacting with GitHub API."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get('GITHUB_TOKEN')

        if not self.token:
            raise ValueError(
                'GitHub token not found. Please set GITHUB_TOKEN environment variable or '
                'provide it explicitly.'
            )

        self.headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json',
        }

    def create_release(
        self,
        owner: str,
        repo: str,
        tag_name: str,
        name: str,
        body: str,
        draft: bool = False,
        prerelease: bool = False,
    ) -> Dict:
        """Create a new release on GitHub."""
        url = f'https://api.github.com/repos/{owner}/{repo}/releases'

        payload = {
            'tag_name': tag_name,
            'name': name,
            'body': body,
            'draft': draft,
            'prerelease': prerelease,
        }

        response = requests.post(url, headers=self.headers, json=payload)

        if response.status_code in (200, 201):
            return response.json()
        else:
            raise Exception(f'Failed to create release: {response.status_code} - {response.text}')

    def get_releases(self, owner: str, repo: str, per_page: int = 10) -> List[Dict]:
        """Get releases for a repository."""
        url = f'https://api.github.com/repos/{owner}/{repo}/releases'
        params = {'per_page': per_page}

        response = requests.get(url, headers=self.headers, params=params)

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f'Failed to get releases: {response.status_code} - {response.text}')

    def delete_release(self, owner: str, repo: str, release_id: int) -> bool:
        """Delete a release by ID."""
        url = f'https://api.github.com/repos/{owner}/{repo}/releases/{release_id}'

        response = requests.delete(url, headers=self.headers)

        return response.status_code == 204

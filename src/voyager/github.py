#!/usr/bin/env python3

import os
import urllib3
from typing import Dict, List, Optional

import requests


class GitHubClient:
    """Client for interacting with GitHub API."""

    def __init__(
        self,
        api_url: Optional[str] = None,
        token: Optional[str] = None,
        required: bool = True,
        verifySSL=False,
    ):
        self.api_url = api_url or os.environ.get('GITHUB_API_URL')
        self.token = token or os.environ.get('GITHUB_TOKEN')
        self.is_authenticated = bool(self.token)
        self.verifySSL = verifySSL

        if not self.api_url:
            # Default to GitHub API URL if not provided
            # This is the public GitHub API URL
            # If you are using GitHub Enterprise, set GITHUB_API_URL environment variable
            # or provide it explicitly
            # Example: https://github.example.com/api/v3
            self.api_url = 'https://api.github.com'

        print(f'Using GitHub API URL: {self.api_url}')
        if not self.token and required:
            raise ValueError(
                'GitHub token not found. Please set GITHUB_TOKEN environment variable or '
                'provide it explicitly.'
            )

        self.headers = {
            'Accept': 'application/vnd.github.v3+json',
        }

        if self.token:
            self.headers['Authorization'] = f'token {self.token}'

        if not self.verifySSL:
            urllib3.disable_warnings()

    def get_latest_release(self, owner: str, repo: str) -> Dict:
        """Get the latest release from GitHub API."""
        url = f'{self.api_url}/repos/{owner}/{repo}/releases/latest'
        response = requests.get(url, verify=self.verifySSL, headers=self.headers)

        if response.status_code == 200:
            return response.json()
        else:
            err_msg = f'Failed to get latest release: {response.status_code} - {response.text}'
            raise Exception(err_msg)

    def get_releases(self, owner: str, repo: str) -> List[Dict]:
        """Get all releases for a repository."""
        url = f'{self.api_url}/repos/{owner}/{repo}/releases'
        response = requests.get(url, verify=self.verifySSL, headers=self.headers)
        if response.status_code == 200:
            return response.json()
        raise Exception(f'Failed to get releases: {response.status_code} - {response.text}')

    def delete_release(self, owner: str, repo: str, release_id: int) -> bool:
        """Delete a release by ID."""
        url = f'{self.api_url}/repos/{owner}/{repo}/releases/{release_id}'
        response = requests.delete(url, verify=self.verifySSL, headers=self.headers)
        if response.status_code == 204:
            return True
        self.error(f'Failed to delete release: {response.status_code} - {response.text}')
        return False

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
        url = f'{self.api_url}/repos/{owner}/{repo}/releases'

        payload = {
            'tag_name': tag_name,
            'name': name,
            'body': body,
            'draft': draft,
            'prerelease': prerelease,
        }

        response = requests.post(url, verify=self.verifySSL, headers=self.headers, json=payload)

        if response.status_code in (200, 201):
            return response.json()
        else:
            raise Exception(f'Failed to create release: {response.status_code} - {response.text}')

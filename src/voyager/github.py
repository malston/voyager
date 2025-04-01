#!/usr/bin/env python3

"""GitHub API client module for interacting with GitHub's API endpoints."""

import os
from typing import Dict, List, Optional

import requests
import urllib3


class GitHubClient:
    """Client for interacting with GitHub API.

    This client provides methods to interact with GitHub's API endpoints,
    including managing releases, authentication, and API configuration.
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        token: Optional[str] = None,
        required: bool = True,
        verify_ssl: bool = False,
    ) -> None:
        """Initialize the GitHub client.

        Args:
            api_url: Optional GitHub API URL. If not provided, uses GITHUB_API_URL env var
                    or defaults to https://api.github.com
            token: Optional GitHub API token. If not provided, uses GITHUB_TOKEN env var
            required: Whether token is required (defaults to True)
            verify_ssl: Whether to verify SSL certificates (defaults to False)
        """
        self.api_url = api_url or os.environ.get("GITHUB_API_URL")
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.is_authenticated = bool(self.token)
        self.verify_ssl = verify_ssl

        if not self.api_url:
            # Default to GitHub API URL if not provided
            # This is the public GitHub API URL
            # If you are using GitHub Enterprise, set GITHUB_API_URL environment variable
            # or provide it explicitly
            # Example: https://github.example.com/api/v3
            self.api_url = "https://api.github.com"

        print(f"Using GitHub API URL: {self.api_url}")
        if not self.token and required:
            raise ValueError(
                "GitHub token not found. Please set GITHUB_TOKEN environment variable or "
                "provide it explicitly."
            )

        self.headers = {
            "Accept": "application/vnd.github.v3+json",
        }

        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

        if not self.verify_ssl:
            urllib3.disable_warnings()

    def get_latest_release(self, owner: str, repo: str) -> Dict:
        """Get the latest release from GitHub API.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Dict containing release information

        Raises:
            Exception: If the API request fails
        """
        url = f"{self.api_url}/repos/{owner}/{repo}/releases/latest"
        response = requests.get(url, verify=self.verify_ssl, headers=self.headers, timeout=10)

        if response.status_code == 200:
            return response.json()
        err_msg = f"Failed to get latest release: {response.status_code} - {response.text}"
        raise requests.exceptions.HTTPError(err_msg)

    def get_releases(self, owner: str, repo: str, per_page: int = 30) -> List[Dict]:
        """Get all releases for a repository.

        Args:
            owner: Repository owner
            repo: Repository name
            per_page: Number of releases to return per page (default: 30)

        Returns:
            List of dictionaries containing release information

        Raises:
            requests.exceptions.HTTPError: If the API request fails
        """
        url = f"{self.api_url}/repos/{owner}/{repo}/releases"
        params = {"per_page": per_page}
        response = requests.get(
            url, verify=self.verify_ssl, headers=self.headers, params=params, timeout=10
        )
        if response.status_code == 200:
            return response.json()
        raise requests.exceptions.HTTPError(
            f"Failed to get releases: {response.status_code} - {response.text}"
        )

    def delete_release(self, owner: str, repo: str, release_id: int) -> None:
        """Delete a release by ID.

        Args:
            owner: Repository owner
            repo: Repository name
            release_id: ID of the release to delete

        Raises:
            Exception: If the API request fails
        """
        url = f"{self.api_url}/repos/{owner}/{repo}/releases/{release_id}"
        response = requests.delete(url, verify=self.verify_ssl, headers=self.headers, timeout=10)
        if response.status_code != 204:
            raise requests.exceptions.HTTPError(
                f"Failed to delete release: {response.status_code} - {response.text}"
            )

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
        """Create a new release on GitHub.

        Args:
            owner: Repository owner
            repo: Repository name
            tag_name: Git tag name for the release
            name: Release name
            body: Release description
            draft: Whether this is a draft release (defaults to False)
            prerelease: Whether this is a prerelease (defaults to False)

        Returns:
            Dict containing the created release information

        Raises:
            Exception: If the API request fails
        """
        url = f"{self.api_url}/repos/{owner}/{repo}/releases"

        payload = {
            "tag_name": tag_name,
            "name": name,
            "body": body,
            "draft": draft,
            "prerelease": prerelease,
        }

        response = requests.post(
            url, verify=self.verify_ssl, headers=self.headers, json=payload, timeout=10
        )

        if response.status_code in (200, 201):
            return response.json()

        raise requests.exceptions.HTTPError(
            f"Failed to create release: {response.status_code} - {response.text}"
        )

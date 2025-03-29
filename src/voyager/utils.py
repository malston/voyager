#!/usr/bin/env python3

import os
import re
import git
from typing import Tuple


def get_repo_info() -> Tuple[str, str]:
    """Extract owner and repo name from git remote URL."""
    try:
        repo = git.Repo(os.getcwd())
        for remote in repo.remotes:
            if remote.name == 'origin':
                url = next(remote.urls)
                # Handle SSH or HTTPS URL formats
                match = re.search(r'github\.com[:/]([^/]+)/([^/.]+)', url)
                if match:
                    return match.group(1), match.group(2)

        raise ValueError('Not a GitHub repository or missing origin remote')
    except (git.InvalidGitRepositoryError, git.NoSuchPathError):
        raise ValueError('Current directory is not a git repository')


def check_git_repo() -> bool:
    """Check if the current directory is a git repository."""
    try:
        git.Repo(os.getcwd())
        return True
    except (git.InvalidGitRepositoryError, git.NoSuchPathError):
        return False

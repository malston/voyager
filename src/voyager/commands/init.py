#!/usr/bin/env python3

import os
import sys
from pathlib import Path

import click
import yaml

from ..click_utils import CONTEXT_SETTINGS
from ..utils import check_git_repo, get_repo_info


@click.command('init', context_settings=CONTEXT_SETTINGS)
@click.option('--concourse-url', help='Concourse CI API URL')
@click.option('--concourse-team', help='Concourse CI team name')
@click.option('--pipeline', help='Concourse pipeline name')
def init_repo(concourse_url, concourse_team, pipeline):
    """Initialize the current repository for Voyager."""
    if not check_git_repo():
        click.echo('Error: Current directory is not a git repository', err=True)
        sys.exit(1)

    try:
        owner, repo = get_repo_info()
        click.echo(f'Initializing Voyager for {owner}/{repo}...')

        # Create .github directory if it doesn't exist
        github_dir = Path('.github')
        github_dir.mkdir(exist_ok=True)

        # Create ci directory if it doesn't exist
        ci_dir = Path('ci')
        ci_dir.mkdir(exist_ok=True)

        # Create workflows directory within .github if it doesn't exist
        workflows_dir = github_dir / 'workflows'
        workflows_dir.mkdir(exist_ok=True)

        # Check if GitHub token is set
        if not os.environ.get('GITHUB_TOKEN'):
            click.echo('Warning: GITHUB_TOKEN environment variable is not set.')
            click.echo(
                'You will need to set this before using Voyager commands that interact with GitHub.'
            )

        # Create GitHub Actions workflow file
        workflow_file = workflows_dir / 'voyager.yml'
        if not workflow_file.exists() or click.confirm(
            f'The file {workflow_file} already exists. Overwrite?'
        ):
            create_github_workflow(workflow_file)
            click.echo(f'✓ Created GitHub Actions workflow: {workflow_file}')

        # Copy and customize Concourse pipeline files
        if concourse_url and concourse_team:
            pipeline_name = pipeline or 'release-pipeline'

            # Copy pipeline.yml
            pipeline_file = ci_dir / 'pipeline.yml'
            if not pipeline_file.exists() or click.confirm(
                f'The file {pipeline_file} already exists. Overwrite?'
            ):
                create_concourse_pipeline(pipeline_file, owner, repo)
                click.echo(f'✓ Created Concourse pipeline configuration: {pipeline_file}')

            # Create set-pipeline.sh script
            set_pipeline_file = ci_dir / 'set-pipeline.sh'
            if not set_pipeline_file.exists() or click.confirm(
                f'The file {set_pipeline_file} already exists. Overwrite?'
            ):
                create_set_pipeline_script(
                    set_pipeline_file, concourse_url, concourse_team, pipeline_name, owner, repo
                )
                os.chmod(set_pipeline_file, 0o755)  # Make executable
                click.echo(f'✓ Created Concourse setup script: {set_pipeline_file}')

            # Check if Concourse token is set
            if not os.environ.get('CONCOURSE_TOKEN'):
                click.echo('Warning: CONCOURSE_TOKEN environment variable is not set.')
                click.echo(
                    'You will need to set this before using Voyager commands '
                    'that interact with Concourse CI.'
                )

        # Create .env.example file
        env_example_file = Path('.env.example')
        if not env_example_file.exists() or click.confirm(
            f'The file {env_example_file} already exists. Overwrite?'
        ):
            create_env_example(env_example_file, concourse_url is not None)
            click.echo(f'✓ Created environment variables example: {env_example_file}')

        # Add .env to .gitignore if not already there
        gitignore_file = Path('.gitignore')
        if gitignore_file.exists():
            with open(gitignore_file, 'r') as f:
                gitignore_content = f.read()

            if '.env' not in gitignore_content:
                with open(gitignore_file, 'a') as f:
                    f.write('\n# Environment variables\n.env\n')
                click.echo('✓ Added .env to .gitignore')

        # Create voyager.yml configuration file
        config_file = Path('voyager.yml')
        if not config_file.exists() or click.confirm(
            f'The file {config_file} already exists. Overwrite?'
        ):
            create_voyager_config(config_file, owner, repo, concourse_url, concourse_team, pipeline)
            click.echo(f'✓ Created Voyager configuration: {config_file}')

        click.echo('\nVoyager initialized successfully!')
        click.echo('\nNext steps:')
        click.echo('1. Review the created configuration files and customize as needed.')

        if concourse_url and concourse_team:
            click.echo('2. Set the CONCOURSE_TOKEN environment variable.')
            click.echo('3. Run the pipeline setup script: ./ci/set-pipeline.sh')

        click.echo(
            "4. Set the GITHUB_TOKEN environment variable with a token that has 'repo' scope."
        )
        click.echo('5. Try creating your first release: voyager release')

    except Exception as e:
        click.echo(f'Error initializing repository: {str(e)}', err=True)
        sys.exit(1)


def create_github_workflow(file_path):
    """Create a GitHub Actions workflow file for Voyager."""
    workflow_content = """name: Voyager Release Workflow

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.x'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install build twine
          if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
      - name: Build package
        run: python -m build
      - name: Publish to PyPI
        if: startsWith(github.ref, 'refs/tags/v')
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          password: ${{ secrets.PYPI_API_TOKEN }}
          skip-existing: true
"""
    with open(file_path, 'w') as f:
        f.write(workflow_content)


def create_concourse_pipeline(file_path, owner, repo):
    """Create a Concourse pipeline configuration file."""
    pipeline_content = f"""resource_types:
  - name: github-release
    type: registry-image
    source:
      repository: concourse/github-release-resource
      tag: latest

resources:
  - name: source-code
    type: git
    source:
      uri: https://github.com/{owner}/{repo}.git
      branch: main
  - name: github-release
    type: github-release
    source:
      owner: {owner}
      repository: {repo}
      access_token: ((github_token))

jobs:
  - name: build-and-release
    plan:
      - get: source-code
        trigger: false
      - task: build
        config:
          platform: linux
          image_resource:
            type: registry-image
            source: {{repository: python, tag: 3.9-slim}}
          inputs:
            - name: source-code
          outputs:
            - name: built-release
          params:
            VERSION: ((version))
          run:
            path: sh
            args:
              - -exc
              - |
                cd source-code
                echo "Building version ${{VERSION}}"
                pip install -e .
                python setup.py sdist bdist_wheel
                cp dist/* ../built-release/
      - put: github-release
        params:
          name: v((version))
          tag: v((version))
          globs: ["built-release/*.tar.gz", "built-release/*.whl"]

  - name: rollback
    plan:
      - get: source-code
        passed: [build-and-release]
      - task: prepare-rollback
        config:
          platform: linux
          image_resource:
            type: registry-image
            source: {{repository: python, tag: 3.9-slim}}
          inputs:
            - name: source-code
          outputs:
            - name: rollback-info
          params:
            VERSION: ((version))
            IS_ROLLBACK: ((is_rollback))
          run:
            path: sh
            args:
              - -exc
              - |
                if [ "${{IS_ROLLBACK}}" == "true" ]; then
                  echo "Executing rollback to version ${{VERSION}}"
                  # Add rollback-specific steps here
                  echo "${{VERSION}}" > rollback-info/rollback-version.txt
                  echo "Rollback prepared successfully"
                else
                  echo "Not a rollback operation, skipping"
                  exit 0
                fi
"""
    with open(file_path, 'w') as f:
        f.write(pipeline_content)


def create_set_pipeline_script(file_path, concourse_url, team, pipeline, owner, repo):
    """Create a script to set up the Concourse pipeline."""
    script_content = f"""#!/bin/bash
# Script to set the Concourse pipeline

if [ -z "$CONCOURSE_TOKEN" ]; then
    echo "Error: CONCOURSE_TOKEN environment variable is not set"
    exit 1
fi

if [ -z "$GITHUB_TOKEN" ]; then
    echo "Error: GITHUB_TOKEN environment variable is not set"
    exit 1
fi

# Concourse connection details
CONCOURSE_URL="{concourse_url}"
TEAM="{team}"
PIPELINE="{pipeline}"

# Repository details
REPO_NAME="{repo}"
OWNER="{owner}"

echo "Setting up Concourse pipeline for $OWNER/$REPO_NAME"

# Command to set the pipeline
fly -t $TEAM login -c $CONCOURSE_URL -n $TEAM
fly -t $TEAM set-pipeline -p $PIPELINE -c ci/pipeline.yml \\
   -v github_token=$GITHUB_TOKEN \\
   -v version="0.1.0"

echo "Pipeline setup complete."
"""
    with open(file_path, 'w') as f:
        f.write(script_content)


def create_env_example(file_path, include_concourse):
    """Create a .env.example file with required environment variables."""
    env_content = """# GitHub API token with 'repo' scope
GITHUB_TOKEN=your_github_token
"""

    if include_concourse:
        env_content += """
# Concourse CI token
CONCOURSE_TOKEN=your_concourse_token
"""

    with open(file_path, 'w') as f:
        f.write(env_content)


def create_voyager_config(
    file_path, owner, repo, concourse_url=None, concourse_team=None, pipeline=None
):
    """Create a voyager.yml configuration file."""
    config = {
        'repository': {'owner': owner, 'name': repo, 'default_branch': 'main'},
        'versioning': {'default_bump': 'patch'},
    }

    if concourse_url and concourse_team:
        config['concourse'] = {
            'url': concourse_url,
            'team': concourse_team,
            'pipeline': pipeline or 'release-pipeline',
            'release_job': 'build-and-release',
            'rollback_job': 'rollback',
        }

    with open(file_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)

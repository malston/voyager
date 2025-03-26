# Voyager - Developer Guide

## Overview

Voyager is a Python-based command-line tool designed to streamline GitHub release management workflows with Concourse CI integration. This guide provides detailed information for developers who want to use, modify, or contribute to the Voyager tool.

## Getting Started

### Prerequisites

- Python 3.6+
- pip (Python package manager)
- Git command-line tools
- GitHub personal access token with `repo` scope
- Concourse CI instance and access token
- `fly` CLI tool for Concourse interaction (optional, for pipeline management)

### Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/malston/voyager.git
   cd voyager
   ```

2. Install the package in development mode:

   ```bash
   pip install -e .
   ```

3. Set up required environment variables:

   ```bash
   export GITHUB_TOKEN=your_github_token
   export CONCOURSE_TOKEN=your_concourse_token
   ```

## Command Reference

### Initialize a Repository

```bash
voyager init --concourse-url https://concourse.example.com --concourse-team main --pipeline release-pipeline
```

### Creating Releases

```bash
# Create a patch release (0.0.x)
voyager release -t patch

# Create a minor release (0.x.0)
voyager release -t minor

# Create a major release (x.0.0)
voyager release -t major
```

### Listing Releases

```bash
# List the last 10 releases
voyager list

# List the last 5 releases
voyager list -l 5
```

### Rolling Back

```bash
# Interactive rollback (choose from a list)
voyager rollback

# Rollback to a specific tag
voyager rollback -t v1.2.3
```

### Deleting Releases

```bash
# Interactive delete (choose from a list)
voyager delete

# Delete a specific tag and release
voyager delete -t v1.2.3
```

### Monitoring Pipelines

```bash
# View pipeline builds
voyager pipelines --concourse-url https://concourse.example.com --concourse-team main --pipeline release-pipeline
```

## Extending Voyager

To add a new command:

1. Create a new Python module in the `voyager/commands` directory
2. Implement your command using Click
3. Import and register your command in `voyager/cli.py`

## Contributing

Contributions to Voyager are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

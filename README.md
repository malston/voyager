# Voyager

![img](./docs/img/voyager-logo.svg)

A Python-based command-line tool for managing GitHub releases with Concourse CI integration.

## Features

- Create GitHub releases with semantic versioning
- Run Concourse CI pipelines to build and publish releases
- Rollback to previous versions
- Delete releases and their associated tags
- View release history and pipeline status

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/voyager.git
cd voyager

# Install the package
pip install -e .
```

## Configuration

Set up your required environment variables:

```bash
export GITHUB_TOKEN=your_github_token
export CONCOURSE_TOKEN=your_concourse_token
```

## Usage

```bash
# Initialize a repository
voyager init 

# Create a release
voyager release -t minor -m "New feature release"

# List releases
voyager list 

# Rollback to a specific version
voyager rollback -t v1.2.3

# Delete a release
voyager delete -t v1.0.0
```

## Documentation

For more detailed information, refer to the [Developer Guide](docs/developer-guide.md).

## License

[MIT License](LICENSE)

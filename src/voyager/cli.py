#!/usr/bin/env python3

import click

from . import __version__
from .click_utils import CONTEXT_SETTINGS
from .commands.delete import delete_release
from .commands.init import init_repo
from .commands.list import list_releases
from .commands.pipelines import list_pipelines
from .commands.release import create_release
from .commands.rollback import rollback


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(version=__version__)
def cli():
    """Voyager - A tool for managing GitHub releases with Concourse CI pipelines."""
    pass


# Add commands to CLI group
cli.add_command(create_release)
cli.add_command(list_releases)
cli.add_command(rollback)
cli.add_command(delete_release)
cli.add_command(list_pipelines)
cli.add_command(init_repo)

if __name__ == '__main__':
    cli()

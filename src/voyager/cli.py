#!/usr/bin/env python3

import click

from . import __version__
from .click_utils import CONTEXT_SETTINGS
from .commands.delete import delete_release
from .commands.init import init_repo
from .commands.list import list_group
from .commands.release import create_release
from .commands.rollback import rollback


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(version=__version__)
@click.option('--quiet', '-q', is_flag=True, help='Suppress informational output')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.pass_context
def cli(ctx, quiet, verbose):
    """Voyager - A tool for managing GitHub releases with Concourse CI pipelines."""
    # Store global options in context for subcommands to access
    ctx.ensure_object(dict)
    ctx.obj['quiet'] = quiet
    ctx.obj['verbose'] = verbose
    pass


# Add commands to CLI group
cli.add_command(create_release)
cli.add_command(rollback)
cli.add_command(delete_release)
cli.add_command(init_repo)
cli.add_command(list_group)

if __name__ == '__main__':
    cli()

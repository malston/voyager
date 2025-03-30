#!/usr/bin/env python3

"""Shared Click utilities and settings for Voyager CLI."""

# Context settings to enable -h as a help option shortcut across all commands
# and ensure consistent POSIX-style help and error handling
CONTEXT_SETTINGS = dict(
    help_option_names=['-h', '--help'],
    max_content_width=80,
    auto_envvar_prefix='VOYAGER',
    show_default=True,
    terminal_width=80,
)

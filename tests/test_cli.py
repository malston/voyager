import pytest
from voyager import cli


def test_cli_version():
    assert hasattr(cli, 'cli')

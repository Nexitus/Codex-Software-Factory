"""Help/version entry point; source invocation falls back without distribution metadata."""
from __future__ import annotations

import argparse
from importlib.metadata import PackageNotFoundError, version


try:
    _VERSION = version("codex-software-factory")
except PackageNotFoundError:
    if __package__:
        from . import __version__ as _VERSION
    else:
        _VERSION = "0.6.0"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="software-factory",
        description="Command-line interface for Codex Software Factory.",
    )
    parser.add_argument("--version", action="version", version=_VERSION)
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Help/version and project initialization entry point."""
from __future__ import annotations

import argparse
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import sys


try:
    _VERSION = version("codex-software-factory")
except PackageNotFoundError:
    _VERSION = "0.6.0"

if __package__:
    from .project_setup import ALL_HARNESSES, initialize
else:
    from project_setup import ALL_HARNESSES, initialize


def main(argv: list[str] | None = None) -> int:
    cli_args = list(sys.argv[1:] if argv is None else argv)
    if cli_args[:1] == ["run"]:
        supervisor_args = cli_args[1:]
        if supervisor_args[:1] == ["--"]:
            supervisor_args = supervisor_args[1:]
        try:
            if __package__:
                from . import factory
            else:
                import factory
            return factory.main(supervisor_args)
        except SystemExit as error:
            return int(error.code or 0)
        except (ImportError, OSError, ValueError) as error:
            print(f"software-factory run: BLOCKED: {error}", file=sys.stderr)
            return 2
    parser = argparse.ArgumentParser(
        prog="software-factory",
        description="Command-line interface for Codex Software Factory.",
    )
    parser.add_argument("--version", action="version", version=_VERSION)
    commands = parser.add_subparsers(dest="command")
    init = commands.add_parser("init", help="initialize an existing Git checkout")
    init.add_argument("--project", type=Path, default=Path.cwd(), help="checkout to initialize")
    init.add_argument("--harness", choices=ALL_HARNESSES, action="append",
                      help="install a selected host skill (repeatable; defaults to all)")
    commands.add_parser("run", help="run the supervised workflow")
    args = parser.parse_args(cli_args)
    if args.command == "init":
        try:
            written = initialize(args.project, args.harness or list(ALL_HARNESSES))
        except (OSError, ValueError) as error:
            print(f"software-factory init: {error}", file=sys.stderr)
            return 2
        if written:
            print("Initialized project files:")
            for path in written:
                print(path)
        else:
            print("Project already initialized; no changes made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

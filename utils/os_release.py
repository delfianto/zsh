#!/usr/bin/env python3

"""Render freedesktop os-release metadata as readable text or JSON."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from collections.abc import Mapping, Sequence
from typing import NoReturn, cast


class OsReleaseError(RuntimeError):
    """A user-facing failure that does not need a Python traceback."""


def fail(message: str) -> NoReturn:
    raise OsReleaseError(message)


def read_os_release() -> dict[str, str]:
    """Read and normalize os-release using Python's freedesktop parser."""
    try:
        release = platform.freedesktop_os_release()
    except OSError as error:
        fail(f"could not read os-release metadata: {error}")
    return {key.lower(): value for key, value in release.items()}


def render_shell(release: Mapping[str, str]) -> str:
    """Render the repository's established sorted `key: value` format."""
    return "\n".join(f"{key}: {release[key]}" for key in sorted(release))


def render_json(release: Mapping[str, str]) -> str:
    """Render stable UTF-8 JSON without relying on jq."""
    return json.dumps(release, ensure_ascii=False, indent=2, sort_keys=True)


def parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser(
        prog="os-release",
        description="Show freedesktop operating-system metadata.",
    )
    _ = argument_parser.add_argument(
        "format",
        nargs="?",
        choices=("shell", "json"),
        help="output format (default: shell)",
    )
    format_group = argument_parser.add_mutually_exclusive_group()
    _ = format_group.add_argument(
        "-s",
        "--shell",
        dest="format_flag",
        action="store_const",
        const="shell",
        help="emit sorted key: value lines",
    )
    _ = format_group.add_argument(
        "-j",
        "--json",
        dest="format_flag",
        action="store_const",
        const="json",
        help="emit formatted JSON",
    )
    return argument_parser


def output_format(
    arguments: argparse.Namespace, argument_parser: argparse.ArgumentParser
) -> str:
    positional = cast(str | None, arguments.format)
    flag = cast(str | None, arguments.format_flag)
    if positional is not None and flag is not None:
        argument_parser.error("choose either a format argument or a format flag")
    return flag or positional or "shell"


def main(argv: Sequence[str] | None = None) -> int:
    argument_parser = parser()
    arguments = argument_parser.parse_args(argv)
    selected_format = output_format(arguments, argument_parser)

    try:
        release = read_os_release()
        output = (
            render_json(release) if selected_format == "json" else render_shell(release)
        )
        print(output)
        return 0
    except OsReleaseError as error:
        print(f"os-release: {error}", file=sys.stderr)
        return 1
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3

"""Manage project virtual environments without requiring prior activation."""

from __future__ import annotations

import argparse
import keyword
import os
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import NoReturn, cast
from venv import EnvBuilder

import tomllib

EXCLUDED_DIRECTORIES = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
}
TomlTable = dict[str, object]


class VenvToolError(RuntimeError):
    """A user-facing failure that does not need a Python traceback."""


def fail(message: str) -> NoReturn:
    raise VenvToolError(message)


def environment_path(
    explicit: Path | None,
    *,
    cwd: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Select an explicit environment, then the active one, then .venv."""
    if explicit is not None:
        return explicit.expanduser().absolute()
    environment = os.environ if environ is None else environ
    active = environment.get("VIRTUAL_ENV")
    if active:
        return Path(active).expanduser().absolute()
    working_directory = Path.cwd() if cwd is None else cwd
    return (working_directory / ".venv").absolute()


def environment_python(environment: Path) -> Path:
    python = environment / "bin" / "python"
    if not python.is_file() or not os.access(python, os.X_OK):
        fail(f"virtual environment interpreter not found: {python}")
    return python


def run_command(command: Sequence[str]) -> int:
    try:
        return subprocess.run(command, check=False).returncode
    except OSError as error:
        fail(f"could not execute {command[0]}: {error}")


def capture(command: Sequence[str]) -> str:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        fail(f"could not execute {command[0]}: {error}")
    if result.returncode:
        detail = result.stderr.strip() or f"exit status {result.returncode}"
        fail(f"{' '.join(command)} failed: {detail}")
    return result.stdout.strip()


def module_available(python: Path, module: str) -> bool:
    code = "import importlib.util,sys;sys.exit(importlib.util.find_spec(sys.argv[1]) is None)"
    try:
        result = subprocess.run(
            (str(python), "-c", code, module),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return False
    return result.returncode == 0


def as_table(value: object, label: str) -> TomlTable:
    if not isinstance(value, dict):
        fail(f"{label} must be a TOML table")
    mapping = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in mapping):
        fail(f"{label} contains a non-string key")
    return cast(TomlTable, mapping)


def load_pyproject(path: Path) -> TomlTable:
    if not path.is_file():
        fail(f"pyproject.toml not found: {path}")
    try:
        with path.open("rb") as pyproject_file:
            raw = cast(object, tomllib.load(pyproject_file))
    except OSError as error:
        fail(f"could not read {path}: {error}")
    except tomllib.TOMLDecodeError as error:
        fail(f"invalid TOML in {path}: {error}")
    return as_table(raw, str(path))


def development_sources(pyproject: TomlTable) -> tuple[bool, bool]:
    """Return whether dev is declared as an optional extra and dependency group."""
    has_extra = False
    project_value = pyproject.get("project")
    if project_value is not None:
        project = as_table(project_value, "project")
        optional_value = project.get("optional-dependencies")
        if optional_value is not None:
            optional = as_table(optional_value, "project.optional-dependencies")
            has_extra = "dev" in optional

    has_group = False
    groups_value = pyproject.get("dependency-groups")
    if groups_value is not None:
        groups = as_table(groups_value, "dependency-groups")
        has_group = "dev" in groups
    return has_extra, has_group


def pip_supports_groups(python: Path) -> bool:
    if not module_available(python, "pip"):
        return False
    return "--group" in capture((str(python), "-m", "pip", "install", "--help"))


def dependency_command(
    python: Path,
    *,
    uv: str | None,
    install_dev: bool,
    has_dev_extra: bool,
    has_dev_group: bool,
    pip_has_groups: bool,
) -> list[str]:
    target = ".[dev]" if install_dev and has_dev_extra else "."
    if uv is not None:
        command = [uv, "pip", "install", "--python", str(python), "-e", target]
    else:
        command = [str(python), "-m", "pip", "install", "-e", target]

    if install_dev and has_dev_group:
        if uv is None and not pip_has_groups:
            message = "this project's dev dependencies use dependency-groups, "
            message += "but the selected environment's pip lacks --group support; "
            fail(message + "install uv or upgrade pip")
        command.extend(("--group", "dev"))
    return command


def create_environment(path: Path) -> int:
    environment = path.expanduser().absolute()
    if environment.exists():
        fail(f"virtual environment already exists: {environment}")
    print(f"Creating virtual environment: {environment}")
    try:
        EnvBuilder(with_pip=True).create(environment)
    except (OSError, subprocess.SubprocessError) as error:
        fail(f"could not create virtual environment: {error}")
    print(f"Created virtual environment: {environment}")
    print(f"Activate it with: venv load {environment}")
    return 0


def install_dependencies(environment: Path, install_dev: bool) -> int:
    python = environment_python(environment)
    pyproject = load_pyproject(Path.cwd() / "pyproject.toml")
    has_dev_extra, has_dev_group = development_sources(pyproject)
    if install_dev and not (has_dev_extra or has_dev_group):
        message = "pyproject.toml defines neither "
        fail(message + "project.optional-dependencies.dev nor dependency-groups.dev")

    uv = shutil.which("uv")
    pip_has_groups = False if uv is not None else pip_supports_groups(python)
    if uv is None and not module_available(python, "pip"):
        fail(f"pip is not installed in {environment}")

    command = dependency_command(
        python,
        uv=uv,
        install_dev=install_dev,
        has_dev_extra=has_dev_extra,
        has_dev_group=has_dev_group,
        pip_has_groups=pip_has_groups,
    )
    installer = "uv" if uv is not None else "pip"
    scope = "project and development dependencies" if install_dev else "project"
    print(f"Installing {scope} into {environment} with {installer}")
    return run_command(command)


def check_environment(environment: Path) -> int:
    python = environment_python(environment)
    version = capture((str(python), "--version"))
    active_value = os.environ.get("VIRTUAL_ENV")
    active = active_value is not None and Path(active_value).absolute() == environment
    print("Virtual environment: active" if active else "Virtual environment: available")
    print(f"Path: {environment}")
    print(f"Python: {python}")
    print(f"Version: {version}")
    return 0


def valid_module_parts(parts: Sequence[str]) -> bool:
    return all(part.isidentifier() and not keyword.iskeyword(part) for part in parts)


def detect_app_path(directory: Path, max_depth: int = 3) -> tuple[Path, str] | None:
    candidates: list[tuple[Path, tuple[str, ...]]] = []
    try:
        paths = directory.rglob("main.py")
        for path in paths:
            relative = path.relative_to(directory)
            if len(relative.parts) > max_depth:
                continue
            if any(part in EXCLUDED_DIRECTORIES for part in relative.parts[:-1]):
                continue
            module_parts = relative.with_suffix("").parts
            if not valid_module_parts(module_parts):
                continue
            candidates.append((relative, module_parts))
    except OSError as error:
        fail(f"could not search for main.py: {error}")

    if not candidates:
        return None
    relative, module_parts = min(
        candidates,
        key=lambda candidate: (
            len(candidate[0].parts),
            candidate[0].as_posix().casefold(),
        ),
    )
    return relative, f"{'.'.join(module_parts)}:app"


def run_server(
    environment: Path,
    app: str | None,
    host: str,
    port: int,
    reload_enabled: bool,
    passthrough: Sequence[str],
) -> int:
    python = environment_python(environment)
    if not module_available(python, "uvicorn"):
        fail(f"uvicorn is not installed in {environment}")
    if not 1 <= port <= 65535:
        fail(f"invalid port: {port}")

    selected_app = app
    if selected_app is None:
        detected = detect_app_path(Path.cwd())
        if detected is None:
            selected_app = "main:app"
            print("No valid main.py found within three levels; using main:app")
        else:
            path, selected_app = detected
            print(f"Auto-detected {path} -> {selected_app}")

    command = [
        str(python),
        "-m",
        "uvicorn",
        selected_app,
        "--host",
        host,
        "--port",
        str(port),
    ]
    if reload_enabled:
        command.append("--reload")
    command.extend(passthrough)
    print(f"Starting uvicorn from {environment}: {selected_app}")
    return run_command(command)


def run_tests(environment: Path, passthrough: Sequence[str]) -> int:
    python = environment_python(environment)
    if not module_available(python, "pytest"):
        fail(f"pytest is not installed in {environment}")
    command = [str(python), "-m", "pytest"]
    if (Path.cwd() / "tests").is_dir():
        command.append("tests")
    command.append("-v")
    command.extend(passthrough)
    return run_command(command)


def add_environment_argument(command_parser: argparse.ArgumentParser) -> None:
    _ = command_parser.add_argument(
        "--venv",
        type=Path,
        metavar="PATH",
        help="environment path (default: active environment, then .venv)",
    )


def parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser(
        prog="venv",
        description="Manage project virtual environments without requiring activation.",
    )
    subparsers = argument_parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="create a virtual environment")
    _ = init_parser.add_argument(
        "path", nargs="?", type=Path, default=Path(".venv"), help="default: .venv"
    )

    deps_parser = subparsers.add_parser(
        "deps", help="install the current pyproject into an environment"
    )
    add_environment_argument(deps_parser)
    _ = deps_parser.add_argument(
        "--dev", action="store_true", help="include the dev extra and/or group"
    )

    check_parser = subparsers.add_parser("check", help="inspect an environment")
    add_environment_argument(check_parser)

    run_parser = subparsers.add_parser("run", help="run a Uvicorn application")
    add_environment_argument(run_parser)
    _ = run_parser.add_argument("app", nargs="?", help="ASGI app, e.g. src.main:app")
    _ = run_parser.add_argument(
        "--host", default=os.environ.get("VENV_HOST", "127.0.0.1")
    )
    _ = run_parser.add_argument(
        "--port", type=int, default=os.environ.get("VENV_PORT", "8000")
    )
    _ = run_parser.add_argument(
        "--reload",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="enable or disable Uvicorn reload (default: enabled)",
    )

    test_parser = subparsers.add_parser("test", help="run pytest")
    add_environment_argument(test_parser)
    _ = subparsers.add_parser("help", help="show this help")
    return argument_parser


def split_passthrough(argv: Sequence[str]) -> tuple[list[str], list[str]]:
    arguments = list(argv)
    if "--" not in arguments:
        return arguments, []
    separator = arguments.index("--")
    return arguments[:separator], arguments[separator + 1 :]


def main(argv: Sequence[str] | None = None) -> int:
    raw_arguments = list(sys.argv[1:] if argv is None else argv)
    own_arguments, passthrough = split_passthrough(raw_arguments)
    argument_parser = parser()
    arguments = argument_parser.parse_args(own_arguments)
    command = cast(str | None, arguments.command)

    if command is None:
        argument_parser.print_help()
        return 1
    if passthrough and command not in {"run", "test"}:
        argument_parser.error(
            "-- passthrough arguments are supported only by run and test"
        )

    try:
        if command == "init":
            return create_environment(cast(Path, arguments.path))
        if command == "deps":
            environment = environment_path(cast(Path | None, arguments.venv))
            return install_dependencies(environment, cast(bool, arguments.dev))
        if command == "check":
            return check_environment(
                environment_path(cast(Path | None, arguments.venv))
            )
        if command == "run":
            environment = environment_path(cast(Path | None, arguments.venv))
            return run_server(
                environment,
                cast(str | None, arguments.app),
                cast(str, arguments.host),
                cast(int, arguments.port),
                cast(bool, arguments.reload),
                passthrough,
            )
        if command == "test":
            environment = environment_path(cast(Path | None, arguments.venv))
            return run_tests(environment, passthrough)
        if command == "help":
            argument_parser.print_help()
            return 0
        fail(f"unsupported command: {command}")
    except VenvToolError as error:
        print(f"venv: {error}", file=sys.stderr)
        return 1
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

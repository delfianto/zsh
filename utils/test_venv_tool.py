"""Regression tests for the virtual-environment management utility."""

import tempfile
import unittest
from pathlib import Path

from utils import venv_tool


class EnvironmentResolutionTest(unittest.TestCase):
    def test_environment_precedence(self) -> None:
        cwd = Path("/project")
        active = "/active/environment"

        self.assertEqual(
            venv_tool.environment_path(
                Path("custom"), cwd=cwd, environ={"VIRTUAL_ENV": active}
            ),
            Path("custom").absolute(),
        )
        self.assertEqual(
            venv_tool.environment_path(None, cwd=cwd, environ={"VIRTUAL_ENV": active}),
            Path(active),
        )
        self.assertEqual(
            venv_tool.environment_path(None, cwd=cwd, environ={}),
            cwd / ".venv",
        )

    def test_environment_python_requires_an_executable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            environment = Path(temporary_directory)
            python = environment / "bin" / "python"
            python.parent.mkdir()
            _ = python.write_text("#!/bin/sh\n", encoding="utf-8")

            with self.assertRaisesRegex(
                venv_tool.VenvToolError, "interpreter not found"
            ):
                _ = venv_tool.environment_python(environment)

            python.chmod(0o755)
            self.assertEqual(venv_tool.environment_python(environment), python)


class DependenciesTest(unittest.TestCase):
    def test_development_sources_support_extras_and_groups(self) -> None:
        pyproject: venv_tool.TomlTable = {
            "project": {"optional-dependencies": {"dev": ["pytest"]}},
            "dependency-groups": {"dev": ["ruff"]},
        }

        self.assertEqual(venv_tool.development_sources(pyproject), (True, True))

    def test_uv_command_targets_exact_interpreter_and_both_dev_sources(self) -> None:
        command = venv_tool.dependency_command(
            Path("/project/.venv/bin/python"),
            uv="/usr/bin/uv",
            install_dev=True,
            has_dev_extra=True,
            has_dev_group=True,
            pip_has_groups=False,
        )

        self.assertEqual(
            command,
            [
                "/usr/bin/uv",
                "pip",
                "install",
                "--python",
                "/project/.venv/bin/python",
                "-e",
                ".[dev]",
                "--group",
                "dev",
            ],
        )

    def test_old_pip_rejects_dependency_groups(self) -> None:
        with self.assertRaisesRegex(venv_tool.VenvToolError, "lacks --group"):
            _ = venv_tool.dependency_command(
                Path("/project/.venv/bin/python"),
                uv=None,
                install_dev=True,
                has_dev_extra=False,
                has_dev_group=True,
                pip_has_groups=False,
            )


class AppDetectionTest(unittest.TestCase):
    def test_detection_prefers_depth_and_skips_invalid_modules(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            for relative in (
                ".venv/main.py",
                "bad-name/main.py",
                "src/main.py",
                "a/b/main.py",
            ):
                path = project / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()

            detected = venv_tool.detect_app_path(project)

        self.assertEqual(detected, (Path("src/main.py"), "src.main:app"))

    def test_detection_uses_alphabetical_tiebreaker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            for relative in ("zeta/main.py", "alpha/main.py"):
                path = project / relative
                path.parent.mkdir(parents=True)
                path.touch()

            detected = venv_tool.detect_app_path(project)

        self.assertEqual(detected, (Path("alpha/main.py"), "alpha.main:app"))

    def test_passthrough_requires_separator_and_preserves_arguments(self) -> None:
        own, passthrough = venv_tool.split_passthrough(
            ["test", "--venv", ".venv", "--", "-k", "unit and not slow"]
        )

        self.assertEqual(own, ["test", "--venv", ".venv"])
        self.assertEqual(passthrough, ["-k", "unit and not slow"])


if __name__ == "__main__":
    _ = unittest.main()

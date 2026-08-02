"""Regression tests for the stdlib os-release utility."""

import io
import json
import platform
import unittest
from contextlib import redirect_stderr, redirect_stdout
from typing import ClassVar
from unittest import mock

from utils import os_release


class OsReleaseTest(unittest.TestCase):
    release: ClassVar[dict[str, str]] = {
        "PRETTY_NAME": 'Example "Linux"',
        "ID": "example",
        "ANSI_COLOR": "1;34",
    }

    def test_read_os_release_normalizes_keys(self) -> None:
        with mock.patch.object(
            platform,
            "freedesktop_os_release",
            return_value=self.release,
        ):
            result = os_release.read_os_release()

        self.assertEqual(
            result,
            {
                "ansi_color": "1;34",
                "id": "example",
                "pretty_name": 'Example "Linux"',
            },
        )

    def test_default_output_is_sorted_shell_format(self) -> None:
        stdout = io.StringIO()
        with (
            mock.patch.object(os_release, "read_os_release", return_value=self.release),
            redirect_stdout(stdout),
        ):
            status = os_release.main([])

        self.assertEqual(status, 0)
        self.assertEqual(
            stdout.getvalue(),
            'ANSI_COLOR: 1;34\nID: example\nPRETTY_NAME: Example "Linux"\n',
        )

    def test_json_flag_uses_stdlib_escaping(self) -> None:
        stdout = io.StringIO()
        with (
            mock.patch.object(os_release, "read_os_release", return_value=self.release),
            redirect_stdout(stdout),
        ):
            status = os_release.main(["--json"])

        self.assertEqual(status, 0)
        self.assertEqual(json.loads(stdout.getvalue()), self.release)

    def test_read_failure_has_no_traceback(self) -> None:
        stderr = io.StringIO()
        with (
            mock.patch.object(
                platform,
                "freedesktop_os_release",
                side_effect=OSError("missing"),
            ),
            redirect_stderr(stderr),
        ):
            status = os_release.main([])

        self.assertEqual(status, 1)
        self.assertEqual(
            stderr.getvalue(),
            "os-release: could not read os-release metadata: missing\n",
        )


if __name__ == "__main__":
    _ = unittest.main()

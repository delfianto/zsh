#!/usr/bin/env python3
"""Generate the NVIDIA container device interface configuration."""

import os
import shutil
import subprocess
import sys


def main() -> int:
    command = ["nvidia-ctk", "cdi", "generate", "--output=/etc/cdi/nvidia.yaml"]
    try:
        if sys.argv[1:2] == ["--sudo"]:
            if shutil.which("nvidia-ctk") is None:
                print("nvidia-ctk is not installed.", file=sys.stderr)
                return 1
            command.insert(0, "sudo")
            mkdir = subprocess.run(["sudo", "mkdir", "-p", "/etc/cdi"], check=False)
            if mkdir.returncode:
                return (
                    mkdir.returncode if mkdir.returncode > 0 else 128 - mkdir.returncode
                )
        os.execvp(command[0], command)
    except FileNotFoundError:
        print(f"nvidia-cdi: {command[0]} is not installed.", file=sys.stderr)
        return 127
    except OSError as error:
        print(f"nvidia-cdi: {error}", file=sys.stderr)
        return 126


if __name__ == "__main__":
    sys.exit(main())

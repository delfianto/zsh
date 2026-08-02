#!/usr/bin/env python3

"""Inspect Linux PCI IOMMU groups and their attached USB controllers.

The implementation intentionally uses only the Python standard library. It
still delegates PCI and USB name lookup to pciutils/usbutils: duplicating those
system databases here would merely exchange Zsh sorcery for Python cosplay.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn, cast

DEFAULT_RULES = """\
# Cleanup rules for `iommu group`, applied to each device description.
#
# Format:  'text to find'='replacement'
#
# Matching is a plain literal substring replacement, NOT a regex or glob --
# every character is taken as-is. Rules are applied in the order listed, so
# put the specific ones before the general ones.
#
# Trailing PCI revision markers -- " (rev a1)" -- and redundant whitespace are
# stripped automatically; you do not need rules for those.

# Vendor name cleanup
'Advanced Micro Devices, Inc. [AMD]'='AMD'
'NVIDIA Corporation'='NVIDIA'
'Shenzhen Longsys Electronics Co., Ltd.'=''
'Realtek Semiconductor Co., Ltd.'='Realtek'
'ASMedia Technology Inc.'='ASMedia'
'Phison Electronics Corporation'='Phison'
'Qualcomm Technologies, Inc'='Qualcomm'

# Specific device name cleanup
'Raphael/Granite Ridge'='Zen 5'
'Family 19h'='Zen 5'
'600 Series Chipset'='X870E'
'800 Series Chipset'='X870E'
'Technology Inc.'=''
'Corporation'=''
"""

RULE_RE = re.compile(r"^'([^']*)'='([^']*)'$")
REVISION_RE = re.compile(r"\s+\(rev [0-9a-f]+\)$", re.IGNORECASE)


class IommuError(RuntimeError):
    """A user-facing failure that does not need a Python traceback."""


@dataclass(frozen=True)
class Rule:
    find: str
    replacement: str


@dataclass(frozen=True)
class PciDevice:
    address: str
    description: str | None


@dataclass(frozen=True)
class IommuGroup:
    number: str
    devices: tuple[PciDevice, ...]


@dataclass(frozen=True)
class UsbController:
    bus: str
    controller: str
    group: str | None
    devices: tuple[str, ...]


def fail(message: str) -> NoReturn:
    raise IommuError(message)


def require_command(name: str) -> str:
    command = shutil.which(name)
    if command is None:
        fail(f"required command not found: {name}")
    return command


def capture(command: Sequence[str]) -> str:
    """Run a data-provider command and return stdout with useful errors."""
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
    return result.stdout


def ensure_rules_file(path: Path) -> None:
    """Create the editable default cleanup rules without overwriting a race."""
    if path.exists():
        return

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as rules_file:
            _ = rules_file.write(DEFAULT_RULES)
    except FileExistsError:
        return
    except OSError as error:
        fail(f"could not create cleanup rules at {path}: {error}")

    print(f"Created default cleanup rules at {path}", file=sys.stderr)


def load_rules(path: Path) -> tuple[Rule, ...]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        fail(f"could not read cleanup rules from {path}: {error}")

    rules: list[Rule] = []
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        match = RULE_RE.fullmatch(line)
        if match is None:
            fail(
                f"invalid cleanup rule at {path}:{line_number}: expected 'text to find'='replacement'"
            )
        if not match.group(1):
            fail(f"invalid cleanup rule at {path}:{line_number}: search text is empty")
        rules.append(Rule(match.group(1), match.group(2)))

    return tuple(rules)


def clean_description(description: str, rules: Sequence[Rule]) -> str:
    """Remove the PCI class, apply literal rules, and normalize the result."""
    _, separator, device_name = description.partition(": ")
    cleaned = device_name if separator else description
    for rule in rules:
        cleaned = cleaned.replace(rule.find, rule.replacement)
    cleaned = REVISION_RE.sub("", cleaned)
    return " ".join(cleaned.split())


def pci_descriptions() -> dict[str, str]:
    lspci = require_command("lspci")
    descriptions: dict[str, str] = {}
    for line in capture((lspci, "-D")).splitlines():
        address, separator, description = line.partition(" ")
        if separator:
            descriptions[address] = description
    return descriptions


def numeric_name(path: Path) -> tuple[int, int | str]:
    match = re.search(r"(\d+)$", path.name)
    return (0, int(match.group(1))) if match else (1, path.name)


def collect_groups(sysfs_root: Path, rules: Sequence[Rule]) -> tuple[IommuGroup, ...]:
    descriptions = pci_descriptions()
    groups_root = sysfs_root / "kernel" / "iommu_groups"
    if not groups_root.is_dir():
        fail(f"IOMMU group directory not found: {groups_root}")

    groups: list[IommuGroup] = []
    for group_path in sorted(
        (path for path in groups_root.iterdir() if path.is_dir()), key=numeric_name
    ):
        devices_root = group_path / "devices"
        device_paths = sorted(devices_root.iterdir()) if devices_root.is_dir() else []
        devices: list[PciDevice] = []
        for device_path in device_paths:
            address = device_path.name
            raw_description = descriptions.get(address)
            description = (
                clean_description(raw_description, rules)
                if raw_description is not None
                else None
            )
            devices.append(PciDevice(address, description))
        groups.append(IommuGroup(group_path.name, tuple(devices)))

    return tuple(groups)


def group_payload(groups: Sequence[IommuGroup]) -> list[dict[str, object]]:
    return [
        {
            "group": group.number,
            "devices": [
                {"address": device.address, "description": device.description}
                for device in group.devices
            ],
        }
        for group in groups
    ]


def print_groups(groups: Sequence[IommuGroup], as_json: bool) -> None:
    if as_json:
        json.dump(group_payload(groups), sys.stdout, indent=2)
        print()
        return

    for group in groups:
        print(f"IOMMU Group {group.number}:")
        for device in group.devices:
            description = device.description or "No device info found"
            print(f" - {device.address} {description}")
        print()


def read_text(path: Path, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as error:
        fail(f"could not read {label} from {path}: {error}")


def collect_usb(sysfs_root: Path) -> tuple[UsbController, ...]:
    lsusb = require_command("lsusb")
    usb_root = sysfs_root / "bus" / "usb" / "devices"
    if not usb_root.is_dir():
        fail(f"USB device directory not found: {usb_root}")

    controllers: list[UsbController] = []
    usb_paths = sorted(usb_root.glob("usb*"), key=numeric_name)
    for usb_path in usb_paths:
        bus = read_text(usb_path / "busnum", "USB bus number")
        try:
            controller_path = usb_path.resolve(strict=True).parent
        except OSError as error:
            fail(f"could not resolve USB controller {usb_path}: {error}")

        group_link = controller_path / "iommu_group"
        group = group_link.resolve().name if group_link.exists() else None
        devices = tuple(
            line for line in capture((lsusb, "-s", f"{bus}:")).splitlines() if line
        )
        controllers.append(UsbController(bus, controller_path.name, group, devices))

    return tuple(controllers)


def usb_payload(controllers: Sequence[UsbController]) -> list[dict[str, object]]:
    return [
        {
            "bus": controller.bus,
            "controller": controller.controller,
            "group": controller.group,
            "devices": list(controller.devices),
        }
        for controller in controllers
    ]


def print_usb(controllers: Sequence[UsbController], as_json: bool) -> None:
    if as_json:
        json.dump(usb_payload(controllers), sys.stdout, indent=2)
        print()
        return

    for controller in controllers:
        group = controller.group or "none"
        print(f"Bus {controller.bus} --> {controller.controller} (IOMMU group {group})")
        if controller.devices:
            print(*controller.devices, sep="\n")
        print()


def show_pci(address: str) -> int:
    sudo = require_command("sudo")
    lspci = require_command("lspci")
    try:
        return subprocess.run(
            (sudo, lspci, "-vv", "-s", address), check=False
        ).returncode
    except OSError as error:
        fail(f"could not execute lspci: {error}")


def default_rules_path() -> Path:
    config_home = os.environ.get("XDG_CONFIG_HOME")
    if config_home:
        return Path(config_home) / "iommu_cleanup_rules"
    return Path.home() / ".config" / "iommu_cleanup_rules"


def parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser(
        prog="iommu",
        description="Inspect Linux PCI IOMMU groups and USB controllers.",
    )
    _ = argument_parser.add_argument(
        "--sysfs-root",
        type=Path,
        default=Path("/sys"),
        metavar="PATH",
        help=argparse.SUPPRESS,
    )
    subparsers = argument_parser.add_subparsers(dest="command")

    pci_parser = subparsers.add_parser(
        "pci", aliases=("p",), help="show verbose PCI information for one address"
    )
    _ = pci_parser.add_argument("address", help="PCI address understood by lspci")

    group_parser = subparsers.add_parser(
        "group", aliases=("g",), help="list IOMMU groups and their PCI devices"
    )
    _ = group_parser.add_argument(
        "--rules",
        type=Path,
        default=default_rules_path(),
        metavar="PATH",
        help="description cleanup rules (default: %(default)s)",
    )
    _ = group_parser.add_argument(
        "--json", action="store_true", help="emit structured JSON"
    )

    usb_parser = subparsers.add_parser(
        "usb", aliases=("u",), help="list USB buses and their IOMMU controllers"
    )
    _ = usb_parser.add_argument(
        "--json", action="store_true", help="emit structured JSON"
    )
    return argument_parser


def run_pci(arguments: argparse.Namespace) -> int:
    return show_pci(cast(str, arguments.address))


def run_group(arguments: argparse.Namespace) -> int:
    rules_path = cast(Path, arguments.rules).expanduser()
    sysfs_root = cast(Path, arguments.sysfs_root)
    as_json = cast(bool, arguments.json)
    ensure_rules_file(rules_path)
    rules = load_rules(rules_path)
    print_groups(collect_groups(sysfs_root, rules), as_json)
    return 0


def run_usb(arguments: argparse.Namespace) -> int:
    sysfs_root = cast(Path, arguments.sysfs_root)
    as_json = cast(bool, arguments.json)
    print_usb(collect_usb(sysfs_root), as_json)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    argument_parser = parser()
    arguments = argument_parser.parse_args(argv)
    command = cast(str | None, arguments.command)
    if command is None:
        argument_parser.print_help()
        return 0

    try:
        if command in {"pci", "p"}:
            return run_pci(arguments)
        if command in {"group", "g"}:
            return run_group(arguments)
        if command in {"usb", "u"}:
            return run_usb(arguments)
        fail(f"unsupported command: {command}")
    except IommuError as error:
        print(f"iommu: {error}", file=sys.stderr)
        return 1
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

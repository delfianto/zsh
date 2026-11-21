#!/usr/bin/env python3
"""Display a grouped snapshot of lm-sensors readings."""

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tomllib
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from itertools import zip_longest
from pathlib import Path
from textwrap import wrap
from typing import cast

SensorValue = float | None
SensorFields = dict[str, SensorValue]
SensorChip = dict[str, str | SensorFields]
SensorData = dict[str, SensorChip]
Row = tuple[str, ...]
Sections = dict[str, list[Row]]
Panel = tuple[str, list[Row]]

READING = re.compile(r"([a-z]+)\d+_(input|average)$")
PWM = re.compile(r"pwm\d+$")
PCI_ADDRESS = re.compile(r"([0-9a-f]{4}):([0-9a-f]{2}):([0-9a-f]{2})\.([0-7])")
NUMERIC_VALUE = re.compile(r"^([+-]?[0-9]+)(?:\.[0-9]+)?(?=\s|%|$)")
UNAVAILABLE = re.compile(r"ERROR: Can't get value of subfeature \w+: Can't read")
UNITS = {
    "temp": (".1f", " °C"),
    "in": (".3f", " V"),
    "fan": (".0f", " RPM"),
    "pwm": (".0f", "%"),
    "power": (".2f", " W"),
    "energy": (".0f", " J"),
    "curr": (".2f", " A"),
    "humidity": (".1f", "% RH"),
}
READING_SEPARATOR = "  /  "


@dataclass(frozen=True)
class DashboardConfig:
    board_chip: str
    chip_labels: dict[str, str]
    reading_labels: dict[str, dict[str, str]]
    row_order: dict[str, dict[str, int]]


def config_table(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a table")
    return cast(dict[str, object], value)


def config_label(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    return value


def config_labels(value: object, name: str) -> dict[str, str]:
    return {
        key: config_label(label, f"{name}.{key}")
        for key, label in config_table(value, name).items()
    }


def normalize_label(label: str) -> str:
    return label.upper().removeprefix("+").replace(" ", "")


def load_config(path: Path) -> DashboardConfig:
    with path.open("rb") as handle:
        document = cast(dict[str, object], tomllib.load(handle))

    reading_tables = config_table(document.get("reading_labels", {}), "reading_labels")
    order_tables = config_table(document.get("row_order", {}), "row_order")
    row_order: dict[str, dict[str, int]] = {}
    for section, values in order_tables.items():
        name = f"row_order.{section}"
        if not isinstance(values, list):
            raise TypeError(f"{name} must be an array of labels")
        row_order[section] = {
            normalize_label(config_label(label, name)): index
            for index, label in enumerate(cast(list[object], values))
        }

    return DashboardConfig(
        board_chip=config_label(document.get("board_chip", ""), "board_chip"),
        chip_labels=config_labels(document.get("chip_labels", {}), "chip_labels"),
        reading_labels={
            group: config_labels(labels, f"reading_labels.{group}")
            for group, labels in reading_tables.items()
        },
        row_order=row_order,
    )


def display_value(kind: str, value: SensorValue) -> str:
    if value is None or not math.isfinite(value):
        return "N/A"
    if kind == "freq":
        for scale, unit in ((1e9, "GHz"), (1e6, "MHz"), (1e3, "kHz")):
            if abs(value) >= scale:
                return f"{value / scale:g} {unit}"
        return f"{value:g} Hz"
    if kind == "power" and 0 < abs(value) < 1:
        return f"{value * 1000:g} mW"
    if kind == "energy" and abs(value) >= 1000:
        return f"{value / 1000:.0f} kJ"
    if kind == "beep":
        return "Enabled" if value else "Disabled"
    precision, suffix = UNITS.get(kind, ("g", ""))
    return f"{value:{precision}}{suffix}"


def readings(chip: SensorChip) -> Iterator[tuple[str, str, str]]:
    for label, fields in chip.items():
        if not isinstance(fields, dict):
            continue
        samples: list[tuple[str, str]] = []
        for field, value in fields.items():
            match = READING.fullmatch(field)
            if match:
                if (
                    match[2] == "average"
                    and field.removesuffix("_average") + "_input" in fields
                ):
                    continue
                samples.append((match[1], display_value(match[1], value)))
            elif PWM.fullmatch(field):
                samples.append(("pwm", display_value("pwm", value)))
            elif field == "beep_enable":
                samples.append(("beep", display_value("beep", value)))
        if not samples and re.fullmatch(r"(?:temp|in|fan|power|curr)\d+", label):
            samples.append((label.rstrip("0123456789"), "N/A"))
        alarms = [value for field, value in fields.items() if field.endswith("_alarm")]
        if alarms and not samples:
            samples.append(("alarm", "ALARM" if any(alarms) else "OK"))
        elif any(alarms):
            kind, value = samples[0]
            samples[0] = (kind, f"{value} [ALARM]")
        for kind, value in samples:
            yield kind, label, value


def compact(chip: SensorChip, names: dict[str, str] | None = None) -> str:
    names = names or {}
    pairs: list[str] = []
    for _, label, value in readings(chip):
        label = names.get(label, label).upper()
        pairs.append(f"{label} {value}" if label else value)
    return READING_SEPARATOR.join(pairs)


def row_sort_key(
    label: str, priority: dict[str, int]
) -> tuple[int, tuple[int | str, ...]]:
    normalized = normalize_label(label)
    natural = tuple(
        int(part) if part.isdigit() else part
        for part in re.split(r"([0-9]+)", normalized)
    )
    return priority.get(normalized, len(priority)), natural


def nvme_drive_labels() -> dict[str, str]:
    labels: dict[str, str] = {}
    for controller in Path("/sys/class/nvme").glob("nvme*"):
        endpoint = PCI_ADDRESS.fullmatch((controller / "device").resolve().name)
        if endpoint is None:
            continue
        try:
            product = " ".join(
                (controller / "model").read_text(errors="replace").split()
            )
        except OSError:
            product = ""
        domain, bus, slot, function = (int(part, 16) for part in endpoint.groups())
        # lm-sensors encodes the PCI domain, bus, slot and function in its chip name.
        address = f"{(domain << 16) | (bus << 8) | (slot << 3) | function:04x}"
        labels[f"nvme-pci-{address}"] = (
            f"{product} ({controller.name})" if product else controller.name
        )
    return labels


def grouped_rows(data: SensorData, config: DashboardConfig) -> Sections:
    drives = nvme_drive_labels()
    sections: Sections = {
        name: []
        for name in (
            "CPU",
            "Voltage rails",
            "Cooling",
            "Board temperatures",
            "Graphics",
            "NVMe temperatures",
            "Memory",
            "Chipset and network",
            "Board status",
            "Other sensors",
        )
    }
    for chip, features in sorted(data.items()):
        if chip.startswith("k10temp-"):
            sections["CPU"].extend(
                (label, value) for _, label, value in readings(features)
            )
        elif chip == config.board_chip:
            cooling: defaultdict[str, dict[str, str]] = defaultdict(dict)
            for kind, label, value in readings(features):
                if kind in ("fan", "pwm"):
                    cooling[label.removesuffix(" PWM")][kind] = value
                else:
                    section = {"temp": "Board temperatures", "in": "Voltage rails"}
                    sections[section.get(kind, "Board status")].append((label, value))
            for label, values in cooling.items():
                rpm = values.get("fan", "-").replace(" RPM", "")
                sections["Cooling"].append((label, rpm, values.get("pwm", "-")))
        elif chip.startswith("nvme-"):
            temperatures = [
                (f"  {label}", value)
                for kind, label, value in readings(features)
                if kind == "temp"
            ]
            if temperatures:
                sections["NVMe temperatures"].append((drives.get(chip, chip),))
                sections["NVMe temperatures"].extend(temperatures)
        else:
            prefix = chip.split("-", 1)[0]
            address = chip.rsplit("-", 1)[-1]
            if prefix == "spd5118":
                section, name, label_group = "Memory", f"DIMM SPD {address}", "memory"
            elif prefix in ("amdgpu", "i915", "xe", "nouveau"):
                section, name, label_group = (
                    "Graphics",
                    f"{prefix} {address}",
                    "graphics",
                )
            elif prefix == "prom21_xhci":
                section, name, label_group = (
                    "Chipset and network",
                    f"PROM21 {address}",
                    "chipset",
                )
            elif prefix.startswith("r8169_"):
                section, name, label_group = (
                    "Chipset and network",
                    f"LAN {prefix.rsplit('_', 1)[-1]}",
                    "ethernet",
                )
            elif prefix == "ath12k_hwmon":
                section, name, label_group = (
                    "Chipset and network",
                    f"Wi-Fi {address}",
                    "wifi",
                )
            else:
                section, name, label_group = "Other sensors", chip, "other"
            value = compact(features, config.reading_labels.get(label_group))
            if value:
                sections[section].append((config.chip_labels.get(chip, name), value))
    for section, rows in sections.items():
        rows[:] = [(label.upper(), *values) for label, *values in rows]
        if section in config.row_order:
            priority = config.row_order[section]
            rows.sort(key=lambda row: row_sort_key(row[0], priority))
    return sections


def wrap_readings(value: str, width: int) -> list[str]:
    lines: list[str] = []
    for reading in value.split(READING_SEPARATOR):
        if lines and len(lines[-1]) + len(READING_SEPARATOR) + len(reading) <= width:
            lines[-1] += READING_SEPARATOR + reading
        else:
            lines.extend(wrap(reading, width, break_on_hyphens=False))
    return lines


def reading_number(value: str) -> re.Match[str] | None:
    if READING_SEPARATOR not in value:
        return NUMERIC_VALUE.match(value)
    return None


def table(
    title: str, rows: list[Row], width: int, label_width: int, number_width: int
) -> list[str]:
    heading = f"─ {title} "
    lines = [f"╭{heading:─<{width - 2}}╮"]
    value_width = width - label_width - 6
    if title == "Cooling":
        rows = [("HEADER", "RPM", "PWM"), *rows]
        pwm_width = min(max(len(pwm) for _, _, pwm in rows), (value_width - 2) // 2)
        rpm_width = min(
            max(len(rpm) for _, rpm, _ in rows), value_width - pwm_width - 2
        )
        for label, rpm, pwm in rows:
            for left, center, right in zip_longest(
                wrap(label, label_width, break_on_hyphens=False),
                wrap(rpm, rpm_width),
                wrap(pwm, pwm_width),
                fillvalue="",
            ):
                values = f"{center:>{rpm_width}}  {right:>{pwm_width}}"
                lines.append(f"│ {left:<{label_width}}  {values:<{value_width}} │")
    else:
        for label, *fields in rows:
            if not fields:
                lines.extend(
                    f"│ {part:<{width - 4}} │"
                    for part in wrap(label, width - 4, break_on_hyphens=False)
                )
                continue
            value = fields[0]
            if len(label) > label_width:
                label = label.lstrip()
            labels = wrap(label, label_width, break_on_hyphens=False)
            number = reading_number(value)
            padding = max(0, number_width - len(number[1])) if number else 0
            values = wrap_readings(value, value_width - padding)
            for left, right in zip_longest(labels, values, fillvalue=""):
                reading = " " * padding + right
                lines.append(f"│ {left:<{label_width}}  {reading:<{value_width}} │")
    lines.append(f"╰{'─' * (width - 2)}╯")
    return lines


def render_stack(panels: list[Panel], width: int) -> list[str]:
    label_width = min(
        max(
            (len(row[0]) for _, rows in panels for row in rows if len(row) > 1),
            default=1,
        ),
        (width - 6) // 2,
    )
    number_width = min(
        max(
            (
                len(number[1])
                for _, rows in panels
                for row in rows
                if len(row) == 2 and (number := reading_number(row[1]))
            ),
            default=0,
        ),
        width - label_width - 6,
    )
    lines: list[str] = []
    for title, rows in panels:
        panel = table(title, rows, width, label_width, number_width)
        if lines:
            lines[-1] = f"├{panel[0][1:-1]}┤"
            lines.extend(panel[1:])
        else:
            lines.extend(panel)
    return lines


def render(sections: Sections) -> None:
    terminal_width = min(shutil.get_terminal_size().columns, 132)
    if sys.stdout.isatty():
        terminal_width = max(1, terminal_width - 1)
    if not any(sections.values()):
        print("No sensor readings available.")
        return
    if terminal_width < 24:
        for title, rows in sections.items():
            if rows:
                print("\n".join(wrap(title, terminal_width)))
                for row in rows:
                    print("\n".join(wrap("  ".join(row), terminal_width)))
        return

    gap = "  "
    count = max(1, min(3, (terminal_width + len(gap)) // 32))
    width = (terminal_width - len(gap) * (count - 1)) // count
    stacks: list[list[Panel]] = [[] for _ in range(count)]
    columns: list[list[str]] = [[] for _ in range(count)]
    related = ("Memory", "Board status") if sections.get("Voltage rails") else ()
    for title, rows in sections.items():
        if not rows or title in related:
            continue
        index = min(range(count), key=lambda index: len(columns[index]))
        stacks[index].append((title, rows))
        if title == "Voltage rails":
            stacks[index].extend(
                (name, sections[name]) for name in related if sections.get(name)
            )
        columns[index] = render_stack(stacks[index], width)
    for lines in zip_longest(*columns, fillvalue=""):
        print(gap.join(line.ljust(width) for line in lines).rstrip())


def main() -> None:
    parser = argparse.ArgumentParser(prog="hwmon", description=__doc__)
    _ = parser.add_argument(
        "--json", action="store_true", help="print the source lm-sensors JSON"
    )
    args = parser.parse_args()
    try:
        result = subprocess.run(
            ["sensors", "-j"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "LC_ALL": "C"},
        )
        if result.returncode:
            parser.exit(
                1, result.stderr or f"sensors exited with status {result.returncode}\n"
            )
        for line in result.stderr.splitlines():
            if not UNAVAILABLE.fullmatch(line):
                print(line, file=sys.stderr)
        raw_data = cast(
            object, json.loads(result.stdout, parse_constant=lambda _: None)
        )
        if not isinstance(raw_data, dict) or not all(
            isinstance(chip, dict)
            for chip in cast(dict[str, object], raw_data).values()
        ):
            raise ValueError("unexpected lm-sensors JSON structure")
    except (OSError, subprocess.TimeoutExpired, ValueError) as error:
        parser.exit(1, f"{parser.prog}: {error}\n")
    data = cast(SensorData, raw_data)
    if cast(bool, args.json):
        print(json.dumps(data, indent=2))
    else:
        config_path = Path(__file__).resolve().with_suffix(".toml")
        try:
            config = load_config(config_path)
        except (OSError, TypeError, ValueError) as error:
            parser.exit(1, f"{parser.prog}: config {config_path}: {error}\n")
        render(grouped_rows(data, config))


if __name__ == "__main__":
    main()

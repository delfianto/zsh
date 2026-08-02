#!/usr/bin/env python3

"""Inspect Linux CPU topology and frequency scaling without shell pipelines."""

from __future__ import annotations

import argparse
import json
import platform
import re
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn, cast

CPU_LIST_PART = re.compile(r"^(\d+)(?:-(\d+))?$")


class CpuInfoError(RuntimeError):
    """A user-facing failure that does not need a Python traceback."""


@dataclass(frozen=True)
class Processor:
    """Topology and frequency information for one online logical CPU."""

    cpu: int
    package: int | None
    core: int | None
    current_mhz: float | None
    minimum_mhz: float | None
    maximum_mhz: float | None
    driver: str | None
    governor: str | None


@dataclass(frozen=True)
class CpuSnapshot:
    """A normalized snapshot of Linux CPU information."""

    architecture: str
    model: str
    vendor: str | None
    microcode: str | None
    logical_cpus: int
    online_cpus: int
    physical_cores: int | None
    sockets: int | None
    caches: Mapping[str, str]
    processors: tuple[Processor, ...]


def fail(message: str) -> NoReturn:
    raise CpuInfoError(message)


def read_optional(path: Path) -> str | None:
    """Read a small sysfs value, treating absent or inaccessible files as unknown."""
    try:
        return path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return None


def parse_integer(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_cpu_list(value: str) -> tuple[int, ...]:
    """Expand Linux CPU-list syntax such as ``0-3,8,10-11``."""
    cpus: set[int] = set()
    for raw_part in value.split(","):
        part = raw_part.strip()
        match = CPU_LIST_PART.fullmatch(part)
        if match is None:
            fail(f"invalid CPU list: {value!r}")
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if end < start:
            fail(f"invalid descending CPU range: {part!r}")
        cpus.update(range(start, end + 1))
    return tuple(sorted(cpus))


def parse_proc_cpuinfo(text: str) -> dict[int, dict[str, str]]:
    """Parse /proc/cpuinfo records without assuming an x86-only key set."""
    records: dict[int, dict[str, str]] = {}
    for block in re.split(r"\n\s*\n", text.strip()):
        fields: dict[str, str] = {}
        for line in block.splitlines():
            key, separator, value = line.partition(":")
            if separator:
                fields[key.strip().casefold()] = value.strip()
        cpu = parse_integer(fields.get("processor"))
        if cpu is not None:
            records[cpu] = fields
    return records


def read_proc_cpuinfo(path: Path) -> dict[int, dict[str, str]]:
    try:
        return parse_proc_cpuinfo(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as error:
        fail(f"could not read {path}: {error}")


def first_value(
    records: Mapping[int, Mapping[str, str]], keys: Sequence[str]
) -> str | None:
    for record in records.values():
        for key in keys:
            value = record.get(key)
            if value:
                return value
    return None


def kilohertz_to_megahertz(value: str | None) -> float | None:
    integer = parse_integer(value)
    return None if integer is None else integer / 1000


def proc_megahertz(record: Mapping[str, str] | None) -> float | None:
    if record is None:
        return None
    value = record.get("cpu mhz") or record.get("clock")
    if value is None:
        return None
    match = re.search(r"\d+(?:\.\d+)?", value)
    return None if match is None else float(match.group())


def online_cpu_ids(cpu_root: Path, records: Mapping[int, object]) -> tuple[int, ...]:
    online = read_optional(cpu_root / "online")
    if online:
        return parse_cpu_list(online)
    if records:
        return tuple(sorted(records))
    ids: list[int] = []
    for path in cpu_root.glob("cpu[0-9]*"):
        suffix = path.name.removeprefix("cpu")
        if suffix.isdigit():
            ids.append(int(suffix))
    return tuple(sorted(ids))


def policy_values(cpu_root: Path) -> dict[int, dict[str, str]]:
    """Map each logical CPU to the cpufreq policy that controls it."""
    policies: dict[int, dict[str, str]] = {}
    for policy in sorted((cpu_root / "cpufreq").glob("policy[0-9]*")):
        affected = read_optional(policy / "affected_cpus")
        if affected is None:
            affected = read_optional(policy / "related_cpus")
        if not affected:
            suffix = policy.name.removeprefix("policy")
            affected = suffix if suffix.isdigit() else None
        if not affected:
            continue
        values = {
            name: value
            for name in (
                "scaling_cur_freq",
                "scaling_min_freq",
                "scaling_max_freq",
                "cpuinfo_min_freq",
                "cpuinfo_max_freq",
                "scaling_driver",
                "scaling_governor",
            )
            if (value := read_optional(policy / name)) is not None
        }
        for cpu in parse_cpu_list(affected):
            policies[cpu] = values
    return policies


def cpu_policy_values(cpu_root: Path, cpu: int) -> dict[str, str]:
    path = cpu_root / f"cpu{cpu}" / "cpufreq"
    return {
        name: value
        for name in (
            "scaling_cur_freq",
            "scaling_min_freq",
            "scaling_max_freq",
            "cpuinfo_min_freq",
            "cpuinfo_max_freq",
            "scaling_driver",
            "scaling_governor",
        )
        if (value := read_optional(path / name)) is not None
    }


def read_caches(cpu_root: Path) -> dict[str, str]:
    caches: dict[str, str] = {}
    for index in sorted((cpu_root / "cpu0" / "cache").glob("index[0-9]*")):
        level = read_optional(index / "level")
        kind = read_optional(index / "type")
        size = read_optional(index / "size")
        if level is None or kind is None or size is None:
            continue
        suffix = {"data": "d", "instruction": "i", "unified": ""}.get(
            kind.casefold(), f" {kind}"
        )
        caches[f"L{level}{suffix}"] = size
    return caches


def topology_counts(processors: Sequence[Processor]) -> tuple[int | None, int | None]:
    packages = {
        processor.package for processor in processors if processor.package is not None
    }
    cores = {
        (processor.package, processor.core)
        for processor in processors
        if processor.core is not None
    }
    return (len(cores) or None, len(packages) or None)


def collect_snapshot(
    *,
    cpu_root: Path | None = None,
    proc_path: Path | None = None,
) -> CpuSnapshot:
    cpu_root = Path("/sys/devices/system/cpu") if cpu_root is None else cpu_root
    proc_path = Path("/proc/cpuinfo") if proc_path is None else proc_path
    records = read_proc_cpuinfo(proc_path)
    cpu_ids = online_cpu_ids(cpu_root, records)
    if not cpu_ids:
        fail("no logical CPUs were discovered")

    policies = policy_values(cpu_root)
    processors: list[Processor] = []
    for cpu in cpu_ids:
        topology = cpu_root / f"cpu{cpu}" / "topology"
        record = records.get(cpu, {})
        values = policies.get(cpu) or cpu_policy_values(cpu_root, cpu)
        current = kilohertz_to_megahertz(values.get("scaling_cur_freq"))
        if current is None:
            current = proc_megahertz(record)
        package = parse_integer(read_optional(topology / "physical_package_id"))
        if package is None:
            package = parse_integer(record.get("physical id"))
        core = parse_integer(read_optional(topology / "core_id"))
        if core is None:
            core = parse_integer(record.get("core id"))
        processors.append(
            Processor(
                cpu=cpu,
                package=package,
                core=core,
                current_mhz=current,
                minimum_mhz=kilohertz_to_megahertz(
                    values.get("scaling_min_freq") or values.get("cpuinfo_min_freq")
                ),
                maximum_mhz=kilohertz_to_megahertz(
                    values.get("scaling_max_freq") or values.get("cpuinfo_max_freq")
                ),
                driver=values.get("scaling_driver"),
                governor=values.get("scaling_governor"),
            )
        )

    physical_cores, sockets = topology_counts(processors)
    possible = read_optional(cpu_root / "possible")
    logical_cpus = len(parse_cpu_list(possible)) if possible else len(cpu_ids)
    model = first_value(records, ("model name", "hardware", "cpu", "system type"))
    vendor = first_value(records, ("vendor_id", "cpu implementer", "vendor"))
    microcode = first_value(records, ("microcode",))
    return CpuSnapshot(
        architecture=platform.machine() or "unknown",
        model=model or "Unknown CPU",
        vendor=vendor,
        microcode=microcode,
        logical_cpus=logical_cpus,
        online_cpus=len(cpu_ids),
        physical_cores=physical_cores,
        sockets=sockets,
        caches=read_caches(cpu_root),
        processors=tuple(processors),
    )


def format_frequency(value: float | None) -> str:
    if value is None:
        return "unknown"
    if value >= 1000:
        return f"{value / 1000:.2f} GHz"
    return f"{value:.0f} MHz"


def common_value(values: Sequence[str | None]) -> str | None:
    known = {value for value in values if value}
    if not known:
        return None
    return next(iter(known)) if len(known) == 1 else "mixed"


def render_summary(snapshot: CpuSnapshot) -> str:
    frequencies = [
        processor.current_mhz
        for processor in snapshot.processors
        if processor.current_mhz is not None
    ]
    lines = [
        snapshot.model,
        f"  Architecture:   {snapshot.architecture}",
        f"  Logical CPUs:   {snapshot.online_cpus} online / {snapshot.logical_cpus} possible",
    ]
    if snapshot.physical_cores is not None:
        lines.append(f"  Physical cores: {snapshot.physical_cores}")
    if snapshot.sockets is not None:
        lines.append(f"  Sockets:        {snapshot.sockets}")
    if snapshot.vendor is not None:
        lines.append(f"  Vendor:         {snapshot.vendor}")
    if snapshot.microcode is not None:
        lines.append(f"  Microcode:      {snapshot.microcode}")
    if frequencies:
        average = sum(frequencies) / len(frequencies)
        frequency_range = " / ".join(
            (
                format_frequency(min(frequencies)),
                format_frequency(average),
                format_frequency(max(frequencies)),
            )
        )
        lines.append(f"  Frequency:      {frequency_range} (min/avg/max current)")
    driver = common_value([processor.driver for processor in snapshot.processors])
    governor = common_value([processor.governor for processor in snapshot.processors])
    if driver is not None:
        lines.append(f"  Scaling driver: {driver}")
    if governor is not None:
        lines.append(f"  Governor:       {governor}")
    if snapshot.caches:
        rendered = ", ".join(f"{name} {size}" for name, size in snapshot.caches.items())
        lines.append(f"  Caches:         {rendered}")
    return "\n".join(lines)


def render_frequencies(snapshot: CpuSnapshot) -> str:
    header = f"{'CPU':>5} {'CORE':>7} {'CURRENT':>11} {'MIN':>11} {'MAX':>11}  GOVERNOR"
    lines = [header]
    for processor in snapshot.processors:
        location = (
            "-"
            if processor.core is None
            else f"{processor.package if processor.package is not None else '?'}:{processor.core}"
        )
        row = "{cpu:>5} {location:>7} {current:>11} {minimum:>11} "
        row += "{maximum:>11}  {governor}"
        lines.append(
            row.format(
                cpu=processor.cpu,
                location=location,
                current=format_frequency(processor.current_mhz),
                minimum=format_frequency(processor.minimum_mhz),
                maximum=format_frequency(processor.maximum_mhz),
                governor=processor.governor or "-",
            )
        )
    return "\n".join(lines)


def snapshot_dict(snapshot: CpuSnapshot) -> dict[str, object]:
    return {
        "architecture": snapshot.architecture,
        "model": snapshot.model,
        "vendor": snapshot.vendor,
        "microcode": snapshot.microcode,
        "logical_cpus": snapshot.logical_cpus,
        "online_cpus": snapshot.online_cpus,
        "physical_cores": snapshot.physical_cores,
        "sockets": snapshot.sockets,
        "caches": dict(snapshot.caches),
        "processors": [
            {
                "cpu": processor.cpu,
                "package": processor.package,
                "core": processor.core,
                "current_mhz": processor.current_mhz,
                "minimum_mhz": processor.minimum_mhz,
                "maximum_mhz": processor.maximum_mhz,
                "driver": processor.driver,
                "governor": processor.governor,
            }
            for processor in snapshot.processors
        ],
    }


def parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser(
        prog="cpuinfo",
        description="Inspect Linux CPU topology and frequency scaling.",
    )
    _ = argument_parser.add_argument(
        "mode",
        nargs="?",
        choices=("summary", "frequency", "watch"),
        default="summary",
        help="view to display (default: summary)",
    )
    _ = argument_parser.add_argument(
        "-j", "--json", action="store_true", help="emit the complete snapshot as JSON"
    )
    _ = argument_parser.add_argument(
        "-n",
        "--interval",
        type=float,
        default=2.0,
        metavar="SECONDS",
        help="watch refresh interval (default: 2)",
    )
    return argument_parser


def watch_frequencies(interval: float) -> int:
    if interval <= 0:
        fail("watch interval must be greater than zero")
    first = True
    try:
        while True:
            snapshot = collect_snapshot()
            if not first:
                print("\033[H\033[J", end="")
            first = False
            print("CPU frequency monitor (Ctrl-C to stop)\n")
            print(render_frequencies(snapshot), flush=True)
            time.sleep(interval)
    except KeyboardInterrupt:
        return 0


def main(argv: Sequence[str] | None = None) -> int:
    argument_parser = parser()
    arguments = argument_parser.parse_args(argv)
    mode = cast(str, arguments.mode)
    json_output = cast(bool, arguments.json)
    interval = cast(float, arguments.interval)
    if mode == "watch" and json_output:
        argument_parser.error("--json cannot be combined with watch mode")
    if mode != "watch" and interval != 2.0:
        argument_parser.error("--interval is supported only by watch mode")

    try:
        if mode == "watch":
            return watch_frequencies(interval)
        snapshot = collect_snapshot()
        if json_output:
            print(json.dumps(snapshot_dict(snapshot), indent=2, sort_keys=True))
        elif mode == "frequency":
            print(render_frequencies(snapshot))
        else:
            print(render_summary(snapshot))
        return 0
    except CpuInfoError as error:
        print(f"cpuinfo: {error}", file=sys.stderr)
        return 1
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

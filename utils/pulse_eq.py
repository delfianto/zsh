#!/usr/bin/env python3

"""Load EasyEffects output presets and inspect their parametric EQ bands."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import NoReturn, cast

EQUALIZER_RE = re.compile(r"^equalizer#(\d+)$")
BAND_RE = re.compile(r"^band(\d+)$")
JsonObject = dict[str, object]


class PulseEqError(RuntimeError):
    """A user-facing failure that does not need a Python traceback."""


@dataclass(frozen=True)
class Band:
    index: int
    filter_type: str
    frequency: float
    gain: float
    q: float
    mode: str
    slope: str
    width: float
    mute: bool
    solo: bool


@dataclass(frozen=True)
class Equalizer:
    instance: str
    mode: str
    bypass: bool
    input_gain: float
    output_gain: float
    split_channels: bool
    left: tuple[Band, ...]
    right: tuple[Band, ...]


@dataclass(frozen=True)
class Preset:
    path: Path
    pipeline: str
    equalizers: tuple[Equalizer, ...]


def fail(message: str) -> NoReturn:
    raise PulseEqError(message)


def default_preset_directory() -> Path:
    override = os.environ.get("EASYEFFECTS_PRESET_DIR")
    if override:
        return Path(override).expanduser()
    data_home = os.environ.get("XDG_DATA_HOME")
    base = Path(data_home) if data_home else Path.home() / ".local" / "share"
    return base / "easyeffects" / "output"


def require_command(name: str) -> str:
    command = shutil.which(name)
    if command is None:
        fail(f"required command not found: {name}")
    return command


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


def find_presets(directory: Path) -> tuple[Path, ...]:
    if not directory.is_dir():
        fail(f"EasyEffects output preset directory not found: {directory}")
    presets = tuple(path for path in directory.glob("*.json") if path.is_file())
    if not presets:
        fail(f"no EasyEffects output preset JSON files found in {directory}")
    return tuple(
        sorted(
            presets,
            key=lambda path: (
                path.stem.casefold() in {"flat", "flat response"},
                path.stem.casefold(),
            ),
        )
    )


def resolve_preset(target: str, directory: Path) -> Path:
    candidate = Path(target).expanduser()
    if candidate.is_file():
        return candidate
    if candidate.suffix == ".json" or candidate.parent != Path("."):
        fail(f"preset file not found: {candidate}")

    name = candidate.stem if candidate.suffix == ".json" else target
    for preset in find_presets(directory):
        if preset.stem == name:
            return preset
    fail(f"EasyEffects output preset not found: {target}")


def resolve_local_preset(target: str, directory: Path) -> Path:
    candidate = Path(target)
    if candidate.parent != Path("."):
        fail("loading accepts a local preset name, not an arbitrary JSON path")
    name = candidate.stem if candidate.suffix == ".json" else target
    for preset in find_presets(directory):
        if preset.stem == name:
            return preset
    fail(f"EasyEffects output preset not found: {target}")


def as_object(value: object, label: str) -> JsonObject:
    if not isinstance(value, dict):
        fail(f"{label} must be a JSON object")
    mapping = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in mapping):
        fail(f"{label} contains a non-string key")
    return cast(JsonObject, mapping)


def as_string(value: object, label: str, default: str = "") -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        fail(f"{label} must be a string")
    return value


def as_number(value: object, label: str, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        fail(f"{label} must be a number")
    return float(value)


def as_bool(value: object, label: str, default: bool = False) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        fail(f"{label} must be a boolean")
    return value


def parse_band(index: int, value: object, label: str) -> Band:
    band = as_object(value, label)
    return Band(
        index=index,
        filter_type=as_string(band.get("type"), f"{label}.type", "Bell"),
        frequency=as_number(band.get("frequency"), f"{label}.frequency"),
        gain=as_number(band.get("gain"), f"{label}.gain"),
        q=as_number(band.get("q"), f"{label}.q"),
        mode=as_string(band.get("mode"), f"{label}.mode"),
        slope=as_string(band.get("slope"), f"{label}.slope"),
        width=as_number(band.get("width"), f"{label}.width"),
        mute=as_bool(band.get("mute"), f"{label}.mute"),
        solo=as_bool(band.get("solo"), f"{label}.solo"),
    )


def parse_channel(value: object, label: str) -> tuple[Band, ...]:
    channel = as_object(value, label)
    indexed_bands: list[tuple[int, object]] = []
    for key, band in channel.items():
        match = BAND_RE.fullmatch(key)
        if match:
            indexed_bands.append((int(match.group(1)), band))
    if not indexed_bands:
        fail(f"{label} contains no equalizer bands")
    return tuple(
        parse_band(index, band, f"{label}.band{index}")
        for index, band in sorted(indexed_bands)
    )


def parse_equalizer(instance: str, value: object, label: str) -> Equalizer:
    equalizer = as_object(value, label)
    left = parse_channel(equalizer.get("left"), f"{label}.left")
    right = parse_channel(equalizer.get("right"), f"{label}.right")
    declared_bands = int(as_number(equalizer.get("num-bands"), f"{label}.num-bands"))
    if declared_bands and (declared_bands != len(left) or declared_bands != len(right)):
        message = f"{label} declares {declared_bands} bands but contains "
        message += f"{len(left)} left and {len(right)} right bands"
        fail(message)
    return Equalizer(
        instance=instance,
        mode=as_string(equalizer.get("mode"), f"{label}.mode"),
        bypass=as_bool(equalizer.get("bypass"), f"{label}.bypass"),
        input_gain=as_number(equalizer.get("input-gain"), f"{label}.input-gain"),
        output_gain=as_number(equalizer.get("output-gain"), f"{label}.output-gain"),
        split_channels=as_bool(
            equalizer.get("split-channels"), f"{label}.split-channels"
        ),
        left=left,
        right=right,
    )


def read_preset(path: Path) -> Preset:
    try:
        raw = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except OSError as error:
        fail(f"could not read preset {path}: {error}")
    except json.JSONDecodeError as error:
        fail(f"invalid JSON in {path}:{error.lineno}:{error.colno}: {error.msg}")

    root = as_object(raw, str(path))
    pipelines = [name for name in ("output", "input") if name in root]
    if len(pipelines) != 1:
        fail(f"{path} must contain exactly one input or output pipeline")
    pipeline_name = pipelines[0]
    pipeline = as_object(root[pipeline_name], f"{path}.{pipeline_name}")

    equalizers: list[Equalizer] = []
    for key, value in pipeline.items():
        match = EQUALIZER_RE.fullmatch(key)
        if match:
            equalizers.append(
                parse_equalizer(key, value, f"{path}.{pipeline_name}.{key}")
            )
    equalizers.sort(key=lambda equalizer: int(equalizer.instance.partition("#")[2]))
    if not equalizers:
        fail(f"{path} contains no equalizer instances")
    return Preset(path, pipeline_name, tuple(equalizers))


def format_frequency(frequency: float) -> str:
    if frequency >= 1000:
        return f"{frequency / 1000:.3g} kHz"
    return f"{frequency:.4g} Hz"


def format_gain(gain: float) -> str:
    return f"{gain:+.2f} dB"


def flags(band: Band) -> str:
    values: list[str] = []
    if band.mute:
        values.append("mute")
    if band.solo:
        values.append("solo")
    if band.slope:
        values.append(band.slope)
    return ", ".join(values) or "-"


def print_bands(channel: str, bands: Sequence[Band]) -> None:
    print(
        f"  {'Ch':<5} {'#':>2}  {'Type':<12} {'Frequency':>10} {'Gain':>10} {'Q':>7}  {'Mode':<12} Flags"
    )
    for band in bands:
        row = f"  {channel:<5} {band.index + 1:>2}  {band.filter_type:<12} "
        row += f"{format_frequency(band.frequency):>10} "
        row += f"{format_gain(band.gain):>10} {band.q:>7.3g}  "
        row += f"{band.mode:<12} {flags(band)}"
        print(row)


def print_inspection(preset: Preset, channel: str) -> None:
    print(f"Preset: {preset.path.stem}")
    print(f"File: {preset.path}")
    print(f"Pipeline: {preset.pipeline}")
    for equalizer in preset.equalizers:
        state = "bypassed" if equalizer.bypass else "active"
        linked = not equalizer.split_channels and equalizer.left == equalizer.right
        layout = "linked channels" if linked else "split channels"
        print()
        summary = f"{equalizer.instance}: {equalizer.mode or 'unknown mode'}, "
        print(summary + f"{state}, {layout}")
        gain_summary = f"  Input gain: {format_gain(equalizer.input_gain)}  "
        print(gain_summary + f"Output gain: {format_gain(equalizer.output_gain)}")
        if channel == "left":
            print_bands("Left", equalizer.left)
        elif channel == "right":
            print_bands("Right", equalizer.right)
        elif linked:
            print_bands("L/R", equalizer.left)
        else:
            print_bands("Left", equalizer.left)
            print()
            print_bands("Right", equalizer.right)


def preset_payload(preset: Preset) -> dict[str, object]:
    return {
        "name": preset.path.stem,
        "file": str(preset.path),
        "pipeline": preset.pipeline,
        "equalizers": [asdict(equalizer) for equalizer in preset.equalizers],
    }


def list_presets(directory: Path) -> int:
    for preset in find_presets(directory):
        print(preset.stem)
    return 0


def load_preset(path: Path) -> int:
    easyeffects = require_command("easyeffects")
    try:
        result = subprocess.run(
            (easyeffects, "--load-preset", path.stem),
            check=False,
        )
    except OSError as error:
        fail(f"could not execute easyeffects: {error}")
    if result.returncode:
        fail(f"EasyEffects failed to load preset {path.stem!r}")
    print(f"Loaded EasyEffects output preset: {path.stem}")
    return 0


def current_preset_name() -> str:
    easyeffects = require_command("easyeffects")
    name = capture((easyeffects, "--last-loaded-preset", "output"))
    if not name:
        fail("EasyEffects has no last-loaded output preset")
    return name.splitlines()[0]


def interactive(directory: Path) -> int:
    _ = require_command("easyeffects")
    presets = find_presets(directory)
    print("Available EasyEffects output presets:")
    for index, preset in enumerate(presets, start=1):
        print(f"  {index}) {preset.stem}")
    print(f"  {len(presets) + 1}) Quit")

    while True:
        try:
            answer = input("Select a preset: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 130
        if answer.isdecimal():
            choice = int(answer)
            if 1 <= choice <= len(presets):
                return load_preset(presets[choice - 1])
            if choice == len(presets) + 1:
                print("No preset loaded.")
                return 0
        print(f"Enter a number from 1 to {len(presets) + 1}.", file=sys.stderr)


def parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser(
        prog="pulse-eq",
        description="Load EasyEffects output presets and inspect their PEQ bands.",
    )
    _ = argument_parser.add_argument(
        "--preset-dir",
        type=Path,
        default=default_preset_directory(),
        metavar="PATH",
        help="local output preset directory (default: %(default)s)",
    )
    subparsers = argument_parser.add_subparsers(dest="command")
    _ = subparsers.add_parser("list", help="list local output presets")

    load_parser = subparsers.add_parser("load", help="load a local output preset")
    _ = load_parser.add_argument("preset", help="local preset name")

    inspect_parser = subparsers.add_parser(
        "inspect", help="show parametric equalizer bands"
    )
    _ = inspect_parser.add_argument(
        "preset",
        nargs="?",
        help="preset name or JSON path (default: last loaded output preset)",
    )
    _ = inspect_parser.add_argument(
        "--channel",
        choices=("left", "right", "both"),
        default="both",
        help="channel detail to display (default: both)",
    )
    _ = inspect_parser.add_argument(
        "--json", action="store_true", help="emit structured JSON"
    )
    return argument_parser


def main(argv: Sequence[str] | None = None) -> int:
    argument_parser = parser()
    arguments = argument_parser.parse_args(argv)
    command = cast(str | None, arguments.command)
    directory = cast(Path, arguments.preset_dir).expanduser()
    try:
        if command is None:
            return interactive(directory)
        if command == "list":
            return list_presets(directory)
        if command == "load":
            return load_preset(
                resolve_local_preset(cast(str, arguments.preset), directory)
            )
        if command == "inspect":
            target = cast(str | None, arguments.preset) or current_preset_name()
            preset = read_preset(resolve_preset(target, directory))
            if cast(bool, arguments.json):
                json.dump(preset_payload(preset), sys.stdout, indent=2)
                print()
            else:
                print_inspection(preset, cast(str, arguments.channel))
            return 0
        fail(f"unsupported command: {command}")
    except PulseEqError as error:
        print(f"pulse-eq: {error}", file=sys.stderr)
        return 1
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

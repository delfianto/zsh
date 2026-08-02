"""Regression tests for the EasyEffects preset loader and PEQ inspector."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from utils import pulse_eq


def band(
    frequency: float = 1000.0,
    gain: float = -2.5,
    q: float = 1.4,
) -> dict[str, object]:
    return {
        "frequency": frequency,
        "gain": gain,
        "mode": "APO (DR)",
        "mute": False,
        "q": q,
        "slope": "x1",
        "solo": False,
        "type": "Bell",
        "width": 4.0,
    }


def preset_data(*, split_channels: bool = False) -> dict[str, object]:
    left = {
        "band0": band(105.0, 5.5, 0.71),
        "band1": band(2200.0, -1.5, 2.0),
    }
    right = {
        "band0": band(105.0, 5.5, 0.71),
        "band1": band(2200.0, -1.5 if not split_channels else -2.0, 2.0),
    }
    return {
        "output": {
            "blocklist": [],
            "equalizer#0": {
                "balance": 0.0,
                "bypass": False,
                "input-gain": -5.5,
                "left": left,
                "mode": "IIR",
                "num-bands": 2,
                "output-gain": 0.0,
                "right": right,
                "split-channels": split_channels,
            },
            "plugins_order": ["equalizer#0"],
        }
    }


def write_preset(directory: Path, name: str, data: object | None = None) -> Path:
    path = directory / f"{name}.json"
    _ = path.write_text(
        json.dumps(preset_data() if data is None else data),
        encoding="utf-8",
    )
    return path


class PulseEqTest(unittest.TestCase):
    def test_find_presets_sorts_flat_last(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            _ = write_preset(directory, "Sundara")
            _ = write_preset(directory, "Flat")
            _ = write_preset(directory, "Ananda Nano")

            names = [path.stem for path in pulse_eq.find_presets(directory)]

        self.assertEqual(names, ["Ananda Nano", "Sundara", "Flat"])

    def test_load_resolution_rejects_arbitrary_json_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            _ = write_preset(directory, "Local")

            with self.assertRaisesRegex(pulse_eq.PulseEqError, "local preset name"):
                _ = pulse_eq.resolve_local_preset("/tmp/Elsewhere.json", directory)

    def test_read_preset_extracts_current_equalizer_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = write_preset(Path(temporary_directory), "Headphones")

            preset = pulse_eq.read_preset(path)

        equalizer = preset.equalizers[0]
        self.assertEqual(preset.pipeline, "output")
        self.assertEqual(equalizer.instance, "equalizer#0")
        self.assertEqual(equalizer.input_gain, -5.5)
        self.assertFalse(equalizer.split_channels)
        self.assertEqual(equalizer.left[0].frequency, 105.0)
        self.assertEqual(equalizer.left[0].gain, 5.5)
        self.assertEqual(equalizer.left[0].filter_type, "Bell")

    def test_inspection_collapses_identical_linked_channels(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            preset = pulse_eq.read_preset(
                write_preset(Path(temporary_directory), "Headphones")
            )
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                pulse_eq.print_inspection(preset, "both")

        output = stdout.getvalue()
        self.assertIn("linked channels", output)
        self.assertIn("L/R", output)
        self.assertIn("105 Hz", output)
        self.assertIn("+5.50 dB", output)
        self.assertNotIn("Right", output)

    def test_inspection_shows_both_split_channels(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            preset = pulse_eq.read_preset(
                write_preset(
                    Path(temporary_directory),
                    "Split",
                    preset_data(split_channels=True),
                )
            )
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                pulse_eq.print_inspection(preset, "both")

        output = stdout.getvalue()
        self.assertIn("split channels", output)
        self.assertIn("Left", output)
        self.assertIn("Right", output)
        self.assertIn("-2.00 dB", output)

    def test_declared_band_count_must_match_json(self) -> None:
        data = preset_data()
        output = pulse_eq.as_object(data["output"], "fixture.output")
        equalizer = pulse_eq.as_object(
            output["equalizer#0"], "fixture.output.equalizer#0"
        )
        equalizer["num-bands"] = 3
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = write_preset(Path(temporary_directory), "Broken", data)

            with self.assertRaisesRegex(pulse_eq.PulseEqError, "declares 3 bands"):
                _ = pulse_eq.read_preset(path)

    def test_json_payload_contains_band_parameters(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            preset = pulse_eq.read_preset(
                write_preset(Path(temporary_directory), "Headphones")
            )

            payload = pulse_eq.preset_payload(preset)

        equalizers = payload["equalizers"]
        self.assertIsInstance(equalizers, list)
        encoded = json.dumps(payload)
        self.assertIn('"frequency": 105.0', encoded)
        self.assertIn('"gain": 5.5', encoded)
        self.assertIn('"q": 0.71', encoded)


if __name__ == "__main__":
    _ = unittest.main()

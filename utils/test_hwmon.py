"""Regression tests for the configured sensor dashboard."""

import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

from utils import hwmon


class DashboardConfigTests(unittest.TestCase):
    def test_config_controls_board_chip_labels_and_row_order(self) -> None:
        data: hwmon.SensorData = {
            "demo-board": {
                "+12V": {"in1_input": 12.1},
                "+5V": {"in2_input": 5.0},
            },
            "spd5118-i2c-15-51": {"temp1": {"temp1_input": 42}},
            "spd5118-i2c-15-53": {"temp1": {"temp1_input": 39}},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hwmon.toml"
            _ = path.write_text(
                dedent("""\
                    board_chip = "demo-board"
                    [chip_labels]
                    "spd5118-i2c-15-51" = "Slot A"
                    [reading_labels.memory]
                    temp1 = ""
                    [row_order]
                    "Voltage rails" = ["+5v", "12V"]
                    """),
                encoding="utf-8",
            )
            sections = hwmon.grouped_rows(data, hwmon.load_config(path))

        self.assertEqual(
            sections["Voltage rails"], [("+5V", "5.000 V"), ("+12V", "12.100 V")]
        )
        self.assertEqual(
            sections["Memory"], [("SLOT A", "42.0 °C"), ("DIMM SPD 53", "39.0 °C")]
        )

    def test_invalid_mapping_reports_the_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hwmon.toml"
            _ = path.write_text('[chip_labels]\n"some-chip" = 42\n', encoding="utf-8")
            with self.assertRaisesRegex(
                TypeError, r"chip_labels\.some-chip must be a string"
            ):
                _ = hwmon.load_config(path)

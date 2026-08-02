"""Regression tests for the stdlib-only IOMMU utility."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from utils import iommu


class RulesTest(unittest.TestCase):
    def test_load_rules_preserves_equals_and_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "rules"
            _ = path.write_text(
                "# comment\n'long=value'='short=value'\n'Corp'=''\n",
                encoding="utf-8",
            )

            self.assertEqual(
                iommu.load_rules(path),
                (
                    iommu.Rule("long=value", "short=value"),
                    iommu.Rule("Corp", ""),
                ),
            )

    def test_load_rules_reports_the_invalid_line(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "rules"
            _ = path.write_text("valid-looking-but-not-valid\n", encoding="utf-8")

            with self.assertRaisesRegex(iommu.IommuError, rf"{path}:1"):
                _ = iommu.load_rules(path)

    def test_clean_description_is_literal_and_normalized(self) -> None:
        description = (
            "VGA compatible controller: NVIDIA Corporation  Example GPU (rev a1)"
        )
        rules = (iommu.Rule("NVIDIA Corporation", "NVIDIA"),)

        self.assertEqual(
            iommu.clean_description(description, rules), "NVIDIA Example GPU"
        )


class SysfsTest(unittest.TestCase):
    def test_groups_are_numeric_and_keep_unknown_devices(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            sysfs = Path(temporary_directory)
            groups_root = sysfs / "kernel" / "iommu_groups"
            for number, address in (("10", "0000:0a:00.0"), ("2", "0000:02:00.0")):
                (groups_root / number / "devices" / address).mkdir(parents=True)

            descriptions = {
                "0000:02:00.0": "Ethernet controller: Example Corporation NIC"
            }
            rules = (iommu.Rule(" Corporation", ""),)
            with mock.patch.object(
                iommu, "pci_descriptions", return_value=descriptions
            ):
                groups = iommu.collect_groups(sysfs, rules)

            self.assertEqual([group.number for group in groups], ["2", "10"])
            self.assertEqual(groups[0].devices[0].description, "Example NIC")
            self.assertIsNone(groups[1].devices[0].description)

    def test_usb_resolves_controller_and_iommu_group(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            sysfs = Path(temporary_directory)
            controller = sysfs / "devices" / "pci0000:00" / "0000:00:14.0"
            usb_bus = controller / "usb2"
            usb_bus.mkdir(parents=True)
            _ = (usb_bus / "busnum").write_text("2\n", encoding="utf-8")

            group = sysfs / "kernel" / "iommu_groups" / "12"
            group.mkdir(parents=True)
            (controller / "iommu_group").symlink_to(group, target_is_directory=True)

            usb_root = sysfs / "bus" / "usb" / "devices"
            usb_root.mkdir(parents=True)
            (usb_root / "usb2").symlink_to(usb_bus, target_is_directory=True)

            with (
                mock.patch.object(iommu, "require_command", return_value="lsusb"),
                mock.patch.object(
                    iommu, "capture", return_value="Bus 002 Device 001: root hub\n"
                ),
            ):
                controllers = iommu.collect_usb(sysfs)

            self.assertEqual(
                controllers,
                (
                    iommu.UsbController(
                        "2",
                        "0000:00:14.0",
                        "12",
                        ("Bus 002 Device 001: root hub",),
                    ),
                ),
            )


if __name__ == "__main__":
    _ = unittest.main()

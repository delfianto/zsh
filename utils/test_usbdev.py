"""Regression tests for USB names and topology."""

import plistlib
import tempfile
import unittest
from pathlib import Path

from utils import usbdev


def sysfs_entry(root: Path, name: str, **attributes: str) -> None:
    entry = root / name
    entry.mkdir()
    for key, value in attributes.items():
        _ = (entry / key).write_text(value + "\n", encoding="utf-8")


class UsbTreeTest(unittest.TestCase):
    def test_linux_tree_resolves_names_and_sorts_nested_ports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ids = root / "usb.ids"
            _ = ids.write_text(
                "1234  Finch\n"
                + "\t0001  Feather Keyboard\n"
                + "\t\t00  A subsection\n"
                + "C 03  Human Interface Device\n"
                + "\t0002  A class description\n",
                encoding="utf-8",
            )
            sysfs_entry(root, "usb10", speed="5000")
            sysfs_entry(root, "usb2", speed="480")
            sysfs_entry(
                root, "2-4.10", idVendor="1234", idProduct="0002", bDeviceClass="08"
            )
            sysfs_entry(
                root,
                "2-4.2",
                idVendor="1234",
                idProduct="0001",
                manufacturer="Generic",
                product="Љ",
                speed="12",
                devnum="7",
            )
            sysfs_entry(
                root,
                "2-4.2:1.0",
                bInterfaceClass="03",
                bInterfaceSubClass="01",
                bInterfaceProtocol="01",
            )
            sysfs_entry(
                root,
                "2-4",
                idVendor="1234",
                idProduct="0002",
                manufacturer=" Finch ",
                product="Finch   桌面 Hub",
                bDeviceClass="09",
                speed="480",
            )
            sysfs_entry(root, "2-7")
            sysfs_entry(root, "2-7.3", idVendor="1234", idProduct="0003")
            names = usbdev.load_names((root / "missing.ids", ids))
            buses = usbdev.linux_tree(root, names)

        self.assertEqual(
            list(
                usbdev.tree_lines(
                    buses, all_buses=False, verbose=False, ascii_only=False
                )
            ),
            [
                "USB topology                            Link speed",
                "USB bus 2                                 480 Mb/s",
                "├── Port 4  Finch 桌面 Hub                480 Mb/s",
                "│   ├── Port 2  Finch Feather Keyboard     12 Mb/s",
                "│   └── Port 10  Finch Mass storage              -",
                "└── Port 7.3  Finch USB device                   -",
            ],
        )
        verbose = list(
            usbdev.tree_lines(buses, all_buses=True, verbose=True, ascii_only=True)
        )
        self.assertIn(
            "|   |-- Port 2  Finch Feather Keyboard     12 Mb/s  |  1234:0001  |  path 2-4.2  |  device 007",
            verbose,
        )
        self.assertEqual(
            verbose[-1], "USB bus 10                                  5 Gb/s"
        )

    def test_macos_registry_keeps_devices_nested_through_port_nodes(self) -> None:
        child_key = "IORegistryEntryChildren"
        keyboard = {
            "IORegistryEntryName": "Feather",
            "idVendor": 0x1234,
            "idProduct": 1,
            "locationID": 0x14230000,
            "USBSpeed": 1,
            child_key: [
                {
                    "idVendor": 0x1234,
                    "idProduct": 1,
                    "bInterfaceNumber": 0,
                    "bInterfaceClass": 3,
                    "bInterfaceSubClass": 1,
                    "bInterfaceProtocol": 1,
                }
            ],
        }
        hub = {
            "USB Product Name": "Desk Hub",
            "idVendor": 0x1234,
            "idProduct": 2,
            "PortNum": 2,
            "bDeviceClass": 9,
            "USBSpeed": 3,
            child_key: [
                {"usb-port-number": b"\x03\x00\x00\x00", child_key: [keyboard]}
            ],
        }
        root = {
            "IORegistryEntryName": "Root",
            child_key: [{"IORegistryEntryName": "XHCI", child_key: [hub]}],
        }
        for archive in (root, [root]):
            with self.subTest(archive_type=type(archive)):
                buses = usbdev.macos_tree(plistlib.dumps(archive), usbdev.UsbNames())
                self.assertEqual(
                    list(
                        usbdev.tree_lines(
                            buses, all_buses=False, verbose=True, ascii_only=False
                        )
                    ),
                    [
                        "USB topology                        Link speed",
                        "USB controller 1                             -  ·  XHCI",
                        "└── Port 2  Desk Hub                    5 Gb/s  ·  1234:0002",
                        "    └── Port 3  Feather (Keyboard)     12 Mb/s  ·  1234:0001  ·  location 0x14230000",
                    ],
                )


if __name__ == "__main__":
    _ = unittest.main()

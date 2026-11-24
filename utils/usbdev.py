#!/usr/bin/env python3
"""List USB buses, hubs, and devices as a readable tree."""

import argparse
import plistlib
import re
import subprocess
import sys
import unicodedata
from collections import defaultdict
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast
from xml.parsers.expat import ExpatError

SYSFS_USB = Path("/sys/bus/usb/devices")
USB_IDS = (
    Path("/usr/share/hwdata/usb.ids"),
    Path("/usr/share/misc/usb.ids"),
    Path("/usr/share/usb.ids"),
    Path("/var/lib/usbutils/usb.ids"),
)
LINUX_DEVICE = re.compile(r"(?:usb([0-9]+)|([0-9]+)-([0-9]+(?:\.[0-9]+)*))")
VENDOR_LINE = re.compile(r"([0-9a-f]{4})\s+(.+)")
PRODUCT_LINE = re.compile(r"\t" + VENDOR_LINE.pattern)
CLASS_NAMES = {
    0x01: "Audio",
    0x02: "Communications",
    0x03: "Input device",
    0x06: "Imaging",
    0x07: "Printer",
    0x08: "Mass storage",
    0x09: "Hub",
    0x0B: "Smart card",
    0x0E: "Video",
    0x10: "Audio/video",
    0x11: "Billboard",
    0xE0: "Wireless controller",
}
GENERIC_NAMES = {
    "generic",
    "unknown",
    "unknown device",
    "usb",
    "usb device",
    "usb2.0 device",
    "iousbdevice",
    "iousbhostdevice",
    "n/a",
}
MAC_SPEEDS = {0: "1.5", 1: "12", 2: "480", 3: "5000", 4: "10000", 5: "20000"}
UsbClass = tuple[int, int, int]
RegistryEntry = dict[str, object]


@dataclass
class Node:
    name: str
    speed: str = ""
    ports: tuple[int, ...] = ()
    details: tuple[str, ...] = ()
    children: list["Node"] = field(default_factory=list)


@dataclass
class UsbNames:
    vendors: dict[str, str] = field(default_factory=dict)
    products: dict[str, str] = field(default_factory=dict)


def clean_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    printable = "".join(char for char in value if char.isprintable() or char.isspace())
    return " ".join(printable.split())


def useful_name(value: str) -> str:
    if value.casefold() in GENERIC_NAMES or sum(char.isalnum() for char in value) < 2:
        return ""
    return value


def load_names(paths: Iterable[Path]) -> UsbNames:
    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        names = UsbNames()
        vendor = ""
        for line in lines:
            if match := VENDOR_LINE.fullmatch(line):
                vendor, name = match.groups()
                names.vendors[vendor] = clean_text(name)
            elif line.startswith("C "):
                break
            elif vendor and (match := PRODUCT_LINE.fullmatch(line)):
                product, name = match.groups()
                names.products[f"{vendor}:{product}"] = clean_text(name)
        return names
    return UsbNames()


def class_name(code: UsbClass) -> str:
    if code == (0xE0, 1, 1):
        return "Bluetooth"
    if code == (0x03, 1, 1):
        return "Keyboard"
    if code == (0x03, 1, 2):
        return "Mouse"
    return CLASS_NAMES.get(code[0], "")


def device_name(
    usb_id: str,
    manufacturer: str,
    product: str,
    classes: Iterable[UsbClass],
    names: UsbNames,
) -> str:
    kinds = list(dict.fromkeys(name for code in classes if (name := class_name(code))))
    if "Input device" in kinds and ("Keyboard" in kinds or "Mouse" in kinds):
        kinds.remove("Input device")

    vendor = useful_name(manufacturer)
    model = useful_name(product)
    category_names = {kind.casefold() for kind in kinds}
    if not model or model.casefold().removeprefix("usb ") in category_names:
        model = useful_name(names.products.get(usb_id, "")) or model
        vendor = vendor or useful_name(names.vendors.get(usb_id.partition(":")[0], ""))

    model = model or " / ".join(kinds) or "USB device"
    if vendor and not re.search(
        rf"(?<!\w){re.escape(vendor)}(?!\w)", model, re.IGNORECASE
    ):
        model = f"{vendor} {model}"

    extra = [kind for kind in kinds if kind.casefold() not in model.casefold()]
    return f"{model} ({' / '.join(extra)})" if extra else model


def read_attribute(path: Path, attribute: str) -> str:
    try:
        return clean_text(
            (path / attribute).read_text(encoding="utf-8", errors="replace")
        )
    except OSError:
        return ""


def linux_class(path: Path, prefix: str) -> UsbClass:
    def read_hex(suffix: str) -> int:
        value = read_attribute(path, f"b{prefix}{suffix}")
        return int(value, 16) if re.fullmatch(r"[0-9a-fA-F]{2}", value) else 0

    return read_hex("Class"), read_hex("SubClass"), read_hex("Protocol")


def linux_tree(root: Path, names: UsbNames) -> list[Node]:
    paths: dict[tuple[int, tuple[int, ...]], Path] = {}
    interfaces: dict[str, list[Path]] = defaultdict(list)
    for path in root.iterdir():
        device, separator, _ = path.name.partition(":")
        if separator:
            interfaces[device].append(path)
        elif match := LINUX_DEVICE.fullmatch(device):
            bus, device_bus, port_path = match.groups()
            ports = tuple(map(int, port_path.split("."))) if port_path else ()
            paths[int(bus or device_bus), ports] = path

    buses: dict[int, Node] = {}
    devices: dict[tuple[int, tuple[int, ...]], Node] = {}
    for (bus_number, ports), path in sorted(paths.items()):
        speed = read_attribute(path, "speed")
        if not ports:
            controller = read_attribute(path, "product")
            buses[bus_number] = Node(
                f"USB bus {bus_number}",
                speed,
                details=(controller,) if controller else (),
            )
            continue

        vendor = read_attribute(path, "idVendor").lower()
        product = read_attribute(path, "idProduct").lower()
        usb_id = f"{vendor}:{product}"
        if not re.fullmatch(r"[0-9a-f]{4}:[0-9a-f]{4}", usb_id):
            continue  # The device may have been unplugged during enumeration.
        classes = [linux_class(path, "Device")]
        classes.extend(
            linux_class(interface, "Interface")
            for interface in sorted(interfaces[path.name])
        )
        name = device_name(
            usb_id,
            read_attribute(path, "manufacturer"),
            read_attribute(path, "product"),
            classes,
            names,
        )
        details = [usb_id, f"path {path.name}"]
        if (number := read_attribute(path, "devnum")).isdecimal():
            details.append(f"device {int(number):03}")
        # A hub can disappear mid-scan. Keep its children under the closest
        # available ancestor and show the remaining port path.
        parent_ports = ports[:-1]
        while parent_ports and (bus_number, parent_ports) not in devices:
            parent_ports = parent_ports[:-1]
        parent = devices.get((bus_number, parent_ports))
        if parent is None:
            parent = buses.setdefault(bus_number, Node(f"USB bus {bus_number}"))
        node = Node(name, speed, ports[len(parent_ports) :], tuple(details))
        devices[bus_number, ports] = node
        parent.children.append(node)
    return list(buses.values())


def registry_entries(value: object) -> list[RegistryEntry]:
    entries = cast(list[object], value) if isinstance(value, list) else [value]
    return [cast(RegistryEntry, entry) for entry in entries if isinstance(entry, dict)]


def registry_children(entry: RegistryEntry) -> list[RegistryEntry]:
    return registry_entries(entry.get("IORegistryEntryChildren"))


def registry_int(entry: RegistryEntry, key: str, default: int = 0) -> int:
    value = entry.get(key)
    return value if type(value) is int else default


def macos_devices(
    entries: Sequence[RegistryEntry], names: UsbNames, parent_port: int = 0
) -> list[Node]:
    devices: list[Node] = []
    for entry in entries:
        children = registry_children(entry)
        vendor = registry_int(entry, "idVendor", -1)
        product = registry_int(entry, "idProduct", -1)
        if (
            not 0 <= vendor <= 0xFFFF
            or not 0 <= product <= 0xFFFF
            or "bInterfaceNumber" in entry
        ):
            # Some registry trees include port objects between devices.
            port = entry.get("usb-port-number", entry.get("port"))
            port = int.from_bytes(port, "little") if isinstance(port, bytes) else port
            devices.extend(
                macos_devices(
                    children, names, port if isinstance(port, int) else parent_port
                )
            )
            continue

        usb_id = f"{vendor:04x}:{product:04x}"
        classes = [
            (
                registry_int(entry, "bDeviceClass"),
                registry_int(entry, "bDeviceSubClass"),
                registry_int(entry, "bDeviceProtocol"),
            )
        ]
        classes.extend(
            (
                registry_int(child, "bInterfaceClass"),
                registry_int(child, "bInterfaceSubClass"),
                registry_int(child, "bInterfaceProtocol"),
            )
            for child in children
            if "bInterfaceNumber" in child
        )
        name = device_name(
            usb_id,
            clean_text(entry.get("USB Vendor Name")),
            clean_text(entry.get("USB Product Name"))
            or clean_text(entry.get("IORegistryEntryName")),
            classes,
            names,
        )
        speed = MAC_SPEEDS.get(
            registry_int(entry, "USBSpeed", registry_int(entry, "Device Speed", -1)), ""
        )
        port = registry_int(entry, "PortNum") or parent_port
        location = registry_int(entry, "locationID")
        details = (usb_id, f"location {location:#010x}") if location else (usb_id,)
        devices.append(
            Node(
                name,
                speed,
                (port,) if port > 0 else (),
                details,
                macos_devices(children, names),
            )
        )

    return sorted(devices, key=lambda device: device.ports)


def macos_tree(plist: bytes, names: UsbNames) -> list[Node]:
    data = cast(object, plistlib.loads(plist))
    entries = registry_entries(data)
    if not isinstance(data, (dict, list)):
        raise TypeError("unexpected USB registry format")
    controllers: list[RegistryEntry] = []
    for entry in entries:
        if entry.get("IORegistryEntryName") == "Root":
            controllers.extend(registry_children(entry))
        else:
            controllers.append(entry)
    buses: list[Node] = []
    for index, controller in enumerate(controllers, start=1):
        name = clean_text(controller.get("IORegistryEntryName"))
        buses.append(
            Node(
                f"USB controller {index}",
                details=(name,) if name else (),
                children=macos_devices(registry_children(controller), names),
            )
        )
    return buses


def display_speed(speed: str) -> str:
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", speed):
        return ""
    mbps = float(speed)
    if mbps >= 1000:
        return f"{mbps / 1000:g} Gb/s"
    return f"{mbps:g} Mb/s" if mbps else ""


def tree_lines(
    buses: Sequence[Node], *, all_buses: bool, verbose: bool, ascii_only: bool
) -> Iterator[str]:
    branch, last_branch, vertical, separator = (
        ("|-- ", "`-- ", "|   ", "  |  ")
        if ascii_only
        else ("├── ", "└── ", "│   ", "  ·  ")
    )

    def label(node: Node) -> str:
        port_path = ".".join(map(str, node.ports))
        return f"Port {port_path}  {node.name}" if port_path else node.name

    def children(nodes: Sequence[Node], indent: str) -> Iterator[tuple[str, Node]]:
        for index, node in enumerate(nodes, start=1):
            last = index == len(nodes)
            yield indent + (last_branch if last else branch) + label(node), node
            yield from children(node.children, indent + ("    " if last else vertical))

    def display_width(value: str) -> int:
        if ascii_only:
            return len(value)
        return sum(
            2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
            for char in value
            if unicodedata.category(char) not in ("Mn", "Me")
        )

    rows: list[tuple[str, Node]] = []
    for bus in buses:
        if all_buses or bus.children:
            rows.append((label(bus), bus))
            rows.extend(children(bus.children, ""))
    if not rows:
        yield "No USB devices found."
        return

    name_heading = "USB topology"
    speed_heading = "Link speed"
    name_width = max(len(name_heading), *(display_width(name) for name, _ in rows))
    speeds = [display_speed(node.speed) or "-" for _, node in rows]
    speed_width = max(len(speed_heading), *(len(speed) for speed in speeds))
    yield f"{name_heading:<{name_width}}  {speed_heading:>{speed_width}}"
    for (name, node), speed in zip(rows, speeds, strict=True):
        padding = " " * (name_width - display_width(name) + 2)
        row = f"{name}{padding}{speed:>{speed_width}}"
        yield separator.join((row, *node.details)) if verbose else row


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="usbdev", description=__doc__)
    _ = parser.add_argument(
        "-a", "--all-buses", action="store_true", help="show empty USB buses"
    )
    _ = parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="include USB IDs and device locations",
    )
    args = parser.parse_args(argv)
    names = load_names(USB_IDS)
    try:
        if sys.platform.startswith("linux"):
            buses = linux_tree(SYSFS_USB, names)
        elif sys.platform == "darwin":
            scan = subprocess.run(
                ("/usr/sbin/ioreg", "-a", "-l", "-p", "IOUSB"),
                check=True,
                capture_output=True,
                timeout=10,
            )
            buses = macos_tree(scan.stdout, names)
        else:
            parser.exit(1, f"usbdev: unsupported platform: {sys.platform}\n")
    except (
        OSError,
        TypeError,
        ValueError,
        ExpatError,
        subprocess.SubprocessError,
    ) as error:
        parser.exit(1, f"usbdev: could not read USB devices: {error}\n")

    encoding = sys.stdout.encoding or "utf-8"
    ascii_only = "├─".encode(encoding, errors="replace").decode(encoding) != "├─"
    for line in tree_lines(
        buses,
        all_buses=cast(bool, args.all_buses),
        verbose=cast(bool, args.verbose),
        ascii_only=ascii_only,
    ):
        print(line.encode(encoding, errors="replace").decode(encoding))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Regression tests for the stdlib Linux CPU information utility."""

import json
import tempfile
import unittest
from pathlib import Path

from utils import cpuinfo


def write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(value, encoding="utf-8")


class CpuListTest(unittest.TestCase):
    def test_ranges_are_expanded_and_sorted(self) -> None:
        self.assertEqual(cpuinfo.parse_cpu_list("4,0-2,8-9"), (0, 1, 2, 4, 8, 9))

    def test_descending_range_is_rejected(self) -> None:
        with self.assertRaisesRegex(cpuinfo.CpuInfoError, "descending"):
            _ = cpuinfo.parse_cpu_list("3-1")


class ProcCpuInfoTest(unittest.TestCase):
    def test_records_are_parsed_without_x86_specific_assumptions(self) -> None:
        text = "processor: 0\nmodel name: Example CPU\ncpu MHz: 1200.5\n\n"
        text += "processor: 1\nmodel name: Example CPU\ncpu MHz: 800\n"
        records = cpuinfo.parse_proc_cpuinfo(text)

        self.assertEqual(records[0]["model name"], "Example CPU")
        self.assertEqual(cpuinfo.proc_megahertz(records[1]), 800.0)


class SnapshotTest(unittest.TestCase):
    def test_sysfs_topology_policy_cache_and_proc_fallback_are_combined(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            cpu_root = root / "sys"
            proc_path = root / "cpuinfo"
            write(cpu_root / "online", "0-1\n")
            write(cpu_root / "possible", "0-3\n")
            for cpu, core in ((0, 0), (1, 0)):
                topology = cpu_root / f"cpu{cpu}" / "topology"
                write(topology / "physical_package_id", "0\n")
                write(topology / "core_id", f"{core}\n")
            policy = cpu_root / "cpufreq" / "policy0"
            write(policy / "affected_cpus", "0-1\n")
            write(policy / "scaling_cur_freq", "2400000\n")
            write(policy / "scaling_min_freq", "800000\n")
            write(policy / "scaling_max_freq", "4200000\n")
            write(policy / "scaling_driver", "example-pstate\n")
            write(policy / "scaling_governor", "powersave\n")
            cache = cpu_root / "cpu0" / "cache" / "index0"
            write(cache / "level", "1\n")
            write(cache / "type", "Data\n")
            write(cache / "size", "32K\n")
            proc_text = "processor: 0\nvendor_id: ExampleVendor\n"
            proc_text += "model name: Example CPU\nmicrocode: 0x12\n"
            proc_text += "cpu MHz: 1000\n\nprocessor: 1\n"
            proc_text += "vendor_id: ExampleVendor\nmodel name: Example CPU\n"
            proc_text += "microcode: 0x12\ncpu MHz: 1100\n"
            write(proc_path, proc_text)

            snapshot = cpuinfo.collect_snapshot(cpu_root=cpu_root, proc_path=proc_path)

        self.assertEqual(snapshot.model, "Example CPU")
        self.assertEqual(snapshot.logical_cpus, 4)
        self.assertEqual(snapshot.online_cpus, 2)
        self.assertEqual(snapshot.physical_cores, 1)
        self.assertEqual(snapshot.sockets, 1)
        self.assertEqual(snapshot.caches, {"L1d": "32K"})
        self.assertEqual(snapshot.processors[0].current_mhz, 2400.0)
        self.assertEqual(snapshot.processors[1].driver, "example-pstate")

    def test_proc_frequency_is_used_when_cpufreq_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            cpu_root = root / "sys"
            proc_path = root / "cpuinfo"
            write(cpu_root / "online", "0\n")
            write(proc_path, "processor: 0\nmodel name: Example CPU\ncpu MHz: 987.5\n")

            snapshot = cpuinfo.collect_snapshot(cpu_root=cpu_root, proc_path=proc_path)

        self.assertEqual(snapshot.processors[0].current_mhz, 987.5)
        self.assertIsNone(snapshot.processors[0].driver)

    def test_json_contains_numeric_frequency_data(self) -> None:
        snapshot = cpuinfo.CpuSnapshot(
            architecture="x86_64",
            model="Example CPU",
            vendor="ExampleVendor",
            microcode=None,
            logical_cpus=1,
            online_cpus=1,
            physical_cores=1,
            sockets=1,
            caches={},
            processors=(
                cpuinfo.Processor(
                    cpu=0,
                    package=0,
                    core=0,
                    current_mhz=1234.5,
                    minimum_mhz=800.0,
                    maximum_mhz=4000.0,
                    driver="example",
                    governor="performance",
                ),
            ),
        )

        encoded = json.dumps(cpuinfo.snapshot_dict(snapshot))

        self.assertEqual(json.loads(encoded)["processors"][0]["current_mhz"], 1234.5)


class RenderingTest(unittest.TestCase):
    def test_frequency_format_switches_to_ghz(self) -> None:
        self.assertEqual(cpuinfo.format_frequency(900.0), "900 MHz")
        self.assertEqual(cpuinfo.format_frequency(2450.0), "2.45 GHz")
        self.assertEqual(cpuinfo.format_frequency(None), "unknown")


if __name__ == "__main__":
    _ = unittest.main()

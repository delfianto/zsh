#!/usr/bin/env python3
"""Display the processes using the most resident memory."""

import os
import sys
import time
from collections.abc import Iterator
from importlib import import_module
from typing import NotRequired, Protocol, TypedDict, cast


class ProcessMemory(Protocol):
    rss: int


class ProcessInfo(TypedDict):
    pid: int
    username: str | None
    memory_info: ProcessMemory | None
    name: str | None
    cmdline: list[str] | None
    cpu_percent: NotRequired[float | None]


class Process(Protocol):
    info: ProcessInfo


class SystemMemory(Protocol):
    total: int
    used: int
    percent: float


class Psutil(Protocol):
    def process_iter(self, attrs: list[str], /) -> Iterator[Process]: ...
    def virtual_memory(self) -> SystemMemory: ...
    def swap_memory(self) -> SystemMemory: ...
    def cpu_count(self, *, logical: bool) -> int | None: ...
    def cpu_percent(self, *, interval: float | None) -> float: ...


# --- Configuration ---
TOP_N = 15
BAR_WIDTH = 20
REFRESH_RATE = 2.0  # Seconds for watch mode

# --- Colors ---
C_RESET = "\033[0m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"
C_GRAY = "\033[90m"
C_BOLD = "\033[1m"
C_CYAN = "\033[96m"
C_MEM = "\033[33m"


def clear_screen() -> None:
    print("\033[2J\033[H", end="")


def get_smart_name(info: ProcessInfo) -> str:
    name = info["name"] or "N/A"
    cmdline = info["cmdline"]
    if name in ["python", "python3", "java", "node", "ruby"] and cmdline:
        for arg in cmdline:
            if arg.endswith(".py"):
                return arg.split("/")[-1]
            if "uvicorn" in arg:
                return "uvicorn"
            if "celery" in arg:
                return "celery"
            if "jar" in arg:
                return arg.split("/")[-1]
        if len(cmdline) > 1:
            return cmdline[1].split("/")[-1]
    return name


def format_bytes(size: int) -> str:
    power = 2**10
    n: float = size
    power_labels = {0: "", 1: "K", 2: "M", 3: "G", 4: "T"}
    count = 0
    while n > power:
        n /= power
        count += 1
    return f"{n:.1f}{power_labels[count]}"


def create_bar(percent: float, color_override: str | None = None) -> str:
    vis_percent = min(percent, 100)
    filled = int(vis_percent / 100 * BAR_WIDTH)

    if color_override:
        color = color_override
    else:
        color = C_GREEN
        if percent > 75:
            color = C_YELLOW
        if percent > 90:
            color = C_RED

    bar = "█" * filled + "░" * (BAR_WIDTH - filled)
    return f"{color}{bar}{C_RESET}"


def get_stress_label(load_percent: float) -> str:
    if load_percent < 50:
        return f"{C_GREEN}Chilling{C_RESET}"
    if load_percent < 80:
        return f"{C_GREEN}Active{C_RESET}"
    if load_percent < 100:
        return f"{C_YELLOW}Busy{C_RESET}"
    if load_percent < 150:
        return f"{C_RED}Strained{C_RESET}"
    return f"{C_RED}{C_BOLD}OVERLOAD{C_RESET}"


def print_dashboard(psutil: Psutil, watch_mode: bool = False) -> None:
    # Gather Process Data
    attrs = ["pid", "username", "memory_info", "name", "cmdline"]
    if watch_mode:
        attrs.append("cpu_percent")

    processes = (
        (memory.rss, process.info)
        for process in psutil.process_iter(attrs)
        if (memory := process.info["memory_info"]) is not None
    )
    top_procs = sorted(processes, key=lambda entry: entry[0], reverse=True)[:TOP_N]

    # Print Header
    if watch_mode:
        print(
            f"{C_BOLD}{'PID':<8} {'USER':<10} {'RSS':>8} {'CPU':>6} {'COMMAND':<25}{C_RESET}"
        )
        print(f"{C_GRAY}{'-' * 62}{C_RESET}")
    else:
        print(f"{C_BOLD}{'PID':<8} {'USER':<10} {'RSS':>8} {'COMMAND':<25}{C_RESET}")
        print(f"{C_GRAY}{'-' * 55}{C_RESET}")

    for rss, info in top_procs:
        pid = info["pid"]
        user = info["username"] or "N/A"
        if len(user) > 9:
            user = user[:8] + "+"

        mem = format_bytes(rss)
        name = get_smart_name(info)
        if len(name) > 24:
            name = name[:23] + "…"

        if watch_mode:
            cpu_val = info.get("cpu_percent") or 0.0

            cpu_color = C_RESET
            if cpu_val > 50:
                cpu_color = C_YELLOW
            if cpu_val > 80:
                cpu_color = C_RED

            print(
                f"{pid:<8} {user:<10} {C_MEM}{mem:>8}{C_RESET} {cpu_color}{cpu_val:>5.1f}%{C_RESET} {name:<25}"
            )
        else:
            print(f"{pid:<8} {user:<10} {C_MEM}{mem:>8}{C_RESET} {name:<25}")

    # System Stats Footer
    width = 62 if watch_mode else 55
    print(f"{C_GRAY}{'=' * width}{C_RESET}")

    mem = psutil.virtual_memory()
    print(
        f" RAM:    [{create_bar(mem.percent)}] {format_bytes(mem.used)} / {format_bytes(mem.total)}"
    )

    swap = psutil.swap_memory()
    if swap.total > 0:
        print(
            f" SWAP:   [{create_bar(swap.percent)}] {format_bytes(swap.used)} / {format_bytes(swap.total)}"
        )

    cpu_pct = psutil.cpu_percent(interval=None)
    print(f" CPU:    [{create_bar(cpu_pct, C_CYAN)}] {cpu_pct:.1f}%")

    load1, _, _ = os.getloadavg()
    cpu_cores = psutil.cpu_count(logical=True)

    # Ensure cpu_cores is an int, not None
    if not cpu_cores:
        cpu_cores = 1

    stress_percent = (load1 / cpu_cores) * 100
    stress_bar = create_bar(stress_percent)
    stress_label = get_stress_label(stress_percent)

    print(f" STRESS: [{stress_bar}] {stress_percent:.0f}% ({stress_label})")


def main() -> None:
    try:
        psutil = cast(Psutil, cast(object, import_module("psutil")))
    except ImportError:
        sys.exit("psmem: psutil is required")

    watch_mode = "--watch" in sys.argv

    _ = psutil.cpu_percent(interval=None)

    try:
        if watch_mode:
            while True:
                clear_screen()
                print_dashboard(psutil, watch_mode=True)
                print(
                    f"\n{C_GRAY}[CTRL+C to quit] Refreshing every {REFRESH_RATE}s...{C_RESET}"
                )
                time.sleep(REFRESH_RATE)
        else:
            _ = psutil.cpu_percent(interval=0.1)
            print_dashboard(psutil)

    except KeyboardInterrupt:
        print(f"\n{C_GREEN}Done.{C_RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()

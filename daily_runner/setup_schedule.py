#!/usr/bin/env python3
"""Set up a cron job (Linux/macOS) to run the daily recommender automatically.

Usage:
    python -m daily_runner.setup_schedule            # install cron job
    python -m daily_runner.setup_schedule --remove    # remove cron job
    python -m daily_runner.setup_schedule --show      # show current cron entry

The schedule time and timezone are read from daily_runner/watchlist.yaml.
"""

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CRON_TAG = "# tradingagents-daily-recommender"


def _load_schedule_cfg() -> dict:
    cfg_path = Path(__file__).resolve().parent / "watchlist.yaml"
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)
    return cfg.get("schedule", {})


def _build_cron_line(hour: int, minute: int) -> str:
    python = sys.executable
    runner = _PROJECT_ROOT / "daily_runner" / "run.py"
    log = _PROJECT_ROOT / "daily_reports" / "cron.log"
    return (
        f"{minute} {hour} * * 1-5 "
        f"cd {_PROJECT_ROOT} && {python} {runner} "
        f">> {log} 2>&1 {_CRON_TAG}"
    )


def _get_current_crontab() -> str:
    try:
        return subprocess.check_output(["crontab", "-l"], text=True)
    except subprocess.CalledProcessError:
        return ""


def install() -> None:
    schedule_cfg = _load_schedule_cfg()
    time_str = schedule_cfg.get("time", "07:00")
    hour, minute = (int(x) for x in time_str.split(":"))
    tz = schedule_cfg.get("timezone", "US/Eastern")

    cron_line = _build_cron_line(hour, minute)

    current = _get_current_crontab()
    # Remove old entry if present
    lines = [l for l in current.splitlines() if _CRON_TAG not in l]
    # Add TZ env var and new line
    lines.append(f"TZ={tz}")
    lines.append(cron_line)
    new_crontab = "\n".join(lines) + "\n"

    proc = subprocess.run(
        ["crontab", "-"], input=new_crontab, text=True, capture_output=True
    )
    if proc.returncode != 0:
        print(f"Failed to install crontab: {proc.stderr}", file=sys.stderr)
        sys.exit(1)

    print(f"Cron job installed: runs weekdays at {time_str} ({tz})")
    print(f"  {cron_line}")


def remove() -> None:
    current = _get_current_crontab()
    lines = [l for l in current.splitlines()
             if _CRON_TAG not in l and not l.startswith("TZ=")]
    new_crontab = "\n".join(lines) + "\n" if lines else ""
    subprocess.run(["crontab", "-"], input=new_crontab, text=True)
    print("Cron job removed.")


def show() -> None:
    current = _get_current_crontab()
    found = [l for l in current.splitlines() if _CRON_TAG in l]
    if found:
        print("Current cron entry:")
        for l in found:
            print(f"  {l}")
    else:
        print("No daily recommender cron job found.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage daily recommender cron job")
    parser.add_argument("--remove", action="store_true", help="Remove the cron job")
    parser.add_argument("--show", action="store_true", help="Show current cron entry")
    args = parser.parse_args()

    if args.remove:
        remove()
    elif args.show:
        show()
    else:
        install()


if __name__ == "__main__":
    main()

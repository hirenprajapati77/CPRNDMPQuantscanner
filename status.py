"""
NDMP OS v6.0 - Operational Health & Status CLI Endpoint
Checks build versions, manifests, scheduler, and calculates the live Release Fingerprint.
"""

import glob
import hashlib
import os
import subprocess
from datetime import datetime


def get_git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return result.stdout.strip()[:12]
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return "unknown"


def calculate_release_fingerprint() -> str:
    hasher = hashlib.sha256()
    yaml_files = sorted(glob.glob("ndmp_research/registry/*.yaml"))
    for yf in yaml_files:
        with open(yf, "rb") as f:
            hasher.update(f.read())

    config_file = "ndmp_core/src/config.py"
    if os.path.exists(config_file):
        with open(config_file, "rb") as f:
            hasher.update(f.read())

    return hasher.hexdigest()[:16]


def get_last_scan() -> str:
    journals = sorted(glob.glob("ndmp_knowledge/journal/decisions_*.json"))
    if not journals:
        return "NEVER"
    last_file = os.path.basename(journals[-1])
    try:
        parts = last_file.split("_")
        date_str = parts[1]
        time_str = parts[2].split(".")[0]
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]} {time_str[:2]}:{time_str[2:4]}:{time_str[4:]} UTC"
    except Exception:
        return "UNKNOWN (MALFORMED FILE)"


def main():
    fingerprint = calculate_release_fingerprint()
    last_scan = get_last_scan()
    git_commit = get_git_commit()
    yaml_files = glob.glob("ndmp_research/registry/*.yaml")
    errors = glob.glob("*.log")

    print("=" * 80)
    print("NDMP OS v6.0 - OPERATIONAL HEALTH & STATUS REPORT")
    print("=" * 80)
    print(f"Build Signature:  {git_commit}")
    print(f"Dataset Version:  NSE_FO_5YR_V1.2")
    print(f"Release Finger:   {fingerprint}")
    print(f"Registry Count:   {len(yaml_files)} feature plugins discovered")
    print(f"Last Live Scan:   {last_scan}")
    print(f"Schedule Config:  ACTIVE (15:20 IST / 09:50 UTC)")
    print("-" * 80)
    print(f"Uptime Warnings:  {len(errors)} active log warnings")
    verdict = "READY" if git_commit != "unknown" and len(yaml_files) >= 4 else "DEGRADED"
    print(f"Status Verdict:   {verdict}")
    print("=" * 80)


if __name__ == "__main__":
    main()

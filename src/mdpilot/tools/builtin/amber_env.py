"""AMBER environment detection tool for mdpilot."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Optional

from mdpilot.tools.decorator import tool


@tool(
    name="amber_env_check",
    description="Check AMBER environment: AMBERHOME, version, and available executables.",
    category="amber",
)
def amber_env_check() -> str:
    """Check the AMBER installation environment.

    Returns a formatted string describing the AMBER environment.

    Returns:
        Formatted string with AMBER environment details, or error message.
    """
    lines = ["=== AMBER Environment Check ==="]

    # Check AMBERHOME
    amber_home = os.environ.get("AMBERHOME")
    if amber_home:
        lines.append(f"AMBERHOME: {amber_home}")
    else:
        lines.append("AMBERHOME: NOT SET")

    # Check for common AMBER executables
    executables = [
        "pmemd",
        "sander",
        "tleap",
        "antechamber",
        "parmchk2",
        "cpptraj",
        "metals",
    ]

    found: list[str] = []
    missing: list[str] = []

    for exe in executables:
        if shutil.which(exe):
            found.append(exe)
        else:
            missing.append(exe)

    lines.append(f"\nAvailable executables ({len(found)}):")
    for exe in found:
        lines.append(f"  [+] {exe}")

    if missing:
        lines.append(f"\nMissing executables ({len(missing)}):")
        for exe in missing:
            lines.append(f"  [-] {exe}")

    # Try to detect version via cpptraj
    try:
        result = subprocess.run(
            ["cpptraj", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            version_output = result.stdout + result.stderr
            # Look for version string
            for line in version_output.split("\n"):
                if "Version" in line or "AmberTools" in line:
                    lines.append(f"\nVersion info: {line.strip()}")
                    break
    except (FileNotFoundError, subprocess.TimeoutExpired, NotADirectoryError, OSError):
        pass

    # Check if AMBERHOME directory exists and list some contents
    if amber_home and os.path.isdir(amber_home):
        lines.append(f"\nAMBERHOME contents (top-level):")
        try:
            entries = os.listdir(amber_home)
            for entry in sorted(entries)[:20]:
                full_path = os.path.join(amber_home, entry)
                marker = "/" if os.path.isdir(full_path) else ""
                lines.append(f"  {entry}{marker}")
            if len(entries) > 20:
                lines.append(f"  ... ({len(entries) - 20} more entries)")
        except PermissionError:
            lines.append("  (permission denied)")

    return "\n".join(lines)

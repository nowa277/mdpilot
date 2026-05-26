"""Auto-detect local AMBER/AmberTools installation.

Called once at startup (CLI / TUI).  Searches standard install paths,
sets OS-level environment variables (AMBERHOME, PATH, LD_LIBRARY_PATH),
detects available executables and GPU support, then returns a structured
snapshot that the config system and agent can consume immediately.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# --------------------------------------------------------------------------- #
# Data structures
# --------------------------------------------------------------------------- #

@dataclass
class AmberExecutable:
    """One AMBER executable and its status."""

    name: str
    available: bool = False
    path: str | None = None
    version: str | None = None


@dataclass
class AmberEnvironment:
    """Complete snapshot of the detected AMBER environment."""

    amber_home: str | None = None
    tools_version: str | None = None
    source: str | None = None  # how it was found: "env", "search", "conda", …
    gpu_enabled: bool = False
    executables: list[AmberExecutable] = field(default_factory=list)
    env_applied: bool = False  # were OS env vars actually modified?

    @property
    def available(self) -> bool:
        return self.amber_home is not None

    def summary_lines(self) -> list[str]:
        """Human-readable summary for startup banner / logging."""
        lines = ["[bold cyan]AMBER Environment[/bold cyan]"]
        if not self.available:
            lines.append("  [yellow]No local AMBER installation detected.[/yellow]")
            lines.append("  Set AMBERHOME or install AmberTools to enable simulation tools.")
            return lines

        lines.append(f"  AMBERHOME  : {self.amber_home}")
        lines.append(f"  Version    : {self.tools_version or 'unknown'}")
        lines.append(f"  GPU        : {'yes' if self.gpu_enabled else 'no'}")
        lines.append(f"  Detected via: {self.source}")

        found = [e for e in self.executables if e.available]
        missing = [e for e in self.executables if not e.available]
        if found:
            lines.append(f"  Tools ({len(found)}): {', '.join(e.name for e in found)}")
        if missing:
            lines.append(f"  Missing ({len(missing)}): {', '.join(e.name for e in missing)}")

        if self.env_applied:
            lines.append("  [dim]Environment variables applied automatically.[/dim]")

        return lines


# --------------------------------------------------------------------------- #
# Executables we care about
# --------------------------------------------------------------------------- #

_CORE_EXES: list[str] = [
    "sander",
    "tleap",
    "antechamber",
    "parmchk2",
    "cpptraj",
    "ambpdb",
    "pdb4amber",
    "parmed",
    "reduce",
    "sqm",
    "MMPBSA.py",
    "nab",
    "mdgx",
]

_GPU_EXES: list[str] = [
    "pmemd",
    "pmemd.MPI",
    "pmemd.cuda",
    "pmemd.cuda.MPI",
]


# --------------------------------------------------------------------------- #
# Search strategies
# --------------------------------------------------------------------------- #

def _check_env() -> str | None:
    """Strategy 1: AMBERHOME already set in environment."""
    home = os.environ.get("AMBERHOME")
    if home and Path(home, "bin").is_dir():
        return home
    return None


def _search_common_paths() -> str | None:
    """Strategy 2: scan well-known install locations."""
    candidates: list[Path] = []

    # Home directory expansions
    home = Path.home()
    candidates += [
        home / "amber25",
        home / "amber24",
        home / "amber",
        home / "Downloads" / "ambertools25" / "ambertools25",
        home / "Downloads" / "ambertools25",
        home / "opt" / "amber25",
        home / "opt" / "ambertools25",
    ]

    # System-wide paths
    candidates += [
        Path("/opt/amber25"),
        Path("/opt/amber24"),
        Path("/opt/amber"),
        Path("/usr/local/amber25"),
        Path("/usr/local/amber"),
    ]

    # Conda environments (most common for AmberTools)
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        candidates.append(Path(conda_prefix))

    for path in candidates:
        if path.is_dir() and (path / "bin").is_dir():
            return str(path)

    return None


def _find_conda_envs() -> str | None:
    """Strategy 3: look for conda envs with amber packages."""
    conda_exe = shutil.which("conda")
    if not conda_exe:
        return None

    try:
        result = subprocess.run(
            [conda_exe, "env", "list", "--json"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return None
        import json
        data = json.loads(result.stdout)
        for env_path_str in data.get("envs", []):
            env_path = Path(env_path_str)
            if (env_path / "bin" / "sander").exists() or (env_path / "bin" / "tleap").exists():
                return str(env_path)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass

    return None


def _scan_downloads_recursive() -> str | None:
    """Strategy 4: deep scan ~/Downloads for ambertools directories."""
    downloads = Path.home() / "Downloads"
    if not downloads.is_dir():
        return None

    for item in downloads.rglob("amber.sh"):
        parent = item.parent
        if (parent / "bin").is_dir():
            return str(parent)

    return None


# --------------------------------------------------------------------------- #
# Version / GPU detection helpers
# --------------------------------------------------------------------------- #

def _detect_sander_version(bin_dir: Path) -> str | None:
    """Get sander version string."""
    sander = bin_dir / "sander"
    if not sander.exists():
        return None
    try:
        result = subprocess.run(
            [str(sander), "--version"],
            capture_output=True, text=True, timeout=10,
        )
        output = result.stdout + result.stderr
        for line in output.splitlines():
            if "Version" in line:
                return line.strip()
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def _detect_cpptraj_version(bin_dir: Path) -> str | None:
    """Get cpptraj version string."""
    cpptraj = bin_dir / "cpptraj"
    if not cpptraj.exists():
        return None
    try:
        result = subprocess.run(
            [str(cpptraj), "--version"],
            capture_output=True, text=True, timeout=10,
        )
        output = result.stdout + result.stderr
        for line in output.splitlines():
            if "Version" in line or "AmberTools" in line:
                return line.strip()
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def _detect_tools_version(amber_home: str) -> str | None:
    """Determine AmberTools version from version file or binary output."""
    home = Path(amber_home)

    # Try version file
    for name in ("amber.version", "VERSION"):
        vf = home / name
        if vf.exists():
            content = vf.read_text().strip()
            if content:
                return content

    # Try sander binary
    v = _detect_sander_version(home / "bin")
    if v:
        # Extract version number like "24.0"
        import re
        m = re.search(r"(\d+\.\d+)", v)
        if m:
            return m.group(1)

    return None


def _detect_gpu(bin_dir: Path) -> bool:
    """Check for GPU-accelerated executables."""
    for name in _GPU_EXES:
        if (bin_dir / name).exists():
            return True
    return False


# --------------------------------------------------------------------------- #
# Probe individual executables
# --------------------------------------------------------------------------- #

def _probe_executables(bin_dir: Path) -> list[AmberExecutable]:
    """Check availability of each AMBER executable."""
    all_names = _CORE_EXES + _GPU_EXES
    results: list[AmberExecutable] = []

    for name in all_names:
        exe_path = bin_dir / name
        if exe_path.exists() and os.access(str(exe_path), os.X_OK):
            results.append(AmberExecutable(name=name, available=True, path=str(exe_path)))
        elif shutil.which(name):
            found = shutil.which(name)
            results.append(AmberExecutable(name=name, available=True, path=found))
        else:
            results.append(AmberExecutable(name=name, available=False))

    return results


# --------------------------------------------------------------------------- #
# Apply environment to current process
# --------------------------------------------------------------------------- #

def _apply_env(amber_home: str) -> None:
    """Set AMBERHOME, PATH, LD_LIBRARY_PATH, PYTHONPATH in os.environ."""
    home = Path(amber_home)
    bin_dir = str(home / "bin")
    lib_dir = str(home / "lib")

    # PATH
    existing_path = os.environ.get("PATH", "")
    if bin_dir not in existing_path.split(os.pathsep):
        os.environ["PATH"] = bin_dir + os.pathsep + existing_path

    # AMBERHOME
    os.environ["AMBERHOME"] = str(home)

    # LD_LIBRARY_PATH
    existing_ld = os.environ.get("LD_LIBRARY_PATH", "")
    if lib_dir not in existing_ld.split(os.pathsep):
        os.environ["LD_LIBRARY_PATH"] = lib_dir + os.pathsep + existing_ld

    # PYTHONPATH — find site-packages
    for sp in home.rglob("site-packages"):
        sp_str = str(sp)
        existing_py = os.environ.get("PYTHONPATH", "")
        if sp_str not in existing_py.split(os.pathsep):
            os.environ["PYTHONPATH"] = sp_str + os.pathsep + existing_py
        break  # first match is enough


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def detect_amber_env(apply: bool = True) -> AmberEnvironment:
    """Detect the local AMBER installation.

    Parameters
    ----------
    apply : bool
        If True (default), set OS environment variables so that
        subprocess calls to sander/tleap/etc. work immediately.

    Returns
    -------
    AmberEnvironment
        Structured snapshot of the detected environment.
    """
    # Run search strategies in priority order
    amber_home: str | None = None
    source: str | None = None

    # Strategy 1: existing env var
    amber_home = _check_env()
    if amber_home:
        source = "env"

    # Strategy 2: common paths
    if not amber_home:
        amber_home = _search_common_paths()
        if amber_home:
            source = "path_search"

    # Strategy 3: conda envs
    if not amber_home:
        amber_home = _find_conda_envs()
        if amber_home:
            source = "conda"

    # Strategy 4: recursive scan
    if not amber_home:
        amber_home = _scan_downloads_recursive()
        if amber_home:
            source = "recursive_scan"

    # Nothing found
    if not amber_home:
        return AmberEnvironment()

    home_path = Path(amber_home)
    bin_dir = home_path / "bin"

    # Probe
    tools_version = _detect_tools_version(amber_home)
    gpu_enabled = _detect_gpu(bin_dir)
    executables = _probe_executables(bin_dir)

    # Apply env vars
    env_applied = False
    if apply:
        _apply_env(amber_home)
        env_applied = True

    return AmberEnvironment(
        amber_home=amber_home,
        tools_version=tools_version,
        source=source,
        gpu_enabled=gpu_enabled,
        executables=executables,
        env_applied=env_applied,
    )

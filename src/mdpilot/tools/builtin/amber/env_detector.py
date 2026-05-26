"""AmberTools environment detection and configuration.

This module automatically detects AmberTools installation paths and
configures the environment for AMBER tools.
"""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AmberEnvironment:
    """AmberTools environment configuration.

    Attributes
    ----------
    amberhome : Path
        AMBERHOME directory path
    bin_dir : Path
        Binary directory (AMBERHOME/bin)
    dat_dir : Path
        Data directory (AMBERHOME/dat)
    lib_dir : Path
        Library directory (AMBERHOME/lib)
    version : str | None
        AmberTools version (e.g., "26")
    """

    amberhome: Path
    bin_dir: Path
    dat_dir: Path
    lib_dir: Path
    version: Optional[str] = None

    def __post_init__(self):
        """Validate paths after initialization."""
        if not self.amberhome.exists():
            raise ValueError(f"AMBERHOME does not exist: {self.amberhome}")
        if not self.bin_dir.exists():
            raise ValueError(f"Binary directory does not exist: {self.bin_dir}")

    def to_env_dict(self) -> dict[str, str]:
        """Convert to environment variable dictionary.

        Returns
        -------
        dict[str, str]
            Environment variables (AMBERHOME, PATH, LD_LIBRARY_PATH)
        """
        env = os.environ.copy()
        env["AMBERHOME"] = str(self.amberhome)

        # Add bin to PATH
        path_parts = env.get("PATH", "").split(os.pathsep)
        bin_str = str(self.bin_dir)
        if bin_str not in path_parts:
            path_parts.insert(0, bin_str)
        env["PATH"] = os.pathsep.join(path_parts)

        # Add lib to LD_LIBRARY_PATH (Linux) or DYLD_LIBRARY_PATH (macOS)
        if self.lib_dir.exists():
            lib_str = str(self.lib_dir)
            if os.name == "posix":
                if "darwin" in os.uname().sysname.lower():
                    lib_var = "DYLD_LIBRARY_PATH"
                else:
                    lib_var = "LD_LIBRARY_PATH"

                lib_parts = env.get(lib_var, "").split(os.pathsep)
                if lib_str not in lib_parts:
                    lib_parts.insert(0, lib_str)
                env[lib_var] = os.pathsep.join(lib_parts)

        return env

    def apply(self) -> None:
        """Apply environment configuration to current process."""
        env = self.to_env_dict()
        os.environ.update(env)
        logger.info(f"Applied AmberTools environment: AMBERHOME={self.amberhome}")

    def __str__(self) -> str:
        """Human-readable string representation."""
        lines = [
            f"AMBERHOME: {self.amberhome}",
            f"Version: {self.version or 'unknown'}",
            f"Binary directory: {self.bin_dir}",
            f"Data directory: {self.dat_dir}",
            f"Library directory: {self.lib_dir}",
        ]
        return "\n".join(lines)


class AmberEnvironmentDetector:
    """Detects AmberTools installation and configures environment.

    Search order:
    1. AMBERHOME environment variable
    2. User-specified path
    3. Standard installation paths:
       - ~/amber{26,24,22,20}
       - ~/Downloads/amber{26,24,22,20}/ambertools{26,24,22,20}
       - /opt/amber{26,24,22,20}
       - /usr/local/amber{26,24,22,20}
       - $CONDA_PREFIX (if in conda environment)
    """

    STANDARD_PATHS = [
        # Home directory installations
        Path.home() / "amber26",
        Path.home() / "amber24",
        Path.home() / "amber22",
        Path.home() / "amber20",

        # Downloads directory (user's specific case)
        Path.home() / "Downloads" / "amber26" / "ambertools26",
        Path.home() / "Downloads" / "amber24" / "ambertools24",
        Path.home() / "Downloads" / "amber22" / "ambertools22",

        # System-wide installations
        Path("/opt/amber26"),
        Path("/opt/amber24"),
        Path("/opt/amber22"),
        Path("/opt/amber20"),
        Path("/usr/local/amber26"),
        Path("/usr/local/amber24"),
        Path("/usr/local/amber22"),
        Path("/usr/local/amber20"),
    ]

    def __init__(self):
        self._cache: Optional[AmberEnvironment] = None

    def detect(
        self,
        user_path: str | Path | None = None,
        use_cache: bool = True,
    ) -> AmberEnvironment:
        """Detect AmberTools installation.

        Parameters
        ----------
        user_path : str | Path | None
            User-specified AMBERHOME path (highest priority)
        use_cache : bool
            Use cached result if available

        Returns
        -------
        AmberEnvironment
            Detected environment configuration

        Raises
        ------
        RuntimeError
            If AmberTools installation not found
        """
        if use_cache and self._cache is not None:
            return self._cache

        # Priority 1: User-specified path
        if user_path is not None:
            env = self._validate_path(Path(user_path))
            if env is not None:
                self._cache = env
                return env
            raise RuntimeError(f"Invalid AMBERHOME path: {user_path}")

        # Priority 2: AMBERHOME environment variable
        amberhome_env = os.environ.get("AMBERHOME")
        if amberhome_env:
            env = self._validate_path(Path(amberhome_env))
            if env is not None:
                logger.info(f"Using AMBERHOME from environment: {amberhome_env}")
                self._cache = env
                return env

        # Priority 3: Conda environment
        conda_prefix = os.environ.get("CONDA_PREFIX")
        if conda_prefix:
            env = self._validate_conda_path(Path(conda_prefix))
            if env is not None:
                logger.info(f"Using AmberTools from conda: {conda_prefix}")
                self._cache = env
                return env

        # Priority 4: Standard paths
        for path in self.STANDARD_PATHS:
            env = self._validate_path(path)
            if env is not None:
                logger.info(f"Found AmberTools at: {path}")
                self._cache = env
                return env

        # Not found
        raise RuntimeError(
            "AmberTools installation not found. Please:\n"
            "1. Set AMBERHOME environment variable, or\n"
            "2. Install via conda: conda install -c conda-forge ambertools, or\n"
            "3. Specify path explicitly"
        )

    def _validate_path(self, path: Path) -> Optional[AmberEnvironment]:
        """Validate a potential AMBERHOME path.

        Parameters
        ----------
        path : Path
            Potential AMBERHOME directory

        Returns
        -------
        AmberEnvironment | None
            Environment if valid, None otherwise
        """
        if not path.exists():
            return None

        # Check for required directories
        bin_dir = path / "bin"
        dat_dir = path / "dat"

        if not bin_dir.exists():
            return None

        # Check for key executables
        required_tools = ["pdb4amber", "tleap", "sander"]
        for tool in required_tools:
            tool_path = bin_dir / tool
            if not tool_path.exists() and not shutil.which(tool, path=str(bin_dir)):
                logger.debug(f"Missing required tool: {tool} in {bin_dir}")
                return None

        # Extract version from path
        version = None
        for part in path.parts:
            if part.startswith("amber") and part[5:].isdigit():
                version = part[5:]
                break

        lib_dir = path / "lib"

        return AmberEnvironment(
            amberhome=path,
            bin_dir=bin_dir,
            dat_dir=dat_dir,
            lib_dir=lib_dir,
            version=version,
        )

    def _validate_conda_path(self, conda_prefix: Path) -> Optional[AmberEnvironment]:
        """Validate conda environment for AmberTools.

        Parameters
        ----------
        conda_prefix : Path
            Conda environment prefix

        Returns
        -------
        AmberEnvironment | None
            Environment if valid, None otherwise
        """
        bin_dir = conda_prefix / "bin"
        dat_dir = conda_prefix / "dat"

        if not bin_dir.exists():
            return None

        # Check for pdb4amber (key AmberTools executable)
        if not (bin_dir / "pdb4amber").exists():
            return None

        lib_dir = conda_prefix / "lib"

        return AmberEnvironment(
            amberhome=conda_prefix,
            bin_dir=bin_dir,
            dat_dir=dat_dir,
            lib_dir=lib_dir,
            version="conda",
        )

    def find_tool(self, tool_name: str) -> Optional[Path]:
        """Find a specific AMBER tool executable.

        Parameters
        ----------
        tool_name : str
            Tool name (e.g., "pdb4amber", "tleap")

        Returns
        -------
        Path | None
            Path to executable if found, None otherwise
        """
        try:
            env = self.detect()
            tool_path = env.bin_dir / tool_name
            if tool_path.exists():
                return tool_path
        except RuntimeError:
            pass

        # Fallback to system PATH
        tool_path = shutil.which(tool_name)
        if tool_path:
            return Path(tool_path)

        return None


# Global detector instance
_detector = AmberEnvironmentDetector()


def detect_amber_environment(
    user_path: str | Path | None = None,
    use_cache: bool = True,
) -> AmberEnvironment:
    """Detect and return AmberTools environment.

    Parameters
    ----------
    user_path : str | Path | None
        User-specified AMBERHOME path
    use_cache : bool
        Use cached result if available

    Returns
    -------
    AmberEnvironment
        Detected environment configuration
    """
    return _detector.detect(user_path=user_path, use_cache=use_cache)


def find_amber_tool(tool_name: str) -> Optional[Path]:
    """Find a specific AMBER tool executable.

    Parameters
    ----------
    tool_name : str
        Tool name (e.g., "pdb4amber", "tleap")

    Returns
    -------
    Path | None
        Path to executable if found, None otherwise
    """
    return _detector.find_tool(tool_name)


def configure_amber_environment(user_path: str | Path | None = None) -> AmberEnvironment:
    """Detect and apply AmberTools environment configuration.

    Parameters
    ----------
    user_path : str | Path | None
        User-specified AMBERHOME path

    Returns
    -------
    AmberEnvironment
        Applied environment configuration
    """
    env = detect_amber_environment(user_path=user_path)
    env.apply()
    return env

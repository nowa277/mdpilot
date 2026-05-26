"""H++ server automation for protein protonation.

H++ (http://biophysics.cs.vt.edu/H++) is a web-based tool for adding
hydrogen atoms to protein structures and optimizing their positions based on pH.

This module provides CLI automation using Playwright for web interaction.

References:
- Gordon et al. (2005) Nucleic Acids Res. 33, W368-W371
- Anandakrishnan et al. (2012) Nucleic Acids Res. 40, W537-W541

Note: H++ does not provide a public REST API, so this implementation uses
web automation. This requires playwright to be installed:
    pip install playwright
    playwright install chromium
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)


@dataclass
class HPlusPlusConfig:
    """Configuration for H++ server submission."""

    ph: float = 7.0  # Target pH
    salinity: float = 0.15  # Salt concentration (M)
    internal_dielectric: float = 10.0  # Internal dielectric constant
    external_dielectric: float = 80.0  # External dielectric constant
    output_format: Literal["pdb", "pqr", "amber"] = "pdb"


@dataclass
class HPlusPlusResult:
    """Result from H++ server."""

    success: bool
    output_pdb: Path | None = None
    output_pqr: Path | None = None
    output_amber_prmtop: Path | None = None
    output_amber_inpcrd: Path | None = None
    log: str | None = None
    error: str | None = None


class HPlusPlusWrapper:
    """Wrapper for H++ server automation using Playwright.

    Note: This is a web automation approach since H++ does not provide
    a public REST API. Requires playwright installation.
    """

    H_PLUS_PLUS_URL = "http://newbiophysics.cs.vt.edu/H++/"

    def __init__(self):
        """Initialize H++ wrapper."""
        self._check_playwright()

    def _check_playwright(self) -> bool:
        """Check if playwright is installed."""
        try:
            import playwright
            return True
        except ImportError:
            logger.warning(
                "playwright not installed. Install with: "
                "pip install playwright && playwright install chromium"
            )
            return False

    def is_available(self) -> bool:
        """Check if H++ automation is available."""
        return self._check_playwright()

    def run(
        self,
        pdb_file: Path | str,
        config: HPlusPlusConfig | None = None,
        output_dir: Path | str | None = None,
        timeout: int = 300
    ) -> HPlusPlusResult:
        """Submit PDB file to H++ server and retrieve results.

        Args:
            pdb_file: Path to input PDB file
            config: H++ configuration (default: pH 7.0, 0.15M salt)
            output_dir: Directory for output files (default: same as input)
            timeout: Maximum wait time in seconds (default: 300)

        Returns:
            HPlusPlusResult with protonated structure

        Raises:
            RuntimeError: If playwright is not available or submission fails
            FileNotFoundError: If PDB file does not exist
            TimeoutError: If job does not complete within timeout
        """
        if not self.is_available():
            raise RuntimeError(
                "playwright not installed. Install with: "
                "pip install playwright && playwright install chromium"
            )

        # Validate input
        pdb_file = Path(pdb_file).resolve()
        if not pdb_file.exists():
            raise FileNotFoundError(f"PDB file not found: {pdb_file}")
        if not pdb_file.is_file():
            raise ValueError(f"Path is not a file: {pdb_file}")

        # Set defaults
        if config is None:
            config = HPlusPlusConfig()
        if output_dir is None:
            output_dir = pdb_file.parent
        else:
            output_dir = Path(output_dir).resolve()
            output_dir.mkdir(parents=True, exist_ok=True)

        # Run automation
        logger.info(f"Submitting {pdb_file.name} to H++ server")
        logger.info(f"Parameters: pH={config.ph}, salinity={config.salinity}M")

        try:
            return self._automate_submission(pdb_file, config, output_dir, timeout)
        except Exception as e:
            logger.error(f"H++ automation failed: {e}")
            return HPlusPlusResult(
                success=False,
                error=str(e)
            )

    def _automate_submission(
        self,
        pdb_file: Path,
        config: HPlusPlusConfig,
        output_dir: Path,
        timeout: int
    ) -> HPlusPlusResult:
        """Automate H++ web submission using Playwright.

        This method:
        1. Opens H++ website
        2. Uploads PDB file
        3. Sets parameters (pH, salinity, etc.)
        4. Submits job
        5. Waits for completion
        6. Downloads results

        Args:
            pdb_file: Input PDB file
            config: H++ configuration
            output_dir: Output directory
            timeout: Maximum wait time

        Returns:
            HPlusPlusResult with downloaded files
        """
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

        with sync_playwright() as p:
            # Launch browser (headless mode)
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            try:
                # Step 1: Navigate to H++ server with retry
                logger.info("Opening H++ server")
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        page.goto(self.H_PLUS_PLUS_URL, timeout=30000)
                        logger.debug(f"Successfully loaded H++ server (attempt {attempt + 1})")
                        break
                    except PlaywrightTimeout:
                        if attempt == max_retries - 1:
                            raise RuntimeError(
                                f"Failed to load H++ server after {max_retries} attempts. "
                                "Server may be down or unreachable."
                            )
                        logger.warning(f"Timeout loading H++ server, retrying ({attempt + 1}/{max_retries})")
                        time.sleep(2)

                # Step 2: Upload PDB file
                logger.info("Uploading PDB file")
                try:
                    file_input = page.locator('input[type="file"]').first
                    if file_input.count() == 0:
                        raise RuntimeError("Could not find file upload input on H++ page")
                    file_input.set_input_files(str(pdb_file))
                    logger.debug(f"Uploaded {pdb_file.name}")
                except Exception as e:
                    raise RuntimeError(f"Failed to upload PDB file: {e}")

                # Step 3: Set parameters
                logger.info("Setting parameters")
                try:
                    # pH
                    ph_input = page.locator('input[name="ph"]').first
                    if ph_input.count() > 0:
                        ph_input.fill(str(config.ph))
                        logger.debug(f"Set pH = {config.ph}")
                    else:
                        logger.warning("Could not find pH input field")

                    # Salinity
                    salt_input = page.locator('input[name="salinity"]').first
                    if salt_input.count() > 0:
                        salt_input.fill(str(config.salinity))
                        logger.debug(f"Set salinity = {config.salinity} M")
                    else:
                        logger.warning("Could not find salinity input field")

                    # Internal dielectric
                    int_diel_input = page.locator('input[name="intdiel"]').first
                    if int_diel_input.count() > 0:
                        int_diel_input.fill(str(config.internal_dielectric))
                        logger.debug(f"Set internal dielectric = {config.internal_dielectric}")

                    # External dielectric
                    ext_diel_input = page.locator('input[name="extdiel"]').first
                    if ext_diel_input.count() > 0:
                        ext_diel_input.fill(str(config.external_dielectric))
                        logger.debug(f"Set external dielectric = {config.external_dielectric}")
                except Exception as e:
                    raise RuntimeError(f"Failed to set parameters: {e}")

                # Step 4: Submit job
                logger.info("Submitting job")
                try:
                    submit_button = page.locator('input[type="submit"]').first
                    if submit_button.count() == 0:
                        raise RuntimeError("Could not find submit button on H++ page")
                    submit_button.click()
                    logger.debug("Job submitted")
                except Exception as e:
                    raise RuntimeError(f"Failed to submit job: {e}")

                # Step 5: Wait for job completion
                logger.info(f"Waiting for job completion (timeout: {timeout}s)")
                start_time = time.time()
                poll_interval = 5
                last_status = None

                while time.time() - start_time < timeout:
                    elapsed = int(time.time() - start_time)

                    # Check for various completion/error indicators
                    # Try multiple selectors for robustness
                    download_selectors = [
                        'text="Download Results"',
                        'a[href*=".pdb"]',
                        'text="Results"',
                        '.download-link'
                    ]

                    results_ready = False
                    for selector in download_selectors:
                        if page.locator(selector).count() > 0:
                            logger.info(f"Job completed after {elapsed}s")
                            results_ready = True
                            break

                    if results_ready:
                        break

                    # Check for errors with multiple selectors
                    error_selectors = [
                        'text="Error"',
                        '.error',
                        'text="Failed"',
                        'text="Invalid"'
                    ]

                    for selector in error_selectors:
                        if page.locator(selector).count() > 0:
                            try:
                                error_msg = page.locator(selector).first.text_content()
                            except:
                                error_msg = "Unknown error"
                            raise RuntimeError(f"H++ server error: {error_msg}")

                    # Log progress periodically
                    if elapsed % 30 == 0 and elapsed != last_status:
                        logger.info(f"Still waiting... ({elapsed}/{timeout}s)")
                        last_status = elapsed

                    time.sleep(poll_interval)
                else:
                    raise TimeoutError(
                        f"Job did not complete within {timeout} seconds. "
                        "The H++ server may be overloaded or the structure may be too large."
                    )

                # Step 6: Download results
                logger.info("Downloading results")
                output_pdb = output_dir / f"{pdb_file.stem}_hplusplus.pdb"

                try:
                    # Try to download PDB file
                    pdb_link = page.locator('a[href*=".pdb"]').first
                    if pdb_link.count() == 0:
                        raise RuntimeError("Could not find PDB download link")

                    with page.expect_download(timeout=30000) as download_info:
                        pdb_link.click()
                    download = download_info.value
                    download.save_as(output_pdb)

                    # Validate downloaded file
                    if not output_pdb.exists():
                        raise RuntimeError(f"Downloaded file does not exist: {output_pdb}")
                    if output_pdb.stat().st_size == 0:
                        raise RuntimeError(f"Downloaded file is empty: {output_pdb}")

                    # Basic PDB format validation
                    with output_pdb.open() as f:
                        first_line = f.readline()
                        if not first_line.strip():
                            raise RuntimeError(f"Downloaded PDB file appears to be invalid (empty first line)")

                    logger.info(f"Results saved to {output_pdb} ({output_pdb.stat().st_size} bytes)")

                except Exception as e:
                    raise RuntimeError(f"Failed to download results: {e}")

                return HPlusPlusResult(
                    success=True,
                    output_pdb=output_pdb
                )

            except Exception as e:
                # Log page content for debugging
                try:
                    page_content = page.content()
                    logger.debug(f"Page content at error: {page_content[:500]}...")
                except:
                    pass
                raise

            finally:
                browser.close()


# ------------------------------------------------------------------ #
# Convenience functions
# ------------------------------------------------------------------ #

def protonate_with_hplusplus(
    pdb_file: Path | str,
    ph: float = 7.0,
    salinity: float = 0.15,
    output_dir: Path | str | None = None,
    timeout: int = 300
) -> HPlusPlusResult:
    """Protonate protein structure using H++ server.

    Args:
        pdb_file: Path to input PDB file
        ph: Target pH (default: 7.0)
        salinity: Salt concentration in M (default: 0.15)
        output_dir: Output directory (default: same as input)
        timeout: Maximum wait time in seconds (default: 300)

    Returns:
        HPlusPlusResult with protonated structure

    Example:
        result = protonate_with_hplusplus("protein.pdb", ph=7.0)
        if result.success:
            print(f"Protonated structure: {result.output_pdb}")
        else:
            print(f"Failed: {result.error}")

    Note:
        Requires playwright: pip install playwright && playwright install chromium
    """
    config = HPlusPlusConfig(ph=ph, salinity=salinity)
    wrapper = HPlusPlusWrapper()
    return wrapper.run(pdb_file, config=config, output_dir=output_dir, timeout=timeout)


def is_hplusplus_available() -> bool:
    """Check if H++ automation is available.

    Returns:
        True if playwright is installed, False otherwise
    """
    wrapper = HPlusPlusWrapper()
    return wrapper.is_available()

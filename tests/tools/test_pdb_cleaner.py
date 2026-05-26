"""Tests for professional PDB cleaner tool."""

import tempfile
from pathlib import Path

import pytest

from mdpilot.tools.builtin.amber.pdb_cleaner import (
    clean_pdb_professional,
    validate_and_fix_pdb,
)


@pytest.fixture
def sample_pdb_with_headers():
    """Create a sample PDB file with various header lines."""
    content = """CRYST1   59.062   68.451   30.517  90.00  90.00  90.00 P 21 21 21
REMARK 290   SMTRY1   1  1.000000  0.000000  0.000000        0.00000
REMARK 290   SMTRY2   1  0.000000  1.000000  0.000000        0.00000
ATOM      1  N   LYS A   1      35.365  22.342 -11.980  1.00 22.28           N
ATOM      2  CA  LYS A   1      35.892  21.073 -11.427  1.00 21.12           C
HETATM 1001  O   HOH A 201      12.580  21.214   5.006  0.51 17.97           O
CONECT    1    2
CONECT    2    1
END
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".pdb", delete=False) as f:
        f.write(content)
        return Path(f.name)


@pytest.fixture
def sample_clean_pdb():
    """Create a sample PDB file that's already clean."""
    content = """ATOM      1  N   LYS A   1      35.365  22.342 -11.980  1.00 22.28           N
ATOM      2  CA  LYS A   1      35.892  21.073 -11.427  1.00 21.12           C
HETATM 1001  O   HOH A 201      12.580  21.214   5.006  0.51 17.97           O
END
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".pdb", delete=False) as f:
        f.write(content)
        return Path(f.name)


def test_validate_and_fix_pdb_with_headers(sample_pdb_with_headers):
    """Test validation and fixing of PDB with header lines."""
    result = validate_and_fix_pdb(sample_pdb_with_headers)

    assert result["fixed"] is True
    assert result["removed_conect"] == 2
    assert result["removed_remark"] == 2
    assert result["removed_cryst1"] == 1
    assert result["total_removed"] == 5

    # Verify file was actually cleaned
    content = sample_pdb_with_headers.read_text()
    assert "CONECT" not in content
    assert "REMARK" not in content
    assert "CRYST1" not in content
    assert "ATOM" in content
    assert "HETATM" in content
    assert "END" in content

    # Cleanup
    sample_pdb_with_headers.unlink()


def test_validate_and_fix_pdb_already_clean(sample_clean_pdb):
    """Test validation of already clean PDB."""
    result = validate_and_fix_pdb(sample_clean_pdb)

    assert result["fixed"] is False
    assert result["total_removed"] == 0

    # Cleanup
    sample_clean_pdb.unlink()


def test_clean_pdb_professional_missing_input():
    """Test error handling for missing input file."""
    result = clean_pdb_professional(
        input_pdb="nonexistent.pdb",
        workdir="/tmp"
    )

    assert "Error" in result
    assert "not found" in result


@pytest.mark.integration
def test_clean_pdb_professional_integration(sample_pdb_with_headers):
    """Integration test with real pdb4amber (if available)."""
    import shutil
    if not shutil.which("pdb4amber"):
        pytest.skip("pdb4amber not available")

    output_path = sample_pdb_with_headers.parent / "cleaned_output.pdb"

    result = clean_pdb_professional(
        input_pdb=str(sample_pdb_with_headers),
        output="cleaned_output.pdb",
        workdir=str(sample_pdb_with_headers.parent)
    )

    # Should succeed or report pdb4amber issues
    assert "Error" not in result or "pdb4amber" in result

    # Cleanup
    sample_pdb_with_headers.unlink()
    if output_path.exists():
        output_path.unlink()

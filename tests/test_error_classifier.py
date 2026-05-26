"""Tests for AMBER error classifier."""

from __future__ import annotations

import pytest

from mdpilot.tools.error_classifier import (
    ClassifiedError,
    classify_amber_error,
    format_classified_error,
)


class TestClassifyMissingFiles:
    def test_missing_leaprc(self):
        result = classify_amber_error("could not open leaprc.protein.ff19SB")
        assert result is not None
        assert result.code == "MISSING_FF"
        assert result.category == "amber_config"

    def test_missing_dat_file(self):
        result = classify_amber_error("could not open parm10.dat")
        assert result is not None
        assert result.code == "MISSING_PARAM"

    def test_file_not_found(self):
        result = classify_amber_error("file does not exist: /path/to/system.prmtop")
        assert result is not None
        assert result.category == "missing_file"


class TestClassifyPDBErrors:
    def test_unknown_residue(self):
        result = classify_amber_error("FATAL: Unknown residue LIG")
        assert result is not None
        assert result.category == "pdb_format"

    def test_duplicate_atoms(self):
        result = classify_amber_error("Duplicate atom name: CA in residue ALA")
        assert result is not None
        assert result.code == "PDB_DUPLICATE"


class TestClassifyMemoryErrors:
    def test_oom(self):
        result = classify_amber_error("out of memory allocating array")
        assert result is not None
        assert result.category == "memory"

    def test_segfault(self):
        result = classify_amber_error("Segmentation fault (core dumped)")
        assert result is not None
        assert result.code == "SEGFAULT"


class TestClassifyGPU:
    def test_cuda_error(self):
        result = classify_amber_error("CUDA error: an illegal memory access was encountered")
        assert result is not None
        assert result.category == "gpu"


class TestClassifyNumerical:
    def test_nan_energy(self):
        result = classify_amber_error("NAN on Etot at step 500")
        assert result is not None
        assert result.category == "numerical"

    def test_vlimit(self):
        result = classify_amber_error("vlimit exceeded for step 1234")
        assert result is not None
        assert result.code == "VLIMIT"

    def test_shake_failure(self):
        result = classify_amber_error("SHAKE error: coordinate reset failed")
        assert result is not None
        assert result.code == "SHAKE_FAIL"


class TestClassifyTimeout:
    def test_timeout(self):
        result = classify_amber_error("sander/pmemd timed out after 3600s")
        assert result is not None
        assert result.category == "timeout"


class TestNoMatch:
    def test_empty_string(self):
        assert classify_amber_error("") is None

    def test_unrecognized_error(self):
        assert classify_amber_error("Something weird happened") is None


class TestFormatHelper:
    def test_returns_tuple(self):
        code, cat, sug = format_classified_error("FATAL: Atom list mismatch")
        assert code is not None
        assert cat is not None
        assert sug is not None

    def test_no_match_returns_nones(self):
        code, cat, sug = format_classified_error("all good")
        assert code is None

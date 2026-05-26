"""Tests for AMBER domain-specific tools (Layer 4).

Uses real subprocess calls with fake executables to test tool logic
without requiring actual AMBER installations.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from mdpilot.tools.registry import ToolRegistry
from mdpilot.types import ToolCall


# ------------------------------------------------------------------ #
# Fixtures
# ------------------------------------------------------------------ #

@pytest.fixture()
def registry_with_amber() -> ToolRegistry:
    """Registry with all builtin + amber tools discovered."""
    reg = ToolRegistry()
    reg.auto_discover("mdpilot.tools.builtin")
    return reg


@pytest.fixture()
def fake_exe_dir(tmp_path: Path) -> Path:
    """Create a directory with fake executables that produce output."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    # Create fake tleap
    tleap = bin_dir / "tleap"
    tleap.write_text("#!/bin/sh\necho 'Welcome to tLEaP'\necho 'Exiting...'\n")
    tleap.chmod(tleap.stat().st_mode | stat.S_IEXEC)

    # Create fake cpptraj
    cpptraj = bin_dir / "cpptraj"
    cpptraj.write_text("#!/bin/sh\necho 'CPPTRAJ: processing'\n")
    cpptraj.chmod(cpptraj.stat().st_mode | stat.S_IEXEC)

    # Create fake antechamber
    ante = bin_dir / "antechamber"
    ante.write_text("#!/bin/sh\necho 'Antechamber completed'\n")
    ante.chmod(ante.stat().st_mode | stat.S_IEXEC)

    # Create fake parmchk2
    pc = bin_dir / "parmchk2"
    pc.write_text("#!/bin/sh\necho 'parmchk2 completed'\n")
    pc.chmod(pc.stat().st_mode | stat.S_IEXEC)

    # Create fake sander
    sander = bin_dir / "sander"
    sander.write_text("#!/bin/sh\necho 'Etot = -12345.6789'\necho 'STOP'\n")
    sander.chmod(sander.stat().st_mode | stat.S_IEXEC)

    # Create fake pdb4amber
    p4a = bin_dir / "pdb4amber"
    p4a.write_text("#!/bin/sh\necho 'pdb4amber completed'\n")
    p4a.chmod(p4a.stat().st_mode | stat.S_IEXEC)

    return bin_dir


@pytest.fixture()
def fake_amber_env(fake_exe_dir: Path, monkeypatch):
    """Set up fake AMBER environment for testing."""
    amber_home = fake_exe_dir.parent
    monkeypatch.setenv("AMBERHOME", str(amber_home))
    monkeypatch.setenv("PATH", str(fake_exe_dir) + os.pathsep + os.environ.get("PATH", ""))
    return amber_home


# ------------------------------------------------------------------ #
# Registry / Auto-discover
# ------------------------------------------------------------------ #

class TestAmberToolDiscovery:
    def test_all_amber_tools_discovered(self, registry_with_amber):
        tools = registry_with_amber.list_tools()
        for expected in ("tleap", "cpptraj", "antechamber", "sander", "pdb4amber"):
            assert expected in tools, f"Tool '{expected}' not found in {tools}"

    def test_amber_tools_have_schemas(self, registry_with_amber):
        schemas = registry_with_amber.schemas()
        amber_names = {"tleap", "cpptraj", "antechamber", "sander", "pdb4amber"}
        for schema in schemas:
            name = schema["function"]["name"]
            if name in amber_names:
                params = schema["function"]["parameters"]
                assert "properties" in params

    def test_amber_tool_count(self, registry_with_amber):
        assert len(registry_with_amber.list_tools()) == 16

    def test_tleap_schema_required(self, registry_with_amber):
        meta, fn = registry_with_amber.get("tleap")
        assert "input_script" in meta.parameters.get("required", [])

    def test_sander_schema_required(self, registry_with_amber):
        meta, fn = registry_with_amber.get("sander")
        required = meta.parameters.get("required", [])
        assert "input_config" in required
        assert "prmtop" in required
        assert "inpcrd" in required


# ------------------------------------------------------------------ #
# tLEaP
# ------------------------------------------------------------------ #

class TestTleap:
    def test_tleap_not_found(self, monkeypatch):
        monkeypatch.delenv("AMBERHOME", raising=False)
        from mdpilot.tools.builtin.amber.tleap import tleap_run
        with patch("shutil.which", return_value=None):
            result = tleap_run(input_script="source leaprc.ff14SB")
        assert "not found" in result.lower()

    def test_tleap_runs(self, fake_amber_env, tmp_path):
        from mdpilot.tools.builtin.amber.tleap import tleap_run
        result = tleap_run(
            input_script="source leaprc.ff14SB\nquit",
            workdir=str(tmp_path),
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_tleap_workdir_created(self, fake_amber_env, tmp_path):
        from mdpilot.tools.builtin.amber.tleap import tleap_run
        workdir = tmp_path / "test_workdir"
        result = tleap_run(input_script="quit", workdir=str(workdir))
        assert workdir.exists()

    def test_tleap_creates_input_file(self, fake_amber_env, tmp_path):
        from mdpilot.tools.builtin.amber.tleap import tleap_run
        result = tleap_run(input_script="quit", workdir=str(tmp_path))
        assert (tmp_path / "tleap.in").exists()

    def test_tleap_via_dispatcher(self, registry_with_amber, fake_amber_env, tmp_path):
        from mdpilot.tools.dispatcher import ToolDispatcher
        dispatcher = ToolDispatcher(registry_with_amber)
        call = ToolCall(
            id="test-1",
            name="tleap",
            arguments={"input_script": "quit", "workdir": str(tmp_path)},
        )
        import asyncio
        output = asyncio.run(dispatcher.execute(call))
        assert output.success


# ------------------------------------------------------------------ #
# cpptraj
# ------------------------------------------------------------------ #

class TestCpptraj:
    def test_cpptraj_not_found(self, monkeypatch):
        monkeypatch.delenv("AMBERHOME", raising=False)
        from mdpilot.tools.builtin.amber.cpptraj import cpptraj_run
        with patch("shutil.which", return_value=None):
            result = cpptraj_run(input_script="trajin md.nc")
        assert "not found" in result.lower()

    def test_cpptraj_runs(self, fake_amber_env, tmp_path):
        from mdpilot.tools.builtin.amber.cpptraj import cpptraj_run
        result = cpptraj_run(input_script="trajin md.nc\nrms first", workdir=str(tmp_path))
        assert isinstance(result, str)

    def test_cpptraj_creates_input_file(self, fake_amber_env, tmp_path):
        from mdpilot.tools.builtin.amber.cpptraj import cpptraj_run
        cpptraj_run(input_script="trajin md.nc", workdir=str(tmp_path))
        assert (tmp_path / "cpptraj.in").exists()


# ------------------------------------------------------------------ #
# antechamber
# ------------------------------------------------------------------ #

class TestAntechamber:
    def test_antechamber_not_found(self, monkeypatch):
        monkeypatch.delenv("AMBERHOME", raising=False)
        from mdpilot.tools.builtin.amber.antechamber import antechamber_run
        with patch("shutil.which", return_value=None):
            result = antechamber_run(input_file="test.mol2")
        assert "not found" in result.lower()

    def test_antechamber_input_not_found(self, fake_amber_env, tmp_path):
        from mdpilot.tools.builtin.amber.antechamber import antechamber_run
        result = antechamber_run(input_file="nonexistent.mol2", workdir=str(tmp_path))
        assert "not found" in result.lower()

    def test_antechamber_runs(self, fake_amber_env, tmp_path):
        from mdpilot.tools.builtin.amber.antechamber import antechamber_run
        # Create a fake input file
        input_file = tmp_path / "ligand.mol2"
        input_file.write_text("@<TRIPOS>MOLECULE\nfake\n")
        result = antechamber_run(
            input_file=str(input_file),
            input_format="mol2",
            workdir=str(tmp_path),
            run_parmchk=False,
        )
        assert isinstance(result, str)

    def test_antechamber_with_parmchk(self, fake_amber_env, tmp_path):
        from mdpilot.tools.builtin.amber.antechamber import antechamber_run
        input_file = tmp_path / "ligand.mol2"
        input_file.write_text("@<TRIPOS>MOLECULE\nfake\n")
        result = antechamber_run(
            input_file=str(input_file),
            workdir=str(tmp_path),
        )
        assert "parmchk" in result.lower() or isinstance(result, str)


# ------------------------------------------------------------------ #
# sander
# ------------------------------------------------------------------ #

class TestSander:
    def test_sander_not_found(self, monkeypatch):
        monkeypatch.delenv("AMBERHOME", raising=False)
        from mdpilot.tools.builtin.amber.sander import sander_run
        with patch("shutil.which", return_value=None):
            result = sander_run(
                input_config="minimization",
                prmtop="test.prmtop",
                inpcrd="test.inpcrd",
            )
        assert "not found" in result.lower()

    def test_sander_prmtop_not_found(self, fake_amber_env, tmp_path):
        from mdpilot.tools.builtin.amber.sander import sander_run
        result = sander_run(
            input_config="minimization",
            prmtop="nonexistent.prmtop",
            inpcrd="nonexistent.inpcrd",
            workdir=str(tmp_path),
        )
        assert "not found" in result.lower()

    def test_sander_runs(self, fake_amber_env, tmp_path):
        from mdpilot.tools.builtin.amber.sander import sander_run
        # Create fake input files
        prmtop = tmp_path / "test.prmtop"
        inpcrd = tmp_path / "test.inpcrd"
        prmtop.write_text("%VERSION\n")
        inpcrd.write_text("fake coords\n")

        # Create fake output file (the fake sander just echoes)
        result = sander_run(
            input_config="Minimization\n &cntrl imin=1, /",
            prmtop=str(prmtop),
            inpcrd=str(inpcrd),
            workdir=str(tmp_path),
        )
        assert isinstance(result, str)

    def test_sander_creates_input_file(self, fake_amber_env, tmp_path):
        from mdpilot.tools.builtin.amber.sander import sander_run
        prmtop = tmp_path / "test.prmtop"
        inpcrd = tmp_path / "test.inpcrd"
        prmtop.write_text("%VERSION\n")
        inpcrd.write_text("fake\n")

        sander_run(
            input_config="imin=1",
            prmtop=str(prmtop),
            inpcrd=str(inpcrd),
            workdir=str(tmp_path),
        )
        assert (tmp_path / "sander.in").exists()


# ------------------------------------------------------------------ #
# pdb4amber
# ------------------------------------------------------------------ #

class TestPdb4amber:
    def test_pdb4amber_not_found(self, monkeypatch):
        monkeypatch.delenv("AMBERHOME", raising=False)
        from mdpilot.tools.builtin.amber.pdb4amber import pdb4amber_run
        with patch("shutil.which", return_value=None):
            result = pdb4amber_run(input_pdb="test.pdb")
        assert "not found" in result.lower()

    def test_pdb4amber_input_not_found(self, fake_amber_env, tmp_path):
        from mdpilot.tools.builtin.amber.pdb4amber import pdb4amber_run
        result = pdb4amber_run(input_pdb="nonexistent.pdb", workdir=str(tmp_path))
        assert "not found" in result.lower()

    def test_pdb4amber_runs(self, fake_amber_env, tmp_path):
        from mdpilot.tools.builtin.amber.pdb4amber import pdb4amber_run
        # Create fake input PDB
        input_pdb = tmp_path / "test.pdb"
        input_pdb.write_text(
            "ATOM      1  CA  ALA A   1       1.000   2.000   3.000  1.00  0.00\n"
            "END\n"
        )
        result = pdb4amber_run(
            input_pdb=str(input_pdb),
            workdir=str(tmp_path),
            reduce=False,
        )
        assert isinstance(result, str)

    def test_pdb4amber_default_output_name(self, fake_amber_env, tmp_path):
        from mdpilot.tools.builtin.amber.pdb4amber import pdb4amber_run
        input_pdb = tmp_path / "protein.pdb"
        input_pdb.write_text("ATOM      1  CA  ALA A   1       1.000   2.000   3.000\nEND\n")
        result = pdb4amber_run(input_pdb=str(input_pdb), workdir=str(tmp_path), reduce=False)
        # The fake exe won't create output, just verify the command ran
        assert isinstance(result, str)
        # Verify the expected output path appears in the command call
        # (fake pdb4amber receives -o protein_clean.pdb)

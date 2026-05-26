"""Tests for workflow validator."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from mdpilot.workflows.validator import ValidationCheck, ValidationReport


class TestValidationCheck:
    """Test ValidationCheck dataclass."""
    
    def test_init_pass(self):
        check = ValidationCheck(
            name="test_check",
            passed=True,
            value="10",
            expected="10"
        )
        assert check.name == "test_check"
        assert check.passed is True
        assert check.value == "10"
        assert check.expected == "10"
        assert check.message == ""
    
    def test_init_fail_with_message(self):
        check = ValidationCheck(
            name="test_check",
            passed=False,
            value="5",
            expected="10",
            message="Value too low"
        )
        assert check.passed is False
        assert check.message == "Value too low"
    
    def test_str_pass(self):
        check = ValidationCheck(
            name="charge_neutral",
            passed=True,
            value="0.0",
            expected="0.0"
        )
        result = str(check)
        assert "✅ PASS" in result
        assert "charge_neutral" in result
        assert "0.0" in result
    
    def test_str_fail(self):
        check = ValidationCheck(
            name="charge_neutral",
            passed=False,
            value="2.0",
            expected="0.0",
            message="Not neutral"
        )
        result = str(check)
        assert "❌ FAIL" in result
        assert "charge_neutral" in result
        assert "expected: 0.0" in result
        assert "Not neutral" in result


class TestValidationReport:
    """Test ValidationReport dataclass."""
    
    def test_init(self):
        checks = [
            ValidationCheck("check1", True, "1", "1"),
            ValidationCheck("check2", False, "2", "3")
        ]
        report = ValidationReport(
            system_type="standard_protein",
            passed=False,
            checks=checks,
            prmtop_path="test.prmtop",
            inpcrd_path="test.inpcrd"
        )
        
        assert report.system_type == "standard_protein"
        assert report.passed is False
        assert len(report.checks) == 2
    
    def test_num_passed(self):
        checks = [
            ValidationCheck("check1", True, "1", "1"),
            ValidationCheck("check2", True, "2", "2"),
            ValidationCheck("check3", False, "3", "4")
        ]
        report = ValidationReport("test", False, checks, "a.prmtop", "a.inpcrd")
        
        assert report.num_passed == 2
    
    def test_num_failed(self):
        checks = [
            ValidationCheck("check1", True, "1", "1"),
            ValidationCheck("check2", False, "2", "3"),
            ValidationCheck("check3", False, "3", "4")
        ]
        report = ValidationReport("test", False, checks, "a.prmtop", "a.inpcrd")
        
        assert report.num_failed == 2
    
    def test_num_total(self):
        checks = [
            ValidationCheck("check1", True, "1", "1"),
            ValidationCheck("check2", False, "2", "3")
        ]
        report = ValidationReport("test", False, checks, "a.prmtop", "a.inpcrd")
        
        assert report.num_total == 2
    
    def test_str_passed(self):
        checks = [
            ValidationCheck("check1", True, "1", "1"),
            ValidationCheck("check2", True, "2", "2")
        ]
        report = ValidationReport("test", True, checks, "a.prmtop", "a.inpcrd")
        
        result = str(report)
        assert "✅ PASSED" in result
        assert "2/2 passed" in result
        assert "a.prmtop" in result
    
    def test_str_failed(self):
        checks = [
            ValidationCheck("check1", True, "1", "1"),
            ValidationCheck("check2", False, "2", "3")
        ]
        report = ValidationReport("test", False, checks, "a.prmtop", "a.inpcrd")
        
        result = str(report)
        assert "❌ FAILED" in result
        assert "1/2 passed, 1 failed" in result


class TestSystemValidator:
    """Test SystemValidator base class."""
    
    def test_init(self):
        from mdpilot.workflows.validator import SystemValidator
        validator = SystemValidator()
        assert validator.checks == []
    
    def test_validate_not_implemented(self):
        from mdpilot.workflows.validator import SystemValidator
        validator = SystemValidator()
        
        with pytest.raises(NotImplementedError):
            validator.validate("test.prmtop", "test.inpcrd")
    
    def test_check_charge_neutral_pass(self):
        from mdpilot.workflows.validator import SystemValidator
        
        # Mock structure with neutral charge
        mock_structure = Mock()
        mock_atom1 = Mock()
        mock_atom1.charge = 0.5
        mock_atom2 = Mock()
        mock_atom2.charge = -0.5
        mock_structure.atoms = [mock_atom1, mock_atom2]
        
        validator = SystemValidator()
        check = validator._check_charge_neutral(mock_structure)
        
        assert check.passed is True
        assert check.name == "charge_neutral"
    
    def test_check_charge_neutral_fail(self):
        from mdpilot.workflows.validator import SystemValidator
        
        # Mock structure with non-neutral charge
        mock_structure = Mock()
        mock_atom1 = Mock()
        mock_atom1.charge = 1.0
        mock_atom2 = Mock()
        mock_atom2.charge = 1.0
        mock_structure.atoms = [mock_atom1, mock_atom2]
        
        validator = SystemValidator()
        check = validator._check_charge_neutral(mock_structure)
        
        assert check.passed is False
        assert "neutral" in check.message.lower()
    
    def test_check_ep_atoms_opc3(self):
        from mdpilot.workflows.validator import SystemValidator
        
        # Mock structure with no EP atoms (OPC3)
        mock_structure = Mock()
        mock_atom1 = Mock()
        mock_atom1.atomic_number = 1  # Hydrogen
        mock_atom2 = Mock()
        mock_atom2.atomic_number = 8  # Oxygen
        mock_structure.atoms = [mock_atom1, mock_atom2]
        
        validator = SystemValidator()
        check = validator._check_ep_atoms(mock_structure, water_model="OPC3")
        
        assert check.passed is True
        assert check.value == "0"
    
    def test_check_ep_atoms_opc(self):
        from mdpilot.workflows.validator import SystemValidator
        
        # Mock structure with EP atoms (OPC)
        mock_structure = Mock()
        mock_atom1 = Mock()
        mock_atom1.atomic_number = 0  # EP atom
        mock_atom2 = Mock()
        mock_atom2.atomic_number = 8  # Oxygen
        mock_structure.atoms = [mock_atom1, mock_atom2]
        
        validator = SystemValidator()
        check = validator._check_ep_atoms(mock_structure, water_model="OPC")
        
        assert check.passed is True
        assert check.value == "1"
    
    def test_check_ep_atoms_tip3p_no_ep(self):
        from mdpilot.workflows.validator import SystemValidator
        
        mock_structure = Mock()
        mock_atom1 = Mock()
        mock_atom1.atomic_number = 1
        mock_structure.atoms = [mock_atom1]
        
        validator = SystemValidator()
        check = validator._check_ep_atoms(mock_structure, water_model="TIP3P")
        
        assert check.passed is True
        assert check.expected == "0"
    
    def test_check_ep_atoms_tip4p_with_ep(self):
        from mdpilot.workflows.validator import SystemValidator
        
        mock_structure = Mock()
        mock_atom1 = Mock()
        mock_atom1.atomic_number = 0  # EP
        mock_structure.atoms = [mock_atom1]
        
        validator = SystemValidator()
        check = validator._check_ep_atoms(mock_structure, water_model="TIP4P")
        
        assert check.passed is True
        assert check.expected == "> 0"
    
    def test_check_ep_atoms_tip4pew_with_ep(self):
        from mdpilot.workflows.validator import SystemValidator
        
        mock_structure = Mock()
        mock_atom1 = Mock()
        mock_atom1.atomic_number = 0
        mock_structure.atoms = [mock_atom1]
        
        validator = SystemValidator()
        check = validator._check_ep_atoms(mock_structure, water_model="TIP4PEW")
        
        assert check.passed is True
    
    def test_check_ep_atoms_unknown_model(self):
        from mdpilot.workflows.validator import SystemValidator
        
        mock_structure = Mock()
        mock_structure.atoms = []
        
        validator = SystemValidator()
        check = validator._check_ep_atoms(mock_structure, water_model="UNKNOWN")
        
        assert check.passed is True
        assert check.expected == "unknown"
    
    def test_check_ep_atoms_opc3_fail(self):
        from mdpilot.workflows.validator import SystemValidator
        
        mock_structure = Mock()
        mock_atom1 = Mock()
        mock_atom1.atomic_number = 0  # EP atom (should not exist for OPC3)
        mock_structure.atoms = [mock_atom1]
        
        validator = SystemValidator()
        check = validator._check_ep_atoms(mock_structure, water_model="OPC3")
        
        assert check.passed is False
        assert "OPC3" in check.message
    
    def test_check_ep_atoms_opc_fail(self):
        from mdpilot.workflows.validator import SystemValidator
        
        mock_structure = Mock()
        mock_atom1 = Mock()
        mock_atom1.atomic_number = 1  # No EP atoms (should exist for OPC)
        mock_structure.atoms = [mock_atom1]
        
        validator = SystemValidator()
        check = validator._check_ep_atoms(mock_structure, water_model="OPC")
        
        assert check.passed is False
        assert "OPC" in check.message
    
    def test_check_box_angles_no_box(self):
        from mdpilot.workflows.validator import SystemValidator
        
        mock_structure = Mock()
        mock_structure.box = None
        
        validator = SystemValidator()
        check = validator._check_box_angles(mock_structure)
        
        assert check.passed is False
        assert check.value == "None"
        assert "No box information" in check.message
    
    def test_check_box_angles_octahedron_pass(self):
        from mdpilot.workflows.validator import SystemValidator
        
        mock_structure = Mock()
        mock_structure.box = [50.0, 50.0, 50.0, 109.47, 109.47, 109.47]
        
        validator = SystemValidator()
        check = validator._check_box_angles(mock_structure, expected_type="octahedron")
        
        assert check.passed is True
        assert "109.47" in check.value
    
    def test_check_box_angles_octahedron_fail(self):
        from mdpilot.workflows.validator import SystemValidator
        
        mock_structure = Mock()
        mock_structure.box = [50.0, 50.0, 50.0, 90.0, 90.0, 90.0]
        
        validator = SystemValidator()
        check = validator._check_box_angles(mock_structure, expected_type="octahedron")
        
        assert check.passed is False
        assert "octahedron" in check.message
    
    def test_check_box_angles_cubic_pass(self):
        from mdpilot.workflows.validator import SystemValidator
        
        mock_structure = Mock()
        mock_structure.box = [50.0, 50.0, 50.0, 90.0, 90.0, 90.0]
        
        validator = SystemValidator()
        check = validator._check_box_angles(mock_structure, expected_type="cubic")
        
        assert check.passed is True
        assert "90.0" in check.value
    
    def test_check_box_angles_cubic_fail(self):
        from mdpilot.workflows.validator import SystemValidator
        
        mock_structure = Mock()
        mock_structure.box = [50.0, 50.0, 50.0, 109.47, 109.47, 109.47]
        
        validator = SystemValidator()
        check = validator._check_box_angles(mock_structure, expected_type="cubic")
        
        assert check.passed is False
        assert "cubic" in check.message
    
    def test_check_box_angles_unknown_type(self):
        from mdpilot.workflows.validator import SystemValidator
        
        mock_structure = Mock()
        mock_structure.box = [50.0, 50.0, 50.0, 100.0, 100.0, 100.0]
        
        validator = SystemValidator()
        check = validator._check_box_angles(mock_structure, expected_type="unknown")
        
        assert check.passed is True
        assert check.expected == "unknown"
    
    def test_check_his_assignment_pass(self):
        from mdpilot.workflows.validator import SystemValidator
        
        mock_structure = Mock()
        mock_res1 = Mock()
        mock_res1.name = "HIE"
        mock_res2 = Mock()
        mock_res2.name = "HID"
        mock_structure.residues = [mock_res1, mock_res2]
        
        validator = SystemValidator()
        check = validator._check_his_assignment(mock_structure)
        
        assert check.passed is True
        assert check.value == "0"
    
    def test_check_his_assignment_fail(self):
        from mdpilot.workflows.validator import SystemValidator
        
        mock_structure = Mock()
        mock_res1 = Mock()
        mock_res1.name = "HIS"
        mock_res2 = Mock()
        mock_res2.name = "HIS"
        mock_structure.residues = [mock_res1, mock_res2]
        
        validator = SystemValidator()
        check = validator._check_his_assignment(mock_structure)
        
        assert check.passed is False
        assert check.value == "2"
        assert "HIE/HID/HIP" in check.message
    
    def test_check_atom_count_pass(self):
        from mdpilot.workflows.validator import SystemValidator
        
        mock_structure = Mock()
        mock_structure.atoms = [Mock() for _ in range(150)]
        
        validator = SystemValidator()
        check = validator._check_atom_count(mock_structure, min_atoms=100)
        
        assert check.passed is True
        assert check.value == "150"
    
    def test_check_atom_count_fail(self):
        from mdpilot.workflows.validator import SystemValidator
        
        mock_structure = Mock()
        mock_structure.atoms = [Mock() for _ in range(50)]
        
        validator = SystemValidator()
        check = validator._check_atom_count(mock_structure, min_atoms=100)
        
        assert check.passed is False
        assert check.value == "50"
        assert "too few atoms" in check.message
    
    def test_check_water_molecules_pass(self):
        from mdpilot.workflows.validator import SystemValidator
        
        mock_structure = Mock()
        mock_res1 = Mock()
        mock_res1.name = "WAT"
        mock_res2 = Mock()
        mock_res2.name = "HOH"
        mock_res3 = Mock()
        mock_res3.name = "ALA"
        mock_structure.residues = [mock_res1, mock_res2, mock_res3]
        
        validator = SystemValidator()
        check = validator._check_water_molecules(mock_structure)
        
        assert check.passed is True
        assert check.value == "2"
    
    def test_check_water_molecules_fail(self):
        from mdpilot.workflows.validator import SystemValidator
        
        mock_structure = Mock()
        mock_res1 = Mock()
        mock_res1.name = "ALA"
        mock_structure.residues = [mock_res1]
        
        validator = SystemValidator()
        check = validator._check_water_molecules(mock_structure)
        
        assert check.passed is False
        assert check.value == "0"
        assert "water molecules" in check.message
    
    def test_check_water_molecules_all_types(self):
        from mdpilot.workflows.validator import SystemValidator
        
        mock_structure = Mock()
        mock_res1 = Mock()
        mock_res1.name = "WAT"
        mock_res2 = Mock()
        mock_res2.name = "HOH"
        mock_res3 = Mock()
        mock_res3.name = "TIP3"
        mock_res4 = Mock()
        mock_res4.name = "OPC"
        mock_res5 = Mock()
        mock_res5.name = "OPC3"
        mock_structure.residues = [mock_res1, mock_res2, mock_res3, mock_res4, mock_res5]
        
        validator = SystemValidator()
        check = validator._check_water_molecules(mock_structure)
        
        assert check.passed is True
        assert check.value == "5"
    
    def test_run_cpptraj_check_success(self):
        from mdpilot.workflows.validator import SystemValidator
        
        validator = SystemValidator()
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")
            
            success, output = validator._run_cpptraj_check("test.prmtop", "test.inpcrd", "parm test.prmtop")
            
            assert success is True
            assert "Success" in output
            mock_run.assert_called_once()
    
    def test_run_cpptraj_check_failure(self):
        from mdpilot.workflows.validator import SystemValidator
        
        validator = SystemValidator()
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="Error")
            
            success, output = validator._run_cpptraj_check("test.prmtop", "test.inpcrd", "parm test.prmtop")
            
            assert success is False
            assert "Error" in output
    
    def test_run_cpptraj_check_exception(self):
        from mdpilot.workflows.validator import SystemValidator
        
        validator = SystemValidator()
        
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = Exception("Command failed")
            
            success, output = validator._run_cpptraj_check("test.prmtop", "test.inpcrd", "parm test.prmtop")
            
            assert success is False
            assert "Command failed" in output


class TestStandardProteinValidator:
    """Test StandardProteinValidator class."""
    
    def test_init(self):
        from mdpilot.workflows.validator import StandardProteinValidator
        
        validator = StandardProteinValidator()
        assert validator.checks == []
    
    def test_validate_missing_parmed(self):
        from mdpilot.workflows.validator import StandardProteinValidator
        
        validator = StandardProteinValidator()
        
        with patch.dict('sys.modules', {'parmed': None}):
            with pytest.raises(ImportError, match="parmed is required"):
                validator.validate("test.prmtop", "test.inpcrd")
    
    def test_validate_missing_prmtop(self, tmp_path):
        from mdpilot.workflows.validator import StandardProteinValidator
        
        validator = StandardProteinValidator()
        inpcrd = tmp_path / "test.inpcrd"
        inpcrd.touch()
        
        mock_parmed = Mock()
        with patch.dict('sys.modules', {'parmed': mock_parmed}):
            with pytest.raises(FileNotFoundError, match="Topology file not found"):
                validator.validate("nonexistent.prmtop", str(inpcrd))
    
    def test_validate_missing_inpcrd(self, tmp_path):
        from mdpilot.workflows.validator import StandardProteinValidator
        
        validator = StandardProteinValidator()
        prmtop = tmp_path / "test.prmtop"
        prmtop.touch()
        
        mock_parmed = Mock()
        with patch.dict('sys.modules', {'parmed': mock_parmed}):
            with pytest.raises(FileNotFoundError, match="Coordinate file not found"):
                validator.validate(str(prmtop), "nonexistent.inpcrd")
    
    def test_validate_success(self, tmp_path):
        from mdpilot.workflows.validator import StandardProteinValidator
        
        prmtop = tmp_path / "test.prmtop"
        inpcrd = tmp_path / "test.inpcrd"
        prmtop.touch()
        inpcrd.touch()
        
        validator = StandardProteinValidator()
        
        mock_structure = Mock()
        mock_atom1 = Mock()
        mock_atom1.charge = 0.5
        mock_atom1.atomic_number = 1
        mock_atom2 = Mock()
        mock_atom2.charge = -0.5
        mock_atom2.atomic_number = 8
        mock_structure.atoms = [mock_atom1, mock_atom2] * 500
        
        mock_res1 = Mock()
        mock_res1.name = "HIE"
        mock_res2 = Mock()
        mock_res2.name = "WAT"
        mock_structure.residues = [mock_res1, mock_res2]
        
        mock_structure.box = [50.0, 50.0, 50.0, 109.47, 109.47, 109.47]
        
        mock_parmed = Mock()
        mock_parmed.load_file = Mock(return_value=mock_structure)
        
        with patch.dict('sys.modules', {'parmed': mock_parmed}):
            report = validator.validate(str(prmtop), str(inpcrd))
            
            assert report.system_type == "standard_protein"
            assert report.prmtop_path == str(prmtop)
            assert report.inpcrd_path == str(inpcrd)
            assert len(report.checks) == 6
            assert report.passed is True
    
    def test_validate_with_failures(self, tmp_path):
        from mdpilot.workflows.validator import StandardProteinValidator
        
        prmtop = tmp_path / "test.prmtop"
        inpcrd = tmp_path / "test.inpcrd"
        prmtop.touch()
        inpcrd.touch()
        
        validator = StandardProteinValidator()
        
        mock_structure = Mock()
        mock_atom1 = Mock()
        mock_atom1.charge = 2.0
        mock_atom1.atomic_number = 1
        mock_structure.atoms = [mock_atom1] * 50
        
        mock_res1 = Mock()
        mock_res1.name = "HIS"
        mock_structure.residues = [mock_res1]
        
        mock_structure.box = [50.0, 50.0, 50.0, 90.0, 90.0, 90.0]
        
        mock_parmed = Mock()
        mock_parmed.load_file = Mock(return_value=mock_structure)
        
        with patch.dict('sys.modules', {'parmed': mock_parmed}):
            report = validator.validate(str(prmtop), str(inpcrd))
            
            assert report.passed is False
            assert report.num_failed > 0
    
    def test_validate_custom_water_model(self, tmp_path):
        from mdpilot.workflows.validator import StandardProteinValidator
        
        prmtop = tmp_path / "test.prmtop"
        inpcrd = tmp_path / "test.inpcrd"
        prmtop.touch()
        inpcrd.touch()
        
        validator = StandardProteinValidator()
        
        mock_structure = Mock()
        mock_atom1 = Mock()
        mock_atom1.charge = 0.0
        mock_atom1.atomic_number = 0
        mock_structure.atoms = [mock_atom1] * 1000
        
        mock_res1 = Mock()
        mock_res1.name = "OPC"
        mock_structure.residues = [mock_res1]
        
        mock_structure.box = [50.0, 50.0, 50.0, 109.47, 109.47, 109.47]
        
        mock_parmed = Mock()
        mock_parmed.load_file = Mock(return_value=mock_structure)
        
        with patch.dict('sys.modules', {'parmed': mock_parmed}):
            report = validator.validate(str(prmtop), str(inpcrd), water_model="OPC")
            
            ep_check = next(c for c in report.checks if c.name == "ep_atoms")
            assert ep_check.passed is True

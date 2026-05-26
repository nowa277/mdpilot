"""
Unit tests for workflows/protonation.py

Tests ProtonationEngine class and determine_protonation_states function
for intelligent protonation state assignment.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from mdpilot.workflows.protonation import (
    ProtonationEngine,
    ProtonationAssignment,
    ProtonationReport,
    determine_protonation_states
)


@pytest.fixture
def mock_pdb_info():
    """Create mock PDBInfo object."""
    info = Mock()
    info.residues = []
    info.chains = ["A"]
    info.metals = []
    return info


@pytest.fixture
def mock_propka_result():
    """Create mock PropkaResult object."""
    result = Mock()
    result.pka_values = {}
    return result


class TestProtonationAssignment:
    """Test ProtonationAssignment dataclass."""
    
    def test_assignment_creation(self):
        """Test creating ProtonationAssignment."""
        assignment = ProtonationAssignment(
            residue_name="HIS",
            residue_number=42,
            chain_id="A",
            assigned_name="HID",
            reason="pKa < pH",
            pka=5.5
        )
        
        assert assignment.residue_name == "HIS"
        assert assignment.residue_number == 42
        assert assignment.chain_id == "A"
        assert assignment.assigned_name == "HID"
        assert assignment.reason == "pKa < pH"
        assert assignment.pka == 5.5
    
    def test_assignment_without_pka(self):
        """Test creating assignment without pKa value."""
        assignment = ProtonationAssignment(
            residue_name="CYS",
            residue_number=10,
            chain_id="B",
            assigned_name="CYX",
            reason="Disulfide bond"
        )
        
        assert assignment.pka is None


class TestProtonationReport:
    """Test ProtonationReport dataclass."""
    
    def test_report_creation(self):
        """Test creating ProtonationReport."""
        assignments = [
            ProtonationAssignment("HIS", 1, "A", "HID", "test", 5.5)
        ]
        report = ProtonationReport(
            assignments=assignments,
            his_assignments={1: "HID"},
            asp_glu_assignments={},
            cys_assignments={}
        )
        
        assert len(report.assignments) == 1
        assert report.his_assignments[1] == "HID"
    
    def test_get_tleap_commands_his(self):
        """Test tleap command generation for HIS."""
        assignments = [
            ProtonationAssignment("HIS", 10, "A", "HID", "test")
        ]
        report = ProtonationReport(
            assignments=assignments,
            his_assignments={10: "HID"},
            asp_glu_assignments={},
            cys_assignments={}
        )
        
        commands = report.get_tleap_commands()
        assert len(commands) == 1
        assert 'set mol.10 name "HID"' in commands
    
    def test_get_tleap_commands_ash(self):
        """Test tleap command generation for protonated ASP."""
        assignments = [
            ProtonationAssignment("ASP", 5, "A", "ASH", "test")
        ]
        report = ProtonationReport(
            assignments=assignments,
            his_assignments={},
            asp_glu_assignments={5: "ASH"},
            cys_assignments={}
        )
        
        commands = report.get_tleap_commands()
        assert len(commands) == 1
        assert 'set mol.5 name "ASH"' in commands
    
    def test_get_tleap_commands_cyx(self):
        """Test tleap command generation for disulfide CYS."""
        assignments = [
            ProtonationAssignment("CYS", 20, "A", "CYX", "test")
        ]
        report = ProtonationReport(
            assignments=assignments,
            his_assignments={},
            asp_glu_assignments={},
            cys_assignments={20: "CYX"}
        )
        
        commands = report.get_tleap_commands()
        assert len(commands) == 1
        assert 'set mol.20 name "CYX"' in commands
    
    def test_get_tleap_commands_skip_standard(self):
        """Test that standard protonation states are not included."""
        assignments = [
            ProtonationAssignment("ASP", 5, "A", "ASP", "standard")
        ]
        report = ProtonationReport(
            assignments=assignments,
            his_assignments={},
            asp_glu_assignments={5: "ASP"},  # Standard, not ASH
            cys_assignments={}
        )
        
        commands = report.get_tleap_commands()
        assert len(commands) == 0  # ASP is standard, no command needed
    
    def test_summary_with_his(self):
        """Test summary generation with HIS assignments."""
        assignments = [
            ProtonationAssignment("HIS", 10, "A", "HID", "pKa < pH", 5.5)
        ]
        report = ProtonationReport(
            assignments=assignments,
            his_assignments={10: "HID"},
            asp_glu_assignments={},
            cys_assignments={}
        )
        
        summary = report.summary()
        assert "Histidine" in summary
        assert "HIS  10 → HID" in summary
        assert "pKa < pH" in summary
    
    def test_summary_with_multiple_types(self):
        """Test summary with multiple residue types."""
        assignments = [
            ProtonationAssignment("HIS", 10, "A", "HIP", "test1"),
            ProtonationAssignment("ASP", 5, "A", "ASH", "test2"),
            ProtonationAssignment("CYS", 20, "A", "CYX", "test3")
        ]
        report = ProtonationReport(
            assignments=assignments,
            his_assignments={10: "HIP"},
            asp_glu_assignments={5: "ASH"},
            cys_assignments={20: "CYX"}
        )
        
        summary = report.summary()
        assert "Histidine" in summary
        assert "Acidic residues" in summary
        assert "Cysteine" in summary


class TestProtonationEngineInit:
    """Test ProtonationEngine initialization."""
    
    def test_init_default_ph(self):
        """Test initialization with default pH."""
        engine = ProtonationEngine()
        assert engine.ph == 7.0
        assert engine.pka_threshold == 1.0
    
    def test_init_custom_ph(self):
        """Test initialization with custom pH."""
        engine = ProtonationEngine(ph=5.5)
        assert engine.ph == 5.5
    
    def test_init_custom_threshold(self):
        """Test initialization with custom pKa threshold."""
        engine = ProtonationEngine(pka_threshold=0.5)
        assert engine.pka_threshold == 0.5
    
    def test_init_invalid_ph_negative(self):
        """Test that negative pH raises ValueError."""
        with pytest.raises(ValueError, match="pH must be between 0 and 14"):
            ProtonationEngine(ph=-1.0)
    
    def test_init_invalid_ph_too_high(self):
        """Test that pH > 14 raises ValueError."""
        with pytest.raises(ValueError, match="pH must be between 0 and 14"):
            ProtonationEngine(ph=15.0)
    
    def test_init_extreme_ph_warning(self):
        """Test that extreme pH values trigger warning."""
        with patch('mdpilot.workflows.protonation.logger') as mock_logger:
            ProtonationEngine(ph=1.5)
            mock_logger.warning.assert_called_once()
            assert "outside typical physiological range" in mock_logger.warning.call_args[0][0]


class TestProtonationEngineDetermineProtonation:
    """Test ProtonationEngine.determine_protonation() method."""
    
    @patch('mdpilot.workflows.protonation.PDBInfo')
    @patch('mdpilot.workflows.protonation.predict_pka')
    @patch('builtins.open', create=True)
    def test_determine_protonation_basic(self, mock_open, mock_predict_pka, mock_pdb_info_class):
        """Test basic protonation determination."""
        pdb_content = "ATOM      1  CA  HIS A  10      10.000  10.000  10.000  1.00 20.00           C\n"
        mock_open.return_value.__enter__.return_value = pdb_content.splitlines(keepends=True)
        
        mock_info = Mock()
        mock_info.residues = [
            {"name": "HIS", "resSeq": 10, "chainID": "A"}
        ]
        mock_info.chains = ["A"]
        mock_info.metals = []
        mock_pdb_info_class.from_file.return_value = mock_info
        
        mock_propka = Mock()
        mock_propka.pka_values = {"HIS_10_A": 5.5}
        mock_propka.get_asp_residues = Mock(return_value=[])
        mock_propka.get_glu_residues = Mock(return_value=[])
        mock_propka.get_cys_residues = Mock(return_value=[])
        mock_predict_pka.return_value = mock_propka
        
        engine = ProtonationEngine(ph=7.0)
        report = engine.determine_protonation(Path("/tmp/test.pdb"))
        
        assert isinstance(report, ProtonationReport)
        assert len(report.assignments) > 0
    
    @patch('mdpilot.workflows.protonation.PDBInfo')
    @patch('builtins.open', create=True)
    def test_determine_protonation_without_propka(self, mock_open, mock_pdb_info_class):
        """Test protonation determination without propka."""
        pdb_content = "ATOM      1  CA  HIS A  10      10.000  10.000  10.000  1.00 20.00           C\n"
        mock_open.return_value.__enter__.return_value = pdb_content.splitlines(keepends=True)
        
        mock_info = Mock()
        mock_info.residues = [
            {"name": "HIS", "resSeq": 10, "chainID": "A"}
        ]
        mock_info.chains = ["A"]
        mock_info.metals = []
        mock_pdb_info_class.from_file.return_value = mock_info
        
        engine = ProtonationEngine(ph=7.0)
        report = engine.determine_protonation(Path("/tmp/test.pdb"), use_propka=False)
        
        assert isinstance(report, ProtonationReport)
    
    @patch('mdpilot.workflows.protonation.PDBInfo')
    @patch('mdpilot.workflows.protonation.predict_pka')
    @patch('builtins.open', create=True)
    def test_determine_protonation_his_low_pka(self, mock_open, mock_predict_pka, mock_pdb_info_class):
        """Test HIS assignment when pKa < pH."""
        pdb_content = "ATOM      1  CA  HIS A  10      10.000  10.000  10.000  1.00 20.00           C\n"
        mock_open.return_value.__enter__.return_value = pdb_content.splitlines(keepends=True)
        
        mock_info = Mock()
        mock_info.residues = [
            {"name": "HIS", "resSeq": 10, "chainID": "A"}
        ]
        mock_info.chains = ["A"]
        mock_info.metals = []
        mock_pdb_info_class.from_file.return_value = mock_info
        
        mock_propka = Mock()
        mock_propka.pka_values = {"HIS_10_A": 5.0}
        mock_propka.get_asp_residues = Mock(return_value=[])
        mock_propka.get_glu_residues = Mock(return_value=[])
        mock_propka.get_cys_residues = Mock(return_value=[])
        mock_predict_pka.return_value = mock_propka
        
        engine = ProtonationEngine(ph=7.0)
        report = engine.determine_protonation(Path("/tmp/test.pdb"))
        
        assert 10 in report.his_assignments
    
    @patch('mdpilot.workflows.protonation.PDBInfo')
    @patch('mdpilot.workflows.protonation.predict_pka')
    @patch('builtins.open', create=True)
    def test_determine_protonation_his_high_pka(self, mock_open, mock_predict_pka, mock_pdb_info_class):
        """Test HIS assignment when pKa > pH."""
        pdb_content = "ATOM      1  CA  HIS A  10      10.000  10.000  10.000  1.00 20.00           C\n"
        mock_open.return_value.__enter__.return_value = pdb_content.splitlines(keepends=True)
        
        mock_info = Mock()
        mock_info.residues = [
            {"name": "HIS", "resSeq": 10, "chainID": "A"}
        ]
        mock_info.chains = ["A"]
        mock_info.metals = []
        mock_pdb_info_class.from_file.return_value = mock_info
        
        mock_residue = Mock()
        mock_residue.pka = 9.0
        mock_residue.metal_interaction = False
        
        mock_propka = Mock()
        mock_propka.pka_values = {"HIS_10_A": 9.0}
        mock_propka.get_residue = Mock(return_value=mock_residue)
        mock_propka.get_asp_residues = Mock(return_value=[])
        mock_propka.get_glu_residues = Mock(return_value=[])
        mock_propka.get_cys_residues = Mock(return_value=[])
        mock_predict_pka.return_value = mock_propka
        
        engine = ProtonationEngine(ph=7.0)
        report = engine.determine_protonation(Path("/tmp/test.pdb"))
        
        assert 10 in report.his_assignments
        assert report.his_assignments[10] == "HIP"


class TestProtonationEngineHelperMethods:
    """Test ProtonationEngine helper methods."""
    
    def test_standard_pka_values(self):
        """Test that standard pKa values are defined."""
        assert ProtonationEngine.STANDARD_PKA["HIS"] == 6.0
        assert ProtonationEngine.STANDARD_PKA["ASP"] == 3.9
        assert ProtonationEngine.STANDARD_PKA["GLU"] == 4.3
        assert ProtonationEngine.STANDARD_PKA["LYS"] == 10.5
        assert ProtonationEngine.STANDARD_PKA["CYS"] == 8.3
    
    def test_metal_ions_defined(self):
        """Test that metal ions are defined."""
        assert "ZN" in ProtonationEngine.METAL_IONS
        assert "FE" in ProtonationEngine.METAL_IONS
        assert "CU" in ProtonationEngine.METAL_IONS


class TestDetermineProtonationStatesFunction:
    """Test determine_protonation_states convenience function."""
    
    @patch('mdpilot.workflows.protonation.ProtonationEngine')
    def test_function_creates_engine(self, mock_engine_class):
        """Test that function creates ProtonationEngine."""
        mock_engine = Mock()
        mock_report = Mock()
        mock_engine.determine_protonation.return_value = mock_report
        mock_engine_class.return_value = mock_engine
        
        result = determine_protonation_states("/tmp/test.pdb", ph=7.0)
        
        mock_engine_class.assert_called_once_with(ph=7.0)
        mock_engine.determine_protonation.assert_called_once()
        assert result == mock_report
    
    @patch('mdpilot.workflows.protonation.ProtonationEngine')
    def test_function_default_ph(self, mock_engine_class):
        """Test function with default pH."""
        mock_engine = Mock()
        mock_engine.determine_protonation.return_value = Mock()
        mock_engine_class.return_value = mock_engine
        
        determine_protonation_states("/tmp/test.pdb")
        
        mock_engine_class.assert_called_once_with(ph=7.0)
    
    @patch('mdpilot.workflows.protonation.ProtonationEngine')
    def test_function_custom_ph(self, mock_engine_class):
        """Test function with custom pH."""
        mock_engine = Mock()
        mock_engine.determine_protonation.return_value = Mock()
        mock_engine_class.return_value = mock_engine
        
        determine_protonation_states("/tmp/test.pdb", ph=5.5)
        
        mock_engine_class.assert_called_once_with(ph=5.5)
    
    @patch('mdpilot.workflows.protonation.ProtonationEngine')
    def test_function_use_propka_flag(self, mock_engine_class):
        """Test function passes use_propka flag."""
        mock_engine = Mock()
        mock_engine.determine_protonation.return_value = Mock()
        mock_engine_class.return_value = mock_engine
        
        determine_protonation_states("/tmp/test.pdb", use_propka=False)
        
        mock_engine.determine_protonation.assert_called_once()
        call_kwargs = mock_engine.determine_protonation.call_args[1]
        assert call_kwargs["use_propka"] is False
    
    @patch('mdpilot.workflows.protonation.ProtonationEngine')
    def test_function_accepts_path_object(self, mock_engine_class):
        """Test function accepts Path object."""
        mock_engine = Mock()
        mock_engine.determine_protonation.return_value = Mock()
        mock_engine_class.return_value = mock_engine
        
        pdb_path = Path("/tmp/test.pdb")
        determine_protonation_states(pdb_path)
        
        mock_engine.determine_protonation.assert_called_once()
        assert mock_engine.determine_protonation.call_args[0][0] == pdb_path


class TestProtonationEngineIntegration:
    """Integration tests for ProtonationEngine."""
    
    @patch('mdpilot.workflows.protonation.PDBInfo')
    @patch('mdpilot.workflows.protonation.predict_pka')
    @patch('builtins.open', create=True)
    def test_multiple_residue_types(self, mock_open, mock_predict_pka, mock_pdb_info_class):
        """Test handling multiple residue types."""
        pdb_content = """ATOM      1  CA  HIS A  10      10.000  10.000  10.000  1.00 20.00           C
ATOM      2  CA  ASP A  20      11.000  11.000  11.000  1.00 20.00           C
ATOM      3  CA  GLU A  30      12.000  12.000  12.000  1.00 20.00           C
ATOM      4  CA  CYS A  40      13.000  13.000  13.000  1.00 20.00           C
"""
        mock_open.return_value.__enter__.return_value = pdb_content.splitlines(keepends=True)
        
        mock_info = Mock()
        mock_info.residues = [
            {"name": "HIS", "resSeq": 10, "chainID": "A"},
            {"name": "ASP", "resSeq": 20, "chainID": "A"},
            {"name": "GLU", "resSeq": 30, "chainID": "A"},
            {"name": "CYS", "resSeq": 40, "chainID": "A"}
        ]
        mock_info.chains = ["A"]
        mock_info.metals = []
        mock_pdb_info_class.from_file.return_value = mock_info
        
        mock_propka = Mock()
        mock_propka.pka_values = {
            "HIS_10_A": 6.5,
            "ASP_20_A": 3.5,
            "GLU_30_A": 4.0,
            "CYS_40_A": 8.0
        }
        mock_propka.get_asp_residues = Mock(return_value=[])
        mock_propka.get_glu_residues = Mock(return_value=[])
        mock_propka.get_cys_residues = Mock(return_value=[])
        mock_predict_pka.return_value = mock_propka
        
        engine = ProtonationEngine(ph=7.0)
        report = engine.determine_protonation(Path("/tmp/test.pdb"))
        
        assert isinstance(report, ProtonationReport)
        assert len(report.assignments) >= 1
    
    @patch('mdpilot.workflows.protonation.PDBInfo')
    @patch('mdpilot.workflows.protonation.predict_pka')
    @patch('builtins.open', create=True)
    def test_multi_chain_protein(self, mock_open, mock_predict_pka, mock_pdb_info_class):
        """Test handling multi-chain proteins."""
        pdb_content = """ATOM      1  CA  HIS A  10      10.000  10.000  10.000  1.00 20.00           C
ATOM      2  CA  HIS B  10      11.000  11.000  11.000  1.00 20.00           C
"""
        mock_open.return_value.__enter__.return_value = pdb_content.splitlines(keepends=True)
        
        mock_info = Mock()
        mock_info.residues = [
            {"name": "HIS", "resSeq": 10, "chainID": "A"},
            {"name": "HIS", "resSeq": 10, "chainID": "B"}
        ]
        mock_info.chains = ["A", "B"]
        mock_info.metals = []
        mock_pdb_info_class.from_file.return_value = mock_info
        
        mock_propka = Mock()
        mock_propka.pka_values = {
            "HIS_10_A": 6.0,
            "HIS_10_B": 7.0
        }
        mock_propka.get_asp_residues = Mock(return_value=[])
        mock_propka.get_glu_residues = Mock(return_value=[])
        mock_propka.get_cys_residues = Mock(return_value=[])
        mock_predict_pka.return_value = mock_propka
        
        engine = ProtonationEngine(ph=7.0)
        report = engine.determine_protonation(Path("/tmp/test.pdb"))
        
        assert len(report.assignments) >= 2

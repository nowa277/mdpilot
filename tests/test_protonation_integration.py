"""Unit tests for protonation workflow integration."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from mdpilot.workflows.standard_protein import WorkflowConfig, StandardProteinWorkflow


class TestWorkflowConfig:
    """Test WorkflowConfig protonation parameters."""

    def test_default_values(self):
        """Test default protonation parameters."""
        config = WorkflowConfig()
        assert config.pka_threshold == 1.0
        assert config.use_hplusplus == False
        assert config.hplusplus_timeout == 300
        assert config.protonation_report_detail == "summary"

    def test_custom_values(self):
        """Test custom protonation parameters."""
        config = WorkflowConfig(
            pka_threshold=0.5,
            use_hplusplus=True,
            hplusplus_timeout=600,
            protonation_report_detail="full"
        )
        assert config.pka_threshold == 0.5
        assert config.use_hplusplus == True
        assert config.hplusplus_timeout == 600
        assert config.protonation_report_detail == "full"

    def test_invalid_threshold(self):
        """Test negative pka_threshold raises error."""
        with pytest.raises(ValueError, match="pka_threshold must be non-negative"):
            WorkflowConfig(pka_threshold=-1.0)

    def test_invalid_detail_level(self):
        """Test invalid report detail level raises error."""
        with pytest.raises(ValueError, match="protonation_report_detail must be"):
            WorkflowConfig(protonation_report_detail="verbose")

    def test_invalid_timeout(self):
        """Test low timeout raises error."""
        with pytest.raises(ValueError, match="hplusplus_timeout must be at least"):
            WorkflowConfig(hplusplus_timeout=10)


class TestProtonationEngineIntegration:
    """Test that WorkflowConfig parameters are correctly passed to ProtonationEngine."""

    def test_config_values_set_correctly(self):
        """Test that WorkflowConfig stores pka_threshold correctly."""
        config = WorkflowConfig(
            pka_threshold=0.5,
            target_ph=7.4
        )
        workflow = StandardProteinWorkflow(config)

        assert workflow.config.pka_threshold == 0.5
        assert workflow.config.target_ph == 7.4

    @patch('mdpilot.workflows.standard_protein.ProtonationEngine')
    @patch('mdpilot.workflows.standard_protein.StandardProteinValidator')
    async def test_pka_threshold_passed_to_engine_in_workflow(self, mock_validator_class, mock_engine_class):
        """Test that pka_threshold is passed to ProtonationEngine during workflow execution."""
        # Setup mock engine
        mock_engine = Mock()
        mock_engine_class.return_value = mock_engine
        mock_report = Mock()
        mock_report.assignments = []
        mock_report.summary = Mock(return_value="Test summary")
        mock_engine.determine_protonation.return_value = mock_report

        # Setup mock validator
        mock_validator = Mock()
        mock_validator_class.return_value = mock_validator
        mock_validation = Mock()
        mock_validation.passed = True
        mock_validator.validate.return_value = mock_validation

        # Create workflow with custom pka_threshold
        config = WorkflowConfig(
            pka_threshold=0.5,
            target_ph=7.4
        )
        workflow = StandardProteinWorkflow(config)

        # Create a minimal test PDB file
        test_pdb = Path('/tmp/test_protonation.pdb')
        test_pdb.write_text(
            "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00\n"
            "END\n"
        )

        # Mock the other workflow steps
        with patch.object(workflow, '_run_pdb4amber', return_value=test_pdb), \
             patch.object(workflow, '_run_reduce', side_effect=FileNotFoundError("reduce not found")), \
             patch.object(workflow, '_run_tleap', return_value=(Path('/tmp/test.prmtop'), Path('/tmp/test.inpcrd'))), \
             patch.object(workflow, '_run_minimization', return_value=Path('/tmp/min.rst')):

            try:
                result = await workflow.run_from_pdb_file(test_pdb)
            except Exception as e:
                # We expect some failures due to mocking, but we only care about ProtonationEngine call
                pass

        # Verify ProtonationEngine was initialized with correct parameters
        mock_engine_class.assert_called_once_with(
            ph=7.4,
            pka_threshold=0.5
        )


class TestWorkflowResultSummary:
    """Test WorkflowResult.summary() enhancements for protonation display."""

    def test_summary_mode_displays_statistics(self):
        """Test that summary mode displays key protonation statistics."""
        from mdpilot.workflows.standard_protein import WorkflowResult
        from mdpilot.workflows.protonation import ProtonationReport, ProtonationAssignment

        # Create mock assignments
        assignments = [
            ProtonationAssignment("HIS", 36, "A", "HIE", "pKa ≈ pH"),
            ProtonationAssignment("HIS", 60, "A", "HID", "Metal coordination"),
            ProtonationAssignment("HIS", 63, "A", "HID", "Metal coordination"),
            ProtonationAssignment("HIS", 94, "A", "HIP", "pKa >> pH"),
            ProtonationAssignment("ASP", 42, "A", "ASH", "pKa > pH"),
            ProtonationAssignment("CYS", 22, "A", "CYX", "Disulfide bond"),
            ProtonationAssignment("CYS", 94, "A", "CYX", "Disulfide bond"),
        ]

        protonation = ProtonationReport(
            assignments=assignments,
            his_assignments={36: "HIE", 60: "HID", 63: "HID", 94: "HIP"},
            asp_glu_assignments={42: "ASH"},
            cys_assignments={22: "CYX", 94: "CYX"}
        )

        result = WorkflowResult(
            success=True,
            prmtop=Path("/tmp/system.prmtop"),
            inpcrd=Path("/tmp/min.rst"),
            protonation=protonation,
            _report_detail="summary"
        )

        summary = result.summary()

        # Verify summary contains key statistics
        assert "📊 Protonation State Summary:" in summary
        assert "HIS residues: 4 assigned" in summary
        assert "HID (metal-coordinating): 2" in summary
        assert "HIE (neutral): 1" in summary
        assert "HIP (charged): 1" in summary
        assert "Protonated acidic residues: 1" in summary
        assert "Disulfide bonds: 1" in summary

    def test_full_mode_delegates_to_protonation_report(self):
        """Test that full mode delegates to ProtonationReport.summary()."""
        from mdpilot.workflows.standard_protein import WorkflowResult
        from mdpilot.workflows.protonation import ProtonationReport, ProtonationAssignment

        assignments = [
            ProtonationAssignment("HIS", 36, "A", "HIE", "pKa ≈ pH"),
        ]

        protonation = ProtonationReport(
            assignments=assignments,
            his_assignments={36: "HIE"},
            asp_glu_assignments={},
            cys_assignments={}
        )

        result = WorkflowResult(
            success=True,
            prmtop=Path("/tmp/system.prmtop"),
            inpcrd=Path("/tmp/min.rst"),
            protonation=protonation,
            _report_detail="full"
        )

        summary = result.summary()

        # Should contain full ProtonationReport output
        # ProtonationReport.summary() includes detailed residue listings
        assert "📊 Protonation State Summary:" in summary

    def test_detail_override_parameter(self):
        """Test that detail_override parameter works."""
        from mdpilot.workflows.standard_protein import WorkflowResult
        from mdpilot.workflows.protonation import ProtonationReport, ProtonationAssignment

        assignments = [
            ProtonationAssignment("HIS", 36, "A", "HIE", "pKa ≈ pH"),
        ]

        protonation = ProtonationReport(
            assignments=assignments,
            his_assignments={36: "HIE"},
            asp_glu_assignments={},
            cys_assignments={}
        )

        result = WorkflowResult(
            success=True,
            prmtop=Path("/tmp/system.prmtop"),
            inpcrd=Path("/tmp/min.rst"),
            protonation=protonation,
            _report_detail="summary"
        )

        # Override to full
        summary_full = result.summary(detail_override="full")
        assert "📊 Protonation State Summary:" in summary_full

        # Override to summary
        summary_brief = result.summary(detail_override="summary")
        assert "HIS residues: 1 assigned" in summary_brief

    def test_no_protonation_report(self):
        """Test that summary works when protonation is None."""
        from mdpilot.workflows.standard_protein import WorkflowResult

        result = WorkflowResult(
            success=True,
            prmtop=Path("/tmp/system.prmtop"),
            inpcrd=Path("/tmp/min.rst"),
            protonation=None
        )

        summary = result.summary()

        # Should not crash, and should not contain protonation section
        assert "✅ Workflow completed successfully" in summary
        assert "📊 Protonation State Summary:" not in summary



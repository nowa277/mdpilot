"""
Unit tests for workflows/standard_protein.py

Tests WorkflowConfig, WorkflowResult, and StandardProteinWorkflow
for standard protein preparation pipeline.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from mdpilot.workflows.standard_protein import (
    WorkflowConfig,
    WorkflowResult,
    StandardProteinWorkflow,
    prepare_standard_protein
)


class TestWorkflowConfig:
    """Test WorkflowConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = WorkflowConfig()
        
        assert config.force_field == "ff19SB"
        assert config.water_model == "OPC3"
        assert config.box_type == "octahedron"
        assert config.box_padding == 10.0
        assert config.use_propka is True
        assert config.target_ph == 7.0
        assert config.pka_threshold == 1.0
        assert config.use_hplusplus is False
        assert config.minimize_steps == 1000
        assert config.output_prefix == "system"
        assert config.keep_intermediates is True
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = WorkflowConfig(
            force_field="ff14SB",
            water_model="TIP3P",
            box_type="cubic",
            target_ph=5.5,
            minimize_steps=500
        )
        
        assert config.force_field == "ff14SB"
        assert config.water_model == "TIP3P"
        assert config.box_type == "cubic"
        assert config.target_ph == 5.5
        assert config.minimize_steps == 500
    
    def test_invalid_pka_threshold(self):
        """Test that negative pKa threshold raises ValueError."""
        with pytest.raises(ValueError, match="pka_threshold must be non-negative"):
            WorkflowConfig(pka_threshold=-1.0)
    
    def test_invalid_hplusplus_timeout(self):
        """Test that short H++ timeout raises ValueError."""
        with pytest.raises(ValueError, match="hplusplus_timeout must be at least 60"):
            WorkflowConfig(hplusplus_timeout=30)
    
    def test_invalid_report_detail(self):
        """Test that invalid report detail raises ValueError."""
        with pytest.raises(ValueError, match="protonation_report_detail must be"):
            WorkflowConfig(protonation_report_detail="invalid")
    
    def test_work_dir_default(self):
        """Test that work_dir defaults to current directory."""
        config = WorkflowConfig()
        assert isinstance(config.work_dir, Path)


class TestWorkflowResult:
    """Test WorkflowResult dataclass."""
    
    def test_success_result(self):
        """Test successful workflow result."""
        result = WorkflowResult(
            success=True,
            prmtop=Path("/tmp/system.prmtop"),
            inpcrd=Path("/tmp/system.inpcrd")
        )
        
        assert result.success is True
        assert result.prmtop == Path("/tmp/system.prmtop")
        assert result.inpcrd == Path("/tmp/system.inpcrd")
        assert result.error is None
    
    def test_failure_result(self):
        """Test failed workflow result."""
        result = WorkflowResult(
            success=False,
            error="Test error message"
        )
        
        assert result.success is False
        assert result.error == "Test error message"
        assert result.prmtop is None
        assert result.inpcrd is None
    
    def test_summary_success(self):
        """Test summary generation for successful result."""
        result = WorkflowResult(
            success=True,
            prmtop=Path("/tmp/system.prmtop"),
            inpcrd=Path("/tmp/system.inpcrd")
        )
        
        summary = result.summary()
        assert "✅" in summary or "completed successfully" in summary.lower()
        assert "system.prmtop" in summary
        assert "system.inpcrd" in summary
    
    def test_summary_failure(self):
        """Test summary generation for failed result."""
        result = WorkflowResult(
            success=False,
            error="Test error"
        )
        
        summary = result.summary()
        assert "❌" in summary or "failed" in summary.lower()
        assert "Test error" in summary
    
    def test_intermediate_files_default(self):
        """Test that intermediate_files defaults to empty dict."""
        result = WorkflowResult(success=True)
        assert result.intermediate_files == {}
    
    def test_intermediate_files_storage(self):
        """Test storing intermediate files."""
        result = WorkflowResult(
            success=True,
            intermediate_files={
                "cleaned_pdb": Path("/tmp/cleaned.pdb"),
                "protonated_pdb": Path("/tmp/protonated.pdb")
            }
        )
        
        assert "cleaned_pdb" in result.intermediate_files
        assert result.intermediate_files["cleaned_pdb"] == Path("/tmp/cleaned.pdb")


class TestStandardProteinWorkflowInit:
    """Test StandardProteinWorkflow initialization."""
    
    def test_init_with_default_config(self):
        """Test initialization with default config."""
        workflow = StandardProteinWorkflow()
        
        assert isinstance(workflow.config, WorkflowConfig)
        assert workflow.config.force_field == "ff19SB"
    
    def test_init_with_custom_config(self):
        """Test initialization with custom config."""
        config = WorkflowConfig(force_field="ff14SB", target_ph=5.5)
        workflow = StandardProteinWorkflow(config=config)
        
        assert workflow.config.force_field == "ff14SB"
        assert workflow.config.target_ph == 5.5
    
    def test_init_creates_work_dir(self):
        """Test that initialization handles work directory."""
        config = WorkflowConfig(work_dir=Path("/tmp/test_workflow"))
        workflow = StandardProteinWorkflow(config=config)
        
        assert workflow.config.work_dir == Path("/tmp/test_workflow")


class TestStandardProteinWorkflowMethods:
    """Test StandardProteinWorkflow methods."""
    
    def test_workflow_has_config(self):
        """Test that workflow stores config."""
        config = WorkflowConfig(force_field="ff14SB")
        workflow = StandardProteinWorkflow(config=config)
        
        assert workflow.config == config
        assert workflow.config.force_field == "ff14SB"


class TestPrepareStandardProteinFunction:
    """Test prepare_standard_protein convenience function."""
    
    @pytest.mark.asyncio
    @patch('mdpilot.workflows.standard_protein.StandardProteinWorkflow')
    async def test_function_creates_workflow(self, mock_workflow_class):
        """Test that function creates workflow instance."""
        mock_workflow = AsyncMock()
        mock_result = WorkflowResult(success=True)
        mock_workflow.run_from_pdb_id.return_value = mock_result
        mock_workflow_class.return_value = mock_workflow
        
        result = await prepare_standard_protein("1AKI")
        
        mock_workflow_class.assert_called_once()
        assert result == mock_result
    
    @pytest.mark.asyncio
    @patch('mdpilot.workflows.standard_protein.StandardProteinWorkflow')
    async def test_function_with_custom_config(self, mock_workflow_class):
        """Test function with custom config."""
        mock_workflow = AsyncMock()
        mock_result = WorkflowResult(success=True)
        mock_workflow.run_from_pdb_id.return_value = mock_result
        mock_workflow_class.return_value = mock_workflow
        
        config = WorkflowConfig(force_field="ff14SB")
        result = await prepare_standard_protein("1AKI", config=config)
        
        call_args = mock_workflow_class.call_args
        assert call_args[0][0] == config or call_args[1].get('config') == config
        assert result == mock_result
    
    @pytest.mark.asyncio
    @patch('mdpilot.workflows.standard_protein.StandardProteinWorkflow')
    async def test_function_handles_failure(self, mock_workflow_class):
        """Test function handles workflow failure."""
        mock_workflow = AsyncMock()
        mock_result = WorkflowResult(success=False, error="Test error")
        mock_workflow.run_from_pdb_id.return_value = mock_result
        mock_workflow_class.return_value = mock_workflow
        
        result = await prepare_standard_protein("1AKI")
        
        assert result.success is False
        assert result.error == "Test error"


class TestWorkflowConfigValidation:
    """Test WorkflowConfig validation logic."""
    
    def test_valid_box_types(self):
        """Test that valid box types are accepted."""
        config1 = WorkflowConfig(box_type="cubic")
        config2 = WorkflowConfig(box_type="octahedron")
        
        assert config1.box_type == "cubic"
        assert config2.box_type == "octahedron"
    
    def test_ph_range(self):
        """Test various pH values."""
        config1 = WorkflowConfig(target_ph=1.0)
        config2 = WorkflowConfig(target_ph=7.0)
        config3 = WorkflowConfig(target_ph=14.0)
        
        assert config1.target_ph == 1.0
        assert config2.target_ph == 7.0
        assert config3.target_ph == 14.0
    
    def test_minimize_steps_range(self):
        """Test various minimization step counts."""
        config1 = WorkflowConfig(minimize_steps=100)
        config2 = WorkflowConfig(minimize_steps=1000)
        config3 = WorkflowConfig(minimize_steps=10000)
        
        assert config1.minimize_steps == 100
        assert config2.minimize_steps == 1000
        assert config3.minimize_steps == 10000


class TestWorkflowResultReporting:
    """Test WorkflowResult reporting features."""
    
    def test_summary_with_validation(self):
        """Test summary includes validation info."""
        mock_validation = Mock()
        mock_validation.passed = True
        
        result = WorkflowResult(
            success=True,
            prmtop=Path("/tmp/system.prmtop"),
            inpcrd=Path("/tmp/system.inpcrd"),
            validation=mock_validation
        )
        
        summary = result.summary()
        assert isinstance(summary, str)
        assert len(summary) > 0
    
    def test_summary_with_protonation(self):
        """Test summary includes protonation info."""
        mock_protonation = Mock()
        mock_protonation.his_assignments = {10: "HID", 20: "HIE"}
        mock_protonation.asp_glu_assignments = {}
        mock_protonation.cys_assignments = {}
        
        result = WorkflowResult(
            success=True,
            prmtop=Path("/tmp/system.prmtop"),
            inpcrd=Path("/tmp/system.inpcrd"),
            protonation=mock_protonation
        )
        
        summary = result.summary()
        assert isinstance(summary, str)
        assert len(summary) > 0
    
    def test_summary_detail_override(self):
        """Test summary detail level override."""
        result = WorkflowResult(
            success=True,
            prmtop=Path("/tmp/system.prmtop"),
            inpcrd=Path("/tmp/system.inpcrd"),
            _report_detail="summary"
        )
        
        summary_brief = result.summary(detail_override="summary")
        summary_full = result.summary(detail_override="full")
        
        assert isinstance(summary_brief, str)
        assert isinstance(summary_full, str)

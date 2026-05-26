"""Comprehensive tests for WorkflowEngine to improve coverage."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from mdpilot.agent.legacy_workflow_engine import (
    WorkflowEngine,
    Phase,
    ANALYSIS_READY,
    MODE_SELECT_REQUEST,
    PARAMS_PREVIEW,
    PARAM_CONFIRM_REQUEST,
    STEP_CONFIGURE,
    STEP_EXECUTING,
    STEP_RESULT,
    STEP_CONFIRM_REQUEST,
    RETRY_ATTEMPT,
    WORKFLOW_COMPLETE,
)
from mdpilot.agent.events import EventEmitter


@pytest.fixture
def mock_config():
    """Mock configuration."""
    config = MagicMock()
    config.agent.default_mode = "react"
    config.provider.model = "test-model"
    return config


@pytest.fixture
def mock_dispatcher():
    """Mock tool dispatcher."""
    dispatcher = MagicMock()
    dispatcher.execute = AsyncMock()
    return dispatcher


@pytest.fixture
def mock_llm():
    """Mock LLM provider."""
    llm = MagicMock()
    llm.complete = AsyncMock(return_value="mock response")
    return llm


@pytest.fixture
def mock_error_classifier():
    """Mock error classifier."""
    def classifier(error_msg: str):
        result = MagicMock()
        result.code = "TEST_ERROR"
        result.category = "test"
        result.suggestion = "test suggestion"
        return result
    return classifier


@pytest.fixture
def events():
    """Real event emitter."""
    return EventEmitter()


@pytest.fixture
def workflow_engine(mock_config, mock_dispatcher, mock_llm, mock_error_classifier, events):
    """Create WorkflowEngine instance."""
    return WorkflowEngine(
        config=mock_config,
        dispatcher=mock_dispatcher,
        llm=mock_llm,
        error_classifier=mock_error_classifier,
        events=events,
    )


class TestWorkflowEngineInitialization:
    """Test WorkflowEngine initialization."""

    def test_initial_state(self, workflow_engine):
        """Engine starts in ANALYZE phase with default settings."""
        assert workflow_engine._phase == Phase.ANALYZE
        assert workflow_engine._workflow_mode == "auto"
        assert workflow_engine._retry_count == 0
        assert workflow_engine._params == {}

    def test_futures_are_none(self, workflow_engine):
        """Confirmation futures start as None."""
        assert workflow_engine._mode_selected is None
        assert workflow_engine._param_confirm_future is None
        assert workflow_engine._step_confirm_future is None


class TestWorkflowModeManagement:
    """Test workflow mode setting and confirmation."""

    def test_set_workflow_mode(self, workflow_engine):
        """set_workflow_mode updates internal state."""
        workflow_engine.set_workflow_mode("semi-auto")
        assert workflow_engine._workflow_mode == "semi-auto"

    def test_set_workflow_mode_resolves_future(self, workflow_engine):
        """set_workflow_mode resolves pending future."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            future = loop.create_future()
            workflow_engine._mode_selected = future

            workflow_engine.set_workflow_mode("manual")

            assert future.done()
            assert future.result() == "manual"
        finally:
            loop.close()

    def test_set_workflow_mode_ignores_done_future(self, workflow_engine):
        """set_workflow_mode doesn't error on already-done future."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            future = loop.create_future()
            future.set_result("old-value")
            workflow_engine._mode_selected = future

            # Should not raise
            workflow_engine.set_workflow_mode("new-value")

            # Future still has old value
            assert future.result() == "old-value"
        finally:
            loop.close()


class TestParameterConfirmation:
    """Test parameter confirmation logic."""

    def test_confirm_parameters_true(self, workflow_engine):
        """confirm_parameters resolves future with True."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            future = loop.create_future()
            workflow_engine._param_confirm_future = future

            workflow_engine.confirm_parameters(True)

            assert future.done()
            assert future.result() is True
        finally:
            loop.close()

    def test_confirm_parameters_false(self, workflow_engine):
        """confirm_parameters resolves future with False."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            future = loop.create_future()
            workflow_engine._param_confirm_future = future

            workflow_engine.confirm_parameters(False)

            assert future.done()
            assert future.result() is False
        finally:
            loop.close()

    def test_confirm_parameters_no_future(self, workflow_engine):
        """confirm_parameters handles None future gracefully."""
        workflow_engine._param_confirm_future = None
        # Should not raise
        workflow_engine.confirm_parameters(True)


class TestStepConfirmation:
    """Test step confirmation logic."""

    def test_confirm_step_true(self, workflow_engine):
        """confirm_step resolves future with True."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            future = loop.create_future()
            workflow_engine._step_confirm_future = future

            workflow_engine.confirm_step(True)

            assert future.done()
            assert future.result() is True
        finally:
            loop.close()

    def test_confirm_step_false(self, workflow_engine):
        """confirm_step resolves future with False."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            future = loop.create_future()
            workflow_engine._step_confirm_future = future

            workflow_engine.confirm_step(False)

            assert future.done()
            assert future.result() is False
        finally:
            loop.close()


class TestAnalyzePhase:
    """Test ANALYZE phase logic."""

    @pytest.mark.asyncio
    async def test_analyze_with_valid_pdb_path(self, workflow_engine, tmp_path):
        """_run_analyze extracts PDB path from input."""
        # Create a test PDB file
        pdb_file = tmp_path / "test.pdb"
        pdb_file.write_text("ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N\n")

        events_received = []
        workflow_engine._events.on(ANALYSIS_READY, lambda data: events_received.append(("analysis", data)))
        workflow_engine._events.on(MODE_SELECT_REQUEST, lambda data: events_received.append(("mode_select", data)))

        # Start analyze in background and immediately resolve the future
        async def run_with_timeout():
            task = asyncio.create_task(workflow_engine._run_analyze(str(pdb_file)))
            await asyncio.sleep(0.1)  # Let it start
            workflow_engine.set_workflow_mode("auto")
            await task

        await run_with_timeout()

        assert workflow_engine._phase == Phase.CONFIGURE
        assert len(events_received) == 2
        assert events_received[0][0] == "analysis"
        assert events_received[1][0] == "mode_select"

    @pytest.mark.asyncio
    async def test_analyze_with_invalid_path(self, workflow_engine):
        """_run_analyze handles invalid PDB path."""
        events_received = []
        # The event handler receives an Event object with a .data attribute
        def handler(event):
            events_received.append(event)

        workflow_engine._events.on(ANALYSIS_READY, handler)

        async def run_with_timeout():
            task = asyncio.create_task(workflow_engine._run_analyze("invalid input"))
            await asyncio.sleep(0.1)
            workflow_engine.set_workflow_mode("auto")
            await task

        await run_with_timeout()

        assert len(events_received) == 1
        # events_received[0] is an Event object with .data dict
        # The emit call wraps the analysis in {"data": analysis}
        assert "data" in events_received[0].data
        analysis_data = events_received[0].data["data"]
        assert "error" in analysis_data
        assert analysis_data["atoms"] == 0

    @pytest.mark.asyncio
    async def test_analyze_timeout_defaults_to_auto(self, workflow_engine):
        """_run_analyze defaults to auto mode on timeout."""
        async def run_with_timeout():
            # Don't resolve the future - let it timeout
            with patch('asyncio.wait_for', side_effect=asyncio.TimeoutError):
                await workflow_engine._run_analyze("test.pdb")

        await run_with_timeout()

        assert workflow_engine._workflow_mode == "auto"
        assert workflow_engine._phase == Phase.CONFIGURE

    @pytest.mark.asyncio
    async def test_analyze_exception_defaults_to_auto(self, workflow_engine):
        """_run_analyze defaults to auto mode on exception."""
        async def run_with_timeout():
            with patch('asyncio.wait_for', side_effect=RuntimeError("test error")):
                await workflow_engine._run_analyze("test.pdb")

        await run_with_timeout()

        assert workflow_engine._workflow_mode == "auto"


class TestConfigurePhase:
    """Test CONFIGURE phase logic."""

    @pytest.mark.asyncio
    async def test_configure_auto_mode(self, workflow_engine):
        """_run_configure in auto mode doesn't wait for confirmation."""
        workflow_engine._workflow_mode = "auto"

        events_received = []
        workflow_engine._events.on(STEP_CONFIGURE, lambda data: events_received.append(("configure", data)))
        workflow_engine._events.on(PARAMS_PREVIEW, lambda data: events_received.append(("preview", data)))

        await workflow_engine._run_configure()

        assert workflow_engine._phase == Phase.EXECUTE
        assert len(events_received) == 2
        assert workflow_engine._params["forcefield"] == "ff19SB"
        assert workflow_engine._params["water_model"] == "OPC3"

    @pytest.mark.asyncio
    async def test_configure_semi_auto_confirmed(self, workflow_engine):
        """_run_configure in semi-auto mode waits for confirmation."""
        workflow_engine._workflow_mode = "semi-auto"

        async def run_with_confirm():
            task = asyncio.create_task(workflow_engine._run_configure())
            await asyncio.sleep(0.1)  # Let it start waiting
            workflow_engine.confirm_parameters(True)
            await task

        await run_with_confirm()

        assert workflow_engine._phase == Phase.EXECUTE

    @pytest.mark.asyncio
    async def test_configure_semi_auto_cancelled(self, workflow_engine):
        """_run_configure raises error when user cancels."""
        workflow_engine._workflow_mode = "semi-auto"

        async def run_with_cancel():
            task = asyncio.create_task(workflow_engine._run_configure())
            await asyncio.sleep(0.1)
            workflow_engine.confirm_parameters(False)
            with pytest.raises(RuntimeError, match="User cancelled"):
                await task

        await run_with_cancel()

    @pytest.mark.asyncio
    async def test_configure_timeout(self, workflow_engine):
        """_run_configure raises error on timeout."""
        workflow_engine._workflow_mode = "semi-auto"

        with patch('asyncio.wait_for', side_effect=asyncio.TimeoutError):
            with pytest.raises(RuntimeError, match="timeout"):
                await workflow_engine._run_configure()


class TestPDBAnalysis:
    """Test PDB file analysis."""

    @pytest.mark.asyncio
    async def test_analyze_pdb_file_valid(self, workflow_engine, tmp_path):
        """_analyze_pdb_file parses valid PDB."""
        pdb_file = tmp_path / "test.pdb"
        pdb_content = """ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N
ATOM      2  CA  ALA A   1       1.000   1.000   1.000  1.00  0.00           C
HETATM    3  O   HOH A 100       2.000   2.000   2.000  1.00  0.00           O
"""
        pdb_file.write_text(pdb_content)

        result = await workflow_engine._analyze_pdb_file(str(pdb_file))

        assert result["atoms"] == 3
        assert result["residues"] == 1  # Only ALA, not HOH
        assert result["waters"] == 1
        assert "A" in result["chains"]

    @pytest.mark.asyncio
    async def test_analyze_pdb_file_nonexistent(self, workflow_engine):
        """_analyze_pdb_file handles nonexistent file."""
        result = await workflow_engine._analyze_pdb_file("/nonexistent/file.pdb")

        assert result["atoms"] == 0
        assert result["residues"] == 0
        assert result["chains"] == []

    @pytest.mark.asyncio
    async def test_analyze_pdb_file_exception(self, workflow_engine, tmp_path):
        """_analyze_pdb_file handles read errors."""
        pdb_file = tmp_path / "test.pdb"
        pdb_file.write_text("invalid content")
        pdb_file.chmod(0o000)  # Make unreadable

        try:
            result = await workflow_engine._analyze_pdb_file(str(pdb_file))
            # Should return default data on error
            assert result["atoms"] == 0
        finally:
            pdb_file.chmod(0o644)


class TestScriptGeneration:
    """Test tleap and sander script generation."""

    def test_generate_tleap_script(self, workflow_engine):
        """_generate_tleap_script returns valid script."""
        workflow_engine._params = {
            "forcefield": "ff19SB",
            "water_model": "OPC3",
            "box_type": "truncated octahedron",
        }

        script = workflow_engine._generate_tleap_script()

        assert "source leaprc.protein.ff19SB" in script
        assert "solvateoct" in script.lower() or "solvate" in script.lower()

    def test_generate_sander_script(self, workflow_engine):
        """_generate_sander_script returns valid script."""
        script = workflow_engine._generate_sander_script()

        assert "imin" in script or "ntmin" in script
        assert "maxcyc" in script


class TestPhaseEnums:
    """Test Phase enum values."""

    def test_phase_values(self):
        """Phase enum has correct values."""
        assert Phase.ANALYZE.value == "analyze"
        assert Phase.CONFIGURE.value == "configure"
        assert Phase.EXECUTE.value == "execute"
        assert Phase.COMPLETE.value == "complete"


class TestEventConstants:
    """Test event constant values."""

    def test_event_constants(self):
        """Event constants are defined."""
        assert ANALYSIS_READY == "analysis_ready"
        assert MODE_SELECT_REQUEST == "mode_select_request"
        assert PARAMS_PREVIEW == "params_preview"
        assert PARAM_CONFIRM_REQUEST == "param_confirm_request"
        assert STEP_CONFIGURE == "step_configure"
        assert STEP_EXECUTING == "step_executing"
        assert STEP_RESULT == "step_result"
        assert STEP_CONFIRM_REQUEST == "step_confirm_request"
        assert RETRY_ATTEMPT == "retry_attempt"
        assert WORKFLOW_COMPLETE == "workflow_complete"

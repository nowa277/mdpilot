"""Integration tests for WorkflowEngine 4-phase flow."""

from unittest.mock import MagicMock, AsyncMock, patch
import pytest
import asyncio

from mdpilot.agent.legacy_workflow_engine import WorkflowEngine, Phase
from mdpilot.agent.task_classifier import TaskClassifier


class TestWorkflowIntegration:
    """Integration tests for 4-phase workflow."""

    @pytest.fixture
    def mock_dispatcher(self):
        """Mock ToolDispatcher."""
        dispatcher = MagicMock()
        return dispatcher

    @pytest.fixture
    def mock_llm(self):
        """Mock LLM client."""
        llm = MagicMock()
        llm.complete = AsyncMock(return_value="mock response")
        llm.complete_with_structured_output = AsyncMock(return_value={
            "action": "continue",
            "reasoning": "test",
        })
        return llm

    @pytest.fixture
    def mock_events(self):
        """Mock EventEmitter."""
        from mdpilot.agent.events import EventEmitter
        return EventEmitter()

    @pytest.fixture
    def mock_config(self):
        """Mock config object."""
        config = MagicMock()
        config.agent.default_mode = "react"
        config.provider.model = "test-model"
        return config

    @pytest.fixture
    def workflow_engine(self, mock_config, mock_dispatcher, mock_llm, mock_events):
        """Create WorkflowEngine with mocks."""
        from mdpilot.tools.error_classifier import classify_amber_error
        engine = WorkflowEngine(
            config=mock_config,
            dispatcher=mock_dispatcher,
            llm=mock_llm,
            error_classifier=classify_amber_error,
            events=mock_events,
        )
        return engine

    def test_phase1_analysis(self, workflow_engine):
        """Test Phase 1: PDB Analysis sets initial phase."""
        assert workflow_engine._phase == Phase.ANALYZE
        assert workflow_engine._workflow_mode == "auto"

    def test_phase2_parameter_selection(self, workflow_engine):
        """Test Phase 2: CONFIGURE phase sets hardcoded params."""
        workflow_engine._phase = Phase.CONFIGURE
        # params are set internally during configure; verify structure exists
        assert workflow_engine._params == {}

    def test_phase3_execution(self, workflow_engine):
        """Test Phase 3: EXECUTE phase enum value."""
        assert Phase.EXECUTE.value == "execute"

    def test_phase4_verification(self, workflow_engine):
        """Test Phase 4: COMPLETE phase enum value."""
        assert Phase.COMPLETE.value == "complete"

    def test_task_classification_md_task(self):
        """Test MD_TASK routing."""
        classifier = TaskClassifier()
        result = classifier.classify("帮我构建 1AKI 蛋白")
        assert result == "MD_TASK"

    def test_task_classification_chat(self):
        """Test CHAT routing."""
        classifier = TaskClassifier()
        result = classifier.classify("什么是分子动力学")
        assert result == "CHAT"

    def test_workflow_mode_setter(self, workflow_engine):
        """Test set_workflow_mode updates internal state."""
        workflow_engine.set_workflow_mode("semi-auto")
        assert workflow_engine._workflow_mode == "semi-auto"
        workflow_engine.set_workflow_mode("auto")
        assert workflow_engine._workflow_mode == "auto"

    def test_routing_integration(self):
        """Test full routing: input -> classifier -> workflow."""
        test_cases = [
            ("构建 1AKI 蛋白体系", "MD_TASK"),
            ("解释 ff19SB 力场", "CHAT"),
            ("用 tleap 构建体系", "MD_TASK"),
            ("为什么需要加盐", "CHAT"),
        ]
        classifier = TaskClassifier()
        for input_text, expected in test_cases:
            result = classifier.classify(input_text)
            assert result == expected, f"Failed for '{input_text}': expected {expected}, got {result}"

    def test_error_classifier(self):
        """Test error classifier runs without error on unknown input."""
        from mdpilot.tools.error_classifier import classify_amber_error
        result = classify_amber_error("tleap: command not found")
        # Returns None for unknown errors; should not raise
        assert result is None or hasattr(result, "error_code")

    @pytest.mark.asyncio
    async def test_full_workflow_execution(self):
        """Test complete workflow from PDB input to completion.

        This test verifies that WorkflowEngine uses real ToolDispatcher calls
        instead of placeholder execution.
        """
        # Setup mock components
        config = MagicMock()
        config.agent.default_mode = "auto"
        config.provider.model = "test-model"

        dispatcher = MagicMock()
        # Mock successful tool execution
        from mdpilot.types import ToolOutput
        dispatcher.execute = AsyncMock(return_value=ToolOutput(
            output="Tool executed successfully",
            success=True
        ))

        llm = MagicMock()
        llm.complete = AsyncMock(return_value="Analysis complete")
        llm.complete_with_structured_output = AsyncMock(return_value={
            "action": "continue",
            "reasoning": "test reasoning",
        })

        from mdpilot.agent.events import EventEmitter
        events = EventEmitter()

        from mdpilot.tools.error_classifier import classify_amber_error

        # Create engine
        engine = WorkflowEngine(
            config=config,
            dispatcher=dispatcher,
            llm=llm,
            error_classifier=classify_amber_error,
            events=events,
        )

        # Mock mode selection (simulates user selecting auto mode)
        async def mock_mode_select():
            await asyncio.sleep(0.1)
            engine.set_workflow_mode("auto")

        asyncio.create_task(mock_mode_select())

        # Run workflow with PDB input
        pdb_path = "tests/test_output/1ubq/1UBQ.pdb"
        result = await engine.run(f"Build system: {pdb_path}")

        # Verify workflow completed
        assert engine._phase == Phase.COMPLETE
        assert "Workflow complete" in result or "complete" in result.lower()

        # Verify dispatcher.execute was called for each workflow step
        assert dispatcher.execute.call_count == 4, \
            f"Expected 4 tool calls (pdb4amber, reduce, tleap, sander), got {dispatcher.execute.call_count}"

        # Verify tool names in the calls
        tool_names = [call.args[0].name for call in dispatcher.execute.call_args_list]
        expected_tools = ["pdb4amber", "reduce", "tleap", "sander"]
        assert tool_names == expected_tools, \
            f"Expected tools {expected_tools}, got {tool_names}"

        # Verify each call had a ToolCall object with proper structure
        for call in dispatcher.execute.call_args_list:
            tool_call = call.args[0]
            assert hasattr(tool_call, 'id'), "ToolCall missing 'id' attribute"
            assert hasattr(tool_call, 'name'), "ToolCall missing 'name' attribute"
            assert hasattr(tool_call, 'arguments'), "ToolCall missing 'arguments' attribute"
            assert isinstance(tool_call.arguments, dict), "ToolCall arguments must be a dict"
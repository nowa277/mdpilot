"""Unit tests for PlanGenerator with mocked LLM."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from mdpilot.coordination.plan_generator import PlanGenerator
from mdpilot.coordination.types import ExecutionPlan, PlanStep, ResourceEstimate
from mdpilot.types import LLMResponse


class TestPlanGenerator:
    """Test PlanGenerator with mocked LLM."""

    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM client."""
        llm = MagicMock()
        llm.chat_once = AsyncMock()
        return llm

    @pytest.fixture
    def mock_kb(self):
        """Create mock knowledge base."""
        kb = MagicMock()
        kb.index = {
            'categories': {
                'tools': {
                    'documents': [
                        {'id': 'pdb4amber', 'title': 'PDB4AMBER'},
                        {'id': 'tleap', 'title': 'tLEaP'},
                        {'id': 'sander', 'title': 'Sander'},
                    ]
                }
            }
        }
        kb.search = MagicMock(return_value=[
            {'id': 'protein_prep', 'title': 'Protein Preparation'},
            {'id': 'minimization', 'title': 'Energy Minimization'},
        ])
        return kb

    @pytest.fixture
    def generator(self, mock_llm, mock_kb):
        """Create PlanGenerator instance."""
        return PlanGenerator(mock_llm, mock_kb)

    @pytest.fixture
    def valid_plan_json(self):
        """Valid plan JSON response."""
        return {
            "steps": [
                {
                    "step_id": "step_1",
                    "action": "prepare_system",
                    "intent": "Clean PDB and prepare topology",
                    "parameters": {"pdb_id": "1AKI"},
                    "required_tools": ["pdb4amber", "tleap"],
                    "expected_output": "topology files",
                    "error_handling": "retry_with_backoff"
                },
                {
                    "step_id": "step_2",
                    "action": "minimize",
                    "intent": "Energy minimization",
                    "parameters": {"maxcyc": 1000},
                    "required_tools": ["sander"],
                    "expected_output": "minimized structure",
                    "error_handling": "abort"
                }
            ],
            "estimated_resources": {
                "cpu_hours": 2.0,
                "memory_gb": 4.0,
                "disk_gb": 1.0
            }
        }

    @pytest.mark.asyncio
    async def test_generate_plan_basic(self, generator, mock_llm, valid_plan_json):
        """Test basic plan generation."""
        # Mock LLM response
        mock_llm.chat_once.return_value = LLMResponse(
            content=json.dumps(valid_plan_json),
            tool_calls=[],
            finish_reason="stop"
        )

        # Generate plan
        plan = await generator.generate_plan("Prepare 1AKI for MD simulation")

        # Verify
        assert isinstance(plan, ExecutionPlan)
        assert plan.plan_id.startswith("plan_")
        assert plan.task_description == "Prepare 1AKI for MD simulation"
        assert len(plan.steps) == 2
        assert plan.steps[0].step_id == "step_1"
        assert plan.steps[0].action == "prepare_system"
        assert plan.steps[1].step_id == "step_2"
        assert plan.estimated_resources.cpu_hours == 2.0

    @pytest.mark.asyncio
    async def test_generate_plan_with_context(self, generator, mock_llm, valid_plan_json):
        """Test plan generation with context."""
        mock_llm.chat_once.return_value = LLMResponse(
            content=json.dumps(valid_plan_json),
            tool_calls=[],
            finish_reason="stop"
        )

        context = {"pdb_id": "1AKI", "force_field": "ff19SB"}
        plan = await generator.generate_plan("Run MD simulation", context)

        # Verify LLM was called with context
        call_args = mock_llm.chat_once.call_args
        messages = call_args[0][0]
        assert "Context:" in messages[0]["content"]
        assert "1AKI" in messages[0]["content"]

    @pytest.mark.asyncio
    async def test_generate_plan_without_kb(self, mock_llm, valid_plan_json):
        """Test plan generation without knowledge base."""
        generator = PlanGenerator(mock_llm, knowledge_base=None)

        mock_llm.chat_once.return_value = LLMResponse(
            content=json.dumps(valid_plan_json),
            tool_calls=[],
            finish_reason="stop"
        )

        plan = await generator.generate_plan("Test task")

        assert isinstance(plan, ExecutionPlan)
        assert len(plan.steps) == 2

    @pytest.mark.asyncio
    async def test_parse_plan_with_extra_text(self, generator, mock_llm, valid_plan_json):
        """Test parsing plan with extra text around JSON."""
        response_text = f"""Here's the plan:

{json.dumps(valid_plan_json)}

This plan should work well."""

        mock_llm.chat_once.return_value = LLMResponse(
            content=response_text,
            tool_calls=[],
            finish_reason="stop"
        )

        plan = await generator.generate_plan("Test task")

        assert isinstance(plan, ExecutionPlan)
        assert len(plan.steps) == 2

    @pytest.mark.asyncio
    async def test_parse_plan_malformed_json(self, generator, mock_llm):
        """Test error handling for malformed JSON."""
        mock_llm.chat_once.return_value = LLMResponse(
            content='{"steps": [invalid json}',
            tool_calls=[],
            finish_reason="stop"
        )

        with pytest.raises(ValueError, match="Invalid JSON"):
            await generator.generate_plan("Test task")

    @pytest.mark.asyncio
    async def test_parse_plan_no_json(self, generator, mock_llm):
        """Test error handling when no JSON in response."""
        mock_llm.chat_once.return_value = LLMResponse(
            content="Sorry, I cannot generate a plan.",
            tool_calls=[],
            finish_reason="stop"
        )

        with pytest.raises(ValueError, match="No JSON found"):
            await generator.generate_plan("Test task")

    @pytest.mark.asyncio
    async def test_parse_plan_missing_steps(self, generator, mock_llm):
        """Test error handling for missing steps field."""
        mock_llm.chat_once.return_value = LLMResponse(
            content='{"estimated_resources": {"cpu_hours": 1.0}}',
            tool_calls=[],
            finish_reason="stop"
        )

        with pytest.raises(ValueError, match="Missing 'steps'"):
            await generator.generate_plan("Test task")

    @pytest.mark.asyncio
    async def test_parse_plan_empty_steps(self, generator, mock_llm):
        """Test error handling for empty steps list."""
        mock_llm.chat_once.return_value = LLMResponse(
            content='{"steps": []}',
            tool_calls=[],
            finish_reason="stop"
        )

        with pytest.raises(ValueError, match="at least one step"):
            await generator.generate_plan("Test task")

    @pytest.mark.asyncio
    async def test_parse_plan_missing_step_fields(self, generator, mock_llm):
        """Test error handling for missing required step fields."""
        invalid_plan = {
            "steps": [
                {
                    "step_id": "step_1",
                    # Missing 'action' and 'intent'
                }
            ]
        }

        mock_llm.chat_once.return_value = LLMResponse(
            content=json.dumps(invalid_plan),
            tool_calls=[],
            finish_reason="stop"
        )

        with pytest.raises(ValueError, match="missing 'action'"):
            await generator.generate_plan("Test task")

    @pytest.mark.asyncio
    async def test_parse_plan_optional_fields(self, generator, mock_llm):
        """Test parsing plan with minimal required fields."""
        minimal_plan = {
            "steps": [
                {
                    "step_id": "step_1",
                    "action": "prepare_system",
                    "intent": "Prepare system"
                }
            ]
        }

        mock_llm.chat_once.return_value = LLMResponse(
            content=json.dumps(minimal_plan),
            tool_calls=[],
            finish_reason="stop"
        )

        plan = await generator.generate_plan("Test task")

        assert len(plan.steps) == 1
        assert plan.steps[0].parameters == {}
        assert plan.steps[0].required_tools == []
        assert plan.steps[0].expected_output == ""
        assert plan.steps[0].error_handling is None
        assert plan.estimated_resources.cpu_hours == 0.0

    @pytest.mark.asyncio
    async def test_enrich_with_knowledge(self, generator, mock_llm, mock_kb, valid_plan_json):
        """Test plan enrichment with knowledge base."""
        mock_llm.chat_once.return_value = LLMResponse(
            content=json.dumps(valid_plan_json),
            tool_calls=[],
            finish_reason="stop"
        )

        plan = await generator.generate_plan("Test task")

        # Verify KB search was called
        mock_kb.search.assert_called_once()

        # Verify plan metadata includes KB docs
        assert 'kb_docs' in plan.metadata
        assert 'protein_prep' in plan.metadata['kb_docs']

    @pytest.mark.asyncio
    async def test_build_planning_prompt_includes_kb_tools(self, generator):
        """Test that planning prompt includes KB tools."""
        prompt = generator._build_planning_prompt("Test task", {})

        assert "Available AMBER tools:" in prompt
        assert "pdb4amber" in prompt
        assert "tleap" in prompt

    @pytest.mark.asyncio
    async def test_build_planning_prompt_includes_context(self, generator):
        """Test that planning prompt includes context."""
        context = {"pdb_id": "1AKI", "force_field": "ff19SB"}
        prompt = generator._build_planning_prompt("Test task", context)

        assert "Context:" in prompt
        assert "1AKI" in prompt
        assert "ff19SB" in prompt

    @pytest.mark.asyncio
    async def test_plan_id_generation(self, generator, mock_llm, valid_plan_json):
        """Test that plan IDs are generated consistently."""
        mock_llm.chat_once.return_value = LLMResponse(
            content=json.dumps(valid_plan_json),
            tool_calls=[],
            finish_reason="stop"
        )

        plan1 = await generator.generate_plan("Same task")
        plan2 = await generator.generate_plan("Same task")

        # Same task should generate same plan ID
        assert plan1.plan_id == plan2.plan_id

        plan3 = await generator.generate_plan("Different task")

        # Different task should generate different plan ID
        assert plan3.plan_id != plan1.plan_id

    @pytest.mark.asyncio
    async def test_resource_estimate_parsing(self, generator, mock_llm):
        """Test parsing of resource estimates."""
        plan_json = {
            "steps": [
                {
                    "step_id": "step_1",
                    "action": "production",
                    "intent": "Run production MD"
                }
            ],
            "estimated_resources": {
                "cpu_hours": 24.5,
                "memory_gb": 16.0,
                "disk_gb": 50.0
            }
        }

        mock_llm.chat_once.return_value = LLMResponse(
            content=json.dumps(plan_json),
            tool_calls=[],
            finish_reason="stop"
        )

        plan = await generator.generate_plan("Test task")

        assert plan.estimated_resources.cpu_hours == 24.5
        assert plan.estimated_resources.memory_gb == 16.0
        assert plan.estimated_resources.disk_gb == 50.0

    @pytest.mark.asyncio
    async def test_multiple_steps_parsing(self, generator, mock_llm):
        """Test parsing plan with multiple steps."""
        plan_json = {
            "steps": [
                {
                    "step_id": f"step_{i}",
                    "action": f"action_{i}",
                    "intent": f"Intent {i}"
                }
                for i in range(1, 6)
            ]
        }

        mock_llm.chat_once.return_value = LLMResponse(
            content=json.dumps(plan_json),
            tool_calls=[],
            finish_reason="stop"
        )

        plan = await generator.generate_plan("Test task")

        assert len(plan.steps) == 5
        for i, step in enumerate(plan.steps, 1):
            assert step.step_id == f"step_{i}"
            assert step.action == f"action_{i}"

    @pytest.mark.asyncio
    async def test_kb_enrichment_failure_handling(self, generator, mock_llm, mock_kb, valid_plan_json):
        """Test that KB enrichment failures don't break plan generation."""
        mock_llm.chat_once.return_value = LLMResponse(
            content=json.dumps(valid_plan_json),
            tool_calls=[],
            finish_reason="stop"
        )

        # Make KB search fail
        mock_kb.search.side_effect = Exception("KB error")

        # Should still generate plan
        plan = await generator.generate_plan("Test task")

        assert isinstance(plan, ExecutionPlan)
        assert len(plan.steps) == 2

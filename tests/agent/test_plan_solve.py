# tests/agent/test_plan_solve.py
"""Tests for PlanAndSolveAgent."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mdpilot.agent.base import AgentBase
from mdpilot.agent.plan_solve import PlanAndSolveAgent
from mdpilot.config.schema import AgentConfig, AppConfig, ProviderConfig
from mdpilot.types import LLMResponse, ToolCall, ToolOutput


def _make_config(max_iterations: int = 20) -> AppConfig:
    return AppConfig(
        provider=ProviderConfig(model="test-model"),
        agent=AgentConfig(max_iterations=max_iterations),
    )


def _mock_llm_response(content: str, tool_calls=None) -> LLMResponse:
    return LLMResponse(
        content=content,
        tool_calls=tool_calls or [],
        usage_prompt_tokens=10,
        usage_completion_tokens=10,
    )


PLAN_JSON = """```json
[
    {"step_id": "s1", "action": "Clean PDB", "tool_name": "pdb4amber", "parameters": {"input": "test.pdb"}},
    {"step_id": "s2", "action": "Run prediction", "tool_name": "alphafold2_predict", "parameters": {"sequence": "MVHL"}}
]
```"""


class TestPlanAndSolveIsAgentBase:
    def test_inherits_agent_base(self):
        agent = PlanAndSolveAgent(_make_config())
        assert isinstance(agent, AgentBase)


class TestPlanGeneration:
    """Test plan generation from LLM response."""

    @pytest.mark.asyncio
    async def test_generate_plan_from_prompt(self):
        agent = PlanAndSolveAgent(_make_config())
        mock_resp = _mock_llm_response(PLAN_JSON)

        async def mock_chat_once(*args, **kwargs):
            return mock_resp

        with patch.object(agent._llm, "chat_once", side_effect=mock_chat_once):
            plan = await agent._generate_plan("Predict structure for this protein")

        assert len(plan.steps) == 2
        assert plan.steps[0].tool_name == "pdb4amber"
        assert plan.steps[1].tool_name == "alphafold2_predict"


class TestStepExecution:
    """Test step-by-step execution."""

    @pytest.mark.asyncio
    async def test_execute_plan_steps(self):
        agent = PlanAndSolveAgent(_make_config())

        plan_resp = _mock_llm_response(PLAN_JSON)
        tool_call_resp = _mock_llm_response(
            "Executing step...",
            tool_calls=[ToolCall(id="c1", name="pdb4amber", arguments={"input": "test.pdb"})],
        )
        tool_output = ToolOutput(output="cleaned.pdb")
        next_step_resp = _mock_llm_response(
            "Executing step 2...",
            tool_calls=[ToolCall(id="c2", name="alphafold2_predict", arguments={"sequence": "MVHL"})],
        )
        next_tool_output = ToolOutput(output="predicted.pdb")
        summary_resp = _mock_llm_response("Structure prediction complete. Results: ...")

        call_count = 0
        async def mock_chat_once(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return plan_resp
            elif call_count == 2:
                return tool_call_resp
            elif call_count == 3:
                return next_step_resp
            return summary_resp

        async def mock_execute(tc):
            if tc.name == "pdb4amber":
                return tool_output
            return next_tool_output

        with patch.object(agent._llm, "chat_once", side_effect=mock_chat_once), \
             patch.object(agent._dispatcher, "execute", side_effect=mock_execute):
            result = await agent.run("Predict structure")

        assert "prediction" in result.lower() or "complete" in result.lower()


class TestReplanning:
    """Test replanning on failure."""

    @pytest.mark.asyncio
    async def test_replan_on_step_failure(self):
        agent = PlanAndSolveAgent(_make_config())

        replan_json = """```json
[
    {"step_id": "s1", "action": "Retry with different params", "tool_name": "pdb4amber", "parameters": {"input": "fixed.pdb"}}
]
```"""

        plan_resp = _mock_llm_response(PLAN_JSON)
        tool_call_resp = _mock_llm_response(
            "Trying...",
            tool_calls=[ToolCall(id="c1", name="pdb4amber", arguments={"input": "test.pdb"})],
        )
        fail_output = ToolOutput(output="", success=False, error="File not found")
        replan_resp = _mock_llm_response(replan_json)
        retry_tool_resp = _mock_llm_response(
            "Retrying...",
            tool_calls=[ToolCall(id="c2", name="pdb4amber", arguments={"input": "fixed.pdb"})],
        )
        retry_output = ToolOutput(output="cleaned.pdb")
        summary_resp = _mock_llm_response("Completed after replan.")

        call_count = 0
        async def mock_chat_once(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return plan_resp
            elif call_count == 2:
                return tool_call_resp
            elif call_count == 3:
                return replan_resp
            elif call_count == 4:
                return retry_tool_resp
            return summary_resp

        async def mock_execute(tc):
            if tc.id == "c1":
                return fail_output
            return retry_output

        with patch.object(agent._llm, "chat_once", side_effect=mock_chat_once), \
             patch.object(agent._dispatcher, "execute", side_effect=mock_execute):
            result = await agent.run("Predict structure")

        assert call_count >= 4  # plan + fail + replan + retry + summary


class TestEvents:
    """Test event emission."""

    @pytest.mark.asyncio
    async def test_emits_plan_events(self):
        from mdpilot.agent.events import Event

        agent = PlanAndSolveAgent(_make_config())
        plan_resp = _mock_llm_response(PLAN_JSON)
        summary_resp = _mock_llm_response("Done.")

        events: list[Event] = []
        agent.events.on("plan_generated", lambda e: events.append(e))
        agent.events.on("plan_step_complete", lambda e: events.append(e))

        call_count = 0
        async def mock_chat_once(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return plan_resp if call_count == 1 else summary_resp

        with patch.object(agent._llm, "chat_once", side_effect=mock_chat_once):
            await agent.run("Test")

        plan_events = [e for e in events if e.type == "plan_generated"]
        assert len(plan_events) == 1


class TestPlanAndSolveSkillInjection:
    """PlanAndSolveAgent injects skill context and per-step L2."""

    @pytest.mark.asyncio
    async def test_run_injects_context_and_tool_skills(self):
        agent = PlanAndSolveAgent(_make_config())

        plan_resp = _mock_llm_response(PLAN_JSON)
        step1_resp = _mock_llm_response("Step 1 text output")
        step2_resp = _mock_llm_response("Step 2 text output")
        summary_resp = _mock_llm_response("Summary done.")

        call_count = 0
        async def mock_chat_once(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return plan_resp
            elif call_count == 2:
                return step1_resp
            elif call_count == 3:
                return step2_resp
            return summary_resp

        with patch.object(agent._skills, "build_context", return_value="## Skill: AMBER"), \
             patch.object(agent, "_inject_tool_skills", return_value="## Tool Guide: pdb4amber\nClean PDB files.") as mock_inject, \
             patch.object(agent._llm, "chat_once", side_effect=mock_chat_once):
            await agent.run("Predict structure for protein")

        mock_inject.assert_called_once_with("Predict structure for protein")
        system_msg = agent._context.messages[0]
        assert "Skill: AMBER" in system_msg["content"]
        assert "Tool Guide: pdb4amber" in system_msg["content"]

    @pytest.mark.asyncio
    async def test_execute_step_injects_per_step_skill(self):
        """_execute_step injects the specific tool's L2 into step_context."""
        agent = PlanAndSolveAgent(_make_config())

        from mdpilot.agent.plan_types import AgentPlan, PlanStep

        plan = AgentPlan(
            task="clean PDB",
            steps=[PlanStep(step_id="s1", action="Clean PDB", tool_name="pdb4amber", parameters={"input": "test.pdb"})],
        )

        from mdpilot.types import ToolMeta

        def fake_pdb4amber(input_pdb: str) -> str:
            return "cleaned.pdb"
        fake_pdb4amber._tool_meta = ToolMeta(
            name="pdb4amber",
            description="Clean PDB",
            parameters={"type": "object", "properties": {"input_pdb": {"type": "string"}}},
            skill_guide="amber/skills/pdb4amber.md",
        )
        agent._registry.register(fake_pdb4amber)

        tool_call_resp = _mock_llm_response(
            "Executing...",
            tool_calls=[ToolCall(id="c1", name="pdb4amber", arguments={"input_pdb": "test.pdb"})],
        )
        tool_output = ToolOutput(output="cleaned.pdb")

        messages_sent = []

        async def mock_chat_once(*args, **kwargs):
            messages_sent.append(kwargs.get("messages", args[0] if args else []))
            return tool_call_resp

        async def mock_execute(tc):
            return tool_output

        with patch.object(agent._llm, "chat_once", side_effect=mock_chat_once), \
             patch.object(agent._dispatcher, "execute", side_effect=mock_execute), \
             patch("mdpilot.tools.skill_loader.SkillLoader.load_l2", return_value="## PDB4AMBER Guide\nAlways check for missing residues."):
            result = await agent._execute_step(plan.steps[0], plan, [])

        assert result.success
        assert len(messages_sent) > 0
        last_messages = messages_sent[-1]
        step_user_msg = last_messages[-1]["content"]
        assert "PDB4AMBER Guide" in step_user_msg

    @pytest.mark.asyncio
    async def test_run_injects_when_no_skill_context(self):
        """Even when _inject_context returns empty, _inject_tool_skills is still called."""
        agent = PlanAndSolveAgent(_make_config())

        plan_resp = _mock_llm_response(PLAN_JSON)
        step_resp = _mock_llm_response("Step done")
        summary_resp = _mock_llm_response("Summary.")

        call_count = 0
        async def mock_chat_once(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return plan_resp
            elif call_count == 2:
                return step_resp
            return summary_resp

        with patch.object(agent._skills, "build_context", return_value=""), \
             patch.object(agent, "_inject_tool_skills", return_value="## Tool Guide: alphafold2\nPredict structures.") as mock_inject, \
             patch.object(agent._llm, "chat_once", side_effect=mock_chat_once):
            await agent.run("predict structure")

        mock_inject.assert_called_once_with("predict structure")
        system_msg = agent._context.messages[0]
        assert "Tool Guide: alphafold2" in system_msg["content"]

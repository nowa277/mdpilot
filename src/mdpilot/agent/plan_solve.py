# src/mdpilot/agent/plan_solve.py
"""PlanAndSolveAgent — plan-then-execute paradigm for multi-step workflows."""

from __future__ import annotations

import json
import re
from typing import Any

import structlog

from .base import AgentBase
from .events import ERROR, ITERATION_START, LOOP_END, TOOL_CALL, TOOL_RESULT
from .output_summarizer import summarize_tool_output
from .plan_types import AgentPlan, PlanStep, StepResult
from mdpilot.config.schema import AppConfig
from mdpilot.types import ToolCall, ToolOutput


class PlanAndSolveAgent(AgentBase):
    """Plan-and-Solve agent: generate a plan, then execute step by step.

    Suitable for multi-step workflows like AlphaFold2 prediction,
    Amber MD simulation, and complex analysis pipelines.

    Parameters
    ----------
    config : AppConfig
        Application configuration.
    max_replans : int
        Maximum number of replanning attempts on failure.
    """

    def __init__(self, config: AppConfig, max_replans: int = 1) -> None:
        super().__init__(config)
        self._max_replans = max_replans
        self._replan_count = 0

    async def run(
        self,
        prompt: str,
        stream: bool = False,
        mode: str = "agent",
        manual_queue: list[dict] | None = None,
        enabled_tools: list[str] | None = None,
        active_skills: list[str] | None = None,
    ) -> str:
        """Execute plan-and-solve loop."""
        # Inject skill and knowledge context
        injected = self._inject_context(prompt, active_skills=active_skills)
        skill_ctx = self._inject_tool_skills(prompt)
        comp_ctx = self._inject_compression_notes(prompt)

        skill_instruction = ""
        if active_skills and injected:
            skill_instruction = (
                "\n\n## Important: Pre-loaded Knowledge\n"
                "The knowledge above has been pre-loaded for this query. "
                "Use the injected content as your primary source. "
                "Only call search_knowledge or read_knowledge if the user's question "
                "covers a topic NOT addressed by the injected content.\n"
            )

        if injected or skill_ctx or comp_ctx:
            enhanced = self._build_system_prompt(active_skills=active_skills)
            if injected:
                enhanced += "\n\n" + injected
            if skill_ctx:
                enhanced += "\n\n" + skill_ctx
            if comp_ctx:
                enhanced += comp_ctx
            if skill_instruction:
                enhanced += skill_instruction
            self._context.update_system_prompt(enhanced)

        self._context.add(role="user", content=prompt)
        self._events.emit(ITERATION_START, iteration=1)

        try:
            # Phase 1: Generate plan
            plan = await self._generate_plan(prompt)
            self._events.emit("plan_generated", step_count=len(plan.steps), task=plan.task)

            # Phase 2: Execute steps
            results: list[StepResult] = []
            for step in plan.steps:
                if self._budget.iteration >= self._budget._max_iterations:
                    break

                if self._context.token_count >= self._context._max_tokens * self._compressor._trigger_ratio:
                    await self._compressor.maybe_compress(self._context)
                if self._context.token_count >= self._context._max_tokens:
                    self._context.truncate(keep_system=True)

                step.status = "running"
                result = await self._execute_step(step, plan, results)

                if result.success:
                    step.status = "completed"
                    results.append(result)
                    self._events.emit("plan_step_complete", step_id=step.step_id)
                else:
                    step.status = "failed"
                    results.append(result)

                    # Try replanning
                    if self._replan_count < self._max_replans:
                        self._replan_count += 1
                        remaining = plan.get_pending_steps()
                        if remaining:
                            new_plan = await self._replan(prompt, results, step, result.error)
                            if new_plan:
                                plan.steps.extend(new_plan.steps)
                                self._events.emit("plan_replanned", reason=result.error)
                    break

            # Phase 3: Summarize
            summary = await self._summarize(prompt, plan, results)
            self._context.add(role="assistant", content=summary)
            self._events.emit(LOOP_END, reason="plan_complete", content=summary)
            return summary

        except Exception as exc:
            self._events.emit(ERROR, message=str(exc), iteration=1)
            error_msg = f"PlanAndSolve error: {exc}"
            self._context.add(role="assistant", content=error_msg)
            return error_msg

    def _build_tool_descriptions(self) -> str:
        """Build concise tool descriptions with parameter names for plan generation."""
        parts = []
        for name in self._registry.list_tools():
            entry = self._registry.get(name)
            if entry is None:
                continue
            meta, _ = entry
            params = list(meta.parameters.get("properties", {}).keys())
            parts.append(f"- {name}({', '.join(params)}): {meta.description}")
        return "\n".join(parts)

    async def _generate_plan(self, prompt: str) -> AgentPlan:
        """Ask LLM to generate an execution plan."""
        plan_prompt = (
            "Given the following task, create a step-by-step execution plan.\n"
            "Each step should have: step_id, action, tool_name, parameters, expected_output.\n"
            "CRITICAL: Use EXACT parameter names shown in the tool signatures below. "
            "Do NOT invent parameter names.\n"
            "Respond ONLY with a JSON array of steps, wrapped in ```json ... ```.\n\n"
            f"Task: {prompt}\n\n"
            f"Available tools:\n{self._build_tool_descriptions()}\n"
        )

        messages = self._context.messages + [{"role": "user", "content": plan_prompt}]
        response = await self._llm_caller.call(messages=messages, tools=[])
        steps = self._parse_plan_json(response.content)

        return AgentPlan(task=prompt, steps=steps)

    def _parse_plan_json(self, text: str) -> list[PlanStep]:
        """Extract plan steps from LLM response."""
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if not json_match:
            json_match = re.search(r"\[.*\]", text, re.DOTALL)

        if not json_match:
            return []

        try:
            raw_steps = json.loads(json_match.group(1) if json_match.lastindex else json_match.group(0))
        except json.JSONDecodeError:
            return []

        steps = []
        for i, s in enumerate(raw_steps):
            steps.append(PlanStep(
                step_id=s.get("step_id", f"step_{i+1}"),
                action=s.get("action", ""),
                tool_name=s.get("tool_name", "bash"),
                parameters=s.get("parameters", {}),
                expected_output=s.get("expected_output", ""),
            ))
        return steps

    async def _execute_step(
        self,
        step: PlanStep,
        plan: AgentPlan,
        completed: list[StepResult],
    ) -> StepResult:
        """Execute a single plan step via LLM tool calling."""
        # Build completed results with actual output for context passing
        completed_text = ""
        for r in completed:
            if r.success:
                completed_text += f"- {r.step_id}: completed — {r.output[:500]}\n"
            else:
                completed_text += f"- {r.step_id}: failed — {r.error or 'unknown error'}\n"

        # Include tool schema hints for the target tool
        tool_hint = ""
        skill_hint = ""
        entry = self._registry.get(step.tool_name)
        if entry:
            meta, _ = entry
            params = list(meta.parameters.get("properties", {}).keys())
            tool_hint = f"\nExpected parameters: {', '.join(params)}\n"
            # Per-step L2 skill injection
            if meta.skill_guide:
                try:
                    from mdpilot.tools.skill_loader import SkillLoader
                    l2 = SkillLoader.load_l2(meta.skill_guide)
                    if l2:
                        skill_hint = f"\n\n## Tool Guide for {step.tool_name}\n{l2}\n"
                except Exception:
                    pass

        step_context = (
            f"Executing step: {step.action}\n"
            f"Tool: {step.tool_name}{tool_hint}"
            f"Suggested parameters: {json.dumps(step.parameters)}\n"
            f"Completed so far:\n{completed_text}\n"
            "Call the appropriate tool now with the correct parameters. "
            "Use EXACT parameter names from the tool schema."
            f"{skill_hint}"
        )

        messages = self._context.messages + [{"role": "user", "content": step_context}]
        response = await self._llm_caller.call(
            messages=messages,
            tools=self._registry.schemas(),
        )

        if not response.tool_calls:
            return StepResult(
                step_id=step.step_id,
                success=True,
                output=response.content,
            )

        # Execute tool calls
        results_text = []
        all_success = True
        for tc in response.tool_calls:
            self._events.emit(TOOL_CALL, name=tc.name, id=tc.id, arguments=tc.arguments)
            output: ToolOutput = await self._dispatcher.execute(tc)

            if output.success:
                content = summarize_tool_output(output.output)
            else:
                content = f"Error: {output.error}"
                all_success = False

            self._events.emit(
                TOOL_RESULT,
                name=tc.name,
                tool_call_id=tc.id,
                output=output.output if output.success else output.error or "",
                success=output.success,
            )
            results_text.append(f"[{tc.name}] {content}")

        combined = "\n".join(results_text)
        self._context.add(role="assistant", content=combined)
        self._budget.increment()

        return StepResult(
            step_id=step.step_id,
            success=all_success,
            output=combined,
            tool_call_id=response.tool_calls[0].id if response.tool_calls else "",
        )

    async def _replan(
        self,
        original_prompt: str,
        completed: list[StepResult],
        failed_step: PlanStep,
        error: str | None,
    ) -> AgentPlan | None:
        """Replan remaining steps after a failure."""
        replan_prompt = (
            f"Original task: {original_prompt}\n"
            f"Completed steps:\n"
            + "\n".join(f"  - {r.step_id}: {r.output[:200]}" for r in completed if r.success)
            + f"\nFailed step: {failed_step.action} — Error: {error}\n"
            "Generate a new plan for the remaining work. "
            "Respond ONLY with a JSON array of steps in ```json ... ```."
        )

        messages = self._context.messages + [{"role": "user", "content": replan_prompt}]
        response = await self._llm_caller.call(messages=messages, tools=[])
        steps = self._parse_plan_json(response.content)

        if not steps:
            return None
        return AgentPlan(task=f"Replan: {original_prompt}", steps=steps)

    async def _summarize(
        self,
        prompt: str,
        plan: AgentPlan,
        results: list[StepResult],
    ) -> str:
        """Generate final summary of plan execution."""
        completed = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        summary_prompt = (
            f"Task: {prompt}\n\n"
            f"Plan had {len(plan.steps)} steps.\n"
            f"Completed: {len(completed)}, Failed: {len(failed)}\n\n"
            "Results:\n"
            + "\n".join(f"  Step {r.step_id}: {r.output[:300]}" for r in results)
            + "\n\nProvide a concise summary of what was accomplished."
        )

        messages = self._context.messages + [{"role": "user", "content": summary_prompt}]
        response = await self._llm_caller.call(messages=messages, tools=[])
        return response.content

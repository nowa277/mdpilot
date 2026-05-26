"""ReActAgent — ReAct paradigm agent inheriting AgentBase."""

from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Optional

import structlog

from mdpilot.config.schema import AppConfig
from mdpilot.types import LLMChunk, LLMResponse, ToolCall, ToolOutput

from .base import AgentBase
from .events import ERROR, ITERATION_START, LOOP_END, LLM_RESPONSE, TOOL_CALL, TOOL_RESULT, PROGRESS_UPDATE
from .output_summarizer import summarize_tool_output

from mdpilot.coordination import (
    PlanGenerator,
    PlanValidator,
    ExecutionPlanner,
    ToolExecutor,
    GuardrailConfig,
    ResourceGuard,
    ExecutionStatus,
)


class ReActAgent(AgentBase):
    """ReAct (Reason + Act) agent for the AMBER platform.

    Parameters
    ----------
    config : AppConfig
        Application configuration.
    use_coordination : bool
        Whether to enable the coordination layer (planner + executor).
    """

    def __init__(self, config: AppConfig, use_coordination: bool = False) -> None:
        super().__init__(config)
        self._use_coordination = use_coordination

        # Coordination layer (optional)
        self._plan_generator: Optional[PlanGenerator] = None
        self._plan_validator: Optional[PlanValidator] = None
        self._execution_planner: Optional[ExecutionPlanner] = None
        self._tool_executor: Optional[ToolExecutor] = None

        if use_coordination:
            self._init_coordination_layer()

    @property
    def use_coordination(self) -> bool:
        return self._use_coordination

    # ------------------------------------------------------------------
    # Coordination layer initialization
    # ------------------------------------------------------------------

    def _init_coordination_layer(self) -> None:
        """Initialize coordination layer components."""
        try:
            from mdpilot.tools.builtin.knowledge import _get_knowledge_system
            kb, _ = _get_knowledge_system()
        except Exception:
            kb = None

        guardrail_config = GuardrailConfig()
        self._plan_generator = PlanGenerator(self._llm, kb)
        self._plan_validator = PlanValidator(guardrail_config)
        self._execution_planner = ExecutionPlanner(self._registry, kb)

        from mdpilot.coordination.config import ResourceLimits
        resource_limits = ResourceLimits(
            max_cpu_hours=10.0,
            max_memory_gb=16.0,
            max_disk_gb=50.0,
        )
        resource_guard = ResourceGuard(resource_limits)
        self._tool_executor = ToolExecutor(self._dispatcher, resource_guard)

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def run(
        self,
        prompt: str,
        stream: bool = False,
        mode: str = "agent",
        manual_queue: list[dict] | None = None,
        enabled_tools: list[str] | None = None,
    ) -> str:
        if self._use_coordination:
            return await self._run_with_coordination(prompt, stream)
        else:
            return await self._run_legacy(prompt, stream)

    # ------------------------------------------------------------------
    # Coordination path
    # ------------------------------------------------------------------

    async def _run_with_coordination(self, prompt: str, stream: bool = False) -> str:
        injected = self._inject_context(prompt, active_skills=getattr(self, '_active_skills', None))
        skill_ctx = self._inject_tool_skills(prompt)
        if injected or skill_ctx:
            enhanced = self._build_system_prompt()
            if injected:
                enhanced += "\n\n" + injected
            if skill_ctx:
                enhanced += "\n\n" + skill_ctx
            self._context.update_system_prompt(enhanced)

        self._context.add(role="user", content=prompt)

        try:
            self._events.emit(ITERATION_START, iteration=1)
            plan = await self._plan_generator.generate_plan(prompt)

            validation = self._plan_validator.validate(plan)
            if not validation.valid:
                violations_text = "\n".join(
                    f"- [{v.level}] {v.severity.value}: {v.message} (step: {v.step_id})"
                    for v in validation.violations
                )
                error_msg = f"Plan validation failed:\n{violations_text}"
                fixes = self._plan_validator.suggest_fixes(validation.violations)
                if fixes:
                    fixes_text = "\n".join(
                        f"- {f['step_id']}: {f['fix']}" for f in fixes
                    )
                    error_msg += f"\n\nSuggested fixes:\n{fixes_text}"
                self._context.add(role="assistant", content=error_msg)
                self._events.emit(LOOP_END, reason="validation_failed", content=error_msg)
                return error_msg

            sequence = self._execution_planner.plan_execution(plan)
            result = await self._tool_executor.execute(sequence)

            if result.status == ExecutionStatus.SUCCESS:
                output_parts = []
                for i, tool_result in enumerate(result.results):
                    output_parts.append(
                        f"Step {i+1}: {tool_result.message}\n"
                        f"Output: {summarize_tool_output(tool_result.output)}"
                    )
                final_output = "\n\n".join(output_parts)
                self._context.add(role="assistant", content=final_output)
                self._events.emit(LOOP_END, reason="success", content=final_output)
                return final_output
            elif result.status == ExecutionStatus.RESOURCE_EXHAUSTED:
                error_msg = f"Resource exhausted: {result.error}"
                self._context.add(role="assistant", content=error_msg)
                self._events.emit(LOOP_END, reason="resource_exhausted", content=error_msg)
                return error_msg
            else:
                error_msg = f"Execution failed: {result.error}"
                self._context.add(role="assistant", content=error_msg)
                self._events.emit(LOOP_END, reason="execution_failed", content=error_msg)
                return error_msg

        except Exception as exc:
            self._events.emit(ERROR, message=str(exc), iteration=1)
            error_msg = f"Coordination error: {exc}"
            self._context.add(role="assistant", content=error_msg)
            return error_msg

    # ------------------------------------------------------------------
    # Legacy path
    # ------------------------------------------------------------------

    async def _run_legacy(self, prompt: str, stream: bool = False) -> str:
        injected = self._inject_context(prompt, active_skills=getattr(self, '_active_skills', None))
        skill_ctx = self._inject_tool_skills(prompt)
        comp_ctx = self._inject_compression_notes(prompt)
        if injected or skill_ctx or comp_ctx:
            enhanced = self._build_system_prompt()
            if injected:
                enhanced += "\n\n" + injected
            if skill_ctx:
                enhanced += "\n\n" + skill_ctx
            if comp_ctx:
                enhanced += comp_ctx
            self._context.update_system_prompt(enhanced)

        self._context.add(role="user", content=prompt)
        self._logger.info("react_loop_start", prompt_length=len(prompt), max_iterations=self._budget._max_iterations)

        self._progress.update(0, "starting")
        self._events.emit(PROGRESS_UPDATE, percentage=0.0, stage="starting", iteration=0)

        while self._budget.can_continue():
            self._budget.increment()
            iteration = self._budget.iteration

            self._progress.update(iteration, f"iteration_{iteration}")
            if self._progress.percentage is not None:
                self._events.emit(
                    PROGRESS_UPDATE,
                    percentage=self._progress.percentage,
                    stage=self._progress.stage,
                    iteration=iteration,
                )

            self._events.emit(ITERATION_START, iteration=iteration)

            if self._context.token_count >= self._context._max_tokens * self._compressor._trigger_ratio:
                await self._compressor.maybe_compress(self._context)
            if self._context.token_count >= self._context._max_tokens:
                self._context.truncate(keep_system=True)

            try:
                if stream:
                    stream_gen = await self._llm.chat(
                        messages=self._context.messages,
                        tools=self._registry.schemas(),
                        stream=True,
                    )
                    final_content, stream_tool_calls = await self._consume_stream(stream_gen)
                    has_tool_calls = bool(stream_tool_calls)
                    if not has_tool_calls:
                        self._context.add(role="assistant", content=final_content)
                        self._events.emit(LOOP_END, reason="final_answer", content=final_content)
                        return final_content
                    response_tool_calls = stream_tool_calls
                else:
                    response = await self._llm_caller.call(
                        messages=self._context.messages,
                        tools=self._registry.schemas(),
                    )
                    final_content = response.content
                    response_tool_calls = response.tool_calls
                    has_tool_calls = bool(response_tool_calls)

                if not has_tool_calls:
                    self._context.add(role="assistant", content=final_content)
                    self._logger.info("react_loop_end", reason="final_answer", iterations=self._budget.iteration)
                    self._events.emit(LOOP_END, reason="final_answer", content=final_content)
                    return final_content

                # Execute tool calls
                self._context.add(
                    role="assistant",
                    content=final_content or "",
                    tool_calls=[
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.name, "arguments": json.dumps(tc.arguments if isinstance(tc.arguments, dict) else (tc.arguments if isinstance(tc.arguments, str) else str(tc.arguments)))},
                        }
                        for tc in response_tool_calls
                    ],
                )

                for tc in response_tool_calls:
                    self._events.emit(TOOL_CALL, name=tc.name, id=tc.id, arguments=tc.arguments)
                    output = await self._dispatcher.execute(tc)

                    if output.success:
                        result_content = summarize_tool_output(output.output)
                    else:
                        result_content = f"Error: {output.error}"
                        if output.error_suggestion:
                            result_content += f"\n\n💡 Suggestion: {output.error_suggestion}"

                    self._events.emit(
                        TOOL_RESULT,
                        name=tc.name,
                        tool_call_id=tc.id,
                        output=output.output if output.success else output.error or "",
                        success=output.success,
                    )
                    self._context.add(
                        role="tool",
                        content=result_content,
                        tool_call_id=tc.id,
                    )

            except Exception as exc:
                self._logger.error("react_loop_error", error=str(exc), error_type=type(exc).__name__, iteration=self._budget.iteration)
                self._events.emit(ERROR, message=str(exc), iteration=self._budget.iteration)
                self._context.add(role="assistant", content=f"[Error occurred: {exc}]")
                break

        summary = self._build_budget_exceeded_summary()
        self._logger.info("react_loop_end", reason="budget_exhausted", iterations=self._budget.iteration)
        self._events.emit(LOOP_END, reason="budget_exhausted", summary=summary)
        return summary

    # ------------------------------------------------------------------
    # Streaming helper
    # ------------------------------------------------------------------

    async def _consume_stream(
        self,
        stream: AsyncGenerator[LLMChunk, None],
    ) -> tuple[str, list[ToolCall]]:
        import json as _json

        content_parts: list[str] = []
        tc_accum: dict[str, dict] = {}

        async for chunk in stream:
            content_parts.append(chunk.content)

            if chunk.tool_calls:
                for tc in chunk.tool_calls:
                    tc_key = tc.id or ""
                    if not tc_key:
                        for existing_key, existing in tc_accum.items():
                            if existing.get("name") == tc.name or (not tc.name and existing.get("name")):
                                tc_key = existing_key
                                break
                        if not tc_key:
                            continue

                    if tc_key not in tc_accum:
                        tc_accum[tc_key] = {"id": tc.id, "name": tc.name, "raw_args": ""}

                    entry = tc_accum[tc_key]
                    if tc.name:
                        entry["name"] = tc.name
                    args = tc.arguments or {}
                    raw = args.get("__streaming_raw__")
                    if raw:
                        entry["raw_args"] += raw
                    elif args and "__streaming_raw__" not in args:
                        entry["args_parsed"] = args

            self._events.emit(LLM_RESPONSE, content=chunk.content, finish_reason=chunk.finish_reason)

        full_content = "".join(content_parts)

        tool_calls: list[ToolCall] = []
        for _key, entry in tc_accum.items():
            if "args_parsed" in entry:
                arguments = entry["args_parsed"]
            else:
                raw = entry["raw_args"].strip()
                if raw:
                    try:
                        arguments = _json.loads(raw)
                    except _json.JSONDecodeError:
                        arguments = {"__streaming_raw__": raw}
                else:
                    arguments = {}
            tool_calls.append(ToolCall(id=entry["id"], name=entry["name"], arguments=arguments))

        return full_content, tool_calls

    # ------------------------------------------------------------------
    # Budget summary
    # ------------------------------------------------------------------

    def _build_budget_exceeded_summary(self) -> str:
        return (
            f"Budget exceeded after {self._budget.iteration} iteration(s). "
            f"Remaining: {self._budget.remaining} iterations. "
            "Consider simplifying your query or increasing budget limits."
        )


# Backward compatibility alias
ReActLoop = ReActAgent

"""ReflectionAgent — execute → critique → revise paradigm."""

from __future__ import annotations

import structlog

from mdpilot.config.schema import AppConfig

from .base import AgentBase
from .events import ERROR, ITERATION_START, LOOP_END
from .output_summarizer import summarize_tool_output


_SATISFACTION_PATTERNS = ["SATISFIED", "satisfied", " satisfactory ", " no improvement needed"]


def _is_satisfied(critique: str) -> bool:
    return any(p in critique for p in _SATISFACTION_PATTERNS)


_EXECUTE_PROMPT_TEMPLATE = (
    "Execute the following task and provide your best result.\n\n"
    "Task: {task}\n\n"
    "Provide a thorough initial result."
)

_CRITIQUE_PROMPT_TEMPLATE = (
    "You are a critical reviewer. Evaluate the following result for the given task.\n\n"
    "Task: {task}\n\n"
    "Result to evaluate:\n{result}\n\n"
    "If the result is satisfactory and needs no improvement, respond with 'SATISFIED' "
    "followed by a brief explanation.\n"
    "If the result needs improvement, respond with 'NEEDS_IMPROVEMENT' followed by "
    "specific suggestions for how to improve it."
)

_REVISE_PROMPT_TEMPLATE = (
    "Revise the following result based on the critique feedback.\n\n"
    "Task: {task}\n\n"
    "Previous result:\n{result}\n\n"
    "Critique feedback:\n{critique}\n\n"
    "Provide an improved result addressing the feedback."
)


class ReflectionAgent(AgentBase):
    """Reflection agent: execute, critique, and iteratively refine results.

    Parameters
    ----------
    config : AppConfig
        Application configuration.
    max_reflections : int
        Maximum number of critique-revise cycles.
    """

    def __init__(self, config: AppConfig, max_reflections: int = 3) -> None:
        super().__init__(config)
        self._max_reflections = max_reflections

    async def run(
        self,
        prompt: str,
        stream: bool = False,
        mode: str = "agent",
        manual_queue: list[dict] | None = None,
        enabled_tools: list[str] | None = None,
        active_skills: list[str] | None = None,
    ) -> str:
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

        try:
            current_result = await self._initial_execute(prompt)
            self._budget.increment()

            for i in range(1, self._max_reflections + 1):
                self._events.emit(ITERATION_START, iteration=i)

                critique = await self._critique(prompt, current_result)
                self._budget.increment()

                if _is_satisfied(critique):
                    self._context.add(role="assistant", content=current_result)
                    self._events.emit(LOOP_END, reason="satisfied", content=current_result, iterations=i)
                    return current_result

                revised = await self._revise(prompt, current_result, critique)
                self._budget.increment()
                current_result = revised

            self._context.add(role="assistant", content=current_result)
            self._events.emit(
                LOOP_END, reason="max_reflections_reached",
                content=current_result, iterations=self._max_reflections,
            )
            return current_result

        except Exception as exc:
            self._events.emit(ERROR, message=str(exc), iteration=self._budget.iteration)
            error_msg = f"ReflectionAgent error: {exc}"
            self._context.add(role="assistant", content=error_msg)
            return error_msg

    async def _initial_execute(self, task: str) -> str:
        execute_prompt = _EXECUTE_PROMPT_TEMPLATE.format(task=task)
        messages = self._context.messages + [{"role": "user", "content": execute_prompt}]
        response = await self._llm_caller.call(
            messages=messages,
            tools=self._registry.schemas(),
        )

        if not response.tool_calls:
            return response.content

        results = []
        for tc in response.tool_calls:
            self._events.emit("tool_call", name=tc.name, id=tc.id, arguments=tc.arguments)
            output = await self._dispatcher.execute(tc)
            content = summarize_tool_output(output.output) if output.success else f"Error: {output.error}"
            self._events.emit(
                "tool_result",
                name=tc.name, tool_call_id=tc.id,
                output=output.output if output.success else output.error or "",
                success=output.success,
            )
            results.append(f"[{tc.name}] {content}")

        return "\n".join(results)

    async def _critique(self, task: str, result: str) -> str:
        critique_prompt = _CRITIQUE_PROMPT_TEMPLATE.format(task=task, result=result)
        messages = self._context.messages + [{"role": "user", "content": critique_prompt}]
        response = await self._llm_caller.call(messages=messages, tools=[])
        return response.content

    async def _revise(self, task: str, result: str, critique: str) -> str:
        revise_prompt = _REVISE_PROMPT_TEMPLATE.format(task=task, result=result, critique=critique)
        messages = self._context.messages + [{"role": "user", "content": revise_prompt}]
        response = await self._llm_caller.call(messages=messages, tools=[])
        return response.content

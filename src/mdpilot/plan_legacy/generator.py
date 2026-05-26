"""Plan generator — LLM-driven plan creation from a user goal."""

from __future__ import annotations

import json
import textwrap

from mdpilot.llm.provider import LLMProvider
from mdpilot.plan_legacy.schema import Plan, PlanStep
from mdpilot.tools.registry import ToolRegistry


class PlanGenerationError(Exception):
    """Raised when plan generation fails."""
    pass


class PlanGenerator:
    """Generates execution plans from natural language goals.

    Parameters
    ----------
    provider : LLMProvider
        LLM provider for making the generation call.
    tool_registry : ToolRegistry
        Registry to validate tool names against.
    """

    def __init__(
        self,
        provider: LLMProvider,
        tool_registry: ToolRegistry,
    ) -> None:
        self._provider = provider
        self._registry = tool_registry

    async def generate(self, goal: str) -> Plan:
        """Generate a plan for the given goal.

        Parameters
        ----------
        goal : str
            The user's high-level task description.

        Returns
        -------
        Plan
            A validated plan with resolved tool references.

        Raises
        ------
        PlanGenerationError
            If the LLM fails to produce a valid plan or tool references are invalid.
        """
        system_prompt = self._build_system_prompt()
        user_message = self._build_user_message(goal)

        response = await self._provider.chat_once(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            tools=None,
        )

        raw_content = response.content.strip()

        # Attempt to extract JSON from markdown code blocks if present
        raw_content = self._strip_code_fences(raw_content)

        # Extract the first JSON object from the response, ignoring trailing text
        raw_content = self._extract_json_object(raw_content)

        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            raise PlanGenerationError(
                f"LLM returned invalid JSON: {exc}\nContent:\n{raw_content[:500]}"
            ) from exc

        plan = self._parse_and_validate(parsed, goal)
        return plan

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_system_prompt(self) -> str:
        """Compose the system prompt that instructs the LLM on plan format."""
        tool_names = self._registry.list_tools()
        tool_schemas = self._registry.schemas()

        schema_lines: list[str] = []
        for s in tool_schemas:
            fn = s.get("function", {})
            schema_lines.append(
                f"  - {fn['name']}: {fn['description']}"
            )

        tool_list = "\n".join(schema_lines) if schema_lines else "  (no tools registered)"

        return textwrap.dedent(f"""\
            You are a planning agent that decomposes user goals into executable step plans.

            ## Rules
            1. Decompose the goal into the smallest meaningful steps.
            2. Each step must use exactly ONE tool.
            3. Steps must be listed in execution order.
            4. Use `depends_on` to express dependencies between steps (list step IDs, not names).
              - Step IDs are assigned sequentially starting from 1 in the order you list them.
              - If step A must complete before step B, step B's `depends_on` includes step A's ID.
            5. Only use tools that are listed below.

            ## Available tools
            {tool_list}

            ## Response format
            Respond ONLY with a valid JSON object conforming to this schema:
            {{
              "goal": "<string: restate the user goal>",
              "steps": [
                {{
                  "description": "<string: what this step does>",
                  "tool": "<string: tool name>",
                  "arguments": {{ <key-value pairs> }},
                  "depends_on": [<int: list of step IDs this depends on>]
                }}
              ],
              "estimated_time": "<string: optional time estimate>"
            }}

            Do not include any explanatory text outside the JSON.
        """)

    def _build_user_message(self, goal: str) -> str:
        """Build the user message containing the goal."""
        return f"Generate a plan for the following goal:\n\n{goal}"

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """Strip markdown code fences from JSON text."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            # Remove first line (```json or ```)
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            # Remove last line (```)
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines)
        return text.strip()

    @staticmethod
    def _extract_json_object(text: str) -> str:
        """Extract the first complete JSON object from text, ignoring trailing content.

        LLMs often append explanatory text after the JSON response.
        This method finds the first ``{`` and matches its closing ``}`` using
        a simple brace-depth counter, handling nested objects and strings.
        """
        start = text.find("{")
        if start == -1:
            return text

        depth = 0
        in_string = False
        escape = False

        for i in range(start, len(text)):
            ch = text[i]

            if escape:
                escape = False
                continue

            if ch == "\\":
                if in_string:
                    escape = True
                continue

            if ch == '"':
                in_string = not in_string
                continue

            if in_string:
                continue

            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]

        # No matching closing brace found — return original
        return text

    def _parse_and_validate(self, parsed: dict, original_goal: str) -> Plan:
        """Parse the LLM JSON into a Plan, validating tool references."""
        try:
            goal = parsed.get("goal", original_goal)
            raw_steps = parsed.get("steps", [])
        except Exception as exc:
            raise PlanGenerationError(f"Failed to parse plan structure: {exc}") from exc

        if not isinstance(raw_steps, list):
            raise PlanGenerationError("Plan 'steps' must be a list")

        steps: list[PlanStep] = []
        for i, raw_step in enumerate(raw_steps, start=1):
            try:
                step = PlanStep(
                    id=i,
                    description=raw_step.get("description", ""),
                    tool=raw_step.get("tool", ""),
                    arguments=raw_step.get("arguments", {}),
                    depends_on=raw_step.get("depends_on", []),
                    status="pending",
                )
                steps.append(step)
            except Exception as exc:
                raise PlanGenerationError(
                    f"Failed to parse step {i}: {exc}"
                ) from exc

        plan = Plan(goal=goal, steps=steps, estimated_time=parsed.get("estimated_time"))

        # Validate tool names
        available_tools = set(self._registry.list_tools())
        for step in plan.steps:
            if step.tool not in available_tools:
                raise PlanGenerationError(
                    f"Step {step.id} references unknown tool '{step.tool}'. "
                    f"Available tools: {sorted(available_tools)}"
                )

        # Validate dependency references
        step_ids = {s.id for s in plan.steps}
        for step in plan.steps:
            for dep_id in step.depends_on:
                if dep_id not in step_ids:
                    raise PlanGenerationError(
                        f"Step {step.id} depends on non-existent step ID {dep_id}"
                    )

        return plan

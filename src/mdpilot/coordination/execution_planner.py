"""Execution planning - translates high-level plans to tool sequences."""

from typing import Any, Dict, List, Optional

from mdpilot.coordination.types import (
    ExecutionPlan,
    ExecutionSequence,
    PlanStep,
    ToolCall,
)


class ExecutionPlanner:
    """Translates execution plans to tool call sequences."""

    def __init__(self, tool_registry: Any = None, knowledge_base: Any = None):
        """Initialize execution planner.

        Args:
            tool_registry: Registry of available tools
            knowledge_base: Knowledge base for tool lookup
        """
        self.tool_registry = tool_registry
        self.kb = knowledge_base

    def plan_execution(self, plan: ExecutionPlan) -> ExecutionSequence:
        """Translate plan to tool call sequence.

        Args:
            plan: Validated execution plan

        Returns:
            ExecutionSequence with concrete tool calls
        """
        all_calls = []

        for step in plan.steps:
            # Translate step to tool calls
            tool_calls = self._translate_step(step)
            all_calls.extend(tool_calls)

        return ExecutionSequence(plan_id=plan.plan_id, calls=all_calls)

    def _translate_step(self, step: PlanStep) -> List[ToolCall]:
        """Translate single step to tool calls.

        Args:
            step: Plan step to translate

        Returns:
            List of tool calls for this step
        """
        calls = []

        # Use required_tools from step
        for tool_name in step.required_tools:
            tool_call = ToolCall(
                tool_name=tool_name,
                parameters=self._map_parameters(step, tool_name),
                metadata={
                    "step_id": step.step_id,
                    "action": step.action,
                    "intent": step.intent,
                },
            )
            calls.append(tool_call)

        # If no tools specified, infer from action
        if not step.required_tools:
            tool_call = self._infer_tool_from_action(step)
            if tool_call:
                calls.append(tool_call)

        return calls

    def _map_parameters(self, step: PlanStep, tool_name: str) -> Dict[str, Any]:
        """Map step parameters to tool parameters.

        Args:
            step: Plan step with parameters
            tool_name: Target tool name

        Returns:
            Mapped parameters for the tool
        """
        # Start with step parameters
        params = dict(step.parameters)

        # Add common parameter mappings
        if "input_file" not in params and "input" in step.parameters:
            params["input_file"] = step.parameters["input"]

        if "output_file" not in params and "output" in step.parameters:
            params["output_file"] = step.parameters["output"]

        return params

    def _infer_tool_from_action(self, step: PlanStep) -> Optional[ToolCall]:
        """Infer tool from action name.

        Args:
            step: Plan step with action

        Returns:
            Inferred tool call or None
        """
        # Map common actions to tools
        action_to_tool = {
            "prepare_system": "pdb4amber",
            "minimize": "sander",
            "equilibrate": "sander",
            "production": "pmdrun",
            "analyze": "cpptraj",
            "build_topology": "tleap",
            "clean_pdb": "pdb4amber",
            "add_hydrogens": "reduce",
            "solvate": "tleap",
            "add_ions": "tleap",
        }

        tool_name = action_to_tool.get(step.action)
        if tool_name:
            return ToolCall(
                tool_name=tool_name,
                parameters=step.parameters,
                metadata={
                    "step_id": step.step_id,
                    "action": step.action,
                    "intent": step.intent,
                    "inferred": True,
                },
            )
        return None

"""LLM-driven plan generation."""

import json
import logging
from typing import Any, Dict, List, Optional

from mdpilot.coordination.types import ExecutionPlan, PlanStep, ResourceEstimate

logger = logging.getLogger(__name__)


class PlanGenerator:
    """Generates execution plans using LLM."""

    def __init__(self, llm_client: Any, knowledge_base: Any = None):
        """Initialize plan generator.

        Args:
            llm_client: LLM client for plan generation
            knowledge_base: Knowledge base for context (optional)
        """
        self.llm = llm_client
        self.kb = knowledge_base

    async def generate_plan(
        self,
        task: str,
        context: Dict[str, Any] = None
    ) -> ExecutionPlan:
        """Generate high-level execution plan.

        Args:
            task: Natural language task description
            context: Current workflow context

        Returns:
            ExecutionPlan with steps and resource estimates
        """
        context = context or {}

        logger.info(f"Generating plan for task: {task}")

        # Build prompt
        prompt = self._build_planning_prompt(task, context)

        # Call LLM
        messages = [{"role": "user", "content": prompt}]
        response = await self.llm.chat_once(messages)

        logger.debug(f"LLM response: {response.content[:200]}...")

        # Parse response
        plan = self._parse_plan(response.content, task)

        # Enrich with KB
        if self.kb:
            plan = self._enrich_with_knowledge(plan)

        logger.info(f"Generated plan {plan.plan_id} with {len(plan.steps)} steps")

        return plan

    def _build_planning_prompt(self, task: str, context: Dict[str, Any]) -> str:
        """Build LLM prompt for planning."""
        kb_summary = ""
        if self.kb:
            # Get available tools from KB
            try:
                tools = self._get_kb_tools()
                if tools:
                    kb_summary = f"\n\nAvailable AMBER tools: {', '.join(tools)}"
            except Exception as e:
                logger.warning(f"Failed to get KB tools: {e}")

        context_str = ""
        if context:
            context_str = f"\n\nContext: {json.dumps(context, indent=2)}"

        return f"""Generate an execution plan for this AMBER molecular dynamics task:

Task: {task}
{context_str}{kb_summary}

Return a JSON plan with this exact structure:
{{
  "steps": [
    {{
      "step_id": "step_1",
      "action": "prepare_system",
      "intent": "Clean PDB and prepare topology",
      "parameters": {{}},
      "required_tools": ["pdb4amber", "tleap"],
      "expected_output": "topology files",
      "error_handling": "retry_with_backoff"
    }}
  ],
  "estimated_resources": {{
    "cpu_hours": 2.0,
    "memory_gb": 4.0,
    "disk_gb": 1.0
  }}
}}

Guidelines:
- Use descriptive step_ids (step_1, step_2, etc.)
- action should be one of: prepare_system, build_topology, minimize, equilibrate, production, analyze
- intent should explain what this step accomplishes
- required_tools should list AMBER tools needed (pdb4amber, tleap, sander, pmemd, cpptraj, etc.)
- error_handling can be: retry_with_backoff, skip, abort, fallback
- Estimate resources realistically based on system size

Return ONLY the JSON, no additional text."""

    def _parse_plan(self, response: str, task: str) -> ExecutionPlan:
        """Parse LLM response into ExecutionPlan."""
        # Extract JSON from response
        json_start = response.find('{')
        json_end = response.rfind('}') + 1

        if json_start == -1 or json_end == 0:
            raise ValueError("No JSON found in LLM response")

        json_str = response[json_start:json_end]

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            logger.error(f"JSON string: {json_str}")
            raise ValueError(f"Invalid JSON in LLM response: {e}")

        # Validate required fields
        if "steps" not in data:
            raise ValueError("Missing 'steps' field in plan")

        if not isinstance(data["steps"], list) or len(data["steps"]) == 0:
            raise ValueError("Plan must have at least one step")

        # Build steps
        steps = []
        for i, s in enumerate(data["steps"]):
            if not isinstance(s, dict):
                raise ValueError(f"Step {i} is not a dictionary")

            # Validate required step fields
            if "step_id" not in s:
                raise ValueError(f"Step {i} missing 'step_id'")
            if "action" not in s:
                raise ValueError(f"Step {i} missing 'action'")
            if "intent" not in s:
                raise ValueError(f"Step {i} missing 'intent'")

            steps.append(PlanStep(
                step_id=s['step_id'],
                action=s['action'],
                intent=s['intent'],
                parameters=s.get('parameters', {}),
                required_tools=s.get('required_tools', []),
                expected_output=s.get('expected_output', ''),
                error_handling=s.get('error_handling')
            ))

        # Build resource estimate
        res = data.get('estimated_resources', {})
        resources = ResourceEstimate(
            cpu_hours=float(res.get('cpu_hours', 0.0)),
            memory_gb=float(res.get('memory_gb', 0.0)),
            disk_gb=float(res.get('disk_gb', 0.0))
        )

        # Generate plan ID
        plan_id = f"plan_{abs(hash(task)) % 10000:04d}"

        return ExecutionPlan(
            plan_id=plan_id,
            task_description=task,
            steps=steps,
            estimated_resources=resources
        )

    def _enrich_with_knowledge(self, plan: ExecutionPlan) -> ExecutionPlan:
        """Enrich plan with knowledge base information."""
        # Add KB metadata to plan
        if hasattr(self.kb, 'search'):
            # Search for relevant docs
            try:
                relevant_docs = self.kb.search(plan.task_description, top_k=3)
                if relevant_docs:
                    doc_ids = [doc.get('id', '') for doc in relevant_docs]
                    plan.metadata['kb_docs'] = doc_ids
                    logger.debug(f"Enriched plan with KB docs: {doc_ids}")
            except Exception as e:
                logger.warning(f"Failed to enrich plan with KB: {e}")

        return plan

    def _get_kb_tools(self) -> List[str]:
        """Get list of available tools from knowledge base."""
        if not self.kb:
            return []

        # Try to get tools from KB index
        if hasattr(self.kb, 'index'):
            tools_category = self.kb.index.get('categories', {}).get('tools', {})
            docs = tools_category.get('documents', [])
            return [doc.get('id', '') for doc in docs]

        return []

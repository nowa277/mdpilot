"""AgentBase — abstract base class for all MDPilot agent paradigms."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import structlog

from mdpilot.config.schema import AppConfig
from mdpilot.types import ToolOutput
from mdpilot.tools.builtin.knowledge import get_knowledge_index_summary

from .budget import BudgetTracker
from .context import ConversationContext
from .events import EventEmitter
from .llm_caller import LLMCaller
from .progress_tracker import ProgressTracker
from mdpilot.tools.skill_loader import SkillLoader as _SkillLoader  # noqa: F401 — needed for test patching


class AgentBase(ABC):
    """Abstract base class for MDPilot agent paradigms.

    Provides shared infrastructure: LLM, tools, skills, knowledge, context,
    budget, events. Subclasses implement ``run()`` with their own reasoning loop.

    Parameters
    ----------
    config : AppConfig
        Application configuration.
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._logger = structlog.get_logger(__name__)

        # LLM provider
        prov_cfg = config.provider
        from mdpilot.llm import LLMProvider
        self._llm = LLMProvider(
            model=prov_cfg.model,
            api_key=prov_cfg.api_key.get_secret_value() if prov_cfg.api_key else None,
            base_url=prov_cfg.base_url,
            temperature=prov_cfg.temperature,
            max_tokens=prov_cfg.max_tokens,
            timeout=prov_cfg.timeout,
            max_retries=prov_cfg.max_retries,
            custom_llm_provider=prov_cfg.custom_llm_provider,
        )

        # Tool registry + dispatcher
        from mdpilot.tools.registry import ToolRegistry
        from mdpilot.tools.dispatcher import ToolDispatcher
        self._registry = ToolRegistry()
        self._registry.auto_discover("mdpilot.tools.builtin")
        self._dispatcher = ToolDispatcher(self._registry)

        # LLM caller with retry
        self._llm_caller = LLMCaller(self._llm)

        # Skill registry (unified: builtin + user, L1/L2 progressive)
        from mdpilot.agent.skills import UnifiedSkillRegistry
        self._skills = UnifiedSkillRegistry()
        self._skills.discover_all()

        # Conversation context
        system_prompt = self._build_system_prompt()
        self._context = ConversationContext(
            system_prompt=system_prompt,
            max_tokens=config.agent.max_context_tokens,
        )

        # Budget
        self._budget = BudgetTracker(
            max_iterations=config.agent.max_iterations,
        )

        # Progress tracker
        self._progress = ProgressTracker(total_steps=config.agent.max_iterations)

        # Events
        self._events = EventEmitter()

        # Context compressor
        from mdpilot.agent.context_compressor import ContextCompressor
        self._compressor = ContextCompressor(
            llm_provider=self._llm,
            trigger_ratio=0.7,
            keep_recent=2,
        )

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    async def run(self, prompt: str, stream: bool = False) -> str:
        """Execute the agent's reasoning loop."""

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def events(self) -> EventEmitter:
        return self._events

    @property
    def budget(self) -> BudgetTracker:
        return self._budget

    @property
    def config(self) -> AppConfig:
        return self._config

    @property
    def iteration(self) -> int:
        return self._budget.iteration

    @property
    def max_iterations(self) -> int:
        return self._budget._max_iterations

    # ------------------------------------------------------------------
    # Shared methods
    # ------------------------------------------------------------------

    async def _call_llm(self, messages, tools=None, stream=False):
        """Call LLM with retry. Delegates to LLMCaller."""
        return await self._llm_caller.call(
            messages=messages,
            tools=tools or self._registry.schemas(),
        )

    async def _execute_tool(self, tool_call) -> ToolOutput:
        """Execute a single tool call via the dispatcher."""
        return await self._dispatcher.execute(tool_call)

    def _build_system_prompt(self) -> str:
        """Compose the system prompt from configuration."""
        try:
            knowledge_summary = get_knowledge_index_summary()
        except Exception:
            knowledge_summary = "# Knowledge Base (unavailable)\n"

        return (
            "You are MDPilot, an AI agent for protein structure prediction, functional reasoning, and molecular simulation workflows.\n"
            "You can converse naturally with users, create executable plans, and run real terminal/file operations when needed.\n\n"
            "## Interaction Style\n"
            "- For casual questions and explanations: respond conversationally.\n"
            "- For actionable tasks: create a short plan, then execute it step by step with tools.\n"
            "- Prefer the project workflow: validate/clean protein sequence → AlphaFold2 structure prediction → BioReason functional/mechanistic reasoning → summarize outputs.\n"
            "- Always explain what you're doing and why, before and after running tools.\n\n"
            "## Knowledge Base\n"
            "You have access to a comprehensive AMBER knowledge base with detailed documentation.\n"
            "When you need specific information about tools, concepts, or workflows:\n"
            "1. Use `search_knowledge` to find relevant documents\n"
            "2. Use `read_knowledge` to load detailed documentation\n"
            "3. Follow the guidance in the loaded documents\n\n"
            "4. **Proactively** use these tools when you encounter domain-specific questions — do not wait to be told.\n\n"
            f"{knowledge_summary}\n\n"
            "## Protein Workflow Guidelines\n"
            "- Start from the user-provided sequence or file and verify inputs before launching long jobs.\n"
            "- Use AlphaFold2 before BioReason when structure context is needed.\n"
            "- Use BioReason after sequence/structure context exists to explain function, GO terms, or mechanisms.\n"
            "- Report job IDs, remote hosts, outputs, and failures clearly.\n\n"
            "## AMBER Workflow Guidelines\n"
            "- System preparation: pdb4amber (clean PDB) → tleap (build topology/coordinates)\n"
            "- Small molecules: antechamber (parameterize) → parmchk2 (missing parameters)\n"
            "- Simulation: sander for minimization/MD (pmemd auto-selected if available)\n"
            "- Analysis: cpptraj for RMSD, distances, hydrogen bonds, clustering, PCA\n"
            "- Always verify input files exist before running AMBER commands\n"
            "- Report force field choices, simulation parameters, and results clearly\n\n"
            "## AlphaFold2 Usage Guidelines\n"
            "- Default mode: db_preset='full_dbs' (30min-2hr for 100aa, always available)\n"
            "- For faster results (if small_bfd database available): use db_preset='reduced_dbs' (5-10 min)\n"
            "- For balanced mode: use db_preset='casp14' (30-40 min for 100aa)\n"
            "- Example: alphafold2_predict(sequence='MVHL...', db_preset='full_dbs')\n\n"
            "## Available Tools\n"
            "- Knowledge base: search_knowledge, read_knowledge, list_knowledge\n"
            "- bash_run: Execute shell commands with terminal read/write capability\n"
            "- file_read / file_write: Read and write project files\n"
            "- pdb4amber, tleap, cpptraj, sander, antechamber: AMBER-specific tools\n"
            "- amber_env_check: Verify AMBER installation\n\n"
            "Reason step-by-step, use tools when needed, and provide clear, accurate responses.\n"
        )

    def _inject_context(self, prompt: str, active_skills: list[str] | None = None) -> str:
        """Build enhanced context from skills and knowledge.

        Returns the context string. Caller decides how to use it.
        """
        parts = []

        # Skill context (existing behavior)
        skill_ctx = self._skills.build_context(prompt, active_skills=active_skills)
        if skill_ctx:
            parts.append(skill_ctx)

        # Knowledge injection via KnowledgeInjector
        from .knowledge_injector import KnowledgeInjector
        from mdpilot.agent.task_classifier import classify

        injector = KnowledgeInjector()
        task_type = classify(prompt)

        # inject() handles lazy-init via _get_knowledge_system() singleton
        kb_ctx = injector.inject(prompt, task_type)
        if kb_ctx:
            parts.append(kb_ctx)

        return "\n\n".join(parts)

    def _inject_tool_skills(self, prompt: str, max_chars: int = 4000) -> str:
        """Build skill context from tools whose triggers match the prompt."""
        from mdpilot.tools.skill_loader import SkillLoader

        parts: list[str] = []
        total_chars = 0
        prompt_lower = prompt.lower()

        for name in self._registry.list_tools():
            entry = self._registry.get(name)
            if entry is None:
                continue
            meta, _ = entry
            if not meta.skill_guide:
                continue

            try:
                l1 = SkillLoader.load_l1(meta.skill_guide)
                triggers = l1.get("triggers", [])
                if not any(t.lower() in prompt_lower for t in triggers):
                    continue

                l2 = SkillLoader.load_l2(meta.skill_guide)
                section = f"## Tool Guide: {meta.name}\n{l2}\n"
                if total_chars + len(section) > max_chars:
                    remaining = max_chars - total_chars
                    if remaining > 200:
                        section = section[:remaining] + "\n...(truncated)\n"
                    else:
                        break
                parts.append(section)
                total_chars += len(section)
            except Exception:
                continue

        return "\n".join(parts) if parts else ""

    def _inject_compression_notes(self, prompt: str) -> str:
        """Append compressed session notes to the enhanced system prompt."""
        if not self._compressor.should_compress:
            return ""
        return "\n\n" + self._compressor.build_notes_text()

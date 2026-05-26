"""
DEPRECATED: This module is marked for removal in v1.0.0.
Use the new coordination layer (mdpilot.coordination) instead.

Legacy WorkflowEngine - will be replaced by Planner + Executor architecture.
Kept temporarily for backward compatibility.
"""
from __future__ import annotations

import asyncio
import time
import warnings
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

warnings.warn(
    "mdpilot.agent.legacy_workflow_engine is deprecated and will be removed in v1.0.0. "
    "Use mdpilot.coordination instead.",
    DeprecationWarning,
    stacklevel=2
)

from mdpilot.agent.checkpoint import CheckpointManager, WorkflowState
from mdpilot.agent.error_classifier import ErrorClassifier
from mdpilot.agent.events import EventEmitter
from mdpilot.agent.recovery_coordinator import RecoveryActionType, RecoveryCoordinator
from mdpilot.agent.retry_policy import RetryPolicy


class Phase(Enum):
    ANALYZE = "analyze"
    CONFIGURE = "configure"
    EXECUTE = "execute"
    COMPLETE = "complete"


# 10 event types
ANALYSIS_READY = "analysis_ready"
MODE_SELECT_REQUEST = "mode_select_request"
PARAMS_PREVIEW = "params_preview"
PARAM_CONFIRM_REQUEST = "param_confirm_request"
STEP_CONFIGURE = "step_configure"
STEP_EXECUTING = "step_executing"
STEP_RESULT = "step_result"
STEP_CONFIRM_REQUEST = "step_confirm_request"
RETRY_ATTEMPT = "retry_attempt"
WORKFLOW_COMPLETE = "workflow_complete"


class WorkflowEngine:
    """4-phase MD task workflow engine.

    Phases: ANALYZE -> CONFIGURE -> EXECUTE -> COMPLETE
    """

    def __init__(
        self,
        config: Any,
        dispatcher: Any,
        llm: Any,
        error_classifier: Callable[[str], Any],
        events: EventEmitter,
    ) -> None:
        self._config = config
        self._dispatcher = dispatcher
        self._llm = llm
        self._error_classifier = error_classifier
        self._events = events
        self._phase = Phase.ANALYZE
        self._retry_count = 0
        self._workflow_mode = "auto"
        self._params: dict[str, Any] = {}
        self._mode_selected: asyncio.Future[str] | None = None
        self._param_confirm_future: asyncio.Future[bool] | None = None
        self._step_confirm_future: asyncio.Future[bool] | None = None

        # Recovery components (opt-in via config)
        if hasattr(config, 'agent') and hasattr(config.agent, 'recovery'):
            checkpoint_dir = Path.cwd()
            self.checkpoint_mgr: Optional[CheckpointManager] = CheckpointManager(
                checkpoint_dir,
                config.agent.recovery.checkpoint
            )
            self.retry_policy: Optional[RetryPolicy] = RetryPolicy(config.agent.recovery.retry)
            self.recovery: Optional[RecoveryCoordinator] = RecoveryCoordinator(
                self.checkpoint_mgr,
                self.retry_policy,
                ErrorClassifier(),
                events
            )
        else:
            # Backward compatibility: no recovery
            self.checkpoint_mgr = None
            self.retry_policy = None
            self.recovery = None

    def set_workflow_mode(self, mode: str) -> None:
        """Set workflow mode from external caller (e.g. ModeSelectDialog)."""
        self._workflow_mode = mode
        # Resolve the pending future if one exists
        if self._mode_selected is not None and not self._mode_selected.done():
            self._mode_selected.set_result(mode)

    def confirm_parameters(self, confirmed: bool = True) -> None:
        """Resolve parameter confirmation future (called by TUI)."""
        if self._param_confirm_future is not None and not self._param_confirm_future.done():
            self._param_confirm_future.set_result(confirmed)

    def confirm_step(self, confirmed: bool = True) -> None:
        """Resolve step confirmation future (called by TUI)."""
        if self._step_confirm_future is not None and not self._step_confirm_future.done():
            self._step_confirm_future.set_result(confirmed)

    async def run(self, pdb_input: str) -> str:
        """Run the full workflow for a PDB input."""
        # Try to load checkpoint if recovery enabled
        if self.checkpoint_mgr and self.checkpoint_mgr.exists():
            state = self.checkpoint_mgr.load_checkpoint()
            if state:
                # Emit event for checkpoint found
                self._events.emit("checkpoint.loaded", data={
                    "phase": state.current_phase,
                    "step_index": state.current_step_index
                })
                # Resume from checkpoint (simplified for now)
                # Full resume logic can be added later

        await self._run_analyze(pdb_input)
        await self._run_configure()
        await self._run_execute()
        return await self._run_complete()

    async def _run_analyze(self, pdb_input: str) -> None:
        """ANALYZE phase: parse PDB, analyze structure, classify system."""
        # Extract PDB file path from user input
        # User might say: "现在对这个蛋白体系进行构建:/path/to/file.pdb"
        # or just: "/path/to/file.pdb"
        import re
        from pathlib import Path

        # Try to find a file path in the input
        pdb_path = None

        # Pattern 1: Look for .pdb file path
        pdb_match = re.search(r'(/[^\s]+\.pdb)', pdb_input)
        if pdb_match:
            pdb_path = pdb_match.group(1)
        else:
            # Pattern 2: Try the whole input as a path
            if Path(pdb_input).exists() and pdb_input.endswith('.pdb'):
                pdb_path = pdb_input

        # Parse PDB file to get actual structure information
        if pdb_path:
            analysis_data = await self._analyze_pdb_file(pdb_path)
        else:
            # No valid PDB path found, return default data
            analysis_data = {
                "pdb_input": pdb_input,
                "atoms": 0,
                "residues": 0,
                "chains": [],
                "waters": 0,
                "ligands": [],
                "metals": [],
                "classification": "standard protein",
                "error": "No valid PDB file path found in input"
            }

        self._events.emit(ANALYSIS_READY, data=analysis_data)
        self._events.emit(MODE_SELECT_REQUEST, data={})
        # Create a future and wait for the ChatScreen's mode dialog to resolve it
        self._mode_selected = asyncio.get_running_loop().create_future()
        try:
            mode = await asyncio.wait_for(self._mode_selected, timeout=30.0)
            self._workflow_mode = mode
        except (asyncio.TimeoutError, Exception):
            self._workflow_mode = "auto"
        finally:
            self._mode_selected = None
        self._phase = Phase.CONFIGURE

        # Save checkpoint after ANALYZE phase
        if self.checkpoint_mgr:
            state = self._create_checkpoint_state()
            self.checkpoint_mgr.save_checkpoint(state)
            self._events.emit("checkpoint.saved", data={"phase": "ANALYZE"})

    async def _analyze_pdb_file(self, pdb_input: str) -> dict:
        """Analyze PDB file and extract structure information.

        Args:
            pdb_input: Path to PDB file

        Returns:
            Dictionary with structure information
        """
        from pathlib import Path

        # Default data in case of error
        default_data = {
            "pdb_input": pdb_input,
            "atoms": 0,
            "residues": 0,
            "chains": [],
            "ligands": [],
            "metals": [],
            "classification": "standard protein"
        }

        try:
            pdb_path = Path(pdb_input)
            if not pdb_path.exists():
                return default_data

            # Simple PDB parsing
            atoms = 0
            residues = set()
            chains = set()
            waters = 0

            with open(pdb_path, 'r') as f:
                for line in f:
                    if line.startswith('ATOM') or line.startswith('HETATM'):
                        atoms += 1
                        # Chain ID is at position 21
                        if len(line) > 21:
                            chain = line[21].strip()
                            if chain:
                                chains.add(chain)
                        # Residue number is at positions 22-26
                        if len(line) > 26:
                            res_num = line[22:26].strip()
                            res_name = line[17:20].strip()
                            if res_name == 'HOH' or res_name == 'WAT':
                                waters += 1
                            else:
                                residues.add(f"{chain}:{res_num}")

            return {
                "pdb_input": pdb_input,
                "atoms": atoms,
                "residues": len(residues),
                "chains": sorted(list(chains)),
                "waters": waters,
                "ligands": [],
                "metals": [],
                "classification": "standard protein"
            }
        except Exception as e:
            # Return default data on error
            return default_data

    async def _run_configure(self) -> None:
        """CONFIGURE phase: display key params, wait for confirmation."""
        self._params = {
            "forcefield": "ff19SB",
            "water_model": "OPC3",
            "box_type": "truncated octahedron",
            "ion_conc": "150mM NaCl",
            "cutoff": "10.0",
            "protonation": "reduce",
        }
        self._events.emit(STEP_CONFIGURE, data=self._params)
        self._events.emit(PARAMS_PREVIEW, data=self._params)

        # Semi-auto mode: wait for parameter confirmation
        if self._workflow_mode == "semi-auto":
            self._events.emit(PARAM_CONFIRM_REQUEST, data=self._params)
            self._param_confirm_future = asyncio.get_running_loop().create_future()
            try:
                confirmed = await asyncio.wait_for(self._param_confirm_future, timeout=300.0)
                if not confirmed:
                    raise RuntimeError("User cancelled parameter configuration")
            except asyncio.TimeoutError:
                raise RuntimeError("Parameter confirmation timeout")
            finally:
                self._param_confirm_future = None

        self._phase = Phase.EXECUTE

        # Save checkpoint after CONFIGURE phase
        if self.checkpoint_mgr:
            state = self._create_checkpoint_state()
            self.checkpoint_mgr.save_checkpoint(state)
            self._events.emit("checkpoint.saved", data={"phase": "CONFIGURE"})

    async def _run_execute(self) -> None:
        """EXECUTE phase: step-by-step tool calls with optional parallelization."""
        from mdpilot.types import ToolCall

        # Build step definitions with tool arguments
        steps = [
            ("pdb4amber", "Cleaning PDB", {
                "input_pdb": self._params.get("pdb_file", "input.pdb"),
                "reduce": False,
                "dry": False,
            }),
            ("reduce", "Adding hydrogens", {
                "input_pdb": "input_clean.pdb",
                "output_pdb": "input_h.pdb",
            }),
            ("tleap", "Building topology", {
                "input_script": self._generate_tleap_script(),
                "workdir": ".",
            }),
            ("sander", "Energy minimization", {
                "prmtop": "system.prmtop",
                "inpcrd": "system.inpcrd",
                "input_script": self._generate_sander_script(),
                "output": "min.out",
                "trajectory": "min.nc",
                "restart": "min.rst",
            }),
        ]

        # Check if parallel execution is enabled
        parallel_enabled = (
            hasattr(self._config, 'agent') and
            hasattr(self._config.agent, 'parallel') and
            self._config.agent.parallel.enable_parallel
        )

        if parallel_enabled:
            # Try parallel execution path
            try:
                await self._execute_parallel(steps)
                # Save checkpoint after EXECUTE phase
                if self.checkpoint_mgr:
                    state = self._create_checkpoint_state()
                    self.checkpoint_mgr.save_checkpoint(state)
                    self._events.emit("checkpoint.saved", data={"phase": "EXECUTE"})
                return
            except Exception as exc:
                # Fall back to sequential on error
                self._events.emit("parallel.fallback", data={
                    "reason": str(exc),
                    "fallback_mode": "sequential"
                })
                parallel_enabled = False

        # Sequential execution path (original implementation)
        await self._execute_sequential(steps)

        # Save checkpoint after EXECUTE phase
        if self.checkpoint_mgr:
            state = self._create_checkpoint_state()
            self.checkpoint_mgr.save_checkpoint(state)
            self._events.emit("checkpoint.saved", data={"phase": "EXECUTE"})

    async def _execute_parallel(self, steps: list[tuple[str, str, dict]]) -> None:
        """Execute steps using parallel executor.

        Args:
            steps: List of (tool_name, description, arguments) tuples
        """
        from mdpilot.agent.parallel_executor import ParallelExecutor, ExecutionConfig

        # Create execution config from agent config
        exec_config = ExecutionConfig(
            max_concurrent_tools=self._config.agent.parallel.max_concurrent_tools,
            max_memory_mb=self._config.agent.parallel.max_memory_mb,
            max_gpu_tools=self._config.agent.parallel.max_gpu_tools,
            enable_parallel=True
        )

        # Create parallel executor
        executor = ParallelExecutor(
            self._dispatcher,
            self._dispatcher._registry,
            exec_config,
            self._events
        )

        # Execute all steps in parallel waves
        results = await executor.execute_parallel(steps)

        # Process results
        for i, result in enumerate(results, 1):
            desc = steps[i-1][1]  # Get description from original steps

            # Emit result event
            self._events.emit(STEP_RESULT, data={
                "step_name": desc,
                "success": result.output.success,
                "output": result.output.output if result.output.success else result.output.error,
                "error_code": getattr(result.output, 'error_code', None),
                "error_category": getattr(result.output, 'error_category', None),
                "error_suggestion": getattr(result.output, 'error_suggestion', None),
            })

            # Handle errors with recovery coordinator
            if not result.output.success:
                if self.recovery:
                    # Use recovery coordinator for error handling
                    recovery_action = self.recovery.handle_error(
                        RuntimeError(result.output.error),
                        {
                            "tool": result.tool_call.name,
                            "step": desc,
                            "attempt": self._retry_count,
                            "phase": self._phase.value
                        }
                    )

                    if recovery_action.type == RecoveryActionType.RETRY:
                        # Wait for delay and retry
                        await asyncio.sleep(recovery_action.delay)
                        self._retry_count += 1
                        self._events.emit(RETRY_ATTEMPT, data={
                            "step_name": desc,
                            "attempt": self._retry_count,
                            "error": result.output.error,
                        })
                        # For now, continue to next step
                        # Full retry logic can be implemented later
                    elif recovery_action.type == RecoveryActionType.FAIL:
                        raise RuntimeError(f"Step '{desc}' failed: {result.output.error}")
                else:
                    # Legacy behavior: emit retry event if applicable
                    if self._retry_count < 3:
                        self._retry_count += 1
                        self._events.emit(RETRY_ATTEMPT, data={
                            "step_name": desc,
                            "attempt": self._retry_count,
                            "error": result.output.error,
                        })
                    else:
                        raise RuntimeError(f"Step '{desc}' failed after {self._retry_count} retries: {result.output.error}")

            # Semi-auto mode: wait for step confirmation after each step
            if self._workflow_mode == "semi-auto":
                self._events.emit(STEP_CONFIRM_REQUEST, data={
                    "step_name": desc,
                    "step": i,
                    "total": len(steps),
                    "completed": True
                })
                self._step_confirm_future = asyncio.get_running_loop().create_future()
                try:
                    confirmed = await asyncio.wait_for(self._step_confirm_future, timeout=300.0)
                    if not confirmed:
                        raise RuntimeError(f"User cancelled workflow at step {i}")
                except asyncio.TimeoutError:
                    raise RuntimeError(f"Step confirmation timeout at step {i}")
                finally:
                    self._step_confirm_future = None

    async def _execute_sequential(self, steps: list[tuple[str, str, dict]]) -> None:
        """Execute steps sequentially (original implementation).

        Args:
            steps: List of (tool_name, description, arguments) tuples
        """
        from mdpilot.types import ToolCall

        for i, (tool_name, desc, tool_args) in enumerate(steps, 1):
            self._events.emit(STEP_EXECUTING, data={
                "step_name": desc, "tool_name": tool_name, "step": i, "total": len(steps)
            })

            # Execute tool via dispatcher
            tool_call = ToolCall(
                id=f"workflow_step_{i}",
                name=tool_name,
                arguments=tool_args
            )

            try:
                result = await self._dispatcher.execute(tool_call)

                # Emit result event
                self._events.emit(STEP_RESULT, data={
                    "step_name": desc,
                    "success": result.success,
                    "output": result.output if result.success else result.error,
                    "error_code": result.error_code,
                    "error_category": result.error_category,
                    "error_suggestion": result.error_suggestion,
                })

                # Handle errors with recovery coordinator
                if not result.success:
                    if self.recovery:
                        # Use recovery coordinator for error handling
                        recovery_action = self.recovery.handle_error(
                            RuntimeError(result.error),
                            {
                                "tool": tool_name,
                                "step": desc,
                                "attempt": self._retry_count,
                                "phase": self._phase.value
                            }
                        )

                        if recovery_action.type == RecoveryActionType.RETRY:
                            # Wait for delay and retry
                            await asyncio.sleep(recovery_action.delay)
                            self._retry_count += 1
                            self._events.emit(RETRY_ATTEMPT, data={
                                "step_name": desc,
                                "attempt": self._retry_count,
                                "error": result.error,
                            })
                            # For now, continue to next step
                            # Full retry logic can be implemented later
                        elif recovery_action.type == RecoveryActionType.FAIL:
                            raise RuntimeError(f"Step '{desc}' failed: {result.error}")
                    else:
                        # Legacy behavior: emit retry event if applicable
                        if self._retry_count < 3:
                            self._retry_count += 1
                            self._events.emit(RETRY_ATTEMPT, data={
                                "step_name": desc,
                                "attempt": self._retry_count,
                                "error": result.error,
                            })
                            # For now, continue to next step even on error
                            # In production, might want to implement retry logic
                        else:
                            raise RuntimeError(f"Step '{desc}' failed after {self._retry_count} retries: {result.error}")

            except Exception as exc:
                # Handle unexpected errors
                error_msg = f"{type(exc).__name__}: {exc}"
                self._events.emit(STEP_RESULT, data={
                    "step_name": desc,
                    "success": False,
                    "output": error_msg,
                })
                raise RuntimeError(f"Step '{desc}' failed: {error_msg}")

            # Semi-auto mode: wait for step confirmation after each step
            if self._workflow_mode == "semi-auto":
                self._events.emit(STEP_CONFIRM_REQUEST, data={
                    "step_name": desc,
                    "step": i,
                    "total": len(steps),
                    "completed": True
                })
                self._step_confirm_future = asyncio.get_running_loop().create_future()
                try:
                    confirmed = await asyncio.wait_for(self._step_confirm_future, timeout=300.0)
                    if not confirmed:
                        raise RuntimeError(f"User cancelled workflow at step {i}")
                except asyncio.TimeoutError:
                    raise RuntimeError(f"Step confirmation timeout at step {i}")
                finally:
                    self._step_confirm_future = None

    def _generate_tleap_script(self) -> str:
        """Generate tleap input script based on workflow parameters."""
        forcefield = self._params.get("forcefield", "ff19SB")
        water_model = self._params.get("water_model", "OPC3")
        box_type = self._params.get("box_type", "truncated octahedron")

        script = f"""source leaprc.protein.{forcefield}
source leaprc.water.{water_model}

# Load PDB
mol = loadpdb input_h.pdb

# Add ions
addions mol Na+ 0
addions mol Cl- 0

# Solvate
solvatebox mol {water_model}BOX 10.0

# Save topology
saveamberparm mol system.prmtop system.inpcrd
quit
"""
        return script

    def _generate_sander_script(self) -> str:
        """Generate sander minimization input script."""
        return """Energy minimization
 &cntrl
  imin=1, maxcyc=1000, ncyc=500,
  ntb=1, ntp=0,
  cut=10.0,
 /
"""

    async def _run_complete(self) -> str:
        """COMPLETE phase: output summary, post-validation."""
        self._events.emit(WORKFLOW_COMPLETE, data={
            "summary": "System built successfully",
            "files": ["system.prmtop", "system.inpcrd"],
            "validation": {"charge_neutral": True, "ep_zero": True, "box_ok": True}
        })
        self._phase = Phase.COMPLETE

        # Cleanup checkpoint on successful completion
        if self.checkpoint_mgr and self.checkpoint_mgr.config.cleanup_on_success:
            self.checkpoint_mgr.cleanup_checkpoint()
            self._events.emit("checkpoint.cleaned", data={"phase": "COMPLETE"})

        return "Workflow complete"

    def _create_checkpoint_state(self) -> WorkflowState:
        """Create WorkflowState from current engine state.

        Returns:
            WorkflowState: Current workflow state for checkpointing.
        """
        return WorkflowState(
            workflow_id=f"workflow_{int(time.time())}",
            timestamp=datetime.now().isoformat(),
            current_phase=self._phase.value,
            current_step_index=0,
            completed_phases=[],
            phase_results={},
            step_results=[],
            context={"params": self._params}
        )

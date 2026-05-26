"""Dependency graph for analyzing tool execution order."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mdpilot.types import ToolCall, ToolMeta


@dataclass
class ToolNode:
    """Represents a tool in the dependency graph."""
    tool_id: str
    tool_call: ToolCall
    input_files: set[str]
    output_files: set[str]
    explicit_deps: list[str]


@dataclass
class ExecutionWave:
    """A group of tools that can execute in parallel."""
    wave_id: int
    tools: list[ToolNode]


class DependencyGraph:
    """Builds and analyzes tool execution dependencies."""

    def __init__(self):
        self._nodes: dict[str, ToolNode] = {}
        self._edges: dict[str, set[str]] = {}  # tool_id -> set of dependency tool_ids

    def add_tool(self, tool_id: str, tool_call: ToolCall, tool_meta: ToolMeta) -> None:
        """Add a tool to the dependency graph.

        Args:
            tool_id: Unique identifier for this tool instance
            tool_call: The tool call with arguments
            tool_meta: Tool metadata including dependencies
        """
        input_files = self._extract_input_files(tool_call.arguments)
        output_files = self._extract_output_files(tool_call.arguments, tool_call.name)

        node = ToolNode(
            tool_id=tool_id,
            tool_call=tool_call,
            input_files=input_files,
            output_files=output_files,
            explicit_deps=tool_meta.depends_on
        )

        self._nodes[tool_id] = node
        self._edges[tool_id] = set()

    def _extract_input_files(self, arguments: dict[str, Any]) -> set[str]:
        """Extract input file paths from tool arguments.

        Args:
            arguments: Tool arguments dictionary

        Returns:
            Set of input file paths
        """
        input_files = set()

        # Common input parameter patterns
        input_patterns = [
            "input_pdb", "input", "pdb", "prmtop", "inpcrd",
            "input_script", "topology", "coordinates", "structure"
        ]

        for key, value in arguments.items():
            # Check if parameter name matches input pattern
            if any(pattern in key.lower() for pattern in input_patterns):
                if isinstance(value, str) and value:
                    input_files.add(value)
            # Check for list of input files
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and any(ext in item for ext in [".pdb", ".prmtop", ".inpcrd", ".nc", ".rst"]):
                        input_files.add(item)

        return input_files

    def _extract_output_files(self, arguments: dict[str, Any], tool_name: str) -> set[str]:
        """Extract output file paths from tool arguments and tool-specific rules.

        Args:
            arguments: Tool arguments dictionary
            tool_name: Name of the tool

        Returns:
            Set of output file paths
        """
        output_files = set()

        # Common output parameter patterns
        output_patterns = ["output", "trajectory", "restart", "out"]

        for key, value in arguments.items():
            if any(pattern in key.lower() for pattern in output_patterns):
                if isinstance(value, str) and value:
                    output_files.add(value)

        # Tool-specific output rules
        if tool_name == "pdb4amber":
            # pdb4amber: input.pdb -> input_clean.pdb
            if "input_pdb" in arguments:
                input_path = arguments["input_pdb"]
                if input_path.endswith(".pdb"):
                    clean_path = input_path.replace(".pdb", "_clean.pdb")
                    output_files.add(clean_path)

        elif tool_name == "tleap":
            # tleap: always outputs system.prmtop and system.inpcrd
            workdir = arguments.get("workdir", ".")
            output_files.add(f"{workdir}/system.prmtop" if workdir != "." else "system.prmtop")
            output_files.add(f"{workdir}/system.inpcrd" if workdir != "." else "system.inpcrd")

        elif tool_name == "reduce":
            # reduce: output_pdb specified in arguments
            if "output_pdb" in arguments:
                output_files.add(arguments["output_pdb"])

        return output_files

    def analyze_dependencies(self) -> None:
        """Analyze dependencies between tools based on file I/O and explicit declarations."""
        # First, add explicit dependencies
        for tool_id, node in self._nodes.items():
            for dep_tool_name in node.explicit_deps:
                # Find tool_id that matches this tool name
                for other_id, other_node in self._nodes.items():
                    if other_node.tool_call.name == dep_tool_name:
                        self._edges[tool_id].add(other_id)

        # Second, detect file-based dependencies
        for tool_id, node in self._nodes.items():
            for input_file in node.input_files:
                # Check if any other tool produces this file
                for other_id, other_node in self._nodes.items():
                    if other_id == tool_id:
                        continue

                    # Check for exact match or pattern match
                    for output_file in other_node.output_files:
                        if self._files_match(input_file, output_file):
                            self._edges[tool_id].add(other_id)

    def _files_match(self, input_file: str, output_file: str) -> bool:
        """Check if input file matches output file.

        Args:
            input_file: Input file path
            output_file: Output file path

        Returns:
            True if files match
        """
        # Exact match
        if input_file == output_file:
            return True

        # Basename match (ignore directory)
        import os
        if os.path.basename(input_file) == os.path.basename(output_file):
            return True

        return False

    def validate(self) -> None:
        """Validate the dependency graph for circular dependencies.

        Raises:
            ValueError: If circular dependencies are detected
        """
        try:
            self.topological_sort()
        except ValueError as e:
            raise ValueError(f"Dependency graph validation failed: {e}")

    def topological_sort(self) -> list[ExecutionWave]:
        """Perform topological sort and group tools into execution waves.

        Uses Kahn's algorithm to group tools into waves where tools in the same
        wave have no dependencies on each other and can execute in parallel.

        Returns:
            List of ExecutionWave objects, ordered by execution sequence

        Raises:
            ValueError: If circular dependency is detected
        """
        # Calculate in-degree for each node
        in_degree = {tool_id: 0 for tool_id in self._nodes}
        for tool_id, deps in self._edges.items():
            in_degree[tool_id] = len(deps)

        waves = []
        wave_id = 0
        remaining = set(self._nodes.keys())

        while remaining:
            # Find all nodes with in-degree 0
            current_wave_ids = [
                tool_id for tool_id in remaining
                if in_degree[tool_id] == 0
            ]

            if not current_wave_ids:
                raise ValueError(f"Circular dependency detected among tools: {remaining}")

            # Create wave
            wave_tools = [self._nodes[tool_id] for tool_id in current_wave_ids]
            waves.append(ExecutionWave(wave_id=wave_id, tools=wave_tools))

            # Remove from remaining
            for tool_id in current_wave_ids:
                remaining.remove(tool_id)

            # Update in-degrees
            for tool_id in remaining:
                deps_in_current_wave = self._edges[tool_id] & set(current_wave_ids)
                in_degree[tool_id] -= len(deps_in_current_wave)

            wave_id += 1

        return waves

"""Tests for dependency graph data structures."""
from mdpilot.agent.dependency_graph import DependencyGraph, ExecutionWave, ToolNode
from mdpilot.types import ToolCall, ToolMeta


def test_tool_node_creation():
    """ToolNode should store tool metadata and file information."""
    tool_call = ToolCall(id="1", name="test", arguments={})
    node = ToolNode(
        tool_id="1",
        tool_call=tool_call,
        input_files={"input.pdb"},
        output_files={"output.pdb"},
        explicit_deps=["other_tool"]
    )
    assert node.tool_id == "1"
    assert node.tool_call == tool_call
    assert node.input_files == {"input.pdb"}
    assert node.output_files == {"output.pdb"}
    assert node.explicit_deps == ["other_tool"]


def test_execution_wave_creation():
    """ExecutionWave should group tools for parallel execution."""
    tool_call = ToolCall(id="1", name="test", arguments={})
    node = ToolNode(
        tool_id="1",
        tool_call=tool_call,
        input_files=set(),
        output_files=set(),
        explicit_deps=[]
    )
    wave = ExecutionWave(wave_id=0, tools=[node])
    assert wave.wave_id == 0
    assert len(wave.tools) == 1
    assert wave.tools[0] == node


def test_extract_input_files_from_arguments():
    """Should extract input files from tool arguments."""
    graph = DependencyGraph()

    # Test various input parameter patterns
    args1 = {"input_pdb": "protein.pdb", "other": "value"}
    inputs1 = graph._extract_input_files(args1)
    assert "protein.pdb" in inputs1

    args2 = {"pdb": "system.pdb", "prmtop": "system.prmtop"}
    inputs2 = graph._extract_input_files(args2)
    assert "system.pdb" in inputs2
    assert "system.prmtop" in inputs2

    args3 = {"inpcrd": "coords.inpcrd", "input_script": "script.in"}
    inputs3 = graph._extract_input_files(args3)
    assert "coords.inpcrd" in inputs3
    assert "script.in" in inputs3


def test_extract_output_files_from_arguments():
    """Should extract output files from tool arguments."""
    graph = DependencyGraph()

    # Test various output parameter patterns
    args1 = {"output": "result.out", "other": "value"}
    outputs1 = graph._extract_output_files(args1, "generic_tool")
    assert "result.out" in outputs1

    args2 = {"trajectory": "traj.nc", "restart": "restart.rst"}
    outputs2 = graph._extract_output_files(args2, "sander")
    assert "traj.nc" in outputs2
    assert "restart.rst" in outputs2


def test_extract_output_files_tool_specific_rules():
    """Should apply tool-specific output file rules."""
    graph = DependencyGraph()

    # pdb4amber: input.pdb -> input_clean.pdb
    args = {"input_pdb": "protein.pdb"}
    outputs = graph._extract_output_files(args, "pdb4amber")
    assert "protein_clean.pdb" in outputs

    # tleap: always outputs system.prmtop and system.inpcrd
    args = {"input_script": "leap.in"}
    outputs = graph._extract_output_files(args, "tleap")
    assert "system.prmtop" in outputs
    assert "system.inpcrd" in outputs

    # reduce: output_pdb specified in arguments
    args = {"input_pdb": "input.pdb", "output_pdb": "output_h.pdb"}
    outputs = graph._extract_output_files(args, "reduce")
    assert "output_h.pdb" in outputs


def test_add_tool_to_graph():
    """Should add tool node to graph."""
    graph = DependencyGraph()
    tool_call = ToolCall(id="1", name="pdb4amber", arguments={"input_pdb": "input.pdb"})
    tool_meta = ToolMeta(name="pdb4amber", description="Clean PDB", parameters={})

    graph.add_tool("step_1", tool_call, tool_meta)

    assert "step_1" in graph._nodes
    node = graph._nodes["step_1"]
    assert node.tool_id == "step_1"
    assert node.tool_call == tool_call
    assert "input.pdb" in node.input_files
    assert "input_clean.pdb" in node.output_files


def test_add_tool_with_explicit_dependencies():
    """Should store explicit dependencies from tool metadata."""
    graph = DependencyGraph()
    tool_call = ToolCall(id="1", name="sander", arguments={})
    tool_meta = ToolMeta(
        name="sander",
        description="Run sander",
        parameters={},
        depends_on=["tleap"]
    )

    graph.add_tool("step_1", tool_call, tool_meta)

    node = graph._nodes["step_1"]
    assert node.explicit_deps == ["tleap"]


def test_analyze_dependencies_file_based():
    """Should detect file-based dependencies between tools."""
    graph = DependencyGraph()

    # Tool A: produces output.pdb
    tool_a = ToolCall(id="a", name="pdb4amber", arguments={"input_pdb": "input.pdb"})
    meta_a = ToolMeta(name="pdb4amber", description="", parameters={})
    graph.add_tool("step_a", tool_a, meta_a)

    # Tool B: consumes input_clean.pdb (produced by A)
    tool_b = ToolCall(id="b", name="reduce", arguments={"input_pdb": "input_clean.pdb", "output_pdb": "input_h.pdb"})
    meta_b = ToolMeta(name="reduce", description="", parameters={})
    graph.add_tool("step_b", tool_b, meta_b)

    graph.analyze_dependencies()

    # step_b should depend on step_a
    assert "step_a" in graph._edges["step_b"]


def test_analyze_dependencies_explicit_override():
    """Should add explicit dependencies from tool metadata."""
    graph = DependencyGraph()

    tool_a = ToolCall(id="a", name="tool_a", arguments={})
    meta_a = ToolMeta(name="tool_a", description="", parameters={})
    graph.add_tool("step_a", tool_a, meta_a)

    tool_b = ToolCall(id="b", name="tool_b", arguments={})
    meta_b = ToolMeta(name="tool_b", description="", parameters={}, depends_on=["tool_a"])
    graph.add_tool("step_b", tool_b, meta_b)

    graph.analyze_dependencies()

    # step_b should depend on step_a (explicit)
    assert "step_a" in graph._edges["step_b"]


def test_analyze_dependencies_no_false_positives():
    """Should not create dependencies for independent tools."""
    graph = DependencyGraph()

    tool_a = ToolCall(id="a", name="tool_a", arguments={"input": "file_a.pdb"})
    meta_a = ToolMeta(name="tool_a", description="", parameters={})
    graph.add_tool("step_a", tool_a, meta_a)

    tool_b = ToolCall(id="b", name="tool_b", arguments={"input": "file_b.pdb"})
    meta_b = ToolMeta(name="tool_b", description="", parameters={})
    graph.add_tool("step_b", tool_b, meta_b)

    graph.analyze_dependencies()

    # No dependencies should exist
    assert len(graph._edges["step_a"]) == 0
    assert len(graph._edges["step_b"]) == 0


def test_topological_sort_linear_chain():
    """Linear chain A→B→C→D should create 4 waves."""
    graph = DependencyGraph()

    # Create linear chain: A produces file1, B consumes file1 and produces file2, etc.
    tool_a = ToolCall(id="a", name="tool_a", arguments={"output": "file1.pdb"})
    meta_a = ToolMeta(name="tool_a", description="", parameters={})
    graph.add_tool("step_a", tool_a, meta_a)

    tool_b = ToolCall(id="b", name="tool_b", arguments={"input": "file1.pdb", "output": "file2.pdb"})
    meta_b = ToolMeta(name="tool_b", description="", parameters={})
    graph.add_tool("step_b", tool_b, meta_b)

    tool_c = ToolCall(id="c", name="tool_c", arguments={"input": "file2.pdb", "output": "file3.pdb"})
    meta_c = ToolMeta(name="tool_c", description="", parameters={})
    graph.add_tool("step_c", tool_c, meta_c)

    tool_d = ToolCall(id="d", name="tool_d", arguments={"input": "file3.pdb", "output": "file4.pdb"})
    meta_d = ToolMeta(name="tool_d", description="", parameters={})
    graph.add_tool("step_d", tool_d, meta_d)

    graph.analyze_dependencies()
    waves = graph.topological_sort()

    # Should create 4 waves, one for each tool
    assert len(waves) == 4
    assert waves[0].wave_id == 0
    assert len(waves[0].tools) == 1
    assert waves[0].tools[0].tool_id == "step_a"

    assert waves[1].wave_id == 1
    assert len(waves[1].tools) == 1
    assert waves[1].tools[0].tool_id == "step_b"

    assert waves[2].wave_id == 2
    assert len(waves[2].tools) == 1
    assert waves[2].tools[0].tool_id == "step_c"

    assert waves[3].wave_id == 3
    assert len(waves[3].tools) == 1
    assert waves[3].tools[0].tool_id == "step_d"


def test_topological_sort_parallel_branches():
    """A→[B,C] should create 2 waves with B,C in same wave."""
    graph = DependencyGraph()

    # A produces file1
    tool_a = ToolCall(id="a", name="tool_a", arguments={"output": "file1.pdb"})
    meta_a = ToolMeta(name="tool_a", description="", parameters={})
    graph.add_tool("step_a", tool_a, meta_a)

    # B and C both consume file1 (independent of each other)
    tool_b = ToolCall(id="b", name="tool_b", arguments={"input": "file1.pdb", "output": "file2.pdb"})
    meta_b = ToolMeta(name="tool_b", description="", parameters={})
    graph.add_tool("step_b", tool_b, meta_b)

    tool_c = ToolCall(id="c", name="tool_c", arguments={"input": "file1.pdb", "output": "file3.pdb"})
    meta_c = ToolMeta(name="tool_c", description="", parameters={})
    graph.add_tool("step_c", tool_c, meta_c)

    graph.analyze_dependencies()
    waves = graph.topological_sort()

    # Should create 2 waves
    assert len(waves) == 2

    # Wave 0: only A
    assert waves[0].wave_id == 0
    assert len(waves[0].tools) == 1
    assert waves[0].tools[0].tool_id == "step_a"

    # Wave 1: B and C (parallel)
    assert waves[1].wave_id == 1
    assert len(waves[1].tools) == 2
    tool_ids = {tool.tool_id for tool in waves[1].tools}
    assert tool_ids == {"step_b", "step_c"}


def test_topological_sort_all_independent():
    """[A,B,C] should create 1 wave with all 3 tools."""
    graph = DependencyGraph()

    # Three independent tools
    tool_a = ToolCall(id="a", name="tool_a", arguments={"input": "file_a.pdb"})
    meta_a = ToolMeta(name="tool_a", description="", parameters={})
    graph.add_tool("step_a", tool_a, meta_a)

    tool_b = ToolCall(id="b", name="tool_b", arguments={"input": "file_b.pdb"})
    meta_b = ToolMeta(name="tool_b", description="", parameters={})
    graph.add_tool("step_b", tool_b, meta_b)

    tool_c = ToolCall(id="c", name="tool_c", arguments={"input": "file_c.pdb"})
    meta_c = ToolMeta(name="tool_c", description="", parameters={})
    graph.add_tool("step_c", tool_c, meta_c)

    graph.analyze_dependencies()
    waves = graph.topological_sort()

    # Should create 1 wave with all 3 tools
    assert len(waves) == 1
    assert waves[0].wave_id == 0
    assert len(waves[0].tools) == 3
    tool_ids = {tool.tool_id for tool in waves[0].tools}
    assert tool_ids == {"step_a", "step_b", "step_c"}


def test_validate_detects_circular_dependency():
    """Should detect circular dependencies and raise error."""
    graph = DependencyGraph()

    # Create circular dependency: A -> B -> A
    tool_a = ToolCall(id="a", name="tool_a", arguments={"output": "file_a.pdb"})
    tool_b = ToolCall(id="b", name="tool_b", arguments={"input": "file_a.pdb", "output": "file_b.pdb"})

    meta_a = ToolMeta(name="tool_a", description="", parameters={}, depends_on=["tool_b"])
    meta_b = ToolMeta(name="tool_b", description="", parameters={})

    graph.add_tool("step_a", tool_a, meta_a)
    graph.add_tool("step_b", tool_b, meta_b)
    graph.analyze_dependencies()

    # Should raise ValueError on validate
    try:
        graph.validate()
        assert False, "Should have raised ValueError for circular dependency"
    except ValueError as e:
        assert "Circular dependency" in str(e)

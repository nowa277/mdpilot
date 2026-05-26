"""Integration tests for PlanGenerator with real LLM."""

import os
import pytest

from mdpilot.coordination.plan_generator import PlanGenerator
from mdpilot.coordination.types import ExecutionPlan
from mdpilot.llm.provider import LLMProvider
from mdpilot.knowledge.index import KnowledgeIndex


@pytest.mark.integration
class TestPlanGeneratorIntegration:
    """Integration tests with real LLM and knowledge base."""

    @pytest.fixture
    def llm_client(self):
        """Create real LLM client."""
        # Use environment variable or default to Claude
        model = os.getenv("AMBER_LLM_MODEL", "claude-sonnet-4-20250514")
        api_key = os.getenv("ANTHROPIC_API_KEY")

        if not api_key:
            pytest.skip("ANTHROPIC_API_KEY not set")

        return LLMProvider(
            model=model,
            api_key=api_key,
            temperature=0.0,
            max_tokens=4096
        )

    @pytest.fixture
    def knowledge_base(self):
        """Create real knowledge base."""
        kb_path = os.path.join(
            os.path.dirname(__file__),
            "../../knowledge_base"
        )

        if not os.path.exists(kb_path):
            pytest.skip("Knowledge base not found")

        try:
            return KnowledgeIndex(kb_path)
        except FileNotFoundError:
            pytest.skip("Knowledge base index not found")

    @pytest.fixture
    def generator(self, llm_client, knowledge_base):
        """Create PlanGenerator with real components."""
        return PlanGenerator(llm_client, knowledge_base)

    @pytest.mark.asyncio
    async def test_generate_protein_preparation_plan(self, generator):
        """Test generating plan for protein preparation."""
        task = "Prepare protein 1AKI for molecular dynamics simulation"

        plan = await generator.generate_plan(task)

        # Verify plan structure
        assert isinstance(plan, ExecutionPlan)
        assert plan.plan_id.startswith("plan_")
        assert plan.task_description == task
        assert len(plan.steps) > 0

        # Verify steps have required fields
        for step in plan.steps:
            assert step.step_id
            assert step.action
            assert step.intent
            assert isinstance(step.parameters, dict)
            assert isinstance(step.required_tools, list)

        # Verify resource estimates
        assert plan.estimated_resources.cpu_hours >= 0
        assert plan.estimated_resources.memory_gb >= 0
        assert plan.estimated_resources.disk_gb >= 0

        # Verify plan is valid
        assert plan.validate()

    @pytest.mark.asyncio
    async def test_generate_full_md_workflow_plan(self, generator):
        """Test generating plan for complete MD workflow."""
        task = """Run a complete molecular dynamics simulation:
        1. Prepare PDB structure 2LYZ
        2. Build topology with ff19SB force field
        3. Minimize energy
        4. Equilibrate system (NVT then NPT)
        5. Run 10ns production MD
        6. Analyze trajectory"""

        context = {
            "pdb_id": "2LYZ",
            "force_field": "ff19SB",
            "water_model": "OPC3",
            "production_time_ns": 10
        }

        plan = await generator.generate_plan(task, context)

        # Verify comprehensive plan
        assert len(plan.steps) >= 5  # Should have multiple steps
        assert plan.validate()

        # Check for expected actions
        actions = [step.action for step in plan.steps]
        assert any("prepare" in action.lower() for action in actions)
        assert any("minimize" in action.lower() or "minim" in action.lower() for action in actions)

        # Verify resource estimates are reasonable for MD
        assert plan.estimated_resources.cpu_hours > 0
        assert plan.estimated_resources.memory_gb > 0

    @pytest.mark.asyncio
    async def test_generate_plan_with_kb_enrichment(self, generator, knowledge_base):
        """Test that KB enrichment adds relevant metadata."""
        task = "Use pdb4amber to clean protein structure"

        plan = await generator.generate_plan(task)

        # Verify KB enrichment
        if 'kb_docs' in plan.metadata:
            assert isinstance(plan.metadata['kb_docs'], list)
            assert len(plan.metadata['kb_docs']) > 0

        # Verify plan mentions relevant tools
        all_tools = []
        for step in plan.steps:
            all_tools.extend(step.required_tools)

        # Should mention pdb4amber since it's in the task
        assert any('pdb4amber' in tool.lower() for tool in all_tools)

    @pytest.mark.asyncio
    async def test_generate_plan_complex_system(self, generator):
        """Test generating plan for complex system (protein-ligand)."""
        task = """Prepare a protein-ligand complex for MD simulation:
        - Protein: 1AKI
        - Ligand: small molecule inhibitor
        - Need to parameterize ligand with GAFF2
        - Use AM1-BCC charges"""

        context = {
            "system_type": "protein-ligand",
            "ligand_charge_method": "AM1-BCC",
            "ligand_force_field": "GAFF2"
        }

        plan = await generator.generate_plan(task, context)

        # Verify plan handles complexity
        assert len(plan.steps) >= 3
        assert plan.validate()

        # Should mention ligand-related tools
        all_tools = []
        for step in plan.steps:
            all_tools.extend(step.required_tools)

        # Check for ligand preparation tools
        tool_str = ' '.join(all_tools).lower()
        assert any(tool in tool_str for tool in ['antechamber', 'parmchk', 'gaff'])

    @pytest.mark.asyncio
    async def test_generate_plan_analysis_only(self, generator):
        """Test generating plan for analysis-only task."""
        task = "Analyze existing MD trajectory: calculate RMSD, RMSF, and hydrogen bonds"

        context = {
            "trajectory_file": "prod.nc",
            "topology_file": "system.prmtop"
        }

        plan = await generator.generate_plan(task, context)

        # Verify analysis-focused plan
        assert len(plan.steps) > 0
        assert plan.validate()

        # Should mention analysis tools
        all_tools = []
        for step in plan.steps:
            all_tools.extend(step.required_tools)

        tool_str = ' '.join(all_tools).lower()
        assert 'cpptraj' in tool_str or 'pytraj' in tool_str

    @pytest.mark.asyncio
    async def test_plan_validation_passes(self, generator):
        """Test that generated plans pass validation."""
        tasks = [
            "Minimize protein structure",
            "Run equilibration",
            "Analyze trajectory RMSD"
        ]

        for task in tasks:
            plan = await generator.generate_plan(task)

            # Should not raise exception
            assert plan.validate()

            # Verify all required fields
            assert plan.plan_id
            assert plan.task_description
            assert len(plan.steps) > 0

            for step in plan.steps:
                assert step.step_id
                assert step.action
                assert step.intent

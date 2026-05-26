#!/usr/bin/env python3
"""
Phase 1B Round 2 Test: Standard Protein Workflow
Test system: 1UBQ (Ubiquitin - small standard protein)
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mdpilot.workflows.standard_protein import StandardProteinWorkflow, WorkflowConfig
from mdpilot.tools.builtin.amber.env_detector import configure_amber_environment


def main():
    print("=" * 70)
    print("Phase 1B Round 2 Test: Standard Protein Workflow")
    print("System: 1UBQ (Ubiquitin)")
    print("=" * 70)
    print()

    # Configure AmberTools environment
    print("Configuring AmberTools environment...")
    env = configure_amber_environment()
    if env:
        print(f"✅ AmberTools detected: {env.amberhome}")
        print(f"   Version: {env.version}")
    else:
        print("❌ AmberTools not found. Please install AmberTools or set AMBERHOME.")
        return 1
    print()

    # Setup test directory
    test_dir = Path(__file__).parent / "test_output" / "1ubq"
    test_dir.mkdir(parents=True, exist_ok=True)

    # Create workflow configuration
    config = WorkflowConfig(
        force_field="ff19SB",
        water_model="OPC3",
        box_type="octahedron",
        box_padding=10.0,
        work_dir=test_dir,
        keep_intermediates=True,
    )

    # Create workflow
    workflow = StandardProteinWorkflow(config=config)

    print("Starting workflow...")
    print()

    try:
        # Run workflow (async)
        import asyncio
        result = asyncio.run(workflow.run_from_pdb_id("1UBQ"))

        print()
        print("=" * 70)
        print("Results")
        print("=" * 70)
        print()

        if not result.success:
            print(f"❌ Workflow failed: {result.error}")
            return 1

        print("✅ Workflow completed successfully")
        print()
        print("Output files:")
        print(f"  Topology:    {result.prmtop}")
        print(f"  Coordinates: {result.inpcrd}")

        if result.intermediate_files:
            print()
            print("Intermediate files:")
            for key, path in result.intermediate_files.items():
                print(f"  {key:20s}: {path}")

        if result.validation:
            print()
            print("Validation Report:")
            print("-" * 70)
            for check in result.validation.checks:
                status = "✅" if check.passed else "❌"
                print(f"  {status} {check.name:20s}: {check.value:15s} (expected: {check.expected})")
                if check.message:
                    print(f"     → {check.message}")

            print()
            if result.validation.passed:
                print("✅ All validation checks passed!")
                return 0
            else:
                print("❌ Some validation checks failed.")
                return 1

    except Exception as e:
        print()
        print("=" * 70)
        print("Error")
        print("=" * 70)
        print(f"❌ Workflow failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

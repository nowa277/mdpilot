#!/usr/bin/env python3
"""Test script for Phase 1B: Standard protein workflow validation.

This script tests the complete workflow with 2CAB (carbonic anhydrase with Zn).
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for development testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mdpilot.workflows import StandardProteinWorkflow, WorkflowConfig
from mdpilot.tools.builtin.amber.env_detector import configure_amber_environment


async def test_2cab():
    """Test standard protein workflow with 2CAB."""
    print("="*70)
    print("Phase 1B Test: Standard Protein Workflow")
    print("System: 2CAB (Carbonic Anhydrase with Zn)")
    print("="*70)
    print()

    # Configure AmberTools environment
    print("Configuring AmberTools environment...")
    try:
        env = configure_amber_environment()
        print(f"✅ AmberTools detected: {env.amberhome}")
        print(f"   Version: {env.version}")
        print()
    except Exception as e:
        print(f"❌ Failed to configure AmberTools: {e}")
        return False

    # Create test directory
    test_dir = Path(__file__).parent / "test_output" / "2cab"
    test_dir.mkdir(parents=True, exist_ok=True)

    # Configure workflow
    config = WorkflowConfig(
        force_field="ff19SB",
        water_model="OPC3",
        box_type="octahedron",
        box_padding=10.0,
        minimize_steps=100,  # Reduced for testing
        work_dir=test_dir,
        keep_intermediates=True,
    )

    # Create workflow
    workflow = StandardProteinWorkflow(config)

    # Run workflow
    print("Starting workflow...")
    print()

    try:
        result = await workflow.run_from_pdb_id("2CAB")
    except Exception as e:
        print(f"❌ Workflow failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Display results
    print()
    print("="*70)
    print("Results")
    print("="*70)
    print()

    if result.success:
        print("✅ Workflow completed successfully")
        print()
        print(f"Output files:")
        print(f"  Topology:    {result.prmtop}")
        print(f"  Coordinates: {result.inpcrd}")
        print()

        if result.intermediate_files:
            print(f"Intermediate files:")
            for name, path in result.intermediate_files.items():
                print(f"  {name:20s}: {path}")
            print()

        # Validation report
        if result.validation:
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
                return True
            else:
                print("⚠️  Some validation checks failed")
                return False
    else:
        print(f"❌ Workflow failed: {result.error}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_2cab())
    sys.exit(0 if success else 1)

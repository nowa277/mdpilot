#!/usr/bin/env python3
"""Test script for enhanced protonation workflow with propka.

This script tests the new protonation workflow with 2CAB (Zn-containing protein)
to verify that HIS residues coordinating Zn are correctly assigned as HID.
"""

import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mdpilot.workflows.standard_protein import StandardProteinWorkflow, WorkflowConfig
from mdpilot.tools.builtin.amber.env_detector import configure_amber_environment
from mdpilot.tools.builtin.propka import is_propka_available


def main():
    print("=" * 70)
    print("Enhanced Protonation Workflow Test")
    print("System: 2CAB (Carbonic Anhydrase with Zn²⁺)")
    print("=" * 70)
    print()

    # Check propka availability
    print("Checking propka availability...")
    if is_propka_available():
        print("✅ propka3 is available")
    else:
        print("⚠️  propka3 not found. Install with: pip install propka")
        print("   Workflow will use default protonation rules")
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
    test_dir = Path(__file__).parent / "test_output" / "2cab_propka"
    test_dir.mkdir(parents=True, exist_ok=True)

    # Create workflow configuration with propka enabled
    config = WorkflowConfig(
        force_field="ff19SB",
        water_model="OPC3",
        box_type="octahedron",
        box_padding=10.0,
        use_propka=True,  # Enable propka
        target_ph=7.0,
        minimize_steps=100,  # Reduced for testing
        work_dir=test_dir,
        keep_intermediates=True,
    )

    # Create workflow
    workflow = StandardProteinWorkflow(config=config)

    print("Starting enhanced workflow with propka...")
    print()

    try:
        # Run workflow (async)
        result = asyncio.run(workflow.run_from_pdb_id("2CAB"))

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

        # Display protonation report
        if result.protonation:
            print("Protonation State Report:")
            print("-" * 70)
            print(result.protonation.summary())
            print()

            # Check specific HIS residues for 2CAB
            print("2CAB Zn-coordinating HIS residues:")
            print("-" * 70)
            # Note: pdb4amber renumbers residues. Original PDB has HIS 94, 96, 119
            # coordinating Zn, but after pdb4amber processing they become 90, 92, 115
            zn_his_renumbered = [90, 92, 115]  # Renumbered HIS coordinating Zn in 2CAB
            zn_his_original = [94, 96, 119]    # Original PDB numbering (for reference)

            correct_count = 0
            for i, resnum in enumerate(zn_his_renumbered):
                orig_num = zn_his_original[i]
                if resnum in result.protonation.his_assignments:
                    assigned = result.protonation.his_assignments[resnum]
                    status = "✅" if assigned == "HID" else "⚠️ "
                    print(f"  {status} HIS {resnum:3d} (orig {orig_num:3d}) → {assigned:3s}")
                    if assigned == "HID":
                        correct_count += 1
                    else:
                        print(f"      WARNING: Expected HID for Zn coordination!")
                else:
                    print(f"  ❌ HIS {resnum:3d} (orig {orig_num:3d}) → NOT FOUND")
            print()

        print("Output files:")
        print(f"  Topology:    {result.prmtop}")
        print(f"  Coordinates: {result.inpcrd}")
        print()

        if result.intermediate_files:
            print("Intermediate files:")
            for key, path in result.intermediate_files.items():
                if key != "protonation_report":
                    print(f"  {key:20s}: {path}")
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
            else:
                print("⚠️  Some validation checks failed")

        # Final assessment
        print()
        print("=" * 70)
        print("Assessment")
        print("=" * 70)

        issues = []

        # Check if propka was used
        if result.protonation and is_propka_available():
            print("✅ propka was used for pKa prediction")
        elif not is_propka_available():
            print("⚠️  propka not available, used default rules")
            issues.append("propka not installed")

        # Check HIS assignments for metal coordination
        if result.protonation:
            # Use renumbered residue IDs (after pdb4amber processing)
            zn_his_renumbered = [90, 92, 115]
            correct_his = sum(
                1 for resnum in zn_his_renumbered
                if resnum in result.protonation.his_assignments
                and result.protonation.his_assignments[resnum] == "HID"
            )
            if correct_his == len(zn_his_renumbered):
                print(f"✅ All {len(zn_his_renumbered)} Zn-coordinating HIS correctly assigned as HID")
            else:
                print(f"⚠️  Only {correct_his}/{len(zn_his_renumbered)} Zn-coordinating HIS assigned as HID")
                issues.append("Incorrect HIS protonation for metal coordination")

        # Check validation
        if result.validation and result.validation.passed:
            print("✅ System validation passed")
        else:
            print("⚠️  System validation failed")
            issues.append("Validation failed")

        print()
        if not issues:
            print("🎉 Enhanced protonation workflow is working correctly!")
            return 0
        else:
            print("⚠️  Issues detected:")
            for issue in issues:
                print(f"   - {issue}")
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

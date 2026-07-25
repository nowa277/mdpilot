#!/usr/bin/env python3
"""Phase 2B End-to-End Demo: AlphaFold2 + BioReason Integration

This script demonstrates the complete workflow:
1. AlphaFold2 structure prediction on lab02
2. BioReason function annotation on lab06
3. Output results to /home/6-FF/changshenjie/project/mdpilot
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mdpilot.integrations.alphafold2.celery_client import AlphaFold2CeleryClient
from mdpilot.integrations.bioreason.celery_client import BioreasonCeleryClient


async def main():
    # Test sequence: Human hemoglobin alpha chain (50 aa for quick demo)
    sequence = "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHF"
    
    print("=" * 70)
    print("Phase 2B Demo: AlphaFold2 + BioReason Integration")
    print("=" * 70)
    print(f"\nSequence: {sequence}")
    print(f"Length: {len(sequence)} aa\n")
    
    # Step 1: AlphaFold2 Structure Prediction
    print("[1/2] Running AlphaFold2 structure prediction on lab02...")
    print("      (This may take 5-10 minutes for a 50aa sequence)")
    
    af2_config = {
        "ssh": {"host": "lab02", "username": "zhao", "key_path": "~/.ssh/id_rsa"},
        "celery": {
            "broker_url": "redis://localhost:6379/2",
            "backend_url": "redis://localhost:6379/3",
            "task_timeout": 14400,
            "poll_interval": 5
        },
        "work_dir": "/home/2-BB/changeshengjie/project/mdpilot",
        "conda_env": "af2_py310"
    }
    
    af2_client = AlphaFold2CeleryClient(**af2_config)
    await af2_client.connect()
    
    try:
        def progress_callback(progress):
            print(f"      Progress: {progress.message} ({progress.percent}%)")
        
        structure_result = await af2_client.predict(
            sequence,
            "demo_hemoglobin",
            progress_callback=progress_callback
        )
        
        print(f"\n      ✓ Structure predicted")
        print(f"        - Best model: {structure_result['best_model']}")
        print(f"        - Avg pLDDT: {structure_result['avg_plddt']}")
        print(f"        - Output: {structure_result['output_dir']}")
    finally:
        await af2_client.disconnect()
    
    # Step 2: BioReason Function Annotation
    print(f"\n[2/2] Running BioReason function annotation on lab06...")
    print("      (This should take 10-60 seconds)")
    
    bio_config = {
        "ssh": {"host": "lab06", "username": "zhao", "key_path": "~/.ssh/id_rsa"},
        "celery": {
            "broker_url": "redis://localhost:6379/0",
            "backend_url": "redis://localhost:6379/1",
            "task_timeout": 300,
            "poll_interval": 2
        },
        "work_dir": "/home/6-FF/luo/BioReason-Pro",
        "conda_env": "bioreason"
    }
    
    bio_client = BioreasonCeleryClient(**bio_config)
    await bio_client.connect()
    
    try:
        function_result = await bio_client.annotate(sequence, "Homo sapiens (Human)")
        
        print(f"\n      ✓ Function annotated")
        print(f"        - MF: {', '.join(function_result['go_terms']['MF'][:3])}")
        print(f"        - BP: {', '.join(function_result['go_terms']['BP'][:3])}")
        print(f"        - CC: {', '.join(function_result['go_terms']['CC'][:3])}")
    finally:
        await bio_client.disconnect()
    
    # Step 3: Copy results to lab06 output directory
    print(f"\n[3/3] Copying results to /home/6-FF/changshenjie/project/mdpilot...")
    
    import subprocess
    output_dir = "/home/6-FF/changshenjie/project/mdpilot/demo_results"
    
    # Create output directory on lab06
    subprocess.run([
        "ssh", "lab06",
        f"mkdir -p {output_dir}"
    ], check=True)
    
    # Copy PDB file from lab02 to lab06
    subprocess.run([
        "ssh", "lab02",
        f"scp {structure_result['best_model']} lab06:{output_dir}/"
    ], check=True)
    
    # Save annotation results to lab06
    import json
    result_json = json.dumps({
        "sequence": sequence,
        "structure": structure_result,
        "function": function_result
    }, indent=2)
    
    subprocess.run([
        "ssh", "lab06",
        f"echo '{result_json}' > {output_dir}/demo_results.json"
    ], check=True)
    
    print(f"      ✓ Results saved to {output_dir}")
    
    print("\n" + "=" * 70)
    print("Demo Complete!")
    print("=" * 70)
    print(f"\nResults location: lab06:{output_dir}/")
    print(f"  - demo_results.json (complete results)")
    print(f"  - ranked_0.pdb (best structure model)")


if __name__ == "__main__":
    asyncio.run(main())

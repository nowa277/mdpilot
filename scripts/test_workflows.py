#!/usr/bin/env python3
"""
End-to-End Workflow Testing Script
Tests three complete workflows:
1. Sequence Analysis
2. Structure Annotation
3. System Building
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mdpilot.config.loader import load_config
from mdpilot.llm.provider import LLMProvider


async def test_sequence_analysis():
    """Test Workflow 1: Sequence Analysis"""
    print("\n" + "="*80)
    print("🧬 WORKFLOW 1: SEQUENCE ANALYSIS")
    print("="*80)
    
    config = load_config()
    provider = LLMProvider(
        model=config.provider.model,
        api_key=config.provider.api_key,
        base_url=config.provider.base_url,
        temperature=config.provider.temperature,
        max_tokens=config.provider.max_tokens,
        timeout=config.provider.timeout,
        max_retries=config.provider.max_retries,
        custom_llm_provider=config.provider.custom_llm_provider,
    )
    
    prompt = """Analyze this protein sequence and provide:
1. Sequence length and composition
2. Predicted secondary structure elements
3. Potential functional domains
4. Hydrophobicity profile

Sequence: MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHFDLSHGSAQVKGHGKKVADALTNAVAHVDDMPNALSALSDLHAHKLRVDPVNFKLLSHCLLVTLAAHLPAEFTPAVHASLDKFLASVSTVLTSKYR"""
    
    print(f"\n📝 Prompt: {prompt[:100]}...")
    print(f"\n🔧 Config:")
    print(f"   Model: {config.provider.model}")
    print(f"   Base URL: {config.provider.base_url}")
    api_key_str = str(config.provider.api_key) if config.provider.api_key else None
    print(f"   API Key: {api_key_str[:20]}..." if api_key_str else "   API Key: None")
    
    try:
        print("\n⏳ Sending request to LLM...")
        response = await provider.chat(
            messages=[{"role": "user", "content": prompt}],
            stream=False,
        )
        
        print("\n✅ Response received:")
        print("-" * 80)
        print(response.content[:500])
        if len(response.content) > 500:
            print(f"\n... (truncated, total {len(response.content)} chars)")
        print("-" * 80)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_structure_annotation():
    """Test Workflow 2: Structure Annotation"""
    print("\n" + "="*80)
    print("🏗️  WORKFLOW 2: STRUCTURE ANNOTATION")
    print("="*80)
    
    config = load_config()
    provider = LLMProvider(
        model=config.provider.model,
        api_key=config.provider.api_key,
        base_url=config.provider.base_url,
        temperature=config.provider.temperature,
        max_tokens=config.provider.max_tokens,
        timeout=config.provider.timeout,
        max_retries=config.provider.max_retries,
        custom_llm_provider=config.provider.custom_llm_provider,
    )
    
    prompt = """Analyze PDB structure 1AKI and provide:
1. Protein name and function
2. Number of chains and residues
3. Secondary structure composition (alpha-helix, beta-sheet, loops)
4. Active site or binding site information
5. Any notable structural features

Note: You can describe what information would typically be found in this PDB entry."""
    
    print(f"\n📝 Prompt: {prompt[:100]}...")
    
    try:
        print("\n⏳ Sending request to LLM...")
        response = await provider.chat(
            messages=[{"role": "user", "content": prompt}],
            stream=False,
        )
        
        print("\n✅ Response received:")
        print("-" * 80)
        print(response.content[:500])
        if len(response.content) > 500:
            print(f"\n... (truncated, total {len(response.content)} chars)")
        print("-" * 80)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_system_building():
    """Test Workflow 3: System Building"""
    print("\n" + "="*80)
    print("⚙️  WORKFLOW 3: SYSTEM BUILDING")
    print("="*80)
    
    config = load_config()
    provider = LLMProvider(
        model=config.provider.model,
        api_key=config.provider.api_key,
        base_url=config.provider.base_url,
        temperature=config.provider.temperature,
        max_tokens=config.provider.max_tokens,
        timeout=config.provider.timeout,
        max_retries=config.provider.max_retries,
        custom_llm_provider=config.provider.custom_llm_provider,
    )
    
    prompt = """Describe the steps to build an AMBER molecular dynamics system for a protein:
1. Input preparation (PDB cleaning, protonation)
2. Force field selection (ff19SB, OPC water model)
3. Solvation and ion addition
4. Energy minimization strategy
5. Equilibration protocol (NVT, NPT)
6. Production MD parameters

Provide a concise workflow outline."""
    
    print(f"\n📝 Prompt: {prompt[:100]}...")
    
    try:
        print("\n⏳ Sending request to LLM...")
        response = await provider.chat(
            messages=[{"role": "user", "content": prompt}],
            stream=False,
        )
        
        print("\n✅ Response received:")
        print("-" * 80)
        print(response.content[:500])
        if len(response.content) > 500:
            print(f"\n... (truncated, total {len(response.content)} chars)")
        print("-" * 80)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all three workflow tests"""
    print("\n" + "="*80)
    print("🚀 MDPilot End-to-End Workflow Testing")
    print("="*80)
    
    results = {
        "Sequence Analysis": False,
        "Structure Annotation": False,
        "System Building": False,
    }
    
    # Test 1: Sequence Analysis
    results["Sequence Analysis"] = await test_sequence_analysis()
    await asyncio.sleep(1)  # Brief pause between tests
    
    # Test 2: Structure Annotation
    results["Structure Annotation"] = await test_structure_annotation()
    await asyncio.sleep(1)
    
    # Test 3: System Building
    results["System Building"] = await test_system_building()
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    for workflow, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{workflow:30s} {status}")
    
    total = len(results)
    passed = sum(results.values())
    print(f"\nTotal: {passed}/{total} workflows passed")
    
    if passed == total:
        print("\n🎉 All workflows completed successfully!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} workflow(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

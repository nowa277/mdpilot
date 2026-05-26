# tests/integration/test_amber_tools_coverage.py
import pytest
import subprocess
from pathlib import Path
import tempfile
import os

@pytest.mark.integration
def test_pdb4amber_integration(require_amber_tool, amber_tool_paths, sample_pdb):
    """测试 pdb4amber 工具真实调用"""
    require_amber_tool("pdb4amber", "core")

    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "cleaned.pdb"

        # 运行 pdb4amber（使用完整路径）
        result = subprocess.run(
            [amber_tool_paths["pdb4amber"], "-i", str(sample_pdb), "-o", str(output)],
            capture_output=True,
            text=True,
        )

        # 验证执行成功
        assert result.returncode == 0, f"pdb4amber failed: {result.stderr}"

        # 验证输出文件存在
        assert output.exists(), "Cleaned PDB file not created"

        # 验证输出文件非空
        assert output.stat().st_size > 0, "Cleaned PDB file is empty"

        # 验证输出包含 ATOM 记录
        content = output.read_text()
        assert "ATOM" in content, "No ATOM records in cleaned PDB"


@pytest.mark.integration
def test_tleap_integration(require_amber_tool, amber_tool_paths, sample_pdb):
    """测试 tleap 工具真实调用"""
    require_amber_tool("tleap", "core")
    require_amber_tool("pdb4amber", "core")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # 先用 pdb4amber 清理 PDB
        cleaned_pdb = tmpdir / "cleaned.pdb"
        subprocess.run(
            [amber_tool_paths["pdb4amber"], "-i", str(sample_pdb), "-o", str(cleaned_pdb)],
            capture_output=True,
            check=True,
        )

        # 创建 tleap 脚本
        leap_script = tmpdir / "leap.in"
        leap_script.write_text("""
source leaprc.protein.ff14SB
source leaprc.water.tip3p

mol = loadPdb cleaned.pdb
check mol
saveAmberParm mol system.prmtop system.inpcrd
savePdb mol system.pdb
quit
""")

        # 运行 tleap（使用完整路径）
        result = subprocess.run(
            [amber_tool_paths["tleap"], "-f", str(leap_script)],
            cwd=tmpdir,
            capture_output=True,
            text=True,
        )

        # 验证执行成功
        assert result.returncode == 0, f"tleap failed: {result.stderr}"

        # 验证输出文件存在
        prmtop = tmpdir / "system.prmtop"
        inpcrd = tmpdir / "system.inpcrd"
        assert prmtop.exists(), "Topology file not created"
        assert inpcrd.exists(), "Coordinate file not created"

        # 验证文件非空
        assert prmtop.stat().st_size > 0, "Topology file is empty"
        assert inpcrd.stat().st_size > 0, "Coordinate file is empty"


@pytest.mark.integration
def test_sander_integration(require_amber_tool, amber_tool_paths, md_configs):
    """测试 sander 工具真实调用"""
    require_amber_tool("sander", "core")

    # 使用现有的测试输出（如果存在）
    test_output = Path("tests/test_output/2cab")
    if not test_output.exists():
        pytest.skip("Test system not available. Run full workflow test first.")

    prmtop = test_output / "system.prmtop"
    inpcrd = test_output / "system.inpcrd"

    if not (prmtop.exists() and inpcrd.exists()):
        pytest.skip("System files not available")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # 运行最小化（使用完整路径）
        result = subprocess.run(
            [
                amber_tool_paths["sander"],
                "-O",
                "-i", str(md_configs["min"]),
                "-o", str(tmpdir / "min.out"),
                "-p", str(prmtop),
                "-c", str(inpcrd),
                "-r", str(tmpdir / "min.rst"),
            ],
            capture_output=True,
            text=True,
        )

        # 验证执行成功
        assert result.returncode == 0, f"sander failed: {result.stderr}"

        # 验证输出文件存在
        min_out = tmpdir / "min.out"
        min_rst = tmpdir / "min.rst"
        assert min_out.exists(), "Minimization output not created"
        assert min_rst.exists(), "Minimization restart not created"

        # 验证输出包含正常完成标记
        output_content = min_out.read_text()
        assert "Final" in output_content or "FINAL" in output_content, \
            "Minimization did not complete normally"


@pytest.mark.integration
def test_cpptraj_integration(require_amber_tool, amber_tool_paths):
    """测试 cpptraj 工具真实调用"""
    require_amber_tool("cpptraj", "core")

    # 使用现有的测试输出
    test_output = Path("tests/test_output/2cab")
    if not test_output.exists():
        pytest.skip("Test system not available")

    prmtop = test_output / "system.prmtop"
    if not prmtop.exists():
        pytest.skip("Topology file not available")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # 创建 cpptraj 脚本
        cpptraj_script = tmpdir / "cpptraj.in"
        cpptraj_script.write_text("""
parm system.prmtop
parminfo
quit
""")

        # 运行 cpptraj（使用完整路径）
        result = subprocess.run(
            [amber_tool_paths["cpptraj"], "-i", str(cpptraj_script)],
            cwd=test_output,
            capture_output=True,
            text=True,
        )

        # 验证执行成功
        assert result.returncode == 0, f"cpptraj failed: {result.stderr}"

        # 验证输出包含拓扑信息
        assert "atoms" in result.stdout.lower(), "No topology info in output"


@pytest.mark.integration
def test_antechamber_integration(require_amber_tool, amber_tool_paths):
    """测试 antechamber 工具真实调用"""
    require_amber_tool("antechamber", "ligand")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # 创建简单的 MOL2 文件（甲烷）
        mol2_file = tmpdir / "methane.mol2"
        mol2_file.write_text("""@<TRIPOS>MOLECULE
methane
5 4 0 0 0
SMALL
GASTEIGER

@<TRIPOS>ATOM
      1 C           0.0000    0.0000    0.0000 C.3     1  LIG1        0.0000
      2 H           0.6300    0.6300    0.6300 H       1  LIG1        0.0000
      3 H          -0.6300   -0.6300    0.6300 H       1  LIG1        0.0000
      4 H          -0.6300    0.6300   -0.6300 H       1  LIG1        0.0000
      5 H           0.6300   -0.6300   -0.6300 H       1  LIG1        0.0000
@<TRIPOS>BOND
     1     1     2    1
     2     1     3    1
     3     1     4    1
     4     1     5    1
""")

        # 运行 antechamber（使用完整路径）
        result = subprocess.run(
            [
                amber_tool_paths["antechamber"],
                "-i", str(mol2_file),
                "-fi", "mol2",
                "-o", str(tmpdir / "methane.ac"),
                "-fo", "ac",
                "-c", "bcc",
                "-nc", "0",
            ],
            capture_output=True,
            text=True,
        )

        # 验证执行成功
        assert result.returncode == 0, f"antechamber failed: {result.stderr}"

        # 验证输出文件存在
        output = tmpdir / "methane.ac"
        assert output.exists(), "AC file not created"
        assert output.stat().st_size > 0, "AC file is empty"


@pytest.mark.integration
def test_reduce_integration(require_amber_tool, amber_tool_paths, sample_pdb):
    """测试 reduce 工具真实调用"""
    require_amber_tool("reduce", "auxiliary")

    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "reduced.pdb"

        # 运行 reduce（使用完整路径）
        result = subprocess.run(
            [amber_tool_paths["reduce"], str(sample_pdb)],
            capture_output=True,
            text=True,
        )

        # 验证执行成功
        assert result.returncode == 0, f"reduce failed: {result.stderr}"

        # 验证输出包含 ATOM 记录
        assert "ATOM" in result.stdout, "No ATOM records in output"


@pytest.mark.integration
def test_parmed_integration(require_amber_tool, amber_tool_paths):
    """测试 parmed 工具真实调用"""
    require_amber_tool("parmed", "auxiliary")

    # 使用现有的测试输出
    test_output = Path("tests/test_output/2cab")
    if not test_output.exists():
        pytest.skip("Test system not available")

    prmtop = test_output / "system.prmtop"
    if not prmtop.exists():
        pytest.skip("Topology file not available")

    # 运行 parmed（打印信息，使用完整路径）
    # parmed 使用交互式命令，通过 stdin 传入
    result = subprocess.run(
        [amber_tool_paths["parmed"], "-p", str(prmtop)],
        input="summary\nquit\n",
        capture_output=True,
        text=True,
    )

    # 验证执行成功
    assert result.returncode == 0, f"parmed failed: {result.stderr}"

    # 验证输出包含拓扑信息（parmed 成功加载文件就算通过）
    assert "Loaded" in result.stdout or "loaded" in result.stdout, \
        "Topology file not loaded"

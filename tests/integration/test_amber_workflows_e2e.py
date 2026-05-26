"""End-to-end workflow tests for AMBER pipelines"""
import pytest
import subprocess
from pathlib import Path
import tempfile


@pytest.mark.integration
@pytest.mark.slow
def test_simple_protein_preparation_workflow(require_amber_tool, sample_pdb):
    """测试简单蛋白质准备工作流（pdb4amber + tleap）"""
    require_amber_tool("pdb4amber", "core")
    require_amber_tool("tleap", "core")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Step 1: 清理 PDB
        cleaned_pdb = tmpdir / "cleaned.pdb"
        result = subprocess.run(
            ["pdb4amber", "-i", str(sample_pdb), "-o", str(cleaned_pdb)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"pdb4amber failed: {result.stderr}"
        assert cleaned_pdb.exists()

        # Step 2: 使用 tleap 构建系统
        leap_script = tmpdir / "leap.in"
        leap_script.write_text("""source leaprc.protein.ff14SB
source leaprc.water.tip3p

mol = loadPdb cleaned.pdb
check mol
saveAmberParm mol system.prmtop system.inpcrd
savePdb mol system.pdb
quit
""")

        result = subprocess.run(
            ["tleap", "-f", str(leap_script)],
            cwd=tmpdir,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"tleap failed: {result.stderr}"

        # 验证输出文件
        prmtop = tmpdir / "system.prmtop"
        inpcrd = tmpdir / "system.inpcrd"
        assert prmtop.exists(), "Topology not created"
        assert inpcrd.exists(), "Coordinates not created"
        assert prmtop.stat().st_size > 0
        assert inpcrd.stat().st_size > 0


@pytest.mark.integration
@pytest.mark.slow
def test_complete_md_workflow(require_amber_tool, sample_pdb, md_configs):
    """测试完整 MD 工作流（准备 + 最小化 + 分析）"""
    require_amber_tool("pdb4amber", "core")
    require_amber_tool("tleap", "core")
    require_amber_tool("sander", "core")
    require_amber_tool("cpptraj", "core")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Step 1: 清理 PDB
        cleaned_pdb = tmpdir / "cleaned.pdb"
        subprocess.run(
            ["pdb4amber", "-i", str(sample_pdb), "-o", str(cleaned_pdb)],
            capture_output=True,
            check=True,
        )

        # Step 2: 构建系统
        leap_script = tmpdir / "leap.in"
        leap_script.write_text("""
source leaprc.protein.ff14SB
source leaprc.water.tip3p

mol = loadPdb cleaned.pdb
check mol
saveAmberParm mol system.prmtop system.inpcrd
quit
""")

        subprocess.run(
            ["tleap", "-f", str(leap_script)],
            cwd=tmpdir,
            capture_output=True,
            check=True,
        )

        prmtop = tmpdir / "system.prmtop"
        inpcrd = tmpdir / "system.inpcrd"

        # Step 3: 运行最小化
        subprocess.run(
            [
                "sander",
                "-O",
                "-i", str(md_configs["min"]),
                "-o", str(tmpdir / "min.out"),
                "-p", str(prmtop),
                "-c", str(inpcrd),
                "-r", str(tmpdir / "min.rst"),
            ],
            capture_output=True,
            check=True,
        )

        min_out = tmpdir / "min.out"
        min_rst = tmpdir / "min.rst"
        assert min_out.exists()
        assert min_rst.exists()

        # Step 4: 使用 cpptraj 分析
        cpptraj_script = tmpdir / "cpptraj.in"
        cpptraj_script.write_text(f"""
parm {prmtop}
trajin {min_rst}
rmsd first
quit
""")

        result = subprocess.run(
            ["cpptraj", "-i", str(cpptraj_script)],
            cwd=tmpdir,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"cpptraj failed: {result.stderr}"

        # 验证工作流完成
        assert "RMSD" in result.stdout or "rmsd" in result.stdout.lower(), \
            "RMSD analysis not found in output"

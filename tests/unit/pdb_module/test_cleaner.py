"""Tests for PDB cleaner."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import tempfile
import os


class TestPDBCleaner:
    """Test PDBCleaner class."""
    
    def test_init_default(self):
        from mdpilot.tools.builtin.pdb.cleaner import PDBCleaner
        
        cleaner = PDBCleaner()
        
        assert cleaner.keep_conect is True
        assert cleaner.keep_link is True
    
    def test_init_custom(self):
        from mdpilot.tools.builtin.pdb.cleaner import PDBCleaner
        
        cleaner = PDBCleaner(keep_conect=False, keep_link=False)
        
        assert cleaner.keep_conect is False
        assert cleaner.keep_link is False
    
    def test_clean_basic(self):
        from mdpilot.tools.builtin.pdb.cleaner import PDBCleaner
        
        pdb_content = """ATOM      1  CA  ALA A   1       0.000   0.000   0.000
HETATM    2  ZN  ZN  A 101       1.000   1.000   1.000
TER
END
"""
        cleaner = PDBCleaner()
        result = cleaner.clean(pdb_content)
        
        assert "ATOM" in result
        assert "HETATM" in result
        assert "TER" in result
        assert "END" in result
    
    def test_clean_removes_header(self):
        from mdpilot.tools.builtin.pdb.cleaner import PDBCleaner
        
        pdb_content = """HEADER    TEST PROTEIN
TITLE     TEST
ATOM      1  CA  ALA A   1       0.000   0.000   0.000
END
"""
        cleaner = PDBCleaner()
        result = cleaner.clean(pdb_content)
        
        assert "HEADER" not in result
        assert "TITLE" not in result
        assert "ATOM" in result
    
    def test_clean_keeps_conect(self):
        from mdpilot.tools.builtin.pdb.cleaner import PDBCleaner
        
        pdb_content = """ATOM      1  CA  ALA A   1       0.000   0.000   0.000
CONECT    1    2
END
"""
        cleaner = PDBCleaner(keep_conect=True)
        result = cleaner.clean(pdb_content)
        
        assert "CONECT" in result
    
    def test_clean_removes_conect(self):
        from mdpilot.tools.builtin.pdb.cleaner import PDBCleaner
        
        pdb_content = """ATOM      1  CA  ALA A   1       0.000   0.000   0.000
CONECT    1    2
END
"""
        cleaner = PDBCleaner(keep_conect=False)
        result = cleaner.clean(pdb_content)
        
        assert "CONECT" not in result
    
    def test_clean_keeps_link(self):
        from mdpilot.tools.builtin.pdb.cleaner import PDBCleaner
        
        pdb_content = """ATOM      1  CA  ALA A   1       0.000   0.000   0.000
LINK         SG  CYS A   1                 SG  CYS A   2
END
"""
        cleaner = PDBCleaner(keep_link=True)
        result = cleaner.clean(pdb_content)
        
        assert "LINK" in result
    
    def test_clean_removes_link(self):
        from mdpilot.tools.builtin.pdb.cleaner import PDBCleaner
        
        pdb_content = """ATOM      1  CA  ALA A   1       0.000   0.000   0.000
LINK         SG  CYS A   1                 SG  CYS A   2
END
"""
        cleaner = PDBCleaner(keep_link=False)
        result = cleaner.clean(pdb_content)
        
        assert "LINK" not in result
    
    def test_clean_adds_end_if_missing(self):
        from mdpilot.tools.builtin.pdb.cleaner import PDBCleaner
        
        pdb_content = """ATOM      1  CA  ALA A   1       0.000   0.000   0.000
"""
        cleaner = PDBCleaner()
        result = cleaner.clean(pdb_content)
        
        assert result.endswith("END")
    
    def test_clean_skips_empty_lines(self):
        from mdpilot.tools.builtin.pdb.cleaner import PDBCleaner
        
        pdb_content = """ATOM      1  CA  ALA A   1       0.000   0.000   0.000

ATOM      2  CA  ALA A   2       1.000   1.000   1.000

END
"""
        cleaner = PDBCleaner()
        result = cleaner.clean(pdb_content)
        
        lines = result.split("\n")
        assert all(line.strip() for line in lines)
    
    def test_clean_file(self, tmp_path):
        from mdpilot.tools.builtin.pdb.cleaner import PDBCleaner
        
        input_file = tmp_path / "input.pdb"
        output_file = tmp_path / "output.pdb"
        
        input_file.write_text("""HEADER    TEST
ATOM      1  CA  ALA A   1       0.000   0.000   0.000
END
""")
        
        cleaner = PDBCleaner()
        cleaner.clean_file(input_file, output_file)
        
        assert output_file.exists()
        content = output_file.read_text()
        assert "HEADER" not in content
        assert "ATOM" in content
    
    def test_clean_file_creates_parent_dirs(self, tmp_path):
        from mdpilot.tools.builtin.pdb.cleaner import PDBCleaner
        
        input_file = tmp_path / "input.pdb"
        output_file = tmp_path / "subdir" / "output.pdb"
        
        input_file.write_text("ATOM      1  CA  ALA A   1       0.000   0.000   0.000\nEND\n")
        
        cleaner = PDBCleaner()
        cleaner.clean_file(input_file, output_file)
        
        assert output_file.exists()
    
    def test_clean_file_atomic_write(self, tmp_path):
        from mdpilot.tools.builtin.pdb.cleaner import PDBCleaner
        
        input_file = tmp_path / "input.pdb"
        output_file = tmp_path / "output.pdb"
        
        input_file.write_text("ATOM      1  CA  ALA A   1       0.000   0.000   0.000\nEND\n")
        
        cleaner = PDBCleaner()
        
        with patch('os.fdopen', side_effect=Exception("write failed")):
            with pytest.raises(Exception, match="write failed"):
                cleaner.clean_file(input_file, output_file)
        
        assert not output_file.exists()
    
    def test_remove_waters(self):
        from mdpilot.tools.builtin.pdb.cleaner import PDBCleaner
        
        pdb_content = """ATOM      1  CA  ALA A   1       0.000   0.000   0.000
HETATM    2  O   HOH A 101       1.000   1.000   1.000
HETATM    3  O   WAT A 102       2.000   2.000   2.000
END
"""
        cleaner = PDBCleaner()
        result = cleaner.remove_waters(pdb_content)
        
        assert "ALA" in result
        assert "HOH" not in result
        assert "WAT" not in result
    
    def test_remove_waters_all_types(self):
        from mdpilot.tools.builtin.pdb.cleaner import PDBCleaner
        
        pdb_content = """ATOM      1  CA  ALA A   1       0.000   0.000   0.000
HETATM    2  O   HOH A 101       1.000   1.000   1.000
HETATM    3  O   WAT A 102       2.000   2.000   2.000
HETATM    4  O   H2O A 103       3.000   3.000   3.000
HETATM    5  O   TIP A 104       4.000   4.000   4.000
HETATM    6  O   TIP3A 105       5.000   5.000   5.000
HETATM    7  O   SOL A 106       6.000   6.000   6.000
END
"""
        cleaner = PDBCleaner()
        result = cleaner.remove_waters(pdb_content)
        
        assert "ALA" in result
        for water in ["HOH", "WAT", "H2O", "TIP", "TIP3", "SOL"]:
            assert water not in result
    
    def test_remove_heteroatoms_keep_metals(self):
        from mdpilot.tools.builtin.pdb.cleaner import PDBCleaner
        
        pdb_content = """ATOM      1  CA  ALA A   1       0.000   0.000   0.000
HETATM    2  ZN  ZN  A 101       1.000   1.000   1.000
HETATM    3  C   LIG A 102       2.000   2.000   2.000
END
"""
        cleaner = PDBCleaner()
        result = cleaner.remove_heteroatoms(pdb_content, keep_metals=True)
        
        assert "ALA" in result
        assert "ZN" in result
        assert "LIG" not in result
    
    def test_remove_heteroatoms_remove_all(self):
        from mdpilot.tools.builtin.pdb.cleaner import PDBCleaner
        
        pdb_content = """ATOM      1  CA  ALA A   1       0.000   0.000   0.000
HETATM    2  ZN  ZN  A 101       1.000   1.000   1.000
HETATM    3  C   LIG A 102       2.000   2.000   2.000
END
"""
        cleaner = PDBCleaner()
        result = cleaner.remove_heteroatoms(pdb_content, keep_metals=False)
        
        assert "ALA" in result
        assert "ZN" not in result
        assert "LIG" not in result
    
    def test_remove_heteroatoms_all_metals(self):
        from mdpilot.tools.builtin.pdb.cleaner import PDBCleaner
        
        metals = ["ZN", "FE", "CA", "MG", "MN", "CU", "CO", "NI", "K", "NA", "CL"]
        pdb_lines = ["ATOM      1  CA  ALA A   1       0.000   0.000   0.000"]
        
        for i, metal in enumerate(metals, start=2):
            pdb_lines.append(f"HETATM{i:5d}  {metal:<2}  {metal:<3} A{100+i:4d}       1.000   1.000   1.000")
        
        pdb_lines.append("END")
        pdb_content = "\n".join(pdb_lines)
        
        cleaner = PDBCleaner()
        result = cleaner.remove_heteroatoms(pdb_content, keep_metals=True)
        
        for metal in metals:
            assert metal in result
    
    def test_extract_chain(self):
        from mdpilot.tools.builtin.pdb.cleaner import PDBCleaner
        
        pdb_content = """ATOM      1  CA  ALA A   1       0.000   0.000   0.000
ATOM      2  CA  ALA B   1       1.000   1.000   1.000
ATOM      3  CA  ALA C   1       2.000   2.000   2.000
END
"""
        cleaner = PDBCleaner()
        result = cleaner.extract_chain(pdb_content, "B")
        
        lines = [l for l in result.split("\n") if l.startswith("ATOM")]
        assert len(lines) == 1
        assert "B" in lines[0]
    
    def test_extract_chain_with_hetatm(self):
        from mdpilot.tools.builtin.pdb.cleaner import PDBCleaner
        
        pdb_content = """ATOM      1  CA  ALA A   1       0.000   0.000   0.000
HETATM    2  ZN  ZN  A 101       1.000   1.000   1.000
ATOM      3  CA  ALA B   1       2.000   2.000   2.000
HETATM    4  ZN  ZN  B 101       3.000   3.000   3.000
END
"""
        cleaner = PDBCleaner()
        result = cleaner.extract_chain(pdb_content, "A")
        
        lines = [l for l in result.split("\n") if l.startswith(("ATOM", "HETATM"))]
        assert len(lines) == 2
        assert all(" A " in l for l in lines)
        assert "B" not in result
    
    def test_extract_chain_keeps_other_records(self):
        from mdpilot.tools.builtin.pdb.cleaner import PDBCleaner
        
        pdb_content = """ATOM      1  CA  ALA A   1       0.000   0.000   0.000
TER
CONECT    1    2
END
"""
        cleaner = PDBCleaner()
        result = cleaner.extract_chain(pdb_content, "A")
        
        assert "TER" in result
        assert "CONECT" in result
        assert "END" in result
    
    def test_renumber_residues_default(self):
        from mdpilot.tools.builtin.pdb.cleaner import PDBCleaner
        
        pdb_content = """ATOM      1  CA  ALA A  10       0.000   0.000   0.000
ATOM      2  CB  ALA A  10       1.000   1.000   1.000
ATOM      3  CA  GLY A  20       2.000   2.000   2.000
END
"""
        cleaner = PDBCleaner()
        result = cleaner.renumber_residues(pdb_content)
        
        lines = result.split("\n")
        assert "   1" in lines[0]
        assert "   1" in lines[1]
        assert "   2" in lines[2]
    
    def test_renumber_residues_custom_start(self):
        from mdpilot.tools.builtin.pdb.cleaner import PDBCleaner
        
        pdb_content = """ATOM      1  CA  ALA A  10       0.000   0.000   0.000
ATOM      2  CA  GLY A  20       1.000   1.000   1.000
END
"""
        cleaner = PDBCleaner()
        result = cleaner.renumber_residues(pdb_content, start=100)
        
        lines = result.split("\n")
        assert " 100" in lines[0]
        assert " 101" in lines[1]
    
    def test_renumber_residues_preserves_other_records(self):
        from mdpilot.tools.builtin.pdb.cleaner import PDBCleaner
        
        pdb_content = """ATOM      1  CA  ALA A  10       0.000   0.000   0.000
TER
END
"""
        cleaner = PDBCleaner()
        result = cleaner.renumber_residues(pdb_content)
        
        assert "TER" in result
        assert "END" in result
    
    def test_renumber_residues_hetatm(self):
        from mdpilot.tools.builtin.pdb.cleaner import PDBCleaner
        
        pdb_content = """ATOM      1  CA  ALA A  10       0.000   0.000   0.000
HETATM    2  ZN  ZN  A 999       1.000   1.000   1.000
END
"""
        cleaner = PDBCleaner()
        result = cleaner.renumber_residues(pdb_content)
        
        lines = result.split("\n")
        assert "   1" in lines[0]
        assert "   2" in lines[1]


class TestPDBCleanerIntegration:
    """Integration tests for PDBCleaner."""
    
    def test_full_cleaning_pipeline(self):
        from mdpilot.tools.builtin.pdb.cleaner import PDBCleaner
        
        pdb_content = """HEADER    TEST PROTEIN
TITLE     INTEGRATION TEST
ATOM      1  CA  ALA A   1       0.000   0.000   0.000
HETATM    2  O   HOH A 101       1.000   1.000   1.000
HETATM    3  ZN  ZN  A 102       2.000   2.000   2.000
HETATM    4  C   LIG A 103       3.000   3.000   3.000
CONECT    1    3
END
"""
        cleaner = PDBCleaner()
        
        result = cleaner.clean(pdb_content)
        result = cleaner.remove_waters(result)
        result = cleaner.remove_heteroatoms(result, keep_metals=True)
        
        assert "HEADER" not in result
        assert "ALA" in result
        assert "HOH" not in result
        assert "ZN" in result
        assert "LIG" not in result
        assert "CONECT" in result

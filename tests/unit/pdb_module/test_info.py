"""Tests for PDB information extractor."""
import pytest
from pathlib import Path
from mdpilot.tools.builtin.pdb.info import PDBInfo


# Sample PDB content for testing
SIMPLE_PDB = """HEADER    HYDROLASE                               01-JAN-00   1AKI
TITLE     STRUCTURE OF ADENYLATE KINASE
SOURCE    MOL_ID: 1;
SOURCE   2 ORGANISM_SCIENTIFIC: ESCHERICHIA COLI;
REMARK   2 RESOLUTION.    2.00 ANGSTROMS.
ATOM      1  N   MET A   1      27.340  24.430   2.614  1.00  9.67           N
ATOM      2  CA  MET A   1      26.266  25.413   2.842  1.00 10.38           C
ATOM      3  C   MET A   1      26.913  26.639   3.531  1.00  9.62           C
ATOM      4  O   MET A   1      27.886  26.463   4.263  1.00  9.62           O
ATOM      5  CB  MET A   1      25.112  24.880   3.649  1.00 13.77           C
ATOM      6  N   ALA A   2      26.340  27.830   3.314  1.00  8.50           N
ATOM      7  CA  ALA A   2      26.850  29.070   3.890  1.00  8.90           C
ATOM      8  C   ALA A   2      28.200  29.450   3.290  1.00  8.20           C
ATOM      9  O   ALA A   2      28.900  28.600   2.730  1.00  8.10           O
ATOM     10  CB  ALA A   2      25.850  30.200   3.700  1.00  9.50           C
END
"""

MULTI_CHAIN_PDB = """HEADER    PROTEIN
TITLE     MULTI-CHAIN PROTEIN
ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  1.00           N
ATOM      2  CA  ALA A   1       1.000   1.000   1.000  1.00  1.00           C
ATOM      3  N   ALA B   1       2.000   2.000   2.000  1.00  1.00           N
ATOM      4  CA  ALA B   1       3.000   3.000   3.000  1.00  1.00           C
ATOM      5  N   ALA C   1       4.000   4.000   4.000  1.00  1.00           N
ATOM      6  CA  ALA C   1       5.000   5.000   5.000  1.00  1.00           C
END
"""

METAL_PDB = """HEADER    METALLOPROTEIN
TITLE     PROTEIN WITH ZINC
ATOM      1  N   CYS A   1       0.000   0.000   0.000  1.00  1.00           N
ATOM      2  CA  CYS A   1       1.000   1.000   1.000  1.00  1.00           C
ATOM      3  N   HIS A   2       2.000   2.000   2.000  1.00  1.00           N
ATOM      4  CA  HIS A   2       3.000   3.000   3.000  1.00  1.00           C
HETATM 1001 ZN    ZN A 101       5.000   5.000   5.000  1.00 20.00          ZN
HETATM 1002 FE    FE A 102       6.000   6.000   6.000  1.00 20.00          FE
END
"""

LIGAND_PDB = """HEADER    PROTEIN-LIGAND COMPLEX
TITLE     PROTEIN WITH SMALL MOLECULE LIGAND
ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  1.00           N
ATOM      2  CA  ALA A   1       1.000   1.000   1.000  1.00  1.00           C
ATOM      3  N   ALA A   2       2.000   2.000   2.000  1.00  1.00           N
ATOM      4  CA  ALA A   2       3.000   3.000   3.000  1.00  1.00           C
HETATM 2001  C1  LIG A 201       5.000   5.000   5.000  1.00 20.00           C
HETATM 2002  C2  LIG A 201       6.000   6.000   6.000  1.00 20.00           C
HETATM 2003  O1  LIG A 201       7.000   7.000   7.000  1.00 20.00           O
HETATM 3001  O   HOH A 301       8.000   8.000   8.000  1.00 30.00           O
HETATM 3002  O   HOH A 302       9.000   9.000   9.000  1.00 30.00           O
END
"""

NMR_PDB = """HEADER    NMR STRUCTURE
TITLE     NMR SOLUTION STRUCTURE
SOURCE    MOL_ID: 1;
SOURCE   2 ORGANISM_SCIENTIFIC: HOMO SAPIENS;
REMARK   2 RESOLUTION. NOT APPLICABLE.
ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  1.00           N
ATOM      2  CA  ALA A   1       1.000   1.000   1.000  1.00  1.00           C
END
"""

NUCLEOTIDE_PDB = """HEADER    DNA
TITLE     DNA STRUCTURE
ATOM      1  P    DA A   1       0.000   0.000   0.000  1.00  1.00           P
ATOM      2  O5'  DA A   1       1.000   1.000   1.000  1.00  1.00           O
ATOM      3  P    DC A   2       2.000   2.000   2.000  1.00  1.00           P
ATOM      4  O5'  DC A   2       3.000   3.000   3.000  1.00  1.00           O
ATOM      5  P    DG A   3       4.000   4.000   4.000  1.00  1.00           P
ATOM      6  O5'  DG A   3       5.000   5.000   5.000  1.00  1.00           O
END
"""

LONG_TITLE_PDB = """HEADER    PROTEIN
TITLE     THIS IS A VERY LONG TITLE THAT EXCEEDS SIXTY CHARACTERS AND
TITLE    2 SHOULD BE TRUNCATED IN THE STRING REPRESENTATION
ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  1.00           N
END
"""


# ============================================================================
# from_pdb Tests
# ============================================================================

class TestPDBInfoFromPDB:
    """Test PDBInfo.from_pdb() method."""
    
    def test_from_pdb_simple(self):
        """Test extracting info from simple PDB."""
        info = PDBInfo.from_pdb(SIMPLE_PDB)
        
        assert info.pdb_id == "1AKI"
        assert "ADENYLATE KINASE" in info.title
        assert info.organism == "ESCHERICHIA COLI"
        assert info.resolution == 2.00
        assert info.chains == ["A"]
        assert info.num_atoms == 10
        assert info.num_residues == 2
        assert not info.has_metals
        assert not info.has_ligands
    
    def test_from_pdb_multi_chain(self):
        """Test extracting chains from multi-chain PDB."""
        info = PDBInfo.from_pdb(MULTI_CHAIN_PDB)
        
        assert info.chains == ["A", "B", "C"]
        assert info.num_atoms == 6
        assert info.num_residues == 3
    
    def test_from_pdb_with_metals(self):
        """Test detecting metal ions."""
        info = PDBInfo.from_pdb(METAL_PDB)
        
        assert info.has_metals
        assert "ZN" in info.metal_ions
        assert "FE" in info.metal_ions
        assert len(info.metal_ions) == 2
    
    def test_from_pdb_with_ligands(self):
        """Test detecting ligands."""
        info = PDBInfo.from_pdb(LIGAND_PDB)
        
        assert info.has_ligands
        assert "LIG" in info.ligands
        assert len(info.ligands) == 1
    
    def test_from_pdb_excludes_water(self):
        """Test that water molecules are not counted as ligands."""
        info = PDBInfo.from_pdb(LIGAND_PDB)
        
        assert "HOH" not in info.ligands
        assert "WAT" not in info.ligands
    
    def test_from_pdb_nmr_structure(self):
        """Test NMR structure (no resolution)."""
        info = PDBInfo.from_pdb(NMR_PDB)
        
        assert info.resolution is None
        assert info.organism == "HOMO SAPIENS"
    
    def test_from_pdb_nucleotides(self):
        """Test DNA/RNA structures."""
        info = PDBInfo.from_pdb(NUCLEOTIDE_PDB)
        
        assert info.num_atoms == 6
        assert info.num_residues == 3
        assert not info.has_ligands
    
    def test_from_pdb_empty_chains(self):
        """Test handling of atoms without chain identifiers."""
        pdb_no_chain = """HEADER    TEST
ATOM      1  N   ALA     1       0.000   0.000   0.000  1.00  1.00           N
ATOM      2  CA  ALA     1       1.000   1.000   1.000  1.00  1.00           C
END
"""
        info = PDBInfo.from_pdb(pdb_no_chain)
        
        assert info.chains == []
        assert info.num_atoms == 2
    
    def test_from_pdb_counts_residues_correctly(self):
        """Test residue counting with multiple atoms per residue."""
        pdb_multi_atom = """HEADER    TEST
ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  1.00           N
ATOM      2  CA  ALA A   1       1.000   1.000   1.000  1.00  1.00           C
ATOM      3  C   ALA A   1       2.000   2.000   2.000  1.00  1.00           C
ATOM      4  O   ALA A   1       3.000   3.000   3.000  1.00  1.00           O
ATOM      5  CB  ALA A   1       4.000   4.000   4.000  1.00  1.00           C
END
"""
        info = PDBInfo.from_pdb(pdb_multi_atom)
        
        assert info.num_atoms == 5
        assert info.num_residues == 1
    
    def test_from_pdb_multiple_title_lines(self):
        """Test concatenating multiple TITLE lines."""
        pdb_multi_title = """HEADER    TEST
TITLE     FIRST PART OF TITLE
TITLE    2 SECOND PART OF TITLE
TITLE    3 THIRD PART OF TITLE
ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  1.00           N
END
"""
        info = PDBInfo.from_pdb(pdb_multi_title)
        
        assert "FIRST PART" in info.title
        assert "SECOND PART" in info.title
        assert "THIRD PART" in info.title
    
    def test_from_pdb_resolution_formats(self):
        """Test different resolution format variations."""
        pdb_res = """HEADER    TEST
REMARK   2 RESOLUTION.    1.50 ANGSTROMS.
ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  1.00           N
END
"""
        info = PDBInfo.from_pdb(pdb_res)
        
        assert info.resolution == 1.50
    
    def test_from_pdb_no_resolution_remark(self):
        """Test PDB without resolution remark."""
        pdb_no_res = """HEADER    TEST
ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  1.00           N
END
"""
        info = PDBInfo.from_pdb(pdb_no_res)
        
        assert info.resolution is None


# ============================================================================
# from_file Tests
# ============================================================================

class TestPDBInfoFromFile:
    """Test PDBInfo.from_file() method."""
    
    def test_from_file_reads_file(self, tmp_path):
        """Test reading PDB from file."""
        pdb_file = tmp_path / "test.pdb"
        pdb_file.write_text(SIMPLE_PDB)
        
        info = PDBInfo.from_file(pdb_file)
        
        assert info.pdb_id == "1AKI"
        assert info.num_atoms == 10
    
    def test_from_file_accepts_string_path(self, tmp_path):
        """Test from_file accepts string path."""
        pdb_file = tmp_path / "test.pdb"
        pdb_file.write_text(SIMPLE_PDB)
        
        info = PDBInfo.from_file(str(pdb_file))
        
        assert info.pdb_id == "1AKI"
    
    def test_from_file_accepts_path_object(self, tmp_path):
        """Test from_file accepts Path object."""
        pdb_file = tmp_path / "test.pdb"
        pdb_file.write_text(SIMPLE_PDB)
        
        info = PDBInfo.from_file(Path(pdb_file))
        
        assert info.pdb_id == "1AKI"


# ============================================================================
# __str__ Tests
# ============================================================================

class TestPDBInfoStr:
    """Test PDBInfo.__str__() method."""
    
    def test_str_basic_info(self):
        """Test string representation with basic info."""
        info = PDBInfo.from_pdb(SIMPLE_PDB)
        
        str_repr = str(info)
        
        assert "PDB ID: 1AKI" in str_repr
        assert "ADENYLATE KINASE" in str_repr
        assert "ESCHERICHIA COLI" in str_repr
        assert "2.00 Å" in str_repr
        assert "Chains: A" in str_repr
        assert "Atoms: 10" in str_repr
        assert "Residues: 2" in str_repr
    
    def test_str_with_metals(self):
        """Test string representation includes metal ions."""
        info = PDBInfo.from_pdb(METAL_PDB)
        
        str_repr = str(info)
        
        assert "Metal ions:" in str_repr
        assert "FE" in str_repr
        assert "ZN" in str_repr
    
    def test_str_with_ligands(self):
        """Test string representation includes ligands."""
        info = PDBInfo.from_pdb(LIGAND_PDB)
        
        str_repr = str(info)
        
        assert "Ligands:" in str_repr
        assert "LIG" in str_repr
    
    def test_str_nmr_structure(self):
        """Test string representation for NMR (no resolution)."""
        info = PDBInfo.from_pdb(NMR_PDB)
        
        str_repr = str(info)
        
        assert "Resolution: N/A" in str_repr
    
    def test_str_truncates_long_title(self):
        """Test long titles are truncated."""
        info = PDBInfo.from_pdb(LONG_TITLE_PDB)
        
        str_repr = str(info)
        
        assert "..." in str_repr
        assert len([line for line in str_repr.split("\n") if line.startswith("Title:")][0]) < 100
    
    def test_str_multi_chain(self):
        """Test string representation with multiple chains."""
        info = PDBInfo.from_pdb(MULTI_CHAIN_PDB)
        
        str_repr = str(info)
        
        assert "Chains: A, B, C" in str_repr


# ============================================================================
# Edge Cases and Integration Tests
# ============================================================================

class TestPDBInfoEdgeCases:
    """Test edge cases and special scenarios."""
    
    def test_empty_pdb(self):
        """Test handling of empty PDB content."""
        info = PDBInfo.from_pdb("")
        
        assert info.pdb_id == ""
        assert info.title == ""
        assert info.organism == ""
        assert info.resolution is None
        assert info.chains == []
        assert info.num_atoms == 0
        assert info.num_residues == 0
        assert not info.has_metals
        assert not info.has_ligands
    
    def test_pdb_with_only_hetatm(self):
        """Test PDB with only HETATM records."""
        pdb_hetatm_only = """HEADER    LIGAND
HETATM    1  C1  LIG A   1       0.000   0.000   0.000  1.00  1.00           C
HETATM    2  C2  LIG A   1       1.000   1.000   1.000  1.00  1.00           C
HETATM    3  O1  LIG A   1       2.000   2.000   2.000  1.00  1.00           O
END
"""
        info = PDBInfo.from_pdb(pdb_hetatm_only)
        
        assert info.num_atoms == 3
        assert info.has_ligands
        assert "LIG" in info.ligands
    
    def test_metal_ion_variations(self):
        """Test detection of various metal ion types."""
        pdb_metals = """HEADER    METALS
HETATM 1001 CA    CA A 101       0.000   0.000   0.000  1.00  1.00          CA
HETATM 1002 MG    MG A 102       1.000   1.000   1.000  1.00  1.00          MG
HETATM 1003 MN    MN A 103       2.000   2.000   2.000  1.00  1.00          MN
HETATM 1004 CU    CU A 104       3.000   3.000   3.000  1.00  1.00          CU
HETATM 1005 CO    CO A 105       4.000   4.000   4.000  1.00  1.00          CO
HETATM 1006 NI    NI A 106       5.000   5.000   5.000  1.00  1.00          NI
END
"""
        info = PDBInfo.from_pdb(pdb_metals)
        
        assert info.has_metals
        assert len(info.metal_ions) == 6
        assert "CA" in info.metal_ions
        assert "MG" in info.metal_ions
        assert "MN" in info.metal_ions
        assert "CU" in info.metal_ions
        assert "CO" in info.metal_ions
        assert "NI" in info.metal_ions
    
    def test_water_molecule_variations(self):
        """Test that various water molecule names are excluded."""
        pdb_water = """HEADER    WATER
HETATM 1001  O   HOH A 101       0.000   0.000   0.000  1.00  1.00           O
HETATM 1002  O   WAT A 102       1.000   1.000   1.000  1.00  1.00           O
HETATM 1003  O   H2O A 103       2.000   2.000   2.000  1.00  1.00           O
HETATM 1004  O   TIP A 104       3.000   3.000   3.000  1.00  1.00           O
HETATM 1005  O   TIP3 A 105      4.000   4.000   4.000  1.00  1.00           O
HETATM 1006  O   SOL A 106       5.000   5.000   5.000  1.00  1.00           O
END
"""
        info = PDBInfo.from_pdb(pdb_water)
        
        assert not info.has_ligands
        assert len(info.ligands) == 0
    
    def test_modified_amino_acids(self):
        """Test handling of modified amino acids."""
        pdb_modified = """HEADER    MODIFIED
ATOM      1  N   HIE A   1       0.000   0.000   0.000  1.00  1.00           N
ATOM      2  CA  HIE A   1       1.000   1.000   1.000  1.00  1.00           C
ATOM      3  N   HID A   2       2.000   2.000   2.000  1.00  1.00           N
ATOM      4  CA  HID A   2       3.000   3.000   3.000  1.00  1.00           C
ATOM      5  N   CYX A   3       4.000   4.000   4.000  1.00  1.00           N
ATOM      6  CA  CYX A   3       5.000   5.000   5.000  1.00  1.00           C
END
"""
        info = PDBInfo.from_pdb(pdb_modified)
        
        assert info.num_residues == 3
        assert not info.has_ligands
    
    def test_rna_nucleotides(self):
        """Test RNA nucleotide detection."""
        pdb_rna = """HEADER    RNA
ATOM      1  P    RA A   1       0.000   0.000   0.000  1.00  1.00           P
ATOM      2  O5'  RA A   1       1.000   1.000   1.000  1.00  1.00           O
ATOM      3  P    RC A   2       2.000   2.000   2.000  1.00  1.00           P
ATOM      4  O5'  RC A   2       3.000   3.000   3.000  1.00  1.00           O
ATOM      5  P    RG A   3       4.000   4.000   4.000  1.00  1.00           P
ATOM      6  O5'  RG A   3       5.000   5.000   5.000  1.00  1.00           O
ATOM      7  P    RU A   4       6.000   6.000   6.000  1.00  1.00           P
ATOM      8  O5'  RU A   4       7.000   7.000   7.000  1.00  1.00           O
END
"""
        info = PDBInfo.from_pdb(pdb_rna)
        
        assert info.num_residues == 4
        assert not info.has_ligands
    
    def test_complex_structure_with_everything(self):
        """Test complex structure with proteins, metals, ligands, and water."""
        pdb_complex = """HEADER    COMPLEX
TITLE     COMPLEX STRUCTURE WITH EVERYTHING
SOURCE    MOL_ID: 1;
SOURCE   2 ORGANISM_SCIENTIFIC: TEST ORGANISM;
REMARK   2 RESOLUTION.    1.80 ANGSTROMS.
ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  1.00           N
ATOM      2  CA  ALA A   1       1.000   1.000   1.000  1.00  1.00           C
ATOM      3  N   ALA B   1       2.000   2.000   2.000  1.00  1.00           N
ATOM      4  CA  ALA B   1       3.000   3.000   3.000  1.00  1.00           C
HETATM 1001 ZN   ZN  A 101       4.000   4.000   4.000  1.00 20.00          ZN
HETATM 2001  C1  LIG A 201       5.000   5.000   5.000  1.00 20.00           C
HETATM 2002  C2  LIG A 201       6.000   6.000   6.000  1.00 20.00           C
HETATM 3001  O   HOH A 301       7.000   7.000   7.000  1.00 30.00           O
END
"""
        info = PDBInfo.from_pdb(pdb_complex)
        
        assert info.pdb_id == ""
        assert "COMPLEX STRUCTURE" in info.title
        assert info.organism == "TEST ORGANISM"
        assert info.resolution == 1.80
        assert info.chains == ["A", "B"]
        assert info.num_atoms == 8
        assert info.num_residues == 5  # 2 protein + ZN + LIG + HOH
        assert info.has_metals
        assert "ZN" in info.metal_ions
        assert info.has_ligands
        assert "LIG" in info.ligands

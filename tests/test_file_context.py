"""Tests for FileContext."""

import pytest
from pathlib import Path
from mdpilot.tools.file_context import FileContext, FileEntry, detect_file_type


class TestFileEntry:
    """Test FileEntry dataclass."""
    
    def test_name_property(self):
        entry = FileEntry(
            path="/path/to/file.pdb",
            produced_by="pdb4amber",
            step="clean",
            file_type="pdb"
        )
        assert entry.name == "file.pdb"
    
    def test_exists_false_for_nonexistent_file(self):
        entry = FileEntry(
            path="/nonexistent/file.pdb",
            produced_by="test",
            step="test_step",
            file_type="pdb"
        )
        assert entry.exists is False


class TestFileContext:
    """Test FileContext class."""
    
    def test_init_empty(self):
        ctx = FileContext()
        assert len(ctx._files) == 0
    
    def test_add_file(self):
        ctx = FileContext()
        ctx.add_file("test.pdb", "pdb4amber", "clean", "pdb")
        
        assert len(ctx._files) == 1
        assert ctx._files[0].produced_by == "pdb4amber"
        assert ctx._files[0].file_type == "pdb"
    
    def test_add_file_calculates_size_for_existing_file(self, tmp_path):
        # Create a real file
        test_file = tmp_path / "test.pdb"
        test_file.write_text("ATOM      1  CA  ALA A   1")
        
        ctx = FileContext()
        ctx.add_file(str(test_file), "test_tool", "test_step", "pdb")
        
        # Should have calculated size
        assert len(ctx._files) == 1
        assert ctx._files[0].size_bytes > 0
    
    def test_get_recommended_files_by_type(self):
        ctx = FileContext()
        ctx.add_file("file1.pdb", "tool1", "step1", "pdb")
        ctx.add_file("file2.prmtop", "tool2", "step2", "prmtop")
        ctx.add_file("file3.pdb", "tool3", "step3", "pdb")
        
        pdb_files = ctx.get_recommended_files(file_type="pdb")
        assert len(pdb_files) == 2
        assert all(f.file_type == "pdb" for f in pdb_files)
    
    def test_get_recommended_files_by_extension(self):
        ctx = FileContext()
        ctx.add_file("file1.pdb", "tool1", "step1", "pdb")
        ctx.add_file("file2.prmtop", "tool2", "step2", "prmtop")
        
        prmtop_files = ctx.get_recommended_files(filter_ext=".prmtop")
        assert len(prmtop_files) == 1
        assert prmtop_files[0].path.endswith(".prmtop")
    
    def test_get_recommended_files_no_after_step(self):
        ctx = FileContext()
        ctx.add_file("file1.pdb", "tool1", "step1", "pdb")
        ctx.add_file("file2.pdb", "tool2", "step2", "pdb")
        ctx.add_file("file3.pdb", "tool3", "step3", "pdb")
        
        # Without after_step, should get all files in reverse order
        files = ctx.get_recommended_files()
        assert len(files) == 3
        assert files[0].step == "step3"  # Newest first
    
    def test_get_recommended_files_after_nonexistent_step(self):
        ctx = FileContext()
        ctx.add_file("file1.pdb", "tool1", "step1", "pdb")
        
        # After a step that doesn't exist - should return empty
        files = ctx.get_recommended_files(after_step="nonexistent")
        assert len(files) == 0
    
    def test_get_recommended_files_after_existing_step(self):
        ctx = FileContext()
        ctx.add_file("file1.pdb", "tool1", "step1", "pdb")
        ctx.add_file("file2.pdb", "tool2", "step2", "pdb")
        ctx.add_file("file3.pdb", "tool3", "step3", "pdb")
        
        # After step2, should only get files from step1 (reversed order)
        files = ctx.get_recommended_files(after_step="step2")
        assert len(files) == 1
        assert files[0].step == "step1"
    
    def test_get_latest(self):
        ctx = FileContext()
        ctx.add_file("file1.pdb", "tool1", "step1", "pdb")
        ctx.add_file("file2.pdb", "tool2", "step2", "pdb")
        
        latest = ctx.get_latest(file_type="pdb")
        assert latest is not None
        assert latest.step == "step2"
    
    def test_get_latest_no_match(self):
        ctx = FileContext()
        ctx.add_file("file1.pdb", "tool1", "step1", "pdb")
        
        latest = ctx.get_latest(file_type="prmtop")
        assert latest is None
    
    def test_get_pipeline_summary_empty(self):
        ctx = FileContext()
        summary = ctx.get_pipeline_summary()
        assert "(no files in pipeline)" in summary
    
    def test_get_pipeline_summary_with_files(self):
        ctx = FileContext()
        ctx.add_file("file1.pdb", "pdb4amber", "clean", "pdb")
        ctx.add_file("file2.prmtop", "tleap", "build", "prmtop")
        
        summary = ctx.get_pipeline_summary()
        assert "File pipeline:" in summary
        assert "pdb4amber" in summary
        assert "tleap" in summary
    
    def test_files_property(self):
        ctx = FileContext()
        ctx.add_file("file1.pdb", "tool1", "step1", "pdb")
        
        files = ctx.files
        assert len(files) == 1
        assert isinstance(files, list)
    
    def test_clear(self):
        ctx = FileContext()
        ctx.add_file("file1.pdb", "tool1", "step1", "pdb")
        ctx.clear()
        
        assert len(ctx._files) == 0


class TestDetectFileType:
    """Test detect_file_type function."""
    
    def test_detect_pdb(self):
        assert detect_file_type("protein.pdb") == "pdb"
    
    def test_detect_prmtop(self):
        assert detect_file_type("system.prmtop") == "prmtop"
        assert detect_file_type("system.top") == "prmtop"
    
    def test_detect_inpcrd(self):
        assert detect_file_type("coords.inpcrd") == "inpcrd"
        assert detect_file_type("coords.rst7") == "inpcrd"
        assert detect_file_type("coords.crd") == "inpcrd"
    
    def test_detect_mol2(self):
        assert detect_file_type("ligand.mol2") == "mol2"
    
    def test_detect_nc(self):
        assert detect_file_type("traj.nc") == "nc"
        assert detect_file_type("traj.mdcrd") == "nc"
    
    def test_detect_unknown(self):
        assert detect_file_type("unknown.xyz") == "other"
    
    def test_case_insensitive(self):
        assert detect_file_type("FILE.PDB") == "pdb"

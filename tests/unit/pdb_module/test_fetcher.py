"""Tests for PDB file fetcher."""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch, mock_open
import httpx

from mdpilot.tools.builtin.pdb.fetcher import PDBFetcher


# Sample PDB content for testing
VALID_PDB_CONTENT = """HEADER    HYDROLASE                               01-JAN-00   1AKI
TITLE     STRUCTURE OF ADENYLATE KINASE
COMPND    MOL_ID: 1;
ATOM      1  N   MET A   1      27.340  24.430   2.614  1.00  9.67           N
ATOM      2  CA  MET A   1      26.266  25.413   2.842  1.00 10.38           C
ATOM      3  C   MET A   1      26.913  26.639   3.531  1.00  9.62           C
ATOM      4  O   MET A   1      27.886  26.463   4.263  1.00  9.62           O
ATOM      5  CB  MET A   1      25.112  24.880   3.649  1.00 13.77           C
HETATM 1000  O   HOH A 101      10.000  20.000  30.000  1.00 20.00           O
END
"""

VALID_PDB_SHORT = """HEADER    TEST
ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  1.00           N
ATOM      2  CA  ALA A   1       1.000   1.000   1.000  1.00  1.00           C
ATOM      3  C   ALA A   1       2.000   2.000   2.000  1.00  1.00           C
ATOM      4  O   ALA A   1       3.000   3.000   3.000  1.00  1.00           O
ATOM      5  CB  ALA A   1       4.000   4.000   4.000  1.00  1.00           C
ATOM      6  N   ALA A   2       5.000   5.000   5.000  1.00  1.00           N
ATOM      7  CA  ALA A   2       6.000   6.000   6.000  1.00  1.00           C
ATOM      8  C   ALA A   2       7.000   7.000   7.000  1.00  1.00           C
ATOM      9  O   ALA A   2       8.000   8.000   8.000  1.00  1.00           O
ATOM     10  CB  ALA A   2       9.000   9.000   9.000  1.00  1.00           C
END
"""

INVALID_PDB_NO_ATOMS = """HEADER    TEST
TITLE     NO ATOMS HERE
COMPND    NOTHING
REMARK    JUST REMARKS
REMARK    MORE REMARKS
REMARK    EVEN MORE REMARKS
REMARK    STILL NO ATOMS
REMARK    NOPE
REMARK    NADA
REMARK    ZILCH
END
"""

INVALID_PDB_TOO_SHORT = """HEADER    TEST
ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  1.00           N
END
"""


# ============================================================================
# Initialization Tests
# ============================================================================

class TestPDBFetcherInit:
    """Test PDBFetcher initialization."""
    
    def test_init_default_timeout(self):
        """Test initialization with default timeout."""
        fetcher = PDBFetcher()
        assert fetcher.timeout == 30
    
    def test_init_custom_timeout(self):
        """Test initialization with custom timeout."""
        fetcher = PDBFetcher(timeout=60)
        assert fetcher.timeout == 60
    
    def test_base_url_constant(self):
        """Test BASE_URL constant is set correctly."""
        assert PDBFetcher.BASE_URL == "https://files.rcsb.org/download"


# ============================================================================
# Download Tests - Async
# ============================================================================

class TestPDBFetcherDownloadAsync:
    """Test async download method."""
    
    @pytest.mark.asyncio
    async def test_download_valid_pdb(self):
        """Test downloading a valid PDB file."""
        fetcher = PDBFetcher()
        
        # Mock httpx response
        mock_response = Mock()
        mock_response.text = VALID_PDB_CONTENT
        mock_response.raise_for_status = Mock()
        
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock()
            
            content = await fetcher.download("1AKI")
            
            assert content == VALID_PDB_CONTENT
            mock_client.get.assert_called_once_with("https://files.rcsb.org/download/1AKI.pdb")
    
    @pytest.mark.asyncio
    async def test_download_normalizes_pdb_id(self):
        """Test PDB ID is normalized (uppercase, stripped)."""
        fetcher = PDBFetcher()
        
        mock_response = Mock()
        mock_response.text = VALID_PDB_CONTENT
        mock_response.raise_for_status = Mock()
        
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock()
            
            # Test lowercase with spaces
            await fetcher.download("  1aki  ")
            
            mock_client.get.assert_called_with("https://files.rcsb.org/download/1AKI.pdb")
    
    @pytest.mark.asyncio
    async def test_download_invalid_pdb_id_length(self):
        """Test download raises ValueError for invalid PDB ID length."""
        fetcher = PDBFetcher()
        
        with pytest.raises(ValueError, match="Invalid PDB ID.*must be 4 characters"):
            await fetcher.download("1AK")
        
        with pytest.raises(ValueError, match="Invalid PDB ID.*must be 4 characters"):
            await fetcher.download("1AKII")
    
    @pytest.mark.asyncio
    async def test_download_invalid_content_no_header(self):
        """Test download validates PDB content starts with valid record."""
        fetcher = PDBFetcher()
        
        mock_response = Mock()
        mock_response.text = "INVALID CONTENT\nNOT A PDB FILE\n" * 20
        mock_response.raise_for_status = Mock()
        
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock()
            
            with pytest.raises(ValueError, match="does not appear to be a valid PDB file"):
                await fetcher.download("1AKI")
    
    @pytest.mark.asyncio
    async def test_download_too_short(self):
        """Test download validates PDB has minimum line count."""
        fetcher = PDBFetcher()
        
        mock_response = Mock()
        mock_response.text = INVALID_PDB_TOO_SHORT
        mock_response.raise_for_status = Mock()
        
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock()
            
            with pytest.raises(ValueError, match="PDB file too short"):
                await fetcher.download("1AKI")
    
    @pytest.mark.asyncio
    async def test_download_no_atoms(self):
        """Test download validates PDB contains ATOM/HETATM records."""
        fetcher = PDBFetcher()
        
        mock_response = Mock()
        mock_response.text = INVALID_PDB_NO_ATOMS
        mock_response.raise_for_status = Mock()
        
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock()
            
            with pytest.raises(ValueError, match="contains no ATOM or HETATM records"):
                await fetcher.download("1AKI")
    
    @pytest.mark.asyncio
    async def test_download_uses_custom_timeout(self):
        """Test download uses custom timeout setting."""
        fetcher = PDBFetcher(timeout=120)
        
        mock_response = Mock()
        mock_response.text = VALID_PDB_CONTENT
        mock_response.raise_for_status = Mock()
        
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock()
            
            await fetcher.download("1AKI")
            
            # Verify timeout was passed to AsyncClient
            mock_client_cls.assert_called_once_with(timeout=120)


# ============================================================================
# Download Tests - Sync
# ============================================================================

class TestPDBFetcherDownloadSync:
    """Test synchronous download method."""
    
    def test_download_sync_valid_pdb(self):
        """Test synchronous download of valid PDB."""
        fetcher = PDBFetcher()
        
        mock_response = Mock()
        mock_response.text = VALID_PDB_CONTENT
        mock_response.raise_for_status = Mock()
        
        with patch("httpx.Client") as mock_client_cls:
            mock_client = Mock()
            mock_client.get = Mock(return_value=mock_response)
            mock_client_cls.return_value.__enter__ = Mock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = Mock()
            
            content = fetcher.download_sync("1AKI")
            
            assert content == VALID_PDB_CONTENT
            mock_client.get.assert_called_once_with("https://files.rcsb.org/download/1AKI.pdb")
    
    def test_download_sync_normalizes_pdb_id(self):
        """Test sync download normalizes PDB ID."""
        fetcher = PDBFetcher()
        
        mock_response = Mock()
        mock_response.text = VALID_PDB_CONTENT
        mock_response.raise_for_status = Mock()
        
        with patch("httpx.Client") as mock_client_cls:
            mock_client = Mock()
            mock_client.get = Mock(return_value=mock_response)
            mock_client_cls.return_value.__enter__ = Mock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = Mock()
            
            fetcher.download_sync("  2cab  ")
            
            mock_client.get.assert_called_with("https://files.rcsb.org/download/2CAB.pdb")
    
    def test_download_sync_invalid_pdb_id(self):
        """Test sync download validates PDB ID length."""
        fetcher = PDBFetcher()
        
        with pytest.raises(ValueError, match="Invalid PDB ID.*must be 4 characters"):
            fetcher.download_sync("ABC")
    
    def test_download_sync_invalid_content(self):
        """Test sync download validates content."""
        fetcher = PDBFetcher()
        
        mock_response = Mock()
        mock_response.text = "NOT A PDB FILE"
        mock_response.raise_for_status = Mock()
        
        with patch("httpx.Client") as mock_client_cls:
            mock_client = Mock()
            mock_client.get = Mock(return_value=mock_response)
            mock_client_cls.return_value.__enter__ = Mock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = Mock()
            
            with pytest.raises(ValueError, match="does not appear to be a valid PDB file"):
                fetcher.download_sync("1AKI")


# ============================================================================
# Save Tests
# ============================================================================

class TestPDBFetcherSave:
    """Test save method."""
    
    def test_save_creates_parent_directory(self, tmp_path):
        """Test save creates parent directories if needed."""
        fetcher = PDBFetcher()
        output_path = tmp_path / "subdir" / "test.pdb"
        
        # Mock path validation to allow tmp_path
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            fetcher.save(VALID_PDB_CONTENT, output_path)
        
        assert output_path.exists()
        assert output_path.read_text() == VALID_PDB_CONTENT
    
    def test_save_writes_content(self, tmp_path):
        """Test save writes content correctly."""
        fetcher = PDBFetcher()
        output_path = tmp_path / "test.pdb"
        
        # Mock path validation to allow tmp_path
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            fetcher.save(VALID_PDB_CONTENT, output_path)
        
        assert output_path.read_text() == VALID_PDB_CONTENT
    
    def test_save_accepts_string_path(self, tmp_path):
        """Test save accepts string path."""
        fetcher = PDBFetcher()
        output_path = str(tmp_path / "test.pdb")
        
        # Mock path validation to allow tmp_path
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            fetcher.save(VALID_PDB_CONTENT, output_path)
        
        assert Path(output_path).exists()
    
    def test_save_path_traversal_in_cwd(self, tmp_path):
        """Test save allows paths within cwd."""
        fetcher = PDBFetcher()
        
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            output_path = tmp_path / "test.pdb"
            fetcher.save(VALID_PDB_CONTENT, output_path)
            
            assert output_path.exists()
    
    def test_save_path_traversal_in_home(self, tmp_path):
        """Test save allows paths within home directory."""
        fetcher = PDBFetcher()
        
        # Mock cwd to be different from tmp_path, and home to be tmp_path
        with patch("pathlib.Path.cwd", return_value=Path("/different/path")), \
             patch("pathlib.Path.home", return_value=tmp_path):
            
            output_path = tmp_path / "test.pdb"
            fetcher.save(VALID_PDB_CONTENT, output_path)
            
            assert output_path.exists()
    
    def test_save_path_traversal_blocked(self, tmp_path):
        """Test save blocks paths outside cwd and home."""
        fetcher = PDBFetcher()
        
        # Mock both cwd and home to be different from tmp_path
        with patch("pathlib.Path.cwd", return_value=Path("/some/path")), \
             patch("pathlib.Path.home", return_value=Path("/home/user")):
            
            output_path = tmp_path / "test.pdb"
            
            with pytest.raises(ValueError, match="Output path is outside allowed directories"):
                fetcher.save(VALID_PDB_CONTENT, output_path)


# ============================================================================
# Download and Save Tests - Async
# ============================================================================

class TestPDBFetcherDownloadAndSaveAsync:
    """Test async download_and_save method."""
    
    @pytest.mark.asyncio
    async def test_download_and_save_success(self, tmp_path):
        """Test download_and_save downloads and saves in one step."""
        fetcher = PDBFetcher()
        output_path = tmp_path / "1aki.pdb"
        
        mock_response = Mock()
        mock_response.text = VALID_PDB_CONTENT
        mock_response.raise_for_status = Mock()
        
        with patch("httpx.AsyncClient") as mock_client_cls, \
             patch("pathlib.Path.cwd", return_value=tmp_path):
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock()
            
            result_path = await fetcher.download_and_save("1AKI", output_path)
            
            assert result_path == output_path
            assert output_path.exists()
            assert output_path.read_text() == VALID_PDB_CONTENT
    
    @pytest.mark.asyncio
    async def test_download_and_save_returns_path(self, tmp_path):
        """Test download_and_save returns Path object."""
        fetcher = PDBFetcher()
        output_path = tmp_path / "test.pdb"
        
        mock_response = Mock()
        mock_response.text = VALID_PDB_CONTENT
        mock_response.raise_for_status = Mock()
        
        with patch("httpx.AsyncClient") as mock_client_cls, \
             patch("pathlib.Path.cwd", return_value=tmp_path):
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock()
            
            result = await fetcher.download_and_save("1AKI", output_path)
            
            assert isinstance(result, Path)
            assert result == output_path


# ============================================================================
# Download and Save Tests - Sync
# ============================================================================

class TestPDBFetcherDownloadAndSaveSync:
    """Test synchronous download_and_save method."""
    
    def test_download_and_save_sync_success(self, tmp_path):
        """Test sync download_and_save downloads and saves."""
        fetcher = PDBFetcher()
        output_path = tmp_path / "1aki.pdb"
        
        mock_response = Mock()
        mock_response.text = VALID_PDB_CONTENT
        mock_response.raise_for_status = Mock()
        
        with patch("httpx.Client") as mock_client_cls, \
             patch("pathlib.Path.cwd", return_value=tmp_path):
            mock_client = Mock()
            mock_client.get = Mock(return_value=mock_response)
            mock_client_cls.return_value.__enter__ = Mock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = Mock()
            
            result_path = fetcher.download_and_save_sync("1AKI", output_path)
            
            assert result_path == output_path
            assert output_path.exists()
            assert output_path.read_text() == VALID_PDB_CONTENT
    
    def test_download_and_save_sync_returns_path(self, tmp_path):
        """Test sync download_and_save returns Path object."""
        fetcher = PDBFetcher()
        output_path = tmp_path / "test.pdb"
        
        mock_response = Mock()
        mock_response.text = VALID_PDB_CONTENT
        mock_response.raise_for_status = Mock()
        
        with patch("httpx.Client") as mock_client_cls, \
             patch("pathlib.Path.cwd", return_value=tmp_path):
            mock_client = Mock()
            mock_client.get = Mock(return_value=mock_response)
            mock_client_cls.return_value.__enter__ = Mock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = Mock()
            
            result = fetcher.download_and_save_sync("1AKI", output_path)
            
            assert isinstance(result, Path)
            assert result == output_path


# ============================================================================
# Edge Cases and Integration Tests
# ============================================================================

class TestPDBFetcherEdgeCases:
    """Test edge cases and integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_download_with_hetatm_only(self):
        """Test download accepts PDB with only HETATM records."""
        fetcher = PDBFetcher()
        
        hetatm_only = """HEADER    LIGAND
TITLE     LIGAND ONLY
COMPND    SMALL MOLECULE
HETATM    1  C   LIG A   1       0.000   0.000   0.000  1.00  1.00           C
HETATM    2  O   LIG A   1       1.000   1.000   1.000  1.00  1.00           O
HETATM    3  N   LIG A   1       2.000   2.000   2.000  1.00  1.00           N
HETATM    4  C   LIG A   1       3.000   3.000   3.000  1.00  1.00           C
HETATM    5  C   LIG A   1       4.000   4.000   4.000  1.00  1.00           C
HETATM    6  O   LIG A   1       5.000   5.000   5.000  1.00  1.00           O
HETATM    7  N   LIG A   1       6.000   6.000   6.000  1.00  1.00           N
HETATM    8  C   LIG A   1       7.000   7.000   7.000  1.00  1.00           C
HETATM    9  C   LIG A   1       8.000   8.000   8.000  1.00  1.00           C
HETATM   10  O   LIG A   1       9.000   9.000   9.000  1.00  1.00           O
END
"""
        
        mock_response = Mock()
        mock_response.text = hetatm_only
        mock_response.raise_for_status = Mock()
        
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock()
            
            content = await fetcher.download("1AKI")
            assert "HETATM" in content
    
    @pytest.mark.asyncio
    async def test_download_with_title_start(self):
        """Test download accepts PDB starting with TITLE."""
        fetcher = PDBFetcher()
        
        title_start = """TITLE     STRUCTURE OF PROTEIN
COMPND    MOL_ID: 1;
ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  1.00           N
ATOM      2  CA  ALA A   1       1.000   1.000   1.000  1.00  1.00           C
ATOM      3  C   ALA A   1       2.000   2.000   2.000  1.00  1.00           C
ATOM      4  O   ALA A   1       3.000   3.000   3.000  1.00  1.00           O
ATOM      5  CB  ALA A   1       4.000   4.000   4.000  1.00  1.00           C
ATOM      6  N   ALA A   2       5.000   5.000   5.000  1.00  1.00           N
ATOM      7  CA  ALA A   2       6.000   6.000   6.000  1.00  1.00           C
ATOM      8  C   ALA A   2       7.000   7.000   7.000  1.00  1.00           C
ATOM      9  O   ALA A   2       8.000   8.000   8.000  1.00  1.00           O
ATOM     10  CB  ALA A   2       9.000   9.000   9.000  1.00  1.00           C
END
"""
        
        mock_response = Mock()
        mock_response.text = title_start
        mock_response.raise_for_status = Mock()
        
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock()
            
            content = await fetcher.download("1AKI")
            assert content.startswith("TITLE")

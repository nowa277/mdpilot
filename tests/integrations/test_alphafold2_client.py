"""Tests for AlphaFold2 client interface."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from mdpilot.integrations.alphafold2_client import AlphaFold2Client
from mdpilot.integrations.base_client import ClientMode


@pytest.fixture
def local_config():
    """Configuration for local mode."""
    return {
        "mode": "local",
        "local_path": "/opt/alphafold",
        "model_preset": "monomer",
    }


@pytest.fixture
def api_config():
    """Configuration for API mode."""
    return {
        "mode": "api",
        "api_endpoint": "https://api.alphafold.example.com",
        "api_key": "test_key_123",
    }


@pytest.fixture
def local_client(local_config):
    """Create a local mode client."""
    return AlphaFold2Client(local_config)


@pytest.fixture
def api_client(api_config):
    """Create an API mode client."""
    return AlphaFold2Client(api_config)


class TestAlphaFold2ClientInit:
    """Test client initialization."""

    def test_init_local_mode(self, local_client, local_config):
        """Test initialization in local mode."""
        assert local_client.mode == ClientMode.LOCAL
        assert local_client.config == local_config
        assert local_client.local_path == "/opt/alphafold"

    def test_init_api_mode(self, api_client, api_config):
        """Test initialization in API mode."""
        assert api_client.mode == ClientMode.API
        assert api_client.config == api_config
        assert api_client.api_endpoint == "https://api.alphafold.example.com"

    def test_init_invalid_mode(self):
        """Test initialization with invalid mode."""
        with pytest.raises(ValueError, match="Invalid mode"):
            AlphaFold2Client({"mode": "invalid"})

    def test_init_missing_local_path(self):
        """Test initialization without required local_path."""
        with pytest.raises(ValueError, match="local_path is required"):
            AlphaFold2Client({"mode": "local"})

    def test_init_missing_api_endpoint(self):
        """Test initialization without required api_endpoint."""
        with pytest.raises(ValueError, match="api_endpoint is required"):
            AlphaFold2Client({"mode": "api", "api_key": "test"})


class TestAlphaFold2ClientHealthCheck:
    """Test health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_local_success(self, local_client):
        """Test health check in local mode when available."""
        with patch("os.path.exists", return_value=True):
            result = await local_client.health_check()
            assert result["status"] == "healthy"
            assert result["mode"] == "local"
            assert "local_path" in result

    @pytest.mark.asyncio
    async def test_health_check_local_failure(self, local_client):
        """Test health check in local mode when unavailable."""
        with patch("os.path.exists", return_value=False):
            result = await local_client.health_check()
            assert result["status"] == "unhealthy"
            assert "error" in result

    @pytest.mark.asyncio
    async def test_health_check_api_success(self, api_client):
        """Test health check in API mode when available."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"status": "ok"})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await api_client.health_check()
            assert result["status"] == "healthy"
            assert result["mode"] == "api"

    @pytest.mark.asyncio
    async def test_health_check_api_failure(self, api_client):
        """Test health check in API mode when unavailable."""
        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=Exception("Connection failed"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await api_client.health_check()
            assert result["status"] == "unhealthy"
            assert "error" in result


class TestAlphaFold2ClientPredict:
    """Test structure prediction functionality."""

    @pytest.mark.asyncio
    async def test_predict_local_mode(self, local_client):
        """Test prediction in local mode."""
        sequence = "MKFLKFSLLTAVLLSVVFAFSSCGDDDDTYPYDVPDYAIEGIFHATIKQNSKG"

        mock_result = {
            "pdb_string": "ATOM    1  N   MET A   1...",
            "plddt": [95.2, 94.8, 93.5],
            "mean_plddt": 94.5,
            "ptm": 0.89,
        }

        with patch.object(local_client, "_run_local_prediction", return_value=mock_result):
            result = await local_client.predict(sequence)

            assert "pdb_string" in result
            assert "plddt" in result
            assert "mean_plddt" in result
            assert result["mean_plddt"] == 94.5

    @pytest.mark.asyncio
    async def test_predict_api_mode(self, api_client):
        """Test prediction in API mode."""
        sequence = "MKFLKFSLLTAVLLSVVFAFSSCGDDDDTYPYDVPDYAIEGIFHATIKQNSKG"

        mock_response = {
            "pdb_string": "ATOM    1  N   MET A   1...",
            "confidence": {
                "plddt": [95.2, 94.8, 93.5],
                "mean_plddt": 94.5,
                "ptm": 0.89,
            },
        }

        with patch.object(api_client, "_run_api_prediction", return_value=mock_response):
            result = await api_client.predict(sequence)

            assert "pdb_string" in result
            assert "confidence" in result
            assert result["confidence"]["mean_plddt"] == 94.5

    @pytest.mark.asyncio
    async def test_predict_invalid_sequence(self, local_client):
        """Test prediction with invalid sequence."""
        with pytest.raises(ValueError, match="Invalid sequence"):
            await local_client.predict("")

    @pytest.mark.asyncio
    async def test_predict_with_options(self, local_client):
        """Test prediction with custom options."""
        sequence = "MKFLKFSLLTAVLLSVVFAFSSCGDDDDTYPYDVPDYAIEGIFHATIKQNSKG"
        options = {
            "model_preset": "multimer",
            "num_recycles": 3,
        }

        mock_result = {"pdb_string": "ATOM...", "mean_plddt": 90.0}

        with patch.object(local_client, "_run_local_prediction", return_value=mock_result) as mock:
            await local_client.predict(sequence, **options)
            mock.assert_called_once()
            call_args = mock.call_args[1]
            assert call_args.get("model_preset") == "multimer"
            assert call_args.get("num_recycles") == 3

    @pytest.mark.asyncio
    async def test_predict_error_handling(self, local_client):
        """Test error handling during prediction."""
        sequence = "MKFLKFSLLTAVLLSVVFAFSSCGDDDDTYPYDVPDYAIEGIFHATIKQNSKG"

        with patch.object(
            local_client, "_run_local_prediction", side_effect=RuntimeError("Prediction failed")
        ):
            with pytest.raises(RuntimeError, match="Prediction failed"):
                await local_client.predict(sequence)


class TestAlphaFold2ClientMethods:
    """Test helper methods."""

    def test_validate_sequence_valid(self, local_client):
        """Test sequence validation with valid sequence."""
        sequence = "ACDEFGHIKLMNPQRSTVWY"
        assert local_client._validate_sequence(sequence) is True

    def test_validate_sequence_invalid_chars(self, local_client):
        """Test sequence validation with invalid characters."""
        sequence = "ACDEFGHIKLMNPQRSTVWYBZJOUX"
        assert local_client._validate_sequence(sequence) is False

    def test_validate_sequence_empty(self, local_client):
        """Test sequence validation with empty sequence."""
        assert local_client._validate_sequence("") is False

    def test_validate_sequence_lowercase(self, local_client):
        """Test sequence validation with lowercase letters."""
        sequence = "acdefghiklmnpqrstvwy"
        assert local_client._validate_sequence(sequence) is True

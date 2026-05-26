"""Tests for structure-function pipeline."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from mdpilot.pipelines.structure_function import StructureFunctionPipeline


@pytest.fixture
def alphafold_config():
    """AlphaFold2 configuration."""
    return {
        "mode": "local",
        "local_path": "/opt/alphafold",
    }


@pytest.fixture
def bioreason_config():
    """Bioreason configuration."""
    return {
        "mode": "local",
        "local_path": "/opt/bioreason",
    }


@pytest.fixture
def pipeline(alphafold_config, bioreason_config):
    """Create a structure-function pipeline."""
    return StructureFunctionPipeline(
        alphafold_config=alphafold_config,
        bioreason_config=bioreason_config,
    )


@pytest.fixture
def mock_structure_result():
    """Mock AlphaFold2 prediction result."""
    return {
        "pdb_string": "ATOM    1  N   MET A   1      10.000  10.000  10.000  1.00 95.00\n",
        "plddt": [95.0, 94.5, 93.0, 92.5, 91.0],
        "mean_plddt": 93.2,
        "ptm": 0.89,
    }


@pytest.fixture
def mock_annotation_result():
    """Mock Bioreason annotation result."""
    return {
        "go_terms": {
            "molecular_function": [
                {"id": "GO:0003824", "name": "catalytic activity", "score": 0.95},
            ],
            "biological_process": [
                {"id": "GO:0008152", "name": "metabolic process", "score": 0.92},
            ],
            "cellular_component": [
                {"id": "GO:0005737", "name": "cytoplasm", "score": 0.85},
            ],
        },
        "embeddings": [0.1] * 1280,
        "model": "esm2_t33_650M_UR50D",
    }


class TestStructureFunctionPipelineInit:
    """Test pipeline initialization."""

    def test_init_success(self, pipeline, alphafold_config, bioreason_config):
        """Test successful initialization."""
        assert pipeline.alphafold_client is not None
        assert pipeline.bioreason_client is not None

    def test_init_with_custom_thresholds(self):
        """Test initialization with custom quality thresholds."""
        pipeline = StructureFunctionPipeline(
            alphafold_config={"mode": "local", "local_path": "/opt/alphafold"},
            bioreason_config={"mode": "local", "local_path": "/opt/bioreason"},
            quality_threshold=90.0,
            confidence_threshold=0.8,
        )
        assert pipeline.quality_threshold == 90.0
        assert pipeline.confidence_threshold == 0.8


class TestStructureFunctionPipelineHealthCheck:
    """Test pipeline health check."""

    @pytest.mark.asyncio
    async def test_health_check_all_healthy(self, pipeline):
        """Test health check when all services are healthy."""
        mock_af_health = {"status": "healthy", "mode": "local"}
        mock_br_health = {"status": "healthy", "mode": "local"}

        with patch.object(
            pipeline.alphafold_client, "health_check", return_value=mock_af_health
        ), patch.object(pipeline.bioreason_client, "health_check", return_value=mock_br_health):
            result = await pipeline.health_check()

            assert result["status"] == "healthy"
            assert result["alphafold"] == mock_af_health
            assert result["bioreason"] == mock_br_health

    @pytest.mark.asyncio
    async def test_health_check_alphafold_unhealthy(self, pipeline):
        """Test health check when AlphaFold is unhealthy."""
        mock_af_health = {"status": "unhealthy", "error": "Not found"}
        mock_br_health = {"status": "healthy", "mode": "local"}

        with patch.object(
            pipeline.alphafold_client, "health_check", return_value=mock_af_health
        ), patch.object(pipeline.bioreason_client, "health_check", return_value=mock_br_health):
            result = await pipeline.health_check()

            assert result["status"] == "unhealthy"
            assert result["alphafold"]["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_health_check_bioreason_unhealthy(self, pipeline):
        """Test health check when Bioreason is unhealthy."""
        mock_af_health = {"status": "healthy", "mode": "local"}
        mock_br_health = {"status": "unhealthy", "error": "Not found"}

        with patch.object(
            pipeline.alphafold_client, "health_check", return_value=mock_af_health
        ), patch.object(pipeline.bioreason_client, "health_check", return_value=mock_br_health):
            result = await pipeline.health_check()

            assert result["status"] == "unhealthy"
            assert result["bioreason"]["status"] == "unhealthy"


class TestStructureFunctionPipelinePredict:
    """Test structure prediction and annotation."""

    @pytest.mark.asyncio
    async def test_predict_and_annotate_success(
        self, pipeline, mock_structure_result, mock_annotation_result
    ):
        """Test successful prediction and annotation."""
        sequence = "MKFLKFSLLTAVLLSVVFAFSSCGDDDDTYPYDVPDYAIEGIFHATIKQNSKG"

        with patch.object(
            pipeline.alphafold_client, "predict", return_value=mock_structure_result
        ), patch.object(
            pipeline.bioreason_client, "annotate", return_value=mock_annotation_result
        ):
            result = await pipeline.predict_and_annotate(sequence)

            assert "structure" in result
            assert "annotation" in result
            assert "quality_assessment" in result
            assert "md_recommendations" in result
            assert result["structure"]["mean_plddt"] == 93.2
            assert "molecular_function" in result["annotation"]["go_terms"]

    @pytest.mark.asyncio
    async def test_predict_and_annotate_low_quality(self, pipeline, mock_annotation_result):
        """Test prediction with low quality structure."""
        sequence = "MKFLKFSLLTAVLLSVVFAFSSCGDDDDTYPYDVPDYAIEGIFHATIKQNSKG"

        low_quality_result = {
            "pdb_string": "ATOM...",
            "plddt": [60.0, 55.0, 50.0],
            "mean_plddt": 55.0,
            "ptm": 0.45,
        }

        with patch.object(
            pipeline.alphafold_client, "predict", return_value=low_quality_result
        ), patch.object(
            pipeline.bioreason_client, "annotate", return_value=mock_annotation_result
        ):
            result = await pipeline.predict_and_annotate(sequence)

            assert result["quality_assessment"]["overall_quality"] == "low"
            assert "warnings" in result["quality_assessment"]

    @pytest.mark.asyncio
    async def test_predict_and_annotate_with_options(
        self, pipeline, mock_structure_result, mock_annotation_result
    ):
        """Test prediction with custom options."""
        sequence = "MKFLKFSLLTAVLLSVVFAFSSCGDDDDTYPYDVPDYAIEGIFHATIKQNSKG"

        with patch.object(
            pipeline.alphafold_client, "predict", return_value=mock_structure_result
        ) as mock_predict, patch.object(
            pipeline.bioreason_client, "annotate", return_value=mock_annotation_result
        ) as mock_annotate:
            await pipeline.predict_and_annotate(
                sequence,
                model_preset="multimer",
                include_embeddings=True,
            )

            mock_predict.assert_called_once()
            mock_annotate.assert_called_once()

    @pytest.mark.asyncio
    async def test_predict_and_annotate_structure_failure(self, pipeline):
        """Test handling of structure prediction failure."""
        sequence = "MKFLKFSLLTAVLLSVVFAFSSCGDDDDTYPYDVPDYAIEGIFHATIKQNSKG"

        with patch.object(
            pipeline.alphafold_client, "predict", side_effect=RuntimeError("Prediction failed")
        ):
            with pytest.raises(RuntimeError, match="Prediction failed"):
                await pipeline.predict_and_annotate(sequence)

    @pytest.mark.asyncio
    async def test_predict_and_annotate_annotation_failure(
        self, pipeline, mock_structure_result
    ):
        """Test handling of annotation failure."""
        sequence = "MKFLKFSLLTAVLLSVVFAFSSCGDDDDTYPYDVPDYAIEGIFHATIKQNSKG"

        with patch.object(
            pipeline.alphafold_client, "predict", return_value=mock_structure_result
        ), patch.object(
            pipeline.bioreason_client, "annotate", side_effect=RuntimeError("Annotation failed")
        ):
            with pytest.raises(RuntimeError, match="Annotation failed"):
                await pipeline.predict_and_annotate(sequence)


class TestStructureFunctionPipelineQualityAssessment:
    """Test structure quality assessment."""

    def test_assess_structure_quality_high(self, pipeline):
        """Test quality assessment for high-quality structure."""
        structure_data = {
            "mean_plddt": 95.0,
            "ptm": 0.92,
            "plddt": [95.0, 94.0, 93.0],
        }

        result = pipeline._assess_structure_quality(structure_data)

        assert result["overall_quality"] == "high"
        assert result["mean_plddt"] == 95.0
        assert result["ptm"] == 0.92
        assert result["suitable_for_md"] is True

    def test_assess_structure_quality_medium(self, pipeline):
        """Test quality assessment for medium-quality structure."""
        structure_data = {
            "mean_plddt": 75.0,
            "ptm": 0.65,
            "plddt": [75.0, 74.0, 73.0],
        }

        result = pipeline._assess_structure_quality(structure_data)

        assert result["overall_quality"] == "medium"
        assert result["suitable_for_md"] is True

    def test_assess_structure_quality_low(self, pipeline):
        """Test quality assessment for low-quality structure."""
        structure_data = {
            "mean_plddt": 55.0,
            "ptm": 0.45,
            "plddt": [55.0, 54.0, 53.0],
        }

        result = pipeline._assess_structure_quality(structure_data)

        assert result["overall_quality"] == "low"
        assert result["suitable_for_md"] is False
        assert len(result["warnings"]) > 0


class TestStructureFunctionPipelineMDRecommendations:
    """Test MD simulation recommendations."""

    def test_generate_md_recommendations_high_quality(self, pipeline):
        """Test MD recommendations for high-quality structure."""
        quality_assessment = {
            "overall_quality": "high",
            "mean_plddt": 95.0,
            "suitable_for_md": True,
        }

        annotation = {
            "go_terms": {
                "molecular_function": [
                    {"id": "GO:0003824", "name": "catalytic activity", "score": 0.95}
                ],
                "cellular_component": [
                    {"id": "GO:0016020", "name": "membrane", "score": 0.88}
                ],
            }
        }

        result = pipeline._generate_md_recommendations(quality_assessment, annotation)

        assert "force_field" in result
        assert "water_model" in result
        assert "simulation_length" in result
        assert "equilibration_steps" in result
        assert result["recommended"] is True

    def test_generate_md_recommendations_low_quality(self, pipeline):
        """Test MD recommendations for low-quality structure."""
        quality_assessment = {
            "overall_quality": "low",
            "mean_plddt": 55.0,
            "suitable_for_md": False,
        }

        annotation = {
            "go_terms": {
                "molecular_function": [
                    {"id": "GO:0003824", "name": "catalytic activity", "score": 0.95}
                ]
            }
        }

        result = pipeline._generate_md_recommendations(quality_assessment, annotation)

        assert result["recommended"] is False
        assert "warnings" in result

    def test_generate_md_recommendations_membrane_protein(self, pipeline):
        """Test MD recommendations for membrane protein."""
        quality_assessment = {
            "overall_quality": "high",
            "mean_plddt": 90.0,
            "suitable_for_md": True,
        }

        annotation = {
            "go_terms": {
                "cellular_component": [
                    {"id": "GO:0016020", "name": "membrane", "score": 0.92}
                ]
            }
        }

        result = pipeline._generate_md_recommendations(quality_assessment, annotation)

        assert "membrane" in result["force_field"].lower() or "lipid" in str(result).lower()


class TestStructureFunctionPipelineCorrelation:
    """Test structure-function correlation analysis."""

    def test_correlate_structure_function(self, pipeline):
        """Test correlation between structure quality and function."""
        quality_assessment = {
            "overall_quality": "high",
            "mean_plddt": 95.0,
            "plddt": [95.0, 94.0, 93.0, 92.0, 91.0],
        }

        annotation = {
            "go_terms": {
                "molecular_function": [
                    {"id": "GO:0003824", "name": "catalytic activity", "score": 0.95},
                    {"id": "GO:0005515", "name": "protein binding", "score": 0.88},
                ]
            }
        }

        result = pipeline._correlate_structure_function(quality_assessment, annotation)

        assert "confidence_level" in result
        assert "functional_regions" in result
        assert result["confidence_level"] in ["high", "medium", "low"]

    def test_correlate_structure_function_low_confidence(self, pipeline):
        """Test correlation with low confidence."""
        quality_assessment = {
            "overall_quality": "low",
            "mean_plddt": 55.0,
            "plddt": [55.0, 54.0, 53.0],
        }

        annotation = {
            "go_terms": {
                "molecular_function": [
                    {"id": "GO:0003824", "name": "catalytic activity", "score": 0.60}
                ]
            }
        }

        result = pipeline._correlate_structure_function(quality_assessment, annotation)

        assert result["confidence_level"] == "low"

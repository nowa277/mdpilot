"""Structure-function analysis pipeline integrating AlphaFold2 and Bioreason."""

from typing import Any, Dict, List, Optional

from mdpilot.integrations.alphafold2_client import AlphaFold2Client
from mdpilot.integrations.bioreason_client import BioreasonClient


class StructureFunctionPipeline:
    """Pipeline for integrated structure prediction and function annotation.

    Combines AlphaFold2 structure prediction with Bioreason function annotation
    to provide comprehensive protein analysis and MD simulation recommendations.
    """

    def __init__(
        self,
        alphafold_config: Dict[str, Any],
        bioreason_config: Dict[str, Any],
        quality_threshold: float = 70.0,
        confidence_threshold: float = 0.7,
    ):
        """Initialize the structure-function pipeline.

        Args:
            alphafold_config: Configuration for AlphaFold2 client
            bioreason_config: Configuration for Bioreason client
            quality_threshold: Minimum pLDDT score for acceptable structures (default: 70.0)
            confidence_threshold: Minimum confidence for GO annotations (default: 0.7)
        """
        self.alphafold_client = AlphaFold2Client(alphafold_config)
        self.bioreason_client = BioreasonClient(bioreason_config)
        self.quality_threshold = quality_threshold
        self.confidence_threshold = confidence_threshold

    async def health_check(self) -> Dict[str, Any]:
        """Check health of all pipeline components.

        Returns:
            Dictionary with overall status and component health
        """
        alphafold_health = await self.alphafold_client.health_check()
        bioreason_health = await self.bioreason_client.health_check()

        overall_status = "healthy"
        if alphafold_health["status"] != "healthy" or bioreason_health["status"] != "healthy":
            overall_status = "unhealthy"

        return {
            "status": overall_status,
            "alphafold": alphafold_health,
            "bioreason": bioreason_health,
        }

    async def predict_and_annotate(self, sequence: str, **options) -> Dict[str, Any]:
        """Predict structure and annotate function for a protein sequence.

        Args:
            sequence: Amino acid sequence
            **options: Additional options for prediction and annotation

        Returns:
            Dictionary containing:
                - structure: AlphaFold2 prediction results
                - annotation: Bioreason GO annotations
                - quality_assessment: Structure quality metrics
                - correlation: Structure-function correlation analysis
                - md_recommendations: MD simulation parameters

        Raises:
            ValueError: If sequence is invalid
            RuntimeError: If prediction or annotation fails
        """
        # Extract options for each component
        structure_options = {
            k: v for k, v in options.items() if k in ["model_preset", "num_recycles"]
        }
        annotation_options = {
            k: v for k, v in options.items() if k in ["include_embeddings", "confidence_threshold"]
        }

        # Step 1: Predict structure with AlphaFold2
        structure_result = await self.alphafold_client.predict(sequence, **structure_options)

        # Step 2: Assess structure quality
        quality_assessment = self._assess_structure_quality(structure_result)

        # Step 3: Annotate function with Bioreason
        annotation_result = await self.bioreason_client.annotate(sequence, **annotation_options)

        # Step 4: Correlate structure and function
        correlation = self._correlate_structure_function(quality_assessment, annotation_result)

        # Step 5: Generate MD simulation recommendations
        md_recommendations = self._generate_md_recommendations(
            quality_assessment, annotation_result
        )

        return {
            "structure": structure_result,
            "annotation": annotation_result,
            "quality_assessment": quality_assessment,
            "correlation": correlation,
            "md_recommendations": md_recommendations,
        }

    def _assess_structure_quality(self, structure_data: Dict[str, Any]) -> Dict[str, Any]:
        """Assess the quality of predicted structure.

        Args:
            structure_data: AlphaFold2 prediction results

        Returns:
            Dictionary with quality metrics and assessment
        """
        mean_plddt = structure_data.get("mean_plddt", 0)
        ptm = structure_data.get("ptm", 0)
        plddt_scores = structure_data.get("plddt", [])

        # Determine overall quality
        if mean_plddt >= 90:
            overall_quality = "high"
        elif mean_plddt >= 70:
            overall_quality = "medium"
        else:
            overall_quality = "low"

        # Check for low-confidence regions
        low_confidence_regions = []
        if plddt_scores:
            for i, score in enumerate(plddt_scores):
                if score < 50:
                    low_confidence_regions.append(i)

        # Determine suitability for MD
        suitable_for_md = mean_plddt >= self.quality_threshold and ptm >= 0.5

        assessment = {
            "overall_quality": overall_quality,
            "mean_plddt": mean_plddt,
            "ptm": ptm,
            "low_confidence_regions": low_confidence_regions,
            "suitable_for_md": suitable_for_md,
        }

        # Add warnings for low quality
        if overall_quality == "low":
            assessment["warnings"] = [
                f"Low mean pLDDT score ({mean_plddt:.1f})",
                "Structure may not be reliable for MD simulations",
                "Consider experimental validation",
            ]

        return assessment

    def _correlate_structure_function(
        self, quality_assessment: Dict[str, Any], annotation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze correlation between structure quality and predicted function.

        Args:
            quality_assessment: Structure quality metrics
            annotation: Function annotation results

        Returns:
            Dictionary with correlation analysis
        """
        mean_plddt = quality_assessment.get("mean_plddt", 0)
        go_terms = annotation.get("go_terms", {})

        # Calculate average GO term confidence
        all_scores = []
        for category in go_terms.values():
            if isinstance(category, list):
                all_scores.extend([term.get("score", 0) for term in category])

        avg_go_confidence = sum(all_scores) / len(all_scores) if all_scores else 0

        # Determine confidence level for structure-function relationship
        if mean_plddt >= 90 and avg_go_confidence >= 0.8:
            confidence_level = "high"
        elif mean_plddt >= 70 and avg_go_confidence >= 0.6:
            confidence_level = "medium"
        else:
            confidence_level = "low"

        # Identify functional regions
        functional_regions = []
        mf_terms = go_terms.get("molecular_function", [])
        if mf_terms:
            functional_regions.append(
                {
                    "type": "functional_site",
                    "description": "Predicted based on molecular function annotations",
                    "confidence": avg_go_confidence,
                }
            )

        return {
            "confidence_level": confidence_level,
            "structure_quality": mean_plddt,
            "function_confidence": avg_go_confidence,
            "functional_regions": functional_regions,
        }

    def _generate_md_recommendations(
        self, quality_assessment: Dict[str, Any], annotation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate MD simulation parameter recommendations.

        Args:
            quality_assessment: Structure quality metrics
            annotation: Function annotation results

        Returns:
            Dictionary with MD simulation recommendations
        """
        suitable_for_md = quality_assessment.get("suitable_for_md", False)
        overall_quality = quality_assessment.get("overall_quality", "low")
        go_terms = annotation.get("go_terms", {})

        # Check for membrane protein indicators
        is_membrane_protein = False
        cc_terms = go_terms.get("cellular_component", [])
        for term in cc_terms:
            if "membrane" in term.get("name", "").lower():
                is_membrane_protein = True
                break

        recommendations = {
            "recommended": suitable_for_md,
        }

        if not suitable_for_md:
            recommendations["warnings"] = [
                "Structure quality below threshold for reliable MD simulations",
                "Consider refining structure or using experimental data",
            ]
            return recommendations

        # Force field recommendations
        if is_membrane_protein:
            recommendations["force_field"] = "AMBER ff19SB with lipid21"
            recommendations["water_model"] = "TIP3P"
            recommendations["special_considerations"] = [
                "Use membrane builder for lipid bilayer",
                "Extended equilibration for membrane systems",
            ]
        else:
            recommendations["force_field"] = "AMBER ff19SB"
            recommendations["water_model"] = "TIP3P or OPC"

        # Simulation length based on quality
        if overall_quality == "high":
            recommendations["simulation_length"] = "100-500 ns"
            recommendations["equilibration_steps"] = "Standard (1-5 ns)"
        elif overall_quality == "medium":
            recommendations["simulation_length"] = "50-200 ns"
            recommendations["equilibration_steps"] = "Extended (5-10 ns)"
            recommendations["notes"] = [
                "Monitor RMSD carefully during equilibration",
                "Consider restraints on low-confidence regions",
            ]

        # Temperature and pressure
        recommendations["temperature"] = "300 K (physiological)"
        recommendations["pressure"] = "1 atm (NPT ensemble)"

        # Restraints for low-confidence regions
        low_conf_regions = quality_assessment.get("low_confidence_regions", [])
        if low_conf_regions:
            recommendations["restraints"] = {
                "apply_to": "low_confidence_regions",
                "regions": low_conf_regions,
                "type": "positional restraints",
                "force_constant": "5-10 kcal/mol/Å²",
            }

        return recommendations

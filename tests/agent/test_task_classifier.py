"""Tests for task classifier."""

import pytest

from mdpilot.agent.task_classifier import TaskClassifier, classify


class TestTaskClassifier:
    """Test task classification logic."""

    def test_classify_simple_query(self):
        """Test classification of simple queries."""
        classifier = TaskClassifier()

        result = classifier.classify("What is the temperature?")
        assert result == "CHAT"

        result = classifier.classify("How does tleap work?")
        assert result == "CHAT"

    def test_classify_file_operation(self):
        """Test classification of file operations with MD extensions."""
        classifier = TaskClassifier()

        result = classifier.classify("Read the file system.prmtop")
        assert result == "MD_TASK"

        result = classifier.classify("Write output to results.nc")
        assert result == "MD_TASK"

    def test_classify_amber_simulation(self):
        """Test classification of AMBER simulations."""
        classifier = TaskClassifier()

        result = classifier.classify("Run minimization with sander")
        assert result == "MD_TASK"

        result = classifier.classify("Execute MD simulation")
        assert result == "MD_TASK"

    def test_classify_analysis(self):
        """Test classification of analysis tasks."""
        classifier = TaskClassifier()

        result = classifier.classify("Calculate RMSD from trajectory")
        assert result == "MD_TASK"

        result = classifier.classify("Analyze hydrogen bonds")
        assert result == "MD_TASK"

    def test_classify_system_preparation(self):
        """Test classification of system preparation."""
        classifier = TaskClassifier()

        result = classifier.classify("Build topology with tleap")
        assert result == "MD_TASK"

        result = classifier.classify("Prepare PDB file with pdb4amber")
        assert result == "MD_TASK"

    def test_classify_empty_input(self):
        """Test classification with empty input."""
        classifier = TaskClassifier()

        result = classifier.classify("")
        assert result == "CHAT"

    def test_classify_ambiguous_task(self):
        """Test classification of ambiguous tasks."""
        classifier = TaskClassifier()

        result = classifier.classify("Do something")
        assert result == "CHAT"

    def test_classify_case_insensitive(self):
        """Test that classification is case-insensitive."""
        classifier = TaskClassifier()

        result1 = classifier.classify("RUN MINIMIZATION")
        result2 = classifier.classify("run minimization")
        assert result1 == result2 == "MD_TASK"

    def test_classify_with_special_characters(self):
        """Test classification with special characters."""
        classifier = TaskClassifier()

        result = classifier.classify("Read file: system.prmtop (important!)")
        assert result == "MD_TASK"

    def test_classify_long_input(self):
        """Test classification with very long input."""
        classifier = TaskClassifier()

        long_task = "Run sander minimization " + "x" * 1000
        result = classifier.classify(long_task)
        assert result == "MD_TASK"

    def test_classify_function_directly(self):
        """Test classify function directly."""
        result = classify("Run MD simulation")
        assert result == "MD_TASK"

        result = classify("What is AMBER?")
        assert result == "CHAT"

    def test_classifier_initialization(self):
        """Test TaskClassifier can be initialized."""
        classifier = TaskClassifier()
        assert classifier is not None

    def test_classify_multiple_keywords(self):
        """Test classification when multiple keywords present."""
        classifier = TaskClassifier()

        # Multiple MD keywords should result in MD_TASK
        result = classifier.classify("Read trajectory file and calculate RMSD")
        assert result == "MD_TASK"

    def test_classify_workflow_task(self):
        """Test classification of workflow-related tasks."""
        classifier = TaskClassifier()

        result = classifier.classify("Run complete MD workflow")
        assert result == "MD_TASK"

    def test_classify_pdb_operations(self):
        """Test classification of PDB-related operations."""
        classifier = TaskClassifier()

        result = classifier.classify("Download PDB 1AKI")
        assert result == "MD_TASK"

        result = classifier.classify("Clean PDB file with pdb4amber")
        assert result == "MD_TASK"

    def test_classify_cpptraj_tasks(self):
        """Test classification of cpptraj analysis tasks."""
        classifier = TaskClassifier()

        result = classifier.classify("Run cpptraj to analyze trajectory")
        assert result == "MD_TASK"

    def test_classify_tleap_tasks(self):
        """Test classification of tleap tasks."""
        classifier = TaskClassifier()

        result = classifier.classify("Use tleap to build system")
        assert result == "MD_TASK"

    def test_classify_antechamber_tasks(self):
        """Test classification of antechamber tasks."""
        classifier = TaskClassifier()

        result = classifier.classify("Parameterize ligand with antechamber")
        assert result == "MD_TASK"

    def test_classify_chinese_input(self):
        """Test classification with Chinese characters."""
        classifier = TaskClassifier()

        result = classifier.classify("运行分子动力学模拟")
        assert result == "MD_TASK"

        result = classifier.classify("构建蛋白质拓扑")
        assert result == "MD_TASK"

    def test_classify_with_numbers(self):
        """Test classification with numerical values."""
        classifier = TaskClassifier()

        result = classifier.classify("Run 100ns MD simulation at 300K")
        assert result == "MD_TASK"

    def test_classify_batch_operations(self):
        """Test classification of batch operations."""
        classifier = TaskClassifier()

        tasks = [
            "Read system.prmtop",
            "Calculate RMSD",
            "Run minimization",
            "What is the energy?",
        ]

        results = [classifier.classify(task) for task in tasks]

        assert results[0] == "MD_TASK"
        assert results[1] == "MD_TASK"
        assert results[2] == "MD_TASK"
        assert results[3] == "CHAT"

    def test_classify_with_whitespace(self):
        """Test classification with extra whitespace."""
        classifier = TaskClassifier()

        result = classifier.classify("  Run   minimization  ")
        assert result == "MD_TASK"

    def test_classify_multiline_input(self):
        """Test classification with multiline input."""
        classifier = TaskClassifier()

        multiline = """Run minimization
        with sander
        for 1000 steps"""

        result = classifier.classify(multiline)
        assert result == "MD_TASK"

    def test_classify_for_inspector(self):
        """Test classify_for_inspector method."""
        classifier = TaskClassifier()

        result = classifier.classify_for_inspector("Run MD simulation")
        assert result == "workflow"

        result = classifier.classify_for_inspector("What is AMBER?")
        assert result == "chat"

    def test_classify_negative_signals(self):
        """Test that negative signals reduce score."""
        classifier = TaskClassifier()

        # Question about MD should be CHAT
        result = classifier.classify("What is the difference between NVT and NPT?")
        assert result == "CHAT"

        result = classifier.classify("Explain how tleap works")
        assert result == "CHAT"

    def test_classify_pdb_id_pattern(self):
        """Test PDB ID pattern recognition."""
        classifier = TaskClassifier()

        result = classifier.classify("Download 1AKI")
        assert result == "MD_TASK"

        result = classifier.classify("Process PDB:4AKE")
        assert result == "MD_TASK"

    def test_classify_force_field_keywords(self):
        """Test force field keyword recognition."""
        classifier = TaskClassifier()

        result = classifier.classify("Use ff19SB force field")
        assert result == "MD_TASK"

        result = classifier.classify("Apply GAFF2 parameters")
        assert result == "MD_TASK"

    def test_classify_water_model_keywords(self):
        """Test water model keyword recognition."""
        classifier = TaskClassifier()

        result = classifier.classify("Solvate with OPC3 water")
        assert result == "MD_TASK"

        result = classifier.classify("Use TIP3P water model")
        assert result == "MD_TASK"

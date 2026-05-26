"""Unit tests for RichProgressManager."""

import io
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from rich.console import Console

from mdpilot.types import ProgressStage, TaskProgress
from mdpilot.ui.progress_tracker import TaskProgressTracker
from mdpilot.ui.rich_progress import RichProgressManager


@pytest.fixture
def tracker():
    """Create a TaskProgressTracker for testing."""
    return TaskProgressTracker()


@pytest.fixture
def test_console():
    """Create a console optimized for testing."""
    return Console(
        file=io.StringIO(),
        force_terminal=True,
        width=80,
        color_system="truecolor",
        legacy_windows=False,
        _environ={},
    )


class TestRichProgressManagerInit:
    """Test RichProgressManager initialization."""
    
    def test_init_with_tracker(self, tracker):
        """Test initialization with tracker."""
        manager = RichProgressManager(tracker)
        assert manager.tracker is tracker
        assert manager.progress is None
        assert manager._rich_tasks == {}


class TestRichProgressManagerContextManager:
    """Test context manager protocol."""
    
    def test_context_manager_starts_and_stops(self, tracker):
        """Test __enter__ and __exit__ start/stop progress."""
        manager = RichProgressManager(tracker)
        
        with manager:
            assert manager.progress is not None
        
        assert manager.progress is None
    
    def test_context_manager_with_exception(self, tracker):
        """Test context manager stops progress even on exception."""
        manager = RichProgressManager(tracker)
        
        try:
            with manager:
                assert manager.progress is not None
                raise ValueError("Test error")
        except ValueError:
            pass
        
        assert manager.progress is None


class TestRichProgressManagerStartStop:
    """Test start and stop methods."""
    
    def test_start_creates_progress(self, tracker):
        """Test start creates Progress instance."""
        manager = RichProgressManager(tracker)
        manager.start()
        
        assert manager.progress is not None
        
        manager.stop()
    
    def test_stop_clears_progress(self, tracker):
        """Test stop clears Progress instance."""
        manager = RichProgressManager(tracker)
        manager.start()
        manager.stop()
        
        assert manager.progress is None
    
    def test_stop_without_start(self, tracker):
        """Test stop without start doesn't raise error."""
        manager = RichProgressManager(tracker)
        manager.stop()


class TestRichProgressManagerRefresh:
    """Test refresh method."""
    
    def test_refresh_without_progress(self, tracker):
        """Test refresh without started progress doesn't raise error."""
        manager = RichProgressManager(tracker)
        manager.refresh()
    
    def test_refresh_adds_new_tasks(self, tracker):
        """Test refresh adds new tasks from tracker."""
        tracker.add_task("task1", "Test Task 1", total_steps=5)
        
        manager = RichProgressManager(tracker)
        manager.start()
        
        manager.refresh()
        
        assert "task1" in manager._rich_tasks
        
        manager.stop()
    
    def test_refresh_updates_existing_tasks(self, tracker):
        """Test refresh updates existing task progress."""
        tracker.add_task("task1", "Test Task 1", total_steps=5)
        
        manager = RichProgressManager(tracker)
        manager.start()
        manager.refresh()
        
        new_progress = TaskProgress(
            task_id="task1",
            stage=ProgressStage.RUNNING,
            current_step=3,
            total_steps=5,
            percent=60,
            message="Running step 3",
            timestamp=datetime.now()
        )
        tracker.update_progress("task1", new_progress)
        
        manager.refresh()
        
        manager.stop()
    
    def test_refresh_handles_multiple_tasks(self, tracker):
        """Test refresh handles multiple tasks."""
        tracker.add_task("task1", "Task 1", total_steps=5)
        tracker.add_task("task2", "Task 2", total_steps=3)
        tracker.add_task("task3", "Task 3", total_steps=10)
        
        manager = RichProgressManager(tracker)
        manager.start()
        
        manager.refresh()
        
        assert len(manager._rich_tasks) == 3
        assert "task1" in manager._rich_tasks
        assert "task2" in manager._rich_tasks
        assert "task3" in manager._rich_tasks
        
        manager.stop()


class TestRichProgressManagerStageDisplay:
    """Test stage-specific display formatting."""
    
    def test_queued_stage_display(self, tracker):
        """Test QUEUED stage displays with correct color/icon."""
        tracker.add_task("task1", "Queued Task", total_steps=5)
        
        manager = RichProgressManager(tracker)
        manager.start()
        manager.refresh()
        manager.stop()
    
    def test_running_stage_display(self, tracker):
        """Test RUNNING stage displays with correct color/icon."""
        tracker.add_task("task1", "Running Task", total_steps=5)
        
        new_progress = TaskProgress(
            task_id="task1",
            stage=ProgressStage.RUNNING,
            current_step=2,
            total_steps=5,
            percent=40,
            message="Running",
            timestamp=datetime.now()
        )
        tracker.update_progress("task1", new_progress)
        
        manager = RichProgressManager(tracker)
        manager.start()
        manager.refresh()
        manager.stop()
    
    def test_completed_stage_display(self, tracker):
        """Test COMPLETED stage displays with correct color/icon."""
        tracker.add_task("task1", "Completed Task", total_steps=5)
        
        new_progress = TaskProgress(
            task_id="task1",
            stage=ProgressStage.COMPLETED,
            current_step=5,
            total_steps=5,
            percent=100,
            message="Completed",
            timestamp=datetime.now()
        )
        tracker.update_progress("task1", new_progress)
        
        manager = RichProgressManager(tracker)
        manager.start()
        manager.refresh()
        manager.stop()
    
    def test_failed_stage_display(self, tracker):
        """Test FAILED stage displays with correct color/icon."""
        tracker.add_task("task1", "Failed Task", total_steps=5)
        
        new_progress = TaskProgress(
            task_id="task1",
            stage=ProgressStage.FAILED,
            current_step=2,
            total_steps=5,
            percent=40,
            message="Failed",
            timestamp=datetime.now(),
            error="Test error"
        )
        tracker.update_progress("task1", new_progress)
        
        manager = RichProgressManager(tracker)
        manager.start()
        manager.refresh()
        manager.stop()

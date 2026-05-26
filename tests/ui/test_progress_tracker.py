"""Unit tests for TaskProgressTracker."""

import pytest
from datetime import datetime
from threading import Thread
from time import sleep

from mdpilot.types import ProgressStage, TaskProgress
from mdpilot.ui.progress_tracker import TaskProgressTracker, StageInfo, STAGE_INFO_MAP


class TestStageInfoMap:
    """Test STAGE_INFO_MAP completeness."""
    
    def test_all_stages_have_info(self):
        """Verify all ProgressStage values have corresponding StageInfo."""
        for stage in ProgressStage:
            assert stage in STAGE_INFO_MAP, f"Missing StageInfo for {stage}"
            info = STAGE_INFO_MAP[stage]
            assert isinstance(info, StageInfo)
            assert info.name
            assert info.description
            assert info.icon
            assert info.color


class TestTaskProgressTrackerInit:
    """Test TaskProgressTracker initialization."""
    
    def test_init_creates_empty_tracker(self):
        """Test tracker initializes with no tasks."""
        tracker = TaskProgressTracker()
        assert tracker.get_all_tasks() == {}


class TestTaskProgressTrackerAddTask:
    """Test adding tasks to tracker."""
    
    def test_add_task_creates_queued_task(self):
        """Test add_task creates task in QUEUED state."""
        tracker = TaskProgressTracker()
        tracker.add_task("task1", "Test Task", total_steps=5)
        
        progress = tracker.get_progress("task1")
        assert progress is not None
        assert progress.task_id == "task1"
        assert progress.stage == ProgressStage.QUEUED
        assert progress.current_step == 0
        assert progress.total_steps == 5
        assert progress.percent == 0
        assert progress.message == "Test Task"
        assert isinstance(progress.timestamp, datetime)
    
    def test_add_multiple_tasks(self):
        """Test adding multiple tasks."""
        tracker = TaskProgressTracker()
        tracker.add_task("task1", "Task 1", total_steps=3)
        tracker.add_task("task2", "Task 2", total_steps=5)
        
        all_tasks = tracker.get_all_tasks()
        assert len(all_tasks) == 2
        assert "task1" in all_tasks
        assert "task2" in all_tasks


class TestTaskProgressTrackerUpdateProgress:
    """Test updating task progress."""
    
    def test_update_progress_changes_state(self):
        """Test update_progress updates task state."""
        tracker = TaskProgressTracker()
        tracker.add_task("task1", "Test Task", total_steps=5)
        
        new_progress = TaskProgress(
            task_id="task1",
            stage=ProgressStage.RUNNING,
            current_step=2,
            total_steps=5,
            percent=40,
            message="Running step 2",
            timestamp=datetime.now()
        )
        
        tracker.update_progress("task1", new_progress)
        
        progress = tracker.get_progress("task1")
        assert progress.stage == ProgressStage.RUNNING
        assert progress.current_step == 2
        assert progress.percent == 40
        assert progress.message == "Running step 2"
    
    def test_update_nonexistent_task(self):
        """Test updating a task that doesn't exist creates it."""
        tracker = TaskProgressTracker()
        
        new_progress = TaskProgress(
            task_id="task1",
            stage=ProgressStage.RUNNING,
            current_step=1,
            total_steps=3,
            percent=33,
            message="Running",
            timestamp=datetime.now()
        )
        
        tracker.update_progress("task1", new_progress)
        
        progress = tracker.get_progress("task1")
        assert progress is not None
        assert progress.stage == ProgressStage.RUNNING


class TestTaskProgressTrackerGetProgress:
    """Test getting task progress."""
    
    def test_get_progress_existing_task(self):
        """Test get_progress returns correct task."""
        tracker = TaskProgressTracker()
        tracker.add_task("task1", "Test Task", total_steps=5)
        
        progress = tracker.get_progress("task1")
        assert progress is not None
        assert progress.task_id == "task1"
    
    def test_get_progress_nonexistent_task(self):
        """Test get_progress returns None for nonexistent task."""
        tracker = TaskProgressTracker()
        
        progress = tracker.get_progress("nonexistent")
        assert progress is None


class TestTaskProgressTrackerRemoveTask:
    """Test removing tasks."""
    
    def test_remove_task_deletes_task(self):
        """Test remove_task deletes the task."""
        tracker = TaskProgressTracker()
        tracker.add_task("task1", "Test Task", total_steps=5)
        
        tracker.remove_task("task1")
        
        progress = tracker.get_progress("task1")
        assert progress is None
    
    def test_remove_nonexistent_task(self):
        """Test removing nonexistent task doesn't raise error."""
        tracker = TaskProgressTracker()
        tracker.remove_task("nonexistent")


class TestTaskProgressTrackerGetAllTasks:
    """Test getting all tasks."""
    
    def test_get_all_tasks_returns_copy(self):
        """Test get_all_tasks returns a copy, not reference."""
        tracker = TaskProgressTracker()
        tracker.add_task("task1", "Test Task", total_steps=5)
        
        all_tasks = tracker.get_all_tasks()
        all_tasks["task2"] = None
        
        assert "task2" not in tracker.get_all_tasks()
    
    def test_get_all_tasks_empty(self):
        """Test get_all_tasks returns empty dict when no tasks."""
        tracker = TaskProgressTracker()
        assert tracker.get_all_tasks() == {}


class TestTaskProgressTrackerThreadSafety:
    """Test thread safety of TaskProgressTracker."""
    
    def test_concurrent_add_tasks(self):
        """Test adding tasks from multiple threads."""
        tracker = TaskProgressTracker()
        
        def add_tasks(start_id):
            for i in range(10):
                tracker.add_task(f"task{start_id + i}", f"Task {start_id + i}", total_steps=5)
        
        threads = [
            Thread(target=add_tasks, args=(0,)),
            Thread(target=add_tasks, args=(10,)),
            Thread(target=add_tasks, args=(20,)),
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        all_tasks = tracker.get_all_tasks()
        assert len(all_tasks) == 30
    
    def test_concurrent_update_progress(self):
        """Test updating progress from multiple threads."""
        tracker = TaskProgressTracker()
        tracker.add_task("task1", "Test Task", total_steps=100)
        
        def update_progress(step):
            for i in range(10):
                new_progress = TaskProgress(
                    task_id="task1",
                    stage=ProgressStage.RUNNING,
                    current_step=step * 10 + i,
                    total_steps=100,
                    percent=(step * 10 + i),
                    message=f"Step {step * 10 + i}",
                    timestamp=datetime.now()
                )
                tracker.update_progress("task1", new_progress)
                sleep(0.001)
        
        threads = [
            Thread(target=update_progress, args=(0,)),
            Thread(target=update_progress, args=(1,)),
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        progress = tracker.get_progress("task1")
        assert progress is not None

import pytest
from datetime import datetime
from src.mdpilot.types import ProgressStage, TaskProgress

def test_progress_stage_enum():
    """测试进度阶段枚举"""
    assert ProgressStage.PREPARING.value == "preparing"
    assert ProgressStage.EXECUTING.value == "executing"
    assert ProgressStage.PARSING.value == "parsing"
    assert ProgressStage.COMPLETED.value == "completed"

def test_task_progress_creation():
    """测试任务进度创建"""
    progress = TaskProgress(
        task_id="test-123",
        stage=ProgressStage.EXECUTING,
        current_step=2,
        total_steps=4,
        percent=50,
        message="正在运行 GO-GPT 推理",
        timestamp=datetime.now()
    )
    
    assert progress.task_id == "test-123"
    assert progress.stage == ProgressStage.EXECUTING
    assert progress.percent == 50

def test_task_progress_to_dict():
    """测试进度序列化"""
    now = datetime.now()
    progress = TaskProgress(
        task_id="test-123",
        stage=ProgressStage.EXECUTING,
        current_step=2,
        total_steps=4,
        percent=50,
        message="正在运行 GO-GPT 推理",
        timestamp=now
    )
    
    result = progress.to_dict()
    
    assert result["task_id"] == "test-123"
    assert result["stage"] == "executing"
    assert result["percent"] == 50
    assert "timestamp" in result

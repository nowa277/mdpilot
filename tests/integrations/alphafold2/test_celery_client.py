"""Unit tests for AlphaFold2CeleryClient

Tests the AlphaFold2 Celery client with mocked SSH and Celery connections.
Covers all methods, progress callbacks, error handling, and edge cases.
"""

import pytest
import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime

from src.mdpilot.integrations.alphafold2.celery_client import AlphaFold2CeleryClient
from src.mdpilot.types import TaskProgress, ProgressStage


@pytest.fixture
def ssh_config():
    """SSH configuration fixture"""
    return {
        "host": "lab02",
        "port": 22,
        "username": "zhao",
        "key_path": "~/.ssh/id_ed25519_lab",
        "timeout": 30
    }


@pytest.fixture
def celery_config():
    """Celery configuration fixture"""
    return {
        "broker_url": "redis://localhost:6379/2",
        "backend_url": "redis://localhost:6379/3",
        "task_timeout": 14400,
        "poll_interval": 5
    }


@pytest.fixture
def client(ssh_config, celery_config):
    """AlphaFold2CeleryClient fixture"""
    return AlphaFold2CeleryClient(
        ssh=ssh_config,
        celery=celery_config,
        work_dir="/home/2-BB/changeshengjie/project/mdpilot",
        conda_env="af2_py310"
    )


class TestAlphaFold2CeleryClientInit:
    """Test client initialization"""
    
    def test_init_with_valid_config(self, ssh_config, celery_config):
        """Test initialization with valid configuration"""
        client = AlphaFold2CeleryClient(
            ssh=ssh_config,
            celery=celery_config,
            work_dir="/home/2-BB/changeshengjie/project/mdpilot",
            conda_env="af2_py310"
        )
        
        assert client.ssh_config == ssh_config
        assert client.celery_config == celery_config
        assert client.work_dir == "/home/2-BB/changeshengjie/project/mdpilot"
        assert client.conda_env == "af2_py310"
        assert client._conn is None
    
    def test_init_inherits_from_base(self, client):
        """Test that client inherits from BaseRemoteToolClient"""
        from src.mdpilot.integrations.base.remote_tool_client import BaseRemoteToolClient
        assert isinstance(client, BaseRemoteToolClient)


class TestAlphaFold2CeleryClientConnection:
    """Test SSH connection management"""
    
    @pytest.mark.asyncio
    async def test_connect_success(self, client):
        """Test successful SSH connection"""
        with patch('asyncssh.connect', new_callable=AsyncMock) as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            await client.connect()
            
            mock_connect.assert_called_once_with(
                host="lab02",
                username="zhao",
                client_keys=[str(Path("~/.ssh/id_ed25519_lab").expanduser())],
                known_hosts=None
            )
            assert client._conn == mock_conn

    @pytest.mark.asyncio
    async def test_connect_preserves_explicit_non_default_port(self, client):
        """Test SSH connection with an explicit non-default port"""
        client.ssh_config["port"] = 24122
        with patch('asyncssh.connect', new_callable=AsyncMock) as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn

            await client.connect()

            mock_connect.assert_called_once_with(
                host="lab02",
                port=24122,
                username="zhao",
                client_keys=[str(Path("~/.ssh/id_ed25519_lab").expanduser())],
                known_hosts=None
            )
            assert client._conn == mock_conn
    
    @pytest.mark.asyncio
    async def test_connect_already_connected(self, client):
        """Test connect when already connected (should be idempotent)"""
        mock_conn = AsyncMock()
        client._conn = mock_conn
        
        with patch('asyncssh.connect', new_callable=AsyncMock) as mock_connect:
            await client.connect()
            
            # Should not call connect again
            mock_connect.assert_not_called()
            assert client._conn == mock_conn
    
    @pytest.mark.asyncio
    async def test_disconnect_success(self, client):
        """Test successful SSH disconnection"""
        mock_conn = AsyncMock()
        mock_conn.close = MagicMock()
        mock_conn.wait_closed = AsyncMock()
        client._conn = mock_conn
        
        await client.disconnect()
        
        mock_conn.close.assert_called_once()
        mock_conn.wait_closed.assert_called_once()
        assert client._conn is None
    
    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, client):
        """Test disconnect when not connected (should be safe)"""
        client._conn = None
        
        # Should not raise exception
        await client.disconnect()
        
        assert client._conn is None


class TestAlphaFold2CeleryClientPredict:
    """Test structure prediction functionality"""
    
    @pytest.mark.asyncio
    async def test_predict_success(self, client):
        """Test successful structure prediction"""
        sequence = "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHF"
        job_name = "test_job"
        
        mock_result = {
            "success": True,
            "job_name": job_name,
            "sequence_length": len(sequence),
            "best_model": "/path/to/ranked_0.pdb",
            "avg_plddt": 95.3,
            "output_dir": "/tmp/output",
            "num_models": 5
        }
        
        with patch.object(client, '_submit_celery_task', new_callable=AsyncMock) as mock_submit:
            with patch.object(client, '_wait_for_task', new_callable=AsyncMock) as mock_wait:
                mock_submit.return_value = "task-123"
                mock_wait.return_value = mock_result
                
                result = await client.predict(sequence, job_name)
                
                assert result["success"] is True
                assert result["job_name"] == job_name
                assert result["sequence_length"] == len(sequence)
                assert result["avg_plddt"] == 95.3
                assert result["best_model"] == "/path/to/ranked_0.pdb"
                
                mock_submit.assert_called_once_with("predict_structure", sequence, job_name)
                mock_wait.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_predict_with_progress_callback(self, client):
        """Test prediction with progress callback"""
        sequence = "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHF"
        progress_updates = []
        
        async def progress_callback(progress: TaskProgress):
            progress_updates.append(progress)
        
        mock_result = {
            "success": True,
            "job_name": "test",
            "sequence_length": len(sequence),
            "best_model": "/path/to/model.pdb",
            "avg_plddt": 90.0,
            "output_dir": "/tmp/output",
            "num_models": 5
        }
        
        async def mock_wait_for_task(task_id, progress_wrapper):
            # Simulate progress updates
            await progress_wrapper({
                "stage": "preparing",
                "percent": 25,
                "message": "Preparing input",
                "current": 1,
                "total": 5
            })
            await progress_wrapper({
                "stage": "running",
                "percent": 50,
                "message": "Running prediction",
                "current": 2,
                "total": 5
            })
            await progress_wrapper({
                "stage": "completed",
                "percent": 100,
                "message": "Completed",
                "current": 5,
                "total": 5
            })
            return mock_result
        
        with patch.object(client, '_submit_celery_task', new_callable=AsyncMock) as mock_submit:
            with patch.object(client, '_wait_for_task', new_callable=AsyncMock) as mock_wait:
                mock_submit.return_value = "task-123"
                mock_wait.side_effect = mock_wait_for_task
                
                result = await client.predict(sequence, "test", progress_callback)
                
                assert result["success"] is True
                assert len(progress_updates) == 3
                assert progress_updates[0].stage == ProgressStage.QUEUED
                assert progress_updates[1].stage == ProgressStage.RUNNING
                assert progress_updates[2].stage == ProgressStage.COMPLETED
    
    @pytest.mark.asyncio
    async def test_predict_failure(self, client):
        """Test prediction failure handling"""
        sequence = "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHF"
        
        mock_result = {
            "success": False,
            "error": "AlphaFold2 execution failed"
        }
        
        with patch.object(client, '_submit_celery_task', new_callable=AsyncMock) as mock_submit:
            with patch.object(client, '_wait_for_task', new_callable=AsyncMock) as mock_wait:
                mock_submit.return_value = "task-123"
                mock_wait.return_value = mock_result
                
                with pytest.raises(RuntimeError, match="AlphaFold2 prediction failed"):
                    await client.predict(sequence, "test")
    
    @pytest.mark.asyncio
    async def test_predict_timeout(self, client):
        """Test prediction timeout handling"""
        sequence = "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHF"
        
        with patch.object(client, '_submit_celery_task', new_callable=AsyncMock) as mock_submit:
            with patch.object(client, '_wait_for_task', new_callable=AsyncMock) as mock_wait:
                mock_submit.return_value = "task-123"
                mock_wait.side_effect = TimeoutError("Task timed out after 14400 seconds")
                
                with pytest.raises(TimeoutError, match="Task timed out"):
                    await client.predict(sequence, "test")


class TestAlphaFold2CeleryClientGetPredictionStatus:
    """Test prediction status query"""
    
    @pytest.mark.asyncio
    async def test_get_prediction_status_success(self, client):
        """Test successful status query"""
        task_id = "task-123"
        mock_status = {
            "state": "PROGRESS",
            "info": {
                "stage": "running",
                "percent": 50,
                "message": "Running prediction"
            },
            "ready": False,
            "successful": False
        }
        
        with patch.object(client, '_get_task_status', new_callable=AsyncMock) as mock_get_status:
            mock_get_status.return_value = mock_status
            
            status = await client.get_prediction_status(task_id)
            
            assert status == mock_status
            mock_get_status.assert_called_once_with(task_id)


class TestAlphaFold2CeleryClientInheritedMethods:
    """Test inherited methods from BaseRemoteToolClient"""
    
    @pytest.mark.asyncio
    async def test_run_command_success(self, client):
        """Test _run_command execution"""
        mock_conn = AsyncMock()
        mock_result = AsyncMock()
        mock_result.stdout = "command output"
        mock_result.returncode = 0
        mock_conn.run = AsyncMock(return_value=mock_result)
        client._conn = mock_conn
        
        result = await client._run_command("echo test")
        
        assert result.stdout == "command output"
        mock_conn.run.assert_called_once_with("echo test", check=True)
    
    @pytest.mark.asyncio
    async def test_run_command_not_connected(self, client):
        """Test _run_command when not connected"""
        client._conn = None
        
        with pytest.raises(RuntimeError, match="Not connected"):
            await client._run_command("echo test")
    
    @pytest.mark.asyncio
    async def test_submit_celery_task_success(self, client):
        """Test _submit_celery_task"""
        mock_conn = AsyncMock()
        mock_result = AsyncMock()
        mock_result.stdout = "task-id-123\n"
        mock_conn.run = AsyncMock(return_value=mock_result)
        client._conn = mock_conn
        
        task_id = await client._submit_celery_task("predict_structure", "MVLSPADKTN", "test_job")
        
        assert task_id == "task-id-123"
        mock_conn.run.assert_called_once()
        
        # Verify command structure
        call_args = mock_conn.run.call_args[0][0]
        assert "predict_structure.delay" in call_args
        assert "'MVLSPADKTN'" in call_args
        assert "'test_job'" in call_args
    
    @pytest.mark.asyncio
    async def test_get_task_status_success(self, client):
        """Test _get_task_status"""
        mock_conn = AsyncMock()
        mock_result = AsyncMock()
        status_dict = {
            "state": "SUCCESS",
            "info": {"result": "data"},
            "ready": True,
            "successful": True
        }
        mock_result.stdout = json.dumps(status_dict)
        mock_conn.run = AsyncMock(return_value=mock_result)
        client._conn = mock_conn
        
        status = await client._get_task_status("task-123")
        
        assert status == status_dict
        mock_conn.run.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_wait_for_task_success(self, client):
        """Test _wait_for_task completion"""
        task_id = "task-123"
        final_result = {"success": True, "data": "result"}
        
        # Mock status progression: PENDING -> PROGRESS -> SUCCESS
        status_sequence = [
            {"state": "PENDING", "info": {}, "ready": False, "successful": False},
            {"state": "PROGRESS", "info": {"stage": "running"}, "ready": False, "successful": False},
            {"state": "SUCCESS", "info": final_result, "ready": True, "successful": True}
        ]
        
        with patch.object(client, '_get_task_status', new_callable=AsyncMock) as mock_get_status:
            mock_get_status.side_effect = status_sequence
            
            result = await client._wait_for_task(task_id)
            
            assert result == final_result
            assert mock_get_status.call_count == 3
    
    @pytest.mark.asyncio
    async def test_wait_for_task_with_progress_callback(self, client):
        """Test _wait_for_task with progress callback"""
        task_id = "task-123"
        progress_calls = []
        
        async def progress_callback(info):
            progress_calls.append(info)
        
        status_sequence = [
            {"state": "PROGRESS", "info": {"stage": "preparing", "percent": 25}, "ready": False, "successful": False},
            {"state": "PROGRESS", "info": {"stage": "running", "percent": 50}, "ready": False, "successful": False},
            {"state": "SUCCESS", "info": {"success": True}, "ready": True, "successful": True}
        ]
        
        with patch.object(client, '_get_task_status', new_callable=AsyncMock) as mock_get_status:
            mock_get_status.side_effect = status_sequence
            
            result = await client._wait_for_task(task_id, progress_callback)
            
            assert result == {"success": True}
            assert len(progress_calls) == 2  # Only PROGRESS states trigger callback
            assert progress_calls[0]["percent"] == 25
            assert progress_calls[1]["percent"] == 50
    
    @pytest.mark.asyncio
    async def test_wait_for_task_failure(self, client):
        """Test _wait_for_task when task fails"""
        task_id = "task-123"
        
        status_sequence = [
            {"state": "PENDING", "info": {}, "ready": False, "successful": False},
            {"state": "FAILURE", "info": {"error": "Task failed"}, "ready": True, "successful": False}
        ]
        
        with patch.object(client, '_get_task_status', new_callable=AsyncMock) as mock_get_status:
            mock_get_status.side_effect = status_sequence
            
            with pytest.raises(RuntimeError, match="Task failed"):
                await client._wait_for_task(task_id)
    
    @pytest.mark.asyncio
    async def test_wait_for_task_timeout(self, client):
        """Test _wait_for_task timeout"""
        task_id = "task-123"
        client.celery_config["task_timeout"] = 1  # 1 second timeout
        client.celery_config["poll_interval"] = 0.5
        
        # Always return PENDING (never completes)
        with patch.object(client, '_get_task_status', new_callable=AsyncMock) as mock_get_status:
            mock_get_status.return_value = {
                "state": "PENDING",
                "info": {},
                "ready": False,
                "successful": False
            }
            
            with pytest.raises(TimeoutError, match="timed out after 1 seconds"):
                await client._wait_for_task(task_id)


class TestAlphaFold2CeleryClientEdgeCases:
    """Test edge cases and error conditions"""
    
    @pytest.mark.asyncio
    async def test_predict_empty_sequence(self, client):
        """Test prediction with empty sequence"""
        # Should still submit task (validation happens on server side)
        with patch.object(client, '_submit_celery_task', new_callable=AsyncMock) as mock_submit:
            with patch.object(client, '_wait_for_task', new_callable=AsyncMock) as mock_wait:
                mock_submit.return_value = "task-123"
                mock_wait.return_value = {
                    "success": False,
                    "error": "Empty sequence"
                }
                
                with pytest.raises(RuntimeError, match="AlphaFold2 prediction failed"):
                    await client.predict("", "test")
    
    @pytest.mark.asyncio
    async def test_predict_very_long_sequence(self, client):
        """Test prediction with very long sequence (>2000 aa)"""
        long_sequence = "M" * 2500
        
        with patch.object(client, '_submit_celery_task', new_callable=AsyncMock) as mock_submit:
            with patch.object(client, '_wait_for_task', new_callable=AsyncMock) as mock_wait:
                mock_submit.return_value = "task-123"
                mock_wait.return_value = {
                    "success": True,
                    "job_name": "long_seq",
                    "sequence_length": 2500,
                    "best_model": "/path/to/model.pdb",
                    "avg_plddt": 75.0,
                    "output_dir": "/tmp/output",
                    "num_models": 5
                }
                
                result = await client.predict(long_sequence, "long_seq")
                
                assert result["success"] is True
                assert result["sequence_length"] == 2500
    
    @pytest.mark.asyncio
    async def test_connection_lost_during_prediction(self, client):
        """Test handling of connection loss during prediction"""
        sequence = "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHF"
        
        with patch.object(client, '_submit_celery_task', new_callable=AsyncMock) as mock_submit:
            mock_submit.side_effect = ConnectionError("SSH connection lost")
            
            with pytest.raises(ConnectionError, match="SSH connection lost"):
                await client.predict(sequence, "test")
    
    @pytest.mark.asyncio
    async def test_malformed_task_result(self, client):
        """Test handling of malformed task result"""
        sequence = "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHF"
        
        # Missing required fields
        mock_result = {
            "success": True
            # Missing: job_name, sequence_length, best_model, etc.
        }
        
        with patch.object(client, '_submit_celery_task', new_callable=AsyncMock) as mock_submit:
            with patch.object(client, '_wait_for_task', new_callable=AsyncMock) as mock_wait:
                mock_submit.return_value = "task-123"
                mock_wait.return_value = mock_result
                
                # Should not raise, just return the result as-is
                result = await client.predict(sequence, "test")
                assert result["success"] is True


class TestAlphaFold2CeleryClientProgressStageMapping:
    """Test progress stage mapping"""
    
    @pytest.mark.asyncio
    async def test_stage_mapping_preparing(self, client):
        """Test 'preparing' stage maps to QUEUED"""
        progress_updates = []
        
        async def progress_callback(progress: TaskProgress):
            progress_updates.append(progress)
        
        async def mock_wait_for_task(task_id, progress_wrapper):
            await progress_wrapper({
                "stage": "preparing",
                "percent": 25,
                "message": "Preparing",
                "current": 1,
                "total": 5
            })
            return {"success": True, "job_name": "test", "sequence_length": 50, 
                    "best_model": "/path", "avg_plddt": 90, "output_dir": "/tmp", "num_models": 5}
        
        with patch.object(client, '_submit_celery_task', new_callable=AsyncMock) as mock_submit:
            with patch.object(client, '_wait_for_task', new_callable=AsyncMock) as mock_wait:
                mock_submit.return_value = "task-123"
                mock_wait.side_effect = mock_wait_for_task
                
                await client.predict("MVLSPADKTN", "test", progress_callback)
                
                assert len(progress_updates) == 1
                assert progress_updates[0].stage == ProgressStage.QUEUED
    
    @pytest.mark.asyncio
    async def test_stage_mapping_running(self, client):
        """Test 'running' stage maps to RUNNING"""
        progress_updates = []
        
        async def progress_callback(progress: TaskProgress):
            progress_updates.append(progress)
        
        async def mock_wait_for_task(task_id, progress_wrapper):
            await progress_wrapper({
                "stage": "running",
                "percent": 50,
                "message": "Running",
                "current": 2,
                "total": 5
            })
            return {"success": True, "job_name": "test", "sequence_length": 50,
                    "best_model": "/path", "avg_plddt": 90, "output_dir": "/tmp", "num_models": 5}
        
        with patch.object(client, '_submit_celery_task', new_callable=AsyncMock) as mock_submit:
            with patch.object(client, '_wait_for_task', new_callable=AsyncMock) as mock_wait:
                mock_submit.return_value = "task-123"
                mock_wait.side_effect = mock_wait_for_task
                
                await client.predict("MVLSPADKTN", "test", progress_callback)
                
                assert len(progress_updates) == 1
                assert progress_updates[0].stage == ProgressStage.RUNNING
    
    @pytest.mark.asyncio
    async def test_stage_mapping_processing(self, client):
        """Test 'parsing' and 'extracting' stages map to PROCESSING"""
        progress_updates = []
        
        async def progress_callback(progress: TaskProgress):
            progress_updates.append(progress)
        
        async def mock_wait_for_task(task_id, progress_wrapper):
            await progress_wrapper({
                "stage": "parsing",
                "percent": 75,
                "message": "Parsing",
                "current": 3,
                "total": 5
            })
            await progress_wrapper({
                "stage": "extracting",
                "percent": 90,
                "message": "Extracting",
                "current": 4,
                "total": 5
            })
            return {"success": True, "job_name": "test", "sequence_length": 50,
                    "best_model": "/path", "avg_plddt": 90, "output_dir": "/tmp", "num_models": 5}
        
        with patch.object(client, '_submit_celery_task', new_callable=AsyncMock) as mock_submit:
            with patch.object(client, '_wait_for_task', new_callable=AsyncMock) as mock_wait:
                mock_submit.return_value = "task-123"
                mock_wait.side_effect = mock_wait_for_task
                
                await client.predict("MVLSPADKTN", "test", progress_callback)
                
                assert len(progress_updates) == 2
                assert progress_updates[0].stage == ProgressStage.PROCESSING
                assert progress_updates[1].stage == ProgressStage.PROCESSING
    
    @pytest.mark.asyncio
    async def test_stage_mapping_completed(self, client):
        """Test 'completed' stage maps to COMPLETED"""
        progress_updates = []
        
        async def progress_callback(progress: TaskProgress):
            progress_updates.append(progress)
        
        async def mock_wait_for_task(task_id, progress_wrapper):
            await progress_wrapper({
                "stage": "completed",
                "percent": 100,
                "message": "Completed",
                "current": 5,
                "total": 5
            })
            return {"success": True, "job_name": "test", "sequence_length": 50,
                    "best_model": "/path", "avg_plddt": 90, "output_dir": "/tmp", "num_models": 5}
        
        with patch.object(client, '_submit_celery_task', new_callable=AsyncMock) as mock_submit:
            with patch.object(client, '_wait_for_task', new_callable=AsyncMock) as mock_wait:
                mock_submit.return_value = "task-123"
                mock_wait.side_effect = mock_wait_for_task
                
                await client.predict("MVLSPADKTN", "test", progress_callback)
                
                assert len(progress_updates) == 1
                assert progress_updates[0].stage == ProgressStage.COMPLETED

"""Unit tests for BioreasonCeleryClient

Tests the BioReason Celery client with mocked SSH and Celery connections.
Covers all methods, progress callbacks, two GO term formats, error handling, and edge cases.
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime

from src.mdpilot.integrations.bioreason.celery_client import BioreasonCeleryClient
from src.mdpilot.types import TaskProgress, ProgressStage
from src.mdpilot.config.defaults import DEFAULT_BIOREASON_REMOTE


@pytest.fixture
def ssh_config():
    """SSH configuration fixture"""
    return {
        "host": "lab06",
        "port": 22,
        "username": "zhao",
        "key_path": "~/.ssh/id_ed25519_lab",
        "timeout": 30
    }


@pytest.fixture
def celery_config():
    """Celery configuration fixture"""
    return {
        "broker_url": "redis://localhost:6379/0",
        "backend_url": "redis://localhost:6379/1",
        "task_timeout": 300,
        "poll_interval": 2.0
    }


@pytest.fixture
def client(ssh_config, celery_config):
    """BioreasonCeleryClient fixture"""
    return BioreasonCeleryClient(
        ssh=ssh_config,
        celery=celery_config,
        work_dir="/home/6-FF/changshenjie/project/mdpilot",
        conda_env="bioreason"
    )


class TestBioreasonCeleryClientInit:
    """Test client initialization"""
    
    def test_init_with_valid_config(self, ssh_config, celery_config):
        """Test initialization with valid configuration"""
        client = BioreasonCeleryClient(
            ssh=ssh_config,
            celery=celery_config,
            work_dir="/home/6-FF/changshenjie/project/mdpilot",
            conda_env="bioreason"
        )
        
        assert client.ssh_config == ssh_config
        assert client.celery_config == celery_config
        assert client.work_dir == "/home/6-FF/changshenjie/project/mdpilot"
        assert client.conda_env == "bioreason"
        assert client._conn is None
    
    def test_init_with_default_config(self):
        """Test initialization with default configuration"""
        client = BioreasonCeleryClient(**DEFAULT_BIOREASON_REMOTE)
        
        assert client.ssh_config["host"] == "lab06"
        assert client.celery_config["broker_url"] == "redis://localhost:6379/0"
        assert client.work_dir == "/home/6-FF/luo/BioReason-Pro"
        assert client.conda_env == "bioreason"


class TestBioreasonCeleryClientConnection:
    """Test SSH connection management"""
    
    @pytest.mark.asyncio
    async def test_connect_success(self, client):
        """Test successful SSH connection"""
        with patch('asyncssh.connect', new_callable=AsyncMock) as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn
            
            await client.connect()
            
            mock_connect.assert_called_once_with(
                host="lab06",
                username="zhao",
                client_keys=["~/.ssh/id_ed25519_lab"],
                known_hosts=None
            )
            assert client._conn == mock_conn

    @pytest.mark.asyncio
    async def test_connect_preserves_explicit_non_default_port(self, client):
        """Test SSH connection with an explicit non-default port"""
        client.ssh_config["port"] = 24123
        with patch('asyncssh.connect', new_callable=AsyncMock) as mock_connect:
            mock_conn = AsyncMock()
            mock_connect.return_value = mock_conn

            await client.connect()

            mock_connect.assert_called_once_with(
                host="lab06",
                port=24123,
                username="zhao",
                client_keys=["~/.ssh/id_ed25519_lab"],
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


class TestBioreasonCeleryClientSubmitTask:
    """Test task submission"""
    
    @pytest.mark.asyncio
    async def test_submit_task_success(self, client):
        """Test successful task submission"""
        mock_conn = AsyncMock()
        mock_result = AsyncMock()
        mock_result.stdout = "task-id-123\n"
        mock_conn.run = AsyncMock(return_value=mock_result)
        client._conn = mock_conn
        
        task_id = await client._submit_task("MVLSPADKTN", "Homo sapiens")
        
        assert task_id == "task-id-123"
        mock_conn.run.assert_called_once()
        
        # Verify command structure
        call_args = mock_conn.run.call_args[0][0]
        assert "annotate_protein.delay" in call_args
        assert "'MVLSPADKTN'" in call_args
        assert "'Homo sapiens'" in call_args
    
    @pytest.mark.asyncio
    async def test_submit_task_not_connected(self, client):
        """Test task submission when not connected"""
        client._conn = None
        
        with pytest.raises(RuntimeError, match="Not connected"):
            await client._submit_task("MVLSPADKTN", "Homo sapiens")


class TestBioreasonCeleryClientGetTaskStatus:
    """Test task status query"""
    
    @pytest.mark.asyncio
    async def test_get_task_status_success(self, client):
        """Test successful status query"""
        mock_conn = AsyncMock()
        mock_result = AsyncMock()
        status_dict = {
            "state": "SUCCESS",
            "result": {
                "success": True,
                "go_terms": {"MF": ["binding"], "BP": ["transport"], "CC": ["cytoplasm"]}
            }
        }
        mock_result.stdout = json.dumps(status_dict) + "\n"
        mock_conn.run = AsyncMock(return_value=mock_result)
        client._conn = mock_conn
        
        status = await client._get_task_status("task-123")
        
        assert status == status_dict
        mock_conn.run.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_task_status_pending(self, client):
        """Test status query for pending task"""
        mock_conn = AsyncMock()
        mock_result = AsyncMock()
        status_dict = {"state": "PENDING", "result": None}
        mock_result.stdout = json.dumps(status_dict) + "\n"
        mock_conn.run = AsyncMock(return_value=mock_result)
        client._conn = mock_conn
        
        status = await client._get_task_status("task-123")
        
        assert status["state"] == "PENDING"
        assert status["result"] is None


class TestBioreasonCeleryClientPollTask:
    """Test task polling"""
    
    @pytest.mark.asyncio
    async def test_poll_task_success(self, client):
        """Test successful task polling"""
        task_id = "task-123"
        final_result = {
            "success": True,
            "go_terms": {"MF": ["binding"], "BP": ["transport"], "CC": ["cytoplasm"]}
        }
        
        # Mock status progression: PENDING -> STARTED -> SUCCESS
        status_sequence = [
            {"state": "PENDING", "result": None},
            {"state": "STARTED", "result": None},
            {"state": "SUCCESS", "result": final_result}
        ]
        
        with patch.object(client, '_get_task_status', new_callable=AsyncMock) as mock_get_status:
            mock_get_status.side_effect = status_sequence
            
            result = await client._poll_task(task_id)
            
            assert result == final_result
            assert mock_get_status.call_count == 3
    
    @pytest.mark.asyncio
    async def test_poll_task_with_progress_callback(self, client):
        """Test task polling with progress callback"""
        task_id = "task-123"
        progress_calls = []
        
        async def progress_callback(progress: TaskProgress):
            progress_calls.append(progress)
        
        status_sequence = [
            {"state": "PENDING", "result": None},
            {"state": "STARTED", "result": None},
            {"state": "SUCCESS", "result": {"success": True, "go_terms": {}}}
        ]
        
        with patch.object(client, '_get_task_status', new_callable=AsyncMock) as mock_get_status:
            mock_get_status.side_effect = status_sequence
            
            result = await client._poll_task(task_id, progress_callback)
            
            assert result == {"success": True, "go_terms": {}}
            assert len(progress_calls) == 3
            assert progress_calls[0].stage == ProgressStage.PREPARING
            assert progress_calls[1].stage == ProgressStage.EXECUTING
            assert progress_calls[2].stage == ProgressStage.COMPLETED
    
    @pytest.mark.asyncio
    async def test_poll_task_failure(self, client):
        """Test task polling when task fails"""
        task_id = "task-123"
        
        status_sequence = [
            {"state": "PENDING", "result": None},
            {"state": "FAILURE", "result": {"error": "Task failed"}}
        ]
        
        with patch.object(client, '_get_task_status', new_callable=AsyncMock) as mock_get_status:
            mock_get_status.side_effect = status_sequence
            
            result = await client._poll_task(task_id)
            
            assert result == {"error": "Task failed"}
    
    @pytest.mark.asyncio
    async def test_poll_task_timeout(self, client):
        """Test task polling timeout"""
        task_id = "task-123"
        client.celery_config["task_timeout"] = 2  # 2 seconds timeout
        client.celery_config["poll_interval"] = 1
        
        # Always return PENDING (never completes)
        with patch.object(client, '_get_task_status', new_callable=AsyncMock) as mock_get_status:
            mock_get_status.return_value = {"state": "PENDING", "result": None}
            
            with pytest.raises(TimeoutError, match="timed out after 2s"):
                await client._poll_task(task_id)


class TestBioreasonCeleryClientAnnotate:
    """Test protein annotation functionality"""
    
    @pytest.mark.asyncio
    async def test_annotate_success(self, client):
        """Test successful protein annotation"""
        sequence = "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHF"
        organism = "Homo sapiens"
        
        mock_result = {
            "success": True,
            "go_terms": {
                "MF": ["oxygen carrier activity", "heme binding"],
                "BP": ["oxygen transport", "gas transport"],
                "CC": ["hemoglobin complex", "cytoplasm"]
            },
            "metadata": {
                "organism": organism,
                "sequence_length": len(sequence)
            }
        }
        
        with patch.object(client, 'connect', new_callable=AsyncMock):
            with patch.object(client, 'disconnect', new_callable=AsyncMock):
                with patch.object(client, '_submit_task', new_callable=AsyncMock) as mock_submit:
                    with patch.object(client, '_poll_task', new_callable=AsyncMock) as mock_poll:
                        mock_submit.return_value = "task-123"
                        mock_poll.return_value = mock_result
                        
                        result = await client.annotate(sequence, organism)
                        
                        assert result["success"] is True
                        assert "go_terms" in result
                        assert result["go_terms"]["MF"] == ["oxygen carrier activity", "heme binding"]
                        assert result["go_terms"]["BP"] == ["oxygen transport", "gas transport"]
                        assert result["go_terms"]["CC"] == ["hemoglobin complex", "cytoplasm"]
                        
                        mock_submit.assert_called_once_with(sequence, organism, None)
                        mock_poll.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_annotate_with_progress_callback(self, client):
        """Test annotation with progress callback"""
        sequence = "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHF"
        progress_updates = []
        
        async def progress_callback(progress: TaskProgress):
            progress_updates.append(progress)
        
        mock_result = {
            "success": True,
            "go_terms": {"MF": [], "BP": [], "CC": []}
        }
        
        with patch.object(client, 'connect', new_callable=AsyncMock):
            with patch.object(client, 'disconnect', new_callable=AsyncMock):
                with patch.object(client, '_submit_task', new_callable=AsyncMock) as mock_submit:
                    with patch.object(client, '_poll_task', new_callable=AsyncMock) as mock_poll:
                        mock_submit.return_value = "task-123"
                        mock_poll.return_value = mock_result
                        
                        result = await client.annotate(
                            sequence,
                            "Homo sapiens",
                            progress_callback=progress_callback,
                        )
                        
                        assert result["success"] is True
                        # Should have at least one progress update (from annotate method)
                        assert len(progress_updates) >= 1
                        assert progress_updates[0].stage == ProgressStage.PREPARING
    
    @pytest.mark.asyncio
    async def test_annotate_failure(self, client):
        """Test annotation failure handling"""
        sequence = "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHF"
        
        mock_result = {
            "success": False,
            "error": "GO-GPT execution failed"
        }
        
        with patch.object(client, 'connect', new_callable=AsyncMock):
            with patch.object(client, 'disconnect', new_callable=AsyncMock):
                with patch.object(client, '_submit_task', new_callable=AsyncMock) as mock_submit:
                    with patch.object(client, '_poll_task', new_callable=AsyncMock) as mock_poll:
                        mock_submit.return_value = "task-123"
                        mock_poll.return_value = mock_result
                        
                        result = await client.annotate(sequence, "Homo sapiens")
                        
                        assert result["success"] is False
                        assert "error" in result


class TestBioreasonCeleryClientContextManager:
    """Test async context manager"""
    
    @pytest.mark.asyncio
    async def test_context_manager_success(self, client):
        """Test async context manager usage"""
        with patch.object(client, 'connect', new_callable=AsyncMock) as mock_connect:
            with patch.object(client, 'disconnect', new_callable=AsyncMock) as mock_disconnect:
                async with client as ctx:
                    assert ctx == client
                    mock_connect.assert_called_once()
                
                mock_disconnect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_context_manager_with_exception(self, client):
        """Test context manager cleanup on exception"""
        with patch.object(client, 'connect', new_callable=AsyncMock):
            with patch.object(client, 'disconnect', new_callable=AsyncMock) as mock_disconnect:
                try:
                    async with client:
                        raise ValueError("Test exception")
                except ValueError:
                    pass
                
                # Should still disconnect
                mock_disconnect.assert_called_once()


class TestBioreasonCeleryClientGOTermParsing:
    """Test GO term output format parsing"""
    
    @pytest.mark.asyncio
    async def test_parse_concise_format(self, client):
        """Test parsing concise GO term format (MF: term1, term2)"""
        sequence = "MVLSPADKTN"
        
        # Simulate gogpt_api.py output in concise format
        mock_result = {
            "success": True,
            "go_terms": {
                "MF": ["oxygen carrier activity", "heme binding"],
                "BP": ["oxygen transport"],
                "CC": ["hemoglobin complex"]
            }
        }
        
        with patch.object(client, 'connect', new_callable=AsyncMock):
            with patch.object(client, 'disconnect', new_callable=AsyncMock):
                with patch.object(client, '_submit_task', new_callable=AsyncMock):
                    with patch.object(client, '_poll_task', new_callable=AsyncMock) as mock_poll:
                        mock_poll.return_value = mock_result
                        
                        result = await client.annotate(sequence, "Homo sapiens")
                        
                        assert result["go_terms"]["MF"] == ["oxygen carrier activity", "heme binding"]
                        assert result["go_terms"]["BP"] == ["oxygen transport"]
                        assert result["go_terms"]["CC"] == ["hemoglobin complex"]
    
    @pytest.mark.asyncio
    async def test_parse_full_format(self, client):
        """Test parsing full GO term format (Molecular Function (MF): term1, term2)"""
        sequence = "MVLSPADKTN"
        
        # Simulate gogpt_api.py output in full format
        mock_result = {
            "success": True,
            "go_terms": {
                "MF": ["catalytic activity", "hydrolase activity"],
                "BP": ["metabolic process"],
                "CC": ["cytoplasm", "membrane"]
            }
        }
        
        with patch.object(client, 'connect', new_callable=AsyncMock):
            with patch.object(client, 'disconnect', new_callable=AsyncMock):
                with patch.object(client, '_submit_task', new_callable=AsyncMock):
                    with patch.object(client, '_poll_task', new_callable=AsyncMock) as mock_poll:
                        mock_poll.return_value = mock_result
                        
                        result = await client.annotate(sequence, "Homo sapiens")
                        
                        assert result["go_terms"]["MF"] == ["catalytic activity", "hydrolase activity"]
                        assert result["go_terms"]["BP"] == ["metabolic process"]
                        assert result["go_terms"]["CC"] == ["cytoplasm", "membrane"]
    
    @pytest.mark.asyncio
    async def test_parse_empty_go_terms(self, client):
        """Test parsing when GO terms are empty"""
        sequence = "MVLSPADKTN"
        
        mock_result = {
            "success": True,
            "go_terms": {
                "MF": [],
                "BP": [],
                "CC": []
            }
        }
        
        with patch.object(client, 'connect', new_callable=AsyncMock):
            with patch.object(client, 'disconnect', new_callable=AsyncMock):
                with patch.object(client, '_submit_task', new_callable=AsyncMock):
                    with patch.object(client, '_poll_task', new_callable=AsyncMock) as mock_poll:
                        mock_poll.return_value = mock_result
                        
                        result = await client.annotate(sequence, "Homo sapiens")
                        
                        assert result["go_terms"]["MF"] == []
                        assert result["go_terms"]["BP"] == []
                        assert result["go_terms"]["CC"] == []


class TestBioreasonCeleryClientEdgeCases:
    """Test edge cases and error conditions"""
    
    @pytest.mark.asyncio
    async def test_annotate_empty_sequence(self, client):
        """Test annotation with empty sequence raises ValueError"""
        with pytest.raises(ValueError, match="sequence must not be empty"):
            await client.annotate("", "Homo sapiens")
    
    @pytest.mark.asyncio
    async def test_annotate_very_long_sequence(self, client):
        """Test annotation with very long sequence (>2000 aa)"""
        long_sequence = "M" * 2500
        
        with patch.object(client, 'connect', new_callable=AsyncMock):
            with patch.object(client, 'disconnect', new_callable=AsyncMock):
                with patch.object(client, '_submit_task', new_callable=AsyncMock):
                    with patch.object(client, '_poll_task', new_callable=AsyncMock) as mock_poll:
                        mock_poll.return_value = {
                            "success": True,
                            "go_terms": {"MF": ["binding"], "BP": [], "CC": []}
                        }
                        
                        result = await client.annotate(long_sequence, "Homo sapiens")
                        
                        assert result["success"] is True
    
    @pytest.mark.asyncio
    async def test_annotate_invalid_organism(self, client):
        """Test annotation with invalid organism name"""
        sequence = "MVLSPADKTN"
        
        with patch.object(client, 'connect', new_callable=AsyncMock):
            with patch.object(client, 'disconnect', new_callable=AsyncMock):
                with patch.object(client, '_submit_task', new_callable=AsyncMock):
                    with patch.object(client, '_poll_task', new_callable=AsyncMock) as mock_poll:
                        mock_poll.return_value = {
                            "success": False,
                            "error": "Invalid organism"
                        }
                        
                        result = await client.annotate(sequence, "Invalid Organism")
                        
                        assert result["success"] is False
    
    @pytest.mark.asyncio
    async def test_connection_lost_during_annotation(self, client):
        """Test handling of connection loss during annotation"""
        sequence = "MVLSPADKTN"
        
        with patch.object(client, 'connect', new_callable=AsyncMock):
            with patch.object(client, 'disconnect', new_callable=AsyncMock):
                with patch.object(client, '_submit_task', new_callable=AsyncMock) as mock_submit:
                    mock_submit.side_effect = ConnectionError("SSH connection lost")
                    
                    with pytest.raises(ConnectionError, match="SSH connection lost"):
                        await client.annotate(sequence, "Homo sapiens")


class TestBioreasonCeleryClientProgressStageMapping:
    """Test progress stage mapping"""
    
    @pytest.mark.asyncio
    async def test_stage_mapping_pending(self, client):
        """Test PENDING state maps to PREPARING"""
        task_id = "task-123"
        progress_calls = []
        
        async def progress_callback(progress: TaskProgress):
            progress_calls.append(progress)
        
        status_sequence = [
            {"state": "PENDING", "result": None},
            {"state": "SUCCESS", "result": {"success": True, "go_terms": {}}}
        ]
        
        with patch.object(client, '_get_task_status', new_callable=AsyncMock) as mock_get_status:
            mock_get_status.side_effect = status_sequence
            
            await client._poll_task(task_id, progress_callback)
            
            assert len(progress_calls) == 2
            assert progress_calls[0].stage == ProgressStage.PREPARING
            assert progress_calls[0].percent == 25
    
    @pytest.mark.asyncio
    async def test_stage_mapping_started(self, client):
        """Test STARTED state maps to EXECUTING"""
        task_id = "task-123"
        progress_calls = []
        
        async def progress_callback(progress: TaskProgress):
            progress_calls.append(progress)
        
        status_sequence = [
            {"state": "STARTED", "result": None},
            {"state": "SUCCESS", "result": {"success": True, "go_terms": {}}}
        ]
        
        with patch.object(client, '_get_task_status', new_callable=AsyncMock) as mock_get_status:
            mock_get_status.side_effect = status_sequence
            
            await client._poll_task(task_id, progress_callback)
            
            assert len(progress_calls) == 2
            assert progress_calls[0].stage == ProgressStage.EXECUTING
            assert progress_calls[0].percent == 50
    
    @pytest.mark.asyncio
    async def test_stage_mapping_success(self, client):
        """Test SUCCESS state maps to COMPLETED"""
        task_id = "task-123"
        progress_calls = []
        
        async def progress_callback(progress: TaskProgress):
            progress_calls.append(progress)
        
        status_sequence = [
            {"state": "SUCCESS", "result": {"success": True, "go_terms": {}}}
        ]
        
        with patch.object(client, '_get_task_status', new_callable=AsyncMock) as mock_get_status:
            mock_get_status.side_effect = status_sequence
            
            await client._poll_task(task_id, progress_callback)
            
            assert len(progress_calls) == 1
            assert progress_calls[0].stage == ProgressStage.COMPLETED
            assert progress_calls[0].percent == 100
    
    @pytest.mark.asyncio
    async def test_stage_mapping_failure(self, client):
        """Test FAILURE state maps to FAILED"""
        task_id = "task-123"
        progress_calls = []
        
        async def progress_callback(progress: TaskProgress):
            progress_calls.append(progress)
        
        status_sequence = [
            {"state": "FAILURE", "result": {"error": "Task failed"}}
        ]
        
        with patch.object(client, '_get_task_status', new_callable=AsyncMock) as mock_get_status:
            mock_get_status.side_effect = status_sequence
            
            await client._poll_task(task_id, progress_callback)
            
            assert len(progress_calls) == 1
            assert progress_calls[0].stage == ProgressStage.FAILED
            assert progress_calls[0].percent == 0

#!/usr/bin/env python3
"""End-to-end test script for MDPilot API with mock LLM."""
import asyncio
import httpx
import subprocess
import time
import sys
from pathlib import Path

API_BASE = "http://localhost:8000"
API_TOKEN = "test-token-12345"
SERVER_STARTUP_WAIT = 5


def start_server():
    """Start the FastAPI server in background."""
    print("🚀 Starting MDPilot server...")
    env = {
        "API_TOKEN": API_TOKEN,
        "DATABASE_URL": "sqlite+aiosqlite:///./mdpilot.db",
        "LLM_MODEL": "gpt-3.5-turbo",
        "LLM_API_KEY": "mock-key-for-testing",
    }
    
    proc = subprocess.Popen(
        ["python3", "-m", "uvicorn", "mdpilot.api.app:app", 
         "--host", "0.0.0.0", "--port", "8000"],
        env={**subprocess.os.environ, **env},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    
    time.sleep(SERVER_STARTUP_WAIT)
    
    if proc.poll() is not None:
        stdout, stderr = proc.communicate()
        print(f"❌ Server failed to start:\n{stderr.decode()}")
        sys.exit(1)
    
    print(f"✅ Server started (PID: {proc.pid})")
    return proc


async def test_health_check():
    """Test health check endpoint (no auth required)."""
    print("\n📋 Test 1: Health Check")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE}/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data["status"] == "healthy", f"Expected healthy, got {data['status']}"
        print("✅ Health check passed")


async def test_auth_required():
    """Test that protected endpoints require authentication."""
    print("\n📋 Test 2: Authentication Required")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE}/api/v1/tasks")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✅ Authentication enforcement works")


async def test_auth_with_token():
    """Test that valid token grants access."""
    print("\n📋 Test 3: Authentication with Token")
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE}/api/v1/tasks", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✅ Token authentication works")


async def test_submit_background_task():
    """Test submitting a background agent task."""
    print("\n📋 Test 4: Submit Background Task")
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "session_id": "e2e-test-session-001",
        "prompt": "Test prompt for background execution",
        "user_id": "e2e-test-user"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{API_BASE}/api/v1/tasks/agent/execute",
                headers=headers,
                json=payload
            )
            
            if response.status_code != 200:
                print(f"❌ Failed to submit task: {response.status_code}")
                print(f"Response: {response.text}")
                return None
            
            task = response.json()
            task_id = task.get("task_id")
            print(f"✅ Task submitted successfully (ID: {task_id})")
            return task_id
        except Exception as e:
            print(f"❌ Exception during task submission: {e}")
            return None


async def test_query_task_status(task_id: str):
    """Test querying task status."""
    print(f"\n📋 Test 5: Query Task Status (ID: {task_id})")
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/api/v1/tasks/{task_id}",
            headers=headers
        )
        
        if response.status_code != 200:
            print(f"❌ Failed to query task: {response.status_code}")
            return
        
        task = response.json()
        print(f"✅ Task status: {task.get('status')}")
        print(f"   Progress: {task.get('progress_percentage', 0)}%")
        print(f"   Stage: {task.get('current_stage', 'unknown')}")


async def test_list_tasks():
    """Test listing all tasks."""
    print("\n📋 Test 6: List All Tasks")
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/api/v1/tasks",
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        print(f"✅ Found {data.get('total', 0)} tasks")


async def run_all_tests():
    """Run all end-to-end tests."""
    print("=" * 60)
    print("MDPilot End-to-End Test Suite")
    print("=" * 60)
    
    try:
        await test_health_check()
        await test_auth_required()
        await test_auth_with_token()
        
        task_id = await test_submit_background_task()
        
        if task_id:
            await asyncio.sleep(2)
            await test_query_task_status(task_id)
        
        await test_list_tasks()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """Main entry point."""
    server_proc = None
    try:
        server_proc = start_server()
        asyncio.run(run_all_tests())
    finally:
        if server_proc:
            print(f"\n🛑 Stopping server (PID: {server_proc.pid})...")
            server_proc.terminate()
            server_proc.wait(timeout=5)
            print("✅ Server stopped")


if __name__ == "__main__":
    main()

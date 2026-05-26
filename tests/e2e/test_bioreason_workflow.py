import json

import httpx
import pytest
import websockets

BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_full_api_workflow():
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        response = await client.post(
            "/api/v1/bioreason/annotate",
            params={
                "sequence": "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHF",
                "organism": "Homo sapiens"
            }
        )
        assert response.status_code == 200
        data = response.json()
        task_id = data["task_id"]
        
        print(f"任务已提交: {task_id}")
        
        progress_updates = []
        
        async with websockets.connect(f"{WS_URL}/api/v1/bioreason/ws/progress/{task_id}") as ws:
            while True:
                message = await ws.recv()
                update = json.loads(message)
                progress_updates.append(update)
                
                print(f"进度: {update['percent']}% - {update.get('message', '')}")
                
                if update.get('stage') in ['completed', 'failed']:
                    break
        
        final_update = progress_updates[-1]
        assert final_update['stage'] == 'completed'
        assert 'result' in final_update
        
        result = final_update['result']
        assert result['success'] is True
        assert 'go_terms' in result
        
        assert len(progress_updates) >= 4
        
        stages = [u['stage'] for u in progress_updates]
        assert 'preparing' in stages
        assert 'executing' in stages
        assert 'parsing' in stages
        assert 'completed' in stages


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_multiple_proteins():
    test_proteins = [
        ("MVLSPADKTN", "Homo sapiens"),
        (
            "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQFEVVHSLAKWKRQTLGQHDFSAGEGLYTHMKALRPDEDRLSPLHSVYVDQWDWERVMGDGERQFSTLKSTVEAIWAGIKATEAAVSEEFGLAPFLPDQIHFVHSQELLSRYPDLDAKGRERAIAKDLGAVFLVGIGGKLSDGHRHDVRAPDYDDWSTPSELGHAGLNGDILVWNPVLEDAFELSSMGIRVDADTLKHQLALTGDEDRLELEWHQALLRGEMPQTIGGGIGQSRLTMLLLQLPHIGQVQAGVWPAAVRESVPSLL",
            "Escherichia coli"
        ),
        ("MKTIIALSYIFCLVFA", "Saccharomyces cerevisiae")
    ]
    
    results = []
    
    for sequence, organism in test_proteins:
        async with httpx.AsyncClient(base_url=BASE_URL) as client:
            response = await client.post(
                "/api/v1/bioreason/annotate",
                params={"sequence": sequence, "organism": organism}
            )
            assert response.status_code == 200
            
            task_id = response.json()["task_id"]
            
            async with websockets.connect(f"{WS_URL}/api/v1/bioreason/ws/progress/{task_id}") as ws:
                while True:
                    message = await ws.recv()
                    update = json.loads(message)
                    
                    if update.get('stage') == 'completed':
                        results.append(update['result'])
                        break
                    elif update.get('stage') == 'failed':
                        pytest.fail(f"任务失败: {update.get('error')}")
    
    assert len(results) == len(test_proteins)
    for result in results:
        assert result['success'] is True
        assert 'go_terms' in result


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_error_scenarios():
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        response = await client.post(
            "/api/v1/bioreason/annotate",
            params={"sequence": "", "organism": "Homo sapiens"}
        )
        assert response.status_code in [400, 500]
        
        response = await client.post(
            "/api/v1/bioreason/annotate",
            params={"sequence": "MVLSPADKTN", "organism": "Invalid Species"}
        )
        assert response.status_code == 200

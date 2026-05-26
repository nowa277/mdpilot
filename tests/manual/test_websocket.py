import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:8000/api/v1/bioreason/ws/progress/test-123"
    
    async with websockets.connect(uri) as websocket:
        print("WebSocket 已连接")
        
        while True:
            message = await websocket.recv()
            data = json.loads(message)
            
            print(f"进度: {data['percent']}% - {data['message']}")
            
            if data.get('stage') in ['completed', 'failed']:
                print(f"最终结果: {data}")
                break

if __name__ == "__main__":
    asyncio.run(test_websocket())

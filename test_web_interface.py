#!/usr/bin/env python3
"""
Test script for yxi-chat-cli web interface
"""

import asyncio
import websockets
import json
import requests
import sys

async def test_websocket():
    """Test WebSocket connection and message handling"""
    uri = "ws://localhost:8080/ws/chat"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("WebSocket connected successfully!")
            
            # Listen for initial messages (status and history)
            for i in range(2):
                response = await websocket.recv()
                message = json.loads(response)
                print(f"Received: {message['type']}")
            
            # Send a test message
            test_message = {
                "type": "command",
                "command": "get_status"
            }
            await websocket.send(json.dumps(test_message))
            print("Sent status command")
            
            # Get response
            response = await websocket.recv()
            status = json.loads(response)
            print(f"Status: {status['type']}")
            
            print("WebSocket test passed!")
            return True
    
    except Exception as e:
        print(f"WebSocket test failed: {e}")
        return False

def test_api():
    """Test REST API endpoints"""
    base_url = "http://localhost:8080/api"
    
    try:
        # Test status endpoint
        response = requests.get(f"{base_url}/status")
        if response.status_code == 200:
            status = response.json()
            print(f"API status: {status.get('mode', 'unknown')}")
        else:
            print(f"Status endpoint failed: {response.status_code}")
            return False
        
        # Test MCP nodes endpoint
        response = requests.get(f"{base_url}/mcp/nodes")
        if response.status_code == 200:
            nodes = response.json()
            print(f"MCP nodes: {len(nodes)}")
        else:
            print(f"MCP nodes endpoint failed: {response.status_code}")
        
        print("API test passed!")
        return True
    
    except Exception as e:
        print(f"API test failed: {e}")
        return False

def run_tests():
    """Run all tests"""
    print("Testing yxi-chat-cli Web Interface...")
    print("=" * 50)
    
    websocket_success = asyncio.run(test_websocket())
    api_success = test_api()
    
    print("=" * 50)
    print(f"WebSocket: {'✓' if websocket_success else '✗'}")
    print(f"API: {'✓' if api_success else '✗'}")
    
    if websocket_success and api_success:
        print("\nAll tests passed! The web interface is working correctly.")
        print("You can access it at: http://localhost:8080")
    else:
        print("\nSome tests failed. Please check the server logs.")

if __name__ == "__main__":
    # Suppress warnings
    import warnings
    warnings.filterwarnings("ignore")
    
    # Check if server is running
    try:
        response = requests.get("http://localhost:8080/health", timeout=2)
    except:
        print("Server is not running. Please start it first with:")
        print("uv run python server.py")
        sys.exit(1)
    
    # Run tests
    run_tests()
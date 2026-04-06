#!/usr/bin/env python3
"""
WebSocket handler for yxi-chat-cli web interface
"""

import json
import asyncio
from typing import Dict, Any
from fastapi import WebSocket, WebSocketDisconnect
import logging

from chatbot_adapter import ChatbotAdapter

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.adapter = ChatbotAdapter()
    
    async def connect(self, websocket: WebSocket) -> str:
        """Accept a WebSocket connection and return the session ID"""
        await websocket.accept()
        session_id = self.adapter.create_session()
        self.active_connections[session_id] = websocket
        
        # Send initial status
        status = self.adapter.get_status()
        await self.send_personal_message({
            "type": "status",
            "data": status
        }, session_id)
        
        # Send session history
        history = self.adapter.get_session_history(session_id)
        if history:
            await self.send_personal_message({
                "type": "history",
                "data": {
                    "messages": history
                }
            }, session_id)
        
        logger.info(f"WebSocket connected with session ID: {session_id}")
        return session_id
    
    def disconnect(self, session_id: str):
        """Disconnect a WebSocket session"""
        if session_id in self.active_connections:
            # Save session history
            self.adapter.delete_session(session_id)
            del self.active_connections[session_id]
            logger.info(f"WebSocket disconnected: {session_id}")
    
    async def send_personal_message(self, message: Dict[str, Any], session_id: str):
        """Send a message to a specific WebSocket"""
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending message to {session_id}: {e}")
                # Connection likely broken, remove it
                self.disconnect(session_id)
    
    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast a message to all connected WebSockets"""
        disconnected = []
        for session_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error broadcasting to {session_id}: {e}")
                disconnected.append(session_id)
        
        # Clean up disconnected clients
        for session_id in disconnected:
            self.disconnect(session_id)
    
    async def handle_message(self, session_id: str, message: Dict[str, Any]):
        """Handle a message from a WebSocket client"""
        message_type = message.get("type")
        
        if message_type == "chat":
            content = message.get("content", "")
            mode = message.get("mode", "online")
            
            # Update session mode if different
            session = self.adapter.get_session(session_id)
            if session and session.get("mode") != mode:
                session["mode"] = mode
            
            # Send system notification
            await self.send_personal_message({
                "type": "system",
                "data": {
                    "status": "received",
                    "message": "Message received, processing..."
                }
            }, session_id)
            
            # Process the message and stream responses
            async for response in self.adapter.send_message(session_id, content):
                await self.send_personal_message(response, session_id)
        
        elif message_type == "command":
            # Handle special commands
            command = message.get("command", "")
            params = message.get("params", {})
            
            if command == "get_status":
                status = self.adapter.get_status()
                await self.send_personal_message({
                    "type": "status",
                    "data": status
                }, session_id)
            
            elif command == "clear_history":
                self.adapter.clear_session_history(session_id)
                await self.send_personal_message({
                    "type": "system",
                    "data": {
                        "status": "cleared",
                        "message": "History cleared"
                    }
                }, session_id)
            
            elif command == "get_history":
                history = self.adapter.get_session_history(session_id)
                await self.send_personal_message({
                    "type": "history",
                    "data": {
                        "messages": history
                    }
                }, session_id)
            
            else:
                await self.send_personal_message({
                    "type": "error",
                    "data": {
                        "message": f"Unknown command: {command}"
                    }
                }, session_id)
        
        else:
            await self.send_personal_message({
                "type": "error",
                "data": {
                    "message": f"Unknown message type: {message_type}"
                }
            }, session_id)


# Global WebSocket manager
manager = WebSocketManager()


async def websocket_endpoint(websocket: WebSocket):
    """FastAPI WebSocket endpoint"""
    session_id = None
    try:
        session_id = await manager.connect(websocket)
        
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                await manager.handle_message(session_id, message)
            except json.JSONDecodeError:
                await manager.send_personal_message({
                    "type": "error",
                    "data": {"message": "Invalid JSON format"}
                }, session_id)
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if session_id:
            manager.disconnect(session_id)
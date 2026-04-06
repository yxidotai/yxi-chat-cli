#!/usr/bin/env python3
"""
Chatbot adapter for web interface
Provides functionality to use chatbot.py's core logic in a web environment
"""

import os
import json
import uuid
from typing import Any, Dict, List, Optional, Generator, AsyncGenerator
from dataclasses import dataclass
import requests

from chatbot import (
    chat_state, config_state, 
    load_history, save_history, load_config, save_config,
    stream_completion, 
    mcp_client,
    current_api_key, online_available, current_api_base, current_model,
    _format_json_blob, handle_mcp_command, handle_copy_command,
    MODE_ONLINE, MODE_OFFLINE
)


@dataclass
class ChatMessage:
    id: str
    role: str  # "user" or "assistant"
    content: str
    timestamp: float
    metadata: Optional[Dict[str, Any]] = None


class ChatbotAdapter:
    def __init__(self):
        self.sessions = {}  # session_id -> ChatSession
        self.mcp_client = mcp_client
    
    def create_session(self) -> str:
        """Create a new chat session"""
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "messages": load_history(),  # Start with existing history
            "mode": chat_state.get("mode", MODE_ONLINE),
            "offline_node": chat_state.get("offline_node"),
        }
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get existing session"""
        return self.sessions.get(session_id)
    
    def delete_session(self, session_id: str):
        """Delete a session and save its history"""
        if session_id in self.sessions:
            save_history(self.sessions[session_id]["messages"])
            del self.sessions[session_id]
    
    async def send_message(self, session_id: str, message: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Send a message and yield streaming responses
        Yields dictionaries with keys: type, data
        """
        session = self.get_session(session_id)
        if not session:
            yield {"type": "error", "data": {"message": "Session not found"}}
            return
        
        # Check for special commands
        if message.strip().startswith('/'):
            try:
                # Try to handle the command
                result = await self._handle_command(session_id, message)
                if result:
                    yield result
                return
            except Exception as e:
                yield {"type": "error", "data": {"message": f"Command error: {str(e)}"}}
                return
        
        # Add user message
        user_msg = {
            "role": "user", 
            "content": message
        }
        session["messages"].append(user_msg)
        
        # Send system notification about processing
        yield {
            "type": "system",
            "data": {
                "status": "processing",
                "message": "Processing your message..."
            }
        }
        
        # Handle offline mode
        if session.get("mode") == MODE_OFFLINE:
            # Direct tool invocation in offline mode
            try:
                # This is simplified - full offline mode needs more complex handling
                result = await self._handle_offline_message(session, message)
                yield result
            except Exception as e:
                yield {"type": "error", "data": {"message": f"Offline mode error: {str(e)}"}}
            return
        
        # Online mode - stream AI response
        if not online_available():
            yield {
                "type": "error",
                "data": {"message": "Online mode not available. Please set an API key."}
            }
            return
        
        try:
            # Stream AI response
            full_reply = ""
            
            for chunk in self._stream_ai_response(session["messages"]):
                chunk_type = chunk.get("type", "stream")
                
                if chunk_type == "stream":
                    # Content chunk
                    content = chunk.get("content", "")
                    full_reply += content
                    yield {
                        "type": "stream",
                        "data": {
                            "content": content,
                            "accumulated": full_reply
                        }
                    }
                elif chunk_type == "error":
                    yield chunk
            
            # Add full assistant response to history
            if full_reply:
                session["messages"].append({
                    "role": "assistant",
                    "content": full_reply
                })
                
                # Notify completion
                yield {
                    "type": "system",
                    "data": {
                        "status": "complete",
                        "message": "Response complete"
                    }
                }
        
        except Exception as e:
            yield {"type": "error", "data": {"message": f"AI response error: {str(e)}"}}
    
    async def _handle_command(self, session_id: str, command: str) -> Dict[str, Any]:
        """Handle slash commands"""
        session = self.get_session(session_id)
        if not session:
            return {"type": "error", "data": {"message": "Session not found"}}
            
        cmd_parts = command.strip().split()
        cmd = cmd_parts[0].lower() if cmd_parts else ""
        
        # Handle MCP commands
        if cmd in {'/mcp'}:
            try:
                # Create a dummy messages list for command handling
                messages = session["messages"]
                result = handle_mcp_command(command[4:].strip(), messages)
                if result:
                    return {
                        "type": "command_result",
                        "data": {
                            "command": command,
                            "result": "Command executed successfully"
                        }
                    }
            except Exception as e:
                return {"type": "error", "data": {"message": f"MCP command error: {str(e)}"}}
        
        # Handle mode switching
        elif cmd in {'/mode'}:
            # Simplified mode handling
            if len(cmd_parts) > 1:
                new_mode = cmd_parts[1].lower()
                if new_mode == MODE_ONLINE:
                    session["mode"] = MODE_ONLINE
                    return {
                        "type": "system",
                        "data": {
                            "status": "mode_changed",
                            "message": "Switched to online mode"
                        }
                    }
                elif new_mode == MODE_OFFLINE:
                    if len(cmd_parts) > 2:
                        session["offline_node"] = cmd_parts[2]
                        session["mode"] = MODE_OFFLINE
                        return {
                            "type": "system",
                            "data": {
                                "status": "mode_changed",
                                "message": f"Switched to offline mode with node {cmd_parts[2]}"
                            }
                        }
            
            return {"type": "error", "data": {"message": "Invalid mode command"}}
        
        # Handle other commands
        elif cmd in {'/help'}:
            return {
                "type": "help",
                "data": {
                    "content": self._get_help_content()
                }
            }
        
        # Unknown command
        return {
            "type": "error", 
            "data": {"message": f"Unknown command: {command}"}
        }
    
    async def _handle_offline_message(self, session: Dict[str, Any], message: str) -> Dict[str, Any]:
        """Handle messages in offline mode"""
        # Simplified offline handling - should be expanded
        stripped = message.strip()
        if not stripped:
            return {"type": "error", "data": {"message": "Empty message in offline mode"}}
        
        # Try to parse as tool invocation
        parts = stripped.split(maxsplit=2)
        if len(parts) < 2:
            return {"type": "error", "data": {"message": "Offline mode expects '<tool> <json>'"}}
        
        tool_name, payload_raw = parts[1], parts[2] if len(parts) > 2 else ""
        
        try:
            payload_obj = json.loads(payload_raw)
            # Invoke tool through MCP client
            result = self.mcp_client.invoke_tool(
                tool_name,
                payload_obj,
                node_name=session.get("offline_node"),
                context={"chat_history": session["messages"][-6:]}
            )
            
            formatted = _format_json_blob(result)
            return {
                "type": "mcp_result",
                "data": {
                    "tool": tool_name,
                    "result": formatted
                }
            }
        
        except json.JSONDecodeError as e:
            return {"type": "error", "data": {"message": f"Invalid JSON: {str(e)}"}}
        except Exception as e:
            return {"type": "error", "data": {"message": f"Tool invocation error: {str(e)}"}}
    
    def _stream_ai_response(self, messages: List[Dict[str, Any]]) -> Generator[Dict[str, Any], None, None]:
        """Stream AI response from the API"""
        if not online_available():
            yield {"type": "error", "data": {"message": "API key not configured"}}
            return
        
        headers = {
            "Authorization": f"Bearer {current_api_key()}",
            "Content-Type": "application/json"
        }
        data = {
            "model": current_model(),
            "messages": messages,
            "stream": True,
            "temperature": 0.3
        }
        
        try:
            with requests.post(
                f"{current_api_base()}/chat/completions",
                json=data,
                headers=headers,
                stream=True,
                timeout=30,
            ) as response:
                response.raise_for_status()
                
                for raw_line in response.iter_lines():
                    if not raw_line:
                        continue
                    chunk = raw_line.decode("utf-8").strip()
                    
                    # Parse SSE format
                    if chunk.startswith("data:"):
                        payload_str = chunk[len("data:"):].strip()
                    else:
                        payload_str = chunk
                    
                    if payload_str in {"[DONE]", "data: [DONE]"}:
                        break
                    
                    try:
                        event = json.loads(payload_str)
                    except json.JSONDecodeError:
                        continue
                    
                    choice = (event.get("choices") or [{}])[0]
                    delta = choice.get("delta") or choice.get("message") or {}
                    content = delta.get("content") or ""
                    
                    if content:
                        yield {"type": "stream", "content": content}
        
        except Exception as e:
            yield {"type": "error", "data": {"message": f"API Error: {str(e)}"}}
    
    def _get_help_content(self) -> str:
        """Get help content for the web interface"""
        return """
# Available Commands

- `/help` - Show this help message
- `/mode online` - Switch to online mode
- `/mode offline <node>` - Switch to offline mode
- `/mcp add <name> <url>` - Add MCP node
- `/mcp list` - List MCP nodes
- `/mcp use <name>` - Use MCP node

In offline mode, send messages in format: `<tool> <json>`
        """
    
    def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get chat history for a session"""
        session = self.get_session(session_id)
        return session.get("messages", []) if session else []
    
    def clear_session_history(self, session_id: str):
        """Clear history for a session"""
        session = self.get_session(session_id)
        if session:
            # Keep system prompt if exists
            if session["messages"] and session["messages"][0].get("role") == "system":
                session["messages"] = [session["messages"][0]]
            else:
                session["messages"] = []
    
    def get_status(self) -> Dict[str, Any]:
        """Get current system status"""
        return {
            "mode": chat_state.get("mode", MODE_ONLINE),
            "offline_node": chat_state.get("offline_node"),
            "api_key_configured": bool(current_api_key()),
            "api_base": current_api_base(),
            "model": current_model(),
            "mcp_nodes": [{"name": node.name, "url": node.url} for node in mcp_client.list_nodes()],
            "active_mcp": mcp_client.active_name
        }
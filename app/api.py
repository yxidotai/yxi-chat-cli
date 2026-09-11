#!/usr/bin/env python3
"""
REST API endpoints for yxi-chat-cli web interface
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List, Optional
import logging

from chatbot_adapter import ChatbotAdapter
from app.auth import require_session_token

logger = logging.getLogger(__name__)

# CLI-H4: /api 下所有端点统一要求会话令牌(Authorization / ?token= / cookie)
router = APIRouter(prefix="/api", tags=["api"], dependencies=[Depends(require_session_token)])

# Global adapter instance
adapter = ChatbotAdapter()


@router.get("/status")
async def get_status() -> Dict[str, Any]:
    """Get current system status"""
    try:
        return adapter.get_status()
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config")
async def update_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Update system configuration"""
    try:
        # Update API key if provided
        if "api_key" in config:
            from chatbot import chat_state, config_state, save_config
            chat_state["api_key"] = config["api_key"]
            config_state["api_key"] = config["api_key"]
            save_config(config_state)
        
        # Update API base if provided
        if "api_base" in config:
            from chatbot import chat_state, config_state, save_config
            chat_state["api_base"] = config["api_base"]
            config_state["api_base_url"] = config["api_base"]
            save_config(config_state)
        
        # Update model if provided
        if "model" in config:
            from chatbot import chat_state, config_state, save_config
            chat_state["model"] = config["model"]
            config_state["default_model"] = config["model"]
            save_config(config_state)
        
        return {"status": "success", "message": "Configuration updated"}
    
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
async def get_available_models() -> List[Dict[str, Any]]:
    """Get available models from the API"""
    try:
        from chatbot import fetch_model_list
        return fetch_model_list()
    except Exception as e:
        logger.error(f"Error fetching models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mcp/nodes")
async def get_mcp_nodes() -> List[Dict[str, Any]]:
    """Get list of MCP nodes"""
    try:
        from chatbot import mcp_client
        nodes = mcp_client.list_nodes()
        return [
            {
                "name": node.name,
                "url": node.url,
                "active": node.name == mcp_client.active_name,
                "has_token": bool(node.token)
            }
            for node in nodes
        ]
    except Exception as e:
        logger.error(f"Error getting MCP nodes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mcp/nodes")
async def add_mcp_node(node_info: Dict[str, Any]) -> Dict[str, Any]:
    """Add a new MCP node"""
    try:
        from chatbot import mcp_client
        
        name = node_info.get("name")
        url = node_info.get("url")
        token = node_info.get("token")
        
        if not name or not url:
            raise HTTPException(status_code=400, detail="Name and URL are required")
        
        mcp_client.add_node(name, url, token)
        return {"status": "success", "message": f"MCP node '{name}' added"}
    
    except Exception as e:
        logger.error(f"Error adding MCP node: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/mcp/nodes/{node_name}")
async def remove_mcp_node(node_name: str) -> Dict[str, Any]:
    """Remove an MCP node"""
    try:
        from chatbot import mcp_client
        mcp_client.remove_node(node_name)
        return {"status": "success", "message": f"MCP node '{node_name}' removed"}
    
    except Exception as e:
        logger.error(f"Error removing MCP node: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mcp/nodes/{node_name}/use")
async def use_mcp_node(node_name: str) -> Dict[str, Any]:
    """Set an MCP node as active"""
    try:
        from chatbot import mcp_client
        mcp_client.set_active(node_name)
        return {"status": "success", "message": f"MCP node '{node_name}' set as active"}
    
    except Exception as e:
        logger.error(f"Error setting MCP node: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mcp/nodes/{node_name}/tools")
async def get_mcp_tools(node_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get tools available from an MCP node"""
    try:
        from chatbot import mcp_client
        tools = mcp_client.list_tools(node_name=node_name)
        return [
            {
                "name": tool.get("name"),
                "description": tool.get("description")
            }
            for tool in tools
        ]
    except Exception as e:
        logger.error(f"Error getting MCP tools: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mcp/tools/{tool_name}/invoke")
async def invoke_mcp_tool(tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Invoke an MCP tool"""
    try:
        from chatbot import mcp_client
        result = mcp_client.invoke_tool(tool_name, payload.get("payload", {}))
        return {
            "status": "success",
            "result": result
        }
    except Exception as e:
        logger.error(f"Error invoking MCP tool: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session")
async def create_session() -> Dict[str, str]:
    """Create a new chat session"""
    try:
        session_id = adapter.create_session()
        return {"session_id": session_id}
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}/history")
async def get_session_history(session_id: str) -> Dict[str, Any]:
    """Get chat history for a session"""
    try:
        history = adapter.get_session_history(session_id)
        return {"messages": history}
    except Exception as e:
        logger.error(f"Error getting session history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/session/{session_id}/history")
async def clear_session_history(session_id: str) -> Dict[str, str]:
    """Clear history for a session"""
    try:
        adapter.clear_session_history(session_id)
        return {"message": "History cleared"}
    except Exception as e:
        logger.error(f"Error clearing session history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/session/{session_id}")
async def delete_session(session_id: str) -> Dict[str, str]:
    """Delete a session"""
    try:
        adapter.delete_session(session_id)
        return {"message": "Session deleted"}
    except Exception as e:
        logger.error(f"Error deleting session: {e}")
        raise HTTPException(status_code=500, detail=str(e))
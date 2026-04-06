#!/usr/bin/env python3
"""
FastAPI server for yxi-chat-cli web interface
"""

import argparse
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import uvicorn

from app.api import router as api_router
from app.websocket_handler import websocket_endpoint

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize adapter to ensure everything is loaded
try:
    from chatbot_adapter import ChatbotAdapter
    adapter = ChatbotAdapter()
    logger.info("Chatbot adapter initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize chatbot adapter: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan"""
    # Startup
    logger.info("Starting up yxi-chat-cli web server")
    yield
    # Shutdown
    logger.info("Shutting down yxi-chat-cli web server")


# Create FastAPI app
app = FastAPI(
    title="yxi-chat-cli Web Interface",
    description="Web interface for yxi-chat-cli terminal automation tool",
    version="0.1.0",
    lifespan=lifespan
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Include API router
app.include_router(api_router)

# WebSocket endpoint
app.websocket("/ws/chat")(websocket_endpoint)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main web interface"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


def main():
    """Main entry point for the web server"""
    parser = argparse.ArgumentParser(description="yxi-chat-cli Web Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--web-only", action="store_true", help="Run in web-only mode (no CLI)")
    parser.add_argument("--log-level", default="info", choices=["debug", "info", "warning", "error"], help="Log level")
    
    args = parser.parse_args()
    
    # Set log level
    log_level = getattr(logging, args.log_level.upper())
    logging.getLogger().setLevel(log_level)
    
    # Show configuration
    logger.info(f"Starting yxi-chat-cli web server on {args.host}:{args.port}")
    logger.info(f"Web-only mode: {args.web_only}")
    logger.info(f"Log level: {args.log_level}")
    
    # Check if API key is configured
    from chatbot import online_available, current_api_key
    if not online_available():
        logger.warning("No API key configured. Online mode will not be available.")
        logger.info("Set YXI_API_KEY environment variable or use the web interface to configure.")
    
    # Run the server
    uvicorn.run(
        "server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level
    )


if __name__ == "__main__":
    main()
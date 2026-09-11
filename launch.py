#!/usr/bin/env python3
"""
Launch script for yxi-chat-cli with Web interface
"""

import argparse
import subprocess
import sys
import os
import signal
import time
import atexit

def run_cli_only():
    """Run only the CLI chatbot"""
    print("Starting yxi-chat-cli CLI...")
    subprocess.run([sys.executable, "chatbot.py"])

def run_web_only(args):
    """Run only the web server"""
    cmd = [sys.executable, "server.py"]
    
    if args.host:
        cmd.extend(["--host", args.host])
    if args.port:
        cmd.extend(["--port", str(args.port)])
    if args.reload:
        cmd.append("--reload")
    if args.web_only:
        cmd.append("--web-only")
    
    print("Starting yxi-chat-cli Web Server...")
    subprocess.run(cmd)

def run_both(args):
    """Run both CLI and web server"""
    processes = []
    
    def cleanup():
        """Clean up subprocesses on exit"""
        for p in processes:
            if p.poll() is None:
                p.terminate()
                p.wait()
    
    # Register cleanup function
    atexit.register(cleanup)
    
    try:
        # Start web server
        web_cmd = [sys.executable, "server.py"]
        if args.host:
            web_cmd.extend(["--host", args.host])
        if args.port:
            web_cmd.extend(["--port", str(args.port)])
        if args.reload:
            web_cmd.append("--reload")
        
        print("Starting yxi-chat-cli Web Server...")
        web_process = subprocess.Popen(web_cmd)
        processes.append(web_process)
        
        # Give the web server a moment to start
        time.sleep(2)
        
        # Start CLI
        print("Starting yxi-chat-cli CLI...")
        cli_process = subprocess.Popen([sys.executable, "chatbot.py"])
        processes.append(cli_process)
        
        # Wait for any process to exit
        while True:
            for i, p in enumerate(processes):
                if p.poll() is not None:
                    print(f"Process {i} exited with code {p.returncode}")
                    cleanup()
                    sys.exit(p.returncode)
            
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\nReceived interrupt signal, shutting down...")
        cleanup()

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="yxi-chat-cli Launcher")
    parser.add_argument("--mode", choices=["cli", "web", "both"], default="both",
                       help="Launch mode: cli-only, web-only, or both (default)")
    # 默认仅回环监听;外部暴露需显式指定 --host 并自行承担风险
    parser.add_argument("--host", default="127.0.0.1", help="Web server host")
    parser.add_argument("--port", type=int, default=8080, help="Web server port")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for web server")
    parser.add_argument("--web-only", action="store_true", help="Run web server in web-only mode")
    
    args = parser.parse_args()
    
    print("yxi-chat-cli Launcher")
    print("=" * 30)
    
    if args.mode == "cli":
        run_cli_only()
    elif args.mode == "web":
        run_web_only(args)
    else:  # both
        run_both(args)

if __name__ == "__main__":
    main()
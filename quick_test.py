#!/usr/bin/env python3
"""
Quick test script to start the web interface and verify it's working
"""

import subprocess
import time
import sys
import os

def main():
    print("Starting yxi-chat-cli Web Interface for testing...")
    print("=" * 50)
    
    # Start the web server
    try:
        # 默认仅回环监听;外部暴露需显式指定 --host 并自行承担风险
        process = subprocess.Popen([
            sys.executable, "server.py",
            "--host", "127.0.0.1",
            "--port", "8080"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Give it time to start
        time.sleep(3)
        
        # Check if it started successfully
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            print("Failed to start server:")
            print(stderr.decode() if stderr else stdout.decode())
            return False
        
        # Test with a simple request
        import requests
        try:
            response = requests.get("http://localhost:8080/health", timeout=5)
            if response.status_code == 200:
                print("✓ Server is running successfully!")
                print("✓ Health check passed!")
                print("\nWeb interface is available at:")
                print("  - http://localhost:8080")
                print("  - http://127.0.0.1:8080")
                print("\nPress Ctrl+C to stop the server")
                
                # Wait for user to stop it
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    print("\nStopping server...")
                    process.terminate()
                    process.wait()
                    print("Server stopped.")
                    return True
            else:
                print(f"Health check failed: {response.status_code}")
                process.terminate()
                process.wait()
                return False
                
        except Exception as e:
            print(f"Failed to connect to server: {e}")
            process.terminate()
            process.wait()
            return False
    
    except Exception as e:
        print(f"Error starting server: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
#!/usr/bin/env python3
"""
Standalone Stardog Strands Demo
Runs without Docker using in-memory RDF store
"""

import os
import sys
import threading
import time
import webbrowser
import subprocess
from pathlib import Path

def setup_environment():
    """Setup environment variables"""
    os.environ.setdefault("AWS_REGION", "us-east-1")
    os.environ.setdefault("MCP_SERVER_URL", "http://localhost:8000")
    
    # Check for AWS credentials
    if not os.environ.get("AWS_ACCESS_KEY_ID"):
        print("⚠️  WARNING: AWS credentials not found.")
        print("   Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
        print("   or run 'aws configure' to set up your credentials.")
        print()

def start_mcp_server():
    """Start the MCP HTTP server"""
    print("🚀 Starting MCP HTTP Server...")
    try:
        # Import and start the standalone server (local file)
        import standalone_server
        standalone_server.start_server()
    except Exception as e:
        print(f"❌ Failed to start MCP server: {e}")
        return False
    return True

def start_streamlit_app():
    """Start the Streamlit application"""
    print("🚀 Starting Streamlit App...")
    time.sleep(2)  # Give MCP server time to start
    
    try:
        # Use local app.py file
        app_path = Path(__file__).parent / "app.py"
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            str(app_path), 
            "--server.port", "8501",
            "--server.headless", "true"
        ])
    except Exception as e:
        print(f"❌ Failed to start Streamlit app: {e}")

def main():
    """Main demo runner"""
    print("=" * 60)
    print("🌟 STARDOG STRANDS DEMO - STANDALONE VERSION")
    print("=" * 60)
    print()
    
    setup_environment()
    
    print("📋 Demo Components:")
    print("   • In-memory RDF Knowledge Graph (GEOINT data)")
    print("   • HTTP MCP Server (port 8000)")
    print("   • Streamlit Chatbot with AWS Strands Agents (port 8501)")
    print("   • AWS Bedrock Claude 3.7 Sonnet integration")
    print()
    
    # Start MCP server in background thread
    mcp_thread = threading.Thread(target=start_mcp_server, daemon=True)
    mcp_thread.start()
    
    time.sleep(3)  # Give MCP server time to start
    
    print("🌐 Starting web interface...")
    print()
    print("🔗 Access the demo at: http://localhost:8501")
    print()
    print("💡 Sample queries to try:")
    print("   • 'What facilities are near Washington DC?'")
    print("   • 'Find all military bases in Virginia'")
    print("   • 'Show me airports and their locations'")
    print("   • 'What types of facilities do we have data for?'")
    print()
    print("Press Ctrl+C to stop the demo")
    print("-" * 60)
    
    # Try to open browser
    try:
        time.sleep(2)
        webbrowser.open("http://localhost:8501")
    except:
        pass
    
    # Start Streamlit (this will block)
    start_streamlit_app()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Demo stopped. Thank you!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error running demo: {e}")
        sys.exit(1)

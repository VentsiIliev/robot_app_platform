import time


def init_test_mode(config):
    # Start mock server automatically in test mode
    start_mock_server()
    url = f"{config.server.base_url}{config.endpoints.weights}"
    print(f"[GlueDataFetcher] Switched to TEST mode - using {url}")
    return url

def start_mock_server():
    """Start the mock server in a background thread"""
    import subprocess
    import sys
    from pathlib import Path

    try:
        # Get the path to the mock server script
        project_root = Path(__file__).parent.parent.parent
        mock_server_path = project_root / "mock_glue_server.py"

        if not mock_server_path.exists():
            print(f"[GlueDataFetcher] Warning: Mock server script not found at {mock_server_path}")
            return

        # Check if server is already running
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('localhost', 5000))
            sock.close()
            if result == 0:
                print(f"[GlueDataFetcher] Mock server already running on port 5000")
                return
        except Exception:
            pass

        # Start the mock server in a background process
        print(f"[GlueDataFetcher] Starting mock server from {mock_server_path}")
        subprocess.Popen(
            [sys.executable, str(mock_server_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
        )

        # Wait a bit for the server to start
        time.sleep(2)
        print(f"[GlueDataFetcher] Mock server started successfully")

    except Exception as e:
        print(f"[GlueDataFetcher] Error starting mock server: {e}")
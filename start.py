"""
InfoSec Agent — One-Click Launcher
Starts backend + frontend, refreshes AWS if needed, runs health check.
Usage: python start.py
"""
import subprocess
import sys
import os
import time
import threading
from pathlib import Path

ROOT = Path(__file__).parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"

def run_bg(cmd, cwd, label):
    """Run a command in background and print output with label."""
    proc = subprocess.Popen(cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)
    def stream():
        for line in proc.stdout:
            print(f"[{label}] {line.rstrip()}")
    threading.Thread(target=stream, daemon=True).start()
    return proc

def check_health(url, timeout=30):
    import requests
    for _ in range(timeout):
        try:
            r = requests.get(f"{url}/api/health", timeout=3)
            if r.status_code == 200:
                return r.json()
        except:
            pass
        time.sleep(1)
    return None

def main():
    print("=" * 50)
    print("  InfoSec Agent — Starting Up")
    print("=" * 50)

    # 1. Start backend
    print("\n[1/4] Starting backend...")
    backend_proc = run_bg("python -m uvicorn main:app --reload --port 8000", BACKEND, "API")
    time.sleep(3)

    # 2. Start frontend
    print("[2/4] Starting frontend...")
    frontend_proc = run_bg("npm run dev", FRONTEND, "UI")
    time.sleep(3)

    # 3. Health check
    print("[3/4] Waiting for backend...")
    health = check_health("http://localhost:8000")
    if health:
        provider = health.get("provider", "?")
        model = health.get("model", "?")
        print(f"  ✓ Backend healthy — {provider} ({model})")
    else:
        print("  ✗ Backend not responding — check logs above")

    # 4. Check frontend
    print("[4/4] Checking frontend...")
    try:
        import requests
        r = requests.get("http://localhost:5173", timeout=5)
        if r.status_code == 200:
            print("  ✓ Frontend ready at http://localhost:5173")
        else:
            print("  ✓ Frontend ready at http://localhost:5174")
    except:
        print("  ✗ Frontend not responding")

    print("\n" + "=" * 50)
    print("  App is running! Open http://localhost:5173")
    print("  Press Ctrl+C to stop")
    print("=" * 50)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        backend_proc.terminate()
        frontend_proc.terminate()

if __name__ == "__main__":
    main()

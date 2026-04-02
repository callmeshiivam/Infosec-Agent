"""
InfoSec Agent — Deploy Helper
Pushes code to GitHub, waits for Render deploy, then uploads docs.
Usage: python deploy.py
"""
import subprocess
import sys
import time
import requests

PROD_API = "https://infosec-agent-api.onrender.com/api"
PROD_UI = "https://infosec-agent.onrender.com"

def run(cmd):
    print(f"  $ {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr[:200]}")
    return result.returncode == 0

def wait_for_deploy(timeout=300):
    """Wait for Render backend to be healthy after deploy."""
    print(f"  Waiting for backend to be healthy (up to {timeout}s)...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"{PROD_API.replace('/api','')}/api/health", timeout=10)
            if r.status_code == 200:
                return True
        except:
            pass
        time.sleep(10)
        elapsed = int(time.time() - start)
        print(f"  ... {elapsed}s elapsed")
    return False

def main():
    print("=" * 50)
    print("  InfoSec Agent — Deploy to Production")
    print("=" * 50)

    # 1. Git push
    print("\n[1/4] Pushing to GitHub...")
    run("git add -A")
    run('git commit -m "Deploy update"')
    if not run("git push origin main"):
        print("  Push failed — check git auth")
        return

    # 2. Wait for Render
    print("\n[2/4] Waiting for Render to deploy...")
    print("  (Render auto-deploys on git push)")
    if not wait_for_deploy():
        print("  ✗ Backend didn't come up. Check Render dashboard.")
        return
    print("  ✓ Backend is healthy")

    # 3. Check doc count
    print("\n[3/4] Checking knowledge base...")
    try:
        r = requests.get(f"{PROD_API}/documents/stats", timeout=10)
        stats = r.json()
        docs = stats["total_documents"]
        chunks = stats["total_chunks"]
        print(f"  {docs} documents, {chunks} chunks")
        if docs == 0:
            print("  Knowledge base is empty — running bulk upload...")
            run("python backend/bulk_upload.py")
        else:
            print("  ✓ Knowledge base intact")
    except Exception as e:
        print(f"  Error: {e}")

    # 4. Summary
    print("\n[4/4] Deploy complete!")
    print(f"  Frontend: {PROD_UI}")
    print(f"  Backend:  {PROD_API.replace('/api','')}")
    print("=" * 50)

if __name__ == "__main__":
    main()

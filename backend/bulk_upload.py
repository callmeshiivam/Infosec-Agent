"""
Bulk Upload — Push all local documents to the production Render backend.
Usage: python backend/bulk_upload.py
"""
import os
import sys
import time
import requests
from pathlib import Path

LOCAL_UPLOADS = Path(__file__).parent / "data" / "uploads"
PROD_URL = os.getenv("PROD_API_URL", "https://infosec-agent-api.onrender.com/api")
ALLOWED = {".pdf", ".docx", ".xlsx", ".xls", ".txt", ".md", ".csv", ".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov"}


def upload_file(filepath):
    with open(filepath, "rb") as f:
        resp = requests.post(
            f"{PROD_URL}/documents/upload",
            files={"file": (filepath.name, f)},
            timeout=120,
        )
    return resp


def main():
    if not LOCAL_UPLOADS.exists():
        print("No local uploads directory found.")
        sys.exit(1)

    files = [f for f in sorted(LOCAL_UPLOADS.iterdir()) if f.is_file() and f.suffix.lower() in ALLOWED]
    print(f"Found {len(files)} local files")

    # Wake up the Render service first (free tier sleeps)
    print("Waking up production server...")
    try:
        requests.get(f"{PROD_URL.replace('/api','')}/api/health", timeout=60)
        print("Server is awake.")
    except:
        print("Server may be starting up. Waiting 30s...")
        time.sleep(30)

    # Get existing docs to skip
    existing = set()
    try:
        docs = requests.get(f"{PROD_URL}/documents/list", timeout=30).json()
        existing = {d["filename"] for d in docs}
        print(f"Already uploaded: {len(existing)} files")
    except:
        print("Could not fetch existing docs — uploading all")

    to_upload = [f for f in files if f.name not in existing]
    print(f"Uploading: {len(to_upload)} new files (skipping {len(files) - len(to_upload)})")
    print()

    success, failed = 0, []
    for i, f in enumerate(to_upload):
        print(f"[{i+1}/{len(to_upload)}] Uploading {f.name}...", end=" ", flush=True)
        try:
            resp = upload_file(f)
            if resp.status_code == 200:
                data = resp.json()
                print(f"OK — {data.get('chunks_created', '?')} chunks")
                success += 1
            else:
                err = resp.json().get("detail", resp.text[:100])
                print(f"FAIL — {err}")
                failed.append((f.name, err))
        except Exception as e:
            print(f"ERROR — {str(e)[:80]}")
            failed.append((f.name, str(e)[:80]))
        time.sleep(1)

    print()
    print(f"Done: {success}/{len(files)} uploaded successfully")
    if failed:
        print(f"Failed ({len(failed)}):")
        for name, err in failed:
            print(f"  - {name}: {err}")


if __name__ == "__main__":
    main()

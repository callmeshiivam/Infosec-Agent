"""
Retry Failed Uploads — Only uploads images and scanned PDFs that failed previously.
Usage: python backend/retry_failed.py
"""
import os
import time
import requests
from pathlib import Path

LOCAL_UPLOADS = Path(__file__).parent / "data" / "uploads"
PROD_URL = os.getenv("PROD_API_URL", "https://infosec-agent-api.onrender.com/api")

# Files that failed in the first bulk upload
FAILED_FILES = [
    "Biometric_Access_-_Exit.jpeg",
    "Data-Encryption-at-Transit (1).png",
    "Data-Encryption-at-Transit (3).png",
    "Data-Encryption-at-Transit.png",
    "data-purged.png",
    "database-backup-resource.png",
    "datadog(SIEM).png",
    "DRL-149.pdf",
    "encrypted-database evidence.png",
    "fire-extinguish1.jpeg",
    "fire-extinguish2.jpeg",
    "Fire_Drill_Report.pdf",
    "HR CLearance.pdf",
    "media-bucket-encrypted.png",
    "Network Security - alert-mail-example.png",
    "Network Security alert-setup.png",
    "Network Security anomally detection.png",
    "Network Security CIS becnchmark.png",
    "Network Security NACL- snippet.png",
    "Network Security Network snippet.png",
    "Prod seggragation.png",
    "prod-waf (1).png",
    "purge-data.png",
    "Sample MSA+SLA.pdf",
    "Security Training inset .png",
    "SSL-Certificate.png",
    "Staging seggragation.png",
    "UAT seggragation.png",
    "VPN access aprroval.png",
]

def main():
    files = [LOCAL_UPLOADS / f for f in FAILED_FILES if (LOCAL_UPLOADS / f).exists()]
    print(f"Retrying {len(files)} failed files to {PROD_URL}")

    print("Waking up server...")
    try:
        requests.get(PROD_URL.replace("/api", "") + "/api/health", timeout=60)
    except:
        time.sleep(30)

    success, failed = 0, []
    for i, f in enumerate(files):
        print(f"[{i+1}/{len(files)}] {f.name}...", end=" ", flush=True)
        try:
            with open(f, "rb") as fh:
                resp = requests.post(f"{PROD_URL}/documents/upload", files={"file": (f.name, fh)}, timeout=120)
            if resp.status_code == 200:
                print(f"OK — {resp.json().get('chunks_created', '?')} chunks")
                success += 1
            else:
                err = resp.json().get("detail", "")[:80]
                print(f"FAIL — {err}")
                failed.append(f.name)
        except Exception as e:
            print(f"ERROR — {str(e)[:60]}")
            failed.append(f.name)
        time.sleep(2)

    print(f"\nDone: {success}/{len(files)} uploaded")
    if failed:
        print(f"Still failed: {failed}")

if __name__ == "__main__":
    main()

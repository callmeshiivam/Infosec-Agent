"""
AWS SSO Token Refresher
Run this script to refresh your Bedrock credentials automatically.
Usage: python refresh_aws.py
"""
import subprocess
import sys
import os
import re
from pathlib import Path

ENV_FILE = Path(__file__).parent / ".env"
AWS_CLI = r"C:\Program Files\Amazon\AWSCLIV2\aws.exe"

def find_aws():
    """Find aws CLI executable."""
    candidates = [
        r"C:\Program Files\Amazon\AWSCLIV2\aws.exe",
        r"C:\Program Files (x86)\Amazon\AWSCLIV2\aws.exe",
        "aws",
        "aws.exe",
    ]
    for c in candidates:
        try:
            result = subprocess.run([c, "--version"], capture_output=True, text=True, timeout=10)
            if "aws-cli" in result.stdout or "aws-cli" in result.stderr:
                print(f"Found AWS CLI: {c}")
                return c
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            continue
    return None


def refresh_via_sso(aws_cmd):
    """Use AWS CLI v2 SSO to get fresh credentials."""
    print("Logging in via AWS SSO (browser will open)...")
    subprocess.run([aws_cmd, "sso", "login", "--profile", "locobuzz-bedrock"], check=True)
    
    result = subprocess.run(
        [aws_cmd, "configure", "export-credentials", "--profile", "locobuzz-bedrock", "--format", "env"],
        capture_output=True, text=True, check=True
    )
    
    creds = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            key, _, val = line.partition("=")
            creds[key.replace("export ", "").strip()] = val.strip()
    
    return creds


def update_env(creds):
    """Update .env file with fresh credentials."""
    content = ENV_FILE.read_text()
    
    replacements = {
        "AWS_ACCESS_KEY_ID": creds.get("AWS_ACCESS_KEY_ID", ""),
        "AWS_SECRET_ACCESS_KEY": creds.get("AWS_SECRET_ACCESS_KEY", ""),
        "AWS_SESSION_TOKEN": creds.get("AWS_SESSION_TOKEN", ""),
    }
    
    for key, value in replacements.items():
        if not value:
            continue
        # Replace existing line or add it
        pattern = rf"^{key}=.*$"
        replacement = f"{key}={value}"
        if re.search(pattern, content, re.MULTILINE):
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
        else:
            content += f"\n{key}={value}"
    
    ENV_FILE.write_text(content)
    print(f"✅ Updated .env with fresh credentials (expires in ~12 hours)")


def main():
    aws_cmd = find_aws()
    
    if not aws_cmd:
        print("❌ AWS CLI v2 not found.")
        print("\nManual steps:")
        print("1. Go to https://d-9f677f945a.awsapps.com/start")
        print("2. Click your account → 'Command line or programmatic access'")
        print("3. Copy the 3 export lines and paste into backend/.env")
        sys.exit(1)
    
    try:
        creds = refresh_via_sso(aws_cmd)
        if creds:
            update_env(creds)
        else:
            print("❌ Could not extract credentials from SSO login.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

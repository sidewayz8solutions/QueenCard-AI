#!/usr/bin/env python3
"""Quick test script for RunPod endpoint"""
import requests
import time
import os

# Load from .env
from pathlib import Path
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                key, val = line.strip().split("=", 1)
                os.environ.setdefault(key, val)

API_KEY = os.environ.get("RUNPOD_API_KEY")
ENDPOINT_ID = os.environ.get("RUNPOD_ENDPOINT_ID")

print(f"Testing RunPod endpoint: {ENDPOINT_ID}")
print(f"API Key: {API_KEY[:20]}..." if API_KEY else "NO API KEY")

# Submit async job
url = f"https://api.runpod.ai/v2/{ENDPOINT_ID}/run"
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}
payload = {
    "input": {
        "job_id": "test-123",
        "user_id": "test-user",
        "job_type": "test",
        "input_keys": [],
        "output_prefix": "test/",
        "model_name": "test",
        "params": {}
    }
}

print(f"\nSubmitting test job...")
resp = requests.post(url, headers=headers, json=payload, timeout=30)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text}")

if resp.status_code == 200:
    data = resp.json()
    job_id = data.get("id")
    print(f"\nJob ID: {job_id}")
    
    # Poll for status
    status_url = f"https://api.runpod.ai/v2/{ENDPOINT_ID}/status/{job_id}"
    for i in range(10):
        time.sleep(3)
        status_resp = requests.get(status_url, headers=headers, timeout=30)
        status_data = status_resp.json()
        status = status_data.get("status")
        print(f"  [{i+1}] Status: {status}")
        
        if status in ["COMPLETED", "FAILED"]:
            print(f"\nFinal result: {status_data}")
            break


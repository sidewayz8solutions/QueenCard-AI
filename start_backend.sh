#!/bin/bash
# Start FastAPI backend
cd "$(dirname "$0")/api"
source venv/bin/activate 2>/dev/null || python3 -m venv venv && source venv/bin/activate
pip install -q -r ../requirements.txt
echo "Starting FastAPI backend on http://localhost:8000"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000


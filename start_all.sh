#!/bin/bash
# Start both backend and frontend
DIR="$(dirname "$0")"

echo "=== Starting QueenCard AI ==="
echo ""

# Kill any existing processes
pkill -f "uvicorn app.main:app" 2>/dev/null
pkill -f "next dev" 2>/dev/null
sleep 1

# Start backend in background
echo "Starting backend..."
cd "$DIR/api"
source venv/bin/activate 2>/dev/null || (python3 -m venv venv && source venv/bin/activate)
pip install -q -r ../requirements.txt 2>/dev/null
nohup uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > ../backend.log 2>&1 &
echo $! > ../backend.pid
echo "Backend PID: $(cat ../backend.pid)"

# Start frontend in background
echo "Starting frontend..."
cd "$DIR/frontend"
npm install --silent 2>/dev/null
nohup npm run dev > ../frontend.log 2>&1 &
echo $! > ../frontend.pid
echo "Frontend PID: $(cat ../frontend.pid)"

sleep 3

echo ""
echo "=== Services Started ==="
echo "Backend:  http://localhost:8000 (API docs: http://localhost:8000/docs)"
echo "Frontend: http://localhost:3000"
echo ""
echo "Logs:"
echo "  Backend:  tail -f backend.log"
echo "  Frontend: tail -f frontend.log"
echo ""
echo "To stop: pkill -f 'uvicorn|next dev'"


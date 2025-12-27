#!/bin/bash
# Start Next.js frontend
cd "$(dirname "$0")/frontend"
npm install 2>/dev/null
echo "Starting Next.js frontend on http://localhost:3000"
npm run dev


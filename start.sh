#!/bin/bash

# Install dependencies if missing
if [ ! -d "node_modules" ]; then
  echo "Installing dependencies (first time only)..."
  npm install
fi

# Open browser after 2 seconds
(sleep 2 && xdg-open http://localhost:3000 2>/dev/null || open http://localhost:3000 2>/dev/null) &

echo ""
echo "======================================"
echo "  PhD Scraper is starting..."
echo "  Opening browser automatically..."
echo "  Press Ctrl+C to stop"
echo "======================================"
echo ""

node server.js

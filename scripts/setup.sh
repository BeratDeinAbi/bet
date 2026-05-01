#!/bin/bash
# ============================================================
# Quick Setup Script for Sports Prediction Dashboard
# ============================================================
set -e

echo "=== Sports Prediction Dashboard Setup ==="

# Create .env from example
if [ ! -f .env ]; then
  cp .env.example .env
  echo "✓ Created .env from .env.example"
fi

# Create data directories
mkdir -p data/models data/mock data/seed
echo "✓ Created data directories"

# Backend setup
echo ""
echo "--- Backend Setup ---"
cd backend
python -m venv .venv 2>/dev/null || true
source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate 2>/dev/null || true
pip install -r requirements.txt -q
echo "✓ Backend dependencies installed"
cd ..

# Frontend setup
echo ""
echo "--- Frontend Setup ---"
cd frontend
npm install --silent
echo "✓ Frontend dependencies installed"
cd ..

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Start backend:  cd backend && uvicorn main:app --reload"
echo "  2. Start frontend: cd frontend && npm run dev"
echo "  3. Open browser:   http://localhost:5173"
echo "  4. Load demo data: click 'Demo-Daten laden' or POST /admin/seed"

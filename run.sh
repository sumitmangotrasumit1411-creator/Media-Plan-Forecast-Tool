#!/usr/bin/env bash
# run.sh — Install dependencies and launch the Media Plan Forecast Tool
set -e

echo "📦 Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "🚀 Starting Media Plan Forecast Tool..."
echo "   Open http://localhost:8501 in your browser"
echo ""

streamlit run app.py --server.address 127.0.0.1 --server.port 8501

#!/bin/bash
# Aura CashFlow - Start the web application
echo "Starting Aura CashFlow System..."
echo "Access at: http://localhost:5000"
echo ""
cd "$(dirname "$0")"
python3 app.py

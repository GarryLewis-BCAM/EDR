#!/bin/bash
# BCAM Hybrid EDR - Quick Start Script

set -e

EDR_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$EDR_DIR"

echo "=================================================="
echo "  BCAM Hybrid EDR System"
echo "=================================================="
echo ""

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run install.sh first."
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check Python version
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "✓ Python version: $PYTHON_VERSION"

# Check NAS connectivity
if mount | grep -q "192.168.1.80"; then
    echo "✓ NAS connected (192.168.1.80)"
else
    echo "⚠️  Warning: NAS not detected. Logs will only be stored locally."
fi

echo ""
echo "Starting EDR collector..."
echo "Press Ctrl+C to stop"
echo ""

# Run collector
python3 edr_collector.py

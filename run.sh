#!/bin/bash

# Exit on error
set -e

# Check if python3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed."
    exit 1
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "--- Creating Virtual Environment ---"
    python3 -m venv .venv
    
    echo "--- Activating and Installing Dependencies ---"
    source .venv/bin/activate
    pip install --upgrade pip
    
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
    else
        echo "Error: requirements.txt not found!"
        exit 1
    fi
    echo "--- Environment Setup Complete ---"
else
    # Just activate if it exists
    source .venv/bin/activate
fi

# Run the python script with arguments
python download_test.py "$@"

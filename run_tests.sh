#!/bin/bash
# Run tests for the SlideFinder application

# Exit on error
set -e

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Change to the project root directory
cd "$SCRIPT_DIR"

# Add the project root to PYTHONPATH so tests can find modules
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

# Run pytest with any arguments passed to this script
echo "Running tests from: $SCRIPT_DIR"
echo "PYTHONPATH: $PYTHONPATH"
echo "---"

# Run pytest with verbose output by default
python -m pytest "${@:--v}"

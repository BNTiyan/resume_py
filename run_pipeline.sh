#!/bin/bash

# Job Application Pipeline Runner
# -------------------------------
# This script sets up the environment and runs the autonomous job application agent.

# Get the directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# 1. Load Environment Variables
# -----------------------------
# It is recommended to create a .env file in this directory with your secrets.
if [ -f .env ]; then
    echo "Loading configuration from .env..."
    export $(grep -v '^#' .env | xargs)
fi

# 2. Validation
# -------------
MISSING_VARS=0

if [ -z "$WORKDAY_EMAIL" ]; then
    echo "❌ Error: WORKDAY_EMAIL is not set."
    MISSING_VARS=1
fi

if [ -z "$WORKDAY_PASSWORD" ]; then
    echo "❌ Error: WORKDAY_PASSWORD is not set."
    MISSING_VARS=1
fi

if [ -z "$OPENAI_API_KEY" ] && [ -z "$GEMINI_API_KEY" ]; then
    echo "⚠️  Warning: Neither OPENAI_API_KEY nor GEMINI_API_KEY is set. Resume generation will fail."
fi

if [ $MISSING_VARS -eq 1 ]; then
    echo ""
    echo "Please export these variables or create a .env file based on .env.example"
    echo "Usage: ./run_pipeline.sh"
    exit 1
fi

# 3. Run the Pipeline
# -------------------
echo "🚀 Starting Job Application Agent..."
echo "   Log file: execution.log"
echo "----------------------------------------"

if [ ! -z "$WORKDAY_PASSWORD_SECONDARY" ]; then
    echo "ℹ️  Secondary password configured."
fi

# Install requirements if needed (uncomment if running in fresh env)
# pip install -r requirements.txt

# Run the agent
# --auto-submit: Enables actual submission (remove for dry-run)
# --config config.json: Uses your main configuration with all companies
python3 agent_cli.py --config config.json --auto-submit

EXIT_CODE=$?

echo "----------------------------------------"
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Pipeline completed successfully."
else
    echo "❌ Pipeline failed with exit code $EXIT_CODE. Check execution.log for details."
fi

exit $EXIT_CODE

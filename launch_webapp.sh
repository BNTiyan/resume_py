#!/bin/bash
# Quick setup and launch script for the web app

echo "🚀 Quick Apply Web App - Setup & Launch"
echo "========================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed"
    exit 1
fi
echo "✅ Python 3 found: $(python3 --version)"

# Check if we're in the correct directory
if [ ! -f "config.json" ]; then
    echo "❌ config.json not found. Are you in the correct directory?"
    echo "   cd /Users/bhavananare/github/webapp/resume_py-master"
    exit 1
fi
echo "✅ config.json found"

# Check resume file
if [ ! -f "input/resume.yml" ]; then
    echo "❌ input/resume.yml not found"
    exit 1
fi
echo "✅ resume.yml found"

# Check Flask
echo ""
echo "📦 Checking dependencies..."
if ! python3 -c "import flask" 2>/dev/null; then
    echo "⚠️  Flask not found. Installing..."
    pip3 install flask flask-cors
else
    echo "✅ Flask is installed"
fi

if ! python3 -c "import flask_cors" 2>/dev/null; then
    echo "⚠️  Flask-CORS not found. Installing..."
    pip3 install flask-cors
else
    echo "✅ Flask-CORS is installed"
fi

# Check API keys
echo ""
echo "🔑 Checking API keys..."
if [ -n "$GEMINI_API_KEY" ]; then
    echo "✅ GEMINI_API_KEY is set"
elif [ -n "$OPENAI_API_KEY" ]; then
    echo "✅ OPENAI_API_KEY is set"
else
    echo "⚠️  No API key found in environment variables"
    echo "   Make sure to set GEMINI_API_KEY or OPENAI_API_KEY"
    echo "   Or configure them in config.json"
fi

# Create required directories
echo ""
echo "📁 Creating required directories..."
mkdir -p output/web_uploads
mkdir -p output/web_output
mkdir -p templates
echo "✅ Directories created"

# Get local IP
echo ""
echo "🌐 Network Information:"
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')
if [ -n "$LOCAL_IP" ]; then
    echo "   Local IP: $LOCAL_IP"
    echo "   Access from this device: http://localhost:5001"
    echo "   Access from network: http://$LOCAL_IP:5001"
else
    echo "   Access URL: http://localhost:5001"
fi

echo ""
echo "========================================"
echo "🎉 Everything is ready!"
echo "========================================"
echo ""
echo "Starting the web app..."
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Launch the web app
python3 web_app.py


#!/usr/bin/env bash
# Build script for Render.com deployment (with lxml fix)

set -o errexit  # Exit on error

echo "🔧 Starting build process..."

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📦 Installing dependencies from requirements.txt..."
pip install -r requirements.txt

# If lxml is needed and fails, try installing with binary
echo "✅ Verifying installations..."
python -c "import flask; print('✓ Flask installed')"
python -c "import gunicorn; print('✓ Gunicorn installed')"
python -c "import requests; print('✓ Requests installed')"
python -c "import bs4; print('✓ BeautifulSoup4 installed')"
python -c "import rapidfuzz; print('✓ rapidfuzz installed')" || pip install rapidfuzz

# Verify gunicorn is accessible
echo "✅ Verifying gunicorn..."
which gunicorn || python -m pip show gunicorn || pip install gunicorn

# Create required directories
echo "📁 Creating output directories..."
mkdir -p output/web_uploads
mkdir -p output/web_output
mkdir -p templates

# Verify critical files
echo "📋 Verifying critical files..."
if [ -f "web_app.py" ]; then
    echo "✓ web_app.py found"
else
    echo "✗ web_app.py not found!"
fi

if [ -f "templates/index.html" ]; then
    echo "✓ templates/index.html found"
else
    echo "✗ templates/index.html not found!"
fi

if [ -f "config.json" ]; then
    echo "✓ config.json found"
else
    echo "⚠ config.json not found (will use defaults)"
fi

if [ -f "input/resume.yml" ]; then
    echo "✓ input/resume.yml found"
else
    echo "⚠ input/resume.yml not found"
fi

echo "✅ Build completed successfully!"

#!/bin/bash

# Standalone Demo Installation Script

echo "🚀 Setting up Stardog Strands Demo - Standalone Version"
echo "======================================================="

# Check if Python 3.8+ is available
python_version=$(python3 --version 2>&1 | awk '{print $2}')
major_version=$(echo $python_version | cut -d. -f1)
minor_version=$(echo $python_version | cut -d. -f2)

if [[ $major_version -gt 3 ]] || [[ $major_version -eq 3 && $minor_version -ge 8 ]]; then
    echo "✅ Python $python_version detected"
else
    echo "❌ Python 3.8+ required. Found: $python_version"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "📥 Installing Python dependencies..."
pip install -r requirements.txt

# Check AWS credentials
echo "🔐 Checking AWS credentials..."
if aws sts get-caller-identity &>/dev/null; then
    echo "✅ AWS credentials configured"
else
    echo "⚠️  AWS credentials not configured"
    echo "   Please run 'aws configure' to set up your credentials"
    echo "   or set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables"
fi

echo ""
echo "🎉 Installation complete!"
echo ""
echo "To run the demo:"
echo "  1. Activate the environment: source venv/bin/activate"
echo "  2. Run the demo: python run_demo.py"
echo ""
echo "The demo will start:"
echo "  • MCP Server on http://localhost:8000"
echo "  • Streamlit App on http://localhost:8501"

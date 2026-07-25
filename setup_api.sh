#!/bin/bash
# Quick setup script for MDPilot API configuration

set -e

echo "=========================================="
echo "MDPilot API Configuration Setup"
echo "=========================================="
echo ""

# Check if API key is already set
if [ -n "$MDPILOT_API_KEY" ]; then
    echo "✓ API key is already set in environment"
else
    echo "⚠ API key not found in environment"
    echo ""
    read -p "Enter your API key (or press Enter to skip): " api_key
    if [ -n "$api_key" ]; then
        export MDPILOT_API_KEY="$api_key"
        echo "✓ API key set for this session"
        echo ""
        echo "To make it permanent, add this to your ~/.bashrc or ~/.zshrc:"
        echo "  export MDPILOT_API_KEY=\"$api_key\""
    fi
fi

echo ""
echo "Current configuration:"
echo "----------------------"

# Try to load and display config
python3 << 'PYEOF'
import sys
try:
    from mdpilot.config.loader import load_config
    config = load_config()

    print(f"Model:              {config.provider.model}")
    print(f"Base URL:           {config.provider.base_url or '(default)'}")
    print(f"Custom Provider:    {config.provider.custom_llm_provider or '(none)'}")
    print(f"API Key:            {'✓ Set' if config.provider.api_key else '✗ Not set'}")
    print(f"Max Tokens:         {config.provider.max_tokens}")
    print(f"Temperature:        {config.provider.temperature}")
    print(f"Timeout:            {config.provider.timeout}s")
    print(f"Max Retries:        {config.provider.max_retries}")
    print()
    print(f"AMBER Home:         {config.amber.amber_home or '(auto-detect)'}")
    print(f"Tools Version:      {config.amber.tools_version}")
    print(f"GPU Enabled:        {config.amber.gpu_enabled}")

    sys.exit(0)
except Exception as e:
    print(f"Error loading configuration: {e}")
    sys.exit(1)
PYEOF

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "Configuration loaded successfully!"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo "  1. Test the connection:"
    echo "     amber --chat 'Hello, can you confirm the API is working?'"
    echo ""
    echo "  2. Run the test suite:"
    echo "     amber test"
    echo ""
    echo "  3. Try a workflow:"
    echo "     amber prepare --pdb 1AKI"
    echo ""
    echo "For more information, see:"
    echo "  - docs/API-CONFIGURATION-GUIDE.md"
    echo "  - docs/CLI-USAGE-GUIDE.md"
    echo "  - docs/QUICKSTART.md"
else
    echo ""
    echo "=========================================="
    echo "Configuration check failed"
    echo "=========================================="
    echo ""
    echo "Please check:"
    echo "  1. AMBER Agent is installed: pip install -e ."
    echo "  2. API key is set: export MDPILOT_API_KEY='your-key'"
    echo "  3. Configuration file exists: .amber-agent.yaml"
    echo ""
    echo "See docs/API-CONFIGURATION-GUIDE.md for detailed setup instructions"
fi

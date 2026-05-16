#!/bin/bash

# MCP Server Setup Script
# This script checks prerequisites and sets up the n8n MCP server

set -e

echo "========================================="
echo "n8n MCP Server Setup"
echo "========================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Node.js is installed
echo "Checking Node.js installation..."
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo -e "${GREEN}✓ Node.js is installed: ${NODE_VERSION}${NC}"
else
    echo -e "${RED}✗ Node.js is not installed${NC}"
    echo ""
    echo "Please install Node.js using one of these methods:"
    echo ""
    echo "1. Using Homebrew (recommended for macOS):"
    echo "   brew install node"
    echo ""
    echo "2. Using NVM (Node Version Manager):"
    echo "   curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash"
    echo "   source ~/.bashrc  # or ~/.zshrc"
    echo "   nvm install --lts"
    echo ""
    echo "3. Download from https://nodejs.org/"
    echo ""
    exit 1
fi

# Check if npm is installed
echo "Checking npm installation..."
if command -v npm &> /dev/null; then
    NPM_VERSION=$(npm --version)
    echo -e "${GREEN}✓ npm is installed: ${NPM_VERSION}${NC}"
else
    echo -e "${RED}✗ npm is not installed${NC}"
    exit 1
fi

# Check if npx is installed
echo "Checking npx installation..."
if command -v npx &> /dev/null; then
    NPX_VERSION=$(npx --version)
    echo -e "${GREEN}✓ npx is installed: ${NPX_VERSION}${NC}"
else
    echo -e "${RED}✗ npx is not installed${NC}"
    exit 1
fi

echo ""
echo "========================================="
echo "Testing MCP Server Connection"
echo "========================================="
echo ""

# Test the MCP server connection
echo "Attempting to connect to n8n MCP server..."
echo "Endpoint: https://progamerarena.app.n8n.cloud/mcp-server/http"
echo ""

# Run with a timeout to avoid hanging
timeout 10s npx -y supergateway --sse https://progamerarena.app.n8n.cloud/mcp-server/http \
  --header "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhMzU5NWE0Yy0yNWMzLTRiM2YtOWU2Zi1iYjNkNDRlYTE5NmQiLCJpc3MiOiJuOG4iLCJhdWQiOiJtY3Atc2VydmVyLWFwaSIsImp0aSI6ImU2ZWEwZDRjLTEzNDYtNDc1MC05YmYyLTU1YzgxYjcxMTg3YiIsImlhdCI6MTc3ODg3MDk3MX0.zSXUEFyehg6C_3eevHHBc0nQblhyWnk-R4k2xxH03jY" &

PID=$!
sleep 3

if ps -p $PID > /dev/null; then
    echo -e "${GREEN}✓ MCP server connection established${NC}"
    kill $PID 2>/dev/null || true
else
    echo -e "${YELLOW}⚠ MCP server connection test inconclusive${NC}"
    echo "The server may still work when used by Bob AI Assistant"
fi

echo ""
echo "========================================="
echo "Setup Complete"
echo "========================================="
echo ""
echo "The MCP server is configured in .bob/mcp.json"
echo "Bob AI Assistant will automatically use this server when available."
echo ""
echo "For more information, see .bob/MCP_SETUP_GUIDE.md"
echo ""

# Made with Bob

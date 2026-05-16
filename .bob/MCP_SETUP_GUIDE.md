# MCP Server Setup Guide

## Overview
This project uses an n8n MCP (Model Context Protocol) server to enable AI assistants to interact with n8n workflows and automation capabilities.

## Current Configuration
The MCP server is configured in `.bob/mcp.json` to connect to:
- **Endpoint**: `https://progamerarena.app.n8n.cloud/mcp-server/http`
- **Protocol**: SSE (Server-Sent Events)
- **Gateway**: supergateway (npm package)

## Prerequisites

### 1. Install Node.js
The MCP server requires Node.js and npm to run. Install Node.js using one of these methods:

#### Option A: Using Homebrew (Recommended for macOS)
```bash
brew install node
```

#### Option B: Using NVM (Node Version Manager)
```bash
# Install NVM
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash

# Restart terminal or source profile
source ~/.bashrc  # or ~/.zshrc

# Install Node.js LTS
nvm install --lts
nvm use --lts
```

#### Option C: Download from nodejs.org
Visit https://nodejs.org/ and download the LTS version installer for macOS.

### 2. Verify Installation
After installing Node.js, verify the installation:
```bash
node --version
npm --version
npx --version
```

## Testing the MCP Server

Once Node.js is installed, test the MCP server connection:

```bash
npx -y supergateway --sse https://progamerarena.app.n8n.cloud/mcp-server/http \
  --header "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhMzU5NWE0Yy0yNWMzLTRiM2YtOWU2Zi1iYjNkNDRlYTE5NmQiLCJpc3MiOiJuOG4iLCJhdWQiOiJtY3Atc2VydmVyLWFwaSIsImp0aSI6ImU2ZWEwZDRjLTEzNDYtNDc1MC05YmYyLTU1YzgxYjcxMTg3YiIsImlhdCI6MTc3ODg3MDk3MX0.zSXUEFyehg6C_3eevHHBc0nQblhyWnk-R4k2xxH03jY"
```

## Configuration Details

### MCP Server Configuration (`.bob/mcp.json`)
```json
{
  "mcpServers": {
    "n8n-mcp": {
      "command": "npx",
      "args": [
        "-y",
        "supergateway",
        "--sse",
        "https://progamerarena.app.n8n.cloud/mcp-server/http",
        "--header",
        "Authorization: Bearer <JWT_TOKEN>"
      ]
    }
  }
}
```

### Configuration Parameters
- **command**: `npx` - Node Package Execute, runs npm packages
- **-y**: Auto-confirm package installation
- **supergateway**: npm package that acts as a gateway for MCP servers
- **--sse**: Use Server-Sent Events protocol
- **--header**: Authorization header with JWT bearer token

## Security Notes

⚠️ **Important**: The JWT token in the configuration has an issued-at time (`iat`) of `1778870971` (Unix timestamp). This token may expire and need to be refreshed periodically.

### Token Information
- **Subject (sub)**: `a3595a4c-25c3-4b3f-9e6f-bb3d44ea196d`
- **Issuer (iss)**: `n8n`
- **Audience (aud)**: `mcp-server-api`
- **JWT ID (jti)**: `e6ea0d4c-1346-4750-9bf2-55c81b711887`

### Refreshing the Token
If the MCP server connection fails with authentication errors, you may need to:
1. Log into your n8n cloud instance at `https://progamerarena.app.n8n.cloud`
2. Generate a new MCP server API token
3. Update the token in `.bob/mcp.json`

## Troubleshooting

### Issue: "npx: command not found"
**Solution**: Install Node.js (see Prerequisites section above)

### Issue: Connection timeout or refused
**Possible causes**:
- Network connectivity issues
- n8n cloud instance is down
- JWT token has expired
- Firewall blocking the connection

**Solutions**:
1. Check internet connectivity
2. Verify n8n cloud instance is accessible: `curl -I https://progamerarena.app.n8n.cloud`
3. Refresh the JWT token
4. Check firewall settings

### Issue: Authentication failed
**Solution**: The JWT token may have expired. Generate a new token from your n8n cloud instance.

## Usage with Bob AI Assistant

Once properly configured, Bob can use the n8n MCP server to:
- Query and execute n8n workflows
- Access workflow data and results
- Integrate with n8n automation capabilities
- Interact with connected services through n8n

The MCP server will be automatically loaded when Bob starts, provided Node.js is installed and the configuration is valid.

## Additional Resources

- [n8n Documentation](https://docs.n8n.io/)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- [supergateway npm package](https://www.npmjs.com/package/supergateway)
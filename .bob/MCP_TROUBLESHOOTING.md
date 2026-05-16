# n8n MCP Server Troubleshooting

## Current Status

✅ **MCP Server Connection**: Successfully connected to `https://progamerarena.app.n8n.cloud/mcp-server/http`  
✅ **Authentication**: JWT token accepted  
❌ **Available Tools**: No tools currently exposed  

## Issue Analysis

The MCP server is properly configured and connected, but **no tools are available** because the n8n instance hasn't been configured to expose workflows via the MCP server.

## Root Cause

According to the [n8n MCP documentation](https://docs.n8n.io/advanced-ai/mcp/mcp_tools_reference/), the instance-level MCP server exposes these tools:

1. **search_workflows** - Search for workflows with optional filters
2. **get_workflow_details** - Get detailed information about a specific workflow
3. **execute_workflow** - Execute a workflow by ID with optional inputs

However, these tools are only available when:
- Workflows exist in the n8n instance
- Workflows have the **"Available in MCP"** setting enabled
- The user has proper permissions to access the workflows

## Key Finding from Documentation

From the n8n docs, there's an important note:

> **IMPORTANT**: The `search_workflows` tool is able to list all workflows a user has access to, regardless of their `Available in MCP` setting.

This means:
- If no workflows exist, no tools will be exposed
- If workflows exist but aren't marked as "Available in MCP", they can still be searched but may have limited functionality
- The `availableInMCP` field in the workflow data indicates whether a workflow is visible to MCP tools

## Solution Steps

### 1. Check if Workflows Exist

Log into your n8n cloud instance at `https://progamerarena.app.n8n.cloud` and verify:
- Are there any workflows created?
- Are they active?

### 2. Enable MCP for Workflows

For each workflow you want to expose via MCP:

1. Open the workflow in n8n
2. Go to workflow settings
3. Enable the **"Available in MCP"** option
4. Save the workflow

### 3. Verify Permissions

Ensure the JWT token user has:
- Read access to workflows
- Execute permissions (if you want to run workflows via MCP)
- Proper scopes in the token

### 4. Check Workflow Scopes

The documentation mentions that workflows include a `scopes` field showing user permissions:
- `workflow:read` - Can view workflow details
- `workflow:execute` - Can execute the workflow
- `workflow:update` - Can modify the workflow

## Testing After Configuration

Once workflows are configured, you should be able to use these tools:

### Search for Workflows
```json
{
  "tool": "search_workflows",
  "arguments": {
    "limit": 10,
    "projectId": "optional-project-id"
  }
}
```

### Get Workflow Details
```json
{
  "tool": "get_workflow_details",
  "arguments": {
    "workflowId": "workflow-id-here"
  }
}
```

### Execute Workflow
```json
{
  "tool": "execute_workflow",
  "arguments": {
    "workflowId": "workflow-id-here",
    "executionMode": "production",
    "inputs": {
      "chatInput": "your input here"
    }
  }
}
```

## Expected Workflow Data Structure

When tools are available, workflows will return data including:

- `id` - Workflow unique identifier
- `name` - Workflow name
- `description` - Workflow description
- `active` - Whether the workflow is active
- `availableInMCP` - Whether visible to MCP tools
- `scopes` - User permissions for this workflow
- `canExecute` - Whether user can execute the workflow
- `triggerCount` - Number of triggers
- `triggerInfo` - Human-readable trigger instructions

## Current Configuration

**MCP Server Config** (`.bob/mcp.json`):
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

**Connection Test Results**:
- ✅ Supergateway started successfully
- ✅ Connected to SSE endpoint
- ✅ Authorization accepted
- ✅ Stdio server listening

## Next Steps

1. **Log into n8n**: Access `https://progamerarena.app.n8n.cloud`
2. **Create or configure workflows**: Ensure workflows exist and are marked as "Available in MCP"
3. **Verify token permissions**: Check that the JWT token has appropriate scopes
4. **Test again**: After configuration, the MCP tools should become available

## Additional Resources

- [n8n MCP Tools Reference](https://docs.n8n.io/advanced-ai/mcp/mcp_tools_reference/)
- [n8n MCP Server Documentation](https://docs.n8n.io/advanced-ai/mcp/)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)

## Support

If tools are still not available after following these steps:
1. Check n8n cloud instance logs
2. Verify the JWT token hasn't expired (issued at: Unix timestamp 1778870971)
3. Ensure network connectivity to the n8n cloud instance
4. Contact n8n support if the issue persists
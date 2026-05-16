# n8n API Token Usage Guide

## Your API Token

You have an n8n Public API token that allows programmatic access to your n8n instance.

**Token Type**: Public API (`"aud":"public-api"`)  
**Token**: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI5MjI0ZWEzYi0yMTMxLTQxY2MtYmQ4OC1kOTNjMjU4MzEwYzAiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiMzE1Mjg4ODAtM2YzNi00NGFjLTk2NTYtMDRhZTg5MTgwOTQxIiwiaWF0IjoxNzc4OTA1MTM4fQ.q3qW4veWA1hf7RgJgGBZOSCyDJqF94r_WFT_JAFV9Ko`

## Token Differences

You have TWO different tokens:

### 1. MCP Server Token
- **Audience**: `mcp-server-api`
- **Purpose**: Used by Bob to connect to n8n's MCP server
- **Usage**: Configured in `.bob/mcp.json`
- **Allows**: Bob to list, view, and execute workflows via MCP protocol

### 2. Public API Token (This One)
- **Audience**: `public-api`
- **Purpose**: Direct REST API access to n8n
- **Usage**: HTTP requests with `X-N8N-API-KEY` header
- **Allows**: Full programmatic control of n8n

## What You Can Do With the Public API Token

### 1. Workflow Management
- **List all workflows**
- **Get workflow details**
- **Create new workflows**
- **Update existing workflows**
- **Delete workflows**
- **Activate/Deactivate workflows**
- **Export/Import workflows**

### 2. Workflow Execution
- **Execute workflows manually**
- **Pass input data to workflows**
- **Get execution results**
- **Monitor execution status**
- **View execution history**

### 3. Credentials Management
- **List credentials** (names only, not values)
- **Create credentials**
- **Update credentials**
- **Delete credentials**

### 4. Webhook Testing
- **Test workflow webhooks**
- **Send test data to webhooks**
- **Debug webhook responses**

### 5. Automation & Integration
- **Trigger workflows from external systems**
- **Build custom dashboards**
- **Create workflow orchestration tools**
- **Integrate with CI/CD pipelines**

## Quick Start Examples

### Using curl

#### List All Workflows
```bash
curl -X GET "http://localhost:5678/api/v1/workflows" \
  -H "X-N8N-API-KEY: YOUR_TOKEN" \
  -H "Content-Type: application/json"
```

#### Execute a Workflow
```bash
curl -X POST "http://localhost:5678/api/v1/workflows/WORKFLOW_ID/execute" \
  -H "X-N8N-API-KEY: YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"data": "your input data"}'
```

#### Get Workflow Details
```bash
curl -X GET "http://localhost:5678/api/v1/workflows/WORKFLOW_ID" \
  -H "X-N8N-API-KEY: YOUR_TOKEN" \
  -H "Content-Type: application/json"
```

### Using the Helper Script

We've created a helper script with common operations:

```bash
# Make it executable
chmod +x scripts/n8n-api-examples.sh

# List all workflows
./scripts/n8n-api-examples.sh list_workflows

# Get specific workflow
./scripts/n8n-api-examples.sh get_workflow 1

# Execute a workflow
./scripts/n8n-api-examples.sh execute_workflow 1 '{"name":"test"}'

# Import a workflow
./scripts/n8n-api-examples.sh import_workflow workflows/my-workflow.json

# Get all executions
./scripts/n8n-api-examples.sh get_executions

# Activate a workflow
./scripts/n8n-api-examples.sh toggle_workflow 1 true
```

## Use Cases

### 1. CI/CD Integration
Automatically deploy workflows as part of your deployment pipeline:

```bash
# In your CI/CD script
./scripts/n8n-api-examples.sh import_workflow workflows/production-workflow.json
./scripts/n8n-api-examples.sh toggle_workflow WORKFLOW_ID true
```

### 2. Custom Monitoring Dashboard
Build a dashboard that shows workflow execution status:

```bash
# Get recent executions
curl -X GET "http://localhost:5678/api/v1/executions?limit=10" \
  -H "X-N8N-API-KEY: YOUR_TOKEN"
```

### 3. Workflow Orchestration
Trigger workflows based on external events:

```bash
# Trigger incident response workflow
curl -X POST "http://localhost:5678/api/v1/workflows/INCIDENT_WORKFLOW_ID/execute" \
  -H "X-N8N-API-KEY: YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "incident_id": "INC-12345",
    "severity": "high",
    "description": "Database connection failure"
  }'
```

### 4. Backup & Version Control
Export workflows for version control:

```bash
# Export all workflows
./scripts/n8n-api-examples.sh list_workflows | jq -r '.data[].id' | while read id; do
  ./scripts/n8n-api-examples.sh get_workflow $id > "backups/workflow-$id.json"
done
```

### 5. Testing & Development
Test workflows programmatically:

```bash
# Execute test workflow
./scripts/n8n-api-examples.sh execute_workflow TEST_WORKFLOW_ID '{"test": true}'

# Check execution result
./scripts/n8n-api-examples.sh get_executions TEST_WORKFLOW_ID
```

## API Endpoints Reference

### Workflows
- `GET /api/v1/workflows` - List all workflows
- `GET /api/v1/workflows/:id` - Get workflow by ID
- `POST /api/v1/workflows` - Create workflow
- `PUT /api/v1/workflows/:id` - Update workflow
- `PATCH /api/v1/workflows/:id` - Partially update workflow
- `DELETE /api/v1/workflows/:id` - Delete workflow
- `POST /api/v1/workflows/:id/execute` - Execute workflow

### Executions
- `GET /api/v1/executions` - List executions
- `GET /api/v1/executions/:id` - Get execution by ID
- `DELETE /api/v1/executions/:id` - Delete execution

### Credentials
- `GET /api/v1/credentials` - List credentials
- `GET /api/v1/credentials/:id` - Get credential by ID
- `POST /api/v1/credentials` - Create credential
- `PUT /api/v1/credentials/:id` - Update credential
- `DELETE /api/v1/credentials/:id` - Delete credential

## Python Example

```python
import requests
import json

class N8nAPI:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.headers = {
            'X-N8N-API-KEY': api_key,
            'Content-Type': 'application/json'
        }
    
    def list_workflows(self):
        response = requests.get(
            f'{self.base_url}/api/v1/workflows',
            headers=self.headers
        )
        return response.json()
    
    def execute_workflow(self, workflow_id, data=None):
        response = requests.post(
            f'{self.base_url}/api/v1/workflows/{workflow_id}/execute',
            headers=self.headers,
            json=data or {}
        )
        return response.json()
    
    def get_executions(self, workflow_id=None):
        url = f'{self.base_url}/api/v1/executions'
        if workflow_id:
            url += f'?workflowId={workflow_id}'
        response = requests.get(url, headers=self.headers)
        return response.json()

# Usage
api = N8nAPI(
    'http://localhost:5678',
    'YOUR_API_TOKEN'
)

# List workflows
workflows = api.list_workflows()
print(f"Found {len(workflows['data'])} workflows")

# Execute a workflow
result = api.execute_workflow(1, {'input': 'test'})
print(f"Execution ID: {result['data']['executionId']}")
```

## JavaScript/Node.js Example

```javascript
const axios = require('axios');

class N8nAPI {
    constructor(baseUrl, apiKey) {
        this.client = axios.create({
            baseURL: baseUrl,
            headers: {
                'X-N8N-API-KEY': apiKey,
                'Content-Type': 'application/json'
            }
        });
    }

    async listWorkflows() {
        const response = await this.client.get('/api/v1/workflows');
        return response.data;
    }

    async executeWorkflow(workflowId, data = {}) {
        const response = await this.client.post(
            `/api/v1/workflows/${workflowId}/execute`,
            data
        );
        return response.data;
    }

    async getExecutions(workflowId = null) {
        const url = workflowId 
            ? `/api/v1/executions?workflowId=${workflowId}`
            : '/api/v1/executions';
        const response = await this.client.get(url);
        return response.data;
    }
}

// Usage
const api = new N8nAPI(
    'http://localhost:5678',
    'YOUR_API_TOKEN'
);

(async () => {
    // List workflows
    const workflows = await api.listWorkflows();
    console.log(`Found ${workflows.data.length} workflows`);

    // Execute workflow
    const result = await api.executeWorkflow(1, { input: 'test' });
    console.log(`Execution ID: ${result.data.executionId}`);
})();
```

## Security Best Practices

1. **Never commit tokens to version control**
   - Use environment variables
   - Use secret management tools
   - Add `.env` to `.gitignore`

2. **Rotate tokens regularly**
   - Generate new tokens periodically
   - Revoke old tokens
   - Update all systems using the token

3. **Use HTTPS in production**
   - Never send tokens over HTTP
   - Use TLS/SSL certificates
   - Enable HTTPS in n8n

4. **Limit token scope**
   - Create separate tokens for different purposes
   - Use least privilege principle
   - Monitor token usage

5. **Store tokens securely**
   - Use environment variables
   - Use secret management (Kubernetes Secrets, Vault, etc.)
   - Never log tokens

## Environment Variable Setup

```bash
# Add to ~/.bashrc or ~/.zshrc
export N8N_URL="http://localhost:5678"
export N8N_API_TOKEN="your-token-here"

# Use in scripts
curl -X GET "${N8N_URL}/api/v1/workflows" \
  -H "X-N8N-API-KEY: ${N8N_API_TOKEN}"
```

## Troubleshooting

### 401 Unauthorized
- Check token is correct
- Verify token hasn't expired
- Ensure header name is `X-N8N-API-KEY`

### 404 Not Found
- Verify n8n is running
- Check URL is correct
- Ensure API endpoint exists

### 500 Internal Server Error
- Check n8n logs: `kubectl logs -n n8n deployment/n8n`
- Verify workflow is valid
- Check for missing credentials

## Resources

- [n8n API Documentation](https://docs.n8n.io/api/)
- [n8n Public API Reference](https://docs.n8n.io/api/api-reference/)
- Helper Script: [`scripts/n8n-api-examples.sh`](scripts/n8n-api-examples.sh)

---

**Remember**: Keep your API tokens secure and never share them publicly!
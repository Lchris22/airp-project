# n8n Kubernetes Deployment Guide

## Overview

This guide documents the deployment of n8n workflow automation tool on Kubernetes with MCP (Model Context Protocol) server support.

## Deployment Details

### Cluster Information
- **Cluster**: airp-cluster-dns-a70e7v68.hcp.eastus.azmk8s.io
- **Nodes**: 2 nodes (aks-agentpool)
- **Kubernetes Version**: v1.34.7

### n8n Deployment
- **Namespace**: n8n
- **Helm Chart**: oci://8gears.container-registry.com/library/n8n:2.0.1
- **n8n Version**: 1.122.4
- **Release Name**: n8n

### Access Information
- **Local Access**: http://localhost:5678 (via port-forward)
- **Port Forward Command**: `kubectl port-forward -n n8n svc/n8n 5678:80`
- **Service Type**: ClusterIP
- **Service IP**: 10.0.219.125

## Configuration

### Values File Location
`kubernetes/n8n/values.yaml`

### Key Configuration Settings

#### Database
- **Type**: PostgreSQL
- **Host**: postgres-service.default.svc.cluster.local
- **Port**: 5432
- **Database**: n8n
- **User**: n8n

#### MCP Server
- **Enabled**: Yes (via environment variable)
- **Endpoint**: http://localhost:5678/mcp-server/http
- **Environment Variable**: `N8N_MCP_SERVER_ENABLED=true`

#### Resources
- **Limits**: 1024Mi memory, 1000m CPU
- **Requests**: 512Mi memory, 500m CPU

#### Storage
- **Persistence**: Enabled
- **Storage Class**: default
- **Size**: 10Gi
- **Access Mode**: ReadWriteOnce

## Setup Steps

### 1. Prerequisites
```bash
# Verify kubectl access
kubectl cluster-info

# Verify Helm installation
helm version
```

### 2. Create Namespace
```bash
kubectl create namespace n8n
```

### 3. Deploy n8n
```bash
helm install n8n oci://8gears.container-registry.com/library/n8n \
  --namespace n8n \
  --values kubernetes/n8n/values.yaml
```

### 4. Verify Deployment
```bash
# Check pods
kubectl get pods -n n8n

# Check services
kubectl get svc -n n8n

# Check logs
kubectl logs -n n8n deployment/n8n
```

### 5. Access n8n
```bash
# Set up port forwarding
kubectl port-forward -n n8n svc/n8n 5678:80

# Access in browser
open http://localhost:5678
```

## MCP Server Configuration

### Current Status
The n8n instance is deployed with MCP server support enabled via environment variables. However, the MCP server requires additional configuration:

1. **Initial Setup**: Access n8n at http://localhost:5678 and complete the initial setup
2. **Create API Token**: Generate an API token for MCP server authentication
3. **Enable MCP Features**: Configure workflows to be available via MCP

### MCP Configuration File
Location: `.bob/mcp.json`

```json
{
  "mcpServers": {
    "n8n-local": {
      "command": "npx",
      "args": [
        "-y",
        "supergateway",
        "--sse",
        "http://localhost:5678/mcp-server/http",
        "--header",
        "Authorization: Bearer YOUR_API_TOKEN_HERE"
      ]
    }
  }
}
```

### Steps to Enable MCP Server

1. **Access n8n UI**
   ```bash
   kubectl port-forward -n n8n svc/n8n 5678:80
   ```
   Open http://localhost:5678 in your browser

2. **Complete Initial Setup**
   - Create admin account
   - Set up workspace

3. **Generate API Token**
   - Go to Settings → API
   - Create a new API token
   - Copy the token

4. **Update MCP Configuration**
   - Edit `.bob/mcp.json`
   - Replace `YOUR_API_TOKEN_HERE` with the actual token

5. **Restart Bob**
   - Reload VS Code window to refresh MCP connection
   - Bob will automatically connect to the local n8n MCP server

6. **Create Workflows**
   - Create workflows in n8n
   - Enable "Available in MCP" setting for each workflow
   - Workflows will become available as MCP tools

## Available MCP Tools

Once configured, the following tools will be available:

1. **search_workflows** - Search and list workflows
2. **get_workflow_details** - Get detailed workflow information
3. **execute_workflow** - Execute workflows with inputs

## Maintenance Commands

### View Logs
```bash
kubectl logs -n n8n deployment/n8n -f
```

### Restart Deployment
```bash
kubectl rollout restart deployment/n8n -n n8n
```

### Scale Deployment
```bash
kubectl scale deployment/n8n -n n8n --replicas=2
```

### Update Configuration
```bash
# Edit values
vim kubernetes/n8n/values.yaml

# Upgrade deployment
helm upgrade n8n oci://8gears.container-registry.com/library/n8n \
  --namespace n8n \
  --values kubernetes/n8n/values.yaml
```

### Uninstall
```bash
helm uninstall n8n -n n8n
kubectl delete namespace n8n
```

## Troubleshooting

### Pod Not Starting
```bash
# Check pod status
kubectl describe pod -n n8n <pod-name>

# Check logs
kubectl logs -n n8n <pod-name>
```

### Database Connection Issues
```bash
# Verify PostgreSQL is running
kubectl get pods -n default | grep postgres

# Check database service
kubectl get svc -n default postgres-service
```

### MCP Server Not Available
1. Verify n8n is accessible: `curl http://localhost:5678`
2. Check MCP endpoint: `curl http://localhost:5678/mcp-server/http`
3. Verify API token is valid
4. Check n8n logs for MCP-related errors
5. Ensure workflows are marked as "Available in MCP"

### Port Forward Issues
```bash
# Kill existing port-forward
pkill -f "kubectl port-forward.*n8n"

# Start new port-forward
kubectl port-forward -n n8n svc/n8n 5678:80
```

## Security Considerations

### Production Recommendations

1. **Change Encryption Key**
   - Update `encryption_key` in values.yaml
   - Use a strong, random key

2. **Use Secrets**
   - Store sensitive data in Kubernetes secrets
   - Reference secrets in deployment

3. **Enable TLS**
   - Configure ingress with TLS
   - Use cert-manager for certificate management

4. **Network Policies**
   - Restrict pod-to-pod communication
   - Limit external access

5. **RBAC**
   - Configure proper role-based access control
   - Limit service account permissions

## Next Steps

1. ✅ n8n deployed successfully
2. ⏳ Complete initial n8n setup via UI
3. ⏳ Generate API token for MCP server
4. ⏳ Update MCP configuration with token
5. ⏳ Create and configure workflows
6. ⏳ Test MCP server connection
7. ⏳ Import existing workflows from `workflows/` directory

## Resources

- [n8n Documentation](https://docs.n8n.io/)
- [n8n Helm Chart](https://github.com/8gears/n8n-helm-chart)
- [n8n MCP Documentation](https://docs.n8n.io/advanced-ai/mcp/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
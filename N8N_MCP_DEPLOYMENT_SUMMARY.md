# n8n MCP Server Deployment Summary

## Deployment Status: ✅ COMPLETE

### What Was Accomplished

1. ✅ **Kubernetes Cluster Verified**
   - Cluster: airp-cluster-dns-a70e7v68.hcp.eastus.azmk8s.io
   - 2 nodes running Kubernetes v1.34.7
   - Helm v4.2.0 installed and configured

2. ✅ **n8n Deployed on Kubernetes**
   - Namespace: `n8n`
   - Helm Chart: `oci://8gears.container-registry.com/library/n8n:2.0.1`
   - n8n Version: 1.122.4
   - Status: Running and healthy

3. ✅ **Configuration Files Created**
   - [`kubernetes/n8n/values.yaml`](kubernetes/n8n/values.yaml) - Helm values with MCP support
   - [`.bob/mcp.json`](.bob/mcp.json) - MCP server configuration
   - [`kubernetes/n8n/N8N_DEPLOYMENT_GUIDE.md`](kubernetes/n8n/N8N_DEPLOYMENT_GUIDE.md) - Complete deployment guide
   - [`scripts/n8n-manage.sh`](scripts/n8n-manage.sh) - Management helper script

4. ✅ **Port Forwarding Configured**
   - Local access: http://localhost:5678
   - Command: `kubectl port-forward -n n8n svc/n8n 5678:80`
   - Currently running in background

## Current Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Azure Kubernetes Service                  │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Namespace: n8n                                         │ │
│  │                                                         │ │
│  │  ┌──────────────────────────────────────────────────┐ │ │
│  │  │ n8n Deployment (1 replica)                       │ │ │
│  │  │ - Version: 1.122.4                               │ │ │
│  │  │ - Resources: 512Mi-1Gi RAM, 500m-1000m CPU      │ │ │
│  │  │ - MCP Server: Enabled                            │ │ │
│  │  │ - Storage: 10Gi PVC                              │ │ │
│  │  └──────────────────────────────────────────────────┘ │ │
│  │                          │                             │ │
│  │  ┌──────────────────────▼──────────────────────────┐ │ │
│  │  │ Service: n8n (ClusterIP)                        │ │ │
│  │  │ - Port: 80 → 5678                               │ │ │
│  │  └──────────────────────┬──────────────────────────┘ │ │
│  └─────────────────────────┼─────────────────────────────┘ │
│                             │                               │
└─────────────────────────────┼───────────────────────────────┘
                              │
                    Port Forward (5678:80)
                              │
                              ▼
                    ┌──────────────────┐
                    │  localhost:5678  │
                    │                  │
                    │  Bob MCP Client  │
                    └──────────────────┘
```

## Next Steps Required

### 1. Complete n8n Initial Setup
Access n8n at http://localhost:5678 and:
- Create admin account
- Set up workspace
- Configure basic settings

### 2. Generate MCP API Token
In n8n UI:
1. Go to **Settings** → **API**
2. Click **Create API Token**
3. Name it: "MCP Server Token"
4. Copy the generated token

### 3. Update MCP Configuration
Edit [`.bob/mcp.json`](.bob/mcp.json):
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
        "Authorization: Bearer YOUR_ACTUAL_TOKEN_HERE"
      ]
    }
  }
}
```

### 4. Restart Bob
Reload VS Code window to refresh the MCP connection:
- Command Palette (Cmd/Ctrl+Shift+P)
- Type: "Developer: Reload Window"

### 5. Create Workflows
In n8n:
1. Create workflows for your automation needs
2. For each workflow you want to expose via MCP:
   - Open workflow settings
   - Enable **"Available in MCP"**
   - Save the workflow

### 6. Test MCP Connection
Once configured, Bob will have access to these MCP tools:
- `search_workflows` - Search and list workflows
- `get_workflow_details` - Get detailed workflow information  
- `execute_workflow` - Execute workflows with inputs

## Quick Access Commands

### Access n8n UI
```bash
# Start port-forward (if not already running)
kubectl port-forward -n n8n svc/n8n 5678:80

# Or use the management script
./scripts/n8n-manage.sh port-forward
```

### Check Deployment Status
```bash
./scripts/n8n-manage.sh status
```

### View Logs
```bash
./scripts/n8n-manage.sh logs
```

### Restart n8n
```bash
./scripts/n8n-manage.sh restart
```

## Configuration Details

### Database
- **Type**: PostgreSQL
- **Host**: postgres-service.default.svc.cluster.local
- **Database**: n8n
- **Note**: Using existing PostgreSQL deployment in default namespace

### Resources
- **Memory**: 512Mi (request) / 1Gi (limit)
- **CPU**: 500m (request) / 1000m (limit)
- **Storage**: 10Gi persistent volume

### Environment Variables
Key MCP-related environment variables:
- `N8N_MCP_SERVER_ENABLED=true`
- `N8N_LOG_LEVEL=info`
- `N8N_METRICS=true`
- `N8N_PUBLIC_API_DISABLED=false`

## Troubleshooting

### n8n Not Accessible
```bash
# Check pod status
kubectl get pods -n n8n

# Check logs
kubectl logs -n n8n deployment/n8n

# Restart port-forward
pkill -f "kubectl port-forward.*n8n"
kubectl port-forward -n n8n svc/n8n 5678:80
```

### MCP Server Not Working
1. Verify n8n is accessible: `curl http://localhost:5678`
2. Check API token is valid
3. Ensure workflows are marked "Available in MCP"
4. Restart Bob (reload VS Code window)
5. Check [`.bob/MCP_TROUBLESHOOTING.md`](.bob/MCP_TROUBLESHOOTING.md)

### Database Connection Issues
```bash
# Check PostgreSQL is running
kubectl get pods -n default | grep postgres

# Verify service
kubectl get svc -n default postgres-service
```

## Documentation

- 📖 [Complete Deployment Guide](kubernetes/n8n/N8N_DEPLOYMENT_GUIDE.md)
- 🔧 [MCP Setup Guide](.bob/MCP_SETUP_GUIDE.md)
- 🐛 [MCP Troubleshooting](.bob/MCP_TROUBLESHOOTING.md)
- 📝 [n8n Official Docs](https://docs.n8n.io/)
- 🔌 [n8n MCP Documentation](https://docs.n8n.io/advanced-ai/mcp/)

## Comparison: Cloud vs Self-Hosted

### n8n Cloud (Previous Setup)
- ❌ Limited MCP server functionality
- ❌ No tools exposed
- ❌ Restricted configuration
- ✅ Managed service
- ✅ No infrastructure management

### Self-Hosted on Kubernetes (Current Setup)
- ✅ Full MCP server control
- ✅ Complete configuration access
- ✅ Can expose workflows as tools
- ✅ Integrated with existing infrastructure
- ✅ Cost-effective for high usage
- ⚠️ Requires infrastructure management

## Security Recommendations

For production use:
1. **Change encryption key** in values.yaml
2. **Use Kubernetes secrets** for sensitive data
3. **Enable TLS/HTTPS** via ingress
4. **Configure network policies**
5. **Set up proper RBAC**
6. **Regular backups** of workflows and data
7. **Monitor resource usage**

## Success Metrics

✅ n8n deployed and running  
✅ Accessible via port-forward  
✅ MCP server enabled  
✅ Configuration files created  
✅ Management scripts ready  
⏳ Initial setup pending (user action required)  
⏳ API token generation pending  
⏳ MCP connection test pending  

## Support

For issues or questions:
1. Check the troubleshooting sections in documentation
2. Review n8n logs: `kubectl logs -n n8n deployment/n8n`
3. Consult [n8n community](https://community.n8n.io/)
4. Review [n8n GitHub issues](https://github.com/n8n-io/n8n/issues)

---

**Deployment Date**: 2026-05-16  
**Deployed By**: Bob AI Assistant  
**Status**: ✅ Ready for initial configuration
# AIRP Workflow Setup - Complete ✅

## Summary

The AIRP (Autonomous Incident Resolution Platform) workflow has been successfully imported into your self-hosted n8n instance running on Kubernetes.

## Deployment Status

### ✅ Completed Components

1. **AIRP Agents** - Deployed and running
   - External IP: `20.85.151.165:8080`
   - Namespace: `default`
   - Pods: 2/2 running
   - All 7 agents operational (Monitor, Correlation, RCA, Remediation, Execution, Validation, Documentation)

2. **PostgreSQL Database** - Running
   - Service: `postgres-service.default.svc.cluster.local:5432`
   - Database: `n8n` and `airp`

3. **n8n Workflow Platform** - Deployed
   - Namespace: `n8n`
   - Access: `http://localhost:5678` (via port-forward)
   - Port-forward command: `kubectl port-forward -n n8n svc/n8n 5678:80`

4. **AIRP Workflow** - Imported ✅
   - Workflow ID: `VNdvvpxwqvZCAT74`
   - Name: "AIRP - Incident Resolution Workflow"
   - Status: Imported (needs activation)
   - All AIRP agent IPs configured: `20.85.151.165`

## Next Steps to Complete Setup

### 1. Activate n8n Workflow

Since the API activation failed, activate manually:

```bash
# Ensure port-forward is running
kubectl port-forward -n n8n svc/n8n 5678:80

# Open in browser
open http://localhost:5678
```

In the n8n UI:
1. Navigate to the "AIRP - Incident Resolution Workflow"
2. Click the toggle switch to activate it
3. The workflow will turn green when active

### 2. Configure Slack Credentials

The workflow has 4 Slack nodes that need OAuth2 credentials:

1. Open the workflow in n8n UI
2. Click on any Slack node (e.g., "Send Slack Approval Request")
3. Click "Create New Credential"
4. Select "Slack OAuth2 API"
5. Follow the OAuth2 setup wizard:
   - You'll need to create a Slack App at https://api.slack.com/apps
   - Add OAuth scopes: `chat:write`, `channels:read`
   - Install the app to your workspace
   - Copy the OAuth tokens to n8n

### 3. Set Environment Variables

The workflow references an environment variable that needs to be set:

```bash
# Add to n8n deployment
kubectl set env deployment/n8n -n n8n \
  N8N_APPROVAL_WEBHOOK="http://localhost:5678/webhook/sre-approval"
```

Or update in `kubernetes/n8n/values.yaml`:

```yaml
extraEnv:
  N8N_APPROVAL_WEBHOOK: "http://localhost:5678/webhook/sre-approval"
```

Then upgrade the Helm release:

```bash
helm upgrade n8n oci://8gears.container-registry.com/library/n8n \
  --namespace n8n \
  --values kubernetes/n8n/values.yaml
```

### 4. Configure Alertmanager Webhook

Create Alertmanager configuration to send alerts to n8n:

```yaml
# alertmanager-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: alertmanager-config
  namespace: monitoring
data:
  alertmanager.yml: |
    global:
      resolve_timeout: 5m
    
    route:
      group_by: ['alertname', 'cluster', 'service']
      group_wait: 10s
      group_interval: 10s
      repeat_interval: 12h
      receiver: 'n8n-webhook'
    
    receivers:
    - name: 'n8n-webhook'
      webhook_configs:
      - url: 'http://n8n.n8n.svc.cluster.local/webhook/incident-trigger'
        send_resolved: true
```

Apply the configuration:

```bash
kubectl apply -f alertmanager-config.yaml
kubectl rollout restart statefulset/alertmanager -n monitoring
```

### 5. Create Prometheus Alert Rules

Create alert rules for the AIRP system:

```yaml
# prometheus-airp-rules.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-airp-rules
  namespace: monitoring
data:
  airp-rules.yml: |
    groups:
    - name: airp_incidents
      interval: 30s
      rules:
      - alert: HighCheckoutLatency
        expr: checkout_latency_ms > 500
        for: 1m
        labels:
          severity: critical
          service: s1-checkout
        annotations:
          summary: "High checkout latency detected"
          description: "S1 checkout latency is {{ $value }}ms (threshold: 500ms)"
      
      - alert: HighDatabasePoolUsage
        expr: db_pool_usage_percent > 80
        for: 2m
        labels:
          severity: critical
          service: s2-inventory
        annotations:
          summary: "High database pool usage"
          description: "S2 DB pool usage is {{ $value }}% (threshold: 80%)"
      
      - alert: HighGCPause
        expr: gc_pause_ms > 200
        for: 1m
        labels:
          severity: critical
          service: s3-pricing
        annotations:
          summary: "High GC pause time"
          description: "S3 GC pause is {{ $value }}ms (threshold: 200ms)"
```

Apply the rules:

```bash
kubectl apply -f prometheus-airp-rules.yaml
kubectl rollout restart statefulset/prometheus -n monitoring
```

## Webhook URLs

Once the workflow is activated, these webhook URLs will be available:

### Incident Trigger Webhook
```
http://localhost:5678/webhook/incident-trigger
```

**Test with curl:**
```bash
curl -X POST http://localhost:5678/webhook/incident-trigger \
  -H "Content-Type: application/json" \
  -d '{
    "incident_id": "TEST-001",
    "severity": "critical",
    "metrics": {
      "s1_latency_ms": 750,
      "s2_pool_usage_percent": 85,
      "s3_gc_pause_ms": 250
    },
    "service": "s3-pricing"
  }'
```

### SRE Approval Webhook
```
http://localhost:5678/webhook/sre-approval?action=approve&incident=TEST-001
http://localhost:5678/webhook/sre-approval?action=deny&incident=TEST-001
```

## Workflow Architecture

The imported workflow orchestrates 7 AIRP agents:

```
1. Incident Alert → 2. Monitor Agent → 3. Correlation Agent → 
4. RCA Agent (GPT) → 5. Remediation Agent (GPT) → 
6. Slack Approval → 7. Wait for SRE → 8. Execute (if approved) → 
9. Validation Agent → 10. Documentation Agent → 11. Slack Report
```

### Agent Endpoints (All at 20.85.151.165:8080)

- `/monitor` - Monitor Agent (collects metrics)
- `/correlate` - Correlation Agent (finds patterns)
- `/rca` - RCA Agent (GPT-4o root cause analysis)
- `/remediate` - Remediation Agent (GPT-4o generates fix)
- `/execute` - Execution Agent (applies Kubernetes changes)
- `/validate` - Validation Agent (verifies recovery)
- `/document` - Documentation Agent (creates incident report)

## Testing the Complete System

### 1. Manual Test via n8n Webhook

```bash
# Trigger an incident
curl -X POST http://localhost:5678/webhook/incident-trigger \
  -H "Content-Type: application/json" \
  -d '{
    "incident_id": "MANUAL-TEST-001",
    "severity": "critical",
    "metrics": {
      "s1_latency_ms": 750,
      "s2_pool_usage_percent": 85,
      "s3_gc_pause_ms": 250
    },
    "service": "s3-pricing",
    "description": "Manual test of AIRP workflow"
  }'
```

### 2. Monitor Workflow Execution

In n8n UI:
1. Go to "Executions" tab
2. Watch the workflow progress through each node
3. Check for any errors in Slack nodes (will fail until credentials are configured)

### 3. Check AIRP Agent Logs

```bash
# View agent logs
kubectl logs -n default deployment/airp-agents -f

# Check specific agent responses
kubectl logs -n default deployment/airp-agents | grep -A 10 "POST /monitor"
```

### 4. Verify Database Storage

```bash
# Connect to PostgreSQL
kubectl exec -it -n default deployment/postgres -- psql -U airp -d airp

# Check incident history
SELECT * FROM incidents ORDER BY created_at DESC LIMIT 5;
```

## Troubleshooting

### Workflow Not Triggering

1. **Check workflow is active:**
   ```bash
   curl http://localhost:5678/api/v1/workflows/VNdvvpxwqvZCAT74 \
     -H "X-N8N-API-KEY: YOUR_TOKEN"
   ```

2. **Verify webhook URL:**
   - Webhook path must match exactly: `/webhook/incident-trigger`
   - Check n8n logs: `kubectl logs -n n8n deployment/n8n -f`

3. **Test webhook directly:**
   ```bash
   curl -v http://localhost:5678/webhook/incident-trigger
   ```

### AIRP Agents Not Responding

1. **Check agent pods:**
   ```bash
   kubectl get pods -n default | grep airp
   kubectl describe pod -n default <airp-pod-name>
   ```

2. **Check agent logs:**
   ```bash
   kubectl logs -n default deployment/airp-agents -f
   ```

3. **Verify external IP:**
   ```bash
   kubectl get svc -n default airp-agents-service
   ```

### Slack Nodes Failing

This is expected until OAuth2 credentials are configured:

1. Open n8n UI
2. Go to workflow
3. Click on any Slack node
4. Configure OAuth2 credentials
5. Test the connection

## Files Created/Modified

### Configuration Files
- `kubernetes/n8n/values.yaml` - n8n Helm values
- `kubernetes/n8n/N8N_DEPLOYMENT_GUIDE.md` - n8n deployment guide
- `scripts/n8n-api-examples.sh` - n8n API helper script
- `N8N_API_TOKEN_GUIDE.md` - API token usage guide

### Workflow Files
- `workflows/airp-incident-resolution.json` - Original workflow (with variables)
- `/tmp/airp-workflow-ready.json` - Processed workflow (IPs replaced)

### Documentation
- `DEPLOYMENT_SUMMARY.md` - Complete deployment summary
- `N8N_SETUP_GUIDE.md` - n8n setup instructions
- `AIRP_WORKFLOW_SETUP_COMPLETE.md` - This file

## Quick Reference Commands

```bash
# Access n8n UI
kubectl port-forward -n n8n svc/n8n 5678:80
open http://localhost:5678

# View n8n logs
kubectl logs -n n8n deployment/n8n -f

# View AIRP agent logs
kubectl logs -n default deployment/airp-agents -f

# Test AIRP agents directly
curl http://20.85.151.165:8080/health

# List workflows via API
curl http://localhost:5678/api/v1/workflows \
  -H "X-N8N-API-KEY: YOUR_TOKEN"

# Restart n8n
kubectl rollout restart deployment/n8n -n n8n

# Restart AIRP agents
kubectl rollout restart deployment/airp-agents -n default
```

## Success Criteria

- [x] AIRP agents deployed and accessible at 20.85.151.165:8080
- [x] n8n deployed and accessible at localhost:5678
- [x] Workflow imported with ID VNdvvpxwqvZCAT74
- [ ] Workflow activated in n8n UI
- [ ] Slack OAuth2 credentials configured
- [ ] Alertmanager webhook configured
- [ ] Prometheus alert rules created
- [ ] End-to-end test successful

## Support

For issues or questions:
1. Check logs: `kubectl logs -n n8n deployment/n8n -f`
2. Review n8n documentation: https://docs.n8n.io/
3. Check AIRP agent logs: `kubectl logs -n default deployment/airp-agents -f`
4. Verify Kubernetes resources: `kubectl get all -n n8n`

---

**Status:** Workflow imported successfully ✅  
**Next Action:** Activate workflow and configure Slack credentials in n8n UI  
**Estimated Time to Complete:** 15-20 minutes
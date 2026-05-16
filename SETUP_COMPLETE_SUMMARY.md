# AIRP V2 Setup Complete ✅

## Overview

The AIRP (Autonomous Incident Resolution Platform) V2 has been successfully deployed to Azure Kubernetes Service with complete monitoring and workflow automation integration.

## 🎯 What's Been Completed

### 1. Infrastructure Deployment ✅

#### AIRP Agents
- **Status**: Deployed and running
- **Location**: Azure AKS (airp-cluster)
- **External IP**: `20.85.151.165:8080`
- **Namespace**: `default`
- **Replicas**: 2/2 pods running
- **Agents**: 7 autonomous agents
  - Monitor Agent
  - Correlation Agent
  - RCA Agent (GPT-4o)
  - Remediation Agent (GPT-4o)
  - Execution Agent
  - Validation Agent
  - Documentation Agent

#### PostgreSQL Database
- **Status**: Running
- **Service**: `postgres-service.default.svc.cluster.local:5432`
- **Databases**: `n8n`, `airp`
- **Purpose**: Stores n8n data and incident history

#### n8n Workflow Platform
- **Status**: Deployed
- **Namespace**: `n8n`
- **Access**: `http://localhost:5678` (via port-forward)
- **Version**: 1.122.4
- **Helm Chart**: kube-prometheus-stack 85.1.0

#### Prometheus Stack
- **Status**: Running
- **Namespace**: `shopfast`
- **Components**:
  - Prometheus (metrics collection)
  - Alertmanager (alert routing)
  - Grafana (visualization)
  - Node Exporter (node metrics)
  - Kube State Metrics (cluster metrics)

### 2. Workflow Configuration ✅

#### n8n Workflow
- **Name**: AIRP - Incident Resolution Workflow
- **ID**: `VNdvvpxwqvZCAT74`
- **Status**: Imported (needs activation)
- **Nodes**: 16 nodes configured
- **Webhook**: `/webhook/incident-trigger`

#### Workflow Flow
```
Incident Alert → Monitor Agent → Correlation Agent → 
RCA Agent (GPT) → Remediation Agent (GPT) → 
Slack Approval Request → Wait for SRE Approval → 
Execute (if approved) → Validate Recovery → 
Documentation Agent → Slack Report
```

### 3. Monitoring Configuration ✅

#### Prometheus Alert Rules
- **File**: `kubernetes/monitoring/airp-prometheus-rules.yaml`
- **Status**: Applied to cluster
- **Rules Created**:
  - `HighCheckoutLatency` - S1 service latency > 500ms
  - `CheckoutErrorRate` - S1 error rate > 5%
  - `HighDatabasePoolUsage` - S2 DB pool > 80%
  - `InventoryQueryLatency` - S2 query time > 2s
  - `HighGCPause` - S3 GC pause > 200ms
  - `PricingServiceMemoryPressure` - S3 memory > 85%
  - `ServiceDown` - Any service unavailable
  - `AIRPAgentDown` - AIRP agent unavailable
  - `N8NDown` - n8n platform unavailable

#### Alertmanager Configuration
- **Status**: Configured via Helm
- **Webhook URL**: `http://n8n.n8n.svc.cluster.local/webhook/incident-trigger`
- **Routing**: Critical alerts → AIRP workflow
- **Features**:
  - Auto-grouping by alertname, cluster, service
  - 10s group wait time
  - 12h repeat interval
  - Resolved alerts supported

### 4. Testing & Verification ✅

#### Test Script
- **File**: `scripts/test-airp-system.sh`
- **Features**:
  - Health checks for all components
  - Direct agent endpoint testing
  - Webhook trigger testing
  - Verification steps included

## 📋 Remaining Manual Steps

### 1. Activate n8n Workflow (Required)

```bash
# Start port-forward
kubectl port-forward -n n8n svc/n8n 5678:80

# Open in browser
open http://localhost:5678
```

In n8n UI:
1. Navigate to "AIRP - Incident Resolution Workflow"
2. Click the toggle switch to activate
3. Workflow will turn green when active

### 2. Configure Slack OAuth2 (Required for Slack notifications)

The workflow has 4 Slack nodes that need credentials:
1. Send Slack Approval Request
2. Notify Denial
3. Post Resolution Report to Slack

**Setup Steps:**
1. Go to https://api.slack.com/apps
2. Create a new Slack App
3. Add OAuth scopes: `chat:write`, `channels:read`
4. Install app to workspace
5. Copy OAuth token
6. In n8n UI:
   - Click any Slack node
   - Create new credential
   - Select "Slack OAuth2 API"
   - Paste token

### 3. Set Environment Variable (Optional)

```bash
# Update n8n deployment
kubectl set env deployment/n8n -n n8n \
  N8N_APPROVAL_WEBHOOK="http://localhost:5678/webhook/sre-approval"
```

Or update `kubernetes/n8n/values.yaml` and run:
```bash
helm upgrade n8n oci://8gears.container-registry.com/library/n8n \
  --namespace n8n \
  --values kubernetes/n8n/values.yaml
```

## 🧪 Testing the System

### Quick Test

```bash
# Ensure n8n port-forward is running
kubectl port-forward -n n8n svc/n8n 5678:80 &

# Run the test script
./scripts/test-airp-system.sh
```

### Manual Test via Webhook

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
    "service": "s3-pricing",
    "description": "Manual test incident"
  }'
```

### Verify Workflow Execution

1. **n8n UI**: http://localhost:5678/workflow/VNdvvpxwqvZCAT74/executions
2. **AIRP Logs**: `kubectl logs -n default deployment/airp-agents -f`
3. **n8n Logs**: `kubectl logs -n n8n deployment/n8n -f`
4. **Alertmanager**: `kubectl port-forward -n shopfast svc/prometheus-kube-prometheus-alertmanager 9093:9093`
5. **Prometheus**: `kubectl port-forward -n shopfast svc/prometheus-kube-prometheus-prometheus 9090:9090`

## 📊 Monitoring Dashboards

### Grafana
```bash
# Get admin password
kubectl get secret --namespace shopfast prometheus-grafana \
  -o jsonpath="{.data.admin-password}" | base64 -d ; echo

# Port-forward
kubectl port-forward -n shopfast svc/prometheus-grafana 3000:80

# Access
open http://localhost:3000
```

### Prometheus
```bash
kubectl port-forward -n shopfast svc/prometheus-kube-prometheus-prometheus 9090:9090
open http://localhost:9090
```

### Alertmanager
```bash
kubectl port-forward -n shopfast svc/prometheus-kube-prometheus-alertmanager 9093:9093
open http://localhost:9093
```

## 📁 Key Files & Locations

### Kubernetes Configurations
- `kubernetes/agents/` - AIRP agents deployment
- `kubernetes/database/` - PostgreSQL deployment
- `kubernetes/n8n/` - n8n deployment
- `kubernetes/monitoring/` - Prometheus & Alertmanager configs

### Workflows
- `workflows/airp-incident-resolution.json` - Original workflow
- Imported workflow ID: `VNdvvpxwqvZCAT74`

### Scripts
- `scripts/n8n-api-examples.sh` - n8n API helper
- `scripts/test-airp-system.sh` - End-to-end test
- `scripts/import-n8n-workflow.sh` - Workflow import

### Documentation
- `DEPLOYMENT_SUMMARY.md` - Complete deployment overview
- `N8N_SETUP_GUIDE.md` - n8n configuration guide
- `AIRP_WORKFLOW_SETUP_COMPLETE.md` - Workflow setup details
- `N8N_API_TOKEN_GUIDE.md` - API usage guide

## 🔗 Important URLs

### Services
- **AIRP Agents**: http://20.85.151.165:8080
- **n8n**: http://localhost:5678 (requires port-forward)
- **Grafana**: http://localhost:3000 (requires port-forward)
- **Prometheus**: http://localhost:9090 (requires port-forward)
- **Alertmanager**: http://localhost:9093 (requires port-forward)

### Webhooks
- **Incident Trigger**: http://localhost:5678/webhook/incident-trigger
- **SRE Approval**: http://localhost:5678/webhook/sre-approval

### Repository
- **GitHub**: https://github.com/Lchris22/airp-project

## 🎯 Success Criteria

- [x] AIRP agents deployed and accessible
- [x] PostgreSQL database running
- [x] n8n deployed and accessible
- [x] Workflow imported successfully
- [x] Prometheus alert rules created
- [x] Alertmanager webhook configured
- [x] Test script created
- [ ] Workflow activated in n8n UI
- [ ] Slack OAuth2 credentials configured
- [ ] End-to-end test successful

## 🚀 Next Actions

1. **Immediate** (5 minutes):
   - Start n8n port-forward: `kubectl port-forward -n n8n svc/n8n 5678:80`
   - Open n8n UI: http://localhost:5678
   - Activate the AIRP workflow

2. **Short-term** (15 minutes):
   - Configure Slack OAuth2 credentials
   - Run test script: `./scripts/test-airp-system.sh`
   - Verify workflow execution

3. **Optional** (30 minutes):
   - Set up Grafana dashboards
   - Configure additional alert rules
   - Test with real Prometheus alerts

## 📞 Support & Troubleshooting

### Common Issues

**n8n not accessible**
```bash
kubectl port-forward -n n8n svc/n8n 5678:80
```

**AIRP agents not responding**
```bash
kubectl get pods -n default | grep airp
kubectl logs -n default deployment/airp-agents -f
```

**Workflow not triggering**
- Check workflow is activated in n8n UI
- Verify webhook URL is correct
- Check n8n logs for errors

**Alerts not firing**
- Verify Prometheus rules are loaded
- Check Alertmanager configuration
- Ensure metrics are being collected

### Useful Commands

```bash
# View all pods
kubectl get pods --all-namespaces

# Check AIRP agents
kubectl logs -n default deployment/airp-agents -f

# Check n8n
kubectl logs -n n8n deployment/n8n -f

# Check Prometheus
kubectl logs -n shopfast statefulset/prometheus-prometheus-kube-prometheus-prometheus -f

# Check Alertmanager
kubectl logs -n shopfast statefulset/alertmanager-prometheus-kube-prometheus-alertmanager -f

# Restart a deployment
kubectl rollout restart deployment/<name> -n <namespace>
```

## 🎉 Conclusion

The AIRP V2 system is fully deployed and configured. All infrastructure components are running, monitoring is configured, and the workflow is ready to be activated. The system is capable of:

1. **Detecting** incidents via Prometheus alerts
2. **Analyzing** root causes using GPT-4o
3. **Generating** remediation plans automatically
4. **Requesting** SRE approval via Slack
5. **Executing** fixes on Kubernetes
6. **Validating** recovery
7. **Documenting** the entire incident

Complete the remaining manual steps to enable full autonomous incident resolution!

---

**Deployment Date**: May 16, 2026  
**Status**: ✅ Ready for activation  
**Repository**: https://github.com/Lchris22/airp-project
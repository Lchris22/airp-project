# n8n Workflow Setup Guide

## 📋 Prerequisites
- n8n instance: https://progamerarena.app.n8n.cloud
- AIRP agents running at: http://20.85.151.165:8080
- Slack workspace: https://airp-hq.slack.com

---

## 🔧 Step 1: Import the Workflow

### Option A: Via n8n UI
1. Open n8n: https://progamerarena.app.n8n.cloud
2. Click **"Add workflow"** → **"Import from File"**
3. Select `airpAgent.json` from your workspace
4. Click **"Import"**

### Option B: Via API (if MCP is available)
```bash
curl -X POST https://progamerarena.app.n8n.cloud/api/v1/workflows \
  -H "Content-Type: application/json" \
  -H "X-N8N-API-KEY: your-api-key" \
  -d @airpAgent.json
```

---

## ⚙️ Step 2: Configure Workflow Variables

After importing, update these variables in the workflow:

### Update HTTP Request Nodes
Find and replace `{{ $vars.AIRP_AGENTS_IP }}` with `20.85.151.165` in these nodes:
1. **Monitor Agent** (node-monitor-agent)
2. **Correlation Agent** (node-correlation-agent)
3. **RCA Agent (GPT)** (node-rca-agent)
4. **Remediation Agent (GPT)** (node-remediation-agent)
5. **K8s Operator — Scale S3** (node-k8s-operator)
6. **Validate Recovery** (node-validation)
7. **Documentation Agent** (node-documentation)

### Example Update:
**Before:**
```
url: =http://{{ $vars.AIRP_AGENTS_IP }}:8080/monitor
```

**After:**
```
url: http://20.85.151.165:8080/monitor
```

---

## 🔗 Step 3: Configure Webhooks

### 1. Incident Trigger Webhook
- **Node:** "Incident Alert Received" (node-webhook-trigger)
- **Path:** `incident-trigger`
- **Method:** POST
- **Full URL:** `https://progamerarena.app.n8n.cloud/webhook/incident-trigger`

### 2. SRE Approval Webhook
- **Node:** "Wait for SRE Approval" (node-approval-webhook)
- **Path:** `sre-approval`
- **Method:** GET
- **Full URL:** `https://progamerarena.app.n8n.cloud/webhook/sre-approval`

**Important:** Copy these webhook URLs - you'll need them for Alertmanager configuration.

---

## 💬 Step 4: Configure Slack Integration

### Setup Slack OAuth2
1. In n8n, go to **Credentials** → **Add Credential**
2. Select **Slack OAuth2**
3. Follow the OAuth flow to connect your Slack workspace
4. Grant permissions:
   - `chat:write`
   - `chat:write.public`

### Update Slack Nodes
The workflow has 3 Slack nodes that need credentials:
1. **Send Slack Approval Request** (node-slack-approval)
2. **Notify Denial** (node-denied-slack)
3. **Post Resolution Report to Slack** (node-final-slack)

For each node:
- Set **Authentication:** OAuth2
- Select your Slack credential
- Set **Channel:** `#incidents` (or your preferred channel)

---

## 🧪 Step 5: Test the Workflow

### Test 1: Webhook Trigger
```bash
curl -X POST https://progamerarena.app.n8n.cloud/webhook/incident-trigger \
  -H "Content-Type: application/json" \
  -d '{
    "service": "test-service",
    "metric": "latency_ms",
    "value": 1500,
    "threshold": 500,
    "severity": "critical"
  }'
```

**Expected:** 
- Workflow executes
- AIRP agents process the incident
- Slack message sent to #incidents channel

### Test 2: Manual Execution
1. In n8n, open the workflow
2. Click **"Execute Workflow"** button
3. Provide test data in the webhook node
4. Watch the execution flow

---

## 🚨 Step 6: Configure Alertmanager

Now that n8n is ready, configure Prometheus Alertmanager to send alerts:

### Create Alertmanager Configuration
```yaml
# alertmanager-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: alertmanager-config
  namespace: shopfast
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
      routes:
        - match:
            severity: critical
          receiver: 'n8n-webhook'
    
    receivers:
      - name: 'n8n-webhook'
        webhook_configs:
          - url: 'https://progamerarena.app.n8n.cloud/webhook/incident-trigger'
            send_resolved: true
            http_config:
              follow_redirects: true
```

### Apply Configuration
```bash
kubectl apply -f alertmanager-config.yaml

# Restart Alertmanager to pick up new config
kubectl rollout restart statefulset/alertmanager-prometheus-kube-prometheus-alertmanager -n shopfast
```

---

## 📊 Step 7: Create Prometheus Alert Rules

### Create Alert Rules
```yaml
# prometheus-rules.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-airp-rules
  namespace: shopfast
  labels:
    prometheus: kube-prometheus
data:
  airp-alerts.yaml: |
    groups:
      - name: airp-incident-detection
        interval: 30s
        rules:
          # High Latency Alert
          - alert: HighServiceLatency
            expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 0.5
            for: 2m
            labels:
              severity: critical
              component: latency
            annotations:
              summary: "High latency detected on {{ $labels.service }}"
              description: "95th percentile latency is {{ $value }}s (threshold: 0.5s)"
          
          # High Error Rate Alert
          - alert: HighErrorRate
            expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
            for: 2m
            labels:
              severity: critical
              component: errors
            annotations:
              summary: "High error rate on {{ $labels.service }}"
              description: "Error rate is {{ $value | humanizePercentage }}"
          
          # High CPU Usage
          - alert: HighCPUUsage
            expr: rate(container_cpu_usage_seconds_total[5m]) > 0.8
            for: 5m
            labels:
              severity: warning
              component: resources
            annotations:
              summary: "High CPU usage on {{ $labels.pod }}"
              description: "CPU usage is {{ $value | humanizePercentage }}"
          
          # High Memory Usage
          - alert: HighMemoryUsage
            expr: container_memory_usage_bytes / container_spec_memory_limit_bytes > 0.9
            for: 5m
            labels:
              severity: warning
              component: resources
            annotations:
              summary: "High memory usage on {{ $labels.pod }}"
              description: "Memory usage is {{ $value | humanizePercentage }}"
          
          # Pod Restart Alert
          - alert: PodRestarting
            expr: rate(kube_pod_container_status_restarts_total[15m]) > 0
            for: 5m
            labels:
              severity: critical
              component: stability
            annotations:
              summary: "Pod {{ $labels.pod }} is restarting"
              description: "Pod has restarted {{ $value }} times in the last 15 minutes"
```

### Apply Alert Rules
```bash
kubectl apply -f prometheus-rules.yaml

# Verify rules are loaded
kubectl exec -n shopfast prometheus-prometheus-kube-prometheus-prometheus-0 -- \
  promtool check rules /etc/prometheus/rules/prometheus-airp-rules/airp-alerts.yaml
```

---

## ✅ Step 8: Verify Complete Setup

### 1. Check n8n Workflow
- [ ] Workflow imported successfully
- [ ] All HTTP nodes point to 20.85.151.165:8080
- [ ] Slack credentials configured
- [ ] Webhooks are active

### 2. Check Alertmanager
```bash
# Check Alertmanager config
kubectl exec -n shopfast alertmanager-prometheus-kube-prometheus-alertmanager-0 -- \
  cat /etc/alertmanager/config/alertmanager.yml

# Check Alertmanager status
kubectl port-forward -n shopfast svc/prometheus-kube-prometheus-alertmanager 9093:9093
# Open http://localhost:9093
```

### 3. Check Prometheus Rules
```bash
# Port-forward Prometheus
kubectl port-forward -n shopfast svc/prometheus-kube-prometheus-prometheus 9090:9090
# Open http://localhost:9090/rules
```

### 4. Test End-to-End
```bash
# Trigger a test alert
curl -X POST https://progamerarena.app.n8n.cloud/webhook/incident-trigger \
  -H "Content-Type: application/json" \
  -d '{
    "service": "checkout-service",
    "metric": "latency_ms",
    "value": 1500,
    "threshold": 500,
    "severity": "critical",
    "labels": {
      "namespace": "shopfast",
      "pod": "checkout-service-abc123"
    }
  }'
```

**Expected Flow:**
1. ✅ n8n receives webhook
2. ✅ AIRP Monitor Agent analyzes metrics
3. ✅ Correlation Agent checks related services
4. ✅ RCA Agent (GPT) determines root cause
5. ✅ Remediation Agent (GPT) suggests fix
6. ✅ Slack message sent with approval buttons
7. ⏸️ Wait for SRE approval
8. ✅ Execute remediation (if approved)
9. ✅ Validate recovery
10. ✅ Generate documentation
11. ✅ Post resolution report to Slack

---

## 🐛 Troubleshooting

### n8n Workflow Not Triggering
```bash
# Check webhook is accessible
curl -v https://progamerarena.app.n8n.cloud/webhook/incident-trigger

# Check n8n logs
# (Access via n8n UI → Executions)
```

### Alertmanager Not Sending Alerts
```bash
# Check Alertmanager logs
kubectl logs -n shopfast alertmanager-prometheus-kube-prometheus-alertmanager-0

# Check if alerts are firing in Prometheus
# http://localhost:9090/alerts
```

### AIRP Agents Not Responding
```bash
# Check agent health
curl http://20.85.151.165:8080/health

# Check agent logs
kubectl logs -n shopfast -l app=airp-agents --tail=100

# Check if agents can reach Prometheus
kubectl exec -n shopfast -it $(kubectl get pod -n shopfast -l app=airp-agents -o jsonpath='{.items[0].metadata.name}') -- \
  curl http://prometheus-kube-prometheus-prometheus:9090/api/v1/query?query=up
```

---

## 📚 Additional Resources

- **AIRP API Documentation:** See `docs/API.md`
- **Architecture Overview:** See `docs/ARCHITECTURE.md`
- **Configuration Guide:** See `docs/CONFIGURATION.md`
- **Deployment Summary:** See `DEPLOYMENT_SUMMARY.md`

---

## 🎯 Quick Reference

| Component | URL/Command |
|-----------|-------------|
| n8n | https://progamerarena.app.n8n.cloud |
| AIRP Agents | http://20.85.151.165:8080 |
| Incident Webhook | https://progamerarena.app.n8n.cloud/webhook/incident-trigger |
| Approval Webhook | https://progamerarena.app.n8n.cloud/webhook/sre-approval |
| Slack Channel | #incidents |
| Health Check | `curl http://20.85.151.165:8080/health` |
| View Logs | `kubectl logs -n shopfast -l app=airp-agents` |
| Prometheus | `kubectl port-forward -n shopfast svc/prometheus-kube-prometheus-prometheus 9090:9090` |

---

**Setup complete! Your AIRP system is ready for autonomous incident resolution.** 🚀
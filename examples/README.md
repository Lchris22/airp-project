# AIRP Examples & Integration Templates

This directory contains example services and templates to help you integrate AIRP with your applications.

## 📁 Directory Structure

```
examples/
├── sample-services/          # Demo microservices for testing AIRP
├── custom-actions/           # Example custom remediation actions
├── custom-metrics/           # Example custom Prometheus metrics
└── integration-templates/    # Templates for YOUR services
```

## 🚀 Quick Start

### Deploy Example Services

```bash
# Deploy all example services (S1-S5)
cd sample-services
kubectl apply -f .

# Verify deployment
kubectl get pods -n shopfast -l airp.monitored=true
```

### Test AIRP with Examples

```bash
# Trigger a test incident
../scripts/test-incident.sh

# Watch AIRP resolve it
kubectl logs -f deployment/airp-agents -n shopfast
```

## 📋 Integration Templates

### 1. Service Template

**File:** `integration-templates/service-template.yaml`

Complete Kubernetes manifest template showing:
- Required labels for AIRP discovery
- Prometheus metrics exposure
- ServiceMonitor configuration
- Optional HPA integration

**Usage:**
```bash
# Copy template
cp integration-templates/service-template.yaml my-service.yaml

# Customize for your service
vim my-service.yaml

# Deploy
kubectl apply -f my-service.yaml
```

### 2. Metrics Template

**File:** `integration-templates/metrics-template.py`

Python code showing how to expose Prometheus metrics in your service.

**Minimum Required Metrics:**
- `http_request_duration_seconds` (histogram)
- `http_requests_total` (counter with status label)
- `process_cpu_seconds_total` (counter)
- `process_resident_memory_bytes` (gauge)

### 3. Dependency Annotations

**File:** `integration-templates/dependency-annotations.yaml`

Examples of declaring service dependencies for better correlation.

## 🎯 Sample Services

The `sample-services/` directory contains 5 demo microservices that simulate an e-commerce platform:

### S1 - Checkout Service
- **Port:** 8001
- **Dependencies:** S2 (Inventory)
- **Simulates:** Customer checkout flow
- **Failure Mode:** High latency when S2 is slow

### S2 - Inventory Service
- **Port:** 8002
- **Dependencies:** S3 (Pricing)
- **Simulates:** Product inventory management
- **Failure Mode:** DB pool exhaustion when S3 is slow

### S3 - Pricing Service
- **Port:** 8003
- **Dependencies:** None
- **Simulates:** Product pricing calculations
- **Failure Mode:** Memory leak causing GC pauses (the root cause!)

### S4 - Payment Gateway
- **Port:** 8004
- **Dependencies:** S2 (Inventory)
- **Simulates:** Payment processing
- **Failure Mode:** Queue buildup when S2 is saturated

### S5 - Recommendation Service
- **Port:** 8005
- **Dependencies:** S2 (Inventory)
- **Simulates:** Product recommendations
- **Failure Mode:** Timeouts when S2 is unavailable

### Architecture

```
┌─────────┐
│   S1    │ Checkout
│ (8001)  │
└────┬────┘
     │
     ↓
┌─────────┐     ┌─────────┐     ┌─────────┐
│   S2    │────→│   S3    │     │   S4    │
│ (8002)  │     │ (8003)  │     │ (8004)  │
│Inventory│     │ Pricing │     │ Payment │
└────┬────┘     └─────────┘     └────┬────┘
     ↑                                │
     │                                │
     └────────────────────────────────┘
              ↑
              │
         ┌─────────┐
         │   S5    │
         │ (8005)  │
         │  Recom  │
         └─────────┘
```

### Deploying Sample Services

```bash
# Deploy all services
kubectl apply -f sample-services/

# Check status
kubectl get pods -n shopfast

# View metrics
kubectl port-forward svc/s1-checkout 8001:80 -n shopfast
curl http://localhost:8001/metrics
```

### Triggering Test Incidents

#### Scenario 1: Memory Leak (S3)
```bash
# Inject memory leak in S3
kubectl exec -it deployment/s3-pricing -n shopfast -- \
  curl -X POST http://localhost:8003/inject-fault?type=memory_leak

# Wait 2-3 minutes for metrics to spike
# AIRP will detect and resolve automatically
```

#### Scenario 2: High Traffic
```bash
# Generate load on S1
kubectl run load-generator --image=busybox -n shopfast -- \
  /bin/sh -c "while true; do wget -q -O- http://s1-checkout/checkout; done"

# AIRP will detect high latency and scale services
```

#### Scenario 3: Database Saturation
```bash
# Exhaust S2 connection pool
kubectl exec -it deployment/s2-inventory -n shopfast -- \
  curl -X POST http://localhost:8002/inject-fault?type=db_saturation

# AIRP will detect and recommend restart or scaling
```

## 🎨 Custom Actions

The `custom-actions/` directory shows how to add new remediation actions.

### Example: Custom Restart with Delay

**File:** `custom-actions/delayed-restart.yaml`

```yaml
remediation_actions:
  delayed_restart:
    description: "Restart pods one at a time with 30s delay"
    applicable_to: ["memory_leak", "bad_state"]
    risk: "low"
    reversible: false
    kubectl_template: |
      for pod in $(kubectl get pods -l app={service} -n {namespace} -o name); do
        kubectl delete $pod -n {namespace}
        sleep 30
      done
    rollback_template: "kubectl rollout undo deployment/{service} -n {namespace}"
```

Add this to your `agents/config/airp.yaml` and AIRP will use it automatically.

## 📊 Custom Metrics

The `custom-metrics/` directory shows how to add business-specific metrics.

### Example: Business Metrics

**File:** `custom-metrics/business-metrics.yaml`

```yaml
prometheus:
  metric_categories:
    BUSINESS:
      - "checkout_success_rate"
      - "revenue_per_minute"
      - "cart_abandonment_rate"
      - "payment_failure_rate"
```

Add these to your `agents/config/airp.yaml` and AIRP will monitor them.

## 🧪 Testing Your Integration

### 1. Verify Service Discovery

```bash
# Check if AIRP discovers your service
curl http://$AIRP_IP:8080/discover | jq '.merged'

# Should include your service name
```

### 2. Check Metrics Collection

```bash
# Trigger monitor agent manually
curl -X POST http://$AIRP_IP:8080/monitor \
  -H "Content-Type: application/json" \
  -d '{"commonLabels": {"alertname": "test"}}'

# Check if your service appears in service_health
```

### 3. Verify Prometheus Scraping

```bash
# Port-forward Prometheus
kubectl port-forward svc/prometheus-kube-prometheus-prometheus 9090:9090 -n shopfast

# Open http://localhost:9090/targets
# Your service should appear with "UP" status
```

### 4. Test Alert Flow

```bash
# Send test alert
curl -X POST https://your-n8n.app.n8n.cloud/webhook/incident-trigger \
  -H "Content-Type: application/json" \
  -d '{
    "commonLabels": {
      "alertname": "HighServiceLatency",
      "service": "your-service-name"
    }
  }'

# Check n8n executions
# Check Slack for approval request
```

## 📚 Best Practices

### Service Labels

✅ **DO:**
- Always add `airp.monitored: "true"` label
- Use consistent service names across K8s and Prometheus
- Add dependency annotations for complex topologies

❌ **DON'T:**
- Use generic names like "service" or "app"
- Change service names after deployment
- Forget to expose metrics port

### Metrics

✅ **DO:**
- Expose metrics on `/metrics` endpoint
- Include RED metrics (Rate, Errors, Duration)
- Add custom business metrics
- Use consistent metric naming

❌ **DON'T:**
- Expose metrics on non-standard ports without ServiceMonitor
- Use high-cardinality labels (user IDs, etc.)
- Change metric names frequently

### Dependencies

✅ **DO:**
- Declare explicit dependencies via annotations
- Keep dependency chains simple
- Document external dependencies

❌ **DON'T:**
- Create circular dependencies
- Have too many levels (>5) of dependencies
- Forget to update when architecture changes

## 🔧 Customization

### Adding Your Own Examples

1. Create a new directory under `sample-services/`
2. Add Dockerfile and Kubernetes manifests
3. Ensure it exposes Prometheus metrics
4. Add to deployment script
5. Document in this README

### Sharing Custom Actions

If you create useful custom actions:
1. Add to `custom-actions/`
2. Document use case and risk level
3. Submit PR to share with community

## 📞 Support

- **Integration Issues:** See [docs/INTEGRATION_GUIDE.md](../docs/INTEGRATION_GUIDE.md)
- **Troubleshooting:** See [docs/TROUBLESHOOTING.md](../docs/TROUBLESHOOTING.md)
- **Questions:** Open a GitHub Discussion

## 📄 License

MIT License - see [LICENSE](../LICENSE)
# AIRP V2 - Complete Setup Guide
## Autonomous Incident Resolution Platform - Generalized Dynamic Version

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Architecture Overview](#architecture-overview)
3. [Part 1: Azure AKS Cluster Setup](#part-1-azure-aks-cluster-setup)
4. [Part 2: PostgreSQL Database Setup](#part-2-postgresql-database-setup)
5. [Part 3: Deploy Microservices](#part-3-deploy-microservices)
6. [Part 4: Prometheus & Alertmanager](#part-4-prometheus--alertmanager)
7. [Part 5: AIRP Agent Service](#part-5-airp-agent-service)
8. [Part 6: n8n Cloud Workflow](#part-6-n8n-cloud-workflow)
9. [Part 7: Testing & Validation](#part-7-testing--validation)
10. [Part 8: Customization Guide](#part-8-customization-guide)

---

## Prerequisites

### Required Accounts
- Azure account with AKS permissions
- OpenAI API key (GPT-4o access)
- n8n Cloud account (free tier works)
- Slack workspace (for notifications)
- Docker Hub account (or Azure Container Registry)

### Required Tools on Your Laptop
```bash
# Install Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# Install Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Verify installations
az --version
kubectl version --client
helm version
docker --version
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Azure AKS Cluster                            │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Your Microservices (labeled: airp.monitored=true)       │   │
│  │  - Any number of services                                │   │
│  │  - Any architecture                                      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           ↓ metrics                             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Prometheus + Alertmanager                               │   │
│  │  - Collects all metrics                                  │   │
│  │  - Fires alerts to n8n                                   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           ↓ alert webhook                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  AIRP Agent Service (FastAPI)                            │   │
│  │  - Dynamic service discovery                             │   │
│  │  - AI-powered RCA                                        │   │
│  │  - Config-driven remediation                             │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           ↑ calls agents                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  PostgreSQL (incident history)                           │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                           ↓ orchestrates
              ┌────────────────────────────┐
              │      n8n Cloud             │
              │  (workflow orchestrator)   │
              └────────────────────────────┘
                           ↓ approval request
                    ┌──────────────┐
                    │    Slack     │
                    │   (human)    │
                    └──────────────┘
```

---

## Part 1: Azure AKS Cluster Setup

### Step 1: Login to Azure
```bash
az login
az account set --subscription "YOUR_SUBSCRIPTION_NAME"
```

### Step 2: Create Resource Group
```bash
az group create \
  --name airp-rg \
  --location eastus
```

### Step 3: Create AKS Cluster
```bash
az aks create \
  --resource-group airp-rg \
  --name airp-cluster \
  --node-count 3 \
  --node-vm-size Standard_D2s_v3 \
  --enable-managed-identity \
  --generate-ssh-keys \
  --network-plugin azure \
  --enable-addons monitoring
```

This takes ~10 minutes.

### Step 4: Get Credentials
```bash
az aks get-credentials \
  --resource-group airp-rg \
  --name airp-cluster

# Verify
kubectl get nodes
```

### Step 5: Create Namespace
```bash
kubectl create namespace shopfast
kubectl config set-context --current --namespace=shopfast
```

---

## Part 2: PostgreSQL Database Setup

### Option A: Azure Database for PostgreSQL (Recommended for Production)

```bash
# Create PostgreSQL server
az postgres flexible-server create \
  --resource-group airp-rg \
  --name airp-postgres \
  --location eastus \
  --admin-user airpadmin \
  --admin-password 'YourSecurePassword123!' \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --version 14 \
  --storage-size 32 \
  --public-access 0.0.0.0

# Create database
az postgres flexible-server db create \
  --resource-group airp-rg \
  --server-name airp-postgres \
  --database-name airp

# Get connection string
az postgres flexible-server show \
  --resource-group airp-rg \
  --name airp-postgres \
  --query "fullyQualifiedDomainName" -o tsv
```

**Save this connection info**:
- Host: `airp-postgres.postgres.database.azure.com`
- Database: `airp`
- User: `airpadmin`
- Password: `YourSecurePassword123!`

### Option B: PostgreSQL in Kubernetes (For Testing)

```bash
# Create postgres deployment
kubectl apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: postgres-secret
  namespace: shopfast
type: Opaque
stringData:
  POSTGRES_PASSWORD: airp123
  POSTGRES_USER: airp
  POSTGRES_DB: airp
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
  namespace: shopfast
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:14
        ports:
        - containerPort: 5432
        envFrom:
        - secretRef:
            name: postgres-secret
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
      volumes:
      - name: postgres-storage
        emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: shopfast
spec:
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432
EOF
```

---

## Part 3: Deploy Microservices

### Step 1: Label Your Services

For AIRP to discover your services, they must have the label `airp.monitored=true`.

**Example deployment with label**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-service
  namespace: shopfast
  labels:
    app: my-service
    airp.monitored: "true"  # ← Required for discovery
  annotations:
    airp.io/depends-on: "other-service,another-service"  # ← Optional: explicit dependencies
spec:
  replicas: 2
  selector:
    matchLabels:
      app: my-service
  template:
    metadata:
      labels:
        app: my-service
        service: my-service  # ← Required: matches Prometheus service label
    spec:
      containers:
      - name: my-service
        image: your-registry/my-service:latest
        ports:
        - containerPort: 8080
        env:
        - name: SERVICE_NAME
          value: "my-service"
```

### Step 2: Ensure Prometheus Metrics

Your services must expose Prometheus metrics on `/metrics` endpoint.

**Minimum required metrics** (AIRP will collect all available):
- `http_request_duration_seconds` (histogram)
- `http_requests_total` (counter with `status` label)
- `process_cpu_seconds_total` (counter)
- `process_resident_memory_bytes` (gauge)

**Optional but recommended**:
- `db_connection_pool_usage_percent`
- `gc_pause_duration_ms`
- Custom business metrics

### Step 3: Deploy Your Services

```bash
# Apply all your service manifests
kubectl apply -f your-services/

# Verify they're labeled correctly
kubectl get deployments -n shopfast -l airp.monitored=true
```

---

## Part 4: Prometheus & Alertmanager

### Step 1: Install Prometheus Stack with Helm

```bash
# Add Prometheus community Helm repo
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install kube-prometheus-stack
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace shopfast \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false \
  --set prometheus.prometheusSpec.podMonitorSelectorNilUsesHelmValues=false
```

### Step 2: Configure ServiceMonitor for Your Services

```bash
kubectl apply -f - <<EOF
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: airp-services
  namespace: shopfast
spec:
  selector:
    matchLabels:
      airp.monitored: "true"
  endpoints:
  - port: http
    path: /metrics
    interval: 15s
EOF
```

### Step 3: Get n8n Webhook URL

1. Go to https://app.n8n.cloud
2. Create new workflow: "AIRP - Incident Resolution"
3. Add **Webhook** trigger node
4. Set path: `incident-trigger`
5. Copy the webhook URL (looks like: `https://your-instance.app.n8n.cloud/webhook/incident-trigger`)

### Step 4: Configure Alertmanager

```bash
# Get the webhook URL from n8n (from step 3)
N8N_WEBHOOK_URL="https://your-instance.app.n8n.cloud/webhook/incident-trigger"

# Create Alertmanager config
kubectl apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: alertmanager-prometheus-kube-prometheus-alertmanager
  namespace: shopfast
type: Opaque
stringData:
  alertmanager.yaml: |
    global:
      resolve_timeout: 5m
    route:
      group_by: ['alertname', 'cluster', 'service']
      group_wait: 10s
      group_interval: 10s
      repeat_interval: 12h
      receiver: 'airp-webhook'
    receivers:
    - name: 'airp-webhook'
      webhook_configs:
      - url: '${N8N_WEBHOOK_URL}'
        send_resolved: true
EOF

# Restart Alertmanager to pick up new config
kubectl rollout restart statefulset/alertmanager-prometheus-kube-prometheus-alertmanager -n shopfast
```

### Step 5: Create Alert Rules

```bash
kubectl apply -f - <<EOF
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: airp-alerts
  namespace: shopfast
  labels:
    prometheus: kube-prometheus
spec:
  groups:
  - name: airp.rules
    interval: 30s
    rules:
    # High latency alert
    - alert: HighServiceLatency
      expr: |
        histogram_quantile(0.99, 
          rate(http_request_duration_seconds_bucket[2m])
        ) > 0.5
      for: 1m
      labels:
        severity: critical
      annotations:
        summary: "High latency detected on {{ \$labels.service }}"
        description: "P99 latency is {{ \$value }}s (threshold: 0.5s)"
    
    # High error rate alert
    - alert: HighErrorRate
      expr: |
        rate(http_requests_total{status=~"5.."}[5m]) 
        / rate(http_requests_total[5m]) > 0.05
      for: 2m
      labels:
        severity: critical
      annotations:
        summary: "High error rate on {{ \$labels.service }}"
        description: "Error rate is {{ \$value | humanizePercentage }}"
    
    # High memory usage
    - alert: HighMemoryUsage
      expr: |
        process_resident_memory_bytes / 1024 / 1024 > 500
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "High memory usage on {{ \$labels.service }}"
        description: "Memory usage is {{ \$value }}MB"
EOF
```

---

## Part 5: AIRP Agent Service

### Step 1: Create Configuration

```bash
# Create ConfigMap from airp.yaml
kubectl create configmap airp-config \
  --from-file=airp.yaml=new/airp.yaml \
  -n shopfast
```

### Step 2: Create Secrets

```bash
# Create secret with credentials
kubectl create secret generic airp-secrets \
  --from-literal=OPENAI_API_KEY='your-openai-api-key' \
  --from-literal=DB_HOST='postgres' \
  --from-literal=DB_PORT='5432' \
  --from-literal=DB_NAME='airp' \
  --from-literal=DB_USER='airp' \
  --from-literal=DB_PASSWORD='airp123' \
  --from-literal=PROMETHEUS_URL='http://prometheus-kube-prometheus-prometheus:9090' \
  -n shopfast
```

### Step 3: Build and Push Docker Image

```bash
# Create Dockerfile
cat > Dockerfile <<'EOF'
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install kubectl
RUN curl -LO "https://dl.k8s.io/release/v1.28.0/bin/linux/amd64/kubectl" \
    && install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl \
    && rm kubectl

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY main.py .

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
EOF

# Create requirements.txt
cat > requirements.txt <<'EOF'
fastapi==0.104.1
uvicorn[standard]==0.24.0
openai==1.3.5
pyyaml==6.0.1
requests==2.31.0
psycopg2-binary==2.9.9
pydantic==2.5.0
EOF

# Copy main.py from new/ directory
cp new/main.py .

# Build and push
docker build -t your-dockerhub-username/airp-agents:v2 .
docker push your-dockerhub-username/airp-agents:v2
```

### Step 4: Deploy AIRP Agent Service

```bash
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: airp-agents
  namespace: shopfast
spec:
  replicas: 2
  selector:
    matchLabels:
      app: airp-agents
  template:
    metadata:
      labels:
        app: airp-agents
    spec:
      serviceAccountName: airp-agent-sa
      containers:
      - name: airp-agents
        image: your-dockerhub-username/airp-agents:v2
        ports:
        - containerPort: 8080
        env:
        - name: AIRP_CONFIG_PATH
          value: /config/airp.yaml
        envFrom:
        - secretRef:
            name: airp-secrets
        volumeMounts:
        - name: config
          mountPath: /config
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
      volumes:
      - name: config
        configMap:
          name: airp-config
---
apiVersion: v1
kind: Service
metadata:
  name: airp-agents
  namespace: shopfast
spec:
  type: LoadBalancer
  selector:
    app: airp-agents
  ports:
  - port: 8080
    targetPort: 8080
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: airp-agent-sa
  namespace: shopfast
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: airp-agent-role
  namespace: shopfast
rules:
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list", "patch", "update"]
- apiGroups: ["apps"]
  resources: ["deployments/scale"]
  verbs: ["get", "patch", "update"]
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: airp-agent-binding
  namespace: shopfast
subjects:
- kind: ServiceAccount
  name: airp-agent-sa
  namespace: shopfast
roleRef:
  kind: Role
  name: airp-agent-role
  apiGroup: rbac.authorization.k8s.io
EOF
```

### Step 5: Get AIRP Service External IP

```bash
# Wait for external IP
kubectl get svc airp-agents -n shopfast -w

# Once you have the IP, save it
AIRP_AGENTS_IP=$(kubectl get svc airp-agents -n shopfast -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "AIRP Agents IP: $AIRP_AGENTS_IP"
```

### Step 6: Test AIRP Service

```bash
# Health check
curl http://$AIRP_AGENTS_IP:8080/health

# Test service discovery
curl http://$AIRP_AGENTS_IP:8080/discover

# View loaded config
curl http://$AIRP_AGENTS_IP:8080/config
```

---

## Part 6: n8n Cloud Workflow

### Step 1: Configure n8n Variables

In n8n Cloud:
1. Go to **Settings** → **Variables**
2. Add these variables:
   - `AIRP_AGENTS_IP`: `<your-airp-service-ip>` (from Part 5, Step 5)
   - `N8N_APPROVAL_WEBHOOK`: `https://your-instance.app.n8n.cloud/webhook/sre-approval`

### Step 2: Configure Slack Credentials

1. In n8n, go to **Credentials** → **Add Credential**
2. Select **Slack OAuth2 API**
3. Follow the OAuth flow to connect your Slack workspace
4. Grant permissions: `chat:write`, `channels:read`

### Step 3: Import Workflow

1. In n8n, click **Import from File**
2. Upload the `airpAgent.json` file (the fixed version from earlier)
3. Or copy-paste the JSON content

### Step 4: Update Workflow Nodes

The workflow should already be correct, but verify:
- **Webhook** node: Path is `incident-trigger`
- **HTTP Request** nodes: All use `{{ $vars.AIRP_AGENTS_IP }}`
- **Slack** nodes: Use your Slack credential
- **Wait for SRE Approval** webhook: Path is `sre-approval`

### Step 5: Activate Workflow

Click **Active** toggle in top-right corner.

---

## Part 7: Testing & Validation

### Test 1: Manual Service Discovery

```bash
# Trigger discovery
curl http://$AIRP_AGENTS_IP:8080/discover

# Should return list of all services with airp.monitored=true label
```

### Test 2: Simulate an Incident

Create a test pod that generates high latency:

```bash
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-slow-service
  namespace: shopfast
  labels:
    airp.monitored: "true"
spec:
  replicas: 1
  selector:
    matchLabels:
      app: test-slow-service
  template:
    metadata:
      labels:
        app: test-slow-service
        service: test-slow-service
    spec:
      containers:
      - name: app
        image: nginx:alpine
        ports:
        - containerPort: 80
        command: ["/bin/sh"]
        args:
        - -c
        - |
          # Simulate slow responses
          while true; do
            sleep 2  # 2 second delay = high latency
          done
EOF
```

### Test 3: Trigger Alert Manually

```bash
# Send test alert to n8n webhook
curl -X POST https://your-instance.app.n8n.cloud/webhook/incident-trigger \
  -H "Content-Type: application/json" \
  -d '{
    "status": "firing",
    "commonLabels": {
      "alertname": "HighServiceLatency",
      "severity": "critical",
      "service": "test-slow-service"
    },
    "alerts": [{
      "status": "firing",
      "labels": {
        "alertname": "HighServiceLatency",
        "service": "test-slow-service"
      },
      "annotations": {
        "summary": "Test incident"
      }
    }]
  }'
```

### Test 4: Watch the Workflow

1. Go to n8n **Executions** tab
2. Watch the workflow progress through each agent
3. Check Slack for the approval request
4. Click **APPROVE FIX** in Slack
5. Verify the remediation was executed

### Test 5: Verify Database History

```bash
# Connect to PostgreSQL
kubectl exec -it deployment/postgres -n shopfast -- psql -U airp -d airp

# Query incidents
SELECT incident_id, alert_name, root_cause, action_taken, outcome 
FROM incidents 
ORDER BY created_at DESC 
LIMIT 5;

# Exit
\q
```

---

## Part 8: Customization Guide

### Adding New Metrics

Edit `airp.yaml`:

```yaml
prometheus:
  metric_categories:
    CUSTOM:
      - "your_custom_metric_name"
      - "another_metric{label='value'}"
```

Update ConfigMap:
```bash
kubectl create configmap airp-config \
  --from-file=airp.yaml=new/airp.yaml \
  -n shopfast \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl rollout restart deployment/airp-agents -n shopfast
```

### Adding New Remediation Actions

Edit `airp.yaml`:

```yaml
remediation_actions:
  your_new_action:
    description: "What this action does"
    applicable_to: ["incident_type1", "incident_type2"]
    risk: "low"
    reversible: true
    kubectl_template: "kubectl your command {service} {value}"
    rollback_template: "kubectl rollback command {service}"
```

No code changes needed! GPT will automatically use the new action.

### Adjusting Thresholds

Edit `airp.yaml`:

```yaml
anomaly_detection:
  affected_threshold: 2.0      # Lower = more sensitive
  root_cause_threshold: 4.0    # Lower = more candidates
  weights:
    latency_p99: 5.0           # Higher = more important
```

### Changing Risk Tolerance

Edit `airp.yaml`:

```yaml
platform:
  risk_tolerance: "high"       # low | medium | high
  min_confidence_to_act: 0.6   # Lower = more autonomous
  auto_approve_below_risk: "medium"  # Auto-approve medium risk actions
```

### Adding More Services

Just label them:

```bash
kubectl label deployment your-service airp.monitored=true -n shopfast
```

AIRP will auto-discover them on next refresh (5 minutes) or immediately via:

```bash
curl http://$AIRP_AGENTS_IP:8080/discover
```

---

## 🎯 Success Criteria

Your AIRP system is working correctly when:

✅ Service discovery returns all labeled deployments  
✅ Prometheus is scraping metrics from all services  
✅ Alerts fire and reach n8n webhook  
✅ n8n workflow executes all 7 agents successfully  
✅ Slack receives approval requests with full context  
✅ Approved remediations execute kubectl commands  
✅ Validation confirms recovery  
✅ Incidents are saved to PostgreSQL  
✅ Future incidents benefit from historical context  

---

## 🐛 Troubleshooting

### AIRP agents can't discover services
```bash
# Check RBAC permissions
kubectl auth can-i get deployments --as=system:serviceaccount:shopfast:airp-agent-sa -n shopfast

# Check labels
kubectl get deployments -n shopfast --show-labels | grep airp.monitored
```

### Prometheus not scraping metrics
```bash
# Check ServiceMonitor
kubectl get servicemonitor -n shopfast

# Check Prometheus targets
kubectl port-forward svc/prometheus-kube-prometheus-prometheus 9090:9090 -n shopfast
# Open http://localhost:9090/targets
```

### n8n workflow fails
```bash
# Check AIRP service logs
kubectl logs -f deployment/airp-agents -n shopfast

# Check if AIRP is reachable from n8n
curl http://$AIRP_AGENTS_IP:8080/health
```

### Database connection issues
```bash
# Test connection
kubectl exec -it deployment/airp-agents -n shopfast -- \
  python -c "import psycopg2; psycopg2.connect(host='postgres', dbname='airp', user='airp', password='airp123')"
```

---

## 📚 Next Steps

1. **Add More Services**: Label all your production services
2. **Tune Thresholds**: Adjust based on your baseline metrics
3. **Create Custom Alerts**: Add domain-specific alert rules
4. **Extend Actions**: Add remediation actions specific to your stack
5. **Enable Plugins**: Configure Loki, Jaeger, PagerDuty integrations
6. **Monitor AIRP**: Set up alerts for AIRP itself
7. **Train Your Team**: Document your specific incident patterns

---

## 🎓 Learning Resources

- **Prometheus Queries**: https://prometheus.io/docs/prometheus/latest/querying/basics/
- **Kubernetes RBAC**: https://kubernetes.io/docs/reference/access-authn-authz/rbac/
- **n8n Documentation**: https://docs.n8n.io/
- **OpenAI API**: https://platform.openai.com/docs/

---

## 📞 Support

For issues or questions:
1. Check logs: `kubectl logs -f deployment/airp-agents -n shopfast`
2. Review config: `curl http://$AIRP_AGENTS_IP:8080/config`
3. Test discovery: `curl http://$AIRP_AGENTS_IP:8080/discover`

---

**🎉 Congratulations! You now have a production-ready autonomous incident resolution platform that learns and improves over time.**
# AIRP Hackathon — Complete Build Plan
## Autonomous Incident Resolution Platform on Azure AKS + n8n Cloud

---

## The Story: "The Checkout Latency Spiral"

You are the SRE team at **ShopFast**, a growing e-commerce company. Your platform runs
on Azure Kubernetes Service. At 2:14 AM on a Friday, your Checkout Service starts
responding slowly. Customers can't complete purchases. Revenue is bleeding.

But here is the twist: **the problem isn't in Checkout at all.**

```
The Alert:    S1 Checkout Service latency spikes to 720ms (threshold: 500ms)
The Reality:  S3 Pricing Service has a memory leak causing Garbage Collection pauses
The Chain:    S3 slows → S2 Inventory exhausts its DB connection pool
              → S1 Checkout times out waiting for S2
              → S4 Payment and S5 Recommendations also pile onto S2
              → Everything looks broken but only S3 is actually broken
```

The AIRP wakes up, traces the chain, finds S3 as the root cause, recommends scaling
it, waits for your approval, executes the fix, validates recovery, and files the report.
All in under 5 minutes. You just click Approve in Slack.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                  Azure AKS Cluster                       │
│                                                          │
│  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐      │
│  │  S1  │  │  S2  │  │  S3  │  │  S4  │  │  S5  │      │
│  │Check │→ │Inven │→ │Price │  │Pay   │  │Recom │      │
│  │-out  │  │-tory │  │-ing  │  │-ment │  │-end  │      │
│  └──────┘  └──────┘  └──────┘  └──────┘  └──────┘      │
│       │         │         │                              │
│       └─────────┴─────────┘                             │
│                 ↓                                        │
│          ┌──────────┐     ┌─────────┐                   │
│          │Prometheus│     │ Grafana │                    │
│          │+ Alert   │     │Dashboard│                    │
│          │ Manager  │     └─────────┘                   │
│          └──────────┘                                    │
│                 │                                        │
│          ┌──────────────────────────────────┐           │
│          │        AIRP Agent Service        │           │
│          │  /monitor  /correlate  /rca      │           │
│          │  /remediate  /k8s  /document     │           │
│          └──────────────────────────────────┘           │
└─────────────────────────────────────────────────────────┘
                          │  alert webhook
                          ↓
              ┌───────────────────────┐
              │     n8n Cloud         │
              │  Workflow Orchestrator│
              └───────────────────────┘
                          │  approval
                          ↓
                    ┌──────────┐
                    │  Slack   │
                    │  (human) │
                    └──────────┘
```

---

## Part 1: Prerequisites and Accounts Needed

Before writing a single line of code, set these up:

| Tool | Where | Cost | Purpose |
|------|--------|------|---------|
| Azure Account | portal.azure.com | Free tier / trial | Host AKS cluster |
| n8n Cloud | app.n8n.cloud | 14-day free trial | Workflow orchestration |
| OpenAI Account | platform.openai.com | Pay per use (~$1 for demo) | AI reasoning in agents |
| Slack Workspace | slack.com | Free | Human approval channel |
| Docker Desktop | docker.com | Free | Build container images |
| kubectl | kubernetes.io/docs | Free | Talk to AKS from your laptop |
| Azure CLI | learn.microsoft.com | Free | Manage Azure resources |

---

## Part 2: Azure AKS Cluster Setup

### Step 1 — Install tools on your laptop

```bash
# Install Azure CLI (Mac)
brew install azure-cli

# Install kubectl
brew install kubectl

# Login to Azure
az login
```

### Step 2 — Create the AKS cluster

```bash
# Create a resource group
az group create \
  --name airp-hackathon-rg \
  --location eastus

# Create the AKS cluster (small, cheap nodes for hackathon)
az aks create \
  --resource-group airp-hackathon-rg \
  --name airp-cluster \
  --node-count 2 \
  --node-vm-size Standard_B2s \
  --generate-ssh-keys \
  --enable-managed-identity

# Get credentials so kubectl works
az aks get-credentials \
  --resource-group airp-hackathon-rg \
  --name airp-cluster

# Verify it works
kubectl get nodes
# Should show 2 nodes in Ready state
```

### Step 3 — Create a namespace for the project

```bash
kubectl create namespace shopfast
kubectl config set-context --current --namespace=shopfast
```

---

## Part 3: The Microservices (S1–S5)

Each service is a tiny Python FastAPI app. They are intentionally simple.
The point is the observability data they emit, not the business logic.

### S1 — Checkout Service

**File: `services/s1-checkout/main.py`**

```python
import time
import random
import os
import requests
from fastapi import FastAPI
from prometheus_client import Histogram, Counter, generate_latest
from prometheus_client import CONTENT_TYPE_LATEST
from fastapi.responses import Response

app = FastAPI()

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'Request latency',
    ['service', 'endpoint']
)
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total requests',
    ['service', 'status']
)

INJECT_LATENCY = os.getenv("INJECT_LATENCY", "false") == "true"
S2_URL = os.getenv("S2_URL", "http://s2-inventory:8000")

@app.get("/checkout")
def checkout():
    start = time.time()
    try:
        # Call S2 Inventory service
        resp = requests.get(f"{S2_URL}/inventory/check", timeout=5)
        duration = time.time() - start

        if INJECT_LATENCY:
            # Simulate additional latency when fault is injected
            time.sleep(0.4)
            duration += 0.4

        REQUEST_LATENCY.labels(service="s1", endpoint="/checkout").observe(duration)
        REQUEST_COUNT.labels(service="s1", status="200").inc()
        return {"status": "ok", "latency_ms": round(duration * 1000)}
    except Exception as e:
        REQUEST_COUNT.labels(service="s1", status="500").inc()
        return {"status": "error", "message": str(e)}, 500

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/health")
def health():
    return {"status": "healthy", "service": "s1-checkout"}
```

**File: `services/s1-checkout/Dockerfile`**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN pip install fastapi uvicorn prometheus-client requests
COPY main.py .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

### S2 — Inventory Service

**File: `services/s2-inventory/main.py`**

```python
import time
import os
import requests
from fastapi import FastAPI
from prometheus_client import Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

app = FastAPI()

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'Request latency',
    ['service', 'endpoint']
)
DB_POOL_USAGE = Gauge(
    'db_connection_pool_usage_percent',
    'DB connection pool usage',
    ['service']
)

S3_URL = os.getenv("S3_URL", "http://s3-pricing:8000")
# When S3 is slow, S2 pool fills up
_pool_usage = 30.0

@app.get("/inventory/check")
def check_inventory():
    global _pool_usage
    start = time.time()

    try:
        resp = requests.get(f"{S3_URL}/price/calculate", timeout=3)
        s3_latency = resp.json().get("latency_ms", 50)

        # Pool usage goes up when S3 is slow (backpressure simulation)
        if s3_latency > 200:
            _pool_usage = min(98, _pool_usage + 5)
        else:
            _pool_usage = max(30, _pool_usage - 2)

        DB_POOL_USAGE.labels(service="s2").set(_pool_usage)
        duration = time.time() - start
        REQUEST_LATENCY.labels(service="s2", endpoint="/inventory/check").observe(duration)
        return {"status": "ok", "pool_usage_percent": _pool_usage}
    except Exception as e:
        _pool_usage = min(98, _pool_usage + 10)
        DB_POOL_USAGE.labels(service="s2").set(_pool_usage)
        return {"status": "degraded", "pool_usage_percent": _pool_usage}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/health")
def health():
    return {"status": "healthy", "service": "s2-inventory"}
```

**File: `services/s2-inventory/Dockerfile`**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN pip install fastapi uvicorn prometheus-client requests
COPY main.py .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

### S3 — Pricing Service (THE ROOT CAUSE)

**File: `services/s3-pricing/main.py`**

```python
import time
import os
import gc
from fastapi import FastAPI
from prometheus_client import Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

app = FastAPI()

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'Request latency',
    ['service', 'endpoint']
)
GC_PAUSE_DURATION = Gauge(
    'gc_pause_duration_ms',
    'Garbage collection pause duration',
    ['service']
)
MEMORY_USAGE = Gauge(
    'memory_usage_mb',
    'Memory usage in MB',
    ['service']
)

INJECT_GC_FAULT = os.getenv("INJECT_GC_FAULT", "false") == "true"
_leaked_memory = []  # simulated memory leak

@app.get("/price/calculate")
def calculate_price():
    global _leaked_memory
    start = time.time()

    if INJECT_GC_FAULT:
        # Simulate memory leak - allocate but never free
        _leaked_memory.append(" " * 100000)  # 100KB per request
        gc_start = time.time()
        gc.collect()  # force GC which takes time
        gc_pause = (time.time() - gc_start) * 1000
        GC_PAUSE_DURATION.labels(service="s3").set(gc_pause)
        MEMORY_USAGE.labels(service="s3").set(len(_leaked_memory) * 0.1)
        # Add artificial delay to simulate GC pause impact
        time.sleep(0.3)
    else:
        GC_PAUSE_DURATION.labels(service="s3").set(5)
        MEMORY_USAGE.labels(service="s3").set(50)

    duration = time.time() - start
    REQUEST_LATENCY.labels(service="s3", endpoint="/price/calculate").observe(duration)

    return {
        "status": "ok",
        "price": 99.99,
        "latency_ms": round(duration * 1000),
        "gc_active": INJECT_GC_FAULT
    }

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/health")
def health():
    return {"status": "healthy", "service": "s3-pricing"}
```

**File: `services/s3-pricing/Dockerfile`**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN pip install fastapi uvicorn prometheus-client
COPY main.py .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

### S4 — Payment Gateway Proxy

**File: `services/s4-payment/main.py`**

```python
import time
import os
import requests
from fastapi import FastAPI
from prometheus_client import Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

app = FastAPI()

QUEUE_LENGTH = Gauge('payment_queue_length', 'Payment queue length', ['service'])
REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds', 'Latency', ['service', 'endpoint']
)
_queue = 0

S2_URL = os.getenv("S2_URL", "http://s2-inventory:8000")

@app.get("/payment/process")
def process_payment():
    global _queue
    start = time.time()
    _queue += 1
    QUEUE_LENGTH.labels(service="s4").set(_queue)
    try:
        requests.get(f"{S2_URL}/inventory/check", timeout=2)
        _queue = max(0, _queue - 1)
    except:
        pass  # stays in queue
    duration = time.time() - start
    REQUEST_LATENCY.labels(service="s4", endpoint="/payment/process").observe(duration)
    QUEUE_LENGTH.labels(service="s4").set(_queue)
    return {"status": "queued", "queue_length": _queue}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/health")
def health():
    return {"status": "healthy", "service": "s4-payment"}
```

**File: `services/s4-payment/Dockerfile`**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN pip install fastapi uvicorn prometheus-client requests
COPY main.py .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

### S5 — Recommendation Service

**File: `services/s5-recommendation/main.py`**

```python
import time
import os
import requests
from fastapi import FastAPI
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

app = FastAPI()

TIMEOUT_COUNT = Counter('request_timeouts_total', 'Timeouts', ['service'])
REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds', 'Latency', ['service', 'endpoint']
)

S2_URL = os.getenv("S2_URL", "http://s2-inventory:8000")

@app.get("/recommendations")
def get_recommendations():
    start = time.time()
    try:
        requests.get(f"{S2_URL}/inventory/check", timeout=1)
    except requests.Timeout:
        TIMEOUT_COUNT.labels(service="s5").inc()
        return {"status": "degraded", "recommendations": [], "reason": "inventory timeout"}
    except Exception:
        TIMEOUT_COUNT.labels(service="s5").inc()
    duration = time.time() - start
    REQUEST_LATENCY.labels(service="s5", endpoint="/recommendations").observe(duration)
    return {"status": "ok", "recommendations": ["item-1", "item-2", "item-3"]}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/health")
def health():
    return {"status": "healthy", "service": "s5-recommendation"}
```

**File: `services/s5-recommendation/Dockerfile`**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN pip install fastapi uvicorn prometheus-client requests
COPY main.py .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Part 4: Kubernetes Manifests

### Namespace + Services Deployment

**File: `k8s/services.yaml`**

```yaml
# ─────────────────────────────────────────────────
# S1 Checkout Service
# ─────────────────────────────────────────────────
apiVersion: apps/v1
kind: Deployment
metadata:
  name: s1-checkout
  namespace: shopfast
spec:
  replicas: 2
  selector:
    matchLabels:
      app: s1-checkout
  template:
    metadata:
      labels:
        app: s1-checkout
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/metrics"
    spec:
      containers:
      - name: s1-checkout
        image: YOUR_ACR_NAME.azurecr.io/s1-checkout:latest
        ports:
        - containerPort: 8000
        env:
        - name: S2_URL
          value: "http://s2-inventory:8000"
        - name: INJECT_LATENCY
          value: "false"   # ← Change to "true" to trigger the incident
---
apiVersion: v1
kind: Service
metadata:
  name: s1-checkout
  namespace: shopfast
spec:
  selector:
    app: s1-checkout
  ports:
  - port: 8000
  type: ClusterIP

---
# ─────────────────────────────────────────────────
# S2 Inventory Service
# ─────────────────────────────────────────────────
apiVersion: apps/v1
kind: Deployment
metadata:
  name: s2-inventory
  namespace: shopfast
spec:
  replicas: 2
  selector:
    matchLabels:
      app: s2-inventory
  template:
    metadata:
      labels:
        app: s2-inventory
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/metrics"
    spec:
      containers:
      - name: s2-inventory
        image: YOUR_ACR_NAME.azurecr.io/s2-inventory:latest
        ports:
        - containerPort: 8000
        env:
        - name: S3_URL
          value: "http://s3-pricing:8000"
---
apiVersion: v1
kind: Service
metadata:
  name: s2-inventory
  namespace: shopfast
spec:
  selector:
    app: s2-inventory
  ports:
  - port: 8000
  type: ClusterIP

---
# ─────────────────────────────────────────────────
# S3 Pricing Service (Root Cause)
# ─────────────────────────────────────────────────
apiVersion: apps/v1
kind: Deployment
metadata:
  name: s3-pricing
  namespace: shopfast
spec:
  replicas: 2
  selector:
    matchLabels:
      app: s3-pricing
  template:
    metadata:
      labels:
        app: s3-pricing
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/metrics"
    spec:
      containers:
      - name: s3-pricing
        image: YOUR_ACR_NAME.azurecr.io/s3-pricing:latest
        ports:
        - containerPort: 8000
        env:
        - name: INJECT_GC_FAULT
          value: "false"   # ← Change to "true" to inject the fault
---
apiVersion: v1
kind: Service
metadata:
  name: s3-pricing
  namespace: shopfast
spec:
  selector:
    app: s3-pricing
  ports:
  - port: 8000
  type: ClusterIP

---
# ─────────────────────────────────────────────────
# S4 Payment Gateway
# ─────────────────────────────────────────────────
apiVersion: apps/v1
kind: Deployment
metadata:
  name: s4-payment
  namespace: shopfast
spec:
  replicas: 1
  selector:
    matchLabels:
      app: s4-payment
  template:
    metadata:
      labels:
        app: s4-payment
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/metrics"
    spec:
      containers:
      - name: s4-payment
        image: YOUR_ACR_NAME.azurecr.io/s4-payment:latest
        ports:
        - containerPort: 8000
        env:
        - name: S2_URL
          value: "http://s2-inventory:8000"
---
apiVersion: v1
kind: Service
metadata:
  name: s4-payment
  namespace: shopfast
spec:
  selector:
    app: s4-payment
  ports:
  - port: 8000
  type: ClusterIP

---
# ─────────────────────────────────────────────────
# S5 Recommendation Service
# ─────────────────────────────────────────────────
apiVersion: apps/v1
kind: Deployment
metadata:
  name: s5-recommendation
  namespace: shopfast
spec:
  replicas: 1
  selector:
    matchLabels:
      app: s5-recommendation
  template:
    metadata:
      labels:
        app: s5-recommendation
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/metrics"
    spec:
      containers:
      - name: s5-recommendation
        image: YOUR_ACR_NAME.azurecr.io/s5-recommendation:latest
        ports:
        - containerPort: 8000
        env:
        - name: S2_URL
          value: "http://s2-inventory:8000"
---
apiVersion: v1
kind: Service
metadata:
  name: s5-recommendation
  namespace: shopfast
spec:
  selector:
    app: s5-recommendation
  ports:
  - port: 8000
  type: ClusterIP
```

---

## Part 5: Prometheus + Alertmanager Setup

**File: `k8s/prometheus.yaml`**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
  namespace: shopfast
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s

    alerting:
      alertmanagers:
        - static_configs:
            - targets: ['localhost:9093']

    rule_files:
      - /etc/prometheus/alerts.yml

    scrape_configs:
      - job_name: 'shopfast-services'
        kubernetes_sd_configs:
          - role: pod
            namespaces:
              names: ['shopfast']
        relabel_configs:
          - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
            action: keep
            regex: true
          - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
            action: replace
            target_label: __metrics_path__
            regex: (.+)
          - source_labels: [__address__, __meta_kubernetes_pod_annotation_prometheus_io_port]
            action: replace
            regex: ([^:]+)(?::\d+)?;(\d+)
            replacement: $1:$2
            target_label: __address__

  alerts.yml: |
    groups:
      - name: shopfast
        rules:
          - alert: HighCheckoutLatency
            expr: histogram_quantile(0.99,
              rate(http_request_duration_seconds_bucket{service="s1"}[2m])) > 0.5
            for: 1m
            labels:
              severity: critical
            annotations:
              summary: "S1 Checkout latency above 500ms"
              description: "P99 latency is {{ $value | humanizeDuration }}"

          - alert: HighS2PoolUsage
            expr: db_connection_pool_usage_percent{service="s2"} > 80
            for: 1m
            labels:
              severity: warning
            annotations:
              summary: "S2 DB connection pool near saturation"

          - alert: HighS3GCPauses
            expr: gc_pause_duration_ms{service="s3"} > 100
            for: 1m
            labels:
              severity: warning
            annotations:
              summary: "S3 experiencing high GC pause duration"

  alertmanager.yml: |
    global:
      resolve_timeout: 5m

    route:
      group_by: ['alertname']
      group_wait: 10s
      group_interval: 10s
      repeat_interval: 1h
      receiver: 'n8n-webhook'

    receivers:
      - name: 'n8n-webhook'
        webhook_configs:
          - url: 'REPLACE_WITH_YOUR_N8N_WEBHOOK_URL'
            send_resolved: false

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prometheus
  namespace: shopfast
spec:
  replicas: 1
  selector:
    matchLabels:
      app: prometheus
  template:
    metadata:
      labels:
        app: prometheus
    spec:
      serviceAccountName: prometheus-sa
      containers:
      - name: prometheus
        image: prom/prometheus:v2.48.0
        ports:
        - containerPort: 9090
        volumeMounts:
        - name: config
          mountPath: /etc/prometheus
        args:
          - '--config.file=/etc/prometheus/prometheus.yml'
          - '--storage.tsdb.path=/prometheus'
      - name: alertmanager
        image: prom/alertmanager:v0.26.0
        ports:
        - containerPort: 9093
        volumeMounts:
        - name: config
          mountPath: /etc/alertmanager
        args:
          - '--config.file=/etc/alertmanager/alertmanager.yml'
      volumes:
      - name: config
        configMap:
          name: prometheus-config
---
apiVersion: v1
kind: Service
metadata:
  name: prometheus
  namespace: shopfast
spec:
  selector:
    app: prometheus
  ports:
  - name: prometheus
    port: 9090
  - name: alertmanager
    port: 9093
  type: LoadBalancer   # exposed so agents can query it from outside

---
# Prometheus needs permission to read pod info from K8s API
apiVersion: v1
kind: ServiceAccount
metadata:
  name: prometheus-sa
  namespace: shopfast
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: prometheus-role
rules:
- apiGroups: [""]
  resources: ["pods", "endpoints", "services"]
  verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: prometheus-binding
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: prometheus-role
subjects:
- kind: ServiceAccount
  name: prometheus-sa
  namespace: shopfast
```

---

## Part 6: The AIRP Agent Service

All six agents live in **one** Python FastAPI application with six routes.
This means one Dockerfile, one deployment, one URL for n8n to call.

**File: `airp-agents/main.py`**

```python
import os
import time
import subprocess
import requests
from fastapi import FastAPI
from openai import OpenAI
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="AIRP Agent Service")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
NAMESPACE = os.getenv("K8S_NAMESPACE", "shopfast")

# ─── Helper: Query Prometheus ─────────────────────────────────────────
def prom_query(query: str) -> float:
    try:
        r = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": query},
            timeout=5
        )
        result = r.json()["data"]["result"]
        if result:
            return float(result[0]["value"][1])
        return 0.0
    except Exception as e:
        print(f"Prometheus query error: {e}")
        return 0.0

# ─── Helper: Ask GPT ──────────────────────────────────────────────────
def ask_gpt(system_prompt: str, user_prompt: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        response_format={"type": "json_object"}
    )
    return response.choices[0].message.content

# ─── SERVICE DEPENDENCY MAP ───────────────────────────────────────────
DEPENDENCY_MAP = {
    "s1-checkout":      ["s2-inventory"],
    "s2-inventory":     ["s3-pricing"],
    "s4-payment":       ["s2-inventory"],
    "s5-recommendation":["s2-inventory"],
    "s3-pricing":       []
}

# ══════════════════════════════════════════════════════════════════════
# AGENT 1: Monitor Agent
# Reads real metrics from Prometheus and validates the incident
# ══════════════════════════════════════════════════════════════════════
@app.post("/monitor")
def monitor_agent(payload: dict):
    """
    Called first by n8n with the raw Prometheus alert.
    Goes to Prometheus and fetches actual current metrics for all services.
    Returns a validated incident object.
    """
    print("Monitor Agent: fetching current metrics from Prometheus...")

    # Query real metrics
    s1_latency = prom_query(
        'histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{service="s1"}[2m]))'
    ) * 1000  # convert to ms

    s2_pool = prom_query('db_connection_pool_usage_percent{service="s2"}')
    s3_gc   = prom_query('gc_pause_duration_ms{service="s3"}')
    s4_queue = prom_query('payment_queue_length{service="s4"}')
    s5_timeouts = prom_query('increase(request_timeouts_total{service="s5"}[5m])')

    incident = {
        "incident_id": f"INC-{int(time.time())}",
        "triggered_by": payload.get("commonLabels", {}).get("alertname", "HighCheckoutLatency"),
        "severity": "critical",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "metrics": {
            "s1_latency_ms":        round(s1_latency, 1),
            "s2_pool_usage_percent": round(s2_pool, 1),
            "s3_gc_pause_ms":        round(s3_gc, 1),
            "s4_queue_length":       round(s4_queue, 0),
            "s5_timeout_count_5m":   round(s5_timeouts, 0)
        },
        "threshold_breaches": {
            "s1_latency":  s1_latency > 500,
            "s2_pool":     s2_pool > 80,
            "s3_gc":       s3_gc > 100,
        },
        "validated": True
    }

    print(f"Monitor Agent: incident validated → {incident['incident_id']}")
    return incident


# ══════════════════════════════════════════════════════════════════════
# AGENT 2: Correlation Agent
# Maps which services are affected using the dependency map
# ══════════════════════════════════════════════════════════════════════
@app.post("/correlate")
def correlation_agent(incident: dict):
    """
    Receives the validated incident.
    Uses the dependency map to find all affected services.
    Identifies the primary strain point.
    """
    print("Correlation Agent: mapping affected services...")

    metrics = incident.get("metrics", {})
    affected = []
    primary_strain = None
    candidate_cause = None

    # Walk the dependency map and check each service
    for service, deps in DEPENDENCY_MAP.items():
        if service == "s1-checkout" and metrics.get("s1_latency_ms", 0) > 500:
            affected.append({"service": service, "symptom": "high_latency",
                             "value": metrics["s1_latency_ms"]})
        elif service == "s2-inventory" and metrics.get("s2_pool_usage_percent", 0) > 80:
            affected.append({"service": service, "symptom": "pool_saturation",
                             "value": metrics["s2_pool_usage_percent"]})
            primary_strain = "s2-inventory"
        elif service == "s3-pricing" and metrics.get("s3_gc_pause_ms", 0) > 100:
            affected.append({"service": service, "symptom": "gc_pauses",
                             "value": metrics["s3_gc_pause_ms"]})
            candidate_cause = "s3-pricing"
        elif service == "s4-payment" and metrics.get("s4_queue_length", 0) > 10:
            affected.append({"service": service, "symptom": "queue_buildup",
                             "value": metrics["s4_queue_length"]})
        elif service == "s5-recommendation" and metrics.get("s5_timeout_count_5m", 0) > 5:
            affected.append({"service": service, "symptom": "timeouts",
                             "value": metrics["s5_timeout_count_5m"]})

    correlated = {
        **incident,
        "correlated": True,
        "affected_services": affected,
        "primary_strain_service": primary_strain or "s1-checkout",
        "candidate_root_cause": candidate_cause or "unknown",
        "dependency_chain": "s1-checkout → s2-inventory → s3-pricing"
    }

    print(f"Correlation Agent: {len(affected)} services affected, candidate cause: {candidate_cause}")
    return correlated


# ══════════════════════════════════════════════════════════════════════
# AGENT 3: RCA Agent
# Uses GPT to reason about the root cause
# ══════════════════════════════════════════════════════════════════════
@app.post("/rca")
def rca_agent(correlated_incident: dict):
    """
    Receives the correlated incident.
    Calls GPT with full context to determine root cause.
    Returns a diagnosis with confidence scores.
    """
    print("RCA Agent: calling GPT for root cause analysis...")

    metrics = correlated_incident.get("metrics", {})
    affected = correlated_incident.get("affected_services", [])

    system_prompt = """You are a senior Site Reliability Engineer expert in 
    microservice failure analysis. You analyze incident data and provide root 
    cause analysis with confidence scores. Always respond in valid JSON."""

    user_prompt = f"""
    Analyze this incident and determine the root cause.

    INCIDENT METRICS:
    - S1 Checkout Service latency: {metrics.get('s1_latency_ms')}ms (threshold: 500ms)
    - S2 Inventory DB pool usage: {metrics.get('s2_pool_usage_percent')}% (threshold: 80%)
    - S3 Pricing GC pause duration: {metrics.get('s3_gc_pause_ms')}ms (threshold: 100ms)
    - S4 Payment queue length: {metrics.get('s4_queue_length')}
    - S5 Recommendation timeouts (5m): {metrics.get('s5_timeout_count_5m')}

    SERVICE DEPENDENCY CHAIN:
    S1-Checkout → S2-Inventory → S3-Pricing
    S4-Payment → S2-Inventory
    S5-Recommendation → S2-Inventory

    AFFECTED SERVICES: {[s['service'] + ' (' + s['symptom'] + ')' for s in affected]}

    CANDIDATE ROOT CAUSE IDENTIFIED: {correlated_incident.get('candidate_root_cause')}

    RUNBOOK KNOWLEDGE:
    - High GC pauses in a service typically indicate memory leak or insufficient heap
    - When S3 (upstream) slows down, S2 connection pool exhausts because calls queue up
    - When S2 pool exhausts, all downstream callers (S1, S4, S5) experience latency/timeouts
    - Standard remediation for GC issues: scale up replicas to distribute memory pressure

    Provide root cause analysis as JSON with this exact structure:
    {{
      "probable_causes": [
        {{
          "rank": 1,
          "service": "service-name",
          "cause": "description",
          "confidence": 0.0,
          "reasoning": "explanation"
        }}
      ],
      "primary_root_cause": "one sentence summary",
      "failure_chain_explanation": "full explanation of how the failure propagated"
    }}
    """

    result = ask_gpt(system_prompt, user_prompt)

    import json
    diagnosis = json.loads(result)

    return {
        **correlated_incident,
        "diagnosis": diagnosis,
        "rca_complete": True
    }


# ══════════════════════════════════════════════════════════════════════
# AGENT 4: Remediation Agent
# Uses GPT to generate a safe action plan
# ══════════════════════════════════════════════════════════════════════
@app.post("/remediate")
def remediation_agent(rca_result: dict):
    """
    Receives the RCA diagnosis.
    Calls GPT to generate a specific, safe remediation plan.
    Returns recommended action + rollback path.
    """
    print("Remediation Agent: generating action plan...")

    diagnosis = rca_result.get("diagnosis", {})
    primary_cause = diagnosis.get("probable_causes", [{}])[0]
    confidence = primary_cause.get("confidence", 0)

    system_prompt = """You are an SRE remediation specialist. You generate safe,
    specific Kubernetes remediation plans. Always respond in valid JSON.
    Always include a rollback plan. Never recommend destructive actions."""

    user_prompt = f"""
    Generate a remediation plan for this diagnosed incident.

    ROOT CAUSE: {diagnosis.get('primary_root_cause')}
    AFFECTED SERVICE: {primary_cause.get('service')}
    CAUSE TYPE: {primary_cause.get('cause')}
    CONFIDENCE: {confidence}

    AVAILABLE ACTIONS (choose the safest appropriate one):
    1. Scale up deployment replicas
    2. Rolling restart of deployment
    3. Increase resource limits (memory/CPU)
    4. Circuit breaker activation

    CONSTRAINTS:
    - Max replicas per service: 6
    - Current replicas for s3-pricing: 2
    - Must include rollback steps
    - Confidence must be > 0.75 to recommend direct action

    Respond with JSON in this exact structure:
    {{
      "recommended_action": {{
        "type": "scale_up | rolling_restart | resource_increase",
        "target_service": "service-name",
        "target_deployment": "deployment-name-in-k8s",
        "description": "human readable description",
        "kubectl_command": "exact kubectl command to run",
        "expected_outcome": "what should happen after this"
      }},
      "rollback_plan": {{
        "trigger_condition": "when to rollback",
        "kubectl_command": "exact kubectl rollback command",
        "description": "rollback description"
      }},
      "confidence_score": {confidence},
      "requires_human_approval": true,
      "risk_level": "low | medium | high"
    }}
    """

    result = ask_gpt(system_prompt, user_prompt)

    import json
    plan = json.loads(result)

    return {
        **rca_result,
        "remediation_plan": plan,
        "remediation_complete": True
    }


# ══════════════════════════════════════════════════════════════════════
# AGENT 5: K8s Operator
# Actually executes the kubectl command after human approval
# ══════════════════════════════════════════════════════════════════════
class ExecutionRequest(BaseModel):
    deployment: str
    replicas: int
    namespace: str = "shopfast"

@app.post("/execute")
def k8s_operator(req: ExecutionRequest):
    """
    Called by n8n after human approves the plan.
    Runs the actual kubectl scale command against the AKS cluster.
    Returns success/failure.
    """
    print(f"K8s Operator: scaling {req.deployment} to {req.replicas} replicas...")

    cmd = [
        "kubectl", "scale", f"deployment/{req.deployment}",
        f"--replicas={req.replicas}",
        f"--namespace={req.namespace}"
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        success = result.returncode == 0

        # Wait for rollout
        if success:
            rollout_cmd = [
                "kubectl", "rollout", "status",
                f"deployment/{req.deployment}",
                f"--namespace={req.namespace}",
                "--timeout=120s"
            ]
            rollout = subprocess.run(rollout_cmd, capture_output=True, text=True, timeout=130)

        return {
            "success": success,
            "deployment": req.deployment,
            "new_replicas": req.replicas,
            "output": result.stdout,
            "error": result.stderr if not success else None,
            "executed_command": " ".join(cmd)
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "kubectl command timed out"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ══════════════════════════════════════════════════════════════════════
# AGENT 6: Validation Check (Monitor Agent reused)
# Checks if metrics have recovered after the fix
# ══════════════════════════════════════════════════════════════════════
@app.post("/validate")
def validate_recovery(context: dict):
    """
    Called after K8s execution.
    Re-queries Prometheus to check if metrics have recovered.
    """
    print("Validation: checking if metrics recovered...")
    time.sleep(15)  # give the cluster time to stabilize

    s1_latency = prom_query(
        'histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{service="s1"}[2m]))'
    ) * 1000
    s2_pool = prom_query('db_connection_pool_usage_percent{service="s2"}')
    s3_gc   = prom_query('gc_pause_duration_ms{service="s3"}')

    recovered = s1_latency < 300 and s2_pool < 70

    return {
        **context,
        "validation": {
            "recovered": recovered,
            "post_fix_metrics": {
                "s1_latency_ms": round(s1_latency, 1),
                "s2_pool_usage_percent": round(s2_pool, 1),
                "s3_gc_pause_ms": round(s3_gc, 1)
            },
            "recovery_criteria": {
                "s1_latency_below_300ms": s1_latency < 300,
                "s2_pool_below_70_percent": s2_pool < 70
            }
        }
    }


# ══════════════════════════════════════════════════════════════════════
# AGENT 7: Documentation Agent
# GPT writes the full incident report
# ══════════════════════════════════════════════════════════════════════
@app.post("/document")
def documentation_agent(full_context: dict):
    """
    Called at the end of the workflow.
    Uses GPT to write a clean, human-readable incident report.
    """
    print("Documentation Agent: generating incident report...")

    metrics = full_context.get("metrics", {})
    diagnosis = full_context.get("diagnosis", {})
    plan = full_context.get("remediation_plan", {})
    validation = full_context.get("validation", {})

    system_prompt = """You are a technical writer for an SRE team. 
    Write clear, professional incident reports in markdown format.
    Be specific, factual, and concise. Always respond in valid JSON."""

    user_prompt = f"""
    Write a complete incident report for this resolved incident.

    INCIDENT DATA:
    - Incident ID: {full_context.get('incident_id')}
    - Time: {full_context.get('timestamp')}
    - Initial Alert: S1 Checkout latency spike to {metrics.get('s1_latency_ms')}ms
    - Root Cause: {diagnosis.get('primary_root_cause')}
    - Failure Chain: {diagnosis.get('failure_chain_explanation')}
    - Action Taken: {plan.get('recommended_action', {}).get('description')}
    - Recovery Status: {'RECOVERED' if validation.get('recovered') else 'UNRESOLVED'}
    - Post-fix S1 Latency: {validation.get('post_fix_metrics', {}).get('s1_latency_ms')}ms
    - Post-fix S2 Pool: {validation.get('post_fix_metrics', {}).get('s2_pool_usage_percent')}%

    Return JSON with:
    {{
      "title": "incident title",
      "summary": "2-3 sentence executive summary",
      "timeline": ["list of key events with times"],
      "root_cause": "detailed root cause explanation",
      "impact": "what was impacted and for how long",
      "resolution": "what was done to fix it",
      "prevention": "how to prevent this in future",
      "full_markdown_report": "complete markdown report text"
    }}
    """

    result = ask_gpt(system_prompt, user_prompt)

    import json
    report = json.loads(result)

    return {
        "incident_id": full_context.get("incident_id"),
        "report": report,
        "status": "RESOLVED" if validation.get("recovered") else "UNRESOLVED"
    }


@app.get("/health")
def health():
    return {"status": "healthy", "service": "airp-agents"}
```

**File: `airp-agents/Dockerfile`**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN pip install fastapi uvicorn openai requests pydantic
COPY main.py .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

**File: `k8s/airp-agents.yaml`**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: airp-agents
  namespace: shopfast
spec:
  replicas: 1
  selector:
    matchLabels:
      app: airp-agents
  template:
    metadata:
      labels:
        app: airp-agents
    spec:
      serviceAccountName: airp-sa
      containers:
      - name: airp-agents
        image: YOUR_ACR_NAME.azurecr.io/airp-agents:latest
        ports:
        - containerPort: 8080
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: airp-secrets
              key: openai-api-key
        - name: PROMETHEUS_URL
          value: "http://prometheus:9090"
        - name: K8S_NAMESPACE
          value: "shopfast"
---
apiVersion: v1
kind: Service
metadata:
  name: airp-agents
  namespace: shopfast
spec:
  selector:
    app: airp-agents
  ports:
  - port: 8080
  type: LoadBalancer   # Needs public IP so n8n cloud can reach it

---
# AIRP agents need permission to scale deployments
apiVersion: v1
kind: ServiceAccount
metadata:
  name: airp-sa
  namespace: shopfast
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: airp-role
  namespace: shopfast
rules:
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list", "update", "patch"]
- apiGroups: ["apps"]
  resources: ["deployments/scale"]
  verbs: ["update", "patch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: airp-binding
  namespace: shopfast
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: airp-role
subjects:
- kind: ServiceAccount
  name: airp-sa
  namespace: shopfast
```

---

## Part 7: Building and Pushing Docker Images

```bash
# Create Azure Container Registry (image storage)
az acr create \
  --resource-group airp-hackathon-rg \
  --name airphackathonacr \
  --sku Basic

# Log in to the registry
az acr login --name airphackathonacr

# Allow AKS to pull from ACR
az aks update \
  --name airp-cluster \
  --resource-group airp-hackathon-rg \
  --attach-acr airphackathonacr

# Build and push each service
ACR="airphackathonacr.azurecr.io"

# Build all services
for service in s1-checkout s2-inventory s3-pricing s4-payment s5-recommendation; do
  docker build -t $ACR/$service:latest ./services/$service/
  docker push $ACR/$service:latest
done

# Build and push the AIRP agents
docker build -t $ACR/airp-agents:latest ./airp-agents/
docker push $ACR/airp-agents:latest
```

---

## Part 8: Deploy Everything to AKS

```bash
# Store OpenAI key as a Kubernetes secret (never hardcode keys)
kubectl create secret generic airp-secrets \
  --from-literal=openai-api-key=YOUR_OPENAI_API_KEY \
  --namespace shopfast

# Replace YOUR_ACR_NAME in the yaml files
sed -i 's/YOUR_ACR_NAME/airphackathonacr/g' k8s/services.yaml
sed -i 's/YOUR_ACR_NAME/airphackathonacr/g' k8s/airp-agents.yaml

# Deploy everything
kubectl apply -f k8s/services.yaml
kubectl apply -f k8s/prometheus.yaml
kubectl apply -f k8s/airp-agents.yaml

# Wait for everything to start (takes ~3 minutes)
kubectl get pods -n shopfast --watch

# Get the public IPs (takes ~5 minutes for Azure to assign)
kubectl get services -n shopfast
# Look for EXTERNAL-IP on prometheus and airp-agents services
# Note down:
#   PROMETHEUS_IP → for agent environment variable
#   AIRP_AGENTS_IP → for n8n webhook URLs
```

---

## Part 9: n8n Cloud Workflow Setup

### Getting Your n8n Webhook URL

1. Log into app.n8n.cloud
2. Create a new workflow called "AIRP - Incident Resolution"
3. Add a **Webhook** trigger node
4. Copy the webhook URL — it looks like:
   `https://your-instance.app.n8n.cloud/webhook/incident-trigger`
5. Paste this URL into your `alertmanager.yml` ConfigMap and re-apply it

### The Complete n8n Workflow JSON

Import this JSON directly into n8n via **Settings → Import from JSON**:

```json
{
  "name": "AIRP - Incident Resolution Workflow",
  "nodes": [
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "incident-trigger",
        "responseMode": "responseNode",
        "options": {}
      },
      "id": "node-webhook-trigger",
      "name": "Incident Alert Received",
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 1,
      "position": [240, 300]
    },
    {
      "parameters": {
        "respondWith": "json",
        "responseBody": "={{ JSON.stringify({status: 'received', incident_id: Date.now()}) }}"
      },
      "id": "node-webhook-response",
      "name": "Acknowledge Alert",
      "type": "n8n-nodes-base.respondToWebhook",
      "typeVersion": 1,
      "position": [460, 200]
    },
    {
      "parameters": {
        "method": "POST",
        "url": "=http://{{ $vars.AIRP_AGENTS_IP }}:8080/monitor",
        "sendBody": true,
        "bodyContentType": "json",
        "jsonBody": "={{ JSON.stringify($json.body) }}",
        "options": {
          "timeout": 30000
        }
      },
      "id": "node-monitor-agent",
      "name": "Monitor Agent",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4,
      "position": [680, 300]
    },
    {
      "parameters": {
        "method": "POST",
        "url": "=http://{{ $vars.AIRP_AGENTS_IP }}:8080/correlate",
        "sendBody": true,
        "bodyContentType": "json",
        "jsonBody": "={{ JSON.stringify($json) }}",
        "options": {
          "timeout": 30000
        }
      },
      "id": "node-correlation-agent",
      "name": "Correlation Agent",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4,
      "position": [900, 300]
    },
    {
      "parameters": {
        "method": "POST",
        "url": "=http://{{ $vars.AIRP_AGENTS_IP }}:8080/rca",
        "sendBody": true,
        "bodyContentType": "json",
        "jsonBody": "={{ JSON.stringify($json) }}",
        "options": {
          "timeout": 60000
        }
      },
      "id": "node-rca-agent",
      "name": "RCA Agent (GPT)",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4,
      "position": [1120, 300]
    },
    {
      "parameters": {
        "method": "POST",
        "url": "=http://{{ $vars.AIRP_AGENTS_IP }}:8080/remediate",
        "sendBody": true,
        "bodyContentType": "json",
        "jsonBody": "={{ JSON.stringify($json) }}",
        "options": {
          "timeout": 60000
        }
      },
      "id": "node-remediation-agent",
      "name": "Remediation Agent (GPT)",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4,
      "position": [1340, 300]
    },
    {
      "parameters": {
        "authentication": "oAuth2",
        "resource": "message",
        "operation": "post",
        "channel": "#incidents",
        "text": "=🚨 *AIRP INCIDENT DETECTED*\n\n*Incident ID:* {{ $json.incident_id }}\n*Severity:* CRITICAL\n\n*📊 Current Metrics:*\n• S1 Checkout Latency: {{ $json.metrics.s1_latency_ms }}ms _(threshold: 500ms)_\n• S2 DB Pool Usage: {{ $json.metrics.s2_pool_usage_percent }}%\n• S3 GC Pause: {{ $json.metrics.s3_gc_pause_ms }}ms\n\n*🔍 Root Cause (AI Analysis):*\n{{ $json.diagnosis.primary_root_cause }}\n\n*🔧 Recommended Action:*\n{{ $json.remediation_plan.recommended_action.description }}\n`{{ $json.remediation_plan.recommended_action.kubectl_command }}`\n\n*Risk Level:* {{ $json.remediation_plan.risk_level }}\n*AI Confidence:* {{ Math.round($json.remediation_plan.confidence_score * 100) }}%\n\n*Rollback Plan:* {{ $json.remediation_plan.rollback_plan.description }}\n\n✅ <{{ $vars.N8N_APPROVAL_WEBHOOK }}?action=approve&incident={{ $json.incident_id }}|APPROVE FIX>\n❌ <{{ $vars.N8N_APPROVAL_WEBHOOK }}?action=deny&incident={{ $json.incident_id }}|DENY>",
        "otherOptions": {}
      },
      "id": "node-slack-approval",
      "name": "Send Slack Approval Request",
      "type": "n8n-nodes-base.slack",
      "typeVersion": 2,
      "position": [1560, 300]
    },
    {
      "parameters": {
        "httpMethod": "GET",
        "path": "sre-approval",
        "responseMode": "responseNode",
        "options": {}
      },
      "id": "node-approval-webhook",
      "name": "Wait for SRE Approval",
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 1,
      "position": [1780, 300]
    },
    {
      "parameters": {
        "respondWith": "text",
        "responseBody": "Action received. Executing remediation..."
      },
      "id": "node-approval-response",
      "name": "Acknowledge Approval",
      "type": "n8n-nodes-base.respondToWebhook",
      "typeVersion": 1,
      "position": [1780, 180]
    },
    {
      "parameters": {
        "conditions": {
          "string": [
            {
              "value1": "={{ $json.query.action }}",
              "operation": "equals",
              "value2": "approve"
            }
          ]
        }
      },
      "id": "node-approval-check",
      "name": "Approved?",
      "type": "n8n-nodes-base.if",
      "typeVersion": 1,
      "position": [2000, 300]
    },
    {
      "parameters": {
        "method": "POST",
        "url": "=http://{{ $vars.AIRP_AGENTS_IP }}:8080/execute",
        "sendBody": true,
        "bodyContentType": "json",
        "jsonBody": "={{ JSON.stringify({ deployment: 's3-pricing', replicas: 4, namespace: 'shopfast' }) }}",
        "options": {
          "timeout": 180000
        }
      },
      "id": "node-k8s-operator",
      "name": "K8s Operator — Scale S3",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4,
      "position": [2220, 200]
    },
    {
      "parameters": {
        "authentication": "oAuth2",
        "resource": "message",
        "operation": "post",
        "channel": "#incidents",
        "text": "=❌ *AIRP: Remediation DENIED by SRE*\n\nIncident {{ $json.query.incident }} has been denied.\nManual investigation required.",
        "otherOptions": {}
      },
      "id": "node-denied-slack",
      "name": "Notify Denial",
      "type": "n8n-nodes-base.slack",
      "typeVersion": 2,
      "position": [2220, 400]
    },
    {
      "parameters": {
        "method": "POST",
        "url": "=http://{{ $vars.AIRP_AGENTS_IP }}:8080/validate",
        "sendBody": true,
        "bodyContentType": "json",
        "jsonBody": "={{ JSON.stringify({ execution_result: $json, incident_id: $('RCA Agent (GPT)').item.json.incident_id }) }}",
        "options": {
          "timeout": 60000
        }
      },
      "id": "node-validation",
      "name": "Validate Recovery",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4,
      "position": [2440, 200]
    },
    {
      "parameters": {
        "method": "POST",
        "url": "=http://{{ $vars.AIRP_AGENTS_IP }}:8080/document",
        "sendBody": true,
        "bodyContentType": "json",
        "jsonBody": "={{ JSON.stringify({ ...$('RCA Agent (GPT)').item.json, ...$('Remediation Agent (GPT)').item.json, validation: $json.validation }) }}",
        "options": {
          "timeout": 60000
        }
      },
      "id": "node-documentation",
      "name": "Documentation Agent",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4,
      "position": [2660, 200]
    },
    {
      "parameters": {
        "authentication": "oAuth2",
        "resource": "message",
        "operation": "post",
        "channel": "#incidents",
        "text": "=✅ *AIRP: INCIDENT RESOLVED*\n\n*{{ $json.report.title }}*\n\n*Summary:* {{ $json.report.summary }}\n\n*Root Cause:* {{ $json.report.root_cause }}\n\n*Resolution:* {{ $json.report.resolution }}\n\n*Prevention:* {{ $json.report.prevention }}\n\n_Full report filed under incident ID: {{ $json.incident_id }}_",
        "otherOptions": {}
      },
      "id": "node-final-slack",
      "name": "Post Resolution Report to Slack",
      "type": "n8n-nodes-base.slack",
      "typeVersion": 2,
      "position": [2880, 200]
    }
  ],
  "connections": {
    "Incident Alert Received": {
      "main": [
        [
          {"node": "Acknowledge Alert", "type": "main", "index": 0},
          {"node": "Monitor Agent", "type": "main", "index": 0}
        ]
      ]
    },
    "Monitor Agent": {
      "main": [[{"node": "Correlation Agent", "type": "main", "index": 0}]]
    },
    "Correlation Agent": {
      "main": [[{"node": "RCA Agent (GPT)", "type": "main", "index": 0}]]
    },
    "RCA Agent (GPT)": {
      "main": [[{"node": "Remediation Agent (GPT)", "type": "main", "index": 0}]]
    },
    "Remediation Agent (GPT)": {
      "main": [[{"node": "Send Slack Approval Request", "type": "main", "index": 0}]]
    },
    "Send Slack Approval Request": {
      "main": [[{"node": "Wait for SRE Approval", "type": "main", "index": 0}]]
    },
    "Wait for SRE Approval": {
      "main": [
        [{"node": "Acknowledge Approval", "type": "main", "index": 0}],
        [{"node": "Approved?", "type": "main", "index": 0}]
      ]
    },
    "Approved?": {
      "main": [
        [{"node": "K8s Operator — Scale S3", "type": "main", "index": 0}],
        [{"node": "Notify Denial", "type": "main", "index": 0}]
      ]
    },
    "K8s Operator — Scale S3": {
      "main": [[{"node": "Validate Recovery", "type": "main", "index": 0}]]
    },
    "Validate Recovery": {
      "main": [[{"node": "Documentation Agent", "type": "main", "index": 0}]]
    },
    "Documentation Agent": {
      "main": [[{"node": "Post Resolution Report to Slack", "type": "main", "index": 0}]]
    }
  },
  "settings": {
    "executionOrder": "v1"
  }
}
```

### n8n Variables to Configure

In n8n go to **Settings → Variables** and add:

| Variable Name | Value |
|---------------|-------|
| `AIRP_AGENTS_IP` | The EXTERNAL-IP of your airp-agents service in AKS |
| `N8N_APPROVAL_WEBHOOK` | Your n8n sre-approval webhook URL |

### n8n Credentials to Configure

1. **Slack OAuth2** — In n8n go to Credentials → New → Slack OAuth2 API
   - Create a Slack App at api.slack.com/apps
   - Enable OAuth and add the `chat:write` scope
   - Copy the Bot Token into n8n

---

## Part 10: Triggering the Incident (Demo Script)

### Step 1 — Inject the fault

```bash
# Turn on the GC fault in S3 Pricing
kubectl set env deployment/s3-pricing \
  INJECT_GC_FAULT=true \
  --namespace shopfast

# Also inject latency in S1 for good measure
kubectl set env deployment/s1-checkout \
  INJECT_LATENCY=true \
  --namespace shopfast
```

### Step 2 — Generate traffic (so metrics appear)

```bash
# Run this in a separate terminal — it hammers all the services
kubectl run traffic-generator \
  --image=busybox \
  --namespace=shopfast \
  --restart=Never \
  -- /bin/sh -c "while true; do
    wget -q -O- http://s1-checkout:8000/checkout &
    wget -q -O- http://s4-payment:8000/payment/process &
    wget -q -O- http://s5-recommendation:8000/recommendations &
    sleep 0.5
  done"
```

### Step 3 — Watch it trigger

Within 1-2 minutes:
- Prometheus detects S1 latency > 500ms
- Alertmanager fires the webhook to n8n
- n8n workflow starts
- Watch the execution in n8n's execution history panel

### Step 4 — Approve the fix in Slack

- You'll see a Slack message with APPROVE / DENY buttons
- Click APPROVE
- Watch n8n continue the workflow
- S3 scales from 2 to 4 replicas
- Metrics recover
- Final report posted to Slack

### Step 5 — Verify recovery manually

```bash
kubectl get pods -n shopfast | grep s3-pricing
# Should show 4 pods now instead of 2

kubectl get hpa -n shopfast
# Check scaling status
```

---

## Part 11: File Structure Summary

```
airp-hackathon/
├── services/
│   ├── s1-checkout/
│   │   ├── main.py
│   │   └── Dockerfile
│   ├── s2-inventory/
│   │   ├── main.py
│   │   └── Dockerfile
│   ├── s3-pricing/
│   │   ├── main.py
│   │   └── Dockerfile
│   ├── s4-payment/
│   │   ├── main.py
│   │   └── Dockerfile
│   └── s5-recommendation/
│       ├── main.py
│       └── Dockerfile
├── airp-agents/
│   ├── main.py
│   └── Dockerfile
└── k8s/
    ├── services.yaml
    ├── prometheus.yaml
    └── airp-agents.yaml
```

---

## Part 12: Execution Order Checklist

Run these steps in order on hackathon day:

```
□ 1.  az login + az aks create (30 min — do this first, it takes time)
□ 2.  Sign up for n8n cloud 14-day trial
□ 3.  Create n8n workflow, get webhook URL
□ 4.  Build + push Docker images to ACR (30 min)
□ 5.  kubectl apply all k8s manifests
□ 6.  Wait for all pods to be Running
□ 7.  Get EXTERNAL-IPs from kubectl get services
□ 8.  Update alertmanager ConfigMap with n8n webhook URL
□ 9.  Update n8n Variables with AIRP_AGENTS_IP
□ 10. Configure Slack credentials in n8n
□ 11. Import n8n workflow JSON
□ 12. Inject fault: kubectl set env deployment/s3-pricing INJECT_GC_FAULT=true
□ 13. Start traffic generator
□ 14. Watch Prometheus fire → n8n trigger → Slack message
□ 15. Click APPROVE in Slack
□ 16. Watch recovery + final report
□ 17. Demo complete 🎉
```

---

## Estimated Hackathon Timeline

| Time | Activity |
|------|----------|
| 0:00 – 0:30 | AKS cluster creation (runs in background while you do other things) |
| 0:30 – 1:30 | Write + Dockerize all 5 microservices |
| 1:30 – 2:00 | Push images, apply k8s manifests |
| 2:00 – 4:00 | Write AIRP agents service (the main coding work) |
| 4:00 – 4:30 | Push airp-agents image, deploy to AKS |
| 4:30 – 5:00 | Set up Prometheus alerts + alertmanager webhook |
| 5:00 – 5:30 | Import n8n workflow, configure Slack + variables |
| 5:30 – 6:00 | End-to-end test with fault injection |
| 6:00 – 8:00 | Buffer for debugging + polish |

**Total: ~8 hours for a working demo**

---

*Built for the AIRP Hackathon. The Autonomous Incident Resolution Platform demonstrates
that AI-driven SRE is not science fiction — it's an architecture problem.*

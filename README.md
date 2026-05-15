# AIRP V2 - Autonomous Incident Resolution Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)

> **AI-powered autonomous incident resolution for Kubernetes microservices**

AIRP V2 is a production-ready platform that automatically detects, diagnoses, and resolves incidents in your Kubernetes cluster using AI-powered root cause analysis and config-driven remediation strategies.

---

## 🚀 Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/your-org/airp-v2.git
cd airp-v2

# 2. Follow the complete setup guide
cat docs/SETUP_GUIDE.md

# 3. Deploy to your AKS cluster
./scripts/setup-cluster.sh
./scripts/deploy-airp.sh

# 4. Test with example services
./scripts/deploy-examples.sh
./scripts/test-incident.sh
```

**Full setup takes ~45 minutes.** See [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md) for detailed instructions.

---

## ✨ Key Features

### 🔍 **Dynamic Service Discovery**
- Auto-discovers services from Kubernetes labels
- No hardcoded service names or architectures
- Supports unlimited services

### 🤖 **AI-Powered Root Cause Analysis**
- GPT-4o analyzes incidents with generic SRE knowledge
- Multi-hypothesis testing
- Historical incident context for improved accuracy
- Handles 9+ incident types: memory leaks, CPU spikes, DB saturation, network issues, cascading failures, etc.

### ⚙️ **Config-Driven Remediation**
- 7+ remediation actions defined in YAML
- No code changes needed for new actions
- Risk assessment and rollback plans included
- Actions: scale, restart, resource limits, rollback, node operations

### 📊 **Intelligent Anomaly Detection**
- Baseline learning with Z-score analysis
- Collects RED, USE, and custom metrics
- Dynamic threshold adjustment
- Weighted anomaly scoring

### 🧠 **Learning & Improvement**
- PostgreSQL stores incident history
- Similar incident retrieval for context
- Improves diagnosis accuracy over time
- Tracks outcomes and recovery times

### 🔐 **Production-Ready**
- Complete RBAC setup
- Command validation and safety checks
- Environment-specific configurations
- Comprehensive monitoring and logging

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Your Kubernetes Cluster                     │
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │  Your Services (labeled: airp.monitored=true)      │     │
│  └────────────────────────────────────────────────────┘     │
│                          ↓ metrics                          │
│  ┌────────────────────────────────────────────────────┐     │
│  │  Prometheus + Alertmanager                         │     │
│  └────────────────────────────────────────────────────┘     │
│                          ↓ alerts                           │
│  ┌────────────────────────────────────────────────────┐     │
│  │  AIRP Agent Service (7 AI Agents)                  │     │
│  │  • Monitor  • Correlate  • RCA  • Remediate        │     │
│  │  • Execute  • Validate   • Document                │     │
│  └────────────────────────────────────────────────────┘     │
│                          ↑ orchestrates                     │
│  ┌────────────────────────────────────────────────────┐     │
│  │  PostgreSQL (incident history & baselines)         │     │
│  └────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
                          ↓ workflow
              ┌──────────────────────────┐
              │      n8n Cloud           │
              │  (orchestration)         │
              └──────────────────────────┘
                          ↓ approval
                   ┌─────────────┐
                   │   Slack     │
                   │  (human)    │
                   └─────────────┘
```

---

## 📁 Project Structure

```
airp-v2/
├── agents/              # AIRP Agent Service (FastAPI)
├── workflows/           # n8n workflow definitions
├── kubernetes/          # K8s manifests for AIRP platform
├── scripts/             # Automation scripts
├── examples/            # Demo services & integration templates
├── docs/                # Complete documentation
└── archive/             # Legacy V1 files
```

See [Project Structure](docs/SETUP_GUIDE.md#project-structure) for details.

---

## 🎯 How It Works

### 1. **Incident Detection**
Prometheus detects anomalies (high latency, errors, resource saturation) and fires alerts to n8n webhook.

### 2. **Autonomous Resolution Flow**
```
Alert → Monitor Agent (discover & score all services)
     → Correlation Agent (build dependency graph)
     → RCA Agent (GPT-4o root cause analysis)
     → Remediation Agent (select best action from config)
     → Human Approval (Slack notification)
     → Execution Agent (run kubectl command)
     → Validation Agent (confirm recovery)
     → Documentation Agent (write report & learn)
```

### 3. **Continuous Learning**
Every incident is stored in PostgreSQL. Future incidents benefit from historical context, improving diagnosis accuracy over time.

---

## 🔧 Configuration

All behavior is controlled via `agents/config/airp.yaml`:

```yaml
platform:
  risk_tolerance: "medium"           # low | medium | high
  min_confidence_to_act: 0.75        # AI confidence threshold

anomaly_detection:
  affected_threshold: 2.0            # Anomaly score to flag service
  root_cause_threshold: 4.0          # Score to be root cause candidate

remediation_actions:
  scale_up:
    applicable_to: ["high_memory", "high_cpu", "gc_pauses"]
    risk: "low"
    kubectl_template: "kubectl scale deployment/{service} --replicas={value}"
```

**No code changes needed** - just edit YAML and restart agents.

See [Configuration Guide](docs/CONFIGURATION.md) for all options.

---

## 🚦 Prerequisites

- **Azure AKS cluster** (or any Kubernetes 1.24+)
- **OpenAI API key** (GPT-4o access)
- **n8n Cloud account** (free tier works)
- **Slack workspace** (for approvals)
- **kubectl, helm, docker** installed locally

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [Setup Guide](docs/SETUP_GUIDE.md) | Complete installation instructions |
| [Architecture](docs/ARCHITECTURE.md) | System design and agent details |
| [Configuration](docs/CONFIGURATION.md) | Config reference and customization |
| [Integration Guide](docs/INTEGRATION_GUIDE.md) | How to integrate YOUR services |
| [API Reference](docs/API.md) | Agent API endpoints |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Common issues and solutions |

---

## 🎓 Example Services

The `examples/` directory includes:

- **Sample Microservices** (S1-S5): Demo e-commerce services for testing
- **Integration Templates**: How to label and configure YOUR services
- **Custom Actions**: Example custom remediation actions
- **Custom Metrics**: Example business metrics

Deploy examples:
```bash
./scripts/deploy-examples.sh
```

---

## 🧪 Testing

```bash
# Test service discovery
curl http://$AIRP_IP:8080/discover

# Trigger a test incident
./scripts/test-incident.sh

# Watch the workflow in n8n
# Check Slack for approval request
# Verify remediation in Kubernetes
```

---

## 🤝 Integrating Your Services

### Step 1: Label Your Deployments
```yaml
metadata:
  labels:
    airp.monitored: "true"  # Required for discovery
  annotations:
    airp.io/depends-on: "service-a,service-b"  # Optional
```

### Step 2: Expose Prometheus Metrics
```python
# Your service must expose /metrics endpoint
# Minimum: http_request_duration_seconds, http_requests_total
```

### Step 3: Deploy
```bash
kubectl apply -f your-service.yaml
```

AIRP will auto-discover and monitor your service within 5 minutes.

See [Integration Guide](docs/INTEGRATION_GUIDE.md) for complete instructions.

---

## 🔒 Security

- **RBAC**: Least-privilege service account
- **Secrets**: Never commit actual secrets (use `.example` files)
- **Command Validation**: Blocks destructive operations
- **Approval Gates**: Human approval required for high-risk actions
- **Audit Trail**: All actions logged to PostgreSQL

---

## 📊 Monitoring AIRP Itself

AIRP exposes its own metrics:
```bash
# Health check
curl http://$AIRP_IP:8080/health

# View loaded config
curl http://$AIRP_IP:8080/config

# Test discovery
curl http://$AIRP_IP:8080/discover
```

---

## 🐛 Troubleshooting

**AIRP can't discover services?**
```bash
kubectl get deployments -l airp.monitored=true
kubectl auth can-i get deployments --as=system:serviceaccount:shopfast:airp-agent-sa
```

**Prometheus not scraping?**
```bash
kubectl port-forward svc/prometheus-kube-prometheus-prometheus 9090:9090
# Open http://localhost:9090/targets
```

See [Troubleshooting Guide](docs/TROUBLESHOOTING.md) for more.

---

## 🗺️ Roadmap

- [ ] Support for AWS EKS and GCP GKE
- [ ] Grafana dashboard for AIRP metrics
- [ ] Slack bot for interactive commands
- [ ] Multi-cluster support
- [ ] Cost optimization recommendations
- [ ] Integration with PagerDuty, Jira, ServiceNow
- [ ] Custom ML models for anomaly detection

---

## 🤝 Contributing

Contributions welcome! Please read [CONTRIBUTING.md](docs/CONTRIBUTING.md) first.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

---

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file.

---

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/), [OpenAI](https://openai.com/), and [n8n](https://n8n.io/)
- Inspired by Google SRE practices
- Thanks to the Kubernetes and Prometheus communities

---

## 📞 Support

- **Documentation**: [docs/](docs/)
- **Issues**: [GitHub Issues](https://github.com/your-org/airp-v2/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/airp-v2/discussions)

---

**⭐ Star this repo if AIRP helps your team!**

Made with ❤️ by the AIRP Team
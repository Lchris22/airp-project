# AIRP V2 - Project Structure

This document provides a complete overview of the project organization.

## 📁 Directory Tree

```
airp-v2/
├── README.md                          # Project overview & quick start
├── LICENSE                            # MIT License
├── .gitignore                         # Git ignore rules
├── CHANGELOG.md                       # Version history & changes
├── PROJECT_STRUCTURE.md               # This file
│
├── docs/                              # 📚 Documentation
│   ├── SETUP_GUIDE.md                 # Complete setup instructions
│   ├── ARCHITECTURE.md                # System design (to be created)
│   ├── CONFIGURATION.md               # Config reference (to be created)
│   ├── INTEGRATION_GUIDE.md           # How to integrate services (to be created)
│   ├── API.md                         # Agent API docs (to be created)
│   ├── TROUBLESHOOTING.md             # Common issues (to be created)
│   └── CONTRIBUTING.md                # Contribution guidelines (to be created)
│
├── agents/                            # 🤖 AIRP Agent Service
│   ├── README.md                      # Agent documentation
│   ├── Dockerfile                     # Container image definition
│   ├── requirements.txt               # Python dependencies
│   ├── main.py                        # FastAPI application (7 agents)
│   ├── config/
│   │   ├── airp.yaml                  # Main configuration
│   │   ├── airp.dev.yaml              # Dev overrides (to be created)
│   │   └── airp.prod.yaml             # Production overrides (to be created)
│   └── tests/
│       ├── test_monitor.py            # Unit tests (to be created)
│       ├── test_correlation.py        # Unit tests (to be created)
│       └── test_remediation.py        # Unit tests (to be created)
│
├── workflows/                         # 🔄 n8n Workflows
│   ├── README.md                      # Workflow documentation
│   ├── airp-incident-resolution.json  # Main workflow (fixed version)
│   └── screenshots/
│       └── workflow-overview.png      # Visual diagram (to be added)
│
├── kubernetes/                        # ☸️ K8s Manifests
│   ├── README.md                      # K8s deployment docs (to be created)
│   ├── namespace.yaml                 # Namespace definition (to be created)
│   ├── agents/
│   │   ├── deployment.yaml            # Agent deployment (to be created)
│   │   ├── service.yaml               # Agent service (to be created)
│   │   ├── configmap.yaml             # Config as ConfigMap (to be created)
│   │   ├── secrets.yaml.example       # Secrets template (to be created)
│   │   └── rbac.yaml                  # RBAC permissions (to be created)
│   ├── database/
│   │   ├── postgres-deployment.yaml   # PostgreSQL (to be created)
│   │   ├── postgres-service.yaml      # DB service (to be created)
│   │   └── postgres-pvc.yaml          # Persistent volume (to be created)
│   └── monitoring/
│       ├── prometheus-values.yaml     # Helm values (to be created)
│       ├── alertmanager-config.yaml   # Alert config (to be created)
│       ├── prometheus-rules.yaml      # Alert rules (to be created)
│       └── servicemonitor.yaml        # Service monitor (to be created)
│
├── scripts/                           # 🔧 Automation Scripts
│   ├── setup-cluster.sh               # AKS cluster setup (to be created)
│   ├── deploy-airp.sh                 # Deploy AIRP platform (to be created)
│   ├── deploy-examples.sh             # Deploy demo services (to be created)
│   ├── test-incident.sh               # Trigger test incident (to be created)
│   ├── cleanup.sh                     # Remove everything (to be created)
│   └── backup-db.sh                   # Backup incident history (to be created)
│
├── examples/                          # 📝 Examples & Templates
│   ├── README.md                      # Examples documentation
│   ├── sample-services/               # Demo microservices
│   │   ├── s1-checkout/               # Checkout service (to be created)
│   │   ├── s2-inventory/              # Inventory service (to be created)
│   │   ├── s3-pricing/                # Pricing service (to be created)
│   │   ├── s4-payment/                # Payment service (to be created)
│   │   └── s5-recommendation/         # Recommendation service (to be created)
│   ├── custom-actions/                # Custom remediation examples
│   │   └── delayed-restart.yaml       # Example action (to be created)
│   ├── custom-metrics/                # Custom metrics examples
│   │   └── business-metrics.yaml      # Example metrics (to be created)
│   └── integration-templates/         # Templates for YOUR services
│       ├── service-template.yaml      # Complete K8s template ✅
│       ├── metrics-template.py        # Metrics code example (to be created)
│       └── dependency-annotations.yaml # Dependency examples (to be created)
│
└── archive/                           # 📦 Legacy Files
    ├── v1-hackathon/
    │   ├── AIRP_HACKATHON_PLAN.md     # Original V1 plan ✅
    │   └── airpAgent-v1.json          # Original V1 workflow ✅
    └── MIGRATION_NOTES.md             # V1→V2 migration (to be created)
```

## 📊 File Status Legend

- ✅ **Complete** - File exists and is ready to use
- 🔄 **In Progress** - File exists but needs updates
- ⏳ **To Be Created** - Planned but not yet created

## 🎯 Core Components

### 1. Agent Service (`agents/`)
The heart of AIRP - a FastAPI application with 7 AI-powered agents:
- **Monitor Agent** - Service discovery & metric collection
- **Correlation Agent** - Dependency graph building
- **RCA Agent** - AI-powered root cause analysis
- **Remediation Agent** - Action selection & planning
- **Execution Agent** - Safe kubectl execution
- **Validation Agent** - Recovery confirmation
- **Documentation Agent** - Report writing & learning

### 2. Workflows (`workflows/`)
n8n workflow definitions that orchestrate the agent pipeline:
- Receives alerts from Prometheus/Alertmanager
- Calls agents in sequence
- Manages human approval via Slack
- Handles success/failure paths

### 3. Kubernetes Manifests (`kubernetes/`)
Complete K8s deployment configuration:
- Agent service deployment with RBAC
- PostgreSQL for incident history
- Prometheus + Alertmanager setup
- ServiceMonitors for metric collection

### 4. Examples (`examples/`)
Demo services and integration templates:
- 5 sample microservices (S1-S5) for testing
- Complete integration templates for YOUR services
- Custom action and metric examples

### 5. Documentation (`docs/`)
Comprehensive guides:
- Setup instructions (complete ✅)
- Architecture details (planned)
- Configuration reference (planned)
- Integration guide (planned)
- API documentation (planned)
- Troubleshooting (planned)

## 🔑 Key Files

| File | Purpose | Status |
|------|---------|--------|
| `README.md` | Project overview, quick start | ✅ Complete |
| `agents/main.py` | Core agent logic (1274 lines) | ✅ Complete |
| `agents/config/airp.yaml` | All behavior configuration | ✅ Complete |
| `workflows/airp-incident-resolution.json` | n8n workflow | ✅ Fixed |
| `docs/SETUP_GUIDE.md` | Complete setup instructions | ✅ Complete |
| `examples/integration-templates/service-template.yaml` | Integration template | ✅ Complete |

## 📦 Dependencies

### Python (agents/)
- FastAPI 0.104.1 - Web framework
- OpenAI 1.3.5 - GPT-4o integration
- psycopg2-binary 2.9.9 - PostgreSQL client
- pyyaml 6.0.1 - Config parsing
- requests 2.31.0 - HTTP client

### Infrastructure
- Kubernetes 1.24+ - Container orchestration
- PostgreSQL 14+ - Incident history storage
- Prometheus - Metrics collection
- Alertmanager - Alert routing
- n8n Cloud - Workflow orchestration

### External Services
- OpenAI API (GPT-4o) - AI analysis
- Slack - Human approvals & notifications
- Azure AKS - Kubernetes cluster (or any K8s)

## 🚀 Getting Started

1. **Read the README**: Start with `README.md` for overview
2. **Follow Setup Guide**: Complete instructions in `docs/SETUP_GUIDE.md`
3. **Deploy AIRP**: Use scripts in `scripts/` (when created)
4. **Test with Examples**: Deploy sample services from `examples/`
5. **Integrate Your Services**: Use templates in `examples/integration-templates/`

## 🔄 Development Workflow

```bash
# 1. Make changes to agents/main.py or agents/config/airp.yaml
vim agents/main.py

# 2. Test locally
cd agents
pip install -r requirements.txt
uvicorn main:app --reload

# 3. Build Docker image
docker build -t your-registry/airp-agents:v2 .

# 4. Push to registry
docker push your-registry/airp-agents:v2

# 5. Update K8s deployment
kubectl set image deployment/airp-agents airp-agents=your-registry/airp-agents:v2 -n shopfast

# 6. Verify
kubectl rollout status deployment/airp-agents -n shopfast
```

## 📝 Next Steps

### Immediate (Required for Production)
1. Create Kubernetes manifests in `kubernetes/`
2. Create deployment scripts in `scripts/`
3. Add unit tests in `agents/tests/`
4. Create remaining documentation in `docs/`

### Short-term (Enhance Usability)
1. Create sample services in `examples/sample-services/`
2. Add custom action examples
3. Add custom metric examples
4. Create workflow screenshots

### Long-term (Future Enhancements)
1. Add Grafana dashboards
2. Create Slack bot
3. Add more integration examples
4. Enhance ML capabilities

## 🤝 Contributing

See `docs/CONTRIBUTING.md` (to be created) for contribution guidelines.

## 📄 License

MIT License - see `LICENSE` file.

---

**Last Updated:** 2026-05-15
**Version:** 2.0.0
**Status:** Production-Ready Core, Examples & Scripts Pending
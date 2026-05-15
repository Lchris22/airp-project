# AIRP Agent Service

The core AI-powered agent service that performs autonomous incident resolution.

## Overview

This FastAPI application contains 7 specialized agents that work together to detect, diagnose, and resolve incidents:

1. **Monitor Agent** - Discovers services and collects metrics
2. **Correlation Agent** - Builds dependency graphs and identifies affected services
3. **RCA Agent** - AI-powered root cause analysis using GPT-4o
4. **Remediation Agent** - Selects best remediation action from config
5. **Execution Agent** - Safely executes kubectl commands
6. **Validation Agent** - Confirms recovery after remediation
7. **Documentation Agent** - Writes incident reports and learns from outcomes

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export OPENAI_API_KEY="your-key"
export PROMETHEUS_URL="http://localhost:9090"
export DB_HOST="localhost"
export DB_PASSWORD="airp123"
export AIRP_CONFIG_PATH="config/airp.yaml"

# Run the service
uvicorn main:app --reload --port 8080
```

### Docker Build

```bash
# Build image
docker build -t your-registry/airp-agents:v2 .

# Run locally
docker run -p 8080:8080 \
  -e OPENAI_API_KEY="your-key" \
  -e PROMETHEUS_URL="http://prometheus:9090" \
  -v $(pwd)/config:/config \
  your-registry/airp-agents:v2
```

### Deploy to Kubernetes

```bash
# See ../kubernetes/agents/ for manifests
kubectl apply -f ../kubernetes/agents/
```

## Configuration

All behavior is controlled by `config/airp.yaml`. See [Configuration Guide](../docs/CONFIGURATION.md).

### Environment-Specific Configs

- `config/airp.yaml` - Base configuration
- `config/airp.dev.yaml` - Development overrides
- `config/airp.prod.yaml` - Production overrides

Set `AIRP_CONFIG_PATH` to choose which config to load.

## API Endpoints

### Agent Endpoints

- `POST /monitor` - Discover services and collect metrics
- `POST /correlate` - Build dependency graph
- `POST /rca` - Perform root cause analysis
- `POST /remediate` - Generate remediation plan
- `POST /execute` - Execute kubectl command
- `POST /validate` - Validate recovery
- `POST /document` - Write incident report

### Utility Endpoints

- `GET /health` - Health check
- `GET /config` - View loaded configuration
- `GET /discover` - Manually trigger service discovery

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    main.py (FastAPI)                     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Monitor    │→ │ Correlation  │→ │     RCA      │  │
│  │    Agent     │  │    Agent     │  │   (GPT-4o)   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│         ↓                                      ↓         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Remediation  │→ │  Execution   │→ │ Validation   │  │
│  │   (GPT-4o)   │  │    Agent     │  │    Agent     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                              ↓           │
│                                     ┌──────────────┐    │
│                                     │Documentation │    │
│                                     │   (GPT-4o)   │    │
│                                     └──────────────┘    │
│                                                          │
├─────────────────────────────────────────────────────────┤
│  Core Modules:                                          │
│  • config.py - Load and parse YAML config              │
│  • prometheus.py - Query Prometheus                     │
│  • kubernetes.py - kubectl operations                   │
│  • database.py - PostgreSQL for history                 │
│  • ai.py - OpenAI GPT integration                       │
└─────────────────────────────────────────────────────────┘
```

## Dependencies

- **FastAPI** - Web framework
- **OpenAI** - GPT-4o for AI analysis
- **psycopg2** - PostgreSQL client
- **requests** - HTTP client for Prometheus
- **pyyaml** - YAML config parsing
- **pydantic** - Data validation

See `requirements.txt` for versions.

## Testing

```bash
# Run unit tests
pytest tests/

# Test individual agents
pytest tests/test_monitor.py -v

# Integration tests (requires running cluster)
pytest tests/integration/ -v
```

## Database Schema

### incidents table
Stores complete incident history for learning.

```sql
CREATE TABLE incidents (
    id SERIAL PRIMARY KEY,
    incident_id TEXT UNIQUE,
    timestamp TIMESTAMPTZ,
    alert_name TEXT,
    affected_services JSONB,
    root_cause TEXT,
    root_cause_service TEXT,
    action_taken TEXT,
    action_type TEXT,
    confidence FLOAT,
    outcome TEXT,
    recovery_time_s INTEGER,
    full_context JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### service_baselines table
Stores learned baselines for anomaly detection.

```sql
CREATE TABLE service_baselines (
    id SERIAL PRIMARY KEY,
    service TEXT,
    metric TEXT,
    baseline FLOAT,
    stddev FLOAT,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(service, metric)
);
```

## Extending the Agents

### Adding a New Remediation Action

Edit `config/airp.yaml`:

```yaml
remediation_actions:
  your_new_action:
    description: "What this does"
    applicable_to: ["incident_type"]
    risk: "low"
    reversible: true
    kubectl_template: "kubectl your-command {service}"
    rollback_template: "kubectl rollback {service}"
```

No code changes needed! GPT will automatically use it.

### Adding Custom Metrics

Edit `config/airp.yaml`:

```yaml
prometheus:
  metric_categories:
    CUSTOM:
      - "your_metric_name"
      - "another_metric{label='value'}"
```

### Adding a New Agent

1. Create new endpoint in `main.py`
2. Follow the pattern of existing agents
3. Update n8n workflow to call your agent
4. Document in API.md

## Performance

- **Service Discovery**: ~2-5 seconds for 50 services
- **Metric Collection**: ~1 second per service
- **RCA Analysis**: ~5-10 seconds (GPT-4o)
- **Remediation Planning**: ~3-5 seconds (GPT-4o)
- **Total Resolution Time**: ~30-60 seconds (excluding human approval)

## Security

- **RBAC**: Service account with minimal permissions
- **Command Validation**: Blocks destructive operations
- **Secrets**: Never log sensitive data
- **API Keys**: Stored in Kubernetes secrets

## Troubleshooting

### Agent can't connect to Prometheus
```bash
# Check Prometheus URL
echo $PROMETHEUS_URL

# Test connectivity
curl $PROMETHEUS_URL/api/v1/query?query=up
```

### Database connection fails
```bash
# Check credentials
echo $DB_HOST $DB_USER

# Test connection
psql -h $DB_HOST -U $DB_USER -d $DB_NAME
```

### GPT API errors
```bash
# Check API key
echo $OPENAI_API_KEY | cut -c1-10

# Test API
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

## Monitoring

The agent service exposes metrics at `/metrics` (Prometheus format):

- `airp_incidents_total` - Total incidents processed
- `airp_resolutions_total` - Successful resolutions
- `airp_agent_duration_seconds` - Time per agent
- `airp_gpt_calls_total` - GPT API calls
- `airp_kubectl_executions_total` - kubectl commands run

## Contributing

See [CONTRIBUTING.md](../docs/CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](../LICENSE)
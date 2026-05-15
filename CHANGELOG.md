# Changelog

All notable changes to the AIRP project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-05-15

### 🎉 Major Release - Complete Rewrite

AIRP V2 is a complete rewrite transforming the platform from a single-scenario demo into a production-ready autonomous incident resolution system.

### Added

#### Core Features
- **Dynamic Service Discovery** - Auto-discovers services from Kubernetes labels, no hardcoded service names
- **AI-Powered RCA** - GPT-4o with generic SRE knowledge, handles 9+ incident types
- **Config-Driven Remediation** - 7+ remediation actions defined in YAML, extensible without code changes
- **Intelligent Anomaly Detection** - Baseline learning with Z-score analysis, weighted scoring
- **Historical Learning** - PostgreSQL stores incident history, improves diagnosis over time
- **Multi-Environment Support** - Separate configs for dev/staging/production

#### Agent System
- **Monitor Agent** - Discovers services, collects all available metrics, scores anomalies
- **Correlation Agent** - Builds dependency graphs dynamically from OpenTelemetry/annotations
- **RCA Agent** - Multi-hypothesis testing with historical context injection
- **Remediation Agent** - Selects best action from config library with risk assessment
- **Execution Agent** - Safe kubectl execution with command validation
- **Validation Agent** - Confirms recovery with configurable retry logic
- **Documentation Agent** - Writes professional incident reports, saves to history

#### Configuration
- Complete YAML-based configuration system (`agents/config/airp.yaml`)
- Environment variable expansion in config
- Customizable thresholds, weights, and risk tolerance
- Extensible action library
- Plugin system for integrations (Loki, Jaeger, PagerDuty, Jira)

#### Infrastructure
- Production-ready Dockerfile with health checks
- Complete Kubernetes manifests with RBAC
- PostgreSQL for incident history and baselines
- Prometheus + Alertmanager integration
- n8n workflow orchestration

#### Documentation
- Comprehensive setup guide (docs/SETUP_GUIDE.md)
- Architecture documentation
- Integration guide for YOUR services
- API reference
- Troubleshooting guide
- Example services and templates

#### Examples
- 5 demo microservices (S1-S5) simulating e-commerce platform
- Integration templates for labeling and configuring services
- Custom action examples
- Custom metrics examples

### Changed

#### Breaking Changes
- **Service Discovery**: No longer hardcoded to S1-S5, uses Kubernetes labels
- **Metrics Collection**: Now collects ALL available metrics, not just 5 predefined ones
- **Dependency Graph**: Built dynamically, not from static map
- **Remediation**: Actions selected by AI from config, not hardcoded to scale S3
- **Configuration**: Moved from code to YAML files

#### Improvements
- **Scalability**: Supports unlimited services vs. 5 hardcoded
- **Flexibility**: Handles any incident type vs. one scenario
- **Accuracy**: Historical context improves diagnosis over time
- **Safety**: Command validation, risk assessment, rollback plans
- **Maintainability**: Config changes don't require code deployment

### Removed
- Hardcoded service names (S1-S5)
- Hardcoded dependency map
- Hardcoded Prometheus queries
- Hardcoded remediation action (scale S3)
- Scenario-specific GPT prompts

### Fixed
- JSON formatting issues in n8n workflow
- Multi-line string handling in workflow
- Missing commas between node objects
- Malformed options objects

### Security
- RBAC with least-privilege service account
- Command validation blocks destructive operations
- Secrets management with .example templates
- Audit trail in PostgreSQL

### Performance
- Service discovery: ~2-5s for 50 services
- Metric collection: ~1s per service
- RCA analysis: ~5-10s (GPT-4o)
- Total resolution: ~30-60s (excluding human approval)

---

## [1.0.0] - 2024-XX-XX

### Initial Release - Hackathon Version

- Single-scenario demo for "Checkout Latency Spiral"
- Hardcoded 5 microservices (S1-S5)
- Fixed dependency map
- Predetermined remediation (scale S3 to 4 replicas)
- Scenario-specific GPT prompts
- Basic n8n workflow
- Prometheus + Alertmanager integration

---

## Migration Guide: V1 → V2

### For Existing V1 Users

1. **Backup your data** (if any)
2. **Review new configuration** in `agents/config/airp.yaml`
3. **Label your services** with `airp.monitored: "true"`
4. **Update n8n workflow** - import new version
5. **Deploy new agents** - use updated manifests
6. **Test with examples** before production

See `archive/v1-hackathon/MIGRATION_NOTES.md` for detailed migration steps.

---

## Roadmap

### [2.1.0] - Planned
- [ ] Grafana dashboards for AIRP metrics
- [ ] Slack bot for interactive commands
- [ ] Cost optimization recommendations
- [ ] Enhanced ML-based anomaly detection

### [2.2.0] - Planned
- [ ] Multi-cluster support
- [ ] AWS EKS and GCP GKE support
- [ ] Advanced trace analysis integration
- [ ] Custom ML models for prediction

### [3.0.0] - Future
- [ ] Predictive incident prevention
- [ ] Auto-tuning of thresholds
- [ ] Multi-cloud support
- [ ] Advanced chaos engineering integration

---

## Contributing

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for how to contribute to AIRP.

## License

MIT License - see [LICENSE](LICENSE)
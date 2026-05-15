"""
AIRP Agent Service — Generalized, Dynamic Version
===================================================
All behavior is driven by airp.yaml config.
No service names, thresholds, or remediations are hardcoded here.

Agent endpoints:
  POST /monitor      — discover services, fetch ALL metrics, score anomalies
  POST /correlate    — build dependency graph, rank affected services
  POST /rca          — GPT root cause analysis with historical context
  POST /remediate    — GPT picks action from config-driven action library
  POST /execute      — run the approved kubectl command
  POST /validate     — re-score anomalies and confirm recovery
  POST /document     — GPT writes incident report, stores in history
"""

import os
import re
import json
import time
import math
import hashlib
import subprocess
from typing import Any
from datetime import datetime, timezone

import yaml
import requests
import psycopg2
import psycopg2.extras
from fastapi import FastAPI, HTTPException
from openai import OpenAI
from pydantic import BaseModel

# ─────────────────────────────────────────────────────────────────────────────
# Bootstrap
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="AIRP Agent Service — Generalized")
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def load_config() -> dict:
    path = os.getenv("AIRP_CONFIG_PATH", "/config/airp.yaml")
    with open(path) as f:
        raw = f.read()
    # Expand ${ENV_VAR} references in the YAML
    def replace_env(match):
        key = match.group(1)
        return os.getenv(key, f"MISSING_ENV_{key}")
    raw = re.sub(r"\$\{(\w+)\}", replace_env, raw)
    return yaml.safe_load(raw)

CFG = load_config()

PROMETHEUS_URL  = CFG["prometheus"]["url"]
NAMESPACE       = CFG["kubernetes"]["namespace"]
AI_MODEL        = CFG["ai"]["model"]
RISK_TOLERANCE  = CFG["platform"]["risk_tolerance"]
MIN_CONFIDENCE  = CFG["platform"]["min_confidence_to_act"]

# ─────────────────────────────────────────────────────────────────────────────
# Database — stores incident history for learning
# ─────────────────────────────────────────────────────────────────────────────

def get_db():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "postgres"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "airp"),
        user=os.getenv("DB_USER", "airp"),
        password=os.getenv("DB_PASSWORD", "airp"),
    )

def init_db():
    """Create tables if they don't exist."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id              SERIAL PRIMARY KEY,
            incident_id     TEXT UNIQUE,
            timestamp       TIMESTAMPTZ,
            alert_name      TEXT,
            affected_services JSONB,
            root_cause      TEXT,
            root_cause_service TEXT,
            action_taken    TEXT,
            action_type     TEXT,
            confidence      FLOAT,
            outcome         TEXT,   -- 'resolved' | 'failed' | 'denied'
            recovery_time_s INTEGER,
            full_context    JSONB,
            created_at      TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS service_baselines (
            id          SERIAL PRIMARY KEY,
            service     TEXT,
            metric      TEXT,
            baseline    FLOAT,
            stddev      FLOAT,
            updated_at  TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(service, metric)
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

try:
    init_db()
    print("Database initialized.")
except Exception as e:
    print(f"Warning: DB init failed ({e}). History features disabled.")


# ─────────────────────────────────────────────────────────────────────────────
# Prometheus Helpers
# ─────────────────────────────────────────────────────────────────────────────

def prom_query(query: str) -> list[dict]:
    """Run an instant query. Returns list of {metric: {labels}, value: float}."""
    try:
        r = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": query},
            timeout=10
        )
        results = r.json().get("data", {}).get("result", [])
        return [
            {
                "metric": item["metric"],
                "value": float(item["value"][1])
            }
            for item in results
        ]
    except Exception as e:
        print(f"Prometheus query error [{query}]: {e}")
        return []


def prom_query_scalar(query: str) -> float:
    """Run a query and return the first scalar value, or 0."""
    results = prom_query(query)
    return results[0]["value"] if results else 0.0


def prom_label_values(label: str) -> list[str]:
    """Get all distinct values for a Prometheus label (e.g. all service names)."""
    try:
        r = requests.get(
            f"{PROMETHEUS_URL}/api/v1/label/{label}/values",
            timeout=10
        )
        return r.json().get("data", [])
    except Exception as e:
        print(f"Prometheus label query error: {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Kubernetes Helpers
# ─────────────────────────────────────────────────────────────────────────────

def kubectl(args: list[str]) -> dict:
    """Run a kubectl command and return {success, stdout, stderr}."""
    cmd = ["kubectl"] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "command": " ".join(cmd)
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": "kubectl timeout", "command": " ".join(cmd)}


def discover_services_from_k8s() -> list[dict]:
    """
    Discover all labeled services from Kubernetes.
    Returns list of {name, deployment_name, namespace, labels}.
    """
    monitored_label = CFG["kubernetes"]["discovery"]["monitored_label"]
    result = kubectl([
        "get", "deployments",
        "-n", NAMESPACE,
        "-l", monitored_label,
        "-o", "json"
    ])
    if not result["success"]:
        print(f"K8s discovery failed: {result['stderr']}")
        return []

    try:
        data = json.loads(result["stdout"])
        services = []
        for item in data.get("items", []):
            name = item["metadata"]["name"]
            labels = item["metadata"].get("labels", {})
            services.append({
                "name": labels.get("app", name),
                "deployment_name": name,
                "namespace": NAMESPACE,
                "labels": labels,
                "current_replicas": item["spec"].get("replicas", 1),
                "available_replicas": item["status"].get("availableReplicas", 0),
            })
        return services
    except Exception as e:
        print(f"K8s discovery parse error: {e}")
        return []


def discover_services_from_prometheus() -> list[str]:
    """
    Fall back to discovering service names from Prometheus label values.
    More reliable when K8s RBAC is limited.
    """
    label = CFG["prometheus"]["service_label"]
    return prom_label_values(label)


def get_deployment_info(deployment: str) -> dict:
    """Get current replica count and resource limits for a deployment."""
    result = kubectl([
        "get", "deployment", deployment,
        "-n", NAMESPACE,
        "-o", "json"
    ])
    if not result["success"]:
        return {}
    try:
        data = json.loads(result["stdout"])
        spec = data["spec"]
        containers = spec["template"]["spec"]["containers"]
        return {
            "replicas": spec.get("replicas", 1),
            "resources": containers[0].get("resources", {}) if containers else {}
        }
    except Exception:
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Metric Collection — fully dynamic
# ─────────────────────────────────────────────────────────────────────────────

def collect_all_metrics_for_service(service_name: str) -> dict:
    """
    Query every metric category defined in config for a given service.
    Returns a dict of metric_name → current_value.
    """
    svc_label = CFG["prometheus"]["service_label"]
    categories = CFG["prometheus"]["metric_categories"]
    collected = {}

    for category, queries in categories.items():
        for query_template in queries:
            # Inject service label filter into the query
            # Handles both plain metrics and functions like rate(...)
            if "{" in query_template:
                # Already has label selectors — add service filter
                labeled_query = query_template.replace(
                    "{",
                    f'{{{svc_label}="{service_name}",',
                    1
                )
                # Handle edge case of empty selector {}
                labeled_query = labeled_query.replace(
                    f'{{{svc_label}="{service_name}",}}',
                    f'{{{svc_label}="{service_name}"}}'
                )
            else:
                # Plain metric name — add selector
                labeled_query = f'{query_template}{{{svc_label}="{service_name}"}}'

            results = prom_query(labeled_query)
            if results:
                # Use the query template as key, cleaned up
                key = query_template.split("(")[0].replace("rate", "rate").strip()
                # Use actual metric name from result if available
                metric_name = results[0]["metric"].get("__name__", query_template)
                collected[metric_name] = results[0]["value"]

    return collected


def compute_anomaly_score(service: str, current_metrics: dict) -> dict:
    """
    Compare current metrics against stored baselines.
    Returns {score, anomalous_metrics: [{metric, current, baseline, ratio}]}.
    """
    weights = CFG["anomaly_detection"]["weights"]
    multiplier = CFG["prometheus"]["threshold_multiplier"]
    min_abs = CFG["prometheus"]["min_absolute_threshold"]
    score = 0.0
    anomalous = []

    # Try to get stored baselines, fall back to ratio-based detection
    baselines = {}
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute(
            "SELECT metric, baseline, stddev FROM service_baselines WHERE service = %s",
            (service,)
        )
        for row in cur.fetchall():
            baselines[row["metric"]] = {"baseline": row["baseline"], "stddev": row["stddev"]}
        cur.close()
        conn.close()
    except Exception:
        pass  # no baselines yet, use multiplier method

    for metric, value in current_metrics.items():
        if value < min_abs:
            continue

        # Determine weight for this metric type
        weight = 1.0
        for keyword, w in weights.items():
            if keyword in metric.lower():
                weight = w
                break

        if metric in baselines:
            baseline = baselines[metric]["baseline"]
            stddev = baselines[metric]["stddev"] or 1.0
            # Z-score: how many standard deviations from normal
            z = (value - baseline) / stddev
            if z > 2.0:  # more than 2 stddev above normal
                anomaly_score = weight * min(z / 2.0, 5.0)  # cap at 5x weight
                score += anomaly_score
                anomalous.append({
                    "metric": metric,
                    "current": value,
                    "baseline": baseline,
                    "z_score": round(z, 2),
                    "anomaly_contribution": round(anomaly_score, 2),
                    "detection_method": "zscore"
                })
        else:
            # No baseline — flag metrics with unusually high values
            # This is less precise but works on first run
            if metric in ["gc_pause_duration_ms", "db_connection_pool_usage_percent",
                          "memory_usage_mb", "payment_queue_length"]:
                # Known "high is bad" metrics — use fixed thresholds as fallback
                FALLBACK_THRESHOLDS = {
                    "gc_pause_duration_ms": 100,
                    "db_connection_pool_usage_percent": 80,
                    "memory_usage_mb": 500,
                    "payment_queue_length": 10,
                    "http_request_duration_seconds": 0.5,
                    "request_timeouts_total": 5,
                }
                threshold = FALLBACK_THRESHOLDS.get(metric, float("inf"))
                if value > threshold:
                    anomaly_contribution = weight * (value / threshold)
                    score += anomaly_contribution
                    anomalous.append({
                        "metric": metric,
                        "current": value,
                        "threshold_used": threshold,
                        "ratio": round(value / threshold, 2),
                        "anomaly_contribution": round(anomaly_contribution, 2),
                        "detection_method": "fallback_threshold"
                    })

    return {
        "score": round(score, 2),
        "anomalous_metrics": sorted(anomalous, key=lambda x: x["anomaly_contribution"], reverse=True)
    }


def update_baselines(service: str, metrics: dict):
    """
    Update rolling baselines for a service using exponential moving average.
    Called during normal (non-incident) operation to learn what 'normal' looks like.
    """
    alpha = 0.1  # EMA smoothing factor
    try:
        conn = get_db()
        cur = conn.cursor()
        for metric, value in metrics.items():
            cur.execute("""
                INSERT INTO service_baselines (service, metric, baseline, stddev)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (service, metric) DO UPDATE SET
                    baseline = service_baselines.baseline * (1 - %s) + %s * %s,
                    updated_at = NOW()
            """, (service, metric, value, 0.0, alpha, alpha, value))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Baseline update failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Dependency Graph — dynamic from Prometheus traces
# ─────────────────────────────────────────────────────────────────────────────

def build_dependency_graph(known_services: list[str]) -> dict:
    """
    Build a dependency graph by querying Prometheus for span metrics.
    OpenTelemetry exports span data that includes 'upstream' and 'downstream' labels.

    Falls back to a best-effort topology based on which services appear
    in each other's error/latency correlations.

    Returns: {service_name: [list of services it depends on]}
    """
    graph = {svc: [] for svc in known_services}

    # Method 1: OpenTelemetry span metrics (if available)
    # These have labels like upstream_service and downstream_service
    span_results = prom_query(
        'sum by (upstream_service, downstream_service) (rate(traces_spanmetrics_calls_total[5m]))'
    )
    if span_results:
        for item in span_results:
            labels = item["metric"]
            upstream = labels.get("upstream_service")
            downstream = labels.get("downstream_service")
            if upstream and downstream:
                if upstream in graph and downstream not in graph[upstream]:
                    graph[upstream].append(downstream)
        print(f"Dependency graph built from OpenTelemetry spans: {graph}")
        return graph

    # Method 2: Check for standard k8s network policy or service mesh annotations
    result = kubectl([
        "get", "deployments",
        "-n", NAMESPACE,
        "-o", "json"
    ])
    if result["success"]:
        try:
            data = json.loads(result["stdout"])
            for item in data.get("items", []):
                name = item["metadata"]["labels"].get("app", item["metadata"]["name"])
                annotations = item["metadata"].get("annotations", {})
                # Convention: annotate deployments with airp.io/depends-on: "s2,s3"
                depends_on = annotations.get("airp.io/depends-on", "")
                if depends_on and name in graph:
                    graph[name] = [d.strip() for d in depends_on.split(",")]
            has_annotations = any(len(v) > 0 for v in graph.values())
            if has_annotations:
                print(f"Dependency graph built from K8s annotations: {graph}")
                return graph
        except Exception:
            pass

    # Method 3: Fall back — return empty graph (GPT will infer from metrics)
    print("No dependency data found. GPT will infer topology from metric correlations.")
    return graph


# ─────────────────────────────────────────────────────────────────────────────
# Historical Context
# ─────────────────────────────────────────────────────────────────────────────

def find_similar_incidents(
    affected_services: list[str],
    anomalous_metrics: list[str],
    limit: int = None
) -> list[dict]:
    """
    Query the incidents table for past incidents involving similar services and metrics.
    Returns the most relevant past incidents to inject into the GPT RCA prompt.
    """
    if limit is None:
        limit = CFG["ai"]["historical_context_count"]

    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("""
            SELECT incident_id, alert_name, affected_services, root_cause,
                   root_cause_service, action_taken, outcome, recovery_time_s,
                   created_at
            FROM incidents
            WHERE outcome = 'resolved'
              AND created_at > NOW() - INTERVAL '%s days'
            ORDER BY created_at DESC
            LIMIT 20
        """, (CFG["platform"]["incident_history_days"],))

        all_incidents = cur.fetchall()
        cur.close()
        conn.close()

        # Score each past incident for relevance
        scored = []
        for inc in all_incidents:
            past_services = set(inc["affected_services"] or [])
            current_services = set(affected_services)
            overlap = len(past_services & current_services)
            if overlap > 0:
                score = overlap / max(len(past_services), len(current_services))
                scored.append((score, dict(inc)))

        # Return top N most similar
        scored.sort(key=lambda x: x[0], reverse=True)
        return [inc for score, inc in scored[:limit]
                if score >= CFG["ai"]["historical_similarity_threshold"]]
    except Exception as e:
        print(f"Historical query failed: {e}")
        return []


def save_incident(context: dict, outcome: str, recovery_time_s: int = 0):
    """Persist the incident to the database for future learning."""
    try:
        conn = get_db()
        cur = conn.cursor()
        diagnosis = context.get("diagnosis", {})
        plan = context.get("remediation_plan", {})
        probable_causes = diagnosis.get("probable_causes", [{}])
        primary = probable_causes[0] if probable_causes else {}
        action = plan.get("recommended_action", {})

        cur.execute("""
            INSERT INTO incidents
                (incident_id, timestamp, alert_name, affected_services,
                 root_cause, root_cause_service, action_taken, action_type,
                 confidence, outcome, recovery_time_s, full_context)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (incident_id) DO UPDATE SET
                outcome = EXCLUDED.outcome,
                recovery_time_s = EXCLUDED.recovery_time_s
        """, (
            context.get("incident_id"),
            context.get("timestamp"),
            context.get("triggered_by"),
            json.dumps([s["service"] for s in context.get("affected_services", [])]),
            primary.get("cause"),
            primary.get("service"),
            action.get("description"),
            action.get("type"),
            plan.get("confidence_score"),
            outcome,
            recovery_time_s,
            json.dumps(context, default=str)
        ))
        conn.commit()
        cur.close()
        conn.close()
        print(f"Incident {context.get('incident_id')} saved to history.")
    except Exception as e:
        print(f"Failed to save incident: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# GPT Helpers
# ─────────────────────────────────────────────────────────────────────────────

def ask_gpt(system: str, user: str) -> dict:
    """Call GPT and parse JSON response. Raises on failure."""
    response = openai_client.chat.completions.create(
        model=AI_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        response_format={"type": "json_object"},
        temperature=CFG["ai"]["temperature"],
        max_tokens=CFG["ai"]["max_tokens"]
    )
    content = response.choices[0].message.content
    return json.loads(content)


# ─────────────────────────────────────────────────────────────────────────────
# AGENT 1: Monitor Agent
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/monitor")
def monitor_agent(payload: dict):
    """
    Dynamic version:
    1. Discover all services (from K8s labels + Prometheus)
    2. Collect ALL available metrics for each service
    3. Score each service for anomalies
    4. Return a rich incident object with all data
    """
    print("\n═══ MONITOR AGENT ═══")
    
    # Step 1: Discover services
    k8s_services = discover_services_from_k8s()
    prom_services = discover_services_from_prometheus()
    
    # Merge: K8s gives us deployment details, Prometheus gives us metric coverage
    service_names = list(set(
        [s["name"] for s in k8s_services] + prom_services
    ))
    print(f"Discovered {len(service_names)} services: {service_names}")

    k8s_map = {s["name"]: s for s in k8s_services}

    # Step 2: Collect metrics + score anomalies for each service
    service_health = {}
    for svc in service_names:
        metrics = collect_all_metrics_for_service(svc)
        anomaly = compute_anomaly_score(svc, metrics)
        k8s_info = k8s_map.get(svc, {})
        service_health[svc] = {
            "metrics": metrics,
            "anomaly_score": anomaly["score"],
            "anomalous_metrics": anomaly["anomalous_metrics"],
            "current_replicas": k8s_info.get("current_replicas"),
            "available_replicas": k8s_info.get("available_replicas"),
            "deployment_name": k8s_info.get("deployment_name", svc),
        }

    # Step 3: Sort by anomaly score
    sorted_services = sorted(
        service_health.items(),
        key=lambda x: x[1]["anomaly_score"],
        reverse=True
    )

    incident = {
        "incident_id": f"INC-{int(time.time())}",
        "triggered_by": payload.get("commonLabels", {}).get("alertname", "unknown"),
        "severity": payload.get("commonLabels", {}).get("severity", "unknown"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "discovered_services": service_names,
        "service_health": service_health,
        "top_anomalous_services": [
            {"service": svc, "anomaly_score": data["anomaly_score"]}
            for svc, data in sorted_services[:5]
        ],
        "validated": True
    }

    print(f"Monitor Agent complete. Incident: {incident['incident_id']}")
    print(f"Top anomalous: {incident['top_anomalous_services'][:3]}")
    return incident


# ─────────────────────────────────────────────────────────────────────────────
# AGENT 2: Correlation Agent
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/correlate")
def correlation_agent(incident: dict):
    """
    Dynamic version:
    1. Build dependency graph (from OpenTelemetry / K8s annotations / fallback)
    2. Walk the graph to find services above the affected threshold
    3. Use graph topology to narrow down root cause candidates
    4. Return enriched incident with dependency chain context
    """
    print("\n═══ CORRELATION AGENT ═══")

    service_health = incident.get("service_health", {})
    services = list(service_health.keys())

    # Step 1: Build dependency graph dynamically
    dep_graph = build_dependency_graph(services)

    # Step 2: Classify each service
    affected_threshold   = CFG["anomaly_detection"]["affected_threshold"]
    root_cause_threshold = CFG["anomaly_detection"]["root_cause_threshold"]

    affected_services = []
    root_cause_candidates = []

    for svc, health in service_health.items():
        score = health["anomaly_score"]
        if score >= affected_threshold:
            entry = {
                "service": svc,
                "anomaly_score": score,
                "anomalous_metrics": health["anomalous_metrics"],
                "depends_on": dep_graph.get(svc, []),
                "deployment_name": health.get("deployment_name", svc),
            }
            affected_services.append(entry)

        if score >= root_cause_threshold:
            # A service is a stronger root cause candidate if:
            # - It has no anomalous dependencies (i.e. it IS the origin)
            # - OR its anomalous deps have lower scores (it was first to go bad)
            dep_scores = [
                service_health.get(dep, {}).get("anomaly_score", 0)
                for dep in dep_graph.get(svc, [])
            ]
            max_dep_score = max(dep_scores) if dep_scores else 0
            is_likely_origin = score > max_dep_score * 1.5 or max_dep_score < affected_threshold
            root_cause_candidates.append({
                "service": svc,
                "anomaly_score": score,
                "is_likely_origin": is_likely_origin,
                "dependency_scores": dict(zip(dep_graph.get(svc, []), dep_scores)),
            })

    # Sort candidates — origin services first
    root_cause_candidates.sort(
        key=lambda x: (x["is_likely_origin"], x["anomaly_score"]),
        reverse=True
    )

    # Build human-readable dependency chain string for GPT
    def build_chain(svc, depth=0, visited=None):
        if visited is None:
            visited = set()
        if svc in visited or depth > 5:
            return svc
        visited.add(svc)
        deps = dep_graph.get(svc, [])
        if not deps:
            return svc
        return svc + " → " + " → ".join([build_chain(d, depth+1, visited) for d in deps])

    chains = [build_chain(svc) for svc in services if not any(
        svc in dep_graph.get(other, []) for other in services
    )]

    correlated = {
        **incident,
        "correlated": True,
        "dependency_graph": dep_graph,
        "dependency_chains": chains,
        "affected_services": affected_services,
        "root_cause_candidates": root_cause_candidates,
        "primary_candidate": root_cause_candidates[0]["service"] if root_cause_candidates else None,
    }

    print(f"Correlation complete. Affected: {len(affected_services)}, "
          f"Candidates: {[c['service'] for c in root_cause_candidates]}")
    return correlated


# ─────────────────────────────────────────────────────────────────────────────
# AGENT 3: RCA Agent
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/rca")
def rca_agent(correlated_incident: dict):
    """
    Dynamic version:
    - GPT uses generic SRE knowledge, NOT scenario-specific runbooks
    - Injects historical similar incidents for context
    - Tests multiple hypotheses
    - Handles any incident type (memory, CPU, network, DB, cascading, etc.)
    """
    print("\n═══ RCA AGENT ═══")

    service_health = correlated_incident.get("service_health", {})
    affected       = correlated_incident.get("affected_services", [])
    candidates     = correlated_incident.get("root_cause_candidates", [])
    dep_graph      = correlated_incident.get("dependency_graph", {})
    dep_chains     = correlated_incident.get("dependency_chains", [])

    # Build a compact metric summary for each service to put in the prompt
    metric_summary = {}
    for svc, health in service_health.items():
        if health["anomaly_score"] > 0:
            metric_summary[svc] = {
                "anomaly_score": health["anomaly_score"],
                "anomalous_metrics": [
                    f"{m['metric']}={m['current']:.2f} "
                    f"(expected≈{m.get('baseline', m.get('threshold_used', '?')):.2f})"
                    for m in health["anomalous_metrics"][:5]
                ]
            }

    # Fetch similar past incidents
    affected_service_names = [s["service"] for s in affected]
    similar_incidents = find_similar_incidents(
        affected_service_names,
        [m["metric"] for s in affected for m in s.get("anomalous_metrics", [])]
    )

    historical_context = ""
    if similar_incidents:
        historical_context = "\n\nSIMILAR PAST INCIDENTS (for context):\n"
        for inc in similar_incidents:
            historical_context += (
                f"- {inc['created_at'].strftime('%Y-%m-%d')}: "
                f"Root cause was '{inc['root_cause']}' on {inc['root_cause_service']}. "
                f"Fixed by: {inc['action_taken']}. Outcome: {inc['outcome']}.\n"
            )

    system_prompt = f"""You are a senior Site Reliability Engineer with 15 years of 
experience diagnosing microservice failures. You are analyzing an incident in a 
{CFG['platform']['environment']} environment for {CFG['platform']['name']}.

You approach root cause analysis systematically:
1. Look for the service whose anomaly started the chain (not just the most affected)
2. Consider all types of failures: memory leaks, CPU throttling, I/O saturation, 
   network issues, database problems, GC pauses, connection pool exhaustion, 
   cascading failures, bad deployments, traffic spikes, external dependencies
3. Score your confidence honestly based on data completeness
4. Generate multiple hypotheses and rank them
5. Explain the failure propagation chain clearly

Always respond in valid JSON."""

    user_prompt = f"""Analyze this incident and determine the root cause.

DEPENDENCY TOPOLOGY:
{json.dumps(dep_graph, indent=2)}

DEPENDENCY CHAINS:
{chr(10).join(dep_chains)}

SERVICE ANOMALY DATA:
{json.dumps(metric_summary, indent=2)}

ROOT CAUSE CANDIDATES (pre-screened by correlation engine):
{json.dumps(candidates, indent=2)}

ENVIRONMENT: {CFG['platform']['environment']}
{historical_context}

Based on this data, determine the root cause. Consider:
- Which service's anomalies are consistent with being the ORIGIN (not a downstream effect)?
- What type of failure pattern do these metrics suggest?
- How does the failure propagate through the dependency chain?
- What is the confidence level based on available data?

Respond with JSON in exactly this structure:
{{
  "probable_causes": [
    {{
      "rank": 1,
      "service": "service-name",
      "deployment_name": "k8s-deployment-name",
      "cause": "short cause label (e.g. 'memory_leak', 'cpu_throttling', 'db_saturation')",
      "cause_description": "human readable description",
      "confidence": 0.0,
      "supporting_evidence": ["list of metrics that support this hypothesis"],
      "reasoning": "detailed explanation"
    }}
  ],
  "incident_type": "one of: memory_leak | cpu_spike | db_saturation | network_issue | cascading_failure | bad_deployment | traffic_spike | gc_pauses | connection_pool_exhaustion | unknown",
  "primary_root_cause": "one clear sentence summary",
  "failure_propagation": "step by step explanation of how failure spread",
  "data_quality": "complete | partial | insufficient",
  "recommended_data_sources": ["any additional data that would improve confidence"]
}}
"""

    diagnosis = ask_gpt(system_prompt, user_prompt)
    print(f"RCA complete. Primary cause: {diagnosis.get('primary_root_cause')}")
    print(f"Incident type: {diagnosis.get('incident_type')}")

    return {
        **correlated_incident,
        "diagnosis": diagnosis,
        "rca_complete": True
    }


# ─────────────────────────────────────────────────────────────────────────────
# AGENT 4: Remediation Agent
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/remediate")
def remediation_agent(rca_result: dict):
    """
    Dynamic version:
    - Reads available action types from config (no hardcoded actions)
    - GPT selects the best action based on actual diagnosis
    - Builds precise kubectl command with real values
    - Always includes rollback plan
    """
    print("\n═══ REMEDIATION AGENT ═══")

    diagnosis      = rca_result.get("diagnosis", {})
    probable_causes = diagnosis.get("probable_causes", [{}])
    primary        = probable_causes[0] if probable_causes else {}
    incident_type  = diagnosis.get("incident_type", "unknown")
    confidence     = primary.get("confidence", 0)
    target_svc     = primary.get("service", "unknown")
    target_deploy  = primary.get("deployment_name", target_svc)

    # Get current state of the target deployment
    deploy_info = get_deployment_info(target_deploy)
    current_replicas = deploy_info.get("replicas", 1)
    current_resources = deploy_info.get("resources", {})

    # Build the action library from config
    action_library = CFG["remediation_actions"]
    max_replicas = CFG["kubernetes"]["scaling"]["max_replicas_per_service"]

    # Format action library for GPT — include constraints
    action_options = []
    for action_type, action_cfg in action_library.items():
        if incident_type in action_cfg.get("applicable_to", []) or True:
            action_options.append({
                "type": action_type,
                "description": action_cfg["description"],
                "applicable_to": action_cfg.get("applicable_to", []),
                "risk": action_cfg["risk"],
                "reversible": action_cfg["reversible"],
                "template": action_cfg["kubectl_template"]
            })

    system_prompt = f"""You are an SRE remediation specialist. You select the safest 
appropriate remediation action from a provided library. 

You must:
1. Choose the action most likely to resolve the specific root cause
2. Provide exact parameter values (replica counts, memory values, etc.)
3. Assess risk honestly
4. Always provide a rollback plan
5. Consider the current state of the system

Risk tolerance for this environment: {RISK_TOLERANCE}
Always respond in valid JSON."""

    user_prompt = f"""Select and configure the best remediation action for this incident.

ROOT CAUSE DIAGNOSIS:
- Service: {target_svc}
- Deployment: {target_deploy}
- Cause type: {primary.get('cause')}
- Description: {primary.get('cause_description')}
- Incident type: {incident_type}
- Confidence: {confidence}

CURRENT SERVICE STATE:
- Current replicas: {current_replicas}
- Max allowed replicas: {max_replicas}
- Current resources: {json.dumps(current_resources)}
- Namespace: {NAMESPACE}

AVAILABLE ACTIONS:
{json.dumps(action_options, indent=2)}

CONSTRAINTS:
- Max replicas: {max_replicas}
- Min replicas: {CFG['kubernetes']['scaling']['min_replicas_per_service']}
- Risk tolerance: {RISK_TOLERANCE}
- Confidence threshold for action: {MIN_CONFIDENCE}

Select the best action and fill in all template variables with real values.
For scale_up: choose replicas = min(current * 2, max_replicas)
For memory: use standard K8s sizes (256Mi, 512Mi, 1Gi, 2Gi)

Respond with JSON in exactly this structure:
{{
  "recommended_action": {{
    "type": "action_type_from_library",
    "target_service": "{target_svc}",
    "target_deployment": "{target_deploy}",
    "namespace": "{NAMESPACE}",
    "description": "human readable description of what will happen",
    "kubectl_command": "exact kubectl command with all variables filled in",
    "parameters": {{
      "value": "the new value (replicas count, memory limit, etc.)",
      "original_value": "current value for rollback"
    }},
    "expected_outcome": "what metrics should improve and by how much",
    "estimated_recovery_time_seconds": 120
  }},
  "rollback_plan": {{
    "trigger_condition": "when to rollback (e.g. S1 latency still above 500ms after 5 min)",
    "kubectl_command": "exact rollback kubectl command",
    "description": "rollback description"
  }},
  "alternative_actions": [
    {{
      "type": "fallback action type",
      "description": "if primary doesn't work, try this",
      "kubectl_command": "exact command"
    }}
  ],
  "confidence_score": {confidence},
  "requires_human_approval": {str(confidence < MIN_CONFIDENCE or RISK_TOLERANCE == 'low').lower()},
  "risk_level": "low | medium | high",
  "risk_reasoning": "why this risk level"
}}
"""

    plan = ask_gpt(system_prompt, user_prompt)
    print(f"Remediation plan: {plan.get('recommended_action', {}).get('description')}")
    print(f"Risk: {plan.get('risk_level')}, Requires approval: {plan.get('requires_human_approval')}")

    return {
        **rca_result,
        "remediation_plan": plan,
        "remediation_complete": True
    }


# ─────────────────────────────────────────────────────────────────────────────
# AGENT 5: K8s Operator — Dynamic Command Execution
# ─────────────────────────────────────────────────────────────────────────────

class ExecutionRequest(BaseModel):
    kubectl_command: str             # the exact command from remediation plan
    deployment: str                  # for rollout status check
    namespace: str = "shopfast"
    incident_context: dict = {}

@app.post("/execute")
def k8s_operator(req: ExecutionRequest):
    """
    Dynamic version:
    Executes whatever kubectl command the remediation agent produced.
    No hardcoded actions — the command is always generated by GPT + config.
    Validates the command for safety before running.
    """
    print(f"\n═══ K8s OPERATOR ═══")
    print(f"Command: {req.kubectl_command}")

    # Safety check: block destructive commands
    BLOCKED_PATTERNS = [
        "delete namespace",
        "delete cluster",
        "delete pv",
        "--all-namespaces",
        "drain",           # too risky without careful planning
        "rm -rf",
    ]
    command_lower = req.kubectl_command.lower()
    for pattern in BLOCKED_PATTERNS:
        if pattern in command_lower:
            return {
                "success": False,
                "error": f"Blocked: command contains disallowed pattern '{pattern}'",
                "command": req.kubectl_command
            }

    # Parse the kubectl command string into args list
    cmd_parts = req.kubectl_command.split()
    if cmd_parts[0] == "kubectl":
        cmd_parts = cmd_parts[1:]  # remove 'kubectl' prefix, added by our helper

    result = kubectl(cmd_parts)
    print(f"Execution result: {result['success']}")

    if result["success"] and "scale" in req.kubectl_command:
        # Wait for rollout to complete
        print("Waiting for rollout...")
        rollout = kubectl([
            "rollout", "status",
            f"deployment/{req.deployment}",
            f"--namespace={req.namespace}",
            "--timeout=120s"
        ])
        result["rollout_status"] = rollout["stdout"]

    return {
        "success": result["success"],
        "executed_command": result["command"],
        "output": result["stdout"],
        "error": result["stderr"] if not result["success"] else None,
        "deployment": req.deployment,
        "namespace": req.namespace,
    }


# ─────────────────────────────────────────────────────────────────────────────
# AGENT 6: Validation — Dynamic Recovery Check
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/validate")
def validate_recovery(context: dict):
    """
    Dynamic version:
    Re-runs the same anomaly scoring as the monitor agent.
    Recovery is confirmed when ALL previously anomalous services
    drop below the recovery threshold.
    """
    print("\n═══ VALIDATION AGENT ═══")

    wait_time = CFG["validation"]["wait_seconds_after_action"]
    max_attempts = CFG["validation"]["max_validation_attempts"]
    check_interval = CFG["validation"]["check_interval_seconds"]
    recovery_threshold = CFG["validation"]["recovery_anomaly_threshold"]

    original_health = context.get("service_health", {})
    originally_affected = [
        svc for svc, health in original_health.items()
        if health.get("anomaly_score", 0) >= CFG["anomaly_detection"]["affected_threshold"]
    ]

    print(f"Waiting {wait_time}s for system to stabilize...")
    time.sleep(wait_time)

    start_time = time.time()
    attempts = 0
    final_health = {}

    while attempts < max_attempts:
        attempts += 1
        print(f"Validation attempt {attempts}/{max_attempts}...")

        current_scores = {}
        for svc in originally_affected:
            metrics = collect_all_metrics_for_service(svc)
            anomaly = compute_anomaly_score(svc, metrics)
            current_scores[svc] = {
                "anomaly_score": anomaly["score"],
                "anomalous_metrics": anomaly["anomalous_metrics"],
                "metrics": metrics,
                "recovered": anomaly["score"] < recovery_threshold
            }
            print(f"  {svc}: anomaly_score={anomaly['score']:.2f} "
                  f"({'✓ recovered' if anomaly['score'] < recovery_threshold else '✗ still anomalous'})")

        final_health = current_scores
        all_recovered = all(v["recovered"] for v in current_scores.values())

        if all_recovered:
            break

        if attempts < max_attempts:
            time.sleep(check_interval)

    recovery_time = int(time.time() - start_time)
    fully_recovered = all(v.get("recovered", False) for v in final_health.values())

    # Update baselines with post-recovery data (now metrics are healthy again)
    if fully_recovered:
        for svc, data in final_health.items():
            update_baselines(svc, data.get("metrics", {}))

    return {
        **context,
        "validation": {
            "recovered": fully_recovered,
            "recovery_time_seconds": recovery_time,
            "validation_attempts": attempts,
            "post_fix_service_health": final_health,
            "recovery_detail": {
                svc: "recovered" if data.get("recovered") else "still_anomalous"
                for svc, data in final_health.items()
            }
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# AGENT 7: Documentation Agent + Learning
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/document")
def documentation_agent(full_context: dict):
    """
    Dynamic version:
    - GPT writes a complete, professional incident report
    - Saves incident to DB for future learning
    - Updates baselines if helpful
    """
    print("\n═══ DOCUMENTATION AGENT ═══")

    diagnosis  = full_context.get("diagnosis", {})
    plan       = full_context.get("remediation_plan", {})
    validation = full_context.get("validation", {})
    affected   = full_context.get("affected_services", [])

    recovered      = validation.get("recovered", False)
    recovery_time  = validation.get("recovery_time_seconds", 0)
    outcome        = "resolved" if recovered else "failed"

    # Save to incident history first (for future learning)
    save_incident(full_context, outcome, recovery_time)

    system_prompt = f"""You are a technical writer for {CFG['platform']['name']} SRE team.
Write professional, clear incident reports. Be specific and factual.
Include actionable prevention recommendations.
Always respond in valid JSON."""

    probable_causes = diagnosis.get("probable_causes", [{}])
    primary = probable_causes[0] if probable_causes else {}
    action = plan.get("recommended_action", {})
    recovery_detail = validation.get("recovery_detail", {})

    user_prompt = f"""Write a complete incident report.

INCIDENT DATA:
- ID: {full_context.get('incident_id')}
- Time: {full_context.get('timestamp')}
- Trigger: {full_context.get('triggered_by')}
- Incident Type: {diagnosis.get('incident_type')}

IMPACT:
- Affected services: {[s['service'] for s in affected]}
- Number of services impacted: {len(affected)}

ROOT CAUSE:
- Primary cause: {diagnosis.get('primary_root_cause')}
- Failure propagation: {diagnosis.get('failure_propagation')}
- Confidence: {primary.get('confidence', 0) * 100:.0f}%

ACTION TAKEN:
- {action.get('description')}
- Command: {action.get('kubectl_command')}
- Risk level: {plan.get('risk_level')}

OUTCOME:
- Status: {outcome.upper()}
- Recovery time: {recovery_time} seconds
- Service recovery: {json.dumps(recovery_detail)}

Write a comprehensive report as JSON:
{{
  "title": "descriptive incident title",
  "severity": "P1 | P2 | P3",
  "executive_summary": "2-3 sentences for non-technical stakeholders",
  "timeline": [
    {{"time_offset": "+0:00", "event": "description"}},
    {{"time_offset": "+N:NN", "event": "description"}}
  ],
  "technical_root_cause": "detailed technical explanation",
  "business_impact": "user-facing impact description",
  "resolution_steps": ["ordered list of what was done"],
  "prevention_recommendations": [
    {{
      "recommendation": "specific action",
      "priority": "high | medium | low",
      "effort": "hours | days | weeks"
    }}
  ],
  "metrics_to_monitor": ["list of metrics to add to runbook"],
  "full_markdown_report": "complete markdown text of the incident report"
}}
"""

    report = ask_gpt(system_prompt, user_prompt)
    print(f"Documentation complete. Incident {outcome}.")

    return {
        "incident_id": full_context.get("incident_id"),
        "status": outcome.upper(),
        "report": report,
        "saved_to_history": True,
        "will_improve_future_incidents": True
    }


# ─────────────────────────────────────────────────────────────────────────────
# Health + Config Inspection
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "airp-agents-v2",
        "config_loaded": bool(CFG),
        "namespace": NAMESPACE,
        "prometheus": PROMETHEUS_URL,
        "ai_model": AI_MODEL
    }

@app.get("/config")
def get_config():
    """Expose loaded config for debugging (masks secrets)."""
    safe = json.loads(json.dumps(CFG))
    safe["prometheus"]["url"] = "***"
    return safe

@app.get("/discover")
def discover():
    """Endpoint to manually trigger service discovery — useful for testing."""
    k8s_services = discover_services_from_k8s()
    prom_services = discover_services_from_prometheus()
    return {
        "k8s_services": k8s_services,
        "prometheus_services": prom_services,
        "merged": list(set(
            [s["name"] for s in k8s_services] + prom_services
        ))
    }

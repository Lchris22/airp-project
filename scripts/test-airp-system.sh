#!/bin/bash

# AIRP System End-to-End Test Script
# Tests the complete incident resolution workflow

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Configuration
N8N_URL="http://localhost:5678"
AIRP_AGENTS_IP="20.85.151.165"
AIRP_AGENTS_PORT="8080"

print_header "AIRP System Health Check"

# 1. Check AIRP Agents
echo "1. Checking AIRP Agents..."
if curl -s -f "http://${AIRP_AGENTS_IP}:${AIRP_AGENTS_PORT}/health" > /dev/null 2>&1; then
    print_success "AIRP agents are responding"
else
    print_error "AIRP agents are not responding at ${AIRP_AGENTS_IP}:${AIRP_AGENTS_PORT}"
    echo "   Run: kubectl get pods -n default | grep airp"
    exit 1
fi

# 2. Check n8n
echo "2. Checking n8n..."
if curl -s -f "${N8N_URL}" > /dev/null 2>&1; then
    print_success "n8n is accessible"
else
    print_error "n8n is not accessible at ${N8N_URL}"
    echo "   Run: kubectl port-forward -n n8n svc/n8n 5678:80"
    exit 1
fi

# 3. Check PostgreSQL
echo "3. Checking PostgreSQL..."
if kubectl exec -n default deployment/postgres -- pg_isready -U airp > /dev/null 2>&1; then
    print_success "PostgreSQL is running"
else
    print_error "PostgreSQL is not responding"
    exit 1
fi

# 4. Check Prometheus
echo "4. Checking Prometheus..."
if kubectl get pods -n shopfast | grep prometheus-prometheus | grep Running > /dev/null 2>&1; then
    print_success "Prometheus is running"
else
    print_error "Prometheus is not running"
    exit 1
fi

# 5. Check Alertmanager
echo "5. Checking Alertmanager..."
if kubectl get pods -n shopfast | grep alertmanager | grep Running > /dev/null 2>&1; then
    print_success "Alertmanager is running"
else
    print_error "Alertmanager is not running"
    exit 1
fi

echo ""
print_header "Testing AIRP Workflow"

# 6. Test n8n webhook
echo "6. Testing n8n incident webhook..."
INCIDENT_ID="TEST-$(date +%s)"
RESPONSE=$(curl -s -X POST "${N8N_URL}/webhook/incident-trigger" \
  -H "Content-Type: application/json" \
  -d "{
    \"incident_id\": \"${INCIDENT_ID}\",
    \"severity\": \"critical\",
    \"metrics\": {
      \"s1_latency_ms\": 750,
      \"s2_pool_usage_percent\": 85,
      \"s3_gc_pause_ms\": 250
    },
    \"service\": \"s3-pricing\",
    \"description\": \"Automated test incident\"
  }" 2>&1)

if [ $? -eq 0 ]; then
    print_success "Webhook triggered successfully"
    echo "   Incident ID: ${INCIDENT_ID}"
    echo "   Response: ${RESPONSE}"
else
    print_error "Failed to trigger webhook"
    echo "   Error: ${RESPONSE}"
fi

echo ""
print_header "Testing AIRP Agents Directly"

# 7. Test Monitor Agent
echo "7. Testing Monitor Agent..."
MONITOR_RESPONSE=$(curl -s -X POST "http://${AIRP_AGENTS_IP}:${AIRP_AGENTS_PORT}/monitor" \
  -H "Content-Type: application/json" \
  -d "{
    \"incident_id\": \"${INCIDENT_ID}\",
    \"service\": \"s3-pricing\"
  }" 2>&1)

if [ $? -eq 0 ]; then
    print_success "Monitor Agent responded"
    echo "   Response: ${MONITOR_RESPONSE}" | head -c 200
    echo "..."
else
    print_error "Monitor Agent failed"
fi

# 8. Test Correlation Agent
echo "8. Testing Correlation Agent..."
CORRELATION_RESPONSE=$(curl -s -X POST "http://${AIRP_AGENTS_IP}:${AIRP_AGENTS_PORT}/correlate" \
  -H "Content-Type: application/json" \
  -d "{
    \"incident_id\": \"${INCIDENT_ID}\",
    \"metrics\": {
      \"s3_gc_pause_ms\": 250
    }
  }" 2>&1)

if [ $? -eq 0 ]; then
    print_success "Correlation Agent responded"
    echo "   Response: ${CORRELATION_RESPONSE}" | head -c 200
    echo "..."
else
    print_error "Correlation Agent failed"
fi

echo ""
print_header "Checking n8n Workflow Executions"

# 9. Check recent workflow executions
echo "9. Checking recent workflow executions..."
echo "   Visit: ${N8N_URL}/workflow/VNdvvpxwqvZCAT74/executions"
echo "   Or run: ./scripts/n8n-api-examples.sh get_executions"

echo ""
print_header "Verification Steps"

echo "To verify the complete workflow:"
echo ""
echo "1. Check n8n executions:"
echo "   ${N8N_URL}/workflow/VNdvvpxwqvZCAT74/executions"
echo ""
echo "2. Check AIRP agent logs:"
echo "   kubectl logs -n default deployment/airp-agents -f"
echo ""
echo "3. Check n8n logs:"
echo "   kubectl logs -n n8n deployment/n8n -f"
echo ""
echo "4. Check Alertmanager:"
echo "   kubectl port-forward -n shopfast svc/prometheus-kube-prometheus-alertmanager 9093:9093"
echo "   Visit: http://localhost:9093"
echo ""
echo "5. Check Prometheus alerts:"
echo "   kubectl port-forward -n shopfast svc/prometheus-kube-prometheus-prometheus 9090:9090"
echo "   Visit: http://localhost:9090/alerts"
echo ""
echo "6. Check database for incident records:"
echo "   kubectl exec -it -n default deployment/postgres -- psql -U airp -d airp -c 'SELECT * FROM incidents ORDER BY created_at DESC LIMIT 5;'"
echo ""

print_header "Test Summary"

echo "System Status:"
echo "  ✓ AIRP Agents: Running at ${AIRP_AGENTS_IP}:${AIRP_AGENTS_PORT}"
echo "  ✓ n8n: Running at ${N8N_URL}"
echo "  ✓ PostgreSQL: Running"
echo "  ✓ Prometheus: Running"
echo "  ✓ Alertmanager: Running"
echo ""
echo "Test Incident ID: ${INCIDENT_ID}"
echo ""
echo "Next Steps:"
echo "1. Activate the workflow in n8n UI if not already active"
echo "2. Configure Slack OAuth2 credentials"
echo "3. Monitor the workflow execution for incident ${INCIDENT_ID}"
echo "4. Verify all 7 agents are called in sequence"
echo ""

print_success "Health check complete!"

# Made with Bob

#!/bin/bash
# Import AIRP workflow to n8n via REST API

set -e

# Configuration
N8N_URL="https://progamerarena.app.n8n.cloud"
WORKFLOW_FILE="workflows/airp-incident-resolution.json"
AIRP_IP="20.85.151.165"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🔧 AIRP Workflow Import Script${NC}"
echo "================================"
echo ""

# Check if workflow file exists
if [ ! -f "$WORKFLOW_FILE" ]; then
    echo -e "${RED}❌ Error: Workflow file not found: $WORKFLOW_FILE${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Found workflow file: $WORKFLOW_FILE"

# Update AIRP IP in workflow
echo -e "${YELLOW}📝 Updating AIRP agent IP to $AIRP_IP...${NC}"
TEMP_FILE=$(mktemp)
sed "s/\\\${{ \\\$vars\.AIRP_AGENTS_IP }}/$AIRP_IP/g" "$WORKFLOW_FILE" > "$TEMP_FILE"
echo -e "${GREEN}✓${NC} IP address updated"

# Check if n8n API key is provided
if [ -z "$N8N_API_KEY" ]; then
    echo ""
    echo -e "${YELLOW}⚠️  N8N_API_KEY environment variable not set${NC}"
    echo ""
    echo "To import via API, you need an n8n API key:"
    echo "1. Go to: $N8N_URL/settings/api"
    echo "2. Create a new API key"
    echo "3. Run: export N8N_API_KEY='your-api-key'"
    echo "4. Run this script again"
    echo ""
    echo -e "${YELLOW}📋 Manual Import Instructions:${NC}"
    echo "1. Open: $N8N_URL"
    echo "2. Click 'Add workflow' → 'Import from File'"
    echo "3. Select: $TEMP_FILE"
    echo "4. Click 'Import'"
    echo ""
    echo -e "${GREEN}✓${NC} Pre-configured workflow saved to: $TEMP_FILE"
    echo "   (IP already updated to $AIRP_IP)"
    exit 0
fi

# Import workflow via API
echo -e "${YELLOW}📤 Importing workflow to n8n...${NC}"

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$N8N_URL/api/v1/workflows" \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d @"$TEMP_FILE")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "201" ]; then
    WORKFLOW_ID=$(echo "$BODY" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    echo -e "${GREEN}✅ Workflow imported successfully!${NC}"
    echo "   Workflow ID: $WORKFLOW_ID"
    echo "   URL: $N8N_URL/workflow/$WORKFLOW_ID"
    echo ""
    echo -e "${GREEN}✓${NC} Next steps:"
    echo "   1. Configure Slack OAuth2 credentials"
    echo "   2. Activate the workflow"
    echo "   3. Test with: curl -X POST $N8N_URL/webhook/incident-trigger -d '{...}'"
else
    echo -e "${RED}❌ Failed to import workflow${NC}"
    echo "   HTTP Code: $HTTP_CODE"
    echo "   Response: $BODY"
    exit 1
fi

# Cleanup
rm -f "$TEMP_FILE"

# Made with Bob

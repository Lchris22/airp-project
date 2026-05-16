#!/bin/bash

# n8n API Examples
# Using the n8n Public API with your API token

# Configuration
N8N_URL="http://localhost:5678"
API_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI5MjI0ZWEzYi0yMTMxLTQxY2MtYmQ4OC1kOTNjMjU4MzEwYzAiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiMzE1Mjg4ODAtM2YzNi00NGFjLTk2NTYtMDRhZTg5MTgwOTQxIiwiaWF0IjoxNzc4OTA1MTM4fQ.q3qW4veWA1hf7RgJgGBZOSCyDJqF94r_WFT_JAFV9Ko"
AIRP_AGENTS_IP="20.85.151.165"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

# 1. List all workflows
list_workflows() {
    print_header "Listing All Workflows"
    curl -s -X GET "${N8N_URL}/api/v1/workflows" \
        -H "X-N8N-API-KEY: ${API_TOKEN}" \
        -H "Content-Type: application/json" | jq '.'
}

# 2. Get specific workflow details
get_workflow() {
    local workflow_id=$1
    if [ -z "$workflow_id" ]; then
        echo "Usage: get_workflow <workflow_id>"
        return 1
    fi
    
    print_header "Getting Workflow: $workflow_id"
    curl -s -X GET "${N8N_URL}/api/v1/workflows/${workflow_id}" \
        -H "X-N8N-API-KEY: ${API_TOKEN}" \
        -H "Content-Type: application/json" | jq '.'
}

# 3. Execute a workflow
execute_workflow() {
    local workflow_id=$1
    local data=${2:-'{}'}
    
    if [ -z "$workflow_id" ]; then
        echo "Usage: execute_workflow <workflow_id> [json_data]"
        return 1
    fi
    
    print_header "Executing Workflow: $workflow_id"
    curl -s -X POST "${N8N_URL}/api/v1/workflows/${workflow_id}/execute" \
        -H "X-N8N-API-KEY: ${API_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "$data" | jq '.'
}

# 4. Get workflow executions
get_executions() {
    local workflow_id=$1
    
    print_header "Getting Workflow Executions"
    if [ -z "$workflow_id" ]; then
        # Get all executions
        curl -s -X GET "${N8N_URL}/api/v1/executions" \
            -H "X-N8N-API-KEY: ${API_TOKEN}" \
            -H "Content-Type: application/json" | jq '.'
    else
        # Get executions for specific workflow
        curl -s -X GET "${N8N_URL}/api/v1/executions?workflowId=${workflow_id}" \
            -H "X-N8N-API-KEY: ${API_TOKEN}" \
            -H "Content-Type: application/json" | jq '.'
    fi
}

# 5. Get execution details
get_execution() {
    local execution_id=$1
    
    if [ -z "$execution_id" ]; then
        echo "Usage: get_execution <execution_id>"
        return 1
    fi
    
    print_header "Getting Execution: $execution_id"
    curl -s -X GET "${N8N_URL}/api/v1/executions/${execution_id}" \
        -H "X-N8N-API-KEY: ${API_TOKEN}" \
        -H "Content-Type: application/json" | jq '.'
}

# 6. Create a workflow
create_workflow() {
    local workflow_file=$1
    
    if [ -z "$workflow_file" ] || [ ! -f "$workflow_file" ]; then
        echo "Usage: create_workflow <workflow_json_file>"
        return 1
    fi
    
    print_header "Creating Workflow from: $workflow_file"
    curl -s -X POST "${N8N_URL}/api/v1/workflows" \
        -H "X-N8N-API-KEY: ${API_TOKEN}" \
        -H "Content-Type: application/json" \
        -d @"$workflow_file" | jq '.'
}

# 7. Update a workflow
update_workflow() {
    local workflow_id=$1
    local workflow_file=$2
    
    if [ -z "$workflow_id" ] || [ -z "$workflow_file" ] || [ ! -f "$workflow_file" ]; then
        echo "Usage: update_workflow <workflow_id> <workflow_json_file>"
        return 1
    fi
    
    print_header "Updating Workflow: $workflow_id"
    curl -s -X PUT "${N8N_URL}/api/v1/workflows/${workflow_id}" \
        -H "X-N8N-API-KEY: ${API_TOKEN}" \
        -H "Content-Type: application/json" \
        -d @"$workflow_file" | jq '.'
}

# 8. Activate/Deactivate workflow
toggle_workflow() {
    local workflow_id=$1
    local active=$2
    
    if [ -z "$workflow_id" ] || [ -z "$active" ]; then
        echo "Usage: toggle_workflow <workflow_id> <true|false>"
        return 1
    fi
    
    print_header "Setting Workflow $workflow_id Active: $active"
    curl -s -X PATCH "${N8N_URL}/api/v1/workflows/${workflow_id}" \
        -H "X-N8N-API-KEY: ${API_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{\"active\": ${active}}" | jq '.'
}

# 9. Delete a workflow
delete_workflow() {
    local workflow_id=$1
    
    if [ -z "$workflow_id" ]; then
        echo "Usage: delete_workflow <workflow_id>"
        return 1
    fi
    
    read -p "Are you sure you want to delete workflow $workflow_id? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Cancelled"
        return 0
    fi
    
    print_header "Deleting Workflow: $workflow_id"
    curl -s -X DELETE "${N8N_URL}/api/v1/workflows/${workflow_id}" \
        -H "X-N8N-API-KEY: ${API_TOKEN}" \
        -H "Content-Type: application/json"
    echo "Workflow deleted"
}

# 10. Get credentials (list only, not values)
list_credentials() {
    print_header "Listing Credentials"
    curl -s -X GET "${N8N_URL}/api/v1/credentials" \
        -H "X-N8N-API-KEY: ${API_TOKEN}" \
        -H "Content-Type: application/json" | jq '.'
}

# 11. Test workflow webhook
test_webhook() {
    local workflow_id=$1
    local webhook_path=$2
    local data=${3:-'{"test": "data"}'}
    
    if [ -z "$workflow_id" ] || [ -z "$webhook_path" ]; then
        echo "Usage: test_webhook <workflow_id> <webhook_path> [json_data]"
        return 1
    fi
    
    print_header "Testing Webhook: $webhook_path"
    curl -s -X POST "${N8N_URL}/webhook-test/${webhook_path}" \
        -H "Content-Type: application/json" \
        -d "$data" | jq '.'
}

# 12. Import workflow from file
import_workflow() {
    local file=$1
    
    if [ -z "$file" ] || [ ! -f "$file" ]; then
        echo "Usage: import_workflow <workflow_json_file>"
        return 1
    fi
    
    print_header "Importing Workflow: $file"
    
    # Read the workflow file and create it
    create_workflow "$file"
}

# Help function
show_help() {
    echo "n8n API Examples"
    echo ""
    echo "Available functions:"
    echo "  list_workflows                          - List all workflows"
    echo "  get_workflow <id>                       - Get workflow details"
    echo "  execute_workflow <id> [data]            - Execute a workflow"
    echo "  get_executions [workflow_id]            - Get executions"
    echo "  get_execution <id>                      - Get execution details"
    echo "  create_workflow <file>                  - Create workflow from JSON"
    echo "  update_workflow <id> <file>             - Update workflow"
    echo "  toggle_workflow <id> <true|false>       - Activate/deactivate"
    echo "  delete_workflow <id>                    - Delete workflow"
    echo "  list_credentials                        - List credentials"
    echo "  test_webhook <id> <path> [data]         - Test webhook"
    echo "  import_workflow <file>                  - Import workflow"
    echo ""
    echo "Examples:"
    echo "  $0 list_workflows"
    echo "  $0 get_workflow 1"
    echo "  $0 execute_workflow 1 '{\"name\":\"test\"}'"
    echo "  $0 import_workflow workflows/my-workflow.json"
}

# Main
if [ $# -eq 0 ]; then
    show_help
else
    "$@"
fi

# Made with Bob

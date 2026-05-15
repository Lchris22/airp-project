# AIRP n8n Workflows

This directory contains n8n workflow definitions for orchestrating the AIRP agent pipeline.

## Main Workflow

**File:** `airp-incident-resolution.json`

This is the primary workflow that orchestrates the entire incident resolution process:

```
Webhook Trigger (Alertmanager)
    ↓
Acknowledge Alert
    ↓
Monitor Agent → Correlation Agent → RCA Agent → Remediation Agent
    ↓
Send Slack Approval Request
    ↓
Wait for SRE Approval (Webhook)
    ↓
Approved? (IF node)
    ├─ Yes → Execute Remediation → Validate Recovery → Document → Slack Success
    └─ No  → Slack Denial Notification
```

## Setup Instructions

### 1. Import Workflow to n8n Cloud

1. Log into https://app.n8n.cloud
2. Click **"Import from File"** or **"Import from URL"**
3. Select `airp-incident-resolution.json`
4. The workflow will be imported with all nodes

### 2. Configure n8n Variables

Go to **Settings → Variables** and add:

| Variable Name | Value | Description |
|---------------|-------|-------------|
| `AIRP_AGENTS_IP` | `<your-airp-service-ip>` | External IP of AIRP agent service |
| `N8N_APPROVAL_WEBHOOK` | `https://your-instance.app.n8n.cloud/webhook/sre-approval` | Approval webhook URL |

### 3. Configure Slack Credentials

1. Go to **Credentials → Add Credential**
2. Select **Slack OAuth2 API**
3. Follow OAuth flow to connect your Slack workspace
4. Grant permissions:
   - `chat:write` (send messages)
   - `channels:read` (list channels)

### 4. Update Workflow Nodes

Verify these settings in the workflow:

#### Webhook Trigger Node
- **Path:** `incident-trigger`
- **Method:** POST
- **Response Mode:** Using 'Respond to Webhook' Node

#### HTTP Request Nodes (All Agent Calls)
- **URL:** `http://{{ $vars.AIRP_AGENTS_IP }}:8080/<endpoint>`
- **Method:** POST
- **Body:** JSON from previous node

#### Slack Nodes
- **Credential:** Your Slack OAuth2 credential
- **Channel:** `#incidents` (or your preferred channel)

#### Wait for SRE Approval Node
- **Path:** `sre-approval`
- **Method:** GET

### 5. Activate Workflow

Click the **Active** toggle in the top-right corner.

## Webhook URLs

After activation, you'll have two webhook URLs:

### Incident Trigger Webhook
```
https://your-instance.app.n8n.cloud/webhook/incident-trigger
```
Configure this in Alertmanager to receive alerts.

### Approval Webhook
```
https://your-instance.app.n8n.cloud/webhook/sre-approval
```
This is embedded in Slack approval buttons.

## Testing the Workflow

### Manual Test

1. Click **"Execute Workflow"** in n8n
2. Or send a test alert:

```bash
curl -X POST https://your-instance.app.n8n.cloud/webhook/incident-trigger \
  -H "Content-Type: application/json" \
  -d '{
    "status": "firing",
    "commonLabels": {
      "alertname": "HighServiceLatency",
      "severity": "critical",
      "service": "test-service"
    },
    "alerts": [{
      "status": "firing",
      "labels": {
        "alertname": "HighServiceLatency",
        "service": "test-service"
      },
      "annotations": {
        "summary": "Test incident"
      }
    }]
  }'
```

### View Execution

1. Go to **Executions** tab in n8n
2. Click on the execution to see detailed flow
3. Each node shows input/output data

## Workflow Nodes Explained

### 1. Incident Alert Received (Webhook)
- Receives POST from Alertmanager
- Extracts alert data
- Triggers the workflow

### 2. Acknowledge Alert (Respond to Webhook)
- Immediately responds to Alertmanager
- Returns incident ID
- Prevents timeout

### 3. Monitor Agent (HTTP Request)
- Calls `/monitor` endpoint
- Discovers all services
- Collects metrics
- Scores anomalies

### 4. Correlation Agent (HTTP Request)
- Calls `/correlate` endpoint
- Builds dependency graph
- Identifies affected services
- Ranks root cause candidates

### 5. RCA Agent (HTTP Request)
- Calls `/rca` endpoint
- GPT-4o analyzes incident
- Determines root cause
- Provides confidence score

### 6. Remediation Agent (HTTP Request)
- Calls `/remediate` endpoint
- GPT-4o selects best action
- Generates kubectl command
- Creates rollback plan

### 7. Send Slack Approval Request (Slack)
- Posts rich message to Slack
- Includes all incident details
- Shows metrics, diagnosis, recommended action
- Provides APPROVE/DENY buttons

### 8. Wait for SRE Approval (Webhook)
- Pauses workflow
- Waits for button click in Slack
- Receives approval/denial

### 9. Approved? (IF)
- Checks approval status
- Routes to execution or denial

### 10. K8s Operator — Execute (HTTP Request)
- Calls `/execute` endpoint
- Runs kubectl command
- Waits for rollout completion

### 11. Validate Recovery (HTTP Request)
- Calls `/validate` endpoint
- Re-checks metrics
- Confirms anomaly scores dropped

### 12. Documentation Agent (HTTP Request)
- Calls `/document` endpoint
- GPT-4o writes incident report
- Saves to database for learning

### 13. Post Resolution Report (Slack)
- Posts final report to Slack
- Includes timeline, root cause, resolution
- Marks incident as resolved

### 14. Notify Denial (Slack)
- If denied, notifies team
- Incident requires manual investigation

## Customization

### Add More Approval Steps

Insert additional IF nodes after approval to add multi-level approvals.

### Add PagerDuty Integration

Add PagerDuty nodes to create/update incidents:
1. After Monitor Agent: Create PagerDuty incident
2. After Documentation: Resolve PagerDuty incident

### Add Jira Integration

Add Jira nodes to create tickets:
1. After RCA Agent: Create Jira issue
2. After Documentation: Add comment with resolution

### Add Email Notifications

Add Email nodes at key points:
1. After RCA: Email summary to on-call
2. After Resolution: Email final report

## Monitoring the Workflow

### Execution History

- View all executions in **Executions** tab
- Filter by status: Success, Error, Waiting
- See execution time for each node

### Error Handling

The workflow includes error handling:
- Failed HTTP requests retry 3 times
- Timeouts are set appropriately
- Errors are logged to n8n

### Performance

Typical execution times:
- Monitor Agent: 5-10s
- Correlation Agent: 2-3s
- RCA Agent: 5-10s (GPT)
- Remediation Agent: 3-5s (GPT)
- Execution: 30-60s (kubectl + rollout)
- Validation: 30-60s (wait + check)
- Documentation: 5-10s (GPT)

**Total (excluding human approval): ~2-3 minutes**

## Troubleshooting

### Workflow doesn't trigger
- Check Alertmanager webhook URL
- Verify n8n webhook is active
- Test with manual curl

### Agent calls fail
- Verify `AIRP_AGENTS_IP` variable
- Check AIRP service is running: `kubectl get svc airp-agents`
- Test agent health: `curl http://$AIRP_IP:8080/health`

### Slack messages don't send
- Check Slack credential is valid
- Verify channel exists
- Re-authenticate if needed

### Approval webhook doesn't work
- Check `N8N_APPROVAL_WEBHOOK` variable
- Verify webhook path matches node
- Test with manual curl

## Advanced: Workflow as Code

You can version control and deploy workflows programmatically:

```bash
# Export workflow
curl -X GET https://your-instance.app.n8n.cloud/api/v1/workflows/123 \
  -H "X-N8N-API-KEY: your-api-key" > workflow.json

# Import workflow
curl -X POST https://your-instance.app.n8n.cloud/api/v1/workflows \
  -H "X-N8N-API-KEY: your-api-key" \
  -H "Content-Type: application/json" \
  -d @workflow.json
```

## Screenshots

See `screenshots/` directory for visual workflow diagrams.

## License

MIT License - see [LICENSE](../LICENSE)
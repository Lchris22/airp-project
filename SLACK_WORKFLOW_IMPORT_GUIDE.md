# Import AIRP Workflow with Slack Integration

Since you've already configured Slack credentials in n8n (using access token and signature secret), follow these steps to import and activate the full workflow with Slack approval integration.

---

## Option 1: Manual Import via n8n UI (Recommended)

### Step 1: Access n8n
```bash
kubectl port-forward -n n8n svc/n8n 5678:80
```
Then open: http://localhost:5678

### Step 2: Import Workflow
1. Click **"Add workflow"** (+ button in top right)
2. Click **"Import from File"**
3. Select: `workflows/airp-incident-resolution.json`
4. Click **"Import"**

### Step 3: Configure Slack Nodes
The workflow has 3 Slack nodes that need credentials:
1. **"Send Slack Approval Request"** (node-slack-approval)
2. **"Notify Denial"** (node-denied-slack)
3. **"Post Resolution Report to Slack"** (node-final-slack)

For each node:
1. Click on the node
2. In the **"Credential to connect with"** dropdown, select your existing Slack credential
3. In the **"Channel"** field, select `#incidents` (or your preferred channel)
4. Click **"Save"**

### Step 4: Set Environment Variable
1. Go to **Settings** → **Variables**
2. Add variable:
   - **Key:** `AIRP_AGENTS_IP`
   - **Value:** `20.85.151.165`
3. Click **"Save"**

### Step 5: Activate Workflow
1. Click the **"Active"** toggle in the top right
2. Confirm activation

---

## Option 2: Update Existing Workflow

If you want to keep the current workflow (ID: `lZ4wwdH0HiqD3Yc7`) and just add Slack nodes:

### Step 1: Open Current Workflow
1. Go to http://localhost:5678
2. Open workflow: **"AIRP - Incident Resolution (No Slack)"**

### Step 2: Add Slack Approval Node
After **"Remediation Agent (GPT)"** node:
1. Click **"+"** to add new node
2. Search for **"Slack"**
3. Select **"Send a message"**
4. Configure:
   - **Credential:** Your Slack credential
   - **Channel:** `#incidents`
   - **Message:** Copy from `workflows/airp-incident-resolution.json` line 102-116

### Step 3: Add Approval Webhook
1. Add **"Webhook"** node after Slack message
2. Configure:
   - **HTTP Method:** GET
   - **Path:** `sre-approval`
   - **Response Mode:** Using 'Respond to Webhook' Node

### Step 4: Add IF Node for Approval Check
1. Add **"IF"** node
2. Configure condition: `{{ $json.query.action }} equals approve`

### Step 5: Add Denial Slack Node
1. On the **"false"** branch of IF node
2. Add **"Slack"** node
3. Configure denial message

### Step 6: Add Final Report Slack Node
1. After **"Documentation Agent"**
2. Add **"Slack"** node
3. Configure success message

---

## Workflow Architecture with Slack

```
Incident Alert → Acknowledge → Monitor → Correlate → RCA → Remediate
                                                              ↓
                                                    Send Slack Approval
                                                              ↓
                                                    Wait for SRE Approval
                                                              ↓
                                                         Approved?
                                                        /         \
                                                    YES            NO
                                                     ↓              ↓
                                              K8s Execute    Notify Denial
                                                     ↓
                                                 Validate
                                                     ↓
                                                 Document
                                                     ↓
                                            Post Success to Slack
```

---

## Slack Message Examples

### Approval Request Message
```
🚨 *AIRP INCIDENT DETECTED*

*Incident ID:* {{ $json.incident_id }}
*Severity:* CRITICAL

*📊 Current Metrics:*
• S1 Checkout Latency: {{ $json.metrics.s1_latency_ms }}ms _(threshold: 500ms)_
• S2 DB Pool Usage: {{ $json.metrics.s2_pool_usage_percent }}%
• S3 GC Pause: {{ $json.metrics.s3_gc_pause_ms }}ms

*🔍 Root Cause (AI Analysis):*
{{ $json.diagnosis.primary_root_cause }}

*🔧 Recommended Action:*
{{ $json.remediation_plan.recommended_action.description }}
`{{ $json.remediation_plan.recommended_action.kubectl_command }}`

*Risk Level:* {{ $json.remediation_plan.risk_level }}
*AI Confidence:* {{ Math.round($json.remediation_plan.confidence_score * 100) }}%

*Rollback Plan:* {{ $json.remediation_plan.rollback_plan.description }}

✅ <{{ $vars.N8N_APPROVAL_WEBHOOK }}?action=approve&incident={{ $json.incident_id }}|APPROVE FIX>
❌ <{{ $vars.N8N_APPROVAL_WEBHOOK }}?action=deny&incident={{ $json.incident_id }}|DENY>
```

### Success Message
```
✅ *AIRP: INCIDENT RESOLVED*

*{{ $json.report.title }}*

*Summary:* {{ $json.report.summary }}

*Root Cause:* {{ $json.report.root_cause }}

*Resolution:* {{ $json.report.resolution }}

*Prevention:* {{ $json.report.prevention }}

_Full report filed under incident ID: {{ $json.incident_id }}_
```

---

## Testing the Workflow

### Step 1: Trigger Test Incident
```bash
curl -X POST http://localhost:5678/webhook/incident-trigger \
  -H "Content-Type: application/json" \
  -d '{
    "alertname": "HighCheckoutLatency",
    "severity": "critical",
    "service": "s1-checkout",
    "metrics": {
      "s1_latency_ms": 750,
      "s2_pool_usage_percent": 85,
      "s3_gc_pause_ms": 250
    }
  }'
```

### Step 2: Check Slack
1. Go to your `#incidents` channel
2. You should see the approval request message
3. Click **"APPROVE FIX"** or **"DENY"**

### Step 3: Monitor Execution
1. Go to n8n: http://localhost:5678/executions
2. Watch the workflow execution in real-time
3. Verify all 7 agents are called

### Step 4: Verify Resolution
1. Check Slack for final success message
2. Query database for incident record:
```bash
kubectl exec -it -n shopfast deployment/postgres -- \
  psql -U airp -d airp -c \
  "SELECT * FROM incidents ORDER BY created_at DESC LIMIT 1;"
```

---

## Approval Webhook URL

The approval webhook URL needs to be accessible from Slack. Since we're running locally, you have two options:

### Option 1: Use ngrok (for testing)
```bash
ngrok http 5678
```
Then update the `N8N_APPROVAL_WEBHOOK` variable with the ngrok URL:
```
https://your-ngrok-url.ngrok.io/webhook/sre-approval
```

### Option 2: Use Kubernetes Ingress (for production)
1. Set up an Ingress controller
2. Create Ingress for n8n service
3. Use the public domain in the approval webhook URL

---

## Troubleshooting

### Issue: Slack nodes show "Missing Credential"
**Solution:** Make sure you've selected your Slack credential in each Slack node's configuration.

### Issue: Approval links don't work
**Solution:** The webhook URL must be publicly accessible. Use ngrok for local testing or set up proper Ingress for production.

### Issue: Workflow fails at Slack node
**Solution:** 
1. Check Slack credential is valid
2. Verify the bot has permission to post in `#incidents` channel
3. Check n8n logs: `kubectl logs -n n8n deployment/n8n`

### Issue: "Channel not found"
**Solution:** 
1. Make sure the Slack bot is invited to the `#incidents` channel
2. In Slack, type: `/invite @your-bot-name` in the channel

---

## Next Steps

1. ✅ Import workflow with Slack integration
2. ✅ Configure Slack credentials on all 3 nodes
3. ✅ Set AIRP_AGENTS_IP variable
4. ✅ Activate workflow
5. ✅ Test with sample incident
6. ✅ Verify approval flow works
7. ✅ Monitor first real incident

---

## Current Status

- ✅ Slack credentials configured in n8n (access token + signature secret)
- ✅ AIRP agents running at 20.85.151.165:8080
- ✅ Simplified workflow active (ID: lZ4wwdH0HiqD3Yc7)
- ⏳ Full workflow with Slack pending import

Once you complete the import, the full autonomous incident resolution system with human approval gates will be operational!
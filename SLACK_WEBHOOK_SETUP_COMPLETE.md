# AIRP Slack Webhook Integration - Complete ✅

**Status:** ✅ Active and Ready
**Workflow ID:** `Neri3xEBbnQx4IHA`
**Slack Webhook:** `<YOUR_SLACK_WEBHOOK_URL>` (configured in workflow)

---

## ✅ What's Configured

The AIRP workflow now includes **3 Slack notification points** using your Incoming Webhook:

### 1. **Approval Request** (After Remediation Planning)
Sends incident details with APPROVE/DENY buttons to your Slack channel.

**Message includes:**
- Incident ID and severity
- Current metrics (latency, DB pool, GC pause)
- AI-generated root cause analysis
- Recommended remediation action with kubectl command
- Risk level and AI confidence score
- Rollback plan
- Interactive approval buttons

### 2. **Denial Notification** (If SRE Denies)
Notifies team when remediation is denied by SRE.

**Message includes:**
- Incident ID
- Denial confirmation
- Request for manual investigation

### 3. **Resolution Report** (After Successful Remediation)
Posts final incident report after successful resolution.

**Message includes:**
- Incident summary
- Root cause
- Resolution steps taken
- Prevention recommendations
- Incident ID for reference

---

## 🔗 Webhook Configuration

Your Slack webhook is configured in **3 HTTP Request nodes**:

| Node Name | Purpose | Position in Flow |
|-----------|---------|------------------|
| Send Slack Approval Request | Request SRE approval | After Remediation Agent |
| Notify Denial | Alert on denial | After approval check (false branch) |
| Post Resolution Report to Slack | Success notification | After Documentation Agent |

**Webhook URL:** All 3 nodes use the same incoming webhook URL you provided.

---

## 🧪 Testing the Workflow

### Test 1: Trigger Test Incident
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
    },
    "incident_id": "TEST-'$(date +%s)'"
  }'
```

### Test 2: Check Slack Channel
1. Go to your Slack workspace
2. Check the channel where the webhook posts (usually #general or a custom channel)
3. You should see the approval request message

### Test 3: Approve/Deny
Click the **APPROVE FIX** or **DENY** button in the Slack message.

**Note:** For the approval buttons to work, you need to set up the `N8N_APPROVAL_WEBHOOK` variable:
```bash
# In n8n UI: Settings → Variables
Key: N8N_APPROVAL_WEBHOOK
Value: http://your-n8n-url/webhook/sre-approval
```

For local testing, use ngrok:
```bash
ngrok http 5678
# Then use: https://your-ngrok-url.ngrok.io/webhook/sre-approval
```

---

## 📊 Workflow Status

### Active Workflow
- **ID:** `Neri3xEBbnQx4IHA`
- **Name:** AIRP - Incident Resolution (Webhook)
- **Status:** ✅ Active
- **Trigger:** Webhook at `/webhook/incident-trigger`

### Previous Workflows (Deactivated)
- `lZ4wwdH0HiqD3Yc7` - AIRP - Incident Resolution (No Slack) - ⏸️ Deactivated
- `VNdvvpxwqvZCAT74` - AIRP - Incident Resolution Workflow - ⏸️ Inactive
- `0L234Gf7Z5cPTWMh` - AIRP - Incident Resolution Workflow - ⏸️ Inactive
- `hyZXDAWnq95eJMDl` - AIRP - Incident Resolution Workflow - ⏸️ Inactive

---

## 🔄 Complete Workflow Flow

```
1. Prometheus Alert → Alertmanager
2. Alertmanager → n8n Webhook (/webhook/incident-trigger)
3. n8n: Acknowledge Alert
4. n8n: Monitor Agent (collect metrics)
5. n8n: Correlation Agent (identify dependencies)
6. n8n: RCA Agent (GPT-4o analysis)
7. n8n: Remediation Agent (GPT-4o planning)
8. n8n: Send Slack Approval Request ← 📱 SLACK MESSAGE #1
9. n8n: Wait for SRE Approval (webhook)
10. SRE: Click APPROVE or DENY in Slack
    ├─ If APPROVED:
    │   11. n8n: K8s Operator (execute kubectl)
    │   12. n8n: Validate Recovery
    │   13. n8n: Documentation Agent
    │   14. n8n: Post Resolution to Slack ← 📱 SLACK MESSAGE #3
    └─ If DENIED:
        11. n8n: Notify Denial ← 📱 SLACK MESSAGE #2
```

---

## 🎯 Key Features

### ✅ Implemented
- [x] Slack incoming webhook integration
- [x] 3 notification points (approval, denial, success)
- [x] Rich formatted messages with incident details
- [x] Interactive approval buttons (requires public webhook URL)
- [x] Automatic workflow activation
- [x] No OAuth2 credentials needed

### ⏳ Pending (Optional)
- [ ] Public webhook URL for approval buttons (use ngrok for testing)
- [ ] Custom Slack channel configuration
- [ ] Slack thread replies for updates
- [ ] @mention specific users for approvals

---

## 🛠️ Troubleshooting

### Issue: Not receiving Slack messages
**Check:**
1. Webhook URL is correct in all 3 nodes
2. Workflow is active: `curl -s http://localhost:5678/api/v1/workflows/Neri3xEBbnQx4IHA -H "X-N8N-API-KEY: YOUR_TOKEN" | jq .active`
3. Trigger the workflow and check n8n execution logs
4. Verify Slack webhook is not revoked

### Issue: Approval buttons don't work
**Solution:**
The approval webhook needs to be publicly accessible. Options:
1. **For testing:** Use ngrok: `ngrok http 5678`
2. **For production:** Set up Kubernetes Ingress with public domain

### Issue: Messages appear in wrong channel
**Solution:**
Slack incoming webhooks post to a specific channel configured when you created the webhook. To change:
1. Go to Slack App settings
2. Regenerate webhook for different channel
3. Update all 3 nodes in n8n workflow

---

## 📝 Next Steps

1. ✅ **Test the workflow** with a sample incident
2. ✅ **Verify Slack messages** appear correctly
3. ⏳ **Set up ngrok** for approval button testing (optional)
4. ⏳ **Configure production Ingress** for permanent approval URL
5. ⏳ **Monitor first real incident** end-to-end
6. ⏳ **Train SRE team** on approval process

---

## 📚 Related Documentation

- [`AIRP_DEPLOYMENT_COMPLETE.md`](AIRP_DEPLOYMENT_COMPLETE.md) - Full deployment summary
- [`SLACK_WORKFLOW_IMPORT_GUIDE.md`](SLACK_WORKFLOW_IMPORT_GUIDE.md) - OAuth2 setup guide (alternative)
- [`N8N_API_TOKEN_GUIDE.md`](N8N_API_TOKEN_GUIDE.md) - API token usage
- [`scripts/test-airp-system.sh`](scripts/test-airp-system.sh) - System health check

---

**Congratulations! Your AIRP system now has full Slack integration! 🎉**

The system will automatically notify your team when incidents are detected, request approval for remediation actions, and report successful resolutions - all through Slack!
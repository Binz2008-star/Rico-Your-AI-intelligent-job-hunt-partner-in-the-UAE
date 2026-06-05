# Vercel Deploy Diagnoser Agent

A read-only Claude Managed Agent that monitors failed Vercel deployments, diagnoses root causes, and reports findings to Slack for on-call engineers.

## Purpose

- Automatically diagnose failed Vercel deployments
- Provide actionable root cause analysis
- Alert on-call engineers via Slack
- Maintain deployment audit trail

## Architecture

### Input
- Vercel deployment webhook (failed deployments only)
- GitHub commit metadata (via MCP)

### Processing
- Fetch deployment details from Vercel MCP
- Fetch commit details from GitHub MCP
- Analyze build logs and error messages
- Identify root cause and affected files

### Output
- Formatted Slack message with diagnosis
- Tags on-call engineer
- Provides suggested fix steps

## Prerequisites

### 1. MCP Server Configuration

Configure these MCP servers in your MCP client:

#### Vercel MCP
```json
{
  "type": "url",
  "name": "vercel",
  "url": "https://mcp.vercel.com/mcp"
}
```

#### GitHub MCP
```json
{
  "type": "url",
  "name": "github",
  "url": "https://api.githubcopilot.com/mcp/"
}
```

#### Slack MCP
```json
{
  "type": "url",
  "name": "slack",
  "url": "https://mcp.slack.com/mcp"
}
```

### 2. Authentication

**Vercel MCP:**
- Requires Vercel API token
- Set via MCP server configuration or environment variable

**GitHub MCP:**
- Requires GitHub Personal Access Token
- Set via MCP server configuration or environment variable
- Must have `repo` scope for the target repository

**Slack MCP:**
- Requires Slack Bot Token with `chat:write` scope
- Requires Slack App installed in target workspace
- Bot must be invited to target channel

### 3. Environment Variables

Set these before creating the agent:

```bash
# Required
SLACK_CHANNEL_ID=C1234567890
ON_CALL_HANDLE=@oncall-engineer
GITHUB_REPO=Binz2008-star/Rico-Your-AI-intelligent-job-hunt-partner-in-the-UAE
VERCEL_PROJECT_ID=prj_xyz789
VERCEL_TEAM_ID=team_def456

# Optional
TEST_MODE=true
TEST_SLACK_CHANNEL_ID=C0987654321
```

### 4. Persistent Deduplication

Choose one of the following for deployment deduplication:

**Option A: Database (Recommended)**
- PostgreSQL table: `processed_deployments(deployment_id, processed_at)`
- Configure connection string in environment

**Option B: KV Store**
- Redis or similar key-value store
- Key: `deploy:{deployment_id}` with TTL

**Option C: GitHub Issue Comment**
- Create a tracking issue for deployment failures
- Add comments with deployment IDs as markers
- Check for existing comments before posting

**Option D: Manual Mode Only**
- If no persistent store is available
- Agent only posts when explicitly triggered (manual mode)
- No automatic webhook processing

## Setup Instructions

### Step 1: Configure MCP Servers

Add MCP server URLs to your MCP client configuration file (e.g., `~/.codeium/windsurf/mcp_config.json`):

```json
{
  "mcpServers": {
    "vercel": {
      "serverUrl": "https://mcp.vercel.com/mcp"
    },
    "github": {
      "serverUrl": "https://api.githubcopilot.com/mcp/"
    },
    "slack": {
      "serverUrl": "https://mcp.slack.com/mcp"
    }
  }
}
```

### Step 2: Set Up Slack Bot

1. Create a Slack App at https://api.slack.com/apps
2. Enable Bot Token Scopes: `chat:write`
3. Install app to your workspace
4. Invite bot to target channel: `/invite @YourBotName`
5. Copy Bot Token (starts with `xoxb-`)

### Step 3: Configure Vercel Webhook

1. Go to Vercel project settings
2. Navigate to Webhooks
3. Create new webhook for deployment events
4. Filter: `deployment.error` only
5. Set webhook URL to your agent endpoint (when deployed)

### Step 4: Test MCP Connections

Test each MCP server independently before creating the agent:

```bash
# Test Vercel MCP
# (Use MCP client test tools)

# Test GitHub MCP
# (Use MCP client test tools)

# Test Slack MCP
# (Use MCP client test tools)
```

### Step 5: Create Test Slack Channel

Create a dedicated test channel (e.g., `#deploy-diagnostics-test`) for initial testing.

### Step 6: Create the Agent

After all prerequisites are met, run the create command (see below).

## Testing

### Manual Test

Use the provided `test-payload.json` to test the agent:

```bash
# Trigger agent with test payload
# (Method depends on your agent deployment)
```

### Expected Output

The agent should post a message to the test Slack channel with:

```
[TEST] 🚨 **Deployment Failed**

**Project**: rico-hunt-frontend
**Environment**: production
**Branch**: codex/job-quality-core-profile-jsearch
**Commit**: abc123de by loyal
**Deployment ID**: dpl_abc123xyz456

---

**Summary**: TypeScript type error in Dashboard component

**Root Cause**: Type 'undefined' is not assignable to type 'string' at apps/web/components/Dashboard.tsx:45:23

**Affected Files**:
- apps/web/components/Dashboard.tsx

**Suggested Fix**:
1. Check line 45 in Dashboard.tsx
2. Ensure the variable is properly typed or initialized
3. Add null check if the value can be undefined

**Severity**: Medium

---
```

### Verification Checklist

- [ ] MCP servers are accessible
- [ ] Slack bot can post to test channel
- [ ] Vercel deployment details are fetchable
- [ ] GitHub commit details are fetchable
- [ ] Deduplication store is configured
- [ ] Test payload produces expected output
- [ ] No secrets appear in output
- [ ] Agent is read-only (no code changes)

## Security Considerations

### Secrets Management
- Never commit API keys or tokens
- Use environment variables for all credentials
- Rotate tokens regularly
- Use least-privilege scopes

### Data Privacy
- Mask sensitive values from logs before posting
- Do not include user data in Slack messages
- Reference environment variables by name only

### Access Control
- Restrict Slack channel access to authorized personnel
- Limit Vercel webhook to production deployments only
- Use separate test channel for development

## Troubleshooting

### Agent Not Posting to Slack
- Verify Slack bot token is valid
- Check bot is invited to channel
- Confirm channel ID is correct
- Check MCP server logs

### Vercel Details Not Fetching
- Verify Vercel API token has correct scopes
- Check project ID and team ID are correct
- Ensure MCP server URL is accessible

### GitHub Details Not Fetching
- Verify GitHub token has `repo` scope
- Check repository format: `owner/repo`
- Ensure repository is accessible

### Duplicate Posts
- Verify deduplication store is working
- Check deployment ID key is unique
- Review deduplication logic

## Maintenance

### Regular Tasks
- Rotate API tokens quarterly
- Review and update system prompt as needed
- Monitor Slack channel for agent activity
- Update affected file patterns as codebase evolves

### Monitoring
- Track agent invocation frequency
- Monitor false positive rate
- Review diagnosis accuracy
- Collect feedback from on-call engineers

## Files

- `system-prompt.md` - Full agent system prompt
- `test-payload.json` - Sample failed deployment payload
- `README.md` - This file

## License

Internal use only for Rico Hunt project.

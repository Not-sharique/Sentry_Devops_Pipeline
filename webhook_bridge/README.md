# Webhook Bridge (Sentry -> Azure DevOps)

This Azure Functions app receives Sentry webhooks and creates Azure DevOps
work items.

## Local setup

1. Copy `local.settings.json.example` to `local.settings.json`.
2. Fill in `ADO_ORG`, `ADO_PROJECT`, and `ADO_PAT`.
3. Set `SENTRY_WEBHOOK_SECRET` to match the secret you configure in Sentry.
4. Run:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
func start
```

The function will listen on `/api/sentry-webhook`.

## Environment variables

- `SENTRY_WEBHOOK_SECRET`: shared secret validated against Sentry header.
- `SENTRY_TITLE_PREFIX`: optional title prefix (default `Sentry`).
- `ADO_BASE_URL`: base URL for Azure DevOps (default `https://dev.azure.com`).
- `ADO_ORG`: Azure DevOps organization.
- `ADO_PROJECT`: Azure DevOps project.
- `ADO_PAT`: Azure DevOps personal access token.
- `ADO_WORK_ITEM_TYPE`: work item type, for example `Issue` or `Bug`.
- `ADO_AREA_PATH`: optional area path.
- `ADO_ITERATION_PATH`: optional iteration path.
- `ADO_TAGS`: semicolon-separated tags to add.

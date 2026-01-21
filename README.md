# Sentry -> Azure DevOps Pipeline (Webhook Bridge)

This repo contains a Python-based Azure Function that receives Sentry webhooks
and creates Azure DevOps work items, plus an Azure Pipelines YAML to build/test
and deploy the bridge.

## Repo layout

- `azure-pipelines.yml`: build/test pipeline and optional deploy stage.
- `webhook_bridge/`: Azure Functions app for the webhook bridge.
- `src/`, `tests/`: minimal Python app + tests to validate pipeline.

## Step-by-step setup

1. Create an Azure DevOps Personal Access Token (PAT) with **Work Items (read/write)**.
2. Create an Azure Function App (Linux) with Python 3.11 runtime.
3. In the Function App configuration, add these app settings:
   - `ADO_ORG`, `ADO_PROJECT`, `ADO_PAT`, `ADO_WORK_ITEM_TYPE`
   - `SENTRY_WEBHOOK_SECRET` (use a strong secret)
4. Create a service connection in Azure DevOps (service principal) to the
   subscription that hosts the Function App.
5. Create a pipeline in Azure DevOps using `azure-pipelines.yml`, and set:
   - `azureSubscription` = name of the service connection
   - `functionAppName` = name of the Function App
6. In Sentry, add a webhook (Issue Alert -> Webhook action) pointing to:
   - `https://<functionapp>.azurewebsites.net/api/sentry-webhook`
   - This function uses anonymous auth by default and validates `SENTRY_WEBHOOK_SECRET`.
     If you change auth to `FUNCTION`, append `?code=<function key>`.
7. Trigger the pipeline to deploy the bridge, then send a test alert from Sentry.

## Local test

See `webhook_bridge/README.md` for local run instructions.

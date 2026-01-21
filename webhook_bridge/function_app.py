import hmac
import html
import json
import logging
import os
from typing import Any, Dict, Optional, Tuple

import azure.functions as func
import requests

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)
logger = logging.getLogger("webhook_bridge")


def _dig(payload: Dict[str, Any], *keys: str) -> Optional[Any]:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _load_config() -> Tuple[Optional[Dict[str, str]], Optional[str]]:
    ado_pat = os.getenv("ADO_PAT")
    ado_org = os.getenv("ADO_ORG")
    ado_project = os.getenv("ADO_PROJECT")
    if not ado_pat or not ado_org or not ado_project:
        return None, "Missing required ADO_ORG, ADO_PROJECT, or ADO_PAT."

    config = {
        "ado_base_url": os.getenv("ADO_BASE_URL", "https://dev.azure.com"),
        "ado_org": ado_org,
        "ado_project": ado_project,
        "ado_pat": ado_pat,
        "ado_work_item_type": os.getenv("ADO_WORK_ITEM_TYPE", "Issue"),
        "ado_area_path": os.getenv("ADO_AREA_PATH", ""),
        "ado_iteration_path": os.getenv("ADO_ITERATION_PATH", ""),
        "ado_tags": os.getenv("ADO_TAGS", ""),
        "sentry_webhook_secret": os.getenv("SENTRY_WEBHOOK_SECRET", ""),
        "sentry_title_prefix": os.getenv("SENTRY_TITLE_PREFIX", "Sentry"),
    }
    return config, None


def _verify_secret(req: func.HttpRequest, secret: str) -> Tuple[bool, str]:
    if not secret:
        return True, ""

    token = (
        req.headers.get("X-Sentry-Token")
        or req.headers.get("X-Sentry-Signature")
        or req.headers.get("X-Sentry-Secret")
    )
    if not token:
        return False, "Missing Sentry secret header."
    if hmac.compare_digest(token, secret):
        return True, ""
    return False, "Invalid Sentry secret."


def _extract_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    event = payload.get("event") or _dig(payload, "data", "event") or {}
    issue = (
        payload.get("issue")
        or _dig(payload, "data", "issue")
        or _dig(payload, "data", "group")
        or payload.get("group")
        or {}
    )
    project = payload.get("project") or _dig(payload, "data", "project") or {}
    return {
        "event": event if isinstance(event, dict) else {},
        "issue": issue if isinstance(issue, dict) else {},
        "project": project if isinstance(project, dict) else project,
    }


def _normalize_tags(tag_value: str) -> str:
    tags = [tag.strip() for tag in tag_value.split(";") if tag.strip()]
    return ";".join(tags)


def _build_description(details: Dict[str, Any]) -> str:
    def add_line(label: str, value: Optional[str]) -> str:
        if not value:
            return ""
        return f"<p><b>{html.escape(label)}</b>: {html.escape(value)}</p>"

    lines = ["<p>Created from Sentry webhook.</p>"]
    lines.append(add_line("Project", details.get("project")))
    lines.append(add_line("Issue ID", details.get("issue_id")))
    lines.append(add_line("Event ID", details.get("event_id")))
    lines.append(add_line("Level", details.get("level")))
    lines.append(add_line("Environment", details.get("environment")))
    lines.append(add_line("Culprit", details.get("culprit")))

    issue_url = details.get("issue_url")
    event_url = details.get("event_url")
    if issue_url or event_url:
        links = []
        if issue_url:
            links.append(f"<a href=\"{html.escape(issue_url)}\">Issue</a>")
        if event_url:
            links.append(f"<a href=\"{html.escape(event_url)}\">Event</a>")
        lines.append(f"<p><b>Links</b>: {' | '.join(links)}</p>")

    return "".join([line for line in lines if line])


def _build_work_item_fields(
    payload: Dict[str, Any], config: Dict[str, str]
) -> Dict[str, str]:
    extracted = _extract_payload(payload)
    event = extracted["event"]
    issue = extracted["issue"]
    project = extracted["project"]

    project_name = ""
    if isinstance(project, dict):
        project_name = project.get("name") or project.get("slug") or ""
    elif isinstance(project, str):
        project_name = project

    issue_id = (
        issue.get("id")
        or issue.get("short_id")
        or issue.get("shortId")
        or issue.get("shortID")
    )
    issue_url = issue.get("url") or issue.get("web_url") or payload.get("url")
    event_id = event.get("event_id") or event.get("id")
    event_url = event.get("url") or event.get("web_url")
    title = (
        event.get("title")
        or issue.get("title")
        or event.get("message")
        or issue.get("culprit")
        or "Sentry issue"
    )
    if config.get("sentry_title_prefix"):
        title = f"{config['sentry_title_prefix']}: {title}"

    details = {
        "project": project_name or "",
        "issue_id": str(issue_id) if issue_id else "",
        "event_id": str(event_id) if event_id else "",
        "level": str(event.get("level") or issue.get("level") or ""),
        "environment": str(event.get("environment") or issue.get("environment") or ""),
        "culprit": str(event.get("culprit") or issue.get("culprit") or ""),
        "issue_url": str(issue_url) if issue_url else "",
        "event_url": str(event_url) if event_url else "",
    }
    description = _build_description(details)

    tags = []
    if config.get("ado_tags"):
        tags.append(config["ado_tags"])
    tags.append("Sentry")
    if issue_id:
        tags.append(f"SentryIssue{issue_id}")
    tag_value = _normalize_tags(";".join(tags))

    fields = {
        "System.Title": title,
        "System.Description": description,
    }
    if config.get("ado_area_path"):
        fields["System.AreaPath"] = config["ado_area_path"]
    if config.get("ado_iteration_path"):
        fields["System.IterationPath"] = config["ado_iteration_path"]
    if tag_value:
        fields["System.Tags"] = tag_value

    return fields


def _create_work_item(
    config: Dict[str, str], fields: Dict[str, str]
) -> requests.Response:
    base_url = config["ado_base_url"].rstrip("/")
    org = config["ado_org"]
    project = config["ado_project"]
    work_item_type = config["ado_work_item_type"]
    url = (
        f"{base_url}/{org}/{project}/_apis/wit/workitems/${work_item_type}"
        "?api-version=7.1-preview.3"
    )

    patch = []
    for field, value in fields.items():
        patch.append({"op": "add", "path": f"/fields/{field}", "value": value})

    headers = {"Content-Type": "application/json-patch+json"}
    return requests.post(
        url, headers=headers, auth=("", config["ado_pat"]), json=patch, timeout=10
    )


@app.route(route="sentry-webhook", methods=["POST"])
def sentry_webhook(req: func.HttpRequest) -> func.HttpResponse:
    try:
        payload = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON payload.", status_code=400)

    config, error = _load_config()
    if error or not config:
        logger.error("Config error: %s", error)
        return func.HttpResponse(error or "Config error.", status_code=500)

    ok, reason = _verify_secret(req, config["sentry_webhook_secret"])
    if not ok:
        return func.HttpResponse(reason, status_code=401)

    fields = _build_work_item_fields(payload, config)
    response = _create_work_item(config, fields)

    if response.status_code in (200, 201):
        body = {}
        try:
            body = response.json()
        except ValueError:
            body = {}
        result = {"status": "created", "work_item_id": body.get("id")}
        return func.HttpResponse(
            json.dumps(result), status_code=201, mimetype="application/json"
        )

    logger.error(
        "Azure DevOps error %s: %s", response.status_code, response.text[:1000]
    )
    return func.HttpResponse(
        "Azure DevOps work item creation failed.", status_code=502
    )

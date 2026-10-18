"""Where incident briefs go. Each sink is optional and failure-isolated."""

from __future__ import annotations

import logging

import httpx

log = logging.getLogger(__name__)


def post_slack(webhook_url: str | None, text: str, transport: httpx.BaseTransport | None = None) -> bool:
    if not webhook_url:
        return False
    try:
        with httpx.Client(timeout=5.0, transport=transport) as c:
            c.post(webhook_url, json={"text": text}).raise_for_status()
        return True
    except httpx.HTTPError as exc:
        log.warning("slack sink failed: %s", exc)
        return False


def open_github_issue(
    token: str | None, repo: str | None, title: str, body: str, transport: httpx.BaseTransport | None = None
) -> str | None:
    if not (token and repo):
        return None
    try:
        with httpx.Client(timeout=10.0, transport=transport) as c:
            resp = c.post(
                f"https://api.github.com/repos/{repo}/issues",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                json={"title": title, "body": body, "labels": ["incident", "copilot"]},
            )
            resp.raise_for_status()
            return resp.json().get("html_url")
    except httpx.HTTPError as exc:
        log.warning("github sink failed: %s", exc)
        return None

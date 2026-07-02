"""
src/api/routers/email_alerts.py
Public, login-free endpoints for email job alerts.

Currently exposes one-click unsubscribe. This route is intentionally
unauthenticated: it is reached from a link inside an alert email, identifies the
user solely by an opaque unsubscribe token, and can only ever opt a user OUT
(never in). It returns a small HTML confirmation page so a click in any mail
client lands on something friendly.
"""
from __future__ import annotations

import html as _html

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from src.services.email_notifications import unsubscribe_by_token

router = APIRouter(prefix="/api/v1/email", tags=["email-alerts"])


def _page(title: str, message: str) -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{_html.escape(title)}</title></head>"
        "<body style='font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;"
        "max-width:520px;margin:64px auto;padding:0 20px;color:#1a1a1a;line-height:1.5'>"
        f"<h1 style='font-size:20px'>{_html.escape(title)}</h1>"
        f"<p>{_html.escape(message)}</p>"
        "<p style='margin-top:24px'><a href='https://ricohunt.com' "
        "style='color:#2563eb;text-decoration:none'>Back to Rico &rarr;</a></p>"
        "</body></html>"
    )


@router.get("/unsubscribe", response_class=HTMLResponse)
def unsubscribe(token: str = "") -> HTMLResponse:
    """One-click unsubscribe from email job alerts via an opaque token.

    Always returns 200 with an HTML page. An invalid/expired token yields a
    neutral message (no user enumeration) rather than an error. Re-clicking an
    already-unsubscribed link is idempotent and shows the success page.
    """
    if unsubscribe_by_token(token):
        return HTMLResponse(
            _page(
                "You're unsubscribed",
                "You will no longer receive job-alert emails from Rico. "
                "You can re-enable them anytime from your Rico settings.",
            )
        )
    return HTMLResponse(
        _page(
            "Link not recognised",
            "This unsubscribe link is invalid or has expired. You can manage "
            "email alerts anytime from your Rico settings.",
        )
    )

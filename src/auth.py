# src/auth.py
"""
Minimal auth: a single shared API key, not user accounts.

This is deliberately not "log in as a user" -- there's no users table, no
sessions, no passwords. It answers one narrower question: "do you know the
key to use this API at all", appropriate for a project used by one person or
a small trusted group rather than the public. Real per-user accounts (own
job ownership, individual logins) would need a users table and is a
separate, later decision -- see ARCHITECTURE.md.

Configuration: set API_KEY in the environment. If it's unset, auth is
disabled entirely (every request is allowed) -- this keeps local dev
frictionless, but it means forgetting to set API_KEY in a real deployment
silently leaves the API open. Always set it outside local dev.

The key can be supplied two ways, checked in this order:
  - header `X-API-Key: <key>` -- used by every fetch() call the frontend
    makes.
  - query param `?api_key=<key>` -- the header path doesn't work for the
    document viewer, which points a plain <iframe src="..."> / browser
    download at GET /audits/{id}/document and can't attach a custom header
    to that request. This is a materially weaker way to send a secret (it
    can land in server logs or browser history), acceptable here only
    because it's the same single low-sensitivity shared key, not a
    per-user credential.
"""
import os
from typing import Optional

from fastapi import Header, HTTPException, Query, status


def require_api_key(
    x_api_key: Optional[str] = Header(None),
    api_key: Optional[str] = Query(None),
) -> None:
    expected = os.environ.get("API_KEY")
    if not expected:
        return  # auth disabled -- no key configured

    supplied = x_api_key or api_key
    if supplied != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")

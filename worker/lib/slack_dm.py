"""One Slack DM from the "Vlad's Claude Code" app (Empact workspace). Token from env SLACK_BOT_TOKEN.

No link previews: a run report is read in a DM, and an unfurled GitHub card buries it.
"""
from __future__ import annotations

import json
import os
import urllib.request


def send(user_id: str, text: str) -> None:
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        raise RuntimeError("SLACK_BOT_TOKEN is not set")
    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=json.dumps({"channel": user_id, "text": text, "unfurl_links": False, "unfurl_media": False}).encode(),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        out = json.loads(r.read())
    if not out.get("ok"):
        raise RuntimeError(f"slack: {out.get('error')}")

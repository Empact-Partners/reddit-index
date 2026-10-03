"""One Slack DM from the "Vlad's Claude Code" app (Empact workspace). Token from env SLACK_BOT_TOKEN.

No link previews: a run report is read in a DM, and an unfurled GitHub card buries it.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request


def send(user_id: str, text: str) -> None:
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:   # on the laptop: the estate's token helper (the Empact workspace's bot)
        sys.path.insert(0, os.path.expanduser("~/.claude/api_helpers"))
        try:
            import tokens
            token = tokens.slack_bot_token("empact")
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"no Slack token: SLACK_BOT_TOKEN is not set and the local helper failed ({e})")
    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=json.dumps({"channel": user_id, "text": text, "unfurl_links": False, "unfurl_media": False}).encode(),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        out = json.loads(r.read())
    if not out.get("ok"):
        raise RuntimeError(f"slack: {out.get('error')}")

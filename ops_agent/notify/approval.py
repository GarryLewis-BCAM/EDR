import json
import time
import urllib.request
from typing import Any, Dict, Optional

def _get(url: str, timeout: float = 10.0) -> Dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    return json.loads(body)

def wait_for_yes_no(bot_token: str, chat_id: int, timeout_seconds: int = 600) -> Optional[bool]:
    deadline = time.time() + timeout_seconds
    offset = None

    while time.time() < deadline:
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates?timeout=0"
        if offset is not None:
            url += f"&offset={offset}"

        data = _get(url)

        if not data.get("ok"):
            time.sleep(2)
            continue

        for upd in data.get("result", []):
            offset = upd.get("update_id", 0) + 1

            msg = upd.get("message") or upd.get("edited_message")
            if not msg:
                continue

            from_chat = msg.get("chat", {}).get("id")
            if int(from_chat) != int(chat_id):
                continue

            text = (msg.get("text") or "").strip().lower()
            if text in ("yes", "y"):
                return True
            if text in ("no", "n"):
                return False

        time.sleep(2)

    return None

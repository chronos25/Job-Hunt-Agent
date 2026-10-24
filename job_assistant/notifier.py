"""Telegram alerts. Without TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID it prints to the console instead."""
import html
import logging
import os

import requests

from .models import Job

log = logging.getLogger(__name__)


def format_alert(job: Job, s: dict) -> str:
    e = html.escape
    score = s["match_score"]
    badge = "🔥" if score >= 85 else "✅"
    lines = [
        f"{badge} <b>{score}%</b> · <b>{e(job.title)}</b>",
        f"🏢 {e(job.company)} ({e(s['company_size_estimate'])})",
        f"📍 {e(job.location)}",
        f"💰 {e(job.salary or '~' + s['salary_estimate_lpa'] + ' LPA (est.)')}",
        f"🧩 {e(s['role_focus'])}",
    ]
    if job.posted:
        lines.append(f"🕒 Posted {e(job.posted)}")
    if s["key_matches"]:
        lines.append("👍 " + e("; ".join(s["key_matches"])))
    if s["gaps"]:
        lines.append("⚠️ " + e("; ".join(s["gaps"])))
    lines += ["", e(s["summary"]), "", f'<a href="{e(job.url)}">Open job</a> · {e(job.source)}']
    return "\n".join(lines)


def send(text: str) -> bool:
    token, chat_id = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("\n" + "-" * 60 + "\n" + text)
        return True
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                  "disable_web_page_preview": True},
            timeout=20,
        )
        r.raise_for_status()
        return True
    except Exception as e:
        log.error("telegram send failed: %s", e)
        return False

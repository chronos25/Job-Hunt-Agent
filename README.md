# Job Search Assistant

Watches LinkedIn, Indeed, Naukri, Instahyre, Remotive and RemoteOK for new backend roles, filters out
irrelevant ones, has Claude score each remaining job against your resume and preferences (company size,
salary, backend focus), and sends good matches to Telegram. Runs every 10 minutes on GitHub Actions.

```
fetch (all sources) → skip already-seen → rule filters → Claude score → Telegram alert (score ≥ 70)
```

## Files
| Path | What it is |
|---|---|
| `config.yaml` | Search terms, locations, filters, salary, alert threshold — edit this |
| `profile/resume.md` | Your resume (git-ignored; on GitHub use the `RESUME_TEXT` secret) |
| `job_assistant/sources.py` | Job site fetchers |
| `job_assistant/filters.py` | Title / location / company-size rules |
| `job_assistant/scorer.py` | Claude scoring |
| `job_assistant/notifier.py` | Telegram messages |
| `data/seen_jobs.json` | Jobs already processed (auto-updated) |

## Run locally
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m job_assistant.main --no-ai --dry-run      # test sources, prints to console
export ANTHROPIC_API_KEY=...  TELEGRAM_BOT_TOKEN=...  TELEGRAM_CHAT_ID=...
.venv/bin/python -m job_assistant.main
```

## Set up on GitHub Actions
1. **Telegram bot** — in Telegram open `@BotFather`, send `/newbot`, copy the token. Send any message to
   your new bot, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy `"chat":{"id": ...}`.
2. **Anthropic API key** — console.anthropic.com → API Keys.
3. **GitHub repo** — create a repo and push this folder.
4. **Secrets** — repo → Settings → Secrets and variables → Actions → New repository secret:
   `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `RESUME_TEXT` (paste resume.md content).
5. **Test** — Actions tab → "Job alerts" → Run workflow. After that it runs on schedule.

## Notes
- GitHub Actions is free and unlimited for **public** repos; private repos get 2,000 min/month, which a
  10-minute schedule exceeds — use `*/30` or a public repo (your resume stays in a secret either way).
- LinkedIn/Naukri/Indeed sometimes block cloud IPs; a blocked source is logged and skipped, others still run.
- Cost: Claude (Opus 5.5, low effort) is called only for jobs that pass the rule filters — roughly
  $0.01–0.03 per scored job. Set `scoring.model: claude-haiku-5-5` in config.yaml to cut that ~20x.

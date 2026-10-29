"""One run: fetch new jobs, filter, score with Claude, alert on Telegram.

Usage:
  python -m job_assistant.main             # normal run
  python -m job_assistant.main --no-ai     # skip Claude; alert every job passing the rule filters
  python -m job_assistant.main --dry-run   # don't save seen jobs (safe for testing)
"""
import argparse
import logging

import yaml

from . import notifier
from .filters import reject_reason
from .sources import fetch_all
from .store import JobLog, SeenStore

log = logging.getLogger("job_assistant")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--no-ai", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    cfg = yaml.safe_load(open(args.config))
    store = SeenStore()
    job_log = JobLog()

    fetched = fetch_all(cfg)
    candidates, batch_keys = [], set()
    for job in fetched:
        if store.seen(job) or job.dedup_key in batch_keys:
            continue
        batch_keys.add(job.dedup_key)
        reason = reject_reason(job, cfg)
        if reason:
            log.debug("skip %s (%s)", job.title, reason)
            store.add(job)
        else:
            candidates.append(job)
    log.info("fetched %d, new %d, passing filters %d", len(fetched), len(batch_keys), len(candidates))

    scfg = cfg["scoring"]
    to_score = candidates[: scfg["max_jobs_per_run"]]
    scorer = None
    if not args.no_ai:
        from .scorer import Scorer
        scorer = Scorer(cfg)

    alerted, low = 0, []
    for job in to_score:
        if scorer is None:
            result = {"match_score": 0, "company_size_estimate": str(job.company_employees or "?"),
                      "large_stable_company": False, "salary_estimate_lpa": "?", "role_focus": "-",
                      "key_matches": [], "gaps": [], "summary": "(AI scoring off)"}
        else:
            result = scorer.score(job)
            if result is None:
                continue  # leave unseen so the next run retries it
        is_match = scorer is None or result["match_score"] >= scfg["min_score_to_alert"]
        if is_match:
            if not notifier.send(notifier.format_alert(job, result)):
                continue  # retry next run
            alerted += 1
        else:
            low.append(f"{result['match_score']}% {job.title} @ {job.company}")
        store.add(job)
        if scorer is not None:
            job_log.add(job, result, alerted=is_match)

    if low and cfg.get("alerts", {}).get("send_rejected_summary"):
        notifier.send("🗂 Low matches skipped:\n" + "\n".join(low))
    log.info("scored %d, alerted %d, below threshold %d", len(to_score), alerted, len(low))

    if not args.dry_run:
        store.save()
        job_log.save(scfg["min_score_to_alert"])


if __name__ == "__main__":
    main()

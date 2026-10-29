"""Remembers jobs already processed so each job is alerted at most once."""
import json
import time
from pathlib import Path

KEEP_DAYS = 30


class SeenStore:
    def __init__(self, path: str = "data/seen_jobs.json"):
        self.path = Path(path)
        data = json.loads(self.path.read_text()) if self.path.exists() else {}
        self.ids: dict[str, float] = data.get("ids", {})
        self.keys: dict[str, float] = data.get("keys", {})

    def seen(self, job) -> bool:
        return job.id in self.ids or job.dedup_key in self.keys

    def add(self, job) -> None:
        now = time.time()
        self.ids[job.id] = now
        self.keys[job.dedup_key] = now

    def save(self) -> None:
        cutoff = time.time() - KEEP_DAYS * 86400
        self.ids = {k: v for k, v in self.ids.items() if v > cutoff}
        self.keys = {k: v for k, v in self.keys.items() if v > cutoff}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"ids": self.ids, "keys": self.keys}, indent=0))


class JobLog:
    """Every scored job with its Claude verdict, read by the portal (docs/index.html)."""

    MAX_JOBS = 1500

    def __init__(self, path: str = "docs/jobs.json"):
        self.path = Path(path)
        data = json.loads(self.path.read_text()) if self.path.exists() else {}
        self.jobs: list[dict] = data.get("jobs", [])

    def add(self, job, result: dict, alerted: bool) -> None:
        self.jobs.append({
            "id": job.id, "source": job.source, "title": job.title, "company": job.company,
            "location": job.location, "url": job.url, "posted": job.posted, "salary": job.salary,
            "company_employees": job.company_employees, "scored_at": time.time(),
            "alerted": alerted, **result,
        })

    def save(self, min_score_to_alert: int) -> None:
        cutoff = time.time() - KEEP_DAYS * 86400
        jobs = [j for j in self.jobs if j["scored_at"] > cutoff]
        jobs.sort(key=lambda j: j["scored_at"], reverse=True)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"updated_at": time.time(), "min_score_to_alert": min_score_to_alert,
                                         "jobs": jobs[: self.MAX_JOBS]}, ensure_ascii=False))

"""Cheap rule-based filters applied before spending Claude calls."""
import re

from .models import Job


def _has_any(text: str, words: list[str]) -> bool:
    """Whole-word match, so 'java' doesn't match 'javascript'."""
    return any(re.search(rf"(?<!\w){re.escape(w)}(?!\w)", text, re.IGNORECASE) for w in words)


def reject_reason(job: Job, cfg: dict) -> str | None:
    f = cfg["filters"]
    if not job.title or not job.url:
        return "missing title/url"
    if f.get("title_include") and not _has_any(job.title, f["title_include"]):
        return "title not relevant"
    if _has_any(job.title, f.get("title_exclude", [])):
        return "title excluded"
    if f.get("locations") and not _has_any(job.location, f["locations"]):
        return f"location '{job.location}'"
    if _has_any(job.company, f.get("exclude_companies", [])):
        return "company excluded"
    min_emp = f.get("min_company_employees")
    if min_emp and job.company_employees is not None and job.company_employees < min_emp:
        return f"company too small ({job.company_employees})"
    return None

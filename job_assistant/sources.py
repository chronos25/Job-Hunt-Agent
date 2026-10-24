"""Fetchers for each job source. Every fetcher returns a list of Job and never raises."""
import html
import logging
import re

import requests

from .models import Job

log = logging.getLogger(__name__)
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"}


def _clean(value) -> str:
    if value is None or (isinstance(value, float) and value != value):  # None or NaN
        return ""
    return str(value).strip()


def _strip_html(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _parse_employees(value) -> int | None:
    """JobSpy gives ranges like '1,001-5,000' or '10,000+'; return the lower bound."""
    nums = re.findall(r"\d[\d,]*", _clean(value))
    return int(nums[0].replace(",", "")) if nums else None


def fetch_jobspy(cfg: dict) -> list[Job]:
    from jobspy import scrape_jobs

    sites = [s for s in ("linkedin", "indeed", "naukri") if cfg["sources"].get(s)]
    if not sites:
        return []
    search = cfg["search"]
    jobs: list[Job] = []
    for term in search["terms"]:
        for site in sites:  # one site at a time so one blocked site doesn't kill the rest
            try:
                df = scrape_jobs(
                    site_name=[site],
                    search_term=term,
                    location=search["country"],
                    country_indeed=search["country"],
                    results_wanted=search["results_per_search"],
                    hours_old=search["hours_old"],
                    linkedin_fetch_description=True,
                    verbose=0,
                )
            except Exception as e:
                log.warning("%s search '%s' failed: %s", site, term, e)
                continue
            for row in df.to_dict("records"):
                salary = ""
                if _clean(row.get("min_amount")):
                    salary = f"{_clean(row.get('currency'))} {_clean(row.get('min_amount'))}-" \
                             f"{_clean(row.get('max_amount'))} /{_clean(row.get('interval'))}"
                jobs.append(Job(
                    source=site,
                    source_id=_clean(row.get("id")) or _clean(row.get("job_url")),
                    title=_clean(row.get("title")),
                    company=_clean(row.get("company")),
                    location=_clean(row.get("location")),
                    url=_clean(row.get("job_url_direct")) or _clean(row.get("job_url")),
                    description=_clean(row.get("description")),
                    posted=_clean(row.get("date_posted")),
                    salary=salary,
                    company_employees=_parse_employees(row.get("company_num_employees")),
                    extra={"experience": _clean(row.get("experience_range"))},
                ))
            log.info("%s '%s': %d jobs", site, term, len(df))
    return jobs


def fetch_instahyre(cfg: dict) -> list[Job]:
    if not cfg["sources"].get("instahyre"):
        return []
    icfg = cfg.get("instahyre", {})
    jobs: list[Job] = []
    for skill in icfg.get("skills", []):
        try:
            r = requests.get(
                "https://www.instahyre.com/api/v1/job_search",
                params={"company_size": 0, "isLandingPage": "true", "job_type": 0, "limit": 30,
                        "offset": 0, "skills": skill, "years": icfg.get("years", 0)},
                headers=UA, timeout=30,
            )
            r.raise_for_status()
            objects = r.json().get("objects", [])
        except Exception as e:
            log.warning("instahyre '%s' failed: %s", skill, e)
            continue
        for o in objects:
            emp = o.get("employer") or {}
            jobs.append(Job(
                source="instahyre",
                source_id=str(o.get("id")),
                title=o.get("title") or "",
                company=emp.get("company_name") or "",
                location=o.get("locations") or "",
                url=o.get("public_url") or "",
                description=f"Skills: {', '.join(o.get('keywords') or [])}\n"
                            f"About company: {emp.get('instahyre_note') or ''}",
                company_employees=emp.get("employee_count"),
            ))
        log.info("instahyre '%s': %d jobs", skill, len(objects))
    return jobs


def fetch_remote_boards(cfg: dict) -> list[Job]:
    if not cfg["sources"].get("remote_boards"):
        return []
    jobs: list[Job] = []
    try:
        r = requests.get("https://remotive.com/api/remote-jobs",
                         params={"category": "software-dev", "limit": 100}, headers=UA, timeout=30)
        r.raise_for_status()
        for j in r.json().get("jobs", []):
            jobs.append(Job(
                source="remotive", source_id=str(j["id"]), title=j.get("title", ""),
                company=j.get("company_name", ""),
                location=f"Remote ({j.get('candidate_required_location', '')})",
                url=j.get("url", ""), description=_strip_html(j.get("description", "")),
                posted=j.get("publication_date", ""), salary=j.get("salary", ""),
            ))
    except Exception as e:
        log.warning("remotive failed: %s", e)
    try:
        r = requests.get("https://remoteok.com/api", params={"tag": "backend"}, headers=UA, timeout=30)
        r.raise_for_status()
        for j in r.json()[1:]:  # first element is a legal notice
            salary = f"USD {j['salary_min']}-{j['salary_max']}" if j.get("salary_min") else ""
            jobs.append(Job(
                source="remoteok", source_id=str(j["id"]), title=j.get("position", ""),
                company=j.get("company", ""), location=f"Remote ({j.get('location') or 'anywhere'})",
                url=j.get("url", ""), description=_strip_html(j.get("description", "")),
                posted=j.get("date", ""), salary=salary,
            ))
    except Exception as e:
        log.warning("remoteok failed: %s", e)
    # Keep only remote jobs open to candidates in India.
    open_to_india = re.compile(r"worldwide|anywhere|global|india|asia|apac|^remote \(\)$", re.I)
    jobs = [j for j in jobs if open_to_india.search(j.location)]
    log.info("remote boards (open to India): %d jobs", len(jobs))
    return jobs


def fetch_all(cfg: dict) -> list[Job]:
    return fetch_jobspy(cfg) + fetch_instahyre(cfg) + fetch_remote_boards(cfg)

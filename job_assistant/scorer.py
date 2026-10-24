"""Scores a job against the resume and preferences with Claude."""
import json
import logging
import os
from pathlib import Path

import anthropic

from .models import Job

log = logging.getLogger(__name__)

SCHEMA = {
    "type": "object",
    "properties": {
        "match_score": {"type": "integer", "description": "0-100 overall fit"},
        "company_size_estimate": {"type": "string", "description": "e.g. '10,000+', '1,000-5,000', 'startup <200', 'unknown'"},
        "large_stable_company": {"type": "boolean"},
        "salary_estimate_lpa": {"type": "string", "description": "stated or estimated INR LPA range for this role, e.g. '28-40'"},
        "role_focus": {"type": "string", "description": "e.g. 'Backend Node.js + AWS', 'Full-stack', 'DevOps'"},
        "key_matches": {"type": "array", "items": {"type": "string"}},
        "gaps": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string", "description": "one or two sentences on why to apply or not"},
    },
    "required": ["match_score", "company_size_estimate", "large_stable_company", "salary_estimate_lpa",
                 "role_focus", "key_matches", "gaps", "summary"],
    "additionalProperties": False,
}


class Scorer:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.client = anthropic.Anthropic()
        profile = cfg["profile"]
        resume = os.environ.get("RESUME_TEXT") or Path(profile["resume_file"]).read_text()
        lo, hi = profile["target_salary_lpa"]
        # Stable system prompt so the resume is prompt-cached across calls.
        self.system = [{
            "type": "text",
            "text": (
                "You screen job postings for one candidate in India and rate how worth applying each one is.\n\n"
                f"<resume>\n{resume}\n</resume>\n\n"
                f"Experience: {profile['experience_years']} years. Target compensation: {lo}-{hi} LPA.\n"
                f"<preferences>\n{profile['preferences']}\n</preferences>\n\n"
                "Scoring guide: 85-100 = strong fit on skills, seniority, company and pay; 70-84 = good fit worth "
                "applying; 50-69 = partial fit; below 50 = poor fit. Lower the score clearly for small or unstable "
                "companies, staffing/consultancy listings, roles that are not mainly backend, seniority far from "
                "~6-7 years, or pay likely well below the target. Use your knowledge of the company to estimate its "
                "size and typical pay for this level when the posting doesn't say. Keep key_matches and gaps to at "
                "most 4 short items each."
            ),
            "cache_control": {"type": "ephemeral"},
        }]

    def score(self, job: Job) -> dict | None:
        posting = (
            f"Title: {job.title}\nCompany: {job.company}\nLocation: {job.location}\nSource: {job.source}\n"
            f"Posted: {job.posted or 'unknown'}\nSalary: {job.salary or 'not stated'}\n"
            f"Company employees (from site): {job.company_employees or 'unknown'}\n"
            f"Experience asked: {job.extra.get('experience') or 'see description'}\n\n"
            f"Description:\n{job.description[:12000] or '(no description available)'}"
        )
        scfg = self.cfg["scoring"]
        try:
            response = self.client.beta.messages.create(
                model=scfg["model"],
                max_tokens=8000,
                system=self.system,
                messages=[{"role": "user", "content": f"Rate this job posting:\n\n{posting}"}],
                output_config={"effort": scfg["effort"],
                               "format": {"type": "json_schema", "schema": SCHEMA}},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.RateLimitError as e:
            log.warning("rate limited scoring %s: %s", job.id, e)
            return None
        except anthropic.APIStatusError as e:
            log.error("API error %s scoring %s: %s", e.status_code, job.id, e.message)
            return None
        except anthropic.APIConnectionError as e:
            log.warning("connection error scoring %s: %s", job.id, e)
            return None
        if response.stop_reason in ("refusal", "max_tokens"):
            log.warning("scoring %s stopped: %s", job.id, response.stop_reason)
            return None
        text = next(b.text for b in response.content if b.type == "text")
        return json.loads(text)

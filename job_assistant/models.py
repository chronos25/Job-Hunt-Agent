from dataclasses import dataclass, field
import re


@dataclass
class Job:
    source: str
    source_id: str
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    posted: str = ""
    salary: str = ""
    company_employees: int | None = None
    extra: dict = field(default_factory=dict)

    @property
    def id(self) -> str:
        return f"{self.source}:{self.source_id}"

    @property
    def dedup_key(self) -> str:
        """Same title at the same company is treated as one job across sites."""
        norm = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower())
        return f"{norm(self.company)}|{norm(self.title)}"

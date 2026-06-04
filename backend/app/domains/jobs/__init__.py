"""岗位探索域。"""

from app.domains.jobs.assistant import jobs_assistant_bp
from app.domains.jobs.router import jobs_bp

__all__ = ["jobs_assistant_bp", "jobs_bp"]

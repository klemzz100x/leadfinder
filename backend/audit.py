"""Audit des sites web existants.

Phase 0 : stub — retourne un résultat vide (audit complet en Phase 1 via
heuristiques HTTP + PageSpeed Insights en Phase 2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AuditResult:
    url: str
    weak_points: list[str] = field(default_factory=list)
    score_perf: Optional[int] = None     # PageSpeed 0-100 (Phase 2)
    is_https: Optional[bool] = None
    is_responsive: Optional[bool] = None
    response_ms: Optional[int] = None
    cms_detected: Optional[str] = None
    error: Optional[str] = None


async def audit_url(url: str) -> AuditResult:
    """Audit complet d'une URL (Phase 1+ : heuristiques HTTP ; Phase 2 : PSI)."""
    return AuditResult(url=url, error="Audit disponible en Phase 1")

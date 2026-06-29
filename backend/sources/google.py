"""Adapter Google Places API New — STUB (Phase 0).

À n'activer que si GOOGLE_PLACES_API_KEY est défini dans .env.
Rappel : activer uniquement avec des quotas Cloud bridés sous le palier gratuit
(≈ 4 500 req/mois via budget alerts + quotas IAM) pour rendre toute facturation
impossible. Field mask obligatoire : websiteUri, nationalPhoneNumber, rating,
userRatingCount (récupérés directement dans searchNearby, pas de Place Details).
"""

from __future__ import annotations

from .base import BusinessSource, RawBusiness


class GoogleSource(BusinessSource):
    name = "google"

    def __init__(self) -> None:
        self._calls = 0

    @property
    def call_count(self) -> int:
        return self._calls

    async def discover(self, city: str) -> list[RawBusiness]:
        raise NotImplementedError(
            "GoogleSource n'est pas encore implémenté. "
            "Définir GOOGLE_PLACES_API_KEY dans .env pour l'activer (Phase 2)."
        )

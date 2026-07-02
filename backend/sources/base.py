"""Interface commune à toutes les sources de découverte de business.

Chaque source (OSM par défaut, Google/Brave en option plus tard) implémente
`BusinessSource.discover(city)` et renvoie une liste de `RawBusiness`
normalisés. Le reste du pipeline (classify / score / store) ne dépend QUE de
ce modèle, jamais d'un format de source particulier.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass(slots=True)
class RawBusiness:
    """Un business découvert par une source, avant classification/scoring.

    `id` est un identifiant *stable* propre à la source, qui sert de clé
    d'upsert en base. Pour OSM : ``"node:123456"`` / ``"way:987"``. Pour un
    futur adapter Google : ``"place:ChIJ..."``. Deux scans de la même ville
    doivent produire le même `id` pour le même business → pas de doublon.
    """

    id: str
    name: str
    lat: float
    lng: float
    business_type: str                       # type normalisé interne (cf. osm.py TYPE_MAP)
    source: str                              # "osm" | "google" | ...
    phone: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    postcode: Optional[str] = None
    opening_hours: Optional[str] = None
    raw_tags: dict[str, str] = field(default_factory=dict)  # tags bruts, pour debug/audit

    def __post_init__(self) -> None:
        # Normalisation défensive : un nom vide casse l'UI et le dédoublonnage.
        self.name = (self.name or "").strip()
        if self.website:
            self.website = self.website.strip()
        if self.phone:
            self.phone = self.phone.strip()


class BusinessSource(ABC):
    """Contrat d'une source de découverte de business."""

    #: nom court de la source, repris dans `RawBusiness.source` et les logs.
    name: str = "base"

    @abstractmethod
    async def discover(self, city: str) -> list[RawBusiness]:
        """Découvre un maximum de business pour `city`.

        Doit :
          - résoudre la ville en zone géographique,
          - récupérer les business lucratifs de la zone,
          - dédupliquer (par `id`),
          - renvoyer une liste de `RawBusiness` (jamais lever pour une ville
            vide : renvoyer ``[]`` et logguer).
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def call_count(self) -> int:
        """Nombre d'appels réseau effectués depuis l'instanciation.

        Sert au compteur "0 € garanti" exposé dans l'UI et les logs.
        """
        raise NotImplementedError

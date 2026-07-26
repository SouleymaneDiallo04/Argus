from __future__ import annotations

from app.api.schemas import ZoneModel, ZonesConfig
from app.domain.types import Zone


class ZonesStore:
    """Détient la config de zones en mémoire (reset au redémarrage ; persistance = P3)."""

    def __init__(self, zones: list[Zone] | None = None):
        self._zones: list[Zone] = list(zones) if zones else []

    def get_zones(self) -> list[Zone]:
        return list(self._zones)

    def set_from_config(self, config: ZonesConfig) -> None:
        self._zones = [zm.to_domain() for zm in config.zones]

    def to_config(self) -> ZonesConfig:
        return ZonesConfig(zones=[ZoneModel.from_domain(z) for z in self._zones])

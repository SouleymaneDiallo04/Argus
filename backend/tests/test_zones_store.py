from __future__ import annotations

from app.api.schemas import ZoneModel, ZonesConfig
from app.api.zones_store import ZonesStore
from app.domain.types import Zone


def test_store_starts_empty():
    assert ZonesStore().get_zones() == []


def test_set_from_config_produces_domain_zones():
    store = ZonesStore()
    config = ZonesConfig(zones=[ZoneModel(name="z", polygon=[[0, 0], [10, 0], [10, 10]],
                                          required_ppe=["helmet"])])
    store.set_from_config(config)
    zones = store.get_zones()
    assert len(zones) == 1
    assert isinstance(zones[0], Zone)
    assert zones[0].required_ppe == frozenset({"helmet"})


def test_to_config_roundtrips():
    store = ZonesStore()
    config = ZonesConfig(zones=[ZoneModel(name="z", polygon=[[0, 0], [10, 0], [10, 10]],
                                          required_ppe=["helmet", "mask"])])
    store.set_from_config(config)
    out = store.to_config()
    assert out.zones[0].name == "z"
    assert out.zones[0].required_ppe == ["helmet", "mask"]

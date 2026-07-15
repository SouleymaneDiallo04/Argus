# Argus — Moteur de conformité (logique métier) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construire le cœur métier d'Argus — un moteur Python pur et déterministe qui, à partir de détections (boîtes) d'une frame, associe les EPI aux personnes, résout leur zone, évalue la conformité, applique un debounce anti-faux-positifs et émet des événements d'infraction — le tout testé unitairement **sans le modèle YOLO**.

**Architecture:** Un package `app.domain` de fonctions/classes pures (aucune I/O, aucun modèle, aucun réseau). Les détections entrent sous forme de `Detection` (boîtes + classe + `track_id` pour les personnes) ; le moteur en sort des `ComplianceResult` par personne et des `ViolationEvent`. Les couches supérieures (FastAPI, YOLO, floutage, stockage) consommeront ce moteur plus tard — elles ne sont **pas** dans ce plan.

**Tech Stack:** Python ≥ 3.10, pytest. Aucune dépendance tierce pour le moteur (géométrie et point-dans-polygone implémentés à la main — DRY/YAGNI, pas de shapely).

## Global Constraints

- Python ≥ 3.10. Chaque module commence par `from __future__ import annotations`.
- Taxonomie EPI (exacte, verbatim) : `helmet`, `safety-vest`, `mask`, `gloves`, `glasses`, `shoes`. Classes support : `person`, `head`, `face`.
- **⚠️ Amendement 2026-07-15 (décision produit, postérieure aux Tasks 1-3)** : `gloves` et `glasses` sont retirés de la V1 → taxonomie effective : `helmet`, `safety-vest`, `mask`, `shoes`. À répercuter dans le code : `PPE_CLASSES` (types.py), `BODY_BANDS` (association.py), et le test de la Task 3 qui utilise `gloves`. Les Tasks 4-6 n'utilisent que `helmet`/`safety-vest` : inchangées.
- Le moteur est **pur** : pas d'I/O, pas d'horloge murale (les timestamps sont toujours passés en paramètre), pas de dépendance au modèle. Le floutage RGPD et les snapshots sont hors périmètre de ce plan (couche service).
- Debounce : infraction confirmée après `confirm_seconds` d'anomalie **continue** (par `track_id`) ; effacée après `clear_seconds` de conformité continue ; `cooldown_seconds` empêche la ré-émission rapprochée. Valeurs par défaut : `confirm_seconds=3.0`, `clear_seconds=3.0`, `cooldown_seconds=30.0`.
- Une personne **hors de toute zone** n'a aucun EPI requis → considérée conforme (documenté).
- Répertoire de travail des commandes : `backend/`. Les tests s'exécutent avec `python -m pytest`.
- Commits : messages en anglais, préfixe conventionnel (`feat`/`test`/`chore`). **Pas de ligne `Co-Authored-By`** (dépôt personnel de l'auteur).

---

## File Structure

```
backend/
  pyproject.toml                 # config projet + pytest (pythonpath=".")
  app/
    __init__.py
    domain/
      __init__.py
      types.py                   # BBox, Detection, Zone, ComplianceResult, ViolationEvent, FrameResult, constantes
      geometry.py                # iou, intersection_area, containment_ratio, center, bottom_center, point_in_polygon
      zones.py                   # resolve_zone(person_bbox, zones) -> Zone | None
      association.py             # associate(persons, ppe, threshold) -> dict[int, set[str]]
      compliance.py              # evaluate(track_id, present, zone) -> ComplianceResult
      debounce.py                # DebounceTracker.update(track_id, compliant, timestamp) -> bool
      engine.py                  # ComplianceEngine.process_frame(detections, timestamp) -> FrameResult
  tests/
    __init__.py
    test_geometry.py
    test_zones.py
    test_association.py
    test_compliance.py
    test_debounce.py
    test_engine.py
```

Chaque fichier a une responsabilité unique. Les dépendances vont dans un seul sens : `types` ← `geometry` ← (`zones`, `association`) ; `compliance`, `debounce` ← `types` ; `engine` ← tout le reste.

---

### Task 1: Setup projet + types du domaine + primitives géométriques

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py` (vide)
- Create: `backend/app/domain/__init__.py` (vide)
- Create: `backend/tests/__init__.py` (vide)
- Create: `backend/app/domain/types.py`
- Create: `backend/app/domain/geometry.py`
- Test: `backend/tests/test_geometry.py`

**Interfaces:**
- Consumes: rien (tâche fondation).
- Produces :
  - `BBox(x1, y1, x2, y2)` — frozen dataclass ; propriétés `width`, `height`, `area`.
  - `PPE_CLASSES: frozenset[str]`, `SUPPORT_CLASSES: frozenset[str]`.
  - `Detection(cls: str, bbox: BBox, confidence: float, track_id: int | None = None)` — frozen.
  - `iou(a: BBox, b: BBox) -> float`
  - `intersection_area(a: BBox, b: BBox) -> float`
  - `containment_ratio(inner: BBox, outer: BBox) -> float`  # inter_area / inner.area (0.0 si inner.area == 0)
  - `center(b: BBox) -> tuple[float, float]`
  - `bottom_center(b: BBox) -> tuple[float, float]`
  - `point_in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool`

- [ ] **Step 1: Écrire les tests géométrie (échouent)**

`backend/tests/test_geometry.py` :
```python
from __future__ import annotations

from app.domain.types import BBox
from app.domain.geometry import (
    intersection_area,
    iou,
    containment_ratio,
    center,
    bottom_center,
    point_in_polygon,
)


def test_bbox_properties():
    b = BBox(10, 20, 40, 100)
    assert b.width == 30
    assert b.height == 80
    assert b.area == 2400


def test_intersection_area_overlap():
    a = BBox(0, 0, 10, 10)
    b = BBox(5, 5, 15, 15)
    assert intersection_area(a, b) == 25


def test_intersection_area_disjoint():
    a = BBox(0, 0, 10, 10)
    b = BBox(20, 20, 30, 30)
    assert intersection_area(a, b) == 0


def test_iou_identical_is_one():
    a = BBox(0, 0, 10, 10)
    assert iou(a, a) == 1.0


def test_iou_half_overlap():
    a = BBox(0, 0, 10, 10)      # area 100
    b = BBox(5, 0, 15, 10)      # area 100, inter = 50, union = 150
    assert iou(a, b) == 50 / 150


def test_containment_full_inside():
    inner = BBox(2, 2, 4, 4)    # area 4, fully inside outer
    outer = BBox(0, 0, 10, 10)
    assert containment_ratio(inner, outer) == 1.0


def test_containment_partial():
    inner = BBox(-5, 0, 5, 10)  # area 100, half inside outer
    outer = BBox(0, 0, 10, 10)
    assert containment_ratio(inner, outer) == 0.5


def test_center_and_bottom_center():
    b = BBox(0, 0, 100, 300)
    assert center(b) == (50.0, 150.0)
    assert bottom_center(b) == (50.0, 300.0)


def test_point_in_polygon_inside_and_outside():
    square = [(0, 0), (300, 0), (300, 500), (0, 500)]
    assert point_in_polygon((150, 400), square) is True
    assert point_in_polygon((400, 400), square) is False


def test_point_in_polygon_triangle():
    tri = [(0, 0), (10, 0), (0, 10)]
    assert point_in_polygon((1, 1), tri) is True
    assert point_in_polygon((9, 9), tri) is False
```

- [ ] **Step 2: Lancer les tests → doivent échouer**

Run (depuis `backend/`) : `python -m pytest tests/test_geometry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app'` (modules pas encore créés).

- [ ] **Step 3: Créer la config projet et les `__init__.py`**

`backend/pyproject.toml` :
```toml
[project]
name = "argus-backend"
version = "0.1.0"
requires-python = ">=3.10"

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

Créer les fichiers vides : `backend/app/__init__.py`, `backend/app/domain/__init__.py`, `backend/tests/__init__.py`.

- [ ] **Step 4: Implémenter `types.py`**

`backend/app/domain/types.py` :
```python
from __future__ import annotations

from dataclasses import dataclass

PPE_CLASSES: frozenset[str] = frozenset(
    {"helmet", "safety-vest", "mask", "gloves", "glasses", "shoes"}
)
SUPPORT_CLASSES: frozenset[str] = frozenset({"person", "head", "face"})


@dataclass(frozen=True)
class BBox:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def area(self) -> float:
        return max(0.0, self.width) * max(0.0, self.height)


@dataclass(frozen=True)
class Detection:
    cls: str
    bbox: BBox
    confidence: float
    track_id: int | None = None
```

- [ ] **Step 5: Implémenter `geometry.py`**

`backend/app/domain/geometry.py` :
```python
from __future__ import annotations

from app.domain.types import BBox


def intersection_area(a: BBox, b: BBox) -> float:
    ix1 = max(a.x1, b.x1)
    iy1 = max(a.y1, b.y1)
    ix2 = min(a.x2, b.x2)
    iy2 = min(a.y2, b.y2)
    w = max(0.0, ix2 - ix1)
    h = max(0.0, iy2 - iy1)
    return w * h


def iou(a: BBox, b: BBox) -> float:
    inter = intersection_area(a, b)
    union = a.area + b.area - inter
    if union <= 0:
        return 0.0
    return inter / union


def containment_ratio(inner: BBox, outer: BBox) -> float:
    if inner.area <= 0:
        return 0.0
    return intersection_area(inner, outer) / inner.area


def center(b: BBox) -> tuple[float, float]:
    return ((b.x1 + b.x2) / 2.0, (b.y1 + b.y2) / 2.0)


def bottom_center(b: BBox) -> tuple[float, float]:
    return ((b.x1 + b.x2) / 2.0, b.y2)


def point_in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    # Ray casting. Points on the edge are treated as inside is not guaranteed;
    # tests use clearly interior/exterior points.
    x, y = point
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside
```

- [ ] **Step 6: Lancer les tests → doivent passer**

Run : `python -m pytest tests/test_geometry.py -v`
Expected: PASS (10 tests).

- [ ] **Step 7: Commit**

```bash
git add backend/pyproject.toml backend/app backend/tests
git commit -m "feat(engine): geometry primitives + domain types"
```

---

### Task 2: Résolution de zone (point-dans-polygone → EPI requis)

**Files:**
- Modify: `backend/app/domain/types.py` (ajouter `Zone`)
- Create: `backend/app/domain/zones.py`
- Test: `backend/tests/test_zones.py`

**Interfaces:**
- Consumes: `BBox` (Task 1), `bottom_center`, `point_in_polygon` (Task 1).
- Produces:
  - `Zone(name: str, polygon: list[tuple[float, float]], required_ppe: frozenset[str])` — frozen (le champ `polygon` est une `tuple` en interne pour rester hashable, voir impl).
  - `resolve_zone(person_bbox: BBox, zones: list[Zone]) -> Zone | None` — première zone dont le polygone contient le point-au-sol (`bottom_center`) de la personne ; `None` si aucune.

- [ ] **Step 1: Écrire les tests zones (échouent)**

`backend/tests/test_zones.py` :
```python
from __future__ import annotations

from app.domain.types import BBox, Zone
from app.domain.zones import resolve_zone


def _person_at(cx: float, y_bottom: float) -> BBox:
    # boîte de 100x300 dont le bottom-center vaut (cx, y_bottom)
    return BBox(cx - 50, y_bottom - 300, cx + 50, y_bottom)


def test_person_inside_single_zone():
    zone = Zone(
        name="A",
        polygon=[(0, 0), (300, 0), (300, 500), (0, 500)],
        required_ppe=frozenset({"helmet", "safety-vest"}),
    )
    person = _person_at(150, 400)
    resolved = resolve_zone(person, [zone])
    assert resolved is zone


def test_person_outside_all_zones_returns_none():
    zone = Zone(
        name="A",
        polygon=[(0, 0), (300, 0), (300, 500), (0, 500)],
        required_ppe=frozenset({"helmet"}),
    )
    person = _person_at(400, 400)  # bottom-center hors du carré
    assert resolve_zone(person, [zone]) is None


def test_first_matching_zone_wins():
    z1 = Zone("first", [(0, 0), (500, 0), (500, 500), (0, 500)], frozenset({"helmet"}))
    z2 = Zone("second", [(0, 0), (500, 0), (500, 500), (0, 500)], frozenset({"gloves"}))
    person = _person_at(250, 250)
    assert resolve_zone(person, [z1, z2]) is z1


def test_uses_bottom_center_not_box_center():
    # zone couvrant seulement le bas de l'image ; le centre de la boîte est au-dessus
    zone = Zone("floor", [(0, 350), (500, 350), (500, 500), (0, 500)], frozenset({"shoes"}))
    person = _person_at(250, 400)   # bottom-center y=400 -> dans la zone ; center y=250 -> hors
    assert resolve_zone(person, [zone]) is zone
```

- [ ] **Step 2: Lancer → échouent**

Run : `python -m pytest tests/test_zones.py -v`
Expected: FAIL — `ImportError: cannot import name 'Zone'` (et `zones` inexistant).

- [ ] **Step 3: Ajouter `Zone` à `types.py`**

Ajouter dans `backend/app/domain/types.py` (après `Detection`) :
```python
@dataclass(frozen=True)
class Zone:
    name: str
    polygon: list[tuple[float, float]]
    required_ppe: frozenset[str]
```

- [ ] **Step 4: Implémenter `zones.py`**

`backend/app/domain/zones.py` :
```python
from __future__ import annotations

from app.domain.types import BBox, Zone
from app.domain.geometry import bottom_center, point_in_polygon


def resolve_zone(person_bbox: BBox, zones: list[Zone]) -> Zone | None:
    ground_point = bottom_center(person_bbox)
    for zone in zones:
        if point_in_polygon(ground_point, zone.polygon):
            return zone
    return None
```

- [ ] **Step 5: Lancer → passent**

Run : `python -m pytest tests/test_zones.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/app/domain/types.py backend/app/domain/zones.py backend/tests/test_zones.py
git commit -m "feat(engine): zone membership resolution via ground point"
```

---

### Task 3: Association EPI ↔ personne

**Files:**
- Create: `backend/app/domain/association.py`
- Test: `backend/tests/test_association.py`

**Interfaces:**
- Consumes: `Detection`, `BBox` (Task 1), `containment_ratio`, `center` (Task 1).
- Produces:
  - `BODY_BANDS: dict[str, tuple[float, float]]` — bande verticale (fractions 0=haut,1=bas dans la boîte personne) attendue par classe d'EPI.
  - `associate(persons: list[Detection], ppe: list[Detection], containment_threshold: float = 0.5) -> dict[int, set[str]]`
    - Mappe chaque `track_id` de personne → ensemble des classes d'EPI présentes.
    - Algo par détection EPI : (1) candidats = personnes avec `containment_ratio(ppe.bbox, person.bbox) >= threshold` ; (2) parmi les candidats, préférer ceux dont le centre-y **relatif** de l'EPI tombe dans `BODY_BANDS[ppe.cls]`, puis prendre le plus proche (distance des centres) ; s'il n'y a pas de candidat en bande, prendre le plus proche parmi les candidats ; (3) si **aucun** candidat par containment, rattacher à la personne la plus proche (cas ambigu). Une personne sans `track_id` est ignorée.

- [ ] **Step 1: Écrire les tests association (échouent)**

`backend/tests/test_association.py` :
```python
from __future__ import annotations

from app.domain.types import BBox, Detection
from app.domain.association import associate


def person(track_id: int, x1, y1, x2, y2) -> Detection:
    return Detection("person", BBox(x1, y1, x2, y2), 0.9, track_id=track_id)


def ppe(cls: str, x1, y1, x2, y2) -> Detection:
    return Detection(cls, BBox(x1, y1, x2, y2), 0.8)


def test_helmet_on_head_associates_to_person():
    p = person(1, 100, 100, 200, 400)          # tête ~ y in [100,190]
    helmet = ppe("helmet", 120, 110, 180, 150)  # centre (150,130), dans la bande tête
    result = associate([p], [helmet])
    assert result == {1: {"helmet"}}


def test_shoes_at_bottom_associate():
    p = person(1, 100, 100, 200, 400)
    shoes = ppe("shoes", 120, 370, 180, 400)    # bas de la personne
    result = associate([p], [shoes])
    assert result == {1: {"shoes"}}


def test_two_persons_helmet_goes_to_the_right_one():
    left = person(1, 0, 100, 100, 400)
    right = person(2, 300, 100, 400, 400)
    helmet = ppe("helmet", 320, 110, 380, 150)  # au-dessus de la personne 2
    result = associate([left, right], [helmet])
    assert result == {2: {"helmet"}}


def test_multiple_ppe_accumulate_per_person():
    p = person(1, 100, 100, 200, 400)
    helmet = ppe("helmet", 120, 110, 180, 150)
    vest = ppe("safety-vest", 110, 200, 190, 300)
    result = associate([p], [helmet, vest])
    assert result == {1: {"helmet", "safety-vest"}}


def test_person_without_ppe_absent_from_map():
    p = person(1, 100, 100, 200, 400)
    result = associate([p], [])
    assert result == {}


def test_ambiguous_ppe_falls_back_to_nearest_person():
    # gant loin de tout containment -> rattaché à la personne la plus proche
    p1 = person(1, 0, 0, 50, 200)
    p2 = person(2, 1000, 0, 1050, 200)
    gloves = ppe("gloves", 60, 90, 80, 110)     # proche de p1, hors des deux boîtes
    result = associate([p1, p2], [gloves])
    assert result == {1: {"gloves"}}
```

- [ ] **Step 2: Lancer → échouent**

Run : `python -m pytest tests/test_association.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.domain.association'`.

- [ ] **Step 3: Implémenter `association.py`**

`backend/app/domain/association.py` :
```python
from __future__ import annotations

import math

from app.domain.types import Detection
from app.domain.geometry import center, containment_ratio

# Bande verticale attendue (fraction de la hauteur de la personne : 0 = haut, 1 = bas)
BODY_BANDS: dict[str, tuple[float, float]] = {
    "helmet": (0.0, 0.30),
    "glasses": (0.0, 0.30),
    "mask": (0.0, 0.35),
    "safety-vest": (0.20, 0.60),
    "gloves": (0.30, 0.80),
    "shoes": (0.80, 1.0),
}


def _distance(a: Detection, b: Detection) -> float:
    ax, ay = center(a.bbox)
    bx, by = center(b.bbox)
    return math.hypot(ax - bx, ay - by)


def _in_band(ppe_det: Detection, person: Detection) -> bool:
    band = BODY_BANDS.get(ppe_det.cls)
    if band is None or person.bbox.height <= 0:
        return False
    _, ppe_cy = center(ppe_det.bbox)
    rel_y = (ppe_cy - person.bbox.y1) / person.bbox.height
    return band[0] <= rel_y <= band[1]


def _best_person(ppe_det: Detection, persons: list[Detection], threshold: float) -> Detection | None:
    contained = [
        p for p in persons
        if containment_ratio(ppe_det.bbox, p.bbox) >= threshold
    ]
    if contained:
        in_band = [p for p in contained if _in_band(ppe_det, p)]
        pool = in_band if in_band else contained
        return min(pool, key=lambda p: _distance(ppe_det, p))
    if persons:  # fallback ambigu : personne la plus proche
        return min(persons, key=lambda p: _distance(ppe_det, p))
    return None


def associate(
    persons: list[Detection],
    ppe: list[Detection],
    containment_threshold: float = 0.5,
) -> dict[int, set[str]]:
    tracked = [p for p in persons if p.track_id is not None]
    result: dict[int, set[str]] = {}
    for ppe_det in ppe:
        chosen = _best_person(ppe_det, tracked, containment_threshold)
        if chosen is None:
            continue
        result.setdefault(chosen.track_id, set()).add(ppe_det.cls)
    return result
```

- [ ] **Step 4: Lancer → passent**

Run : `python -m pytest tests/test_association.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/domain/association.py backend/tests/test_association.py
git commit -m "feat(engine): PPE-to-person association with body-part priors"
```

---

### Task 4: Évaluation de conformité par personne

**Files:**
- Modify: `backend/app/domain/types.py` (ajouter `ComplianceResult`)
- Create: `backend/app/domain/compliance.py`
- Test: `backend/tests/test_compliance.py`

**Interfaces:**
- Consumes: `Zone` (Task 2).
- Produces:
  - `ComplianceResult(track_id: int, zone: str | None, required: frozenset[str], present: frozenset[str], missing: frozenset[str], compliant: bool)` — frozen.
  - `evaluate(track_id: int, present: set[str], zone: Zone | None) -> ComplianceResult` — `required = zone.required_ppe` (ou vide si `zone is None`) ; `missing = required - present` ; `compliant = (missing == ∅)`.

- [ ] **Step 1: Écrire les tests conformité (échouent)**

`backend/tests/test_compliance.py` :
```python
from __future__ import annotations

from app.domain.types import Zone, ComplianceResult
from app.domain.compliance import evaluate


def test_compliant_when_all_required_present():
    zone = Zone("A", [(0, 0), (1, 0), (1, 1), (0, 1)], frozenset({"helmet", "safety-vest"}))
    res = evaluate(1, {"helmet", "safety-vest", "gloves"}, zone)
    assert res.compliant is True
    assert res.missing == frozenset()
    assert res.zone == "A"
    assert res.required == frozenset({"helmet", "safety-vest"})


def test_non_compliant_lists_missing():
    zone = Zone("A", [(0, 0), (1, 0), (1, 1), (0, 1)], frozenset({"helmet", "safety-vest"}))
    res = evaluate(1, {"helmet"}, zone)
    assert res.compliant is False
    assert res.missing == frozenset({"safety-vest"})


def test_no_zone_means_compliant_with_no_requirements():
    res = evaluate(7, set(), None)
    assert res.compliant is True
    assert res.zone is None
    assert res.required == frozenset()
    assert res.missing == frozenset()


def test_result_type_is_compliance_result():
    zone = Zone("A", [(0, 0), (1, 0), (1, 1), (0, 1)], frozenset({"helmet"}))
    res = evaluate(1, set(), zone)
    assert isinstance(res, ComplianceResult)
    assert res.present == frozenset()
```

- [ ] **Step 2: Lancer → échouent**

Run : `python -m pytest tests/test_compliance.py -v`
Expected: FAIL — `ImportError: cannot import name 'ComplianceResult'`.

- [ ] **Step 3: Ajouter `ComplianceResult` à `types.py`**

Ajouter dans `backend/app/domain/types.py` (après `Zone`) :
```python
@dataclass(frozen=True)
class ComplianceResult:
    track_id: int
    zone: str | None
    required: frozenset[str]
    present: frozenset[str]
    missing: frozenset[str]
    compliant: bool
```

- [ ] **Step 4: Implémenter `compliance.py`**

`backend/app/domain/compliance.py` :
```python
from __future__ import annotations

from app.domain.types import Zone, ComplianceResult


def evaluate(track_id: int, present: set[str], zone: Zone | None) -> ComplianceResult:
    required = zone.required_ppe if zone is not None else frozenset()
    present_fs = frozenset(present)
    missing = required - present_fs
    return ComplianceResult(
        track_id=track_id,
        zone=zone.name if zone is not None else None,
        required=frozenset(required),
        present=present_fs,
        missing=missing,
        compliant=len(missing) == 0,
    )
```

- [ ] **Step 5: Lancer → passent**

Run : `python -m pytest tests/test_compliance.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/app/domain/types.py backend/app/domain/compliance.py backend/tests/test_compliance.py
git commit -m "feat(engine): per-person compliance evaluation"
```

---

### Task 5: Machine à états du debounce (anti-faux-positifs)

**Files:**
- Modify: `backend/app/domain/types.py` (ajouter `ViolationEvent`)
- Create: `backend/app/domain/debounce.py`
- Test: `backend/tests/test_debounce.py`

**Interfaces:**
- Consumes: rien (timers purs).
- Produces:
  - `ViolationEvent(track_id: int, zone: str | None, missing: frozenset[str], timestamp: float, camera: str)` — frozen (défini ici pour Task 6).
  - `DebounceTracker(confirm_seconds: float, clear_seconds: float, cooldown_seconds: float)`.
  - `DebounceTracker.update(track_id: int, compliant: bool, timestamp: float) -> bool` — retourne `True` **uniquement** sur la frame où une nouvelle infraction est confirmée (anomalie continue ≥ `confirm_seconds`, hors cooldown). Sinon `False`. L'état est effacé après `clear_seconds` de conformité continue.

- [ ] **Step 1: Écrire les tests debounce (échouent)**

`backend/tests/test_debounce.py` :
```python
from __future__ import annotations

from app.domain.debounce import DebounceTracker


def make() -> DebounceTracker:
    return DebounceTracker(confirm_seconds=3.0, clear_seconds=3.0, cooldown_seconds=30.0)


def test_no_event_before_confirm_window():
    d = make()
    assert d.update(1, compliant=False, timestamp=0.0) is False
    assert d.update(1, compliant=False, timestamp=1.0) is False
    assert d.update(1, compliant=False, timestamp=2.9) is False


def test_event_fires_once_after_continuous_anomaly():
    d = make()
    d.update(1, compliant=False, timestamp=0.0)
    d.update(1, compliant=False, timestamp=2.0)
    assert d.update(1, compliant=False, timestamp=3.0) is True   # confirmé
    assert d.update(1, compliant=False, timestamp=4.0) is False  # déjà en infraction


def test_compliance_resets_anomaly_window():
    d = make()
    d.update(1, compliant=False, timestamp=0.0)
    d.update(1, compliant=True, timestamp=1.0)      # reset
    d.update(1, compliant=False, timestamp=2.0)     # redémarre le compteur
    assert d.update(1, compliant=False, timestamp=4.9) is False  # 2.9s < 3s
    assert d.update(1, compliant=False, timestamp=5.0) is True   # 3.0s -> confirmé


def test_clear_then_new_violation_fires_again_after_cooldown():
    d = DebounceTracker(confirm_seconds=1.0, clear_seconds=1.0, cooldown_seconds=2.0)
    assert d.update(1, compliant=False, timestamp=0.0) is False
    assert d.update(1, compliant=False, timestamp=1.0) is True    # 1re infraction @ t=1
    d.update(1, compliant=True, timestamp=2.0)                    # conforme -> clear_since=2
    d.update(1, compliant=True, timestamp=3.0)                    # 1s conforme -> in_violation effacé
    d.update(1, compliant=False, timestamp=4.0)                   # anomalie repart
    # cooldown = 2s depuis le dernier event (t=1) -> t=5 OK ; confirm=1s depuis t=4 -> t=5 OK
    assert d.update(1, compliant=False, timestamp=5.0) is True


def test_cooldown_blocks_immediate_refire():
    d = DebounceTracker(confirm_seconds=1.0, clear_seconds=1.0, cooldown_seconds=100.0)
    d.update(1, compliant=False, timestamp=0.0)
    assert d.update(1, compliant=False, timestamp=1.0) is True    # event @ t=1
    d.update(1, compliant=True, timestamp=2.0)
    d.update(1, compliant=True, timestamp=3.0)                    # clear
    d.update(1, compliant=False, timestamp=4.0)
    # confirm satisfait à t=5 mais cooldown=100s depuis t=1 -> bloqué
    assert d.update(1, compliant=False, timestamp=5.0) is False


def test_tracks_are_independent():
    d = make()
    d.update(1, compliant=False, timestamp=0.0)
    d.update(2, compliant=False, timestamp=2.0)
    assert d.update(1, compliant=False, timestamp=3.0) is True    # track 1 : 3s
    assert d.update(2, compliant=False, timestamp=3.0) is False   # track 2 : 1s
```

- [ ] **Step 2: Lancer → échouent**

Run : `python -m pytest tests/test_debounce.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.domain.debounce'`.

- [ ] **Step 3: Ajouter `ViolationEvent` à `types.py`**

Ajouter dans `backend/app/domain/types.py` (après `ComplianceResult`) :
```python
@dataclass(frozen=True)
class ViolationEvent:
    track_id: int
    zone: str | None
    missing: frozenset[str]
    timestamp: float
    camera: str
```

- [ ] **Step 4: Implémenter `debounce.py`**

`backend/app/domain/debounce.py` :
```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class _TrackState:
    anomaly_since: float | None = None
    compliant_since: float | None = None
    in_violation: bool = False
    last_event_ts: float | None = None


class DebounceTracker:
    def __init__(self, confirm_seconds: float, clear_seconds: float, cooldown_seconds: float):
        self.confirm_seconds = confirm_seconds
        self.clear_seconds = clear_seconds
        self.cooldown_seconds = cooldown_seconds
        self._states: dict[int, _TrackState] = {}

    def update(self, track_id: int, compliant: bool, timestamp: float) -> bool:
        st = self._states.setdefault(track_id, _TrackState())

        if not compliant:
            st.compliant_since = None
            if st.anomaly_since is None:
                st.anomaly_since = timestamp
            duration = timestamp - st.anomaly_since
            if not st.in_violation and duration >= self.confirm_seconds:
                cooldown_ok = (
                    st.last_event_ts is None
                    or (timestamp - st.last_event_ts) >= self.cooldown_seconds
                )
                if cooldown_ok:
                    st.in_violation = True
                    st.last_event_ts = timestamp
                    return True
            return False

        # compliant
        st.anomaly_since = None
        if st.compliant_since is None:
            st.compliant_since = timestamp
        if st.in_violation and (timestamp - st.compliant_since) >= self.clear_seconds:
            st.in_violation = False
        return False
```

- [ ] **Step 5: Lancer → passent**

Run : `python -m pytest tests/test_debounce.py -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/app/domain/types.py backend/app/domain/debounce.py backend/tests/test_debounce.py
git commit -m "feat(engine): temporal debounce state machine"
```

---

### Task 6: Orchestration — `ComplianceEngine.process_frame`

**Files:**
- Modify: `backend/app/domain/types.py` (ajouter `FrameResult`)
- Create: `backend/app/domain/engine.py`
- Test: `backend/tests/test_engine.py`

**Interfaces:**
- Consumes: `Detection`, `Zone`, `ComplianceResult`, `ViolationEvent` (Tasks 1–5), `associate` (Task 3), `resolve_zone` (Task 2), `evaluate` (Task 4), `DebounceTracker` (Task 5), `PPE_CLASSES` (Task 1).
- Produces:
  - `FrameResult(results: list[ComplianceResult], events: list[ViolationEvent])` — frozen.
  - `ComplianceEngine(zones: list[Zone], confirm_seconds=3.0, clear_seconds=3.0, cooldown_seconds=30.0, camera="cam-1", containment_threshold=0.5)`.
  - `ComplianceEngine.process_frame(detections: list[Detection], timestamp: float) -> FrameResult` — sépare personnes/EPI, associe, résout zone, évalue, alimente le debounce, émet les événements confirmés cette frame.

- [ ] **Step 1: Écrire les tests d'intégration du moteur (échouent)**

`backend/tests/test_engine.py` :
```python
from __future__ import annotations

from app.domain.types import BBox, Detection, Zone
from app.domain.engine import ComplianceEngine


def person(track_id: int) -> Detection:
    return Detection("person", BBox(100, 100, 200, 400), 0.9, track_id=track_id)


def helmet() -> Detection:
    return Detection("helmet", BBox(120, 110, 180, 150), 0.8)


def vest() -> Detection:
    return Detection("safety-vest", BBox(110, 200, 190, 300), 0.8)


ZONE = Zone(
    name="chantier",
    polygon=[(0, 0), (300, 0), (300, 500), (0, 500)],
    required_ppe=frozenset({"helmet", "safety-vest"}),
)


def test_fully_equipped_person_is_compliant_no_event():
    engine = ComplianceEngine([ZONE])
    result = engine.process_frame([person(1), helmet(), vest()], timestamp=0.0)
    assert len(result.results) == 1
    assert result.results[0].compliant is True
    assert result.events == []


def test_missing_vest_is_non_compliant():
    engine = ComplianceEngine([ZONE])
    result = engine.process_frame([person(1), helmet()], timestamp=0.0)
    assert result.results[0].compliant is False
    assert result.results[0].missing == frozenset({"safety-vest"})


def test_violation_event_emitted_after_confirm_window():
    engine = ComplianceEngine([ZONE], confirm_seconds=2.0)
    # anomalie continue : casque seul, gilet manquant
    engine.process_frame([person(1), helmet()], timestamp=0.0)
    engine.process_frame([person(1), helmet()], timestamp=1.0)
    result = engine.process_frame([person(1), helmet()], timestamp=2.0)
    assert len(result.events) == 1
    ev = result.events[0]
    assert ev.track_id == 1
    assert ev.zone == "chantier"
    assert ev.missing == frozenset({"safety-vest"})
    assert ev.camera == "cam-1"
    assert ev.timestamp == 2.0


def test_no_duplicate_event_while_violation_persists():
    engine = ComplianceEngine([ZONE], confirm_seconds=1.0)
    engine.process_frame([person(1), helmet()], timestamp=0.0)
    engine.process_frame([person(1), helmet()], timestamp=1.0)   # event ici
    later = engine.process_frame([person(1), helmet()], timestamp=2.0)
    assert later.events == []


def test_person_outside_zone_has_no_requirements():
    engine = ComplianceEngine([ZONE])
    outsider = Detection("person", BBox(1000, 100, 1100, 400), 0.9, track_id=9)
    result = engine.process_frame([outsider], timestamp=0.0)
    assert result.results[0].compliant is True
    assert result.results[0].zone is None
```

- [ ] **Step 2: Lancer → échouent**

Run : `python -m pytest tests/test_engine.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.domain.engine'`.

- [ ] **Step 3: Ajouter `FrameResult` à `types.py`**

Ajouter dans `backend/app/domain/types.py` (après `ViolationEvent`) :
```python
@dataclass(frozen=True)
class FrameResult:
    results: list[ComplianceResult]
    events: list[ViolationEvent]
```

- [ ] **Step 4: Implémenter `engine.py`**

`backend/app/domain/engine.py` :
```python
from __future__ import annotations

from app.domain.types import (
    Detection,
    Zone,
    ViolationEvent,
    FrameResult,
    PPE_CLASSES,
)
from app.domain.association import associate
from app.domain.zones import resolve_zone
from app.domain.compliance import evaluate
from app.domain.debounce import DebounceTracker


class ComplianceEngine:
    def __init__(
        self,
        zones: list[Zone],
        confirm_seconds: float = 3.0,
        clear_seconds: float = 3.0,
        cooldown_seconds: float = 30.0,
        camera: str = "cam-1",
        containment_threshold: float = 0.5,
    ):
        self.zones = zones
        self.camera = camera
        self.containment_threshold = containment_threshold
        self.debounce = DebounceTracker(confirm_seconds, clear_seconds, cooldown_seconds)

    def process_frame(self, detections: list[Detection], timestamp: float) -> FrameResult:
        persons = [d for d in detections if d.cls == "person" and d.track_id is not None]
        ppe = [d for d in detections if d.cls in PPE_CLASSES]
        assoc = associate(persons, ppe, self.containment_threshold)

        results = []
        events = []
        for p in persons:
            present = assoc.get(p.track_id, set())
            zone = resolve_zone(p.bbox, self.zones)
            res = evaluate(p.track_id, present, zone)
            results.append(res)
            if self.debounce.update(p.track_id, res.compliant, timestamp):
                events.append(
                    ViolationEvent(
                        track_id=p.track_id,
                        zone=res.zone,
                        missing=res.missing,
                        timestamp=timestamp,
                        camera=self.camera,
                    )
                )
        return FrameResult(results=results, events=events)
```

- [ ] **Step 5: Lancer toute la suite → tout passe**

Run : `python -m pytest -v`
Expected: PASS (34 tests au total : 10 géométrie + 4 zones + 6 association + 4 conformité + 6 debounce + 5 engine — soit 35 ; le total exact dépend du décompte final, tous verts).

- [ ] **Step 6: Commit**

```bash
git add backend/app/domain/types.py backend/app/domain/engine.py backend/tests/test_engine.py
git commit -m "feat(engine): frame orchestration engine emitting violation events"
```

---

## Self-Review

**Spec coverage (§7 Logique métier) :**
- Association EPI↔personne (géométrie + a priori corporels + plus proche si ambigu) → Task 3 ✅
- Appartenance à une zone (bottom-center → point-dans-polygone → EPI requis hérités) → Task 2 + Task 6 ✅
- Conformité (tous requis présents ? sinon manquants) → Task 4 ✅
- Debounce temporel (N s confirmation, M s effacement, cooldown, par ID) → Task 5 ✅
- Événement `{horodatage, zone, EPI manquants, caméra}` → `ViolationEvent` Task 5/6 ✅
- Tracking (ByteTrack) : **hors périmètre** — les `track_id` sont fournis en entrée (produits par la couche inférence, plan #2). Documenté.
- Floutage RGPD / snapshot : **hors périmètre** (couche service, plan #2). Documenté dans Global Constraints.
- Tests unitaires pytest de la logique (§8) → toutes les tâches ✅

**Placeholder scan :** aucun TODO/TBD ; chaque étape contient le code réel et la commande exacte avec sortie attendue. ✅

**Type consistency :** `BBox`, `Detection`, `Zone`, `ComplianceResult`, `ViolationEvent`, `FrameResult` définis dans `types.py` et réutilisés à l'identique ; `associate` renvoie `dict[int, set[str]]` consommé tel quel par `engine` ; `resolve_zone` renvoie `Zone | None`, `evaluate` accepte `Zone | None`, `DebounceTracker.update` renvoie `bool`. Cohérent. ✅

*Note de suivi : le décompte de tests exact sera confirmé à l'exécution ; l'objectif est « toute la suite verte », pas un nombre figé.*

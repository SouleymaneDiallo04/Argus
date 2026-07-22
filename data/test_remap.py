from __future__ import annotations

from remap import remap_label_lines

# Table {classe Argus -> ID fixe}, partagée par les tests (cf. mapping.yaml).
ARGUS_NAME_TO_ID = {
    "person": 0,
    "helmet": 1,
    "safety-vest": 2,
    "mask": 3,
    "shoes": 4,
}


def test_merge_colored_helmets_to_helmet():
    # CHV : la classe source "blue" doit fusionner vers helmet (ID 1).
    src_names = {0: "blue", 4: "person", 5: "vest"}
    cmap = {"blue": "helmet", "person": "person", "vest": "safety-vest"}
    lines = ["0 0.5 0.3 0.1 0.1"]
    assert remap_label_lines(lines, src_names, cmap, ARGUS_NAME_TO_ID) == ["1 0.5 0.3 0.1 0.1"]


def test_box_coordinates_are_preserved():
    # Seul l'ID de classe change ; les coordonnées de la boîte sont intactes.
    src_names = {5: "vest"}
    cmap = {"vest": "safety-vest"}
    lines = ["5 0.50 0.60 0.20 0.40"]
    assert remap_label_lines(lines, src_names, cmap, ARGUS_NAME_TO_ID) == ["2 0.50 0.60 0.20 0.40"]


def test_drop_removes_the_line():
    # css-data : "NO-Hardhat" -> drop -> la ligne disparaît entièrement.
    src_names = {2: "NO-Hardhat", 5: "Person"}
    cmap = {"NO-Hardhat": "drop", "Person": "person"}
    lines = ["2 0.5 0.5 0.2 0.2", "5 0.1 0.1 0.1 0.1"]
    assert remap_label_lines(lines, src_names, cmap, ARGUS_NAME_TO_ID) == ["0 0.1 0.1 0.1 0.1"]


def test_unknown_class_is_dropped_safely():
    # Une classe absente de la table est jetée (défaut sûr, pas d'erreur).
    src_names = {9: "vehicle"}
    cmap = {"Hardhat": "helmet"}
    lines = ["9 0.5 0.5 0.3 0.3"]
    assert remap_label_lines(lines, src_names, cmap, ARGUS_NAME_TO_ID) == []


def test_mixed_lines_keep_and_drop():
    src_names = {0: "Hardhat", 6: "Safety Cone", 5: "Person"}
    cmap = {"Hardhat": "helmet", "Safety Cone": "drop", "Person": "person"}
    lines = [
        "0 0.5 0.2 0.1 0.1",
        "6 0.9 0.9 0.05 0.05",
        "5 0.5 0.6 0.2 0.4",
    ]
    out = remap_label_lines(lines, src_names, cmap, ARGUS_NAME_TO_ID)
    assert out == ["1 0.5 0.2 0.1 0.1", "0 0.5 0.6 0.2 0.4"]


def test_blank_lines_are_ignored():
    src_names = {0: "Hardhat"}
    cmap = {"Hardhat": "helmet"}
    lines = ["", "   ", "0 0.5 0.5 0.2 0.2"]
    assert remap_label_lines(lines, src_names, cmap, ARGUS_NAME_TO_ID) == ["1 0.5 0.5 0.2 0.2"]

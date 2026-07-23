from __future__ import annotations

from remap import build_lookups, remap_dataset, remap_label_file, remap_label_lines

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


def test_build_lookups_from_list_names():
    # data.yaml où `names` est une LISTE : l'index vaut l'ID.
    mapping = {
        "argus_classes": {0: "person", 1: "helmet", 2: "safety-vest", 3: "mask", 4: "shoes"},
        "datasets": {"chv": {"map": {"blue": "helmet", "person": "person", "vest": "safety-vest"}}},
    }
    names = ["blue", "yellow", "white", "red", "person", "vest"]
    src, cmap, a2i = build_lookups(mapping, "chv", names)
    assert src[0] == "blue" and src[4] == "person"
    assert cmap["blue"] == "helmet"
    assert a2i["helmet"] == 1


def test_build_lookups_from_dict_names():
    # data.yaml où `names` est un DICT {id: nom}.
    mapping = {
        "argus_classes": {0: "person", 1: "helmet"},
        "datasets": {"x": {"map": {"Hardhat": "helmet"}}},
    }
    src, cmap, a2i = build_lookups(mapping, "x", {0: "Person", 1: "Hardhat"})
    assert src[1] == "Hardhat"
    assert a2i["helmet"] == 1


def test_remap_label_file_roundtrip(tmp_path):
    src_names = {0: "blue", 4: "person"}
    cmap = {"blue": "helmet", "person": "person"}
    a2i = {"person": 0, "helmet": 1}
    inp = tmp_path / "img1.txt"
    inp.write_text("0 0.5 0.3 0.1 0.1\n4 0.5 0.6 0.2 0.4\n", encoding="utf-8")
    outp = tmp_path / "out1.txt"
    kept = remap_label_file(inp, outp, src_names, cmap, a2i)
    assert kept == 2
    assert outp.read_text(encoding="utf-8").splitlines() == ["1 0.5 0.3 0.1 0.1", "0 0.5 0.6 0.2 0.4"]


def test_remap_label_file_all_dropped_writes_empty(tmp_path):
    # Toutes les boîtes jetées -> fichier vide (image négative valide, pas d'erreur).
    src_names = {2: "NO-Hardhat"}
    cmap = {"NO-Hardhat": "drop"}
    a2i = {"helmet": 1}
    inp = tmp_path / "img2.txt"
    inp.write_text("2 0.5 0.5 0.2 0.2\n", encoding="utf-8")
    outp = tmp_path / "out2.txt"
    kept = remap_label_file(inp, outp, src_names, cmap, a2i)
    assert kept == 0
    assert outp.read_text(encoding="utf-8") == ""


def test_remap_dataset_walks_and_reports_stats(tmp_path):
    mapping = {
        "argus_classes": {0: "person", 1: "helmet", 2: "safety-vest", 3: "mask", 4: "shoes"},
        "datasets": {"sh17": {"map": {"person": "person", "helmet": "helmet", "gloves": "drop"}}},
    }
    names = ["person", "ear", "gloves", "helmet"]  # ids 0..3
    labels = tmp_path / "src" / "labels"
    labels.mkdir(parents=True)
    # id0=person (keep->0), id3=helmet (keep->1), id2=gloves (drop)
    (labels / "img1.txt").write_text(
        "0 0.5 0.5 0.1 0.1\n3 0.2 0.2 0.1 0.1\n2 0.9 0.9 0.05 0.05\n", encoding="utf-8"
    )
    out = tmp_path / "out"
    stats = remap_dataset(tmp_path / "src", out, "sh17", mapping, names)
    assert stats == {"files": 1, "kept": 2, "dropped": 1}
    assert (out / "labels" / "img1.txt").read_text(encoding="utf-8").splitlines() == [
        "0 0.5 0.5 0.1 0.1",
        "1 0.2 0.2 0.1 0.1",
    ]

from __future__ import annotations

"""Harmonisation des labels YOLO : remap des classes source vers la taxonomie Argus.

Le cœur (`remap_label_lines`) est pur et testé. Règle invariante : les coordonnées
des boîtes ne sont JAMAIS modifiées — seul l'ID de classe en tête de ligne change,
ou la ligne est supprimée si la classe vaut "drop" (ou est absente de la table).
"""


def remap_label_lines(
    lines: list[str],
    src_id_to_name: dict[int, str],
    class_map: dict[str, str],
    argus_name_to_id: dict[str, int],
) -> list[str]:
    """Remappe des lignes d'annotation YOLO vers les IDs de classe Argus.

    - `lines` : lignes brutes d'un .txt YOLO ("<id> <x> <y> <w> <h>").
    - `src_id_to_name` : {id source -> nom}, lu depuis le data.yaml du dataset.
    - `class_map` : {nom source -> classe Argus | "drop"}, depuis mapping.yaml.
    - `argus_name_to_id` : {classe Argus -> id Argus fixe}.

    Les boîtes "drop" ou de classe inconnue sont retirées ; les autres gardent
    leurs coordonnées et reçoivent l'ID Argus correspondant.
    """
    out: list[str] = []
    for line in lines:
        parts = line.split()
        if not parts:
            continue
        src_name = src_id_to_name.get(int(parts[0]))
        argus_name = class_map.get(src_name, "drop")
        if argus_name == "drop":
            continue
        argus_id = argus_name_to_id[argus_name]
        out.append(" ".join([str(argus_id), *parts[1:]]))
    return out


def build_lookups(
    mapping: dict,
    dataset_key: str,
    dataset_names,
) -> tuple[dict[int, str], dict[str, str], dict[str, int]]:
    """Construit les 3 tables de correspondance à partir du mapping.yaml chargé
    et des noms de classe du dataset (champ `names` de son data.yaml).

    `dataset_names` peut être une liste (l'index vaut l'ID) ou un dict {id: nom} —
    les deux formes existent selon les datasets.
    """
    argus_name_to_id = {name: cid for cid, name in mapping["argus_classes"].items()}
    class_map = mapping["datasets"][dataset_key]["map"]
    if isinstance(dataset_names, dict):
        src_id_to_name = {int(k): v for k, v in dataset_names.items()}
    else:
        src_id_to_name = {i: name for i, name in enumerate(dataset_names)}
    return src_id_to_name, class_map, argus_name_to_id


def remap_label_file(
    in_path,
    out_path,
    src_id_to_name: dict[int, str],
    class_map: dict[str, str],
    argus_name_to_id: dict[str, int],
) -> int:
    """Lit un .txt YOLO, applique le remap, écrit le résultat, renvoie le nombre
    de boîtes conservées. Un fichier vide (toutes les boîtes jetées) est une image
    négative valide — on l'écrit quand même."""
    from pathlib import Path

    lines = Path(in_path).read_text(encoding="utf-8").splitlines()
    remapped = remap_label_lines(lines, src_id_to_name, class_map, argus_name_to_id)
    text = "\n".join(remapped) + ("\n" if remapped else "")
    Path(out_path).write_text(text, encoding="utf-8")
    return len(remapped)


def remap_dataset(
    src_dir,
    out_dir,
    dataset_key: str,
    mapping: dict,
    dataset_names,
    labels_subdir: str = "labels",
) -> dict[str, int]:
    """Remappe TOUS les .txt d'un dataset vers la taxonomie Argus.

    Parcourt `src_dir/<labels_subdir>/**/*.txt`, réécrit chaque fichier sous
    `out_dir/...` (structure préservée). Renvoie des stats {files, kept, dropped}
    pour l'EDA. Les coordonnées ne changent pas ; seules les classes sont remappées.
    """
    from pathlib import Path

    src, out = Path(src_dir), Path(out_dir)
    src_id_to_name, class_map, argus_name_to_id = build_lookups(
        mapping, dataset_key, dataset_names
    )
    files = kept = dropped = 0
    for txt in sorted((src / labels_subdir).rglob("*.txt")):
        lines = txt.read_text(encoding="utf-8").splitlines()
        n_before = sum(1 for line in lines if line.split())
        remapped = remap_label_lines(lines, src_id_to_name, class_map, argus_name_to_id)
        dest = out / txt.relative_to(src)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("\n".join(remapped) + ("\n" if remapped else ""), encoding="utf-8")
        files += 1
        kept += len(remapped)
        dropped += n_before - len(remapped)
    return {"files": files, "kept": kept, "dropped": dropped}

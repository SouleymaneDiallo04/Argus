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

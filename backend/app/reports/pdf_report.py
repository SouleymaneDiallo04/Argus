from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _pct(rate) -> str:
    return "—" if rate is None else f"{round(rate * 100)}%"


def _table(rows: list[list[str]]) -> Table:
    t = Table(rows)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B0D12")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]))
    return t


def summary_pdf(stats: dict, events: list[dict], meta: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title="Rapport de conformité EPI — Argus")
    styles = getSampleStyleSheet()
    story: list = [
        Paragraph("Rapport de conformité EPI — Argus", styles["Title"]),
        Paragraph(f"Site : {meta.get('site', 'Argus')}", styles["Normal"]),
        Paragraph(
            f"Période : {meta.get('since') or 'début'} → {meta.get('until') or 'maintenant'}",
            styles["Normal"]),
        Paragraph(f"Généré le {meta.get('generated_at', '')}", styles["Normal"]),
        Spacer(1, 12),
    ]

    g = stats.get("global", {})
    v = stats.get("violations", {})
    story += [
        Paragraph("Synthèse", styles["Heading2"]),
        _table([["Indicateur", "Valeur"],
                ["Conformité globale", _pct(g.get("rate"))],
                ["Infractions", str(v.get("total", 0))]]),
        Spacer(1, 12),
    ]

    vbz = v.get("by_zone", {})
    zrows = [["Zone", "Taux", "Infractions"]]
    for z in stats.get("by_zone", []):
        zrows.append([z["zone"], _pct(z.get("rate")), str(vbz.get(z["zone"], 0))])
    story += [Paragraph("Conformité par zone", styles["Heading2"]), _table(zrows),
              Spacer(1, 12)]

    erows = [["Heure", "Zone", "Personne", "EPI manquants"]]
    for e in events:
        erows.append([e.get("ts", ""), e.get("zone") or "—",
                      f"#{e['track_id']}", ", ".join(e.get("missing", []))])
    story += [Paragraph("Journal des infractions", styles["Heading2"]), _table(erows)]

    doc.build(story)
    return buf.getvalue()

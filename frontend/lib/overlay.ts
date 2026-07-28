import type { ComplianceResult, Detection } from "@/lib/types";

export type Box = { x: number; y: number; w: number; h: number; color: string; label: string };

const COLOR = { ok: "#31C46F", bad: "#F0464B", ppe: "#c9a227" };

export function detectionsToBoxes(
  detections: Detection[],
  results: ComplianceResult[],
  scaleX: number,
  scaleY: number
): Box[] {
  const compliantById = new Map<number, boolean>();
  for (const r of results) if (r.track_id != null) compliantById.set(r.track_id, r.compliant);

  return detections.map((d) => {
    const [x1, y1, x2, y2] = d.bbox;
    const isPerson = d.cls === "person";
    let color = COLOR.ppe;
    if (isPerson) {
      const compliant = d.track_id != null ? compliantById.get(d.track_id) : undefined;
      color = compliant === false ? COLOR.bad : COLOR.ok;
    }
    return {
      x: x1 * scaleX,
      y: y1 * scaleY,
      w: (x2 - x1) * scaleX,
      h: (y2 - y1) * scaleY,
      color,
      label: isPerson ? `#${d.track_id ?? "?"}` : d.cls,
    };
  });
}

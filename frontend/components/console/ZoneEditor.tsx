"use client";

import { useRef, useState } from "react";
import { putZones, type ApiZone } from "@/lib/zonesApi";
import { setZoneRisk } from "@/lib/zoneRiskStore";
import { toFramePolygon, buildZoneModel } from "@/lib/zoneGeometry";
import type { ZoneRisk } from "@/lib/priority";

const PPE = ["helmet", "safety-vest", "mask", "shoes"];

export function ZoneEditor({
  videoWidth,
  videoHeight,
  existing,
  onSaved,
  onCancel,
}: {
  videoWidth: number;
  videoHeight: number;
  existing: ApiZone[];
  onSaved: () => void;
  onCancel: () => void;
}) {
  const boxRef = useRef<HTMLDivElement>(null);
  const [points, setPoints] = useState<[number, number][]>([]);
  const [name, setName] = useState("");
  const [ppe, setPpe] = useState<string[]>(["helmet", "safety-vest"]);
  const [risk, setRisk] = useState<ZoneRisk>("high");
  const [saving, setSaving] = useState(false);

  function addPoint(e: React.MouseEvent) {
    const rect = boxRef.current?.getBoundingClientRect();
    if (!rect) return;
    setPoints((p) => [...p, [e.clientX - rect.left, e.clientY - rect.top]]);
  }
  function togglePpe(x: string) {
    setPpe((cur) => (cur.includes(x) ? cur.filter((p) => p !== x) : [...cur, x]));
  }

  async function save() {
    if (points.length < 3 || !name.trim() || !boxRef.current) return;
    setSaving(true);
    try {
      const rect = boxRef.current.getBoundingClientRect();
      const poly = toFramePolygon(points, (videoWidth || rect.width) / rect.width, (videoHeight || rect.height) / rect.height);
      const zone = buildZoneModel(name.trim(), poly, ppe);
      await putZones([...existing, zone]);
      setZoneRisk(zone.name, risk);
      onSaved();
    } finally {
      setSaving(false);
    }
  }

  const path = points.map(([x, y]) => `${x},${y}`).join(" ");

  return (
    <div className="absolute inset-0 z-10 flex">
      <div ref={boxRef} onClick={addPoint} className="relative flex-1 cursor-crosshair bg-black/40">
        <svg className="pointer-events-none absolute inset-0 h-full w-full">
          {points.length > 0 && (
            <polygon points={path} fill="rgba(59,130,246,.15)" stroke="#3B82F6" strokeWidth="2" strokeDasharray="6 4" />
          )}
          {points.map(([x, y], i) => (
            <circle key={i} cx={x} cy={y} r="4" fill="#3B82F6" />
          ))}
        </svg>
        <div className="pointer-events-none absolute left-3 top-3 rounded bg-black/70 px-2.5 py-1 text-[12px] text-ink2">
          Clique pour poser les sommets ({points.length})
        </div>
      </div>
      <aside className="w-72 flex-none border-l border-line bg-s1 p-4">
        <h3 className="mb-3 text-[13px] font-bold">Nouvelle zone</h3>
        <label className="mb-1 block text-[10.5px] font-bold uppercase tracking-[.12em] text-ink3">Nom</label>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="ex. Fonderie·Coulée"
          className="mb-4 w-full rounded-lg border border-line bg-s2 px-3 py-1.5 text-[13px] text-ink" />
        <div className="mb-1 text-[10.5px] font-bold uppercase tracking-[.12em] text-ink3">EPI requis</div>
        <div className="mb-4 flex flex-wrap gap-1.5">
          {PPE.map((p) => (
            <button key={p} onClick={() => togglePpe(p)}
              className={`rounded-md px-2.5 py-1 text-[12px] font-semibold ${ppe.includes(p) ? "bg-brand/20 text-brand" : "bg-s2 text-ink3"}`}>
              {p}
            </button>
          ))}
        </div>
        <div className="mb-1 text-[10.5px] font-bold uppercase tracking-[.12em] text-ink3">Risque</div>
        <div className="mb-5 flex gap-1.5">
          {(["low", "medium", "high"] as ZoneRisk[]).map((r) => (
            <button key={r} onClick={() => setRisk(r)}
              className={`flex-1 rounded-md py-1.5 text-[12px] font-bold ${risk === r ? "bg-warn/20 text-warn" : "bg-s2 text-ink3"}`}>
              {r === "low" ? "Faible" : r === "medium" ? "Moyen" : "Élevé"}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <button disabled={saving || points.length < 3 || !name.trim()} onClick={save}
            className="flex-1 rounded-lg bg-brand px-3 py-2 text-[13px] font-bold text-white disabled:opacity-40">
            {saving ? "…" : "Enregistrer"}
          </button>
          <button onClick={onCancel} className="rounded-lg border border-line2 px-3 py-2 text-[13px] font-bold text-ink hover:bg-s2">
            Annuler
          </button>
        </div>
        <button onClick={() => setPoints([])} className="mt-3 text-[12px] text-ink3 hover:text-ink">Effacer le tracé</button>
      </aside>
    </div>
  );
}

import { detectionsToBoxes } from "./overlay";
import type { Detection, ComplianceResult } from "@/lib/types";

const person = (id: number): Detection => ({ cls: "person", bbox: [10, 20, 30, 60], confidence: 0.9, track_id: id });

test("met la boîte à l'échelle et colore une personne non conforme en rouge", () => {
  const results: ComplianceResult[] = [
    { track_id: 1, zone: "z", required: ["casque"], present: [], missing: ["casque"], compliant: false },
  ];
  const [box] = detectionsToBoxes([person(1)], results, 2, 3);
  expect(box).toMatchObject({ x: 20, y: 60, w: 40, h: 120 });
  expect(box.color).toBe("#F0464B");
  expect(box.label).toBe("#1");
});

test("personne conforme en vert, EPI en ambre", () => {
  const results: ComplianceResult[] = [
    { track_id: 2, zone: "z", required: [], present: [], missing: [], compliant: true },
  ];
  const dets: Detection[] = [person(2), { cls: "casque", bbox: [12, 22, 20, 30], confidence: 0.8, track_id: null }];
  const boxes = detectionsToBoxes(dets, results, 1, 1);
  expect(boxes[0].color).toBe("#31C46F");
  expect(boxes[1].color).toBe("#c9a227");
  expect(boxes[1].label).toBe("casque");
});

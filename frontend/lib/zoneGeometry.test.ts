import { toFramePolygon, buildZoneModel } from "./zoneGeometry";

test("toFramePolygon convertit les points d'affichage en coords frame (entiers)", () => {
  expect(toFramePolygon([[10, 20], [30, 40]], 2, 3)).toEqual([[20, 60], [60, 120]]);
});

test("buildZoneModel construit une ApiZone valide", () => {
  const z = buildZoneModel("Coulée", [[0, 0], [10, 0], [10, 10]], ["helmet", "shoes"]);
  expect(z).toEqual({ name: "Coulée", polygon: [[0, 0], [10, 0], [10, 10]], required_ppe: ["helmet", "shoes"] });
});

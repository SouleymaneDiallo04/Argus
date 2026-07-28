import { severityFor } from "./priority";

test("casque manquant en zone à haut risque = critique", () => {
  expect(severityFor("high", ["casque"])).toBe("crit");
});
test("gilet en zone à haut risque = élevé", () => {
  expect(severityFor("high", ["gilet"])).toBe("high");
});
test("masque en zone bureau (faible) = faible", () => {
  expect(severityFor("low", ["masque"])).toBe("low");
});
test("casque en zone à risque moyen = élevé", () => {
  expect(severityFor("medium", ["casque"])).toBe("high");
});
test("prend le pire EPI manquant", () => {
  expect(severityFor("high", ["masque", "casque"])).toBe("crit");
});

import { scaleY, barWidth, trendSegments } from "./chart";

test("scaleY mappe rate 0..1 vers height..0", () => {
  expect(scaleY(1, 100)).toBe(0);
  expect(scaleY(0, 100)).toBe(100);
  expect(scaleY(0.5, 100)).toBe(50);
});

test("barWidth proportionnel, clampé, 0 si null", () => {
  expect(barWidth(0.5, 200)).toBe(100);
  expect(barWidth(null, 200)).toBe(0);
  expect(barWidth(2, 200)).toBe(200);
});

test("trendSegments coupe les segments sur les null", () => {
  const segs = trendSegments([0.5, null, 1, 1], 300, 100);
  expect(segs).toHaveLength(2);
  expect(segs[0]).toHaveLength(1);
  expect(segs[1]).toHaveLength(2);
});
